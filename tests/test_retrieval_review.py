"""Unknown judgments never become negatives; only agreed, intact bundles score."""
from copy import deepcopy
import json

import pytest

from scripts.evaluate_retrieval import ROOT
from scripts import review_retrieval as review


@pytest.fixture
def packet():
    rows = json.loads((ROOT / 'evals/retrieval-cases.json').read_text())['cases']
    for row in rows:
        label = row.pop('expected_source_ids')
        row['reviews'] = [{'reviewer': who, 'source_ids': label, 'reason': 'Fixture judgment for boundary testing.'}
                          for who in ('reviewer-a', 'reviewer-b')]
    return {'schema_version': 1, 'origin': 'assistant_authored_synthetic', 'cases': rows}


def test_pending_queue_is_valid_but_cannot_be_frozen():
    queue = json.loads((ROOT / 'evals/retrieval-review-queue.json').read_text())
    _, states = review.review(queue)
    assert len(states) == 18 and all(s['state'] == 'pending' for s in states)
    with pytest.raises(ValueError, match='cannot be frozen'):
        review.freeze(queue)


@pytest.mark.parametrize('labels,state', [([], 'pending'), ([None, []], 'ambiguous'),
                                        ([[], ['public-meta-2021-10-04']], 'conflict')])
def test_unresolved_labels_block_entire_export(packet, labels, state):
    packet['cases'][0]['reviews'] = [dict(reviewer=str(i), source_ids=label, reason='Unresolved fixture')
                                    for i, label in enumerate(labels)]
    assert review.review(packet)[1][0]['state'] == state
    with pytest.raises(ValueError, match='cannot be frozen'):
        review.freeze(packet)


def test_agreed_negative_is_distinct_from_unknown(packet):
    bundle = review.freeze(packet)
    cases = review.load_frozen_bundle(bundle)
    assert cases[2]['expected_source_ids'] == []
    assert cases[0]['expected_source_ids'] == ['public-google-router-2026-09-01']


@pytest.mark.parametrize('mutation', ['case', 'review', 'hash', 'extra'])
def test_modified_bundle_fails_validation(packet, mutation):
    bundle = review.freeze(packet)
    if mutation == 'case':
        bundle['cases'][0]['query'] = 'Modified input'
    elif mutation == 'review':
        bundle['packet']['cases'][0]['reviews'][0]['reason'] = 'Changed judgment'
    elif mutation == 'hash':
        bundle['corpus_sha256'] = '0' * 64
    else:
        bundle['unexpected'] = True
    with pytest.raises(ValueError):
        review.load_frozen_bundle(bundle)


def test_corpus_change_requires_new_review_snapshot(packet, monkeypatch):
    bundle = review.freeze(packet)
    changed = deepcopy(review.load_public_evidence())
    changed[0]['caveats'] += ' Source correction.'
    monkeypatch.setattr(review, 'load_public_evidence', lambda: changed)
    with pytest.raises(ValueError, match='stale'):
        review.load_frozen_bundle(bundle)


def test_same_reviewer_under_different_case_cannot_agree_twice(packet):
    packet['cases'][0]['reviews'][1]['reviewer'] = ' REVIEWER-A '
    with pytest.raises(ValueError, match='distinct'):
        review.freeze(packet)


def test_agreed_labels_cannot_cross_source_partitions(packet):
    for entry in packet['cases'][3]['reviews']:
        entry['source_ids'] = ['public-google-router-2026-09-01']
    with pytest.raises(ValueError, match='leaks'):
        review.freeze(packet)


@pytest.mark.parametrize('label', ['unknown', ['unknown'], [True], ['public-meta-2021-10-04'] * 2])
def test_invalid_source_judgments_rejected(packet, label):
    packet['cases'][0]['reviews'][0]['source_ids'] = label
    with pytest.raises(ValueError):
        review.freeze(packet)


def test_cli_freeze_creates_a_loadable_bundle_without_overwriting(packet, tmp_path, monkeypatch):
    path, output = tmp_path / 'packet.json', tmp_path / 'frozen.json'
    path.write_text(json.dumps(packet))
    monkeypatch.setattr('sys.argv', ['review', str(path), '--freeze', str(output)])
    review.main()
    original = output.read_bytes()
    assert len(review.load_frozen_bundle(json.loads(original))) == 9
    with pytest.raises(FileExistsError):
        review.main()
    assert output.read_bytes() == original


def test_cli_does_not_create_output_for_pending_reviews(packet, tmp_path, monkeypatch):
    packet['cases'][0]['reviews'] = []
    path, output = tmp_path / 'packet.json', tmp_path / 'frozen.json'
    path.write_text(json.dumps(packet))
    monkeypatch.setattr('sys.argv', ['review', str(path), '--freeze', str(output)])
    with pytest.raises(ValueError):
        review.main()
    assert not output.exists()
