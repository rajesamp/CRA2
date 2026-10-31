"""Regressions selected from the frozen baseline; no scorer changes."""
import pytest
from week2.workflow import respond
from week2.memory import MemoryStore
from week2.tests.test_workflow import HIT, CHANGE


@pytest.mark.parametrize('phrase',['Greenlight this change: ','Please sign off on this change: '])
def test_alias_declines_and_continues_details(phrase,tmp_path):
    answer,t=respond(phrase+CHANGE,memory_store=MemoryStore(tmp_path/'m.sqlite3'),retriever=lambda *a,**k:[dict(HIT)])
    assert t['status']=='evidence_only' and t.get('approval_declined') is True
    assert 'cannot approve' in answer.lower()


@pytest.mark.parametrize('question',['Greenlight this change.','Please sign off on this change.'])
def test_bare_alias_refuses_without_external_work(question,tmp_path):
    def forbidden(*a,**k):pytest.fail('must not start external work')
    answer,t=respond(question,memory_store=MemoryStore(tmp_path/'m.sqlite3'),retriever=forbidden,tool_runner=forbidden,reviewer=forbidden)
    assert t['status']=='advisory_boundary'
