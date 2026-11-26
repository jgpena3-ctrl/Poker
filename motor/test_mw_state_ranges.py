"""Integration tests from snapshot interpretation through per-player ranges."""
import numpy as np
import pytest

from motor.cards import card_id
from motor.hu_range_contracts import (
    GenericPrior, KnownCards, build_estimated_range,
)
from motor.mw_equity import MultiwayEquityError, calculate_multiway_equity
from motor.mw_ranges import (
    ActionLikelihood, MWRangeError, OpponentRangeState,
    build_ranges_from_state,
    calculate_state_equity, condition_ranges_on_public_card,
    dead_cards_for_state, ranges_for_state,
)
from motor.mw_state import interpret_mw_state
from motor.ranges import COMBO0, COMBO1, N_COMBOS


def _idx(a, b):
    a, b = sorted((card_id(a), card_id(b)))
    return int(np.flatnonzero((COMBO0 == a) & (COMBO1 == b))[0])


def _estimate(player, hero=('As', 'Ad'), board=('2c', '3d', '4h'),
              combos=(('Kc', 'Kd'), ('Qc', 'Qd'))):
    weights = np.zeros(N_COMBOS, dtype=np.float64)
    for combo in combos:
        weights[_idx(*combo)] = 1.0
    prior = GenericPrior('synthetic_fixture', weights, 'manual', 'exact')
    return build_estimated_range(
        player=player, street='flop', board=board, prior=prior,
        likelihood=np.ones(N_COMBOS),
        known_cards=KnownCards(hero_hand=hero, board=board),
        likelihood_model='synthetic_fixture')


def _raw_state(*, statuses=('active', 'active'), actions=None,
               facing=None, to_call=5.0, sequence_complete=True):
    identities = ('hero', 'v1', 'v2', 'v3')[:len(statuses) + 1]
    positions = ('BTN', 'SB', 'BB', 'UTG')
    players = []
    for i, identity in enumerate(identities):
        row = {'identity': identity, 'position': positions[i],
               'status': statuses[i - 1] if i else 'active',
               'stack': 100.0, 'contribution': 5.0 if i else 0.0}
        if i == 0:
            row['hole_cards'] = ['As', 'Ad']
        players.append(row)
    return {
        'hero_id': 'hero', 'street': 'flop', 'board': ['2c', '3d', '4h'],
        'players': players, 'actions': actions or [], 'pot': 5.0 * len(statuses),
        'sequence_complete': sequence_complete,
        'decision': {'actor_id': 'hero', 'facing_action': facing,
                     'to_call': to_call},
    }


def test_state_keeps_observed_unknown_and_identity_per_seat():
    state = interpret_mw_state(_raw_state(
        actions=[{'index': 0, 'player_id': 'v1', 'action': 'bet',
                  'street': 'flop', 'amount': 5.0, 'facing': None}],
        facing={'player_id': 'v1', 'action': 'bet', 'amount': 5.0}))
    assert state.ready
    assert state.mode == 'MW'
    assert state.hero_id == 'hero'
    assert [p.identity for p in state.active_opponents] == ['v1', 'v2']
    assert state.hero.hole_cards.source == 'observed'
    assert state.players[1].hole_cards.source == 'unknown'
    assert state.players[1].position.value == 'SB'
    assert state.to_call.value == 5.0


def test_three_rivals_are_counted_individually_on_a_four_player_plus_flop():
    state = interpret_mw_state(_raw_state(
        statuses=('active', 'active', 'active'), facing=None, to_call=0.0))
    assert state.ready
    assert state.mode == 'MW'
    assert tuple(p.identity for p in state.active_opponents) == (
        'v1', 'v2', 'v3')


def test_missing_status_in_incomplete_sequence_is_not_assumed_active():
    raw = _raw_state(facing=None, to_call=0.0, sequence_complete=False)
    del raw['players'][2]['status']
    state = interpret_mw_state(raw)
    assert state.status == 'unresolved'
    assert 'v2:player_status_unknown' in state.issues
    assert [p.identity for p in state.active_opponents] == ['v1']


def test_unknown_board_and_missing_hero_cards_block_state():
    raw = _raw_state(facing=None, to_call=0.0)
    raw['board'] = {'source': 'unknown', 'value': None,
                    'reason': 'capture_not_ready'}
    state = interpret_mw_state(raw)
    assert state.status == 'unresolved'
    assert state.board_evidence.source == 'unknown'
    assert 'board_unknown' in state.issues

    raw = _raw_state(facing=None, to_call=0.0)
    raw['players'][0]['hole_cards'] = []
    state = interpret_mw_state(raw)
    assert state.status == 'unresolved'
    assert 'hero_hole_cards_unknown' in state.issues


