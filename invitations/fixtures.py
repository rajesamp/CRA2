"""Offline service doubles. They never call Google, send mail or grant CRA2 access."""

from contextlib import closing
import sqlite3


class LocalServices:
    def __init__(self, store):
        self.store = store
        self.path = store.directory / "pilot-services.sqlite3"
        self.mail_available = True
        self.lose_next_ack = False
        self.sheets_available = True
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS mail(id TEXT PRIMARY KEY,at REAL,body BLOB);
                CREATE TABLE IF NOT EXISTS grants(subject TEXT PRIMARY KEY,invite TEXT);
                CREATE TABLE IF NOT EXISTS sheet(id INTEGER PRIMARY KEY,at REAL,masked TEXT,action TEXT,
                    reason TEXT,source TEXT,version TEXT,ref TEXT,repeat_count INTEGER);
            """)

    def receipt(self, ref):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT at FROM mail WHERE id=?", (ref,)).fetchone()
            return row[0] if row else None

    def accept(self, ref, sealed_body):
        if not self.mail_available:
            raise TimeoutError("delivery unresolved")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO mail VALUES(?,?,?)", (ref, self.store.clock(), sealed_body)
            )
        if self.lose_next_ack:
            self.lose_next_ack = False
            raise TimeoutError("receipt pending")
        return self.receipt(ref)

    def read_code(self, ref):
        """Test mailbox only. The HTTP app has no endpoint for reading another mailbox."""
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT body FROM mail WHERE id=?", (ref,)).fetchone()
        return self.store.cipher.decrypt(row[0]).decode() if row and row[0] else None

    def grant(self, subject, ref):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR REPLACE INTO grants VALUES(?,?)", (subject, ref))

    def revoke(self, subject):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM grants WHERE subject=?", (subject,))

    def granted(self, subject, ref):
        with closing(sqlite3.connect(self.path)) as db:
            return bool(
                db.execute(
                    "SELECT 1 FROM grants WHERE subject=? AND invite=?", (subject, ref)
                ).fetchone()
            )

    def project(self, rows):
        if not self.sheets_available:
            raise TimeoutError("reporting paused")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany("INSERT OR REPLACE INTO sheet VALUES(?,?,?,?,?,?,?,?,?)", rows)

    def expire(self, now, history):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE mail SET body=NULL WHERE at<=?", (now - 600,))
            db.execute("DELETE FROM mail WHERE at<?", (history,))
            db.execute("DELETE FROM sheet WHERE at<?", (history,))

    def sheet(self, *, after=0, limit=100):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM sheet WHERE id>? ORDER BY id LIMIT ?", (after, limit)
                )
            ]
