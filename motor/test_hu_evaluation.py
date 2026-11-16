import math
import pytest

from motor.hu_evaluation import (
    HUEvaluationInput, HUEvaluationResult, evaluate_hu)
from motor.hu_ev import VillainResponse
from motor.hu_scenarios import REAL_PREFLOP_SCENARIOS
from motor.preflop_canonical import canonical_preflop


def _resolved_canonical():
    scenario = REAL_PREFLOP_SCENARIOS[0]
    return canonical_preflop(list(scenario.actions), scenario.hero_position,
                            mode='historical')


def test_resolved_evaluation_calculates_ev():
    canon = _resolved_canonical()
    inp = HUEvaluationInput(canonical=canon, pot=10.0, to_call=0.0,
                            equity=0.5, coverage='usable',
                            response=VillainResponse(1.0, 0.0, 0.0))
    res = evaluate_hu(inp)
    assert res.status == 'usable'
    assert res.ev_result is not None
    assert res.ev_result.best_action is not None


def test_unresolved_canonical_blocks_ev():
    canon = canonical_preflop(
        [{'pos': 'UTG', 'action': 'b', 'amount': 2.5}], 'MP',
        mode='historical')
    inp = HUEvaluationInput(canonical=canon, pot=10.0, to_call=0.0,
                            equity=0.5, coverage='usable')
    res = evaluate_hu(inp)
    assert res.status == 'unknown'
    assert res.ev_result is None
    assert 'canonical_no_decision' in res.uncertainty_reasons or \
        'canonical_unresolved' in res.uncertainty_reasons


def test_unknown_coverage_keeps_fold_usable():
    canon = _resolved_canonical()
    inp = HUEvaluationInput(canonical=canon, pot=10.0, to_call=0.0,
                            equity=None, coverage='unknown',
                            coverage_reason='no_equity')
    res = evaluate_hu(inp)
    assert res.ev_result is not None
    assert res.ev_result.best_action == 'fold'


def test_missing_response_marks_unknown():
    canon = _resolved_canonical()
    inp = HUEvaluationInput(canonical=canon, pot=10.0, to_call=0.0,
                            equity=0.5, coverage='usable', response=None)
    res = evaluate_hu(inp)
    assert 'villain_response_unknown' in res.uncertainty_reasons


def test_validation_rejects_bad_input():
    canon = _resolved_canonical()
    with pytest.raises(ValueError):
        HUEvaluationInput(canonical=canon, pot=-1.0)
    with pytest.raises(TypeError):
        HUEvaluationInput(canonical='x', pot=1.0)

def test_alias_coverage_trace():
    canon = _resolved_canonical()
    inp = HUEvaluationInput(canonical=canon, pot=5.0, to_call=0.0,
                            equity=0.5, coverage='alias',
                            coverage_reason='alias_table')
    res = evaluate_hu(inp)
    assert 'alias_table' in res.uncertainty_reasons
    assert res.status == 'usable'


def test_coverage_gap_keeps_fold():
    canon = _resolved_canonical()
    inp = HUEvaluationInput(canonical=canon, pot=5.0, to_call=0.0,
                            equity=None, coverage='coverage_gap',
                            coverage_reason='gap')
    res = evaluate_hu(inp)
    assert res.ev_result.best_action == 'fold'
    assert res.status == 'usable'


def test_response_mismatch_marks_unknown():
    canon = _resolved_canonical()
    inp = HUEvaluationInput(canonical=canon, pot=5.0, to_call=0.0,
                            equity=0.5, coverage='usable',
                            response=VillainResponse(1.0, 0.0, 0.0),
                            response_equities={'fold': 0.2})
    res = evaluate_hu(inp)
    assert 'equity_response_mismatch' in res.uncertainty_reasons


def test_trace_contains_context():
    canon = _resolved_canonical()
    inp = HUEvaluationInput(canonical=canon, pot=7.0, to_call=2.0,
                            equity=0.5, coverage='usable',
                            response=VillainResponse(0.5, 0.5, 0.0),
                            range_kind='estimated', range_source='prior')
    res = evaluate_hu(inp)
    assert res.trace['pot'] == 7.0
    assert res.trace['range_kind'] == 'estimated'
    assert res.trace['best_action'] is not None


def test_incomparable_ev_does_not_select_best():
    canon = _resolved_canonical()
    inp = HUEvaluationInput(canonical=canon, pot=5.0, to_call=0.0,
                            equity=None, coverage='unknown',
                            coverage_reason='gap')
    res = evaluate_hu(inp)
    assert res.comparable is False
    assert res.best_action is None
    assert res.provisional_best_action == 'fold'
    assert res.selection_status == 'provisional'


def test_no_evaluable_action_when_canonical_unresolved():
    canon = canonical_preflop(
        [{'pos': 'UTG', 'action': 'b', 'amount': 2.5}], 'MP',
        mode='historical')
    inp = HUEvaluationInput(canonical=canon, pot=5.0, to_call=0.0,
                            equity=0.5, coverage='usable',
                            response=VillainResponse(1.0, 0.0, 0.0))
    res = evaluate_hu(inp)
    assert res.selection_status == 'none'
    assert res.best_action is None
    assert res.legal_actions == ()


def test_allin_unequal_trace():
    canon = _resolved_canonical()
    inp = HUEvaluationInput(canonical=canon, pot=10.0, to_call=0.0,
                            equity=0.6, coverage='usable',
                            hero_stack=3.0, villain_stack=8.0,
                            response=VillainResponse(0.25, 0.75, 0.0),
                            allow_all_in=True, bet_fractions=())
    res = evaluate_hu(inp)
    allin = next(a for a in res.ev_result.actions if a.action == 'all_in')
    assert allin.amount == 3.0
    assert res.trace['hero_stack'] == 3.0


import numpy as np
from motor.hu_range_contracts import GenericPrior, N_COMBOS


def test_range_integration_computes_equity():
    canon = _resolved_canonical()
    prior = GenericPrior(key='prior', vector=np.ones(N_COMBOS),
                         source='flat', coverage='unknown')
    inp = HUEvaluationInput(canonical=canon, pot=10.0, to_call=0.0,
                            hero_hand=('As', 'Kd'), board=('2c', '7d', '9h'),
                            villain_range=prior, range_kind='prior',
                            range_source='flat', response=VillainResponse(1.0, 0.0, 0.0))
    res = evaluate_hu(inp)
    assert res.ev_result is not None
    assert res.trace['equity_scenario'] == 'showdown_vs_villain_range'
    assert res.trace['range_kind'] == 'prior'


def test_response_ranges_compute_equities():
    canon = _resolved_canonical()
    prior = GenericPrior(key='prior', vector=np.ones(N_COMBOS),
                         source='flat', coverage='unknown')
    inp = HUEvaluationInput(canonical=canon, pot=10.0, to_call=0.0,
                            hero_hand=('As', 'Kd'), board=('2c', '7d', '9h'),
                            villain_range=prior, range_kind='prior',
                            response=VillainResponse(0.5, 0.5, 0.0),
                            response_ranges={'call': prior})
    res = evaluate_hu(inp)
    assert res.trace['response_equities']['call'] is not None
