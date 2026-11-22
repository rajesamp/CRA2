"""Private same-host accounting for the C2 local test profile."""
from contextlib import closing, contextmanager
import hashlib
import math
import os
from pathlib import Path
import sqlite3
import stat
import time


class CapacityUnavailable(Exception):
    """The local capacity store could not establish whether work is allowed."""


class LocalCapacity:
    application_id = 0x43524332

    def __init__(self, path, *, clock=time.time):
        self.path = Path(path)
        self.clock = clock

    def _private_file(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent = self.path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid()
                or stat.S_IMODE(parent.st_mode) != 0o700):
            raise CapacityUnavailable
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open(self.path, flags, 0o600)
        try:
            file = os.fstat(fd)
            if (not stat.S_ISREG(file.st_mode) or file.st_uid != os.getuid()
                    or stat.S_IMODE(file.st_mode) != 0o600 or file.st_nlink != 1):
                raise CapacityUnavailable
        finally:
            os.close(fd)

    @contextmanager
    def transaction(self):
        try:
            self._private_file()
            uri = self.path.resolve().as_uri() + "?mode=rw"
            with closing(sqlite3.connect(uri, uri=True, timeout=0.25)) as db, db:
                db.execute("PRAGMA trusted_schema=OFF")
                db.execute("BEGIN IMMEDIATE")
                app_id, = db.execute("PRAGMA application_id").fetchone()
                if app_id == 0 and not db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone():
                    db.execute("""CREATE TABLE cooldowns (
                        principal TEXT PRIMARY KEY, expires REAL NOT NULL, reason TEXT NOT NULL)""")
                    db.execute(f"PRAGMA application_id={self.application_id}")
                    db.execute("PRAGMA user_version=1")
                elif app_id != self.application_id or db.execute("PRAGMA user_version").fetchone() != (1,):
                    raise CapacityUnavailable
                yield db
        except (OSError, sqlite3.Error):
            raise CapacityUnavailable from None

    @staticmethod
    def principal_key(client):
        if not isinstance(client, str) or not 1 <= len(client) <= 200:
            raise ValueError("Missing trusted client identity")
        return hashlib.sha256(b"cra2.local.capacity.v1\0" + client.encode()).hexdigest()

    def remaining(self, client):
        key = self.principal_key(client)
        with self.transaction() as db:
            row = db.execute("SELECT expires, reason FROM cooldowns WHERE principal=?", (key,)).fetchone()
            seconds = max(0, math.ceil(row[0] - self.clock())) if row else 0
            return (seconds, row[1]) if seconds else (0, "")

    def pause(self, client, reason, duration):
        key = self.principal_key(client)
        with self.transaction() as db:
            now = self.clock()
            db.execute("DELETE FROM cooldowns WHERE expires <= ?", (now,))
            current = db.execute("SELECT reason FROM cooldowns WHERE principal=?", (key,)).fetchone()
            if current:
                return current[0]
            if db.execute("SELECT COUNT(*) FROM cooldowns").fetchone()[0] >= 5000:
                raise CapacityUnavailable
            db.execute("INSERT INTO cooldowns VALUES (?, ?, ?)", (key, now + duration, reason))
            return reason
