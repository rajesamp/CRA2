"""Identity-only ASGI app. No invitation workers, fixture login or workspace routes."""

from contextlib import asynccontextmanager
import os
import sqlite3
import time
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
import httpx

from .google import Denied, GOOGLE_ISSUERS, GoogleIdentity, Settings, Unavailable
from .sessions import Sessions

COOKIE = "__Host-cra2-staging-auth"


def get_cookie(request):
    value = request.cookies.get(COOKIE, "")
    return value if len(value) <= 128 else ""


def set_cookie(response, sid, lifetime):
    response.set_cookie(
        COOKIE, sid, max_age=lifetime, path="/", secure=True, httponly=True, samesite="lax"
    )
    return response


def screen(title, action=None, button=None):
    form = f'<form method="post" action="{action}"><button>{button}</button></form>' if action else ""
    return HTMLResponse(
        f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{title}</title>'
        f"<main><h1>{title}</h1>{form}</main></html>"
    )


def create_app(settings: Settings, sessions: Sessions, *, transport=None, key_clock=time.monotonic):
    client = httpx.Client(transport=transport, trust_env=False, follow_redirects=False, timeout=5)
    identity = GoogleIdentity(settings, client, clock=key_clock)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            client.close()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    host = urlsplit(settings.origin).netloc
    scope = settings.scope_key

    @app.middleware("http")
    async def boundary(request, call_next):
        if request.headers.getlist("host") != [host]:
            response = PlainTextResponse("Invalid host", 400)
        elif request.method == "POST" and request.headers.getlist("origin") != [settings.origin]:
            response = PlainTextResponse("Invalid origin", 403)
        else:
            response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "strict-origin",
                "Content-Security-Policy": "default-src 'none'; form-action 'self' https://accounts.google.com; frame-ancestors 'none'; base-uri 'none'",
                "X-Content-Type-Options": "nosniff",
            }
        )
        return response

    @app.exception_handler(Denied)
    async def denied(request, exc):
        return PlainTextResponse("Identity check denied", 403)

    @app.exception_handler(Unavailable)
    @app.exception_handler(sqlite3.OperationalError)
    async def unavailable(request, exc):
        return PlainTextResponse("Identity check unavailable", 503, headers={"Retry-After": "10"})

    def current_iap(request: Request):
        assertions = request.headers.getlist("x-goog-iap-jwt-assertion")
        if len(assertions) != 1:
            raise Denied()
        return identity.iap(assertions[0])

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def home(request: Request, principal=Depends(current_iap)):
        if sessions.bound(get_cookie(request), principal, scope):
            message = (
                "Enrolled owner verified"
                if settings.mode == "enrolled"
                else "Binding verified for private enrollment"
            )
            return screen(message, "/auth/logout", "End identity session")
        return screen("Verify your Google account", "/auth/start", "Sign in with Google")

    @app.post("/auth/start")
    def start(request: Request, principal=Depends(current_iap)):
        sid, attempt = sessions.start(get_cookie(request), principal, scope)
        destination = identity.authorization_url(attempt.state, attempt.nonce, attempt.challenge)
        return set_cookie(RedirectResponse(destination, 303), sid, 300)

    @app.get("/auth/callback")
    def callback(request: Request, principal=Depends(current_iap)):
        query = request.query_params
        states = query.getlist("state")
        if len(states) != 1 or not 0 < len(states[0]) <= 128:
            raise Denied()
        sid = get_cookie(request)
        nonce, verifier = sessions.consume(sid, states[0], principal, scope)
        codes = query.getlist("code")
        issuer = query.getlist("iss")
        if (
            "error" in query
            or len(codes) != 1
            or not 0 < len(codes[0]) <= 2048
            or not codes[0].isascii()
            or (issuer and (len(issuer) != 1 or issuer[0] not in GOOGLE_ISSUERS))
        ):
            raise Denied()
        identity.bind_code(codes[0], verifier, nonce, principal)
        fresh = sessions.establish(sid, principal, scope)
        return set_cookie(RedirectResponse("/", 303), fresh, 900)

    @app.get("/owner")
    def owner_status(request: Request, principal=Depends(current_iap)):
        if settings.mode != "enrolled" or not sessions.bound(get_cookie(request), principal, scope):
            raise Denied()
        return {"owner_verified": True}

    @app.post("/auth/logout")
    def logout(request: Request, principal=Depends(current_iap)):
        sessions.forget(get_cookie(request))
        return set_cookie(RedirectResponse("/", 303), "", 0)

    return app


def from_env():
    """Explicit local ASGI factory. Absent or invalid configuration prevents startup."""
    settings = Settings.from_env()
    return create_app(settings, Sessions(os.environ["INVITATION_STAGE_STATE_DIR"]))
