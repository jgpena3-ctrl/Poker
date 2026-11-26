"""Synthetic-only mechanics tests for the fail-closed MW response tree."""
import time

import numpy as np
import pytest
from dataclasses import replace
from types import SimpleNamespace

from motor.cards import card_id
from motor.mw_ranges import (
    OpponentRangeState, build_ranges_from_state,
)
from motor.mw_response_tree import (
    ActionSpec, LegacyResponseProvider, MWTreeInput, MWTreeLimits,
    ResponseAssessment, ResponseDistribution, ResponseOutcome,
    evaluate_mw_action_tree, legal_hero_actions,
)
from motor.mw_state import interpret_mw_state
from motor.ranges import COMBO0, COMBO1, N_COMBOS
import motor.mw_response_tree as mw_tree


RIVER = ('2c', '3d', '4h', '5s', '9c')
HERO = ('As', 'Ad')
HANDS = {'v1': ('Kc', 'Kd'), 'v2': ('Qc', 'Qd'), 'v3': ('Jc', 'Jd')}


def _raw_state(*, street='river', n_opponents=2, stacks=None,
               contributions=None, statuses=None, board=RIVER, actions=()):
    identities = ('hero', 'v1', 'v2', 'v3')[:n_opponents + 1]
    stacks = stacks or {'hero': 50.0, **{p: 5.0 for p in identities[1:]}}
    contributions = contributions or {p: 20.0 for p in identities}
    statuses = statuses or {p: 'active' for p in identities}
    positions = dict(zip(identities, ('BTN', 'SB', 'BB', 'UTG')))
    players = []
    for player in identities:
        row = {
            'identity': player, 'position': positions[player],
            'status': statuses[player], 'stack': stacks[player],
            'contribution': contributions[player],
        }
        if player == 'hero':
            row['hole_cards'] = list(HERO)
        else:
            row['hole_cards'] = list(HANDS[player])
        players.append(row)
    return {
        'hero_id': 'hero', 'street': street, 'board': list(board),
        'pot': sum(contributions.values()), 'players': players,
        'actions': list(actions), 'sequence_complete': True,
        'decision': {'actor_id': 'hero', 'to_call': 0.0,
                     'facing_action': None},
    }


def _input(*, n=2, street='river', stacks=None, contributions=None,
           response_sizes=None, pending=None, statuses=None,
           action_space_complete=True, hero_future_sizes=None, history=(),
           board=None):
    board = board or (RIVER if street == 'river' else
                      RIVER[:4] if street == 'turn' else RIVER[:3])
    state = interpret_mw_state(_raw_state(
        n_opponents=n, street=street, stacks=stacks,
        contributions=contributions, statuses=statuses, board=board,
        actions=history))
    initial = {}
    ranges = build_ranges_from_state(state, initial, {})
    order = tuple(p.identity for p in state.active_opponents
                  if p.status.value == 'active')
    pending = tuple(order if pending is None else pending)
    bets = {p.identity: 0.0 for p in state.players}
    return MWTreeInput(
        state=state, ranges=ranges, street_bets=bets,
        action_order=order, pending_opponents=pending,
        min_bet=5.0, min_raise=5.0,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes=response_sizes or {},
        hero_future_sizes=hero_future_sizes or {},
        action_space_complete=action_space_complete,
        action_space_scope=(
            'synthetic finite response sizes' if action_space_complete else None))


class _ConditionalSyntheticProvider:
    """Exact fixture counts; intentionally not a real poker behavior model."""

    def __init__(self, weights=None, *, delay=0.0):
        self.weights = weights or {}
        self.delay = delay
        self.calls = []

    def assess(self, context):
        if self.delay:
            time.sleep(self.delay)
        self.calls.append(context)
        configured = self.weights.get(
            (context.player_id, tuple(context.history)),
            self.weights.get(context.player_id, {}))
        raw = [max(1, int(configured.get(spec.action, 1)))
               for spec in context.legal_actions]
        denominator = sum(raw)
        outcomes = tuple(
            ResponseOutcome(
                spec=spec, probability=count / denominator,
                numerator=count, denominator=denominator,
                source='synthetic_fixture_counts', coverage='exact',
                uncertainty='not_quantified')
            for spec, count in zip(context.legal_actions, raw))
        distribution = ResponseDistribution(
            player_id=context.player_id,
            context_key=context.context_key,
            source='synthetic_fixture_counts', source_kind='synthetic',
            outcomes=outcomes, conditional_on_history=True,
            action_space_complete=True, coverage='exact')
        return ResponseAssessment('available', distribution, None,
                                  {'synthetic_fixture': True})


def _fold_call_weights(*, fold=1, allin=1):
    return {'fold': fold, 'all_in': allin}


def test_three_player_flop_fold_and_call_reaches_showdown_allin():
    data = _input(n=2, street='flop')
    provider = _ConditionalSyntheticProvider({
        'v1': _fold_call_weights(fold=3, allin=7),
        'v2': _fold_call_weights(fold=4, allin=6),
    })
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider,
        limits=MWTreeLimits(exact_equity=False, equity_samples=500,
                            timeout_seconds=10.0, max_nodes=500))
    action = result.actions[0]
    assert result.status == 'provisional'
    assert action.status == 'provisional'
    assert action.ev is not None
    assert action.terminal_nodes == 4
    assert action.equity_error_bound is not None
    assert {call.player_id for call in provider.calls} == {'v1', 'v2'}
    assert result.nodes < 500


