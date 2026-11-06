"""Explicit local gate with verified real BGE weights; never download or skip.

This directory is deliberately separate from week2/tests: the default offline
suite must work on a clean checkout without ignored model/index artifacts.
"""

from pathlib import Path

from week1 import retrieval, setup_index
from week2 import workflow
from week2.tests.test_slack import (
    assert_selected_service_assessment_uses_retrieval_mcp_and_offline_groq,
    settings,
)


def test_selected_service_assessment_with_verified_real_encoder(tmp_path, settings, monkeypatch):
    # Missing/corrupt weights fail this requested gate. Setup never downloads.
    directory = setup_index.provision_model(download=False)
    setup_index._validate_model(directory)
    retrieval._default_encoder.cache_clear()
    encoder = retrieval._default_encoder()
    assert retrieval._encoder_identity(encoder).startswith("fastembed-artifacts-sha256:")
    corpus = Path(__file__).resolve().parents[2] / "week1" / "corpus"
    index = tmp_path / "slack-real-bge.sqlite3"
    counts = retrieval.build_index(corpus, index, encoder=encoder)
    assert counts["chunks"] >= counts["documents"] > 0
    monkeypatch.setattr(workflow.chat, "search", lambda query, _path, **options:
                        retrieval.search(query, index, encoder=encoder, **options))
    assert_selected_service_assessment_uses_retrieval_mcp_and_offline_groq(
        tmp_path, settings, monkeypatch)
