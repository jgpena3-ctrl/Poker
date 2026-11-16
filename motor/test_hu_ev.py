import math
import pytest

from motor.hu_ev import (
    ActionEV, EVInput, EVResult, VillainResponse, calculate_ev)


def test_fold_ev_is_zero():
    r = calculate_ev(EVInput(pot=10.0, equity=0.5, coverage='usable'))
    fold = next(a for a in r.actions if a.action == 'fold')
    assert fold.ev == 0.0 and fold.status == 'usable'


def test_check_ev_uses_equity():
    r = calculate_ev(EVInput(pot=10.0, equity=0.5, coverage='usable'))
    check = next(a for a in r.actions if a.action == 'check')
    assert check.ev == 5.0


def test_call_ev_formula():
    r = calculate_ev(EVInput(pot=10.0, to_call=2.0, equity=0.5,
                             coverage='usable', hero_stack=10.0))
    call = next(a for a in r.actions if a.action == 'call')
    assert call.ev == 0.5 * (10.0 + 4.0) - 2.0


def test_bet_ev_requires_response():
    r = calculate_ev(EVInput(pot=10.0, equity=0.6, coverage='usable'))
    bet = next(a for a in r.actions if a.action.startswith('bet_'))
    assert bet.status == 'unknown'
    assert bet.reason == 'villain_response_unknown'


def test_bet_ev_with_response():
    resp = VillainResponse(p_fold=0.5, p_call=0.4, p_raise=0.1)
    r = calculate_ev(EVInput(pot=10.0, equity=0.6, coverage='usable',
                             response=resp))
    bet = next(a for a in r.actions if a.action.startswith('bet_'))
    assert bet.status == 'usable'
    assert math.isfinite(bet.ev)


def test_unknown_equity_does_not_invent_ev():
    r = calculate_ev(EVInput(pot=10.0))
    check = next(a for a in r.actions if a.action == 'check')
    assert check.ev is None and check.status == 'unknown'


def test_fold_remains_usable_without_equity():
    r = calculate_ev(EVInput(pot=10.0))
    assert r.best_action == 'fold'
    assert r.best_ev == 0.0


def test_validation_rejects_bad_inputs():
    with pytest.raises(ValueError):
        EVInput(pot=-1.0)
    with pytest.raises(ValueError):
        VillainResponse(p_fold=0.5, p_call=0.5, p_raise=0.5)
    with pytest.raises(ValueError):
        EVInput(pot=10.0, equity=0.5, coverage='unknown')


def test_allin_equal_stacks_formula():
    resp = VillainResponse(p_fold=0.2, p_call=0.7, p_raise=0.1)
    r = calculate_ev(EVInput(pot=10.0, equity=0.6, coverage='usable',
                             hero_stack=5.0, villain_stack=5.0, response=resp,
                             allow_all_in=True, bet_fractions=()))
    allin = next(a for a in r.actions if a.action == 'all_in')
    expected = 0.2 * 10.0 + 0.8 * (0.6 * (10.0 + 10.0) - 5.0)
    assert allin.amount == 5.0
    assert abs(allin.ev - expected) < 1e-9


def test_allin_does_not_treat_raise_as_fold():
    resp = VillainResponse(p_fold=0.0, p_call=0.5, p_raise=0.5)
    r = calculate_ev(EVInput(pot=10.0, equity=0.6, coverage='usable',
                             hero_stack=4.0, villain_stack=6.0, response=resp,
                             allow_all_in=True, bet_fractions=()))
    allin = next(a for a in r.actions if a.action == 'all_in')
    expected = 1.0 * (0.6 * (10.0 + 8.0) - 4.0)
    assert abs(allin.ev - expected) < 1e-9


def test_allin_effective_stack_unequal():
    r = calculate_ev(EVInput(pot=10.0, equity=0.6, coverage='usable',
                             hero_stack=8.0, villain_stack=3.0, response=None,
                             allow_all_in=True, bet_fractions=()))
    allin = next(a for a in r.actions if a.action == 'all_in')
    assert allin.amount == 3.0
    assert allin.status == 'unknown'


def test_call_allin_when_to_call_exceeds_stack():
    r = calculate_ev(EVInput(pot=10.0, to_call=5.0, equity=0.6,
                             coverage='usable', hero_stack=3.0))
    call = next(a for a in r.actions if a.action == 'call')
    assert call.amount == 3.0
    assert call.reason == 'all_in_call'
    assert abs(call.ev - (0.6 * (10.0 + 6.0) - 3.0)) < 1e-9


def test_unknown_action_does_not_become_zero():
    r = calculate_ev(EVInput(pot=10.0, equity=0.6, coverage='usable',
                             response=None, bet_fractions=(0.5,)))
    bet = next(a for a in r.actions if a.action == 'bet_50')
    assert bet.ev is None and bet.status == 'unknown'
    assert r.best_action != 'bet_50' or r.best_ev != 0.0


def test_tie_keeps_first_usable_action():
    # Fold EV is 0; make a check with 0 EV by pot=0 to tie with fold.
    r = calculate_ev(EVInput(pot=0.0, equity=0.5, coverage='usable',
                             bet_fractions=()))
    assert r.best_action == 'fold'


def test_all_negative_ev_still_selects_best():
    r = calculate_ev(EVInput(pot=1.0, to_call=10.0, equity=0.1,
                             coverage='usable'))
    assert r.best_action == 'fold'
    assert r.best_ev == 0.0

def test_bet_raise_assumes_hero_fold():
    resp = VillainResponse(p_fold=0.2, p_call=0.5, p_raise=0.3)
    r = calculate_ev(EVInput(pot=10.0, equity=0.6, coverage='usable',
                             response=resp, bet_fractions=(0.5,)))
    bet = next(a for a in r.actions if a.action == 'bet_50')
    expected = 0.2 * 10.0 + 0.5 * (0.6 * (10.0 + 10.0) - 5.0) + 0.3 * (-5.0)
    assert abs(bet.ev - expected) < 1e-9


def test_hero_allin_vs_shorter_rival():
    resp = VillainResponse(p_fold=0.25, p_call=0.75, p_raise=0.0)
    r = calculate_ev(EVInput(pot=10.0, equity=0.6, coverage='usable',
                             hero_stack=8.0, villain_stack=3.0, response=resp,
                             allow_all_in=True, bet_fractions=()))
    allin = next(a for a in r.actions if a.action == 'all_in')
    assert allin.amount == 3.0


def test_hero_allin_vs_taller_rival():
    resp = VillainResponse(p_fold=0.25, p_call=0.75, p_raise=0.0)
    r = calculate_ev(EVInput(pot=10.0, equity=0.6, coverage='usable',
                             hero_stack=3.0, villain_stack=8.0, response=resp,
                             allow_all_in=True, bet_fractions=()))
    allin = next(a for a in r.actions if a.action == 'all_in')
    assert allin.amount == 3.0


def test_rival_allin_hero_can_call():
    r = calculate_ev(EVInput(pot=10.0, to_call=4.0, equity=0.6,
                             coverage='usable', hero_stack=10.0))
    call = next(a for a in r.actions if a.action == 'call')
    assert call.amount == 4.0
    assert abs(call.ev - (0.6 * (10.0 + 8.0) - 4.0)) < 1e-9
