"""Per-instance long-lived connection limits for the C2 local mount."""
import asyncio
from collections import deque
import time

from anyio import to_thread
import orjson
from starlette.responses import StreamingResponse

from week2.capacity import Busy


class CapacityStreams:
    def __init__(self, demo, ledger, *, clock=time.monotonic, idle=60, grace=15):
        self.demo, self.ledger, self.clock = demo, ledger, clock
        self.idle, self.grace = idle, grace
        self.active = set()
        self.activity = {}
        self.interrupted = {}
        self.replacements = {}
        self.orphans = {}
        self.in_delivery = {}
        self.tasks = set()
        self.maximum = 0

    def touch(self, session):
        if session in self.activity:
            self.activity[session] = self.clock()

    def acquire(self, client, session, kind):
        now, key = self.clock(), (session, kind)
        self.interrupted = {k: at for k, at in self.interrupted.items() if now - at < 60}
        self.replacements = {k: times for k, times in self.replacements.items() if times and now - times[-1] < 60}
        if key in self.interrupted:
            recent = self.replacements.setdefault(client, deque())
            while recent and now - recent[0] >= 60:
                recent.popleft()
            if len(recent) >= 4:
                raise Busy(429, 60 - (now - recent[0]), "Please wait before reconnecting.")
            recent.append(now)
        if key in self.active or len(self.active) >= 2:
            raise Busy(503, 1, "The connection limit has been reached.")
        self.active.add(key)
        self.maximum = max(self.maximum, len(self.active))
        self.interrupted.pop(key, None)
        if kind == "data" and session in self.orphans:
            self.orphans.pop(session).cancel()
        self.activity[session] = now

    def release(self, session, kind, *, finished):
        key = (session, kind)
        if key not in self.active:
            return
        self.active.remove(key)
        if not any(s == session for s, _ in self.active):
            self.activity.pop(session, None)
        if finished:
            return
        self.interrupted[key] = self.clock()
        if kind == "data" and session not in self.orphans:
            self.orphans[session] = asyncio.get_running_loop().call_later(
                self.grace, self._start_cleanup, session)

    def _start_cleanup(self, session):
        self.orphans.pop(session, None)
        task = asyncio.create_task(self._abandon(session))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _abandon(self, session):
        self.in_delivery.pop(session, None)
        queue = self.demo._queue
        # Capture the generation of events present at grace expiry. A later
        # submission in this same browser session owns a different receipt.
        ids = tuple(queue.pending_event_ids_session.get(session, ()))
        for event_id in ids:
            await to_thread.run_sync(self.ledger.cancel_event, session, event_id)
            await queue.clean_events(event_id=event_id)
            queue.pending_event_ids_session.get(session, set()).discard(event_id)
        if not queue.pending_event_ids_session.get(session):
            queue.pending_messages_per_session.pop(session, None)

    async def idle_time_left(self, session):
        left = self.idle - (self.clock() - self.activity.get(session, self.clock()))
        if left > 0:
            return left
        if await to_thread.run_sync(self.ledger.session_work, session):
            self.touch(session)
            return self.idle
        return 0

    async def serve(self, client, session, kind, app, scope, receive, send):
        self.acquire(client, session, kind)
        finished = False
        try:
            if kind == "heartbeat":
                started = ended = False
                async def track(message):
                    nonlocal started, ended
                    if message["type"] == "http.response.start":
                        started = True
                    elif message["type"] == "http.response.body" and not message.get("more_body"):
                        ended = True
                    await send(message)
                task = asyncio.create_task(app(scope, receive, track))
                try:
                    while not task.done():
                        remaining = await self.idle_time_left(session)
                        if not remaining:
                            break
                        await asyncio.wait({task}, timeout=remaining)
                    if task.done():
                        await task
                finally:
                    if not task.done():
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                        if started and not ended:
                            await send({"type": "http.response.body", "body": b"", "more_body": False})
                return

            queue = self.demo._queue
            channel = queue.pending_messages_per_session.get(session)
            if channel is None:
                finished = True
                raise Busy(503, 1, "No active review stream is available.")

            async def frames():
                nonlocal finished
                while not queue.stopped:
                    remaining = await self.idle_time_left(session)
                    if not remaining:
                        break
                    msg = self.in_delivery.get(session)
                    if msg is None:
                        try:
                            msg = await asyncio.wait_for(channel.get(), timeout=min(remaining, 10))
                        except asyncio.TimeoutError:
                            yield b'data: {"msg":"heartbeat"}\n\n'
                            continue
                        self.in_delivery[session] = msg
                    yield b"data: " + orjson.dumps(msg.model_dump(), default=str) + b"\n\n"
                    self.in_delivery.pop(session, None)
                    if msg.msg == "process_completed" and msg.event_id:
                        pending = queue.pending_event_ids_session.get(session, set())
                        pending.discard(msg.event_id)
                        if not pending:
                            finished = True
                            break
                yield b'data: {"msg":"close_stream"}\n\n'

            await StreamingResponse(frames(), media_type="text/event-stream")(scope, receive, send)
        finally:
            self.release(session, kind, finished=finished)
