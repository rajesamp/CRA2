"""Durable synthetic rehearsal records. A write can never grant external access."""

from datetime import UTC, datetime, timedelta
import hmac
import json
import re
import secrets
import time

from google.api_core.exceptions import AlreadyExists, FailedPrecondition, NotFound
from google.cloud import firestore

from .firestore_sessions import RPC_TIMEOUT, storage_errors
from .google import Unavailable
from .sessions import digest

COLLECTION = "cra2_invitation_rehearsals"
RECEIPT_SECONDS = 600
RETENTION = timedelta(days=1)
CASE_ID = re.compile(r"[A-Za-z0-9_-]{22}")
RECIPIENT = "recipient"
OTHER_APPLICANT = "other-applicant"


class CaseMissing(Exception):
    pass


class ActionRejected(Exception):
    pass


class Rehearsals:
    def __init__(self, client, clock=time.time):
        self.client = client
        self.documents = client.collection(COLLECTION)
        self.clock = clock

    def now(self):
        return datetime.fromtimestamp(self.clock(), UTC)

    def document(self, principal, scope, case_id):
        if not CASE_ID.fullmatch(case_id):
            raise CaseMissing()
        return self.documents.document(digest(json.dumps([principal, scope, case_id])))

    def request(self, principal, scope, case_id):
        document = self.document(principal, scope, case_id)
        now = self.now()
        with storage_errors():
            try:
                document.create(
                    {"phase": "requested", "requested_at": now, "expires_at": now + RETENTION},
                    retry=None, timeout=RPC_TIMEOUT,
                )
            except AlreadyExists:
                # Retrying a form submission must not reset a prior rehearsal.
                self._active(document.get(retry=None, timeout=RPC_TIMEOUT).to_dict(), self.now())

    def _active(self, row, now):
        if not row or row["expires_at"] <= now:
            raise CaseMissing()
        return row

    def read(self, principal, scope, case_id):
        document = self.document(principal, scope, case_id)
        with storage_errors():
            snapshot = document.get(retry=None, timeout=RPC_TIMEOUT)
        return self._active(snapshot.to_dict(), self.now())

    def apply(self, principal, scope, case_id, action, *, actor="", code=""):
        document = self.document(principal, scope, case_id)
        with storage_errors():
            for _ in range(3):
                snapshot = document.get(retry=None, timeout=RPC_TIMEOUT)
                now = self.now()
                row = self._active(snapshot.to_dict(), now)
                changes = self._transition(row, action, now, actor, code)
                if not changes:
                    return
                try:
                    document.update(
                        changes, option=self.client.write_option(last_update_time=snapshot.update_time),
                        retry=None, timeout=RPC_TIMEOUT,
                    )
                    return
                except (FailedPrecondition, NotFound):
                    # Reevaluate against the winning write. Never issue a second receipt.
                    continue
        raise Unavailable()

    @staticmethod
    def _transition(row, action, now, actor, code):
        phase = row["phase"]
        if action == "approve" and phase == "requested":
            return {"phase": "approved", "approved_at": now}
        if action == "approve" and phase == "approved":
            return {}
        if action == "send" and "receipt_id" in row:
            return {}
        if action == "send" and phase == "approved":
            return {
                "phase": "sent",
                "receipt_id": secrets.token_urlsafe(16),
                "sent_at": now,
                "redeem_by": now + timedelta(seconds=RECEIPT_SECONDS),
                "mailbox_code": secrets.token_urlsafe(24),
                "expires_at": now + RETENTION,
            }
        if action == "redeem" and (
            phase == "sent" and actor == RECIPIENT and row["sent_at"] <= now < row["redeem_by"]
            and code.isascii() and hmac.compare_digest(code, row["mailbox_code"])
        ):
            return {"phase": "redeemed", "redeemed_at": now, "mailbox_code": firestore.DELETE_FIELD}
        if action == "revoke" and phase in ("sent", "redeemed"):
            return {"phase": "revoked", "revoked_at": now, "mailbox_code": firestore.DELETE_FIELD}
        if action == "revoke" and phase == "revoked":
            return {}
        raise ActionRejected()
