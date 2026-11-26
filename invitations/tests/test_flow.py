from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
import threading

import pytest

from invitations.admission import Closed
from invitations.identity import OWNER, RECIPIENT, SECOND
from invitations.policy import DAY, WINDOW, Evidence, Principal, classify
from invitations.service import Pilot
from invitations.worker import Worker


def request(p, who=RECIPIENT):
    p.admission.submit(who, who.email, "1")
    return p.admission.preview(OWNER)[0]["ref"]


def invite(p, who=RECIPIENT):
    ref = p.send(OWNER, who.email)
    p.dispatch(ref)
    return ref, p.local.read_code(ref)


def counts(p, table):
    with p.store.write() as (db, _):
        return db.execute("SELECT count(*) FROM " + table).fetchone()[0]


@pytest.mark.parametrize(
    "facts,expected",
    [
        ((False, True, False, False, True), "valid"),
        ((False, True, False, True, True), "duplicate"),
        ((True, True, False, False, True), "spam"),
        ((False, False, True, False, True), "spam"),
        ((False, False, False, False, True), "correct"),
        ((False, True, False, False, False), "hold"),
        ((False, None, False, False, True), "hold"),
    ],
)
def test_classifier_controls(facts, expected):
    assert classify(Evidence(*facts)).outcome == expected


def test_review(pilot):
    ref = request(pilot)
    for op in ("approve", "deny"):
        with pytest.raises(PermissionError):
            pilot.admission.decide(SECOND, ref, op)
    with pytest.raises(PermissionError):
        pilot.send(RECIPIENT, RECIPIENT.email)
    with pytest.raises(Closed):
        pilot.send(OWNER, RECIPIENT.email)
    pilot.admission.decide(OWNER, ref, "deny")
    assert counts(pilot, "invites") == 0
    assert not pilot.admission.preview(OWNER)
    with pytest.raises(Closed):
        pilot.send(OWNER, RECIPIENT.email, request=ref)
    pilot.admission.decide(OWNER, ref, "reopen")
    with pytest.raises(Closed):
        pilot.admission.decide(OWNER, ref, "approve")
    ref = pilot.admission.preview(OWNER)[0]["ref"]
    pilot.admission.decide(OWNER, ref, "approve")
    assert counts(pilot, "invites") == 0
    delivery = pilot.send(OWNER, RECIPIENT.email, request=ref)
    pilot.dispatch(delivery)
    code = pilot.local.read_code(delivery)
    assert not pilot.redeem(SECOND, code)
    assert not pilot.redeem(Principal("reassigned", RECIPIENT.email), code)
    assert pilot.redeem(RECIPIENT, code)
    assert not pilot.access(RECIPIENT)
    pilot.provision(delivery)
    assert pilot.access(RECIPIENT) == "user"
    pilot.local.revoke(RECIPIENT.subject)
    assert not pilot.access(RECIPIENT)
    pilot.revoke(OWNER, RECIPIENT.email)
    pilot.provision(delivery)
    assert not pilot.redeem(RECIPIENT, code)
    assert pilot.access(OWNER) == "owner"


@pytest.mark.parametrize("age,accept", [(599.999, True), (600, False), (600.001, False)])
def test_exact_expiry_after_restart(pilot, clock, age, accept):
    ref, code = invite(pilot)
    clock.now += age
    restarted = Pilot(pilot.store.directory, OWNER, clock=clock)
    assert restarted.redeem(RECIPIENT, code) is accept
    clock.now += 1000
    restarted.provision(ref)
    assert bool(restarted.access(RECIPIENT)) is accept
    assert counts(pilot, "invites") == 1 and counts(pilot, "strikes") == 0


def test_independent_clocks_and_replacement(pilot, clock):
    first, code = invite(pilot)
    clock.now += 240
    second, code2 = invite(pilot, SECOND)
    clock.now += 360
    assert not pilot.redeem(RECIPIENT, code)
    assert pilot.redeem(SECOND, code2)
    with pytest.raises(Closed):
        pilot.send(OWNER, RECIPIENT.email)
    clock.now += DAY
    new, newcode = invite(pilot)
    assert new != first and newcode != code


def test_cannot_redeem_while_waiting_for_lock(pilot, clock):
    _, code = invite(pilot)
    clock.now += 599
    started = threading.Event()

    def waiting():
        started.set()
        return pilot.redeem(RECIPIENT, code)

    with ThreadPoolExecutor(1) as pool:
        with pilot.store.write():
            result = pool.submit(waiting)
            started.wait()
            clock.now += 1
        assert not result.result()


def test_lost_ack_unknown_and_late_receipt(pilot, clock):
    accepted = clock.now
    pilot.local.lose_next_ack = True
    ref, _ = invite(pilot)
    assert pilot.invitation(RECIPIENT)["state"] == "unknown"
    clock.now += 660
    app = Pilot(pilot.store.directory, OWNER, clock=clock)
    app.dispatch(ref)
    row = app.invitation(RECIPIENT)
    assert row["expires"] == accepted + 600 and row["state"] == "expired"
    app.local.mail_available = False
    ref, _ = invite(app, SECOND)
    app.local.mail_available = True
    app.dispatch(ref)
    assert app.local.receipt(ref) is None  # unknown before acceptance needs owner resolution


