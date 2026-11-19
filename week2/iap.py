"""Signed Google IAP identity for the owner acceptance deployment only."""
from dataclasses import dataclass
import hashlib
import json
import math
import re
import threading
import time

import anyio
import httpx
import jwt
from starlette.responses import JSONResponse

ISSUER = "https://cloud.google.com/iap"
KEYS_URL = "https://www.gstatic.com/iap/verify/public_key-jwk"
KID = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")


class InvalidIdentity(ValueError):
    pass


class OwnerOnly(ValueError):
    pass


class KeysUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class IAPSettings:
    audience: str
    owner_email: str

    def __post_init__(self):
        if not re.fullmatch(r"/projects/[0-9]+/locations/[a-z0-9-]+/services/[a-z][a-z0-9-]{0,62}", self.audience):
            raise ValueError("An exact Cloud Run IAP audience is required")
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", self.owner_email):
            raise ValueError("One owner email is required")
        if len(self.owner_email) > 254:
            raise ValueError("One owner email is required")


@dataclass(frozen=True)
class Principal:
    key: str


class IAPKeys:
    """Bounded public-key cache. Expired keys never survive a failed refresh."""

    def __init__(self, *, client=None, clock=time.monotonic):
        self.client = client or httpx.Client(timeout=3, follow_redirects=False, trust_env=False)
        self.clock = clock
        self.keys = {}
        self.expires = 0.
        self.last_attempt = float("-inf")
        self.lock = threading.Lock()

    def get(self, kid):
        if not isinstance(kid, str) or not KID.fullmatch(kid):
            raise InvalidIdentity("Invalid identity")
        with self.lock:
            now = self.clock()
            if now < self.expires and kid in self.keys:
                return self.keys[kid]
            if now - self.last_attempt < 10:
                if now >= self.expires:
                    raise KeysUnavailable("Identity verification unavailable")
                raise InvalidIdentity("Invalid identity")
            self.last_attempt = now
            try:
                with self.client.stream("GET", KEYS_URL, timeout=3, follow_redirects=False) as response:
                    response.raise_for_status()
                    raw = bytearray()
                    for part in response.iter_bytes():
                        raw.extend(part)
                        if len(raw) > 65536:
                            raise ValueError("Oversized key document")
                    document = json.loads(raw)
                    rows = document["keys"]
                    if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
                        raise ValueError("Invalid key document")
                    keys = {}
                    for row in rows:
                        key_id = row.get("kid")
                        if (not isinstance(key_id, str) or not KID.fullmatch(key_id)
                                or key_id in keys or row.get("kty") != "EC" or row.get("crv") != "P-256"
                                or row.get("alg", "ES256") != "ES256" or row.get("use", "sig") != "sig"
                                or "d" in row):
                            raise ValueError("Invalid public key")
                        keys[key_id] = jwt.PyJWK.from_dict(row, algorithm="ES256").key
                    age = re.search(r"(?:^|,)\s*max-age=(\d+)", response.headers.get("cache-control", ""))
                    ttl = min(int(age[1]), 3600) if age else 300
                    self.keys = keys
                    self.expires = self.clock() + ttl
            except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, jwt.PyJWTError):
                raise KeysUnavailable("Identity verification unavailable") from None
            if kid not in self.keys:
                raise InvalidIdentity("Invalid identity")
            return self.keys[kid]


class IAPVerifier:
    def __init__(self, settings, *, keys=None):
        self.settings = settings
        self.keys = keys or IAPKeys()

    def verify(self, token):
        if not isinstance(token, str) or not 1 <= len(token) <= 8192 or not token.isascii():
            raise InvalidIdentity("Invalid identity")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "ES256" or any(k in header for k in ("crit", "jku", "x5u")):
                raise InvalidIdentity("Invalid identity")
            key = self.keys.get(header.get("kid"))
            claims = jwt.decode(token, key, algorithms=["ES256"], audience=self.settings.audience,
                issuer=ISSUER, leeway=30,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "email"], "strict_aud": True})
            for field in ("iat", "exp"):
                if type(claims[field]) not in (int, float) or not math.isfinite(claims[field]):
                    raise InvalidIdentity("Invalid identity")
            if not 0 < claims["exp"] - claims["iat"] <= 660:
                raise InvalidIdentity("Invalid identity")
            subject, email = claims["sub"], claims["email"]
            if (not isinstance(subject, str) or not 1 <= len(subject) <= 255
                    or not subject.isascii() or any(ord(c) < 33 for c in subject)
                    or not isinstance(email, str) or not email):
                raise InvalidIdentity("Invalid identity")
        except (jwt.PyJWTError, TypeError, KeyError, OverflowError):
            raise InvalidIdentity("Invalid identity") from None
        if email.casefold() != self.settings.owner_email.casefold():
            raise OwnerOnly("Owner acceptance only")
        return Principal("iap:" + hashlib.sha256((ISSUER + "\0" + subject).encode()).hexdigest())


class IAPMiddleware:
    """Protect every HTTP/WebSocket route before Gradio can process a request."""
    def __init__(self, app, verifier):
        self.app, self.verifier = app, verifier

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        if scope["type"] == "http" and scope["path"] == "/healthz" and scope["method"] == "GET":
            return await JSONResponse({"status": "ok"})(scope, receive, send)
        assertions = [value for name, value in scope.get("headers", [])
                      if name.lower() == b"x-goog-iap-jwt-assertion"]
        status = 401
        try:
            if len(assertions) != 1:
                raise InvalidIdentity("Invalid identity")
            principal = await anyio.to_thread.run_sync(self.verifier.verify, assertions[0].decode("ascii"))
        except (InvalidIdentity, UnicodeError):
            pass
        except OwnerOnly:
            status = 403
        except KeysUnavailable:
            status = 503
        else:
            scope.setdefault("state", {})["cra2_principal"] = principal
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        message = "Identity verification unavailable" if status == 503 else "Access denied"
        await JSONResponse({"detail": message}, status_code=status,
                           headers={"Cache-Control": "no-store"})(scope, receive, send)
