from types import SimpleNamespace

from motor.experimental_actions import evaluate_experimental_actions
from motor.hu_evaluation import HUEvaluationInput
from motor.mw_ranges import build_ranges_from_state
from motor.mw_response_tree import (
    ActionSpec, LegacyResponseProvider, MWTreeInput,
)
from motor.mw_state import interpret_mw_state
from motor.preflop_canonical import canonical_preflop


def _state(n_opponents=1, *, incomplete=False):
    identities = ('hero', 'v1', 'v2')[:n_opponents + 1]
    positions = {'hero': 'BTN', 'v1': 'SB', 'v2': 'BB'}
    cards = {'hero': ['As', 'Ad'], 'v1': ['Kc', 'Kd'],
             'v2': ['Qc', 'Qd']}
    players = [{
        'identity': player, 'position': positions[player],
        'status': 'active', 'hole_cards': cards[player],
        'stack': 50.0, 'contribution': 20.0,
    } for player in identities]
    if incomplete and n_opponents > 1:
        del players[-1]['status']
    return interpret_mw_state({
        'hero_id': 'hero', 'street': 'river',
        'board': ['2c', '3d', '4h', '5s', '9c'],
        'players': players, 'pot': 20.0 * len(players),
        'actions': [], 'sequence_complete': not incomplete,
        'decision': {'actor_id': 'hero', 'to_call': 0.0,
                     'facing_action': None},
    })


def _mw_input(state):
    return MWTreeInput(
        state=state,
        ranges=build_ranges_from_state(state, {}, {}),
        street_bets={p.identity: 0.0 for p in state.players},
        action_order=tuple(p.identity for p in state.active_opponents),
        pending_opponents=tuple(p.identity for p in state.active_opponents),
        min_bet=5.0, min_raise=5.0,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes={}, action_space_complete=True,
        action_space_scope='synthetic router fixture')


def test_router_dispatches_one_rival_to_hu_callback():
    state = _state(1)
    seen = []

    def hu_runner(received):
        seen.append(received)
        return SimpleNamespace(status='usable', supported=True,
                               ev_result=object())

    result = evaluate_experimental_actions(state, hu_runner=hu_runner)
    assert result.mode == 'HU'
    assert result.status == 'provisional'
    assert seen == [state]


def test_router_calls_existing_hu_evaluator_with_matching_state_contract():
    preflop = [
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'MP', 'action': 'f', 'amount': 0.0},
        {'pos': 'CO', 'action': 'f', 'amount': 0.0},
        {'pos': 'BTN', 'action': 'f', 'amount': 0.0},
        {'pos': 'SB', 'action': 'f', 'amount': 0.0},
    ]
    identity_by_position = {
        'SB': 'p5', 'BB': 'hero', 'UTG': 'v1',
        'MP': 'p2', 'CO': 'p3', 'BTN': 'p4',
    }
    state_action = {'p': 'post', 'r': 'raise', 'b': 'bet', 'f': 'fold',
                    'c': 'call', 'x': 'check'}
    state = interpret_mw_state({
        'hero_id': 'hero', 'street': 'preflop', 'board': [], 'pot': 4.0,
        'players': [
            {'identity': 'hero', 'position': 'BB', 'status': 'active',
             'hole_cards': ['As', 'Ad'], 'stack': 99.0, 'contribution': 1.0},
            {'identity': 'v1', 'position': 'UTG', 'status': 'active',
             'hole_cards': ['Kc', 'Kd'], 'stack': 97.5, 'contribution': 2.5},
            {'identity': 'p2', 'position': 'MP', 'status': 'folded',
             'stack': 100.0, 'contribution': 0.0},
            {'identity': 'p3', 'position': 'CO', 'status': 'folded',
             'stack': 100.0, 'contribution': 0.0},
            {'identity': 'p4', 'position': 'BTN', 'status': 'folded',
             'stack': 100.0, 'contribution': 0.0},
            {'identity': 'p5', 'position': 'SB', 'status': 'folded',
             'stack': 99.5, 'contribution': 0.5},
        ],
        'actions': [dict(
            action, index=i, street='preflop',
            player_id=identity_by_position[action['pos']],
            action=state_action[action['action']],
            facing=(None if action['action'] in ('p', 'r') else 'raise'))
                    for i, action in enumerate(preflop)],
        'sequence_complete': True,
        'decision': {'actor_id': 'hero', 'to_call': 1.5,
        'facing_action': {'player_id': 'v1', 'action': 'raise',
                                       'amount': 2.5}},
    })
    canonical = canonical_preflop(
        preflop, 'BB', mode='current')
    hu_input = HUEvaluationInput(
        canonical=canonical, pot=4.0, to_call=1.5,
        hero_stack=99.0, villain_stack=97.5,
        equity=0.7, coverage='usable',
        hero_hand=('As', 'Ad'), board=(), bet_fractions=())
    result = evaluate_experimental_actions(state, hu_input=hu_input)
    assert result.mode == 'HU'
    assert result.result is not None
    assert result.status in ('provisional', 'incomplete')


