"""Standalone loopback browser entry point for the synthetic invitation pilot."""

from datetime import datetime, timezone
from html import escape
from urllib.parse import parse_qs
import secrets
import sqlite3

import jwt
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .admission import Busy, Closed, require_owner
from .identity import COOKIE, Login, OWNER
from .policy import Principal, VERSION, address
from .service import Pilot


def page(title, content):
    return HTMLResponse(
        f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)} · CRA2 invitation pilot</title><main><h1>{escape(title)}</h1>{content}</main></html>"
    )


def field(name, label, value="", kind="text"):
    return (
        f'<label>{escape(label)} <input type="{kind}" name="{name}" value="{escape(value, quote=True)}" '
        f'maxlength="254" required></label> '
    )


def form(csrf, op, caption, fields="", **hidden):
    hidden = {"csrf": csrf, "op": op, **hidden}
    values = "".join(
        f'<input type="hidden" name="{k}" value="{escape(str(v), quote=True)}">'
        for k, v in hidden.items()
    )
    return f'<form action="/action" method="post">{values}{fields}<button>{escape(caption)}</button></form>'


def cookie(response, sid):
    response.set_cookie(
        COOKIE, sid, httponly=True, secure=True, samesite="strict", path="/", max_age=3600
    )
    return response


def create_app(directory, *, pilot=None):
    pilot = pilot or Pilot(directory, OWNER)
    login = Login(pilot.store)
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    api.state.pilot = pilot

    @api.exception_handler(sqlite3.OperationalError)
    async def unavailable(req, exc):
        return PlainTextResponse("Invitation storage unavailable", 503, headers={"Retry-After": "5"})

    @api.middleware("http")
    async def boundaries(req, call_next):
        if req.method == "POST" and req.headers.get("origin") != str(req.base_url).rstrip("/"):
            return PlainTextResponse("Invalid origin", 403)
        response = await call_next(req)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "strict-origin",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            }
        )
        return response

    def home(session):
        csrf = session["csrf"]
        if not session["subject"]:
            return page(
                "Request access",
                form(
                    csrf,
                    "start",
                    "Continue to local sign-in",
                    field("email", "Your email", kind="email"),
                ),
            )
        actor = Principal(session["subject"], session["email"])
        html = f"<p>Signed in as {escape(actor.email)}</p>"
        if actor == pilot.owner:
            html += form(
                csrf,
                "pause" if not pilot.held() else "resume",
                "Pause invitations" if not pilot.held() else "Enable local invitations",
            )
            html += "<h2>Owner review</h2>"
            for row in pilot.admission.preview(actor):
                submitted = datetime.fromtimestamp(row["updated"], timezone.utc).isoformat()
                html += f"<p>{escape(row['email'])} · {escape(row['state'])} · {submitted} · verified self · {VERSION}</p>"
                if row["state"] == "pending":
                    html += form(csrf, "approve", "Approve", ref=row["ref"]) + form(
                        csrf, "deny", "Deny", ref=row["ref"]
                    )
                else:
                    html += form(
                        csrf, "send", "Send approved invite", ref=row["ref"], email=row["email"]
                    )
            for row in pilot.admission.denied(actor):
                html += f"<p>{escape(row['email'])} · denied</p>"
                html += form(csrf, "reopen", "Reopen denied request", ref=row["ref"])
            html += "<h2>Direct invitations</h2>" + form(
                csrf,
                "preview-direct",
                "Preview direct invite",
                field("email", "Recipient email", kind="email"),
            )
            html += form(
                csrf,
                "revoke",
                "Revoke access or code",
                field("email", "Address to revoke", kind="email"),
            )
            html += '<p><a href="/report">Private reporting copy</a></p>'
            for row in pilot.admission.appeals(actor):
                html += f"<p>{escape(row['email'])} · {'appealed' if row['appealed'] else 'temporarily banned'}</p>"
                html += form(csrf, "lift", "Lift ban", subject=row["subject"])
        else:
            html += form(
                csrf,
                "interest",
                "Confirm interest",
                field("email", "Your request email", session["address"], "email"),
                ref=secrets.token_urlsafe(),
            )
            inv = pilot.invitation(actor)
            if inv and inv["expires"] is not None:
                deadline = datetime.fromtimestamp(inv["expires"], timezone.utc).isoformat()
                html += f"<p>Invitation {escape(inv['state'])} · deadline {escape(deadline)}</p>"
            html += form(
                csrf, "redeem", "Redeem invitation", field("code", "Invitation code", kind="password")
            )
            html += form(csrf, "appeal", "Submit moderation appeal")
        if pilot.access(actor):
            html += '<p><a href="/workspace">Open pilot workspace</a></p>'
        html += form(csrf, "logout", "Sign out")
        return page("Invitation pilot", html)

    @api.get("/")
    def index(req: Request):
        sess = login.session(req.cookies.get(COOKIE))
        return cookie(home(sess), sess["id"])

    @api.get("/identity")
    def identity(req: Request):
        sess = login.session(req.cookies.get(COOKIE))
        if not sess["state"]:
            return PlainTextResponse("Start sign-in first", 400)
        return page(
            "Local Google identity fixture",
            form(
                sess["csrf"],
                "authenticate",
                "Sign in",
                field("key", "Fixture sign-in key", kind="password"),
            ),
        )

    @api.get("/callback")
    def callback(req: Request, state: str, code: str):
        try:
            sid = login.callback(req.cookies.get(COOKIE), state, code)
        except (ValueError, jwt.InvalidTokenError):
            return PlainTextResponse("Sign in again", 403)
        return cookie(RedirectResponse("/", 303), sid)

    @api.get("/workspace")
    @api.get("/report")
    def protected(req: Request):
        sess = login.session(req.cookies.get(COOKIE))
        if not sess["subject"]:
            return PlainTextResponse("Sign in required", 403)
        actor = Principal(sess["subject"], sess["email"])
        if req.url.path == "/workspace":
            role = pilot.access(actor)
            return (
                page("Pilot workspace", f"<p>Role: {role}</p>")
                if role
                else PlainTextResponse("Access unavailable", 403)
            )
        if actor != pilot.owner:
            return PlainTextResponse("Owner required", 403)
        try:
            after = max(0, int(req.query_params.get("after", "0")))
            if after > 2**63 - 1:
                raise ValueError
        except ValueError:
            return PlainTextResponse("Invalid report cursor", 400)
        rows = pilot.local.sheet(after=after)
        body = "".join(
            "<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row.values()) + "</tr>"
            for row in rows
        )
        head = "<tr>" + "".join(f"<th>{escape(k)}</th>" for k in rows[0]) + "</tr>" if rows else ""
        more = f'<a href="/report?after={rows[-1]["id"]}">Next page</a>' if len(rows) == 100 else ""
        return page("Private reporting copy", "<table>" + head + body + "</table>" + more)

    @api.post("/action")
    async def action(req: Request):
        if req.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            return PlainTextResponse("Use the invitation form", 415)
        data = bytearray()
        async for chunk in req.stream():
            if len(data) + len(chunk) > 4096:
                return PlainTextResponse("Form too large", 413)
            data.extend(chunk)
        try:
            pairs = parse_qs(data.decode(), max_num_fields=8, strict_parsing=True)
            if any(len(v) != 1 for v in pairs.values()):
                raise ValueError("Duplicate form field")
            f = {k: v[0] for k, v in pairs.items()}
            sess = login.session(req.cookies.get(COOKIE))
            if not secrets.compare_digest(f.get("csrf", "").encode(), sess["csrf"].encode()):
                return PlainTextResponse("Refresh the form", 403)
            op = f["op"]
            if op == "start":
                login.start(sess["id"], address(f["email"]))
                return RedirectResponse("/identity", 303)
            if op == "authenticate":
                code = login.authenticate(sess, f["key"])
                return RedirectResponse(f"/callback?state={sess['state']}&code={code}", 303)
            if not sess["subject"]:
                raise PermissionError
            actor = Principal(sess["subject"], sess["email"])
            if op == "logout":
                with pilot.store.write() as (db, _):
                    db.execute("DELETE FROM sessions WHERE id=?", (sess["id"],))
            elif op == "interest":
                decision = pilot.admission.submit(actor, f["email"], f["ref"])
                if decision.reason == "intake_limit":
                    raise Busy("Try again after the intake window")
                msg = (
                    "Use your own signed-in email."
                    if decision.outcome == "correct"
                    else "Request received."
                )
                return page(msg, '<a href="/">Return</a>')
            elif op == "appeal":
                pilot.admission.appeal(actor)
            elif op == "redeem":
                if not pilot.redeem(actor, f["code"]):
                    return page("Invitation unavailable", '<a href="/">Return</a>')
                return page("Setting up access", '<a href="/">Return</a>')
            else:
                require_owner(actor, pilot.owner)
                if op in {"approve", "deny", "reopen"}:
                    pilot.admission.decide(actor, f["ref"], op)
                elif op == "preview-direct":
                    recipient = address(f["email"])
                    return page(
                        "Confirm direct invitation",
                        f"<p>{escape(recipient)}</p>"
                        + form(sess["csrf"], "direct", "Send direct invite", email=recipient),
                    )
                elif op in {"direct", "send"}:
                    pilot.send(actor, f["email"], request=f["ref"] if op == "send" else None)
                elif op == "revoke":
                    pilot.revoke(actor, f["email"])
                elif op == "lift":
                    pilot.admission.lift(actor, f["subject"])
                elif op in {"resume", "pause"}:
                    pilot.hold(actor, op == "pause")
                else:
                    raise ValueError("Unknown action")
        except PermissionError:
            return PlainTextResponse("Owner or signed-in account required", 403)
        except (Closed, Busy) as exc:
            return PlainTextResponse(str(exc), 503, headers={"Retry-After": "60"})
        except (KeyError, ValueError, TypeError):
            return PlainTextResponse("Check the form and try again", 400)
        return RedirectResponse("/", 303)

    return api
