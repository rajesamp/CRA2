from concurrent.futures import ThreadPoolExecutor
import json
import math
from time import perf_counter

from invitations.identity import OWNER
from invitations.policy import Principal
from invitations.service import Pilot


def test_thousand_synthetic_accounts(pilot, clock, record_testsuite_property):
    peers = (pilot, Pilot(pilot.store.directory, OWNER, clock=clock))

    def submit(index):
        actor = Principal(f"s{index}", f"u{index}@example.test")
        start = perf_counter()
        outcome = peers[index % 2].admission.submit(actor, actor.email, "one").outcome
        return outcome, 1000 * (perf_counter() - start)

    results = []
    start = perf_counter()
    with ThreadPoolExecutor(8) as pool:
        for minute in range(10):
            results.extend(pool.map(submit, range(minute * 100, (minute + 1) * 100)))
            clock.now += 60
    duration = perf_counter() - start
    assert all(outcome == "valid" for outcome, _ in results)
    assert len(pilot.admission.preview(OWNER)) == 1000
    latencies = sorted(ms for _, ms in results)
    with pilot.store.write() as (db, now):
        assert db.execute("SELECT count(*) FROM invites").fetchone()[0] == 0
        oldest = db.execute("SELECT min(updated) FROM applications").fetchone()[0]
        report_backlog = db.execute("SELECT count(*) FROM events").fetchone()[0]
    metrics = dict(
        accounts=len(results),
        window_seconds=600,
        oldest_age_seconds=now - oldest,
        p95_ms=round(latencies[math.ceil(0.95 * len(results)) - 1], 2),
        measured_per_second=round(len(results) / duration, 2),
        mails=0,
        external_calls=0,
        external_quota_units=0,
        external_cost=0,
        report_backlog=report_backlog,
    )
    record_testsuite_property("invitation_local_load", json.dumps(metrics, sort_keys=True))
