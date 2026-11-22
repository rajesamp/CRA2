"""Local accounting uses synthetic principals, a controlled clock and private files."""
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

from week2.abuse import AbuseGate
from week2.capacity import LocalCapacity


def restart_and_retry(path, principal, now):
    gate = AbuseGate(cooldowns=LocalCapacity(path, clock=lambda: now))
    return gate.remaining(principal), gate.pause(principal, "unavailable")


def test_cooldown_survives_a_process_restart_and_keeps_its_original_expiry(tmp_path):
    path = tmp_path / "private" / "capacity.sqlite3"
    now = [100.0]
    principal = "iap:" + "a" * 64
    other = "iap:" + "b" * 64
    gate = AbuseGate(cooldowns=LocalCapacity(path, clock=lambda: now[0]))
    gate.pause(principal, "sensitive")
    with ProcessPoolExecutor(1, mp_context=get_context("spawn")) as process:
        remaining, decision = process.submit(restart_and_retry, path, principal, 105.0).result(30)
    assert remaining == (10, "sensitive")
    assert decision == {"blocked": True, "reason": "sensitive"}
    assert gate.remaining(other) == (0, "")
    now[0] = 115.0
    assert gate.remaining(principal) == (0, "")
    assert path.stat().st_mode & 0o777 == 0o600
    assert principal.encode() not in path.read_bytes()


def test_cooldown_ledger_unavailable_prevents_work_without_touching_other_files(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "capacity.sqlite3"
    path.write_text("unrelated contents")
    path.chmod(0o600)
    gate = AbuseGate(cooldowns=LocalCapacity(path))
    assert gate.admit("What is this app?", "synthetic-client") == {
        "blocked": True, "reason": "unavailable", "cooldown": True
    }
    assert path.read_text() == "unrelated contents"
