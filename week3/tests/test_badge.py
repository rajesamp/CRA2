"""Visible cache status agrees with actual eligible lookup outcomes."""
from week2.app import cache_badge


def test_badge_states():
    assert 'not used' in cache_badge({})
    assert 'cache: miss' in cache_badge({'cache':[{'outcome':'miss'}]})
    assert 'cache: hit' in cache_badge({'cache':[{'outcome':'hit'}]})
    assert 'mixed' in cache_badge({'cache':[{'outcome':'miss'},{'outcome':'hit'}]})
