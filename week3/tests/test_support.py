"""Approval continuation and narrowly measured mechanism support."""
from copy import deepcopy
from week2 import workflow
from week2.memory import MemoryStore
from week2.tests.test_workflow import HIT, CHANGE


def test_approval_with_details_declines_then_continues_review(tmp_path):
    answer,trace=workflow.respond('Please approve this change for me: '+CHANGE,
        retriever=lambda *a,**k:[deepcopy(HIT)],memory_store=MemoryStore(tmp_path/'m.sqlite3'))
    assert trace['status']=='evidence_only'
    assert trace['approval_declined'] is True
    assert 'cannot approve' in answer.lower()
    assert len([e for e in trace['events'] if e['event']=='tool_result'])==2


def test_timeout_not_supported_by_same_service_tls_history(tmp_path):
    hit=deepcopy(HIT);hit['service']='payment-gateway';hit['text']='A TLS certificate rotation broke authentication.'
    def forbidden(*a,**k):
        raise AssertionError('unsupported evidence must not reach provider')
    answer,trace=workflow.respond('Change payment-gateway config timeout from 4 seconds to 400 milliseconds.',
        mode='Groq assessment',retriever=lambda *a,**k:[hit],reviewer=forbidden,
        memory_store=MemoryStore(tmp_path/'m.sqlite3'))
    assert trace['status']=='insufficient_evidence'
    assert not trace['request_attempted']
    assert trace['support']['status']=='unsupported'
    assert 'Risk indication:' not in answer