def test_three_players_both_pay_and_ev_subtracts_only_new_hero_bet():
    data = _input(n=2, street='river')
    provider = _ConditionalSyntheticProvider({
        'v1': _fold_call_weights(fold=1, allin=9),
        'v2': _fold_call_weights(fold=1, allin=9),
    })
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider)
    assert result.status == 'provisional'
    assert result.actions[0].ev is not None
    # All-call leaf is 75 pot - 5 incremental hero bet = 70, not 50
    # (which would incorrectly charge the hero's old 20-chip contribution).
    assert result.actions[0].ev == pytest.approx(69.0)


def test_response_tree_includes_a_normal_call_when_stack_exceeds_call():
    data = _input(n=2, street='river',
                  stacks={'hero': 50.0, 'v1': 6.0, 'v2': 6.0})
    provider = _ConditionalSyntheticProvider({
        'v1': {'fold': 1, 'call': 8, 'all_in': 1},
        'v2': {'fold': 1, 'call': 8, 'all_in': 1},
    })
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider)
    assert result.actions[0].ev is not None
    assert any(any(spec.action == 'call' for spec in context.legal_actions)
               for context in provider.calls)


def test_three_players_raise_then_fold_is_a_legal_sequential_path():
    # Hero is all-in, so a later raise does not require an unmodeled hero reply.
    stacks = {'hero': 5.0, 'v1': 20.0, 'v2': 5.0}
    data = _input(n=2, stacks=stacks,
                  response_sizes={'v1': {'raise': (10.0,)}},
                  action_space_complete=True)
    provider = _ConditionalSyntheticProvider({
        'v1': {'fold': 1, 'call': 1, 'raise': 8, 'all_in': 1},
        'v2': {'fold': 5, 'all_in': 5},
    })
    result = evaluate_mw_action_tree(
        data, [ActionSpec('all_in', 5.0)], provider)
    assert result.actions[0].ev is not None
    raised_nodes = [ctx for ctx in provider.calls
                    if ctx.player_id == 'v2'
                    and any(actor == 'v1' and action == 'raise'
                            for _street, actor, action, _amount, _facing
                            in ctx.history)]
    assert raised_nodes, 'v2 debe recibir decisión tras la subida de v1'
    assert result.actions[0].status == 'provisional'


def test_two_successive_raises_reopen_the_correct_actors():
    data = _input(
        n=2, stacks={'hero': 5.0, 'v1': 20.0, 'v2': 20.0},
        response_sizes={'v1': {'raise': (10.0,)},
                        'v2': {'raise': (15.0,)}},
        action_space_complete=True)
    provider = _ConditionalSyntheticProvider()
    result = evaluate_mw_action_tree(
        data, [ActionSpec('all_in', 5.0)], provider,
        limits=MWTreeLimits(max_nodes=1_000, max_depth=18,
                            timeout_seconds=5.0))
    reopened_v1 = [ctx for ctx in provider.calls
                   if ctx.player_id == 'v1'
                    and ('river', 'v1', 'raise', 10.0, 'all_in') in ctx.history
                    and ('river', 'v2', 'raise', 15.0, 'raise') in ctx.history]
    assert reopened_v1
    assert result.nodes < 1_000


def test_one_allin_rival_and_another_rival_with_remaining_stack():
    raw = _raw_state(
        stacks={'hero': 50.0, 'v1': 0.0, 'v2': 5.0},
        contributions={'hero': 20.0, 'v1': 25.0, 'v2': 20.0},
        statuses={'hero': 'active', 'v1': 'all_in', 'v2': 'active'})
    raw['actions'] = [{'index': 0, 'player_id': 'v1', 'action': 'all_in',
                       'street': 'river', 'amount': 5.0, 'facing': None}]
    raw['decision'] = {
        'actor_id': 'hero', 'to_call': 5.0,
        'facing_action': {'player_id': 'v1', 'action': 'all_in', 'amount': 5.0},
    }
    state = interpret_mw_state(raw)
    ranges = build_ranges_from_state(state, {}, {})
    data = MWTreeInput(
        state=state, ranges=ranges,
        street_bets={'hero': 0.0, 'v1': 5.0, 'v2': 0.0},
        action_order=('v2',), pending_opponents=('v2',),
        min_bet=5.0, min_raise=5.0,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes={},
        action_space_complete=True,
        action_space_scope='synthetic call/fold')
    provider = _ConditionalSyntheticProvider()
    result = evaluate_mw_action_tree(
        data, [ActionSpec('call', 5.0)], provider)
    assert result.actions[0].ev is not None
    assert [context.player_id for context in provider.calls] == ['v2']


def test_sidepot_that_excludes_hero_is_not_added_to_hero_payout():
    raw = _raw_state(
        stacks={'hero': 10.0, 'v1': 0.0, 'v2': 0.0},
        contributions={'hero': 20.0, 'v1': 50.0, 'v2': 50.0},
        statuses={'hero': 'active', 'v1': 'all_in', 'v2': 'all_in'})
    raw['actions'] = [
        {'index': 0, 'player_id': 'v1', 'action': 'all_in',
         'street': 'river', 'amount': 30.0, 'facing': None},
        {'index': 1, 'player_id': 'v2', 'action': 'all_in',
         'street': 'river', 'amount': 30.0, 'facing': 'all_in'},
    ]
    raw['decision'] = {
        'actor_id': 'hero', 'to_call': 30.0,
        'facing_action': {'player_id': 'v2', 'action': 'all_in',
                          'amount': 30.0},
    }
    state = interpret_mw_state(raw)
    ranges = build_ranges_from_state(state, {}, {})
    data = MWTreeInput(
        state=state, ranges=ranges,
        street_bets={'hero': 0.0, 'v1': 30.0, 'v2': 30.0},
        action_order=(), pending_opponents=(), min_bet=5.0,
        min_raise=5.0, action_order_source='synthetic',
        pending_source='synthetic', response_sizes={}, action_space_complete=True,
        action_space_scope='forced showdown')
    result = evaluate_mw_action_tree(
        data, [ActionSpec('all_in', 10.0)], _ConditionalSyntheticProvider())
    assert result.actions[0].ev == pytest.approx(80.0)
    assert result.actions[0].status == 'provisional'


