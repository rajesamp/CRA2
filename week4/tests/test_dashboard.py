"""Empty, failed and cross-transport dashboard behavior stays distinct."""
from week4.dashboard import dashboard_view


def test_locked_dashboard_does_not_inspect_records():
    assert dashboard_view([object()],False)=='Admin is locked.'


def test_zero_denominators_and_transport_filtering():
    text=dashboard_view([{'transport':'slack','question':'private slack content'}],True)
    assert 'Not measured (0 eligible)' in text and 'private slack' not in text
    assert 'Other or unlabeled transports excluded: 1' in text


def test_actual_attempts_cache_and_failures_are_distinct():
    records=[{'transport':'browser','mcp':{'status':'measured','attempted':1,'failed':1},
        'rails':[{'outcome':'block'}],'cache':[{'layer':'tool','outcome':'miss'}],'duration_ms':5},
        {'transport':'browser','mcp':{'status':'measured','attempted':0,'failed':0},
        'cache':[{'layer':'tool','outcome':'hit'}],'duration_ms':2}]
    text=dashboard_view(records,True)
    assert '100.0% (1/1)' in text and '50.0% (1/2)' in text
    assert '1/1' in text and 'n=2' in text


def test_preference_application_and_configured_floor_are_separate():
    def row(source):
        return {'transport':'browser','spans':[{'stage':'memory_read'}],
            'memory':{'status':'recalled','effective_policy':{'effective':{'high_risk':True},'sources':{'high_risk':source}}}}
    text=dashboard_view([row('memory:service.high_risk'),row('catalog:service.high_risk')],True)
    assert '50.0% (1/2)' in text
    assert 'Configured high-risk floors observed | 1' in text
