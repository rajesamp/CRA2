from copy import deepcopy
import json

import pytest

from scripts.evaluate_retrieval import ROOT
from scripts.review_exchange import worksheet, submit
from week2 import reviewer_app as ui


@pytest.fixture
def packet():
    return json.loads((ROOT / 'evals/retrieval-review-queue.json').read_text())


@pytest.mark.parametrize('choice,source,expected', [
    (ui.UNCERTAIN, None, None), (ui.NONE, None, []),
    (ui.MATCH, 'public-meta-2021-10-04', ['public-meta-2021-10-04'])])
def test_save_exports_valid_individual_judgment(packet, choice, source, expected):
    sheet = worksheet(packet)
    updated = ui.save_judgment(packet, sheet, 'reviewer', 'review-01', choice, source, 'Fixture reason')
    assert sheet['judgments'] == []
    assert updated['judgments'][0]['source_ids'] == expected
    assert submit(packet, updated)['cases'][0]['reviews'][0]['source_ids'] == expected


def test_draft_edits_replace_only_own_unsent_judgment(packet):
    sheet = ui.save_judgment(packet, worksheet(packet), 'reviewer', 'review-01', ui.NONE, None, 'First')
    updated = ui.save_judgment(packet, sheet, 'reviewer', 'review-01', ui.UNCERTAIN, None, 'Reconsidered')
    assert len(updated['judgments']) == 1
    assert updated['judgments'][0]['reason'] == 'Reconsidered'
    assert sheet['judgments'][0]['reason'] == 'First'
    with pytest.raises(ValueError):
        ui.save_judgment(packet, sheet, 'another', 'review-02', ui.NONE, None, 'Reason')


@pytest.mark.parametrize('decision,source,reason', [(ui.MATCH, None, 'Reason'), ('bad', None, 'Reason'),
                                                   (ui.NONE, None, '')])
def test_invalid_form_does_not_mutate_state(packet, decision, source, reason):
    sheet = worksheet(packet)
    original = deepcopy(sheet)
    with pytest.raises(ValueError):
        ui.save_judgment(packet, sheet, 'reviewer', 'review-01', decision, source, reason)
    assert sheet == original


def test_workspace_components_are_readonly_where_needed_and_session_isolated(packet):
    app = ui.build_app(packet)
    try:
        components = app.config['components']
        props = {c['props'].get('label'): c['props'] for c in components}
        for label in ('CRA2 service', 'Proposed change', 'Source URL, reported facts and caveats'):
            assert props[label]['interactive'] is False
        assert any(c['type'] == 'state' for c in components)
        assert 'No justified external analogue' in str(props['Your judgment'])
        assert 'Unsure / insufficient detail' in str(props['Your judgment'])
        assert not any(c['type'] == 'file' for c in components)
    finally:
        app.close()