def test_response_tree_closes_with_one_allin_and_one_stack_left():
    raw = _raw_state(
        stacks={'hero': 50.0, 'v1': 0.0, 'v2': 5.0},
        contributions={'hero': 20.0, 'v1': 25.0, 'v2': 20.0},
        statuses={'hero': 'active', 'v1': 'all_in', 'v2': 'active'})
    raw['actions'] = [{'index': 0, 'player_id': 'v1', 'action': 'all_in',
                       'street': 'river', 'amount': 5.0, 'facing': None}]
    raw['decision'] = {
        'actor_id': 'hero', 'to_call': 5.0,
        'facing_action': {'player_id': 'v1', 'action': 'all_in', 'amount': 5.0},
    }
    state = interpret_mw_state(raw)
    data = MWTreeInput(
        state=state, ranges=build_ranges_from_state(state, {}, {}),
        street_bets={'hero': 0.0, 'v1': 5.0, 'v2': 0.0},
        action_order=('v2',), pending_opponents=('v2',),
        min_bet=5.0, min_raise=5.0,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes={},
        action_space_complete=True,
        action_space_scope='synthetic call/fold')
    provider = _ConditionalSyntheticProvider()
    result = evaluate_mw_action_tree(
        data, [ActionSpec('call', 5.0)], provider)
    assert result.actions[0].ev is not None
    assert [context.player_id for context in provider.calls] == ['v2']


def test_sidepot_between_other_allins_is_excluded_from_hero_ev():
    raw = _raw_state(
        stacks={'hero': 10.0, 'v1': 0.0, 'v2': 0.0},
        contributions={'hero': 20.0, 'v1': 50.0, 'v2': 50.0},
        statuses={'hero': 'active', 'v1': 'all_in', 'v2': 'all_in'})
    raw['actions'] = [
        {'index': 0, 'player_id': 'v1', 'action': 'all_in',
         'street': 'river', 'amount': 30.0, 'facing': None},
        {'index': 1, 'player_id': 'v2', 'action': 'all_in',
         'street': 'river', 'amount': 30.0, 'facing': 'all_in'},
    ]
    raw['decision'] = {
        'actor_id': 'hero', 'to_call': 30.0,
        'facing_action': {'player_id': 'v2', 'action': 'all_in',
                          'amount': 30.0},
    }
    state = interpret_mw_state(raw)
    data = MWTreeInput(
        state=state, ranges=build_ranges_from_state(state, {}, {}),
        street_bets={'hero': 0.0, 'v1': 30.0, 'v2': 30.0},
        action_order=(), pending_opponents=(), min_bet=5.0,
        min_raise=5.0, action_order_source='synthetic',
        pending_source='synthetic', response_sizes={}, action_space_complete=True,
        action_space_scope='forced showdown')
    result = evaluate_mw_action_tree(
        data, [ActionSpec('all_in', 10.0)], _ConditionalSyntheticProvider())
    assert result.actions[0].ev == pytest.approx(80.0)
    assert result.actions[0].status == 'provisional'


def test_single_eligible_rival_uses_existing_hu_equity_contract(monkeypatch):
    state = interpret_mw_state({
        'hero_id': 'hero', 'street': 'river', 'board': list(RIVER),
        'pot': 10.0,
        'players': [
            {'identity': 'hero', 'position': 'BTN', 'status': 'active',
             'hole_cards': HERO, 'stack': 10.0, 'contribution': 0.0},
            {'identity': 'v1', 'position': 'BB', 'status': 'all_in',
             'hole_cards': HANDS['v1'], 'stack': 0.0, 'contribution': 10.0},
        ],
        'actions': [{'index': 0, 'player_id': 'v1', 'action': 'all_in',
                     'street': 'river', 'amount': 10.0, 'facing': None}],
        'sequence_complete': True,
        'decision': {'actor_id': 'hero', 'to_call': 10.0,
                     'facing_action': {'player_id': 'v1', 'action': 'all_in',
                                       'amount': 10.0}},
    })
    assert state.mode == 'HU'
    calls = []

    def fake_hu_equity(hero, board, *, villain_reach, **kwargs):
        calls.append((tuple(hero), tuple(board), villain_reach.copy()))
        return SimpleNamespace(value=0.6, method='river_exact',
                               uncertainty_reason=None)

    monkeypatch.setattr(mw_tree, 'equity_to_showdown', fake_hu_equity)
    data = MWTreeInput(
        state=state, ranges=build_ranges_from_state(state, {}, {}),
        street_bets={'hero': 0.0, 'v1': 10.0},
        action_order=(), pending_opponents=(), min_bet=5.0, min_raise=5.0,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes={}, action_space_complete=True,
        action_space_scope='synthetic forced HU showdown')
    result = evaluate_mw_action_tree(
        data, [ActionSpec('call', 10.0)], LegacyResponseProvider())
    assert calls
    assert result.actions[0].ev == pytest.approx(2.0)


