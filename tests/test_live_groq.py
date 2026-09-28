"""Opt-in live repeatability and latency probes, separate from offline regression tests.

Run: CRA2_RUN_LIVE_TESTS=1 uv run pytest -q tests/test_live_groq.py
Set GROQ_API_KEY in the environment or select a dotenv file with CRA2_ENV_FILE.
"""

import json
import os
import time
from pathlib import Path

import pytest

from cra2 import system2
from cra2.advisor import assess

CASES = {
    c["id"]: c
    for c in json.loads(
        (Path(__file__).resolve().parent.parent / "evals" / "cases.json").read_text()
    )
}
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("CRA2_RUN_LIVE_TESTS") != "1"
        or not os.environ.get("GROQ_API_KEY"),
        reason="requires explicit CRA2_RUN_LIVE_TESTS=1 and GROQ_API_KEY",
    ),
]


@pytest.mark.parametrize("case_id", ["CHG-01", "CHG-06", "CHG-16"])
def test_same_change_asked_five_times_gives_same_level_and_comments(case_id):
    answers = set()
    for _ in range(5):
        system2.call.cache_clear()  # a real Groq call every time, not the cache
        r = assess(CASES[case_id]["change"], "deep")
        assert r["path"] == "system2", r["note"]
        answers.add((r["level"], json.dumps(r["comments"])))
    assert len(answers) == 1, answers


def test_groq_assessment_takes_seconds_not_minutes():
    system2.call.cache_clear()
    t = time.perf_counter()
    r = assess(CASES["CHG-06"]["change"], "deep")
    assert r["path"] == "system2", r["note"]
    assert time.perf_counter() - t < 5