def test_abuse_dedup_appeal_and_lift(pilot, clock):
    ref = request(pilot)
    pilot.admission.decide(OWNER, ref, "approve")
    ref = pilot.send(OWNER, RECIPIENT.email, request=ref)

    def sub(typed, key):
        return pilot.admission.submit(RECIPIENT, typed, key).outcome

    assert sub("wrong@example.test", "first") == "correct"
    for win in range(3):
        for target in range(3):
            key = f"{win}-{target}"
            result = sub(f"other{target}@example.test", key)
            assert sub(f"other{target}@example.test", key) == result
            assert result == ("spam" if target == 2 else "correct")
        assert counts(pilot, "strikes") == win + 1
        clock.now += WINDOW
    assert sub(RECIPIENT.email, "self") == "spam"
    assert pilot.invitation(RECIPIENT)["state"] == "revoked"
    assert not pilot.admission.preview(OWNER)
    assert pilot.admission.submit(SECOND, SECOND.email, "new").outcome == "valid"
    pilot.dispatch(ref)
    assert pilot.local.receipt(ref) is None
    pilot.admission.appeal(RECIPIENT)
    pilot.admission.appeal(RECIPIENT)
    assert pilot.admission.appeals(OWNER)[0]["appealed"] == 1
    until = pilot.admission.appeals(OWNER)[0]["until"]
    assert sub(RECIPIENT.email, "retry") == "spam"
    assert pilot.admission.appeals(OWNER)[0]["until"] == until
    pilot.admission.lift(OWNER, RECIPIENT.subject)
    assert not pilot.admission.appeals(OWNER)
    assert sub(RECIPIENT.email, "fresh") == "valid"
    assert counts(pilot, "strikes") == 0


def test_defaults_pause_and_restart(pilot, clock, tmp_path):
    fresh = Pilot(tmp_path / "uninitialized", OWNER, clock=clock)
    assert fresh.held()
    with pytest.raises(Closed):
        fresh.send(OWNER, RECIPIENT.email)
    ref = pilot.send(OWNER, RECIPIENT.email)
    pilot.hold(OWNER, True)
    restarted = Pilot(pilot.store.directory, OWNER, clock=clock)
    restarted.dispatch(ref)
    assert not restarted.local.receipt(ref)
    with pytest.raises(Closed):
        restarted.admission.submit(RECIPIENT, RECIPIENT.email, "x")
    restarted.hold(OWNER, False)
    restarted.dispatch(ref)
    assert restarted.redeem(RECIPIENT, restarted.local.read_code(ref))
    restarted.hold(OWNER, True)
    restarted.provision(ref)
    assert not restarted.access(RECIPIENT)
    assert restarted.access(OWNER) == "owner"


def test_reporting_retry_repair_and_retention(pilot, clock):
    ref, code = invite(pilot)
    worker = Worker(pilot)
    pilot.local.sheets_available = False
    worker.tick()
    assert not pilot.local.sheet()
    pilot.local.sheets_available = True
    clock.now += 1
    worker.tick()
    expected = pilot.local.sheet()
    assert expected and code not in repr(expected) and RECIPIENT.email not in repr(expected)
    with closing(sqlite3.connect(pilot.local.path)) as db, db:
        db.execute("UPDATE sheet SET action='forged'")
    clock.now += 3600
    Worker(Pilot(pilot.store.directory, OWNER, clock=clock)).tick()
    assert pilot.local.sheet() == expected
    assert counts(pilot, "members") == 0 and counts(pilot, "invites") == 1
    assert pilot.local.read_code(ref) is None
    clock.now += 31 * DAY
    worker.tick()
    assert not pilot.local.sheet() and counts(pilot, "invites") == 0


def test_cross_instance_races(pilot, clock):
    other = Pilot(pilot.store.directory, OWNER, clock=clock)
    apps = [pilot, other]
    with ThreadPoolExecutor(10) as pool:
        decisions = list(
            pool.map(
                lambda i: apps[i % 2].admission.submit(RECIPIENT, RECIPIENT.email, str(i)).outcome,
                range(100),
            )
        )
        assert decisions.count("valid") == 1 and decisions.count("duplicate") == 99
        ref = pilot.admission.preview(OWNER)[0]["ref"]
        pilot.admission.decide(OWNER, ref, "approve")
        ids = list(pool.map(lambda i: apps[i % 2].send(OWNER, RECIPIENT.email, request=ref), range(20)))
        assert len(set(ids)) == 1
        list(pool.map(lambda i: apps[i % 2].dispatch(ids[i]), range(20)))
        code = pilot.local.read_code(ids[0])
        assert all(pool.map(lambda i: apps[i % 2].redeem(RECIPIENT, code), range(8)))
        list(pool.map(lambda i: apps[i % 2].provision(ids[0]), range(8)))
    assert counts(pilot, "members") == 1
    with closing(sqlite3.connect(pilot.local.path)) as db:
        assert db.execute("SELECT count(*) FROM mail").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM grants").fetchone()[0] == 1


def test_revoke_fails_closed_and_worker_recovers(pilot, clock, monkeypatch):
    ref, code = invite(pilot)
    assert pilot.redeem(RECIPIENT, code)
    pilot.provision(ref)

    def offline(subject):
        raise TimeoutError("Synthetic provider unavailable")

    monkeypatch.setattr(pilot.local, "revoke", offline)
    with pytest.raises(TimeoutError):
        pilot.revoke(OWNER, RECIPIENT.email)
    assert pilot.local.granted(RECIPIENT.subject, ref)
    assert not pilot.access(RECIPIENT)
    restarted = Pilot(pilot.store.directory, OWNER, clock=clock)
    Worker(restarted).tick()
    assert not restarted.local.granted(RECIPIENT.subject, ref)
    assert counts(restarted, "removals") == 0