def test_four_players_can_fold_sequentially_without_double_action():
    data = _input(n=3, street='river')
    provider = _ConditionalSyntheticProvider({
        'v1': _fold_call_weights(fold=9, allin=1),
        'v2': _fold_call_weights(fold=9, allin=1),
        'v3': _fold_call_weights(fold=9, allin=1),
    })
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider)
    assert result.actions[0].terminal_nodes == 8
    assert {ctx.player_id for ctx in provider.calls} == {'v1', 'v2', 'v3'}


def test_different_rival_probabilities_are_conditioned_on_prior_history():
    data = _input(n=2)
    provider = _ConditionalSyntheticProvider({
        'v1': _fold_call_weights(fold=2, allin=8),
        ('v2', (('river', 'hero', 'bet', 5.0, 'none'),
                ('river', 'v1', 'fold', 0.0, 'bet'))):
            _fold_call_weights(fold=5, allin=5),
        ('v2', (('river', 'hero', 'bet', 5.0, 'none'),
                ('river', 'v1', 'all_in', 5.0, 'bet'))):
            _fold_call_weights(fold=1, allin=9),
    })
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider)
    assert result.actions[0].ev == pytest.approx(68.1)
    v2_contexts = [c for c in provider.calls if c.player_id == 'v2']
    assert len(v2_contexts) == 2
    assert v2_contexts[0].history != v2_contexts[1].history
    after_fold = next(c for c in v2_contexts
                      if any(a == 'fold'
                             for _street, _p, a, _amount, _facing in c.history))
    assert dict(after_fold.statuses)['v1'] == 'folded'


def test_unmodeled_legacy_response_model_abstains_with_context_gaps():
    data = _input(n=2)
    provider = LegacyResponseProvider(
        oracle=object(), postflop_model=object(), profiles={'v1': 'PEZ'})
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider)
    assert result.status == 'incomplete'
    assert result.actions[0].ev is None
    assert 'legacy_response_context_insufficient' in result.actions[0].reason
    evidence = result.actions[0].response_evidence[0]['evidence']
    assert evidence['heuristic_fallback_used'] is False
    assert 'bet_sizing_conditional' in evidence['unmodeled']
    assert 'all_in_response_category' in evidence['unmodeled']
    assert 'all_in' not in evidence['available_action_categories']
    assert evidence['denominator'] is None


def test_missing_branch_probability_is_not_renormalized_away():
    class PartialProvider:
        def assess(self, context):
            fold = next(s for s in context.legal_actions if s.action == 'fold')
            allin = next(s for s in context.legal_actions if s.action == 'all_in')
            distribution = ResponseDistribution(
                player_id=context.player_id, context_key=context.context_key,
                source='partial fixture', source_kind='synthetic',
                outcomes=(
                    ResponseOutcome(fold, 0.5, 1, 2, 'fixture', 'exact'),
                    ResponseOutcome(allin, None, None, None,
                                    'uncovered', 'incomplete')),
                conditional_on_history=True, action_space_complete=False,
                coverage='incomplete', reasons=('allin_likelihood_missing',))
            return ResponseAssessment('available', distribution, None)

    result = evaluate_mw_action_tree(
        _input(n=2), [ActionSpec('bet', 5.0)], PartialProvider())
    action = result.actions[0]
    assert action.status == 'incomplete'
    assert action.ev is None
    assert action.covered_probability == pytest.approx(0.5)


def test_missing_range_likelihood_does_not_update_prior_or_report_ev():
    data = _input(n=2, street='river')
    # Replace v1's exact revealed range with a complete, non-known synthetic
    # range: behavior is needed to update it after its response.
    a, b = sorted((card_id('Kc'), card_id('Kd')))
    combo_index = int(np.flatnonzero((COMBO0 == a) & (COMBO1 == b))[0])
    posterior = np.zeros(N_COMBOS)
    posterior[combo_index] = 1.0
    ranges = dict(data.ranges)
    ranges['v1'] = OpponentRangeState(
        identity='v1', position='SB', posterior=posterior,
        source='synthetic prior fixture', source_kind='synthetic',
        coverage='exact', complete=True)
    data = MWTreeInput(
        state=data.state, ranges=ranges, street_bets=data.street_bets,
        action_order=data.action_order, pending_opponents=data.pending_opponents,
        min_bet=data.min_bet, min_raise=data.min_raise,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes=data.response_sizes,
        action_space_complete=True,
        action_space_scope='synthetic call/fold')
    provider = _ConditionalSyntheticProvider()
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider)
    assert result.status == 'incomplete'
    assert result.actions[0].ev is None
    assert 'range_likelihood_missing' in result.actions[0].reason


