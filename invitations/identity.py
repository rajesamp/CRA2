"""Loopback-only OIDC fixture. Only seeded .test identities can authenticate."""

import base64
import hashlib
import hmac
import secrets
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import jwt

from .policy import Principal
from .store import budget


OWNER = Principal("pilot-owner", "owner@example.test")
RECIPIENT = Principal("pilot-recipient", "reviewer@example.test")
SECOND = Principal("pilot-second", "second@example.test")
ACCOUNTS = (OWNER, RECIPIENT, SECOND)
ISSUER = "urn:cra2:invitation-pilot:issuer"
AUDIENCE = "cra2-invitation-pilot"
COOKIE = "cra2_invitation_pilot"


def challenge(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


class Login:
    def __init__(self, store):
        self.store = store
        self.signer = Ed25519PrivateKey.from_private_bytes(store.derive("local fixture issuer"))
        with store.write() as (db, _):
            db.execute("""CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,csrf TEXT,address TEXT,
                state TEXT,nonce TEXT,verifier TEXT,code_digest TEXT,pkce TEXT,assertion TEXT,subject TEXT,email TEXT,expires REAL)""")

    def key(self, account):
        return self.store.derive("fixture login " + account.subject).hex()

    def session(self, cookie):
        with self.store.write() as (db, now):
            db.execute("DELETE FROM sessions WHERE expires<=?", (now,))
            row = db.execute("SELECT * FROM sessions WHERE id=?", (cookie,)).fetchone()
            if not row:
                if not budget(db, "loopback", "sessions", now, 2000, 600):
                    raise ValueError("Pilot login capacity reached")
                cookie = secrets.token_urlsafe(32)
                db.execute(
                    "INSERT INTO sessions(id,csrf,expires) VALUES(?,?,?)",
                    (cookie, secrets.token_urlsafe(32), now + 600),
                )
                row = db.execute("SELECT * FROM sessions WHERE id=?", (cookie,)).fetchone()
            return dict(row)

    def start(self, sid, typed):
        with self.store.write() as (db, now):
            db.execute(
                """UPDATE sessions SET address=?,state=?,nonce=?,verifier=?,assertion=NULL,code_digest=NULL,
                subject=NULL,email=NULL,expires=? WHERE id=?""",
                (
                    typed,
                    secrets.token_urlsafe(),
                    secrets.token_urlsafe(),
                    secrets.token_urlsafe(48),
                    now + 300,
                    sid,
                ),
            )

    def authenticate(self, session, key):
        with self.store.write() as (db, now):
            if not session["state"] or not budget(db, "loopback", "fixture-key", now, 80, 600):
                raise ValueError("Sign in again")
            actor = next((a for a in ACCOUNTS if secrets.compare_digest(self.key(a), key)), None)
            if actor is None:
                raise ValueError("Sign in again")
            issued = int(time.time())
            assertion = jwt.encode(
                dict(
                    iss=ISSUER,
                    aud=AUDIENCE,
                    sub=actor.subject,
                    email=actor.email,
                    email_verified=True,
                    nonce=session["nonce"],
                    iat=issued,
                    exp=issued + 180,
                ),
                self.signer,
                algorithm="EdDSA",
            )
            code = secrets.token_urlsafe()
            digest = hashlib.sha256(code.encode()).hexdigest()
            n = db.execute(
                """UPDATE sessions SET code_digest=?,pkce=?,assertion=? WHERE id=? AND state=?
                              AND code_digest IS NULL AND expires>?""",
                (
                    digest,
                    challenge(session["verifier"]),
                    assertion,
                    session["id"],
                    session["state"],
                    now,
                ),
            ).rowcount
            if not n:
                raise ValueError("Sign in again")
            return code

    def verify(self, assertion, nonce):
        claims = jwt.decode(
            assertion,
            self.signer.public_key(),
            algorithms=["EdDSA"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["exp", "iat", "sub", "nonce", "email", "email_verified"]},
        )
        if claims["email_verified"] is not True or not hmac.compare_digest(claims["nonce"], nonce):
            raise ValueError("Invalid identity")
        actor = Principal(claims["sub"], claims["email"])
        if actor not in ACCOUNTS:
            raise ValueError("Unknown synthetic account")
        return actor

    def callback(self, sid, state, code):
        digest = hashlib.sha256(code.encode()).hexdigest()
        with self.store.write() as (db, now):
            row = db.execute(
                "SELECT * FROM sessions WHERE id=? AND state=? AND code_digest=? AND expires>?",
                (sid, state, digest, now),
            ).fetchone()
            if not row or not hmac.compare_digest(challenge(row["verifier"]), row["pkce"]):
                raise ValueError("Sign in again")
            actor = self.verify(row["assertion"], row["nonce"])
            fresh = secrets.token_urlsafe(32)
            db.execute("DELETE FROM sessions WHERE id=?", (sid,))
            db.execute(
                "INSERT INTO sessions(id,csrf,address,subject,email,expires) VALUES(?,?,?,?,?,?)",
                (
                    fresh,
                    secrets.token_urlsafe(32),
                    row["address"],
                    actor.subject,
                    actor.email,
                    now + 3600,
                ),
            )
            return fresh
