"""UI regressions never opt into cloud exports through an operator's environment."""

import pytest


@pytest.fixture(autouse=True)
def disable_implicit_trace_upload(monkeypatch):
    monkeypatch.setenv("CRA2_LANGSMITH_ENABLED", "false")
