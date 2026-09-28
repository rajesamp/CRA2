"""Offline regression tests for provenance-preserving incident retrieval."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from cra2 import advisor, config
from cra2.incidents import load_incidents, normalize_change_type, select_incidents

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
CHANGE = {
    "service": "notification-service",
    "change_type": "Code deploy",
    "summary": "Batch email sends.",
    "deploy_plan": "Canary the previous and next versions together.",
    "rollback_plan": "Restore the previous image.",
    "monitoring_plan": "Watch queue lag and email delivery rate.",
}
RECORD = {
    "incident_id": "TEST-1",
    "service": "external-system",
    "date": "2026-09-01",
    "change_type": "No change",
    "severity": "SEV2",
    "root_cause": "A malformed invoice blocked the outbound processing queue",
    "source": "internal",
}
SYNTHETIC = {**RECORD, "incident_id": "SYN-1", "service": "notification-service"}


@pytest.fixture
def incidents():
    return load_incidents(config.DATA_DIR)


def write_datasets(directory, synthetic, samples):
    for filename, rows in (
        ("incidents.json", synthetic),
        ("sample_incidents.json", samples),
    ):
        (directory / filename).write_text(json.dumps(rows), encoding="utf-8")


def test_minimal_valid_datasets_are_loadable(tmp_path):
    write_datasets(tmp_path, [SYNTHETIC], [RECORD])
    loaded = load_incidents(tmp_path)
    assert [row["incident_id"] for row in loaded] == ["SYN-1", "TEST-1"]


def test_all_sample_records_keep_exact_source_values_and_provenance(incidents):
    raw = json.loads(
        (config.DATA_DIR / "sample_incidents.json").read_text(encoding="utf-8")
    )
    loaded = [row for row in incidents if row["source_dataset"] == "sanitized_samples"]
    assert len(raw) == len(loaded) == 30
    assert len({row["service"] for row in loaded}) == 28
    assert len(incidents) == len({row["incident_id"] for row in incidents}) == 46
    assert {row["source_dataset"] for row in incidents} == {
        "synthetic",
        "sanitized_samples",
    }
    assert {row["service"] for row in loaded}.isdisjoint(advisor.CATALOG)
    assert all(row["source"] == "internal" for row in loaded)
    assert sorted(
        [
            {key: value for key, value in row.items() if key != "source_dataset"}
            for row in loaded
        ],
        key=lambda row: row["incident_id"],
    ) == sorted(raw, key=lambda row: row["incident_id"])


@pytest.mark.parametrize(
    "original,expected",
    [
        ("Deployment", "Code deploy"),
        ("Code deploy", "Code deploy"),
        ("Capacity", "Capacity"),
        ("No change", "No change"),
        ("Third-party dependency", "Third-party dependency"),
        ("Infra change", "Infra change"),
        ("deployment", "deployment"),
    ],
)
def test_only_unambiguous_deployment_label_is_normalized(original, expected):
    assert normalize_change_type(original) == expected


@pytest.mark.parametrize(
    "incident_id,kind,summary",
    [
        (
            "INC-4351",
            "No change",
            "Handle a malformed invoice in the outbound processing queue.",
        ),
        (
            "INC-2973",
            "Capacity",
            "Prevent database pod OOM eviction and application pod restarts with 503 errors.",
        ),
        (
            "INC-4031",
            "Third-party dependency",
            "Prevent invoice update errors filling the dead-letter queue.",
        ),
    ],
)
def test_relevant_analogues_outrank_unrelated_deployment_history(
    incidents, incident_id, kind, summary
):
    selected = select_incidents({**CHANGE, "summary": summary}, incidents)
    matching = next(
        (row for row in selected if row["incident_id"] == incident_id), None
    )
    assert matching is not None
    assert matching["change_type"] == kind
    assert matching["match_kind"] == "cross_service_analogue"
    assert len(matching["matched_terms"]) >= 2
    assert matching["matched_terms"] == sorted(set(matching["matched_terms"]))


def test_type_alias_cannot_establish_cross_service_relevance():
    row = {
        **RECORD,
        "change_type": "Deployment",
        "root_cause": "Distinct unrelated issue",
    }
    before = deepcopy(row)
    selected = select_incidents({**CHANGE, "summary": "Violet marmalade."}, [row])
    assert selected == []
    assert row == before


def test_minor_copy_edit_does_not_fill_context_with_unrelated_deployments(incidents):
    change = {
        **CHANGE,
        "summary": "Fix spelling in the email footer.",
        "deploy_plan": "Canary the release.",
        "rollback_plan": "Restore the earlier template.",
        "monitoring_plan": "Watch email delivery rate.",
    }
    selected = select_incidents(change, incidents)
    assert len(selected) < 5
    assert all(
        row["service"] == change["service"] or len(row["matched_terms"]) >= 2
        for row in selected
    )
    assert not {"INC-8628", "INC-5162", "INC-6754", "INC-3334"} & {
        row["incident_id"] for row in selected
    }


def test_foreign_payment_label_never_becomes_catalog_service_history(
    incidents, monkeypatch
):
    monkeypatch.setattr(advisor, "INCIDENTS", incidents)
    change = {
        **CHANGE,
        "service": "payment-gateway",
        "summary": "Prevent slow database queries causing payment API timeout errors.",
    }
    ctx = advisor.context(change)
    matching = next(row for row in ctx["related"] if row["incident_id"] == "INC-4913")
    assert (
        matching["service"] == "payment"
        and matching["match_kind"] == "cross_service_analogue"
    )
    assert all(row["service"] == "payment-gateway" for row in ctx["repeats"])
    assert "INC-4913" not in {row["incident_id"] for row in ctx["repeats"]}


def test_unrelated_incident_is_not_selected_just_for_being_severe_or_recent():
    row = {**RECORD, "severity": "SEV1", "date": "2026-09-27"}
    selected = select_incidents(
        {
            **CHANGE,
            "summary": "Violet marmalade.",
            "deploy_plan": "",
            "rollback_plan": "",
            "monitoring_plan": "",
        },
        [row],
    )
    assert selected == []


def test_technical_short_terms_can_establish_context_overlap():
    row = {**RECORD, "change_type": "Capacity", "root_cause": "OOM CPU saturation"}
    selected = select_incidents(
        {**CHANGE, "summary": "Avoid OOM CPU saturation."}, [row]
    )
    assert len(selected) == 1
    assert {"oom", "cpu"} <= set(selected[0]["matched_terms"])


def test_selection_is_bounded_stable_and_does_not_mutate_source(incidents):
    before = deepcopy(incidents)
    selected = select_incidents(CHANGE, incidents)
    assert len(selected) <= 5
    assert len({row["incident_id"] for row in selected}) == len(selected)
    assert selected == select_incidents(CHANGE, list(reversed(incidents)))
    assert select_incidents(CHANGE, incidents, limit=2) == selected[:2]
    assert incidents == before
    selected[0]["root_cause"] = "Caller mutation"
    selected[0]["matched_terms"].append("caller-mutation")
    assert incidents == before


def test_selection_cap_does_not_force_or_exceed_requested_count():
    history = [
        {**RECORD, "incident_id": f"TEST-{index}", "service": CHANGE["service"]}
        for index in range(8)
    ]
    assert len(select_incidents(CHANGE, history)) == 5
    assert len(select_incidents(CHANGE, history, limit=2)) == 2


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_enrichment_keeps_existing_fast_scores_routes_and_same_service_history(
    case, incidents, monkeypatch
):
    synthetic = [row for row in incidents if row["source_dataset"] == "synthetic"]
    monkeypatch.setattr(advisor, "INCIDENTS", synthetic)
    baseline = advisor.assess(case["change"], "fast")
    repeats = {row["incident_id"] for row in advisor.context(case["change"])["repeats"]}
    monkeypatch.setattr(advisor, "INCIDENTS", incidents)
    enriched = advisor.assess(case["change"], "fast")
    assert (enriched["score"], enriched["level"], enriched["route"]) == (
        baseline["score"],
        baseline["level"],
        baseline["route"],
    )
    assert (enriched["level"], enriched["route"]) == (
        case["expected"]["level"],
        case["expected"]["route"],
    )
    assert {
        row["incident_id"] for row in advisor.context(case["change"])["repeats"]
    } == repeats


def test_only_selected_incident_ids_are_citable_and_available_to_system2(
    incidents, monkeypatch
):
    from cra2 import system2

    captured = []
    monkeypatch.setattr(advisor, "INCIDENTS", incidents)

    def capture(payload, _):
        captured.append(payload)
        raise system2.System2Unavailable("Offline payload capture")

    monkeypatch.setattr(system2, "assess", capture)
    result = advisor.assess(
        {
            **CHANGE,
            "summary": "Handle a malformed invoice in the outbound processing queue.",
        },
        "deep",
    )
    payload = captured[0]
    selected_ids = {row["incident_id"] for row in payload["incidents"]}
    all_ids = {row["incident_id"] for row in incidents}
    assert selected_ids == set(payload["evidence_keys"]) & all_ids
    assert result["incident_context"] == payload["incidents"]
    assert all(
        {
            "incident_id",
            "service",
            "date",
            "change_type",
            "severity",
            "root_cause",
            "source_dataset",
            "match_kind",
            "matched_terms",
        }
        <= row.keys()
        for row in payload["incidents"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.pop("incident_id"),
        lambda row: row.pop("service"),
        lambda row: row.pop("date"),
        lambda row: row.pop("change_type"),
        lambda row: row.pop("severity"),
        lambda row: row.pop("root_cause"),
        lambda row: row.update(service=42),
        lambda row: row.update(date="2026-02-30"),
        lambda row: row.update(date="not-a-date"),
        lambda row: row.update(severity="SEV5"),
        lambda row: row.update(root_cause=None),
        lambda row: row.update(source=[]),
    ],
)
def test_malformed_incident_data_fails_closed(tmp_path, mutation):
    row = deepcopy(RECORD)
    mutation(row)
    write_datasets(tmp_path, [SYNTHETIC], [row])
    with pytest.raises(ValueError):
        load_incidents(tmp_path)


@pytest.mark.parametrize("rows", [{}, [None], ["incident"], [42]])
def test_incident_files_require_arrays_of_objects(tmp_path, rows):
    write_datasets(tmp_path, [SYNTHETIC], rows)
    with pytest.raises(ValueError):
        load_incidents(tmp_path)


@pytest.mark.parametrize("across_datasets", [False, True])
def test_duplicate_ids_are_rejected_within_and_across_datasets(
    tmp_path, across_datasets
):
    write_datasets(
        tmp_path,
        [RECORD] if across_datasets else [SYNTHETIC],
        [RECORD] if across_datasets else [RECORD, RECORD],
    )
    with pytest.raises(ValueError):
        load_incidents(tmp_path)


def test_missing_source_file_does_not_silently_remove_history(tmp_path):
    (tmp_path / "incidents.json").write_text(json.dumps([SYNTHETIC]), encoding="utf-8")
    with pytest.raises((OSError, ValueError)):
        load_incidents(tmp_path)
