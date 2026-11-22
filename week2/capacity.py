"""Private same-host accounting for the C2 local test profile."""
from contextlib import closing, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import fcntl
import hashlib
from io import FileIO
import math
import os
from pathlib import Path
import sqlite3
import stat
import threading
import time
from uuid import uuid4

REVIEW_GROUP = "cra2-review"
MAX_WAITING = 2
MAX_OUTSTANDING = 2
WINDOW_SECONDS = 60
WINDOW_ADMISSIONS = 4
WAIT_SECONDS = 15
RUN_SECONDS = 45
_work_clock = ContextVar("cra2_work_clock", default=None)


def remaining_budget():
    active = _work_clock.get()
    if active is None:
        return None
    clock, deadline = active
    remaining = deadline - clock()
    if remaining <= 0:
        raise TimeoutError("Review execution time expired")
    return remaining


@contextmanager
def work_budget(clock, deadline):
    token = _work_clock.set((clock, deadline))
    try:
        yield
    finally:
        _work_clock.reset(token)


class Busy(Exception):
    def __init__(self, status, retry_after, detail):
        super().__init__(detail)
        self.status = status
        self.retry_after = max(1, min(WINDOW_SECONDS, math.ceil(retry_after)))


class ExistingReview(Exception):
    def __init__(self, receipt, state, event_id):
        self.receipt, self.state, self.event_id = receipt, state, event_id


@dataclass(frozen=True)
class Worker:
    receipt: str
    lock: FileIO
    deadline: float


class QueuedReview:
    """Handoff between Gradio's queue response and the real synchronous worker."""

    def __init__(self, store, receipt, client, session, operation):
        self.store, self.receipt = store, receipt
        self.client, self.session, self.operation = client, session, operation
        self.ready = threading.Event()

    def run(self, operation, request, invoke):
        if (operation != self.operation or request.username != self.client
                or request.session_hash != self.session):
            raise CapacityUnavailable
        if not self.ready.wait(WAIT_SECONDS):
            raise Busy(503, 1, "The review reservation expired.")
        while (worker := self.store.try_start(self.receipt)) is None:
            time.sleep(0.05)
        outcome = "failed"
        try:
            with work_budget(self.store.monotonic, worker.deadline):
                result = invoke()
                outcome = "completed"
        finally:
            terminal = self.store.finish(worker, outcome)
        if terminal != "completed":
            raise Busy(503, 1, "The review ended before a result was available.")
        return result


class CapacityUnavailable(Exception):
    """The local capacity store could not establish whether work is allowed."""


