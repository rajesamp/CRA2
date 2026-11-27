"""Owner-authenticated rehearsal routes. All applicant roles and effects are simulated."""

from html import escape
import secrets
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse

from .app import create_app
from .firestore_sessions import FirestoreSessions
from .google import Settings
from .rehearsal_store import OTHER_APPLICANT, RECIPIENT, ActionRejected, CaseMissing, Rehearsals
from .serve import serve
from .sessions import session_store_from_env

MAX_FORM_BYTES = 1024


def page(title, content, *, status=200):
    return HTMLResponse(
        f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{title}</title>'
        f'<main><h1>{title}</h1>{content}</main></html>',
        status_code=status,
    )


def action_form(path, caption, fields=""):
    return f'<form method="post" action="{path}">{fields}<button>{caption}</button></form>'


def case_call(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except CaseMissing:
        raise HTTPException(404, "Rehearsal case unavailable") from None
    except ActionRejected:
        raise HTTPException(409, "This simulated action is unavailable or the code is invalid") from None


def case_page(path, row, now):
    phase = row["phase"]
    receipts = int("receipt_id" in row)
    label = "expired" if phase == "sent" and now >= row["redeem_by"] else phase
    content = [
        '<p>Only the signed-in owner can use this rehearsal. Recipient and applicant are synthetic roles.</p>',
        f'<p>Request status: <strong>{escape(label)}</strong></p>',
    ]
    if phase == "requested":
        content.append(action_form(f"{path}/approve", "Approve synthetic request"))
    if phase == "approved":
        content.append(action_form(f"{path}/send", "Send synthetic invitation"))
    if phase == "sent" and row["sent_at"] <= now < row["redeem_by"]:
        code = escape(row["mailbox_code"])
        expiry = escape(row["redeem_by"].isoformat())
        fields = (
            f'<label>Simulated actor <select name="actor"><option value="{RECIPIENT}">Recipient</option>'
            f'<option value="{OTHER_APPLICANT}">Other applicant</option></select></label> '
            '<label>Invitation code <input name="code" required maxlength="32" autocomplete="off"></label> '
        )
        content.extend((
            f'<section><h2>Synthetic mailbox</h2><p>Invitation code: <code>{code}</code></p>'
            f'<p>Redeem before <time>{expiry}</time> (UTC).</p></section>',
            action_form(f"{path}/redeem", "Redeem synthetic invitation", fields),
        ))
    if phase in ("sent", "redeemed"):
        content.append(action_form(f"{path}/revoke", "Revoke synthetic access"))
    content.extend((
        f'<p><a href="{path}/workspace/{RECIPIENT}">Check simulated recipient access</a></p>',
        f'<section><h2>Rehearsal report</h2><p>Synthetic deliveries: {receipts}</p>'
        '<p>Real deliveries: 0 · External grants: 0</p></section>',
        '<p><a href="/rehearsal">Start another rehearsal</a></p>',
    ))
    return page("Synthetic invitation rehearsal", "".join(content))


async def redemption_fields(request):
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/x-www-form-urlencoded":
        raise HTTPException(415, "Use the rehearsal form")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_FORM_BYTES:
            raise HTTPException(413, "Rehearsal form is too large")
        body.extend(chunk)
    try:
        fields = parse_qs(body.decode("utf-8"), strict_parsing=True, max_num_fields=2)
        if set(fields) == {"actor", "code"}:
            actor, code = fields["actor"], fields["code"]
            if len(actor) == len(code) == 1 and len(code[0]) == 32:
                return actor[0], code[0]
    except ValueError:
        pass
    raise HTTPException(400, "Invalid rehearsal form")


def rehearsal_routes(store, owner, scope):
    router = APIRouter(prefix="/rehearsal")

    @router.get("")
    def index(principal=Depends(owner)):
        path = f"/rehearsal/{secrets.token_urlsafe(16)}/request"
        return page("Synthetic invitation rehearsal", action_form(path, "Create synthetic request"))

    @router.get("/{case_id}")
    def show(case_id: str, principal=Depends(owner)):
        row = case_call(store.read, principal, scope, case_id)
        return case_page(f"/rehearsal/{case_id}", row, store.now())

    @router.get("/{case_id}/workspace/{actor}")
    def workspace(case_id: str, actor: str, principal=Depends(owner)):
        row = case_call(store.read, principal, scope, case_id)
        allowed = actor == RECIPIENT and row["phase"] == "redeemed"
        result = "Simulated recipient access granted" if allowed else "Simulated recipient access denied"
        return page(result, f'<p><a href="/rehearsal/{case_id}">Return to rehearsal</a></p>',
                    status=200 if allowed else 403)

    @router.post("/{case_id}/redeem")
    async def redeem(case_id: str, request: Request, principal=Depends(owner)):
        actor, code = await redemption_fields(request)
        await run_in_threadpool(case_call, store.apply, principal, scope, case_id, "redeem",
                                actor=actor, code=code)
        return RedirectResponse(f"/rehearsal/{case_id}", status_code=303)

    @router.post("/{case_id}/{action}")
    def change(case_id: str, action: str, principal=Depends(owner)):
        if action == "request":
            case_call(store.request, principal, scope, case_id)
        elif action in ("approve", "send", "revoke"):
            case_call(store.apply, principal, scope, case_id, action)
        else:
            raise HTTPException(404, "Unknown rehearsal action")
        return RedirectResponse(f"/rehearsal/{case_id}", status_code=303)

    return router


def create_rehearsal_app(settings, sessions, store, **kwargs):
    if settings.mode != "enrolled":
        raise ValueError("The rehearsal requires an explicitly enrolled owner")
    return create_app(
        settings, sessions, owner_routes=lambda owner, scope: rehearsal_routes(store, owner, scope),
        **kwargs,
    )


def from_env():
    settings = Settings.from_env()
    if settings.mode != "enrolled":
        raise ValueError("The rehearsal requires an explicitly enrolled owner")
    sessions = session_store_from_env()
    if not isinstance(sessions, FirestoreSessions):
        raise ValueError("The rehearsal requires the durable staging database")
    return create_rehearsal_app(settings, sessions, Rehearsals(sessions.client))


if __name__ == "__main__":
    serve("invitations.staging.rehearsal:from_env")