def test_supported_likelihood_updates_only_the_acting_range_per_branch():
    raw = _raw_state()
    del raw['players'][1]['hole_cards']
    state = interpret_mw_state(raw)
    a, b = sorted((card_id('Kc'), card_id('Kd')))
    combo_index = int(np.flatnonzero((COMBO0 == a) & (COMBO1 == b))[0])
    posterior = np.zeros(N_COMBOS)
    posterior[combo_index] = 1.0
    v1_range = OpponentRangeState(
        identity='v1', position='SB', posterior=posterior,
        source='synthetic pre-action range', source_kind='synthetic',
        coverage='exact', complete=True)
    v1_before = v1_range.posterior.copy()
    v2_range = OpponentRangeState.from_known_cards(
        'v2', 'BB', HANDS['v2'], source='observed_hole_cards')
    data = MWTreeInput(
        state=state, ranges={'v1': v1_range, 'v2': v2_range},
        street_bets={'hero': 0.0, 'v1': 0.0, 'v2': 0.0},
        action_order=('v1', 'v2'), pending_opponents=('v1', 'v2'),
        min_bet=5.0, min_raise=5.0,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes={},
        action_space_complete=True,
        action_space_scope='synthetic call/fold')

    class LikelihoodProvider(_ConditionalSyntheticProvider):
        def assess(self, context):
            assessment = super().assess(context)
            if context.player_id != 'v1':
                return assessment
            likelihood = np.ones(N_COMBOS)
            outcomes = tuple(replace(
                outcome, range_likelihood=likelihood,
                range_source='synthetic_contextual_likelihood',
                range_coverage='exact')
                for outcome in assessment.distribution.outcomes)
            dist = replace(assessment.distribution, outcomes=outcomes)
            return ResponseAssessment('available', dist, None,
                                      {'synthetic_fixture': True})

    provider = LikelihoodProvider()
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider)
    assert result.actions[0].ev is not None
    np.testing.assert_array_equal(v1_range.posterior, v1_before)
    v1_evidence = [entry for entry in result.actions[0].response_evidence
                   if entry['player_id'] == 'v1']
    assert v1_evidence
    assert all(
        branch['range_source'] == 'synthetic_contextual_likelihood'
        for entry in v1_evidence
        for branch in entry['distribution']['outcomes'])
    next_actor_contexts = [context for context in provider.calls
                           if context.player_id == 'v2']
    assert next_actor_contexts
    assert all(dict(context.all_range_states)['v1'].updates[-1].event_kind
               == 'simulated_response'
               for context in next_actor_contexts)


def test_illegal_hero_raise_is_not_inserted_into_tree():
    # No bet is outstanding; a raise is not legal.
    data = _input(n=2)
    result = evaluate_mw_action_tree(
        data, [ActionSpec('raise', 5.0)], _ConditionalSyntheticProvider())
    assert result.actions[0].status == 'not_calculable'
    assert 'illegal_hero_action' in result.actions[0].reason


def test_node_limit_and_timeout_fail_closed():
    data = _input(n=2)
    provider = _ConditionalSyntheticProvider()
    limited = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider,
        limits=MWTreeLimits(max_nodes=1))
    assert limited.status == 'incomplete'
    assert 'max_nodes_exceeded' in limited.actions[0].reason

    depth_limited = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], _ConditionalSyntheticProvider(),
        limits=MWTreeLimits(max_depth=1))
    assert depth_limited.status == 'incomplete'
    assert 'max_depth_exceeded' in depth_limited.actions[0].reason

    branch_limited = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], _ConditionalSyntheticProvider(),
        limits=MWTreeLimits(max_branches_per_node=1))
    assert branch_limited.status == 'incomplete'
    assert 'max_branches_per_node_exceeded' in \
        branch_limited.actions[0].reason

    slow = _ConditionalSyntheticProvider(delay=0.01)
    timed = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], slow,
        limits=MWTreeLimits(timeout_seconds=0.001))
    assert timed.status == 'incomplete'
    assert 'timeout' in timed.actions[0].reason


def test_legal_hero_action_space_exposes_check_bet_call_raise_and_allin():
    unopened = _input(n=2)
    actions = legal_hero_actions(unopened, bet_sizes=(5.0,))
    assert {a.action for a in actions} == {'check', 'bet', 'all_in'}

    raw = _raw_state()
    raw['actions'] = [{'index': 0, 'player_id': 'v1', 'action': 'bet',
                       'street': 'river', 'amount': 5.0, 'facing': None}]
    raw['decision'] = {
        'actor_id': 'hero', 'to_call': 5.0,
        'facing_action': {'player_id': 'v1', 'action': 'bet', 'amount': 5.0},
    }
    state = interpret_mw_state(raw)
    ranges = build_ranges_from_state(state, {}, {})
    facing = MWTreeInput(
        state=state, ranges=ranges,
        street_bets={'hero': 0.0, 'v1': 5.0, 'v2': 0.0},
        action_order=('v1', 'v2'), pending_opponents=('v2',),
        min_bet=5.0, min_raise=5.0,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes={'v1': {'raise': (10.0,)},
                         'v2': {'raise': (10.0,)}},
        action_space_complete=True,
        action_space_scope='synthetic raise size 10')
    facing_actions = legal_hero_actions(facing, raise_sizes=(10.0,))
    assert {a.action for a in facing_actions} == {
        'fold', 'call', 'raise', 'all_in'}


def test_opponent_check_and_bet_are_distinct_legal_tree_responses():
    data = _input(
        n=2, street='flop',
        stacks={'hero': 10.0, 'v1': 10.0, 'v2': 10.0},
        response_sizes={'v1': {'bet': (5.0,)},
                        'v2': {'bet': (5.0,)}},
        hero_future_sizes={'raise': (10.0,)})
    provider = _ConditionalSyntheticProvider()
    result = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)], provider,
        limits=MWTreeLimits(max_nodes=20, timeout_seconds=5.0))
    first_node = next(ctx for ctx in provider.calls if ctx.player_id == 'v1')
    legal = {(spec.action, spec.amount) for spec in first_node.legal_actions}
    assert ('check', 0.0) in legal
    assert ('bet', 5.0) in legal
    assert result.status == 'incomplete'  # later streets aren't modelled


