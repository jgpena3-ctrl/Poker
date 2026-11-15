"""Pruebas del resolvedor puro de cobertura preflop (PR-02A)."""
import pytest

from motor.preflop import table_key
from motor.preflop_coverage import (
    CoverageRequest, CoverageResolution, resolve_coverage,
)


def test_exact():
    req = CoverageRequest(requested_key=table_key('OR', 'UTG', ''),
                         action='OR', pos='UTG', vs='')
    r = resolve_coverage(req)
    assert r.coverage_state == 'exact'
    assert r.source_key == r.requested_key
    assert r.approximation_used is False
    assert r.fallback_used is False


def test_alias():
    req = CoverageRequest(requested_key=table_key('4B', 'UTG', 'MP'),
                         action='4B', pos='UTG', vs='MP')
    r = resolve_coverage(req)
    assert r.coverage_state == 'alias'
    assert r.alias_of == '4B_UTG_vs_HJ'
    assert r.approximation_used is False


def test_impossible_or_bb():
    req = CoverageRequest(requested_key=table_key('OR', 'BB', ''),
                         action='OR', pos='BB', vs='')
    r = resolve_coverage(req)
    assert r.coverage_state == 'impossible'


def test_impossible_rol_utg():
    req = CoverageRequest(requested_key=table_key('ROL', 'UTG', ''),
                         action='ROL', pos='UTG', vs='')
    r = resolve_coverage(req)
    assert r.coverage_state == 'impossible'


def test_impossible_never_exact_or_alias_even_if_table_exists():
    # OR_BB no tiene tabla, pero aunque existiera, la imposibilidad tiene precedencia.
    req = CoverageRequest(requested_key=table_key('OR', 'BB', ''),
                         action='OR', pos='BB', vs='')
    r = resolve_coverage(req)
    assert r.coverage_state == 'impossible'


def test_coverage_gap():
    req = CoverageRequest(requested_key=table_key('Call_OR', 'MP', 'UTG'),
                         action='Call_OR', pos='MP', vs='UTG')
    r = resolve_coverage(req)
    assert r.coverage_state == 'coverage_gap'


def test_fallback_other_vs():
    req = CoverageRequest(requested_key=table_key('4B', 'CO', 'MP'),
                         action='4B', pos='CO', vs='MP')
    r = resolve_coverage(req, fallback_policy_permits=True)
    assert r.coverage_state == 'coverage_gap'
    assert r.fallback_used is True
    assert r.approximation_used is True
    assert r.source_key != r.requested_key


def test_fallback_not_permitted():
    req = CoverageRequest(requested_key=table_key('4B', 'CO', 'MP'),
                         action='4B', pos='CO', vs='MP')
    r = resolve_coverage(req, fallback_policy_permits=False)
    assert r.coverage_state == 'coverage_gap'
    assert r.fallback_used is False
    assert r.approximation_used is False


def test_unknown_key_mismatch():
    req = CoverageRequest(requested_key='WRONG_KEY',
                         action='OR', pos='UTG', vs='')
    r = resolve_coverage(req)
    assert r.coverage_state == 'unknown'
    assert r.reason == 'key_mismatch'
    assert r.fallback_used is False


def test_unknown_never_fallback():
    req = CoverageRequest(requested_key='WRONG_KEY',
                         action='OR', pos='UTG', vs='')
    r = resolve_coverage(req)
    assert r.coverage_state == 'unknown'
    assert r.fallback_used is False
    assert r.source_key is None
    assert r.approximation_used is False


def test_order_dependent_impossible_with_valid_sequence():
    req = CoverageRequest(requested_key=table_key('3B', 'UTG', 'MP'),
                         action='3B', pos='UTG', vs='MP',
                         source_context={'sequence_status': 'valid'})
    r = resolve_coverage(req)
    assert r.coverage_state == 'impossible'


def test_order_dependent_unknown_with_not_evaluated_sequence():
    req = CoverageRequest(requested_key=table_key('3B', 'UTG', 'MP'),
                         action='3B', pos='UTG', vs='MP',
                         source_context={'sequence_status': 'not_evaluated'})
    r = resolve_coverage(req)
    assert r.coverage_state == 'unknown'


def test_unknown_no_fallback_even_if_alternative_exists():
    # UNK-FB-01
    req = CoverageRequest(requested_key='WRONG_KEY',
                         action='OR', pos='UTG', vs='')
    r = resolve_coverage(req)
    assert r.coverage_state == 'unknown'
    assert r.fallback_used is False
    assert r.source_key is None
    assert r.approximation_used is False


def test_resolution_immutable():
    req = CoverageRequest(requested_key=table_key('OR', 'UTG', ''),
                         action='OR', pos='UTG', vs='')
    r = resolve_coverage(req)
    with pytest.raises(Exception):
        r.coverage_state = 'alias'


def test_mixed_aggregation_preserves_individual_states():
    r1 = resolve_coverage(CoverageRequest(
        requested_key=table_key('OR', 'UTG', ''), action='OR', pos='UTG', vs=''))
    r2 = resolve_coverage(CoverageRequest(
        requested_key=table_key('Call_OR', 'MP', 'UTG'),
        action='Call_OR', pos='MP', vs='UTG'))
    states = {r1.coverage_state, r2.coverage_state}
    assert 'exact' in states
    assert 'coverage_gap' in states


