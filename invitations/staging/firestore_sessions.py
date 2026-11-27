"""Firestore state for the identity-only staging service."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import secrets
import time

from google.api_core.exceptions import FailedPrecondition, GoogleAPICallError, NotFound, RetryError
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .google import Denied, Unavailable
from .sessions import ATTEMPT_SECONDS, SESSION_SECONDS, Attempt, digest

COLLECTION = "cra2_identity_sessions"
RPC_TIMEOUT = 5


@contextmanager
def storage_errors(*, stale_is_denied=False):
    try:
        yield
    except (GoogleAPICallError, RetryError) as exc:
        if stale_is_denied and isinstance(exc, (FailedPrecondition, NotFound)):
            raise Denied() from None
        raise Unavailable() from None


class FirestoreSessions:
    def __init__(self, client, clock=time.time):
        self.client = client
        self.documents = client.collection(COLLECTION)
        self.clock = clock

    @classmethod
    def connect(cls, project, database):
        return cls(firestore.Client(project=project, database=database))

    def _now(self):
        return datetime.fromtimestamp(self.clock(), UTC)

    def _ref(self, sid):
        return self.documents.document(digest(sid))

    def _read(self, document):
        with storage_errors():
            return document.get(retry=None, timeout=RPC_TIMEOUT)

    def _version(self, snapshot):
        return self.client.write_option(last_update_time=snapshot.update_time)

    def _active(self, row, phase):
        return bool(row and row["phase"] == phase and row["expires_at"] > self._now())

    def start(self, previous, principal, scope):
        sid = secrets.token_urlsafe(32)
        attempt = Attempt(*(secrets.token_urlsafe(32) for _ in range(3)))
        batch = self.client.batch()
        if previous:
            batch.delete(self._ref(previous))
        batch.create(self._ref(sid), {
            "principal": principal,
            "scope": scope,
            "expires_at": self._now() + timedelta(seconds=ATTEMPT_SECONDS),
            "phase": "pending",
            "state": digest(attempt.state),
            "nonce": attempt.nonce,
            "verifier": attempt.verifier,
        })
        with storage_errors():
            batch.commit(retry=None, timeout=RPC_TIMEOUT)
        return sid, attempt

    def consume(self, sid, state, principal, scope):
        if not sid:
            raise Denied()
        document = self._ref(sid)
        snapshot = self._read(document)
        row = snapshot.to_dict()
        if not self._active(row, "pending") or row["state"] != digest(state):
            raise Denied()
        version = self._version(snapshot)
        with storage_errors(stale_is_denied=True):
            if (row["principal"], row["scope"]) != (principal, scope):
                document.delete(option=version, retry=None, timeout=RPC_TIMEOUT)
                raise Denied()
            # Only the writer of this exact document version may exchange the code.
            document.update(
                {
                    "phase": "exchanging",
                    "state": firestore.DELETE_FIELD,
                    "nonce": firestore.DELETE_FIELD,
                    "verifier": firestore.DELETE_FIELD,
                },
                option=version,
                retry=None,
                timeout=RPC_TIMEOUT,
            )
        return row["nonce"], row["verifier"]

    def establish(self, previous, principal, scope):
        sid = secrets.token_urlsafe(32)
        document = self._ref(previous)
        snapshot = self._read(document)
        row = snapshot.to_dict()
        if not self._active(row, "exchanging") or (row["principal"], row["scope"]) != (principal, scope):
            raise Denied()
        batch = self.client.batch()
        batch.create(self._ref(sid), {
            "principal": principal,
            "scope": scope,
            "bound_scope": scope,
            "phase": "bound",
            "expires_at": self._now() + timedelta(seconds=SESSION_SECONDS),
        })
        batch.delete(document, option=self._version(snapshot))
        with storage_errors(stale_is_denied=True):
            batch.commit(retry=None, timeout=RPC_TIMEOUT)
        return sid

    def bound(self, sid, principal, scope):
        if not sid:
            return False
        document = self._ref(sid)
        snapshot = self._read(document)
        row = snapshot.to_dict()
        if not self._active(row, "bound"):
            return False
        if (row["principal"], row["scope"]) == (principal, scope):
            return True
        try:
            with storage_errors(stale_is_denied=True):
                document.delete(option=self._version(snapshot), retry=None, timeout=RPC_TIMEOUT)
        except Denied:
            pass  # A concurrent request already removed the session.
        return False

    def forget(self, sid):
        if sid:
            with storage_errors():
                self._ref(sid).delete(retry=None, timeout=RPC_TIMEOUT)

    def candidate(self, settings):
        if settings.mode != "verify-only":
            raise ValueError("Private verify-only state required")
        query = self.documents.where(
            filter=FieldFilter("bound_scope", "==", settings.scope_key),
        ).select(("phase", "expires_at", "principal"))
        principals = set()
        with storage_errors():
            for snapshot in query.stream(retry=None, timeout=RPC_TIMEOUT):
                row = snapshot.to_dict()
                if self._active(row, "bound"):
                    principals.add(row["principal"])
                    if len(principals) > 1:
                        break
        if len(principals) != 1:
            raise ValueError("Expected exactly one current verified candidate")
        return principals.pop()
