"""Queue contract for the actual CRA2 Gradio callback inventory."""
from inspect import unwrap

import pytest

from week2.app import build_app


@pytest.fixture(scope="module")
def demo():
    return build_app()


def test_review_queue_has_a_finite_waiting_room(demo):
    assert demo._queue.max_size == 2


def test_all_review_callbacks_share_one_running_slot(demo):
    reviews = [
        fn for fn in demo.fns.values()
        if fn.fn and unwrap(fn.fn).__name__ in {"reply", "recovery"}
    ]
    # submit, retry and option selection use three bindings of the chat wrapper.
    # The named API and recovery each register another work-bearing callback.
    assert sorted(fn.name for fn in reviews) == ["_submit_fn"] * 3 + ["recovery", "reply"]
    assert len({fn.concurrency_id for fn in reviews}) == 1
    assert all(fn.queue and fn.concurrency_limit == 1 for fn in reviews)