def test_complete_action_sequence_allows_explicitly_marked_inference():
    raw = _raw_state(facing=None, to_call=0.0, sequence_complete=True)
    del raw['players'][2]['status']
    state = interpret_mw_state(raw)
    assert state.ready
    assert state.players[2].status.value == 'active'
    assert state.players[2].status.source == 'inferred'


def test_overlapping_known_cards_make_state_unresolved():
    raw = _raw_state(facing=None, to_call=0.0)
    raw['players'][1]['hole_cards'] = ['Kc', 'Kd']
    raw['players'][2]['hole_cards'] = ['Kc', 'Qd']
    state = interpret_mw_state(raw)
    assert state.status == 'unresolved'
    assert 'known_cards_overlap' in state.issues


def test_folded_status_and_action_must_agree():
    raw = _raw_state(
        statuses=('folded', 'active'),
        actions=[{'index': 0, 'player_id': 'v1', 'action': 'fold',
                  'street': 'flop', 'amount': 0.0}],
        facing=None, to_call=0.0)
    state = interpret_mw_state(raw)
    assert state.ready
    assert [p.identity for p in state.active_opponents] == ['v2']
    raw['players'][1]['status'] = 'active'
    contradicted = interpret_mw_state(raw)
    assert contradicted.status == 'unresolved'
    assert 'v1:fold_status_contradiction' in contradicted.issues


def test_fold_removes_rival_and_known_muck_cards_block_the_hu_range():
    state = interpret_mw_state(_raw_state(
        statuses=('folded', 'active'),
        actions=[{'index': 0, 'player_id': 'v1', 'action': 'fold',
                  'street': 'flop', 'amount': 0.0}],
        facing=None, to_call=0.0))
    assert state.ready
    assert tuple(p.identity for p in state.active_opponents) == ('v2',)
    assert state.mode == 'HU'
    dead = dead_cards_for_state(state)
    assert dead.complete is False
    assert dead.folded_with_unknown_cards == ('v1',)
    unknown_dead_ranges = build_ranges_from_state(
        state, {'v2': _estimate('v2', combos=(('Qc', 'Qd'),))}, {})
    provisional = calculate_state_equity(state, unknown_dead_ranges, exact=True)
    assert 'unobserved_folded_hole_cards_not_integrated' in \
        provisional.limitations

    # Reparse with the muck cards explicitly observed, then the remaining
    # one-opponent equity uses them as blockers and documents the scope.
    raw = _raw_state(
        statuses=('folded', 'active'),
        actions=[{'index': 0, 'player_id': 'v1', 'action': 'fold',
                  'street': 'flop', 'amount': 0.0}],
        facing=None, to_call=0.0)
    raw['players'][1]['hole_cards'] = ['Kc', 'Kd']
    state = interpret_mw_state(raw)
    dead = dead_cards_for_state(state)
    assert dead.complete
    assert dead.known_cards == ('Kc', 'Kd')
    ranges = build_ranges_from_state(
        state, {'v2': _estimate('v2', combos=(('Qc', 'Qd'),))}, {})
    result = calculate_state_equity(state, ranges, exact=True)
    assert result.dead_cards == dead.known_cards
    assert result.limitations == ()
    assert result.model == 'single_opponent_marginal'


def test_action_likelihood_updates_only_the_actor_range():
    action = {'index': 0, 'player_id': 'v1', 'action': 'bet',
              'street': 'flop', 'amount': 5.0, 'facing': None}
    state = interpret_mw_state(_raw_state(
        actions=[action], facing={'player_id': 'v1', 'action': 'bet',
                                  'amount': 5.0}))
    initial = {
        'v1': _estimate('v1', combos=(('Kc', 'Kd'), ('Qc', 'Qd'))),
        'v2': _estimate('v2', combos=(('Jc', 'Jd'), ('Tc', 'Td'))),
    }
    like = np.ones(N_COMBOS)
    like[_idx('Kc', 'Kd')] = 0.0
    ranges = build_ranges_from_state(
        state, initial,
        {0: ActionLikelihood('test_likelihood', 'exact', like,
                             'v1', 'bet', 'flop', 'SB',
                             ('2c', '3d', '4h'), None, 5.0,
                             'synthetic_bet_size_5')})
    assert ranges['v1'].posterior[_idx('Kc', 'Kd')] == 0.0
    assert ranges['v1'].posterior[_idx('Qc', 'Qd')] == pytest.approx(1.0)
    np.testing.assert_array_equal(
        ranges['v2'].posterior, initial['v2'].posterior)
    equity_ranges = ranges_for_state(state, ranges)
    assert [r.identity for r in equity_ranges] == ['v1', 'v2']