def test_flop_closes_and_advances_to_turn_before_abstaining_on_response_model():
    data = _input(
        n=2, street='flop',
        stacks={'hero': 50.0, 'v1': 50.0, 'v2': 50.0}, pending=(),
        response_sizes={'v1': {'bet': (5.0,)},
                        'v2': {'bet': (5.0,)}},
        history=(
            {'index': 0, 'player_id': 'v1', 'action': 'check',
             'street': 'flop', 'amount': 0.0, 'facing': None},
            {'index': 1, 'player_id': 'v2', 'action': 'check',
             'street': 'flop', 'amount': 0.0, 'facing': None},
        ))
    provider = LegacyResponseProvider(
        oracle=object(), postflop_model=object(), profiles={'v1': 'PEZ'})
    result = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)], provider,
        limits=MWTreeLimits(runout_samples=2, exact_equity=False,
                            timeout_seconds=5.0))
    assert result.status == 'incomplete'
    assert result.actions[0].reason.startswith('public_card_branch_incomplete:')
    assert result.actions[0].chance_evidence
    assert result.actions[0].chance_evidence[0]['from_street'] == 'flop'
    assert result.actions[0].chance_evidence[0]['to_street'] == 'turn'
    turn_nodes = [row for row in result.actions[0].response_evidence
                  if row.get('street') == 'turn']
    assert turn_nodes and turn_nodes[0]['evidence']['heuristic_fallback_used'] is False
    assert any(
        update['event_kind'] == 'simulated_board'
        for updates in turn_nodes[0]['range_update_provenance'].values()
        for update in updates)


def test_flop_bet_and_two_calls_preserve_ranges_into_turn_node():
    data = _input(
        n=2, street='flop',
        stacks={'hero': 50.0, 'v1': 6.0, 'v2': 6.0},
        response_sizes={'v1': {'bet': (5.0,)},
                        'v2': {'bet': (5.0,)}},
        history=())
    synthetic = _ConditionalSyntheticProvider({
        'v1': {'fold': 1, 'call': 8, 'all_in': 1},
        'v2': {'fold': 1, 'call': 8, 'all_in': 1},
    })
    legacy = LegacyResponseProvider(
        oracle=object(), postflop_model=object(), profiles={'v1': 'PEZ'})

    class FlopOnlyEvidence:
        def assess(self, context):
            return (synthetic.assess(context) if context.street == 'flop'
                    else legacy.assess(context))

    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], FlopOnlyEvidence(),
        limits=MWTreeLimits(runout_samples=2, equity_samples=100,
                            exact_equity=False, max_nodes=500,
                            timeout_seconds=5.0))
    assert result.status == 'incomplete'
    assert any(trace['to_street'] == 'turn'
               for trace in result.actions[0].chance_evidence)
    turn = [row for row in result.actions[0].response_evidence
            if row.get('street') == 'turn']
    assert turn
    assert any(('flop', 'v1', 'call', 5.0, 'bet') in row['history']
               and ('flop', 'v2', 'call', 5.0, 'bet') in row['history']
               for row in turn)


def test_turn_closes_and_advances_to_river_with_reproducible_seed():
    history = (
        {'index': 0, 'player_id': 'v1', 'action': 'check',
         'street': 'turn', 'amount': 0.0, 'facing': None},
        {'index': 1, 'player_id': 'v2', 'action': 'check',
         'street': 'turn', 'amount': 0.0, 'facing': None},
    )
    data = _input(
        n=2, street='turn', stacks={'hero': 50.0, 'v1': 50.0, 'v2': 50.0},
        response_sizes={'v1': {'bet': (5.0,)},
                        'v2': {'bet': (5.0,)}},
        pending=(), history=history)
    provider = LegacyResponseProvider(
        oracle=object(), postflop_model=object(), profiles={'v1': 'PEZ'})
    first = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)], provider,
        limits=MWTreeLimits(runout_samples=3, exact_equity=False,
                            timeout_seconds=5.0, seed=91))
    second = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)], provider,
        limits=MWTreeLimits(runout_samples=3, exact_equity=False,
                            timeout_seconds=5.0, seed=91))
    assert first.status == 'incomplete'
    assert first.actions[0].chance_evidence[0]['to_street'] == 'river'
    assert first.actions[0].chance_evidence[0]['samples'] == \
        second.actions[0].chance_evidence[0]['samples']


def test_turn_raise_and_fold_reaches_river_runout():
    data = _input(
        n=2, street='turn',
        stacks={'hero': 20.0, 'v1': 20.0, 'v2': 5.0},
        response_sizes={'v1': {'bet': (5.0,), 'raise': (10.0,)}},
        hero_future_sizes={'bet': (5.0,), 'raise': (15.0,)})
    provider = _ConditionalSyntheticProvider({
        'v1': {'fold': 1, 'call': 1, 'raise': 8, 'all_in': 1},
        'v2': {'fold': 8, 'all_in': 2},
    })
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider,
        limits=MWTreeLimits(exact_equity=False, equity_samples=100,
                            max_nodes=5_000,
                            max_depth=30, timeout_seconds=10.0,
                            runout_samples=2))
    assert result.actions[0].status in ('provisional', 'incomplete')
    assert any(row.get('to_street') == 'river'
               for row in result.actions[0].chance_evidence)
    assert any(context.street == 'river' for context in provider.calls)
    assert any(context.player_id == 'v2'
               and ('turn', 'v1', 'raise', 10.0, 'bet') in context.history
               for context in provider.calls)


def test_exact_showdown_tie_on_shared_board_returns_one_third_pot():
    royal = ('Ah', 'Kh', 'Qh', 'Jh', 'Th')
    data = _input(n=2, street='river', board=royal, pending=())
    result = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)], _ConditionalSyntheticProvider(),
        limits=MWTreeLimits(exact_equity=True, timeout_seconds=5.0))
    action = result.actions[0]
    assert action.ev == pytest.approx(20.0)
    assert action.terminal_nodes == 1
    assert action.status == 'provisional'