class LocalCapacity:
    application_id = 0x43524332

    def __init__(self, path, *, clock=time.time, monotonic=time.monotonic):
        self.path = Path(path)
        self.clock = clock
        self.monotonic = monotonic

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
                elif app_id != self.application_id:
                    raise CapacityUnavailable
                version, = db.execute("PRAGMA user_version").fetchone()
                if version == 1:
                    db.execute("""CREATE TABLE reviews (
                        receipt TEXT NOT NULL UNIQUE, principal TEXT NOT NULL, session TEXT NOT NULL,
                        operation TEXT NOT NULL, created REAL NOT NULL, admitted REAL,
                        state TEXT NOT NULL, ended REAL, stop_reason TEXT)""")
                    db.execute("CREATE INDEX reviews_quota ON reviews(principal, admitted)")
                    db.execute("PRAGMA user_version=2")
                    version = 2
                if version == 2:
                    db.execute("ALTER TABLE reviews ADD COLUMN delivery TEXT")
                    db.execute("ALTER TABLE reviews ADD COLUMN event_id TEXT")
                    db.execute("CREATE UNIQUE INDEX review_delivery ON reviews(principal,session,operation,delivery)")
                    db.execute("PRAGMA user_version=3")
                elif version != 3:
                    raise CapacityUnavailable
                try:
                    yield db
                except Busy:
                    # Expiry and orphan collection observed during a refusal still apply.
                    db.commit()
                    raise
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

    def _worker_lock(self):
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open(self.path.with_name(self.path.name + ".worker.lock"), flags, 0o600)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise CapacityUnavailable
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return None
        except BaseException:
            os.close(fd)
            raise
        return FileIO(fd, mode="r+", closefd=True)

    def _expire(self, db, now):
        db.execute("DELETE FROM reviews WHERE ended IS NOT NULL AND ended <= ?", (now - WINDOW_SECONDS,))
        db.execute("""UPDATE reviews SET state='expired', ended=?
                      WHERE state IN ('reserved','waiting') AND created <= ?""", (now, now - WAIT_SECONDS))
        if db.execute("SELECT 1 FROM reviews WHERE state='running' LIMIT 1").fetchone():
            lock = self._worker_lock()
            if lock is not None:
                with lock:
                    db.execute("""UPDATE reviews SET state=COALESCE(stop_reason,'failed'), ended=?
                                  WHERE state='running'""", (now,))

    def reserve(self, client, session, operation, delivery=None):
        """Reserve a handoff before a callback can consume work or a rate token."""
        if operation not in {"chat", "recovery"}:
            raise ValueError("Unexpected review operation")
        principal = self.principal_key(client)
        session_key = hashlib.sha256(session.encode()).hexdigest()
        with self.transaction() as db:
            now = self.clock()
            self._expire(db, now)
            if delivery is not None:
                row = db.execute("""SELECT receipt, state, event_id FROM reviews
                    WHERE principal=? AND session=? AND operation=? AND delivery=?""",
                    (principal, session_key, operation, delivery)).fetchone()
                if row:
                    raise ExistingReview(*row)
            outstanding, = db.execute("""SELECT COUNT(*) FROM reviews
                WHERE principal=? AND ended IS NULL""", (principal,)).fetchone()
            if outstanding >= MAX_OUTSTANDING:
                raise Busy(429, 1, "You already have two reviews in progress. Try again shortly.")
            charges = db.execute("""SELECT COALESCE(admitted, created) FROM reviews
                WHERE principal=? AND (admitted > ? OR state='reserved') ORDER BY 1""",
                (principal, now - WINDOW_SECONDS)).fetchall()
            if len(charges) >= WINDOW_ADMISSIONS:
                raise Busy(429, charges[0][0] + WINDOW_SECONDS - now, "Your review limit has been reached.")
            waiting, = db.execute("SELECT COUNT(*) FROM reviews WHERE state IN ('reserved','waiting')").fetchone()
            if waiting >= MAX_WAITING:
                raise Busy(503, 1, "The review queue is full. Try again shortly.")
            receipt = uuid4().hex
            db.execute("""INSERT INTO reviews(receipt,principal,session,operation,created,state,delivery)
                          VALUES (?, ?, ?, ?, ?, 'reserved', ?)""", (receipt, principal, session_key, operation, now, delivery))
            return receipt

    def accept(self, receipt, event_id=None):
        with self.transaction() as db:
            now = self.clock()
            self._expire(db, now)
            if not db.execute("""UPDATE reviews SET state='waiting', admitted=?, event_id=?
                                 WHERE receipt=? AND state='reserved'""", (now, event_id, receipt)).rowcount:
                raise Busy(503, 1, "The review reservation has expired.")

    def cancel(self, receipt):
        with self.transaction() as db:
            now = self.clock()
            db.execute("DELETE FROM reviews WHERE receipt=? AND state='reserved'", (receipt,))
            db.execute("""UPDATE reviews SET state='cancelled', ended=?
                          WHERE receipt=? AND state='waiting'""", (now, receipt))
            db.execute("""UPDATE reviews SET stop_reason=COALESCE(stop_reason,'cancelled')
                          WHERE receipt=? AND state='running'""", (receipt,))

    def try_start(self, receipt):
        with self.transaction() as db:
            now = self.clock()
            self._expire(db, now)
            row = db.execute("SELECT state FROM reviews WHERE receipt=?", (receipt,)).fetchone()
            if row != ("waiting",):
                raise Busy(503, 1, "The review is no longer waiting. Submit it again if needed.")
            first = db.execute("""SELECT receipt FROM reviews WHERE state='waiting'
                                  ORDER BY admitted, rowid LIMIT 1""").fetchone()
            if first != (receipt,):
                return None
            lock = self._worker_lock()
            if lock is None:
                return None
            try:
                db.execute("UPDATE reviews SET state='running' WHERE receipt=?", (receipt,))
                db.commit()
                return Worker(receipt, lock, self.monotonic() + RUN_SECONDS)
            except BaseException:
                lock.close()
                raise

    def finish(self, worker, outcome):
        """Only the holder calls this, after the underlying work has stopped."""
        if outcome not in {"completed", "failed", "expired", "cancelled"}:
            raise ValueError("Unexpected review outcome")
        try:
            with self.transaction() as db:
                if self.monotonic() >= worker.deadline:
                    outcome = "expired"
                row = db.execute("""UPDATE reviews SET state=COALESCE(stop_reason, ?), ended=?
                                     WHERE receipt=? AND state='running' RETURNING state""",
                                 (outcome, self.clock(), worker.receipt)).fetchone()
                if row is None:
                    raise CapacityUnavailable
                return row[0]
        finally:
            worker.lock.close()
