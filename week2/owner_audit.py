"""Owner-only local audit storage and CLI. No browser or retrieval read endpoint."""

import argparse
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from week1.responses import guard

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "week2/.local/owner-private/questions.sqlite3"
APP_ID = 0x43524141
FIELDS = ("id", "created_at", "client_hash", "kind", "question", "verdict")
SCHEMA = "CREATE TABLE audit_events (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, client_hash TEXT NOT NULL, kind TEXT NOT NULL, question TEXT NOT NULL, verdict TEXT NOT NULL)"


class AuditUnavailable(ValueError):
    pass


class OwnerAuditStore:
    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path)

    def _path(self, create):
        path = self.path
        resolved = path.resolve()
        if path.is_symlink() or not any(resolved.is_relative_to(root) for root in (ROOT, Path('/tmp').resolve())):
            raise AuditUnavailable("audit_unavailable")
        if create:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.exists():
            parent = path.parent.stat()
            if parent.st_uid != os.getuid() or parent.st_mode & 0o777 != 0o700:
                raise AuditUnavailable("audit_unavailable")
        if path.exists():
            info = path.stat()
            if (not path.is_file() or info.st_uid != os.getuid() or info.st_mode & 0o777 != 0o600
                    or info.st_nlink != 1 or info.st_size > 64 * 1024 * 1024):
                raise AuditUnavailable("audit_unavailable")
        return resolved

    def _connect(self, create=False, readonly=False):
        path = self._path(create)
        new = False
        if not path.exists():
            if not create:
                return None
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                os.fchmod(fd, 0o600)
                os.close(fd)
                new = True
            except FileExistsError:
                self._path(False)
        db = sqlite3.connect(path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True, timeout=.2)
        try:
            db.execute("PRAGMA trusted_schema=OFF")
            if new:
                with db:
                    db.execute(SCHEMA)
                    db.execute(f"PRAGMA application_id={APP_ID}")
                    db.execute("PRAGMA user_version=1")
            if (db.execute("PRAGMA application_id").fetchone()[0] != APP_ID
                    or db.execute("PRAGMA user_version").fetchone()[0] != 1
                    or tuple(row[1] for row in db.execute("PRAGMA table_info(audit_events)")) != FIELDS
                    or list(db.execute("SELECT type,name FROM sqlite_master WHERE type != 'index'")) != [("table", "audit_events")]
                    or db.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok"
                    or db.execute("SELECT count(*) FROM audit_events").fetchone()[0] > 10_000):
                raise AuditUnavailable("audit_unavailable")
            return db
        except Exception:
            db.close()
            raise

    def ensure(self):
        try:
            with closing(self._connect(create=True)):
                pass
        except (OSError, sqlite3.Error, ValueError, TypeError):
            raise AuditUnavailable("audit_unavailable") from None

    def append(self, question, client_hash, kind, verdict):
        try:
            if not isinstance(question, str) or not 1 <= len(question) <= 4000:
                question = "Input withheld"
            try:
                guard(question)
            except ValueError:
                question = "Input withheld: configured credential"
            if (kind not in {"out_of_scope", "suspected_adversarial", "security_unavailable", "sensitive_input"}
                    or len(client_hash) != 64 or any(c not in "0123456789abcdef" for c in client_hash)):
                raise ValueError
            guard(verdict)
            payload = json.dumps(verdict, allow_nan=False, sort_keys=True)
            if len(payload) > 2000:
                raise ValueError
            with closing(self._connect(create=True)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT count(*) FROM audit_events").fetchone()[0] >= 10_000:
                    raise AuditUnavailable("audit_unavailable")
                db.execute("INSERT INTO audit_events(created_at,client_hash,kind,question,verdict) VALUES(?,?,?,?,?)",
                    (datetime.now(timezone.utc).isoformat(), client_hash, kind, question, payload))
        except (OSError, sqlite3.Error, ValueError, TypeError):
            raise AuditUnavailable("audit_unavailable") from None

    def read(self, limit=50):
        try:
            if type(limit) is not int or not 1 <= limit <= 1000:
                raise ValueError
            db = self._connect(readonly=True)
            if db is None:
                return []
            with closing(db):
                rows = db.execute("SELECT id,created_at,client_hash,kind,question,verdict FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            result = [dict(zip(FIELDS, row)) for row in rows]
            for row in result:
                row["verdict"] = json.loads(row["verdict"])
            guard(result)
            return result
        except (OSError, sqlite3.Error, ValueError, TypeError):
            raise AuditUnavailable("audit_unavailable") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH, help="Trusted local owner path, never a chat parameter")
    args = parser.parse_args()
    try:
        print(json.dumps(OwnerAuditStore(args.path).read(args.limit), indent=2, allow_nan=False))
    except AuditUnavailable:
        parser.exit(1, "Owner audit is unavailable; verify local owner permissions and storage.\n")


if __name__ == "__main__":
    main()