def test_multiway_hand_that_folds_to_one_rival_keeps_dead_blocker(monkeypatch):
    data = _input(n=2, street='river')
    provider = _ConditionalSyntheticProvider({
        'v1': {'fold': 1000, 'all_in': 1},
        'v2': {'fold': 1, 'all_in': 1000},
    })
    captured = []
    real = mw_tree.calculate_multiway_equity

    def spy(*args, **kwargs):
        captured.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(mw_tree, 'calculate_multiway_equity', spy)
    result = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], provider)
    assert result.actions[0].ev is not None
    folded = [(args, kwargs) for args, kwargs in captured
              if tuple(r.identity for r in kwargs.get('dead_ranges', ()))
              == ('v1',)]
    assert folded, 'la carta foldeada debe seguir como blocker muerto'
    args, kwargs = folded[0]
    assert tuple(r.identity for r in args[2]) == ('v2',)
    dead = kwargs['dead_ranges'][0]
    a, b = sorted((card_id('Kc'), card_id('Kd')))
    combo_index = int(np.flatnonzero((COMBO0 == a) & (COMBO1 == b))[0])
    assert dead.weights[combo_index] == pytest.approx(1.0)
    assert result.status == 'provisional'


def test_flop_to_turn_refuses_when_folded_hole_cards_are_unknown():
    state = interpret_mw_state({
        'hero_id': 'hero', 'street': 'flop', 'board': list(RIVER[:3]),
        'pot': 15.0,
        'players': [
            {'identity': 'hero', 'position': 'BTN', 'status': 'active',
             'hole_cards': list(HERO), 'stack': 45.0, 'contribution': 5.0},
            {'identity': 'v1', 'position': 'SB', 'status': 'folded',
             'stack': 45.0, 'contribution': 5.0},
            {'identity': 'v2', 'position': 'BB', 'status': 'active',
             'hole_cards': list(HANDS['v2']), 'stack': 45.0,
             'contribution': 5.0},
        ],
        'actions': [{'index': 0, 'player_id': 'v1', 'action': 'fold',
                     'street': 'preflop', 'amount': 0.0, 'facing': 'raise'}],
        'sequence_complete': True,
        'decision': {'actor_id': 'hero', 'to_call': 0.0,
                     'facing_action': None},
    })
    data = MWTreeInput(
        state=state, ranges=build_ranges_from_state(state, {}, {}),
        street_bets={p.identity: 0.0 for p in state.players},
        action_order=('v2',), pending_opponents=(), min_bet=5.0,
        min_raise=5.0, action_order_source='synthetic',
        pending_source='synthetic', response_sizes={},
        action_space_complete=True,
        action_space_scope='synthetic flop-to-turn transition')
    result = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)], _ConditionalSyntheticProvider())
    assert result.status == 'incomplete'
    assert result.actions[0].reason == \
        'folded_hole_cards_unknown_at_street_transition'


def test_flop_to_turn_refuses_a_range_that_lost_coverage():
    data = _input(
        n=2, street='flop', stacks={'hero': 50.0, 'v1': 50.0, 'v2': 50.0},
        pending=(),
        history=(
            {'index': 0, 'player_id': 'v1', 'action': 'check',
             'street': 'flop', 'amount': 0.0, 'facing': None},
            {'index': 1, 'player_id': 'v2', 'action': 'check',
             'street': 'flop', 'amount': 0.0, 'facing': None},
        ))
    # Simulate a snapshot whose valid input range later lost coverage, e.g.
    # because an external provider could not condition it. The street
    # transition must abstain instead of silently reusing the prior.
    a, b = sorted((card_id('Kc'), card_id('Kd')))
    combo_index = int(np.flatnonzero((COMBO0 == a) & (COMBO1 == b))[0])
    posterior = np.zeros(N_COMBOS)
    posterior[combo_index] = 1.0
    data.ranges['v1'] = OpponentRangeState(
        identity='v1', position='SB', posterior=posterior,
        source='synthetic stale range', source_kind='synthetic',
        coverage='coverage_gap', complete=False)
    result = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)], _ConditionalSyntheticProvider(),
        limits=MWTreeLimits(runout_samples=2, exact_equity=False,
                            timeout_seconds=5.0))
    assert result.status == 'incomplete'
    assert result.actions[0].reason == 'range_incomplete_at_street_transition'


