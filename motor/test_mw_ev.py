import numpy as np
import pytest

from motor.cards import card_id
from motor.hu_range_contracts import GenericPrior, KnownCards, build_estimated_range
from motor.mw_equity import calculate_multiway_equity
from motor.mw_ev import (
    EquityEvidence, MWGameEVInput, calculate_mw_ev, mw_ev_input_from_state,
)
from motor.mw_ranges import build_ranges_from_state, ranges_for_state
from motor.mw_state import interpret_mw_state
from motor.ranges import COMBO0, COMBO1, N_COMBOS


def _idx(a, b):
    a, b = sorted((card_id(a), card_id(b)))
    return int(np.flatnonzero((COMBO0 == a) & (COMBO1 == b))[0])


def _estimated(player, hero, board, combo):
    weights = np.zeros(N_COMBOS)
    weights[_idx(*combo)] = 1.0
    prior = GenericPrior('synthetic_fixture', weights, 'manual', 'exact')
    return build_estimated_range(
        player=player, street='river', board=board, prior=prior,
        likelihood=np.ones(N_COMBOS),
        known_cards=KnownCards(hero_hand=hero, board=board),
        likelihood_model='synthetic_fixture')


def _allin_snapshot():
    hero, board = ('As', 'Ad'), ['2c', '3d', '4h', '5s', '9c']
    return interpret_mw_state({
        'hero_id': 'hero', 'street': 'river', 'board': board,
        'pot': 200,
        'players': [
            {'identity': 'hero', 'position': 'BTN', 'status': 'active',
             'hole_cards': hero, 'stack': 50, 'contribution': 50},
            {'identity': 'v1', 'position': 'SB', 'status': 'all_in',
             'hole_cards': ['Kc', 'Kd'], 'stack': 0, 'contribution': 50},
            {'identity': 'v2', 'position': 'BB', 'status': 'all_in',
             'hole_cards': ['Qc', 'Qd'], 'stack': 0, 'contribution': 100},
        ],
        'actions': [
            {'index': 0, 'player_id': 'v1', 'action': 'all_in',
             'street': 'river', 'amount': 50},
            {'index': 1, 'player_id': 'v2', 'action': 'all_in',
             'street': 'river', 'amount': 100},
        ], 'sequence_complete': True,
        'decision': {'actor_id': 'hero', 'to_call': 50,
                     'facing_action': {'player_id': 'v2', 'action': 'all_in',
                                       'amount': 50}},
    }), hero, board


def test_state_ranges_equity_sidepots_and_ev_integrate_for_allin_call():
    state, hero, board = _allin_snapshot()
    estimates = {
        'v1': _estimated('v1', hero, board, ('Kc', 'Kd')),
        'v2': _estimated('v2', hero, board, ('Qc', 'Qd')),
    }
    ranges = ranges_for_state(state, build_ranges_from_state(state, estimates, {}))
    main_equity = calculate_multiway_equity(
        hero, board, ranges, exact=True)
    side_equity = calculate_multiway_equity(
        hero, board, (ranges[1],), exact=True)
    ev_input = mw_ev_input_from_state(state, {
        ('v1', 'v2'): EquityEvidence.from_result(main_equity),
        ('v2',): EquityEvidence.from_result(side_equity),
    })
    result = calculate_mw_ev(ev_input)
    assert main_equity.equity == 1.0
    assert side_equity.equity == 1.0
    assert result.status == 'provisional'
    assert result.reason == 'independent_marginals_baseline'
    assert result.pot_layers.total_pot == 250.0
    call = next(a for a in result.actions if a.action == 'call')
    assert call.status == 'provisional'
    assert call.ev == 200.0  # expected 150 main + 100 side - 50 call


def test_unmodeled_live_opponents_make_ev_incomplete_not_heuristic():
    inp = MWGameEVInput(
        hero_id='hero', contributions={'hero': 0, 'v1': 5, 'v2': 5},
        player_status={'hero': 'active', 'v1': 'active', 'v2': 'active'},
        hero_stack=100, to_call=5, equity_by_opponents={})
    result = calculate_mw_ev(inp)
    assert result.status == 'incomplete'
    assert result.reason == 'no_supported_multiway_response_likelihood'
    assert next(a for a in result.actions if a.action == 'fold').ev == 0.0
    call = next(a for a in result.actions if a.action == 'call')
    assert call.ev is None
    assert call.reason == 'opponent_response_tree_unavailable'


def test_incomplete_equity_for_one_sidepot_keeps_ev_incomplete():
    state, _hero, _board = _allin_snapshot()
    evidence = {'v1,v2': EquityEvidence(
        1.0, True, 0.0, 'test', opponents=('v1', 'v2'))}
    inp = mw_ev_input_from_state(state, {('v1', 'v2'): evidence['v1,v2']})
    result = calculate_mw_ev(inp)
    assert result.status == 'incomplete'
    assert 'equity_missing_for_eligible_subset:v2' in result.reason


def test_sampled_equity_makes_ev_provisional_not_complete():
    state, _hero, _board = _allin_snapshot()
    inp = MWGameEVInput(
        hero_id='hero', contributions={'hero': 50, 'v1': 50, 'v2': 100},
        player_status={'hero': 'active', 'v1': 'all_in', 'v2': 'all_in'},
        hero_stack=50, to_call=50,
        equity_by_opponents={
            ('v1', 'v2'): EquityEvidence(
                0.75, False, 0.01, 'independent', opponents=('v1', 'v2')),
            ('v2',): EquityEvidence(
                0.5, False, 0.02, 'independent', opponents=('v2',)),
        })
    result = calculate_mw_ev(inp)
    assert result.status == 'provisional'
    assert next(a for a in result.actions if a.action == 'call').status == \
        'provisional'


def test_inferred_financial_state_keeps_exact_equity_ev_provisional():
    inp = MWGameEVInput(
        hero_id='hero', contributions={'hero': 50, 'v1': 50, 'v2': 100},
        player_status={'hero': 'active', 'v1': 'all_in', 'v2': 'all_in'},
        hero_stack=50, to_call=50,
        equity_by_opponents={
            ('v1', 'v2'): EquityEvidence(
                1.0, True, 0.0, 'exact_joint', opponents=('v1', 'v2')),
            ('v2',): EquityEvidence(
                1.0, True, 0.0, 'exact_joint', opponents=('v2',)),
        }, input_uncertainty=('v1:status',))
    result = calculate_mw_ev(inp)
    assert result.status == 'provisional'
    assert result.reason == 'state_fields_inferred'
    assert result.input_uncertainty == ('v1:status',)
