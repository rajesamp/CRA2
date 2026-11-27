"""Local transactional sign-in state. No production or invitation tables are opened."""

import base64
from contextlib import closing, contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import secrets
import sqlite3
import time

from .google import Denied


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
                    now + 300,
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
                (digest(sid), principal, scope, now + 900),
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
