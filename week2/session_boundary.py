"""Bind the supported Gradio UI protocol to the verified IAP principal.

Browser session hashes are untrusted. Namespacing every supported state reference
prevents a second invited user from reading or changing the first user's state.
Non-UI APIs (uploads, deep links, component server and event streams) stay closed.
Recheck this protocol boundary when upgrading Gradio.
"""
import hashlib
import json
import re
from urllib.parse import parse_qs, urlencode

from starlette.responses import JSONResponse

from week2.iap import Principal

SESSION = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
BODY_LIMIT = 256 * 1024


def session_key(principal, browser_session):
    if not isinstance(browser_session, str) or not SESSION.fullmatch(browser_session):
        raise ValueError("Invalid session")
    return hashlib.sha256((principal.key + "\0" + browser_session).encode()).hexdigest()


class SessionBoundary:
    def __init__(self, app, demo, presence):
        self.app, self.demo, self.presence = app, demo, presence

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
        await self.app(scope, receive, private_send)

    @staticmethod
    async def reject(scope, receive, send, status):
        await JSONResponse({"detail": "Request not allowed"}, status_code=status,
                           headers={"Cache-Control": "no-store"})(scope, receive, send)
