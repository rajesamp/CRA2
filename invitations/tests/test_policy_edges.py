from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing

import pytest

from invitations.admission import Closed
from invitations.identity import OWNER, RECIPIENT, SECOND
from invitations.policy import DAY, WEEK, WINDOW, Principal
from invitations.service import Pilot


def test_fixture_decision_counts(pilot, record_testsuite_property):
    a = pilot.admission
    cases = [
        ("valid", RECIPIENT, RECIPIENT.email),
        ("duplicate", RECIPIENT, RECIPIENT.email),
        ("hold", Principal("different-subject", RECIPIENT.email), RECIPIENT.email),
        ("correct", SECOND, "typo@example.test"),
        ("correct", SECOND, "a@example.test"),
        ("correct", SECOND, "b@example.test"),
        ("spam", SECOND, "c@example.test"),
    ]
    pairs = Counter()
    for index, (expected, actor, typed) in enumerate(cases):
        got = a.submit(actor, typed, str(index))
        pairs[expected, got.outcome] += 1
        assert got.outcome == expected
    preview = a.preview(OWNER)
    assert len(preview) == 1 and preview[0]["email"] == RECIPIENT.email
    with pilot.store.write() as (db, _):
        strikes = db.execute("SELECT count(*) FROM strikes").fetchone()[0]
        assert strikes == 1
    valid = sum(count for (expected, _), count in pairs.items() if expected == "valid")
    spam = sum(count for (expected, _), count in pairs.items() if expected == "spam")
    record_testsuite_property(
        "invitation_system1_controls",
        json.dumps(
            {
                "policy": got.version,
                "total": len(cases),
                "confusion": {f"{e}/{a}": n for (e, a), n in pairs.items()},
                "valid_suppressed": f"{valid - pairs['valid', 'valid']}/{valid}",
                "spam_in_preview": f"{pairs['spam', 'valid']}/{spam}",
                "unnecessary_strikes": max(0, strikes - 1),
            },
            sort_keys=True,
        ),
    )


def test_window_edges_ban_expiry_and_fingerprints(pilot, clock):
    def sub(email, k):
        return pilot.admission.submit(RECIPIENT, email, k)

    sub("wrong@example.test", "warning")

    def window(number):
        for n in range(3):
            result = sub(f"target{n}@example.test", f"{number}-{n}")
        return result.outcome

    assert window(0) == "spam"
    clock.now += WEEK
    assert window(1) == "spam"
    assert not pilot.admission.appeals(OWNER)
    clock.now += WINDOW
    assert window(2) == "spam"
    assert not pilot.admission.appeals(OWNER)
    clock.now += WINDOW
    assert window(3) == "spam"
    deadline = pilot.admission.appeals(OWNER)[0]["until"]
    clock.now = deadline - 0.001
    assert sub(RECIPIENT.email, "early").outcome == "spam"
    clock.now = deadline
    pilot.maintain()
    assert sub(RECIPIENT.email, "late").outcome == "valid"
    with pilot.store.write() as (db, _):
        assert db.execute("SELECT count(*) FROM targets").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM applications").fetchone()[0] == 1


def test_repeated_typo_and_suppressed_report(pilot):
    for i in range(8):
        assert pilot.admission.submit(RECIPIENT, "same@example.test", str(i)).outcome == "correct"
    pilot.maintain()
    rows = [r for r in pilot.local.sheet() if r["action"] == "correct"]
    assert len(rows) == 1 and rows[0]["repeat_count"] == 8 and rows[0]["masked"] == ""
    assert not pilot.admission.appeals(OWNER)
    with pilot.store.write() as (db, _):
        assert db.execute("SELECT count(*) FROM strikes").fetchone()[0] == 0


def test_denial_cooldown_and_send_budget(pilot, clock):
    pilot.admission.submit(RECIPIENT, RECIPIENT.email, "one")
    ref = pilot.admission.preview(OWNER)[0]["ref"]
    pilot.admission.decide(OWNER, ref, "deny")
    clock.now += WEEK - 1
    assert pilot.admission.submit(RECIPIENT, RECIPIENT.email, "two").outcome == "duplicate"
    clock.now += 1
    assert pilot.admission.submit(RECIPIENT, RECIPIENT.email, "three").outcome == "valid"
    for i in range(100):
        pilot.send(OWNER, f"test{i}@example.test")
    with pytest.raises(Closed, match="budget"):
        pilot.send(OWNER, "extra@example.test")
    clock.now += DAY
    assert pilot.send(OWNER, "extra@example.test")


def _parallel_submit(args):
    directory, identity = args
    # Each worker opens the same secret, database and service receipts independently.
    app = Pilot(directory, OWNER)
    return app.admission.submit(RECIPIENT, RECIPIENT.email, identity).outcome


def test_two_processes_share_one_request(tmp_path):
    app = Pilot(tmp_path / "private", OWNER)
    app.hold(OWNER, False)
    with ProcessPoolExecutor(2, mp_context=multiprocessing.get_context("spawn")) as pool:
        outcomes = list(pool.map(_parallel_submit, [(app.store.directory, f"p{n}") for n in range(16)]))
    assert outcomes.count("valid") == 1 and outcomes.count("duplicate") == 15


@pytest.mark.parametrize("already_active", [False, True])
def test_ban_never_resumes_a_pending_grant(pilot, clock, already_active):
    ref = pilot.send(OWNER, RECIPIENT.email)
    pilot.dispatch(ref)
    assert pilot.redeem(RECIPIENT, pilot.local.read_code(ref))
    if already_active:
        pilot.provision(ref)
    pilot.admission.submit(RECIPIENT, "first@example.test", "warn")
    for win in range(3):
        for i in range(3):
            pilot.admission.submit(RECIPIENT, f"wrong{i}@example.test", f"w{win}-{i}")
        clock.now += WINDOW
    assert pilot.admission.appeals(OWNER)
    clock.now += WEEK
    pilot.provision(ref)
    assert bool(pilot.access(RECIPIENT)) is already_active
