"""Task 16: bounded, team-scoped preferences; no conversations or executable notes."""

import os
import sqlite3
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from cra2.advisor import CATALOG, TEAM_SETTINGS
from week1.responses import guard

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "week2/.local/team-memory.sqlite3"
APP_ID = 0x43524132
MAX_BYTES = 4 * 1024 * 1024
FIELDS = ("team", "service", "high_risk", "freeze_notes", "updated_at", "source")
SCHEMA = """CREATE TABLE preferences (
    team TEXT NOT NULL, service TEXT NOT NULL,
    high_risk INTEGER CHECK(high_risk IN (0, 1)), freeze_notes TEXT,
    updated_at TEXT NOT NULL, source TEXT NOT NULL,
    PRIMARY KEY(team, service)
)"""


class MemoryUnavailable(ValueError):
    """Protected storage failure; never expose paths, SQL, notes or exceptions."""


def _text(value, limit):
    return (isinstance(value, str) and bool(value.strip()) and value == value.strip()
            and len(value) <= limit
            and not any(unicodedata.category(c).startswith("C") for c in value))


class MemoryStore:
    def __init__(self, path=DEFAULT_PATH, *, team=None):
        self.path = Path(path)
        self.team = TEAM_SETTINGS["team"] if team is None else team

    def _validate(self, service):
        guard([self.team, service])
        if not _text(self.team, 100) or service not in CATALOG:
            raise ValueError("Invalid preference identity")
        resolved = self.path.resolve()
        if (self.path.is_symlink() or not any(resolved.is_relative_to(root)
                for root in (ROOT, Path("/tmp").resolve()))):
            raise MemoryUnavailable("memory_unavailable")
        if self.path.exists() and self.path.stat().st_size > MAX_BYTES:
            raise MemoryUnavailable("memory_unavailable")

    def _connect(self, *, create):
        new = False
        if not self.path.exists():
            if not create:
                return None
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                new = True
            except FileExistsError:
                pass
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=0.2)
        try:
            db.execute("PRAGMA trusted_schema=OFF")
            if new:
                with db:
                    db.execute(SCHEMA)
                    db.execute(f"PRAGMA application_id={APP_ID}")
                    db.execute("PRAGMA user_version=1")
            columns = tuple(row[1] for row in db.execute("PRAGMA table_info(preferences)"))
            objects = list(db.execute("SELECT type, name FROM sqlite_master WHERE type != 'index'"))
            if (db.execute("PRAGMA application_id").fetchone()[0] != APP_ID
                    or db.execute("PRAGMA user_version").fetchone()[0] != 1
                    or columns != FIELDS or objects != [("table", "preferences")]
                    or db.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok"
                    or db.execute("SELECT count(*) FROM preferences").fetchone()[0] > 2000):
                raise MemoryUnavailable("memory_unavailable")
            return db
        except Exception:
            db.close()
            raise

    def _record(self, row):
        if row is None:
            return None
        data = dict(zip(FIELDS, row))
        guard(data)
        if (data["team"] != self.team or data["service"] not in CATALOG
                or data["high_risk"] not in (None, 0, 1)
                or (data["freeze_notes"] is not None and not _text(data["freeze_notes"], 500))
                or data["source"] != "explicit_team_preference"
                or not _text(data["updated_at"], 50)):
            raise MemoryUnavailable("memory_unavailable")
        try:
            if datetime.fromisoformat(data["updated_at"]).utcoffset() is None:
                raise ValueError
        except ValueError:
            raise MemoryUnavailable("memory_unavailable") from None
        data["high_risk"] = None if data["high_risk"] is None else bool(data["high_risk"])
        return data

    def read(self, service):
        try:
            self._validate(service)
            db = self._connect(create=False)
            if db is None:
                return None
            with closing(db):
                return self._record(db.execute(
                    "SELECT team,service,high_risk,freeze_notes,updated_at,source FROM preferences WHERE team=? AND service=?",
                    (self.team, service)).fetchone())
        except (OSError, sqlite3.Error, ValueError, TypeError):
            raise MemoryUnavailable("memory_unavailable") from None

    def write(self, service, *, high_risk=None, freeze_notes=None):
        try:
            self._validate(service)
            guard([high_risk, freeze_notes])
            if ((high_risk is None and freeze_notes is None)
                    or (high_risk is not None and type(high_risk) is not bool)
                    or (freeze_notes is not None and not _text(freeze_notes, 500))):
                raise ValueError
            with closing(self._connect(create=True)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                previous = self._record(db.execute(
                    "SELECT team,service,high_risk,freeze_notes,updated_at,source FROM preferences WHERE team=? AND service=?",
                    (self.team, service)).fetchone()) or {}
                if not previous and db.execute("SELECT count(*) FROM preferences").fetchone()[0] >= 2000:
                    raise MemoryUnavailable("memory_unavailable")
                record = {"team": self.team, "service": service,
                          "high_risk": previous.get("high_risk") if high_risk is None else high_risk,
                          "freeze_notes": previous.get("freeze_notes") if freeze_notes is None else freeze_notes,
                          "updated_at": datetime.now(timezone.utc).isoformat(),
                          "source": "explicit_team_preference"}
                guard(record)
                db.execute("""INSERT INTO preferences VALUES (?,?,?,?,?,?)
                    ON CONFLICT(team,service) DO UPDATE SET high_risk=excluded.high_risk,
                    freeze_notes=excluded.freeze_notes,updated_at=excluded.updated_at,source=excluded.source""",
                    tuple(record[field] for field in FIELDS))
                stored = self._record(db.execute(
                    "SELECT team,service,high_risk,freeze_notes,updated_at,source FROM preferences WHERE team=? AND service=?",
                    (self.team, service)).fetchone())
                return stored
        except (OSError, sqlite3.Error, ValueError, TypeError):
            raise MemoryUnavailable("memory_unavailable") from None
