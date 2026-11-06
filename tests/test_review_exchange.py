from copy import deepcopy
import json

import pytest

from scripts.evaluate_retrieval import ROOT
from scripts import review_exchange as exchange
from scripts.review_retrieval import review


@pytest.fixture
def packet():
    return json.loads((ROOT / 'evals/retrieval-review-queue.json').read_text())


def completed_sheet(packet, name='reviewer-a', source_ids=None):
    sheet = exchange.worksheet(packet)
    sheet['reviewer'] = name
    sheet['judgments'] = [dict(case_id=packet['cases'][0]['id'], source_ids=source_ids,
                               reason='Test fixture judgment; not a real review.')]
    return sheet


def test_worksheet_does_not_expose_previous_reviews_or_partition(packet):
    updated = exchange.submit(packet, completed_sheet(packet))
    sheet = exchange.worksheet(updated)
    assert sheet['judgments'] == [] and sheet['reviewer'] == ''
    assert all(set(row) == {'id', 'service', 'query'} for row in sheet['cases'])
    assert 'reviewer-a' not in json.dumps(sheet)
    assert sheet == exchange.worksheet(packet)


def test_two_independent_submissions_combine_without_invalidating_each_other(packet):
    a, b = completed_sheet(packet, source_ids=[]), completed_sheet(packet, 'reviewer-b', [])
    original = deepcopy(packet)
    updated = exchange.submit(exchange.submit(packet, a), b)
    assert packet == original
    assert review(updated)[1][0]['state'] == 'agreed'
    assert len(updated['cases'][0]['reviews']) == 2


def test_disagreement_is_retained_and_uncertainty_is_not_negative(packet):
    updated = exchange.submit(exchange.submit(packet, completed_sheet(packet, source_ids=[])),
                              completed_sheet(packet, 'reviewer-b', None))
    assert review(updated)[1][0]['state'] == 'ambiguous'


@pytest.mark.parametrize('field', ['query', 'service', 'split', 'rationale'])
def test_changed_queue_rejects_old_submissions(packet, field):
    sheet = completed_sheet(packet)
    packet['cases'][0][field] = {'query': 'Updated request', 'service': 'auth-service',
                               'split': 'evaluation', 'rationale': 'Corrected rationale'}[field]
    with pytest.raises(ValueError, match='stale'):
        exchange.submit(packet, sheet)


def test_corpus_change_rejects_submission(packet, monkeypatch):
    sheet = completed_sheet(packet)
    data = deepcopy(exchange.load_public_evidence())
    data[0]['caveats'] += ' Correction.'
    monkeypatch.setattr(exchange, 'load_public_evidence', lambda: data)
    with pytest.raises(ValueError, match='stale'):
        exchange.submit(packet, sheet)


@pytest.mark.parametrize('mutation', ['duplicate', 'unknown', 'forged', 'bad-label', 'empty-reason', 'empty-reviewer'])
def test_invalid_submission_leaves_packet_unchanged(packet, mutation):
    sheet = completed_sheet(packet)
    if mutation == 'duplicate': sheet['judgments'] *= 2
    elif mutation == 'unknown': sheet['judgments'][0]['case_id'] = 'unknown'
    elif mutation == 'forged': sheet['cases'][0]['query'] = 'Forged'
    elif mutation == 'bad-label': sheet['judgments'][0]['source_ids'] = ['unknown']
    elif mutation == 'empty-reason': sheet['judgments'][0]['reason'] = ''
    else: sheet['reviewer'] = ''
    original = deepcopy(packet)
    with pytest.raises(ValueError): exchange.submit(packet, sheet)
    assert packet == original


def test_repeated_reviewer_and_third_review_rejected(packet):
    a = completed_sheet(packet, source_ids=[])
    updated = exchange.submit(packet, a)
    a['reviewer'] = ' REVIEWER-A '
    with pytest.raises(ValueError, match='overwritten'): exchange.submit(updated, a)
    updated = exchange.submit(updated, completed_sheet(packet, 'reviewer-b', []))
    with pytest.raises(ValueError): exchange.submit(updated, completed_sheet(packet, 'reviewer-c', []))


def test_cli_never_overwrites_output(packet, tmp_path, monkeypatch):
    source, output = tmp_path / 'packet.json', tmp_path / 'out.json'
    source.write_text(json.dumps(packet))
    monkeypatch.setattr('sys.argv', ['exchange', str(source), '--out', str(output)])
    exchange.main()
    original = output.read_bytes()
    with pytest.raises(FileExistsError): exchange.main()
    assert output.read_bytes() == original
