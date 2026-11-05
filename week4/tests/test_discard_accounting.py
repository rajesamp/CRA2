"""Discarding unsafe output must preserve actual execution accounting."""
from week2.workflow import respond
from week2.memory import MemoryStore
from week2.tests.test_workflow import HIT,CHANGE


def test_changed_policy_retains_actual_tool_attempt_counts(tmp_path):
    store=MemoryStore(tmp_path/'m.sqlite3')
    def retrieve(*a,**k):
        store.write('checkout-service',high_risk=True)
        return [dict(HIT)]
    answer,t=respond(CHANGE,memory_store=store,retriever=retrieve)
    assert t['status']=='context_changed'
    assert t['mcp']['attempted']==2 and t['mcp']['failed']==0
    assert not t.get('events') and not t.get('assessment')


def test_help_records_no_tool_access_instead_of_missing_accounting(tmp_path):
    answer,t=respond('What is this app?',memory_store=MemoryStore(tmp_path/'m.sqlite3'))
    assert t['mcp']=={'attempted':0,'failed':0,'status':'not_accessed'}


def test_runtime_policy_cannot_change_trusted_team_identity(tmp_path,monkeypatch):
    from copy import deepcopy
    from week2 import workflow
    store=MemoryStore(tmp_path/'m.sqlite3')
    store.write('checkout-service',high_risk=True)
    changed=deepcopy(workflow.chat.TEAM_SETTINGS);changed['team']='different-team'
    monkeypatch.setattr(workflow,'load_settings',lambda *a:changed)
    answer,t=respond('What services depend on checkout-service?',memory_store=store)
    assert t['status']=='memory_unavailable'
    assert not t.get('memory',{}).get('record') and t['mcp']['attempted']==0