def test_router_treats_a_field_that_folds_to_one_rival_as_hu():
    state = interpret_mw_state({
        'hero_id': 'hero', 'street': 'river',
        'board': ['2c', '3d', '4h', '5s', '9c'],
        'pot': 40.0,
        'players': [
            {'identity': 'hero', 'position': 'BTN', 'status': 'active',
             'hole_cards': ['As', 'Ad'], 'stack': 50.0,
             'contribution': 20.0},
            {'identity': 'v1', 'position': 'SB', 'status': 'folded',
             'stack': 50.0, 'contribution': 0.0},
            {'identity': 'v2', 'position': 'BB', 'status': 'active',
             'hole_cards': ['Qc', 'Qd'], 'stack': 50.0,
             'contribution': 20.0},
        ],
        'actions': [{'index': 0, 'player_id': 'v1', 'action': 'fold',
                     'street': 'preflop', 'amount': 0.0, 'facing': 'raise'}],
        'sequence_complete': True,
        'decision': {'actor_id': 'hero', 'to_call': 0.0,
                     'facing_action': None},
    })
    assert state.mode == 'HU'
    seen = []

    def hu_runner(received):
        seen.append(received)
        return SimpleNamespace(status='usable', supported=True,
                               ev_result=object())

    result = evaluate_experimental_actions(state, hu_runner=hu_runner)
    assert result.mode == 'HU'
    assert result.status == 'provisional'
    assert seen == [state]


def test_router_does_not_degrade_multiway_to_hu_when_mw_model_missing():
    state = _state(2)
    hu_calls = []
    result = evaluate_experimental_actions(
        state, hu_runner=lambda value: hu_calls.append(value),
        mw_input=None, mw_provider=None)
    assert result.mode == 'MW'
    assert result.status == 'incomplete'
    assert result.reason == 'matching_mw_tree_input_required'
    assert hu_calls == []


def test_router_runs_mw_tree_and_preserves_its_incomplete_status():
    state = _state(2)
    hu_calls = []
    result = evaluate_experimental_actions(
        state, hu_runner=lambda value: hu_calls.append(value),
        mw_input=_mw_input(state), mw_provider=LegacyResponseProvider(),
        hero_actions=(ActionSpec('check', 0.0),))
    # The current response provider has no supported sizing-conditioned branch.
    assert result.mode == 'MW'
    assert result.status == 'incomplete'
    assert hu_calls == []


def test_ambiguous_player_count_abstains_before_mode_dispatch():
    state = _state(2, incomplete=True)
    called = []
    result = evaluate_experimental_actions(
        state, hu_runner=lambda value: called.append(value),
        mw_input=None, mw_provider=None)
    assert result.mode is None
    assert result.status == 'incomplete'
    assert called == []
