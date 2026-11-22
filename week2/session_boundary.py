"""Bind the supported Gradio UI protocol to the verified IAP principal.

Browser session hashes are untrusted. Namespacing every supported state reference
prevents a second invited user from reading or changing the first user's state.
Non-UI APIs (uploads, deep links, component server and event streams) stay closed.
Recheck this protocol boundary when upgrading Gradio.
"""
import asyncio
import hashlib
import json
import re
from urllib.parse import parse_qs, urlencode

from anyio import to_thread
from gradio.server_messages import ProcessCompletedMessage
from starlette.responses import JSONResponse

from week2.capacity import Busy, CapacityUnavailable, ExistingReview, QueuedReview, REVIEW_GROUP, WAIT_SECONDS, work_budget
from week2.capacity_streams import CapacityStreams
from week2.iap import Principal

SESSION = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
BODY_LIMIT = 256 * 1024


def session_key(principal, browser_session):
    if not isinstance(browser_session, str) or not SESSION.fullmatch(browser_session):
        raise ValueError("Invalid session")
    return hashlib.sha256((principal.key + "\0" + browser_session).encode()).hexdigest()


class SessionBoundary:
    def __init__(self, app, demo, presence, capacity=None):
        self.app, self.demo, self.presence = app, demo, presence
        self.capacity = capacity
        self.streams = CapacityStreams(demo, capacity) if capacity is not None else None
        self.draining = set()
        if capacity is not None:
            heavy = {"submit_review", "retry_review", "choose_review", "ui_response", "recovery"}
            helpers = {"publish", "publish_1", "publish_2", "unnamed", "unnamed_1",
                       "_pop_last_user_message", "reset_trace", "undo_trace", "show_identity",
                       "show_identity_1", "clear_activity", "langsmith_view", "langsmith_view_1",
                       "langsmith_view_2", "cooldown", "cooldown_1", "lambda",
                       *(f"lambda_{i}" for i in range(1, 6))}
            if ({f.api_name for f in demo.fns.values() if f.concurrency_id == REVIEW_GROUP} != heavy
                    or {f.api_name for f in demo.fns.values() if f.concurrency_id != REVIEW_GROUP} != helpers):
                raise ValueError("Review callback inventory requires inspection")
            self.bindings = dict(demo.fns)

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        principal = scope.get("state", {}).get("cra2_principal")
        if not isinstance(principal, Principal):
            return await self.reject(scope, receive, send, 401)
        path, method = scope["path"].rstrip("/"), scope["method"]
        api_path = path.removeprefix("/gradio_api")
        review = None
        stream = None
        delivery = None
        if path.startswith("/gradio_api"):
            try:
                if method == "GET" and api_path in {"/info", "/user", "/login_check", "/theme.css"}:
                    pass
                elif method == "GET" and api_path.startswith("/heartbeat/"):
                    scope = dict(scope)
                    session = session_key(principal, api_path[len("/heartbeat/"):])
                    stream = (session, "heartbeat")
                    scope["path"] = "/gradio_api/heartbeat/" + session
                    scope["raw_path"] = scope["path"].encode()
                elif method == "GET" and api_path == "/queue/data":
                    query = parse_qs(scope.get("query_string", b"").decode("ascii"), max_num_fields=8)
                    values = query.get("session_hash", [])
                    if len(values) != 1:
                        raise ValueError("Invalid session")
                    scope = dict(scope)
                    session = session_key(principal, values[0])
                    stream = (session, "data")
                    scope["query_string"] = urlencode({"session_hash": session}).encode()
                elif method == "POST" and (api_path in {"/queue/join", "/cancel"}
                        or re.fullmatch(r"/(?:run|api)/[A-Za-z0-9_-]+", api_path)):
                    body = bytearray()
                    while True:
                        message = await receive()
                        if message["type"] != "http.request":
                            raise ValueError("Invalid request")
                        body.extend(message.get("body", b""))
                        if len(body) > BODY_LIMIT:
                            return await self.reject(scope, receive, send, 413)
                        if not message.get("more_body", False):
                            break
                    data = json.loads(body)
                    if not isinstance(data, dict):
                        raise ValueError("Invalid request")
                    data["session_hash"] = session_key(principal, data.get("session_hash"))
                    if api_path == "/cancel":
                        event_id = data.get("event_id")
                        if not isinstance(event_id, str) or len(event_id) > 128:
                            raise ValueError("Invalid event")
                        event = self.demo._queue.event_ids_to_events.get(event_id)
                        if event is None or event.username != principal.key or event.session_hash != data["session_hash"]:
                            return await self.reject(scope, receive, send, 403)
                        if self.capacity is not None:
                            handoff = getattr(event.request.state, "cra2_queued_review", None)
                            if isinstance(handoff, QueuedReview):
                                await to_thread.run_sync(self.capacity.cancel, handoff.receipt)
                    elif data.get("event_id") is not None:
                        raise ValueError("Browser cannot select an event")
                    if self.capacity is not None and api_path != "/cancel":
                        name = None if api_path == "/queue/join" else api_path.rsplit("/", 1)[-1]
                        index = data.get("fn_index")
                        if index is None and name is not None:
                            binding = next((fn for fn in self.bindings.values() if fn.api_name == name), None)
                        else:
                            binding = self.bindings.get(index) if type(index) is int else None
                        if (binding is None or (name not in {None, "predict"} and binding.api_name != name)
                                or not isinstance(data.get("data"), list)):
                            raise ValueError("Invalid callback")
                        if binding.concurrency_id == REVIEW_GROUP:
                            review = ("recovery" if binding.api_name == "recovery" else "chat", data["session_hash"])
                            self.streams.touch(data["session_hash"])
                            keys = [v.decode("ascii") for k, v in scope["headers"] if k == b"idempotency-key"]
                            first = data["data"][0] if data["data"] else None
                            if isinstance(first, dict) and set(first) == {"cra2_delivery", "value"}:
                                keys.append(first["cra2_delivery"])
                                data["data"][0] = first["value"]
                            if keys:
                                if (len(keys) != 1 or not isinstance(keys[0], str)
                                        or not re.fullmatch(r"[0-9a-f]{32}", keys[0])):
                                    raise ValueError("Invalid delivery ID")
                                delivery = keys[0]
                    encoded = json.dumps(data).encode()
                    original_receive = receive
                    delivered = False
                    async def rewritten_receive():
                        nonlocal delivered
                        if delivered:
                            return await original_receive()
                        delivered = True
                        return {"type": "http.request", "body": encoded, "more_body": False}
                    receive = rewritten_receive
                    scope = dict(scope)
                    scope["headers"] = [(k, v) for k, v in scope["headers"]
                                        if k.lower() not in {b"content-length", b"content-type"}]
                    scope["headers"] += [(b"content-type", b"application/json"), (b"content-length", str(len(encoded)).encode())]
                    self.presence.touch(principal)
                else:
                    return await self.reject(scope, receive, send, 403)
            except (ValueError, UnicodeError, TypeError, RecursionError):
                return await self.reject(scope, receive, send, 400)
            except CapacityUnavailable as error:
                return await self.capacity_response(scope, receive, send, error)
        elif method not in {"GET", "HEAD"}:
            return await self.reject(scope, receive, send, 403)
        if path in {"", "/config"}:
            self.presence.touch(principal)

        async def private_send(message):
            if message["type"] == "http.response.start" and not path.startswith(("/assets/", "/static/", "/svelte/")):
                message = dict(message)
                message["headers"] = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
                message["headers"].append((b"cache-control", b"private, no-store"))
            await send(message)
        try:
            if self.streams is not None and stream:
                return await self.streams.serve(principal.key, *stream, self.app, scope, receive, private_send)
            if review is None:
                return await self.app(scope, receive, private_send)
            handle = self.join_review if api_path == "/queue/join" else self.run_direct
            await handle(principal.key, *review, delivery, scope, receive, private_send)
        except ExistingReview as prior:
            if api_path == "/queue/join":
                if prior.event_id is None:
                    return await self.capacity_response(scope, receive, private_send,
                        Busy(503, 1, "This submission is being accepted. Retry with the same delivery ID."))
                return await JSONResponse({"event_id": prior.event_id})(scope, receive, private_send)
            await JSONResponse({"receipt": prior.receipt, "state": prior.state}, status_code=202)(
                scope, receive, private_send)
        except (Busy, CapacityUnavailable) as error:
            await self.capacity_response(scope, receive, private_send, error)

    @staticmethod
    async def capacity_response(scope, receive, send, error):
        if not isinstance(error, Busy):
            error = Busy(503, 1, "Review capacity is temporarily unavailable.")
        unit = "second" if error.retry_after == 1 else "seconds"
        await JSONResponse({"detail": f"{error} Retry in {error.retry_after} {unit}."}, status_code=error.status,
                           headers={"Retry-After": str(error.retry_after), "Cache-Control": "no-store"})(
                               scope, receive, send)

    async def join_review(self, client, operation, session, delivery, scope, receive, send):
        capacity = self.capacity
        receipt = await to_thread.run_sync(capacity.reserve, client, session, operation, delivery)
        handoff = QueuedReview(capacity, receipt, client, session, operation)
        scope["state"]["cra2_queued_review"] = handoff
        messages = []
        async def capture(message):
            messages.append(message)
        try:
            self.streams.check_delivery(session)
            await self.app(scope, receive, capture)
            status = messages[0]["status"]
            if status == 200:
                payload = json.loads(b"".join(m.get("body", b"") for m in messages))
                event = self.demo._queue.event_ids_to_events.get(payload.get("event_id"))
                if event is None or event.username != client or event.session_hash != session:
                    raise CapacityUnavailable
                await to_thread.run_sync(capacity.accept, receipt, payload["event_id"])
                handoff.event_id = payload["event_id"]
                self.watch_deadlines(handoff, event)
            else:
                await to_thread.run_sync(capacity.cancel, receipt)
                if status == 503:
                    raise Busy(503, 1, "The review queue is full. Try again shortly.")
        except BaseException:
            await to_thread.run_sync(capacity.cancel, receipt)
            raise
        finally:
            handoff.ready.set()
        for message in messages:
            await send(message)

    def watch_deadlines(self, handoff, event):
        loop = asyncio.get_running_loop()
        queue = self.demo._queue
        timer = None

        async def expire(phase):
            if await to_thread.run_sync(self.capacity.expire_event, handoff.receipt, phase):
                queue.send_message(event, ProcessCompletedMessage(success=False, output={
                    "error": "Review time expired. Retry in 1 second.", "status": 503, "retry_after": 1}))
                await queue.clean_events(event_id=event._id)

        def arm(phase, delay):
            nonlocal timer
            if timer:
                timer.cancel()
            if phase != "finished":
                def fire():
                    task = asyncio.create_task(expire(phase))
                    self.draining.add(task)
                    task.add_done_callback(self.draining.discard)
                timer = loop.call_later(delay, fire)
        handoff.notify = lambda phase, delay: loop.call_soon_threadsafe(arm, phase, delay)
        arm("waiting", WAIT_SECONDS)

    async def run_direct(self, client, operation, session, delivery, scope, receive, send):
        capacity = self.capacity
        receipt = await to_thread.run_sync(capacity.reserve, client, session, operation, delivery)
        try:
            await to_thread.run_sync(capacity.accept, receipt)
            while (worker := await to_thread.run_sync(capacity.try_start, receipt)) is None:
                await asyncio.sleep(0.05)
        except BaseException:
            await to_thread.run_sync(capacity.cancel, receipt)
            raise

        async def execute():
            messages = []
            async def capture(message):
                messages.append(message)
            outcome = "failed"
            try:
                scope["state"]["cra2_direct_review"] = operation
                with work_budget(capacity.monotonic, worker.deadline):
                    await self.app(scope, receive, capture)
                if messages and 200 <= messages[0].get("status", 0) < 300:
                    outcome = "completed"
            finally:
                terminal = await to_thread.run_sync(capacity.finish, worker, outcome)
            return terminal, messages

        # A disconnected HTTP caller does not terminate a synchronous Gradio worker.
        # Keep the task and its slot until the callback really returns.
        task = asyncio.create_task(execute())
        self.draining.add(task)
        def forget(done):
            self.draining.discard(done)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(forget)
        try:
            timeout = max(0.0, worker.deadline - capacity.monotonic())
            done, _ = await asyncio.wait({task}, timeout=timeout)
            if not done:
                raise Busy(503, 1, "Review time expired. Check your change and try again.")
            terminal, messages = task.result()
            if terminal in {"expired", "cancelled"}:
                raise Busy(503, 1, "The review ended before its result was available.")
            for message in messages:
                if message["type"] == "http.response.start":
                    message = {**message, "headers": [*message.get("headers", []),
                                                     (b"x-review-receipt", receipt.encode("ascii"))]}
                await send(message)
        except asyncio.CancelledError:
            await to_thread.run_sync(capacity.cancel, receipt)
            raise

    @staticmethod
    async def reject(scope, receive, send, status):
        await JSONResponse({"detail": "Request not allowed"}, status_code=status,
                           headers={"Cache-Control": "no-store"})(scope, receive, send)