def test_invalid_fallback_approximation_mismatch():
    with pytest.raises(ValueError):
        CoverageResolution(requested_key='k', action='a', pos='p', vs='v',
                           coverage_state='coverage_gap', source_key=None,
                           alias_of=None, fallback_used=True,
                           fallback_key='f', fallback_reason='r',
                           approximation_used=False, reason='coverage_gap',
                           resolved_by='x')


def test_invalid_fallback_without_key():
    with pytest.raises(ValueError):
        CoverageResolution(requested_key='k', action='a', pos='p', vs='v',
                           coverage_state='coverage_gap', source_key=None,
                           alias_of=None, fallback_used=True,
                           fallback_key=None, fallback_reason='r',
                           approximation_used=True, reason='coverage_gap',
                           resolved_by='x')


def test_invalid_fallback_source_key_mismatch():
    with pytest.raises(ValueError):
        CoverageResolution(requested_key='k', action='a', pos='p', vs='v',
                           coverage_state='coverage_gap', source_key='A',
                           alias_of=None, fallback_used=True,
                           fallback_key='B', fallback_reason='r',
                           approximation_used=True, reason='coverage_gap',
                           resolved_by='x')


def test_invalid_alias_of_outside_alias():
    with pytest.raises(ValueError):
        CoverageResolution(requested_key='k', action='a', pos='p', vs='v',
                           coverage_state='exact', source_key='k',
                           alias_of='x', fallback_used=False,
                           fallback_key=None, fallback_reason=None,
                           approximation_used=False, reason='exact_table',
                           resolved_by='x')


def test_invalid_alias_missing_alias_of():
    with pytest.raises(ValueError):
        CoverageResolution(requested_key='k', action='a', pos='p', vs='v',
                           coverage_state='alias', source_key='k',
                           alias_of=None, fallback_used=False,
                           fallback_key=None, fallback_reason=None,
                           approximation_used=False, reason='approved_alias',
                           resolved_by='x')


def test_invalid_fallback_fields_when_not_used():
    with pytest.raises(ValueError):
        CoverageResolution(requested_key='k', action='a', pos='p', vs='v',
                           coverage_state='coverage_gap', source_key=None,
                           alias_of=None, fallback_used=False,
                           fallback_key='f', fallback_reason=None,
                           approximation_used=False, reason='coverage_gap',
                           resolved_by='x')


def test_invalid_coverage_gap_source_key_without_fallback():
    with pytest.raises(ValueError):
        CoverageResolution(requested_key='k', action='a', pos='p', vs='v',
                           coverage_state='coverage_gap', source_key='x',
                           alias_of=None, fallback_used=False,
                           fallback_key=None, fallback_reason=None,
                           approximation_used=False, reason='coverage_gap',
                           resolved_by='x')


def test_key_mismatch_precedence_with_exact_canonical_table():
    req = CoverageRequest(requested_key='WRONG_KEY', action='OR', pos='UTG', vs='')
    r = resolve_coverage(req)
    assert r.coverage_state == 'unknown'
    assert r.reason == 'key_mismatch'


def test_source_context_deepcopy_mutation():
    nested = {'a': [1, 2]}
    ctx = {'nested': nested}
    req = CoverageRequest(requested_key='k', action='a', pos='p', vs='v',
                          source_context=ctx)
    nested['a'].append(3)
    ctx['nested'] = {'changed': True}
    assert req.source_context == {'nested': {'a': [1, 2]}}
    assert req.source_context['nested']['a'] == [1, 2]


def test_source_context_original_mutation_does_not_affect_stored():
    ctx = {'x': 1}
    req = CoverageRequest(requested_key='k', action='a', pos='p', vs='v',
                          source_context=ctx)
    ctx['x'] = 999
    ctx['y'] = 2
    assert req.source_context == {'x': 1}


def test_source_context_direct_mutation_does_not_persist():
    req = CoverageRequest(requested_key='k', action='a', pos='p', vs='v',
                          source_context={'x': 1})
    ref = req.source_context
    ref['x'] = 999
    ref['y'] = 2
    assert req.source_context == {'x': 1}
    assert 'y' not in req.source_context


def test_source_context_nested_mutation_does_not_persist():
    req = CoverageRequest(requested_key='k', action='a', pos='p', vs='v',
                          source_context={'nested': {'a': [1, 2]}})
    ref = req.source_context['nested']
    ref['a'].append(3)
    ref['b'] = 4
    assert req.source_context == {'nested': {'a': [1, 2]}}
    assert 'b' not in req.source_context['nested']


def test_resolve_coverage_works_with_valid_context():
    req = CoverageRequest(requested_key=table_key('OR', 'UTG', ''),
                         action='OR', pos='UTG', vs='',
                         source_context={'sequence_status': 'valid'})
    r = resolve_coverage(req)
    assert r.coverage_state == 'exact'
