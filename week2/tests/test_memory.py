"""Durable storage, identity isolation, corruption and disclosure boundaries."""

import os
import sqlite3
from secrets import token_hex

import pytest

from week2.memory import MemoryStore, MemoryUnavailable


@pytest.fixture
def store(tmp_path):
    return MemoryStore(tmp_path / "memory.sqlite3", team="test-team")


def test_missing_read_does_not_create_database(store):
    assert store.read("checkout-service") is None and not store.path.exists()


def test_write_read_restart_and_partial_update(store):
    result = store.write("checkout-service", high_risk=True)
    assert result["high_risk"] is True
    other = MemoryStore(store.path, team="test-team")
    assert other.read("checkout-service") == result
    updated = other.write("checkout-service", freeze_notes="Verify the calendar with the team.")
    assert updated["high_risk"] is True and updated["freeze_notes"].startswith("Verify")
    assert other.write("checkout-service", high_risk=False)["freeze_notes"] == updated["freeze_notes"]
    assert other.read("checkout-service")["high_risk"] is False
    assert os.stat(store.path).st_mode & 0o777 == 0o600


def test_team_and_service_isolation(store):
    store.write("checkout-service", high_risk=True)
    different = MemoryStore(store.path, team="another-team")
    assert different.read("checkout-service") is None
    different.write("checkout-service", high_risk=False)
    assert store.read("checkout-service")["high_risk"] is True
    assert store.read("auth-service") is None


@pytest.mark.parametrize("kwargs", [{}, {"high_risk": 1}, {"high_risk": "true"},
    {"freeze_notes": " "}, {"freeze_notes": "x" * 501}, {"freeze_notes": "line\nbreak"}])
def test_invalid_records_never_create_storage(store, kwargs):
    with pytest.raises(MemoryUnavailable): store.write("checkout-service", **kwargs)
    assert not store.path.exists()


def test_unknown_service_and_team_injection(store):
    with pytest.raises(MemoryUnavailable): store.write("unknown-service", high_risk=True)
    store.team = "test-team' OR '1'='1"
    store.write("checkout-service", high_risk=True)
    assert MemoryStore(store.path, team="test-team").read("checkout-service") is None


def test_credentials_not_persisted(store, monkeypatch):
    secret = token_hex(24)
    monkeypatch.setenv("GROQ_API_KEY", secret)
    with pytest.raises(MemoryUnavailable): store.write("checkout-service", freeze_notes=secret)
    assert not store.path.exists()


@pytest.mark.parametrize("contents", [b"corrupted database", b""])
def test_existing_unknown_or_corrupt_file_not_reinitialized(store, contents):
    store.path.write_bytes(contents)
    with pytest.raises(MemoryUnavailable): store.read("checkout-service")
    with pytest.raises(MemoryUnavailable): store.write("checkout-service", high_risk=True)
    assert store.path.read_bytes() == contents


def test_locked_database_is_not_empty_memory(store):
    store.write("checkout-service", high_risk=True)
    with sqlite3.connect(store.path) as db:
        db.execute("BEGIN EXCLUSIVE")
        with pytest.raises(MemoryUnavailable): store.read("checkout-service")


def test_unrecognized_schema_and_trigger_fail_closed(store):
    store.write("checkout-service", high_risk=True)
    with sqlite3.connect(store.path) as db:
        db.execute("CREATE TRIGGER surprise AFTER INSERT ON preferences BEGIN SELECT 1; END")
    with pytest.raises(MemoryUnavailable): store.read("checkout-service")


def test_symlink_is_not_followed(store, tmp_path):
    target = tmp_path / "original"
    target.write_text("preserve")
    store.path.symlink_to(target)
    with pytest.raises(MemoryUnavailable): store.write("checkout-service", high_risk=True)
    assert target.read_text() == "preserve"