def test_missing_likelihood_marks_only_that_range_incomplete_and_blocks_equity():
    state = interpret_mw_state(_raw_state(
        actions=[{'index': 0, 'player_id': 'v1', 'action': 'bet',
                  'street': 'flop', 'amount': 5.0}],
        facing={'player_id': 'v1', 'action': 'bet', 'amount': 5.0}))
    initial = {'v1': _estimate('v1'), 'v2': _estimate(
        'v2', combos=(('Jc', 'Jd'), ('Tc', 'Td')))}
    ranges = build_ranges_from_state(state, initial, {})
    assert not ranges['v1'].usable_distribution
    assert ranges['v2'].usable_distribution
    with pytest.raises(MWRangeError, match='incompleto'):
        ranges_for_state(state, ranges)
    with pytest.raises(MultiwayEquityError, match='propio OpponentRange'):
        calculate_multiway_equity(
            ['As', 'Ad'], ['2c', '3d', '4h'],
            [ranges['v1'], ranges['v2']])


def test_declared_preconditioned_action_is_not_applied_twice():
    state = interpret_mw_state(_raw_state(
        actions=[{'index': 0, 'player_id': 'v1', 'action': 'bet',
                  'street': 'flop', 'amount': 5.0}],
        facing={'player_id': 'v1', 'action': 'bet', 'amount': 5.0}))
    initial = {'v1': _estimate('v1'),
               'v2': _estimate('v2', combos=(('Jc', 'Jd'), ('Tc', 'Td')))}
    ranges = build_ranges_from_state(
        state, initial, {}, conditioned_action_indices={'v1': (0,)})
    assert ranges['v1'].usable_distribution
    assert ranges['v1'].updates[0].status == 'already_conditioned'


def test_public_turn_card_conditions_each_range_once_without_replaying_actions():
    estimates = {
        'v1': _estimate('v1', combos=(('Kc', 'Kd'), ('Qc', 'Qd'))),
        'v2': _estimate('v2', combos=(('Jc', 'Jd'), ('Tc', 'Td'))),
    }
    before = {identity: OpponentRangeState.from_estimated(
        identity, 'SB' if identity == 'v1' else 'BB', estimate)
        for identity, estimate in estimates.items()}
    updated = condition_ranges_on_public_card(
        before, 'Kc', event_index=7)
    assert updated['v1'].posterior[_idx('Kc', 'Kd')] == 0.0
    assert updated['v1'].posterior[_idx('Qc', 'Qd')] == pytest.approx(1.0)
    assert updated['v1'].updates[-1].event_index == 7
    np.testing.assert_array_equal(updated['v2'].posterior, before['v2'].posterior)


def test_exact_equity_and_seeded_sampling_agree_within_sampling_error():
    state = interpret_mw_state(_raw_state(facing=None, to_call=0.0))
    initial = {
        'v1': _estimate('v1', combos=(('Kc', 'Kd'),)),
        'v2': _estimate('v2', combos=(('Qc', 'Qd'),)),
    }
    ranges = build_ranges_from_state(state, initial, {})
    exact = calculate_state_equity(state, ranges, exact=True)
    sampled = calculate_state_equity(
        state, ranges, samples=2000, seed=20261125)
    assert exact.exact
    assert sampled.standard_error is not None
    assert abs(exact.equity - sampled.equity) <= \
        4 * sampled.standard_error + 0.01


def test_four_seat_flop_runs_each_rival_range_through_joint_equity():
    state = interpret_mw_state(_raw_state(
        statuses=('active', 'active', 'active'), facing=None, to_call=0.0))
    estimates = {
        'v1': _estimate('v1', combos=(('Kc', 'Kd'),)),
        'v2': _estimate('v2', combos=(('Qc', 'Qd'),)),
        'v3': _estimate('v3', combos=(('Jc', 'Jd'),)),
    }
    assert len(state.active_opponents) == 3
    ranges = build_ranges_from_state(state, estimates, {})
    result = calculate_state_equity(state, ranges, exact=True)
    assert result.exact
    assert result.opponents == ('v1', 'v2', 'v3')
    assert result.valid_joint_assignments == 1
    assert result.runouts_per_assignment == 820
