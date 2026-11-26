"""File-backed pilot state. All policy reads and changes share a write transaction."""

from contextlib import contextmanager, closing
from pathlib import Path
import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import tempfile
import time

from cryptography.fernet import Fernet

from .policy import VERSION, WINDOW


def private_key(directory):
    target = directory / "pilot.key"
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=directory) as temp:
            temp.write(secrets.token_bytes(32))
            temp.flush()
            os.fsync(temp.fileno())
            try:
                os.link(temp.name, target)
            except FileExistsError:
                pass
    secret = target.read_bytes()
    if len(secret) != 32:
        raise ValueError("Invalid pilot key")
    return secret


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),held INTEGER NOT NULL, owner_sub TEXT NOT NULL,owner_email TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS applications(email TEXT PRIMARY KEY,subject TEXT NOT NULL,state TEXT NOT NULL,updated REAL NOT NULL,ref TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS warnings(subject TEXT PRIMARY KEY,start REAL, struck INTEGER DEFAULT 0,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS targets(subject TEXT, fingerprint TEXT, PRIMARY KEY(subject,fingerprint));
CREATE TABLE IF NOT EXISTS strikes(subject TEXT,at REAL,PRIMARY KEY(subject,at));
CREATE TABLE IF NOT EXISTS bans(subject TEXT PRIMARY KEY, email TEXT NOT NULL,until REAL NOT NULL,appealed INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS attempts(subject TEXT, kind TEXT, start REAL, count INTEGER,PRIMARY KEY(subject,kind));
CREATE TABLE IF NOT EXISTS seen(subject TEXT,id TEXT, at REAL,outcome TEXT,reason TEXT,PRIMARY KEY(subject,id));
CREATE TABLE IF NOT EXISTS invites(id TEXT PRIMARY KEY,email TEXT NOT NULL,subject TEXT,state TEXT NOT NULL,created REAL NOT NULL,
    digest TEXT NOT NULL, payload BLOB,sent REAL,expires REAL,source TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS outstanding ON invites(email) WHERE state IN ('queued','unknown','sent');
CREATE INDEX IF NOT EXISTS by_recipient ON invites(email,created);
CREATE TABLE IF NOT EXISTS members(subject TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,invite TEXT NOT NULL,state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS removals(subject TEXT PRIMARY KEY,invite TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,at REAL NOT NULL, masked TEXT NOT NULL,action TEXT NOT NULL,
    reason TEXT NOT NULL,source TEXT NOT NULL,version TEXT NOT NULL,ref TEXT NOT NULL,repeat_count INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS event_group ON events(ref,action,reason);
"""


class Store:
    def __init__(self, directory, owner, clock=time.time):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.stat().st_mode & 0o077:
            raise ValueError("Use a private pilot directory (mode 0700)")
        self.clock = clock
        self.secret = private_key(self.directory)
        self.cipher = Fernet(base64.urlsafe_b64encode(self.derive("local mail encryption")))
        self.path = self.directory / "invites.sqlite3"
        with closing(self.connect()) as db:
            db.executescript(SCHEMA)
        with self.write() as (db, _):
            db.execute("INSERT OR IGNORE INTO settings VALUES(1,1,?,?)", (owner.subject, owner.email))
            record = db.execute("SELECT owner_sub,owner_email FROM settings").fetchone()
            if tuple(record) != (owner.subject, owner.email):
                raise ValueError("Pilot owner differs from stored owner")

    def derive(self, purpose):
        return hmac.digest(self.secret, purpose.encode(), "sha256")

    def fingerprint(self, value):
        return hmac.new(
            self.derive("short-lived third-party targets"), value.encode(), hashlib.sha256
        ).hexdigest()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def write(self):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            yield db, self.clock()


def event(db, now, email, action, reason, *, source="interest", ref=""):
    if action in {"duplicate", "hold", "correct", "spam"}:
        # Report a count per policy window, without a per-applicant suppression row.
        ref = "window-" + str(int(now // WINDOW))
        email = ""
        if db.execute(
            "UPDATE events SET repeat_count=repeat_count+1 WHERE ref=? AND action=? AND reason=?",
            (ref, action, reason),
        ).rowcount:
            return
    local, _, domain = email.partition("@")
    masked = f"{local[:1]}***@{domain}" if domain else ""
    db.execute(
        "INSERT INTO events(at,masked,action,reason,source,version,ref) VALUES(?,?,?,?,?,?,?)",
        (now, masked, action, reason, source, VERSION, ref),
    )


def budget(db, key, kind, now, limit, period):
    row = db.execute(
        "SELECT start,count FROM attempts WHERE subject=? AND kind=?", (key, kind)
    ).fetchone()
    if row and now < row["start"] + period:
        if row["count"] >= limit:
            return False
        db.execute("UPDATE attempts SET count=count+1 WHERE subject=? AND kind=?", (key, kind))
    else:
        db.execute("INSERT OR REPLACE INTO attempts VALUES(?,?,?,1)", (key, kind, now))
    return True
