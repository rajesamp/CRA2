"""Evaluation accounting must expose misses and reject source leakage."""
from copy import deepcopy
import json

import pytest

from cra2.public_evidence import public_documents
from scripts.evaluate_retrieval import ROOT, evaluate, load_cases


def cases():
    return load_cases(ROOT / 'evals/retrieval-cases.json')


def hit(source):
    doc = next(d for d in public_documents() if d['doc_id'] == source)
    return {**doc, 'chunk_id': source + '#chunk-001', 'score': 0.8}


def test_source_overlap_is_rejected_before_retrieval(tmp_path):
    rows = cases()
    rows[3]['expected_source_ids'] = rows[0]['expected_source_ids']
    path = tmp_path / 'cases.json'
    path.write_text(json.dumps({'schema_version': 1, 'cases': rows}))
    with pytest.raises(ValueError, match='leaks'):
        load_cases(path)


@pytest.mark.parametrize('mutation', ['duplicate', 'unknown', 'missing', 'version'])
def test_invalid_evaluation_inputs_fail(tmp_path, mutation):
    data = {'schema_version': 1, 'cases': cases()}
    if mutation == 'duplicate':
        data['cases'].append(deepcopy(data['cases'][0]))
    elif mutation == 'unknown':
        data['cases'][0]['expected_source_ids'] = ['public-unknown']
    elif mutation == 'missing':
        data['cases'][0]['expected_source_ids'] = None
    else:
        data['schema_version'] = True
    path = tmp_path / 'cases.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_cases(path)


def test_misses_are_kept_in_denominator_and_negatives_are_separate():
    rows = cases()
    answer = evaluate(rows, lambda *a, **kw: [])
    assert answer['metrics']['evaluation'] == {
        'positive_cases': 4, 'target_hits_at_3': 0, 'target_hit_rate_at_3': 0,
        'mean_reciprocal_rank_at_3': 0, 'negative_cases': 2, 'negative_passes': 2,
    }
    assert len(answer['cases']) == len(rows)


def test_rank_and_negative_false_positive_accounting():
    rows = cases()
    target = hit(rows[3]['expected_source_ids'][0])
    local = dict(target, doc_id='local', chunk_id='local#1', service='checkout-service', source_dataset='synthetic')
    result = evaluate(rows, lambda *a, **kw: [local, target])
    metric = result['metrics']['evaluation']
    assert metric['target_hits_at_3'] == 1
    assert metric['target_hit_rate_at_3'] == .25
    assert metric['mean_reciprocal_rank_at_3'] == .125
    assert metric['negative_passes'] == 0


@pytest.mark.parametrize('violation', ['cap', 'provenance', 'scope', 'stripped'])
def test_safety_boundary_violation_is_not_scored_as_success(violation):
    rows = cases()
    target = hit(rows[0]['expected_source_ids'][0])
    if violation == 'cap':
        hits = [target, target]
    elif violation == 'provenance':
        hits = [dict(target, service='checkout-service')]
    elif violation == 'scope':
        hits = [dict(target, doc_id='local', source_dataset='synthetic', service='auth-service')]
    else:
        hits = [dict(target, source_dataset='synthetic', service='checkout-service')]
    with pytest.raises(ValueError):
        evaluate(rows, lambda *a, **kw: hits)
