"""Transactional sign-in state contract and the local SQLite implementation."""

import base64
from contextlib import closing, contextmanager
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from typing import Protocol

from .google import Denied

ATTEMPT_SECONDS = 300
SESSION_SECONDS = 900
STAGING_DATABASE = re.compile(r"[a-z][a-z0-9-]{0,54}-staging")


def digest(value):
    return sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Attempt:
    state: str
    nonce: str
    verifier: str

    @property
    def challenge(self):
        return base64.urlsafe_b64encode(sha256(self.verifier.encode()).digest()).rstrip(b"=").decode()


class SessionStore(Protocol):
    def start(self, previous: str, principal: str, scope: str) -> tuple[str, Attempt]: ...
    def consume(self, sid: str, state: str, principal: str, scope: str) -> tuple[str, str]: ...
    def establish(self, previous: str, principal: str, scope: str) -> str: ...
    def bound(self, sid: str, principal: str, scope: str) -> bool: ...
    def forget(self, sid: str) -> None: ...


def session_store_from_env() -> SessionStore:
    directory = os.environ.get("INVITATION_STAGE_STATE_DIR")
    project = os.environ.get("INVITATION_STAGE_FIRESTORE_PROJECT")
    database = os.environ.get("INVITATION_STAGE_FIRESTORE_DATABASE")
    emulator = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if os.environ.get("K_SERVICE") and (directory or emulator):
        raise ValueError("Cloud Run requires staging Firestore without a local or emulator store")
    if project or database:
        if directory or not project or not STAGING_DATABASE.fullmatch(database or ""):
            raise ValueError("Configure the Firestore project and a named database ending in -staging")
        from .firestore_sessions import FirestoreSessions

        return FirestoreSessions.connect(project, database)
    if directory:
        return Sessions(directory)
    raise ValueError("Configure private SQLite or the dedicated staging Firestore database")


def enrollment_candidate(settings, directory):
    """Privileged local read of the sole unexpired, fully verified subject in this probe scope."""
    path = Path(directory)
    if settings.mode != "verify-only" or path.stat().st_mode & 0o077:
        raise ValueError("Private verify-only state required")
    uri = (path / "staging-identity.sqlite3").resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        rows = db.execute(
            """SELECT DISTINCT principal FROM auth WHERE scope=? AND state IS NULL
                             AND expires>? LIMIT 2""",
            (settings.scope_key, time.time()),
        ).fetchall()
    if len(rows) != 1:
        raise ValueError("Expected exactly one current verified candidate")
    return rows[0][0]


class Sessions:
    """A state digest identifies a pending attempt, exchanging marks a claimed callback, and NULL is bound."""

    def __init__(self, directory, clock=time.time):
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.stat().st_mode & 0o077:
            raise ValueError("Use a private directory for staging identity state")
        self.path = directory / "staging-identity.sqlite3"
        self.clock = clock
        with self.write() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS auth(
                sid TEXT PRIMARY KEY, principal TEXT NOT NULL, scope TEXT NOT NULL,
                expires REAL NOT NULL, state TEXT, nonce TEXT, verifier TEXT)""")
            db.execute("CREATE INDEX IF NOT EXISTS auth_expiry ON auth(expires)")

    @contextmanager
    def write(self):
        with closing(sqlite3.connect(self.path, timeout=4)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def start(self, previous, principal, scope):
        sid = secrets.token_urlsafe(32)
        attempt = Attempt(*(secrets.token_urlsafe(32) for _ in range(3)))
        with self.write() as db:
            now = self.clock()
            db.execute("DELETE FROM auth WHERE sid=? OR expires<=?", (digest(previous), now))
            db.execute(
                "INSERT INTO auth VALUES(?,?,?,?,?,?,?)",
                (
                    digest(sid),
                    principal,
                    scope,
                    now + ATTEMPT_SECONDS,
                    digest(attempt.state),
                    attempt.nonce,
                    attempt.verifier,
                ),
            )
        return sid, attempt

    def consume(self, sid, state, principal, scope):
        with self.write() as db:
            row = db.execute(
                """UPDATE auth SET state='exchanging' WHERE sid=? AND state=? AND expires>?
                              RETURNING principal,scope,nonce,verifier""",
                (digest(sid), digest(state), self.clock()),
            ).fetchone()
            matches = row is not None and row[:2] == (principal, scope)
            if row is not None:
                if matches:
                    db.execute("UPDATE auth SET nonce=NULL,verifier=NULL WHERE sid=?", (digest(sid),))
                else:
                    db.execute("DELETE FROM auth WHERE sid=?", (digest(sid),))
        if not matches:
            raise Denied()
        return row[2:]

    def establish(self, previous, principal, scope):
        sid = secrets.token_urlsafe(32)
        with self.write() as db:
            now = self.clock()
            changed = db.execute(
                """DELETE FROM auth WHERE sid=? AND state='exchanging' AND principal=?
                                  AND scope=? AND expires>?""",
                (digest(previous), principal, scope, now),
            ).rowcount
            if not changed:
                raise Denied()
            db.execute(
                "INSERT INTO auth(sid,principal,scope,expires) VALUES(?,?,?,?)",
                (digest(sid), principal, scope, now + SESSION_SECONDS),
            )
        return sid

    def bound(self, sid, principal, scope):
        with self.write() as db:
            row = db.execute(
                "SELECT principal,scope FROM auth WHERE sid=? AND state IS NULL AND expires>?",
                (digest(sid), self.clock()),
            ).fetchone()
            if row == (principal, scope):
                return True
            if row is not None:
                db.execute("DELETE FROM auth WHERE sid=?", (digest(sid),))
            return False

    def forget(self, sid):
        with self.write() as db:
            db.execute("DELETE FROM auth WHERE sid=?", (digest(sid),))