def test_allin_response_likelihood_survives_to_showdown(monkeypatch):
    data = _input(
        n=2, street='river',
        stacks={'hero': 5.0, 'v1': 5.0, 'v2': 5.0})
    a, b = sorted((card_id('Kc'), card_id('Kd')))
    target = int(np.flatnonzero((COMBO0 == a) & (COMBO1 == b))[0])
    # A synthetic prior (not revealed cards) so the response can condition it.
    data.ranges['v1'] = OpponentRangeState(
        identity='v1', position='SB', posterior=np.ones(N_COMBOS),
        source='synthetic uniform prior', source_kind='synthetic',
        coverage='exact', complete=True)
    likelihood = np.zeros(N_COMBOS)
    likelihood[target] = 1.0

    class AllInLikelihoodProvider(_ConditionalSyntheticProvider):
        def assess(self, context):
            assessment = super().assess(context)
            if context.player_id != 'v1':
                return assessment
            outcomes = tuple(
                replace(outcome, range_likelihood=likelihood,
                        range_source='synthetic_allin_likelihood',
                        range_coverage='exact')
                for outcome in assessment.distribution.outcomes)
            return ResponseAssessment(
                'available',
                replace(assessment.distribution, outcomes=outcomes),
                None, {'synthetic_fixture': True})

    captured = []
    real = mw_tree.calculate_multiway_equity

    def spy(hero_hand, board, opponents, **kwargs):
        captured.append(tuple(opponents))
        return real(hero_hand, board, opponents, **kwargs)

    monkeypatch.setattr(mw_tree, 'calculate_multiway_equity', spy)
    provider = AllInLikelihoodProvider({
        'v1': {'check': 1, 'all_in': 1000},
        'v2': {'check': 1, 'all_in': 1000},
    })
    result = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)], provider,
        limits=MWTreeLimits(max_nodes=500, timeout_seconds=5.0))
    assert result.actions[0].ev is not None
    v1_ranges = [r for call in captured for r in call if r.identity == 'v1']
    assert v1_ranges
    assert any(np.argmax(r.weights) == target
               and r.weights[target] == pytest.approx(1.0)
               for r in v1_ranges)


def test_hero_actions_share_no_mutable_tree_state():
    data = _input(n=2, street='river')
    weights = {
        'v1': {'fold': 1, 'call': 1, 'all_in': 8},
        'v2': {'fold': 1, 'call': 1, 'all_in': 8},
    }
    before = {identity: value.posterior.copy()
              for identity, value in data.ranges.items()}
    multi = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0), ActionSpec('check', 0.0)],
        _ConditionalSyntheticProvider(weights))
    bet_alone = evaluate_mw_action_tree(
        data, [ActionSpec('bet', 5.0)], _ConditionalSyntheticProvider(weights))
    check_alone = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)],
        _ConditionalSyntheticProvider(weights))
    assert multi.actions[0].ev == pytest.approx(bet_alone.actions[0].ev)
    assert multi.actions[1].ev == pytest.approx(check_alone.actions[0].ev)
    assert multi.actions[0].status == bet_alone.actions[0].status
    assert multi.actions[1].status == check_alone.actions[0].status
    for identity, original in before.items():
        np.testing.assert_array_equal(
            data.ranges[identity].posterior, original)


def test_sidepots_built_from_multiple_streets_feed_each_layer(monkeypatch):
    raw = _raw_state(
        stacks={'hero': 10.0, 'v1': 0.0, 'v2': 0.0},
        contributions={'hero': 40.0, 'v1': 40.0, 'v2': 25.0},
        statuses={'hero': 'active', 'v1': 'all_in', 'v2': 'all_in'})
    raw['actions'] = [
        {'index': 0, 'player_id': 'hero', 'action': 'bet',
         'street': 'preflop', 'amount': 5.0, 'facing': None},
        {'index': 1, 'player_id': 'v1', 'action': 'raise',
         'street': 'preflop', 'amount': 15.0, 'facing': 'bet'},
        {'index': 2, 'player_id': 'v2', 'action': 'call',
         'street': 'preflop', 'amount': 15.0, 'facing': 'raise'},
        {'index': 3, 'player_id': 'hero', 'action': 'call',
         'street': 'preflop', 'amount': 10.0, 'facing': 'raise'},
        {'index': 4, 'player_id': 'hero', 'action': 'bet',
         'street': 'flop', 'amount': 10.0, 'facing': None},
        {'index': 5, 'player_id': 'v1', 'action': 'call',
         'street': 'flop', 'amount': 10.0, 'facing': 'bet'},
        {'index': 6, 'player_id': 'v2', 'action': 'all_in',
         'street': 'flop', 'amount': 10.0, 'facing': 'bet'},
        {'index': 7, 'player_id': 'hero', 'action': 'bet',
         'street': 'turn', 'amount': 15.0, 'facing': None},
        {'index': 8, 'player_id': 'v1', 'action': 'all_in',
         'street': 'turn', 'amount': 15.0, 'facing': 'bet'},
        {'index': 9, 'player_id': 'hero', 'action': 'call',
         'street': 'turn', 'amount': 15.0, 'facing': 'all_in'},
    ]
    raw['decision'] = {'actor_id': 'hero', 'to_call': 0.0,
                       'facing_action': None}
    state = interpret_mw_state(raw)
    data = MWTreeInput(
        state=state, ranges=build_ranges_from_state(state, {}, {}),
        street_bets={p.identity: 0.0 for p in state.players},
        action_order=(), pending_opponents=(), min_bet=5.0, min_raise=5.0,
        action_order_source='synthetic', pending_source='synthetic',
        response_sizes={}, action_space_complete=True,
        action_space_scope='synthetic forced showdown across streets')
    equities = {('v1', 'v2'): 0.5, ('v1',): 0.7}
    seen = []

    def fake(hero_hand, board, opponents, **kwargs):
        key = tuple(sorted(r.identity for r in opponents))
        seen.append(key)
        return SimpleNamespace(
            equity=equities[key], exact=True, standard_error=0.0,
            limitations=(), model='synthetic_exact_enumeration',
            opponents=key)

    monkeypatch.setattr(mw_tree, 'calculate_multiway_equity', fake)
    result = evaluate_mw_action_tree(
        data, [ActionSpec('check', 0.0)], _ConditionalSyntheticProvider())
    assert result.actions[0].ev == pytest.approx(75.0 * 0.5 + 30.0 * 0.7)
    assert set(seen) == {('v1', 'v2'), ('v1',)}
    assert result.actions[0].status == 'provisional'
