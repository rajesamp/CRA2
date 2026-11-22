"""Local accounting uses synthetic principals, a controlled clock and private files."""
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
import os
import pytest

from week2.abuse import AbuseGate
from week2.capacity import Busy, LocalCapacity


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


def admit(store, client, operation="chat", session="first"):
    receipt = store.reserve(client, session, operation)
    store.accept(receipt)
    return receipt


def test_one_worker_two_waiters_fifo_and_quota_across_sessions(tmp_path):
    store = LocalCapacity(tmp_path / "private" / "ledger.db")
    first = store.try_start(admit(store, "a"))
    assert first
    try:
        second = admit(store, "b", "recovery")
        third = admit(store, "a", session="second")
        for principal, status in (("a", 429), ("c", 503)):
            with pytest.raises(Busy) as rejected:
                store.reserve(principal, "different-tab", "chat")
            assert rejected.value.status == status and rejected.value.retry_after >= 1
        assert store.try_start(second) is None
    finally:
        assert store.finish(first, "completed") == "completed"
    assert store.try_start(third) is None
    worker = store.try_start(second)
    store.cancel(second)
    assert store.try_start(third) is None
    assert store.finish(worker, "completed") == "cancelled"
    assert store.finish(store.try_start(third), "completed") == "completed"


def test_rate_persists_across_restart_and_boundary_is_exclusive(tmp_path):
    path = tmp_path / "private" / "ledger.db"
    now = [100.0]
    store = LocalCapacity(path, clock=lambda: now[0])
    store.cancel(store.reserve("a", "tab", "chat"))  # no handoff, no charge
    for _ in range(4):
        store.cancel(admit(store, "a"))
    restarted = LocalCapacity(path, clock=lambda: now[0])
    for elapsed, hint in ((0, 60), (59.5, 1)):
        now[0] = 100 + elapsed
        with pytest.raises(Busy) as rejected:
            restarted.reserve("a", "other-tab", "recovery")
        assert (rejected.value.status, rejected.value.retry_after) == (429, hint)
    now[0] = 160.0
    assert admit(restarted, "a", "recovery")


def test_deadlines_release_only_stopped_workers(tmp_path):
    now = [10.0]
    store = LocalCapacity(tmp_path / "private" / "ledger.db",
                          clock=lambda: now[0], monotonic=lambda: now[0])
    worker = store.try_start(admit(store, "a"))
    waiting = admit(store, "b", "recovery")
    now[0] += 15
    with pytest.raises(Busy):
        store.try_start(waiting)
    now[0] += 30
    next_review = admit(store, "b")
    assert store.try_start(next_review) is None
    assert store.finish(worker, "completed") == "expired"
    assert store.finish(store.try_start(next_review), "completed") == "completed"


def hold_worker_until_exit(path, control):
    store = LocalCapacity(path)
    worker = store.try_start(admit(store, "child"))
    assert worker
    control.send(worker.receipt)
    control.recv()
    os._exit(0)  # simulate process loss before application cleanup


def test_shared_worker_slot_recovers_only_after_its_process_dies(tmp_path):
    path = tmp_path / "private" / "capacity.db"
    ctx = get_context("spawn")
    parent, child = ctx.Pipe()
    process = ctx.Process(target=hold_worker_until_exit, args=(path, child))
    process.start()
    child.close()
    try:
        assert parent.poll(15)
        original = parent.recv()
        store = LocalCapacity(path)
        next_review = admit(store, "parent", "recovery")
        assert store.try_start(next_review) is None
        parent.send("exit")
        process.join(10)
        assert process.exitcode == 0
        worker = store.try_start(next_review)
        assert worker and store.finish(worker, "completed") == "completed"
        with store.transaction() as db:
            assert db.execute("SELECT state FROM reviews WHERE receipt=?", (original,)).fetchone() == ("failed",)
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
        process.join(10)
