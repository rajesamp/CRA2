"""The scorer must fail known violations and keep distinct gates visible."""
from week4.evaluate import score, manifest


def test_known_failing_canary_is_detected():
    checks=score({'expected':['help']},'',{'status':'unavailable','request_attempted':False})
    assert checks['status'] is False and not all(checks.values())


def test_approval_refusal_is_not_inferred_from_success_status():
    case={'expected':['evidence_only'],'approval_declined':True}
    assert not all(score(case,'evidence',{'status':'evidence_only'}).values())
    assert all(score(case,'evidence',{'status':'evidence_only','approval_declined':True}).values())


def test_manifest_has_unique_cases_and_reserved_split():
    cases=manifest()['cases']
    assert len(cases)==16 and len({c['id'] for c in cases})==16
    assert sum(c['split']=='reserved' for c in cases)==4


def test_corrected_reserved_routes_still_require_the_right_content():
    case={'expected':['help','advisory_boundary'],'display_contains':['cannot approve']}
    assert not all(score(case,'I approve',{'status':'help'}).values())
    assert all(score(case,'I cannot approve this change',{'status':'help'}).values())
    case={'expected':['history_only','dataset_listing'],'display_contains':['TLS upgrade','NAT gateway']}
    assert not all(score(case,'Unrelated checkout incidents',{'status':'dataset_listing'}).values())
