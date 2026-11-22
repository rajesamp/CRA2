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
from starlette.responses import JSONResponse

from week2.capacity import Busy, CapacityUnavailable, REVIEW_GROUP
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
        self.draining = set()

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
        direct_review = None
        if path.startswith("/gradio_api"):
            try:
                if method == "GET" and api_path in {"/info", "/user", "/login_check", "/theme.css"}:
                    pass
                elif method == "GET" and api_path.startswith("/heartbeat/"):
                    scope = dict(scope)
                    scope["path"] = "/gradio_api/heartbeat/" + session_key(principal, api_path[len("/heartbeat/"):])
                    scope["raw_path"] = scope["path"].encode()
                elif method == "GET" and api_path == "/queue/data":
                    query = parse_qs(scope.get("query_string", b"").decode("ascii"), max_num_fields=8)
                    values = query.get("session_hash", [])
                    if len(values) != 1:
                        raise ValueError("Invalid session")
                    scope = dict(scope)
                    scope["query_string"] = urlencode({"session_hash": session_key(principal, values[0])}).encode()
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
                    elif data.get("event_id") is not None:
                        raise ValueError("Browser cannot select an event")
                    if self.capacity is not None and api_path.startswith(("/run/", "/api/")):
                        name = api_path.rsplit("/", 1)[-1]
                        index = data.get("fn_index")
                        if index is None:
                            binding = next((fn for fn in self.demo.fns.values() if fn.api_name == name), None)
                        else:
                            binding = self.demo.fns.get(index) if type(index) is int else None
                        if binding is None or binding.api_name != name or not isinstance(data.get("data"), list):
                            raise ValueError("Invalid callback")
                        if binding.concurrency_id == REVIEW_GROUP:
                            direct_review = ("recovery" if name == "recovery" else "chat", data["session_hash"])
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
        if direct_review is None:
            return await self.app(scope, receive, private_send)
        try:
            await self.run_direct(principal.key, *direct_review, scope, receive, private_send)
        except (Busy, CapacityUnavailable) as error:
            await self.capacity_response(scope, receive, private_send, error)

    @staticmethod
    async def capacity_response(scope, receive, send, error):
        if not isinstance(error, Busy):
            error = Busy(503, 1, "Review capacity is temporarily unavailable.")
        await JSONResponse({"detail": str(error)}, status_code=error.status,
                           headers={"Retry-After": str(error.retry_after), "Cache-Control": "no-store"})(
                               scope, receive, send)

    async def run_direct(self, client, operation, session, scope, receive, send):
        capacity = self.capacity
        receipt = await to_thread.run_sync(capacity.reserve, client, session, operation)
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
                await send(message)
        except asyncio.CancelledError:
            await to_thread.run_sync(capacity.cancel, receipt)
            raise

    @staticmethod
    async def reject(scope, receive, send, status):
        await JSONResponse({"detail": "Request not allowed"}, status_code=status,
                           headers={"Cache-Control": "no-store"})(scope, receive, send)
