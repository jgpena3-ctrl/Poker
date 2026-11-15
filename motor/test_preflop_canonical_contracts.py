"""Pruebas del contrato preflop puro (PR-01)."""
import pytest

from motor.preflop_contract import (
    PreflopAction, PreflopContext, PreflopDecision, RangeQuery,
    normalize_actions, preflop_decision,
)


def test_preflop_action_validates_exactness():
    with pytest.raises(ValueError):
        PreflopAction(index=0, pos='UTG', action='b', amount=2.5,
                     is_blind=False, amount_exactness='exactish')


def test_preflop_action_validates_event_type():
    with pytest.raises(ValueError):
        PreflopAction(index=0, pos='UTG', action='b', amount=2.5,
                     is_blind=False, event_type='raise')


def test_preflop_decision_no_decision_has_no_plan_or_range():
    d = PreflopDecision(status='no_decision')
    assert d.decision_plan is None
    assert d.range_query is None
    assert d.resolved is False


def test_preflop_decision_rejects_no_decision_with_plan():
    with pytest.raises(ValueError):
        PreflopDecision(status='no_decision', decision_plan=object())


def test_preflop_decision_rejects_unresolved_with_plan_or_range():
    with pytest.raises(ValueError):
        PreflopDecision(status='unresolved', decision_plan=object())
    with pytest.raises(ValueError):
        PreflopDecision(status='unresolved',
                       range_query=RangeQuery(query_id='q',
                                            player_position='UTG',
                                            decision_category='OPEN',
                                            table_key='k',
                                            status='available'))

def test_range_query_validates_status():
    with pytest.raises(ValueError):
        RangeQuery(query_id='q', player_position='UTG',
                   decision_category='OPEN', table_key='OR_UTG',
                   status='maybe')


def test_normalize_actions_preserves_unknown_amount_source():
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
    ]}}}
    out = normalize_actions(hand)
    assert len(out) == 1
    a = out[0]
    assert a.amount == 2.5
    assert a.amount_source is None
    assert a.amount_exactness == 'unknown'
    assert a.pot_contribution_delta is None
    assert a.event_type == 'voluntary_action'


def test_normalize_actions_marks_nonblind_p_as_unknown_post():
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'CO', 'action': 'p', 'amount': 3.0},
    ]}}}
    out = normalize_actions(hand)
    assert out[0].event_type == 'unknown_post'


def test_normalize_actions_recognizes_bb_blind_structurally():
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
    ]}}}
    out = normalize_actions(hand)
    assert out[0].event_type == 'big_blind'


def test_preflop_decision_no_decision_for_hand_without_hero_action():
    hand = {'players': [{'pos': 'UTG'}],
            'streets': {'preflop': {'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
            ]}}}
    d = preflop_decision(hand, 'BB')
    assert d.status == 'no_decision'
    assert d.decision_plan is None
    assert d.range_query is None


def test_preflop_decision_resolved_for_open():
    hand = {'players': [{'pos': 'UTG'}],
            'streets': {'preflop': {'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
            ]}}}
    d = preflop_decision(hand, 'UTG')
    assert d.status == 'resolved'
    assert d.hero_action_index == 0
    assert len(d.prior_actions) == 0
    assert d.sequence_status == 'not_evaluated'


def test_preflop_context_state_valid():
    ctx = PreflopContext.initial()
    assert ctx.state_valid is True
    tainted = __import__('dataclasses').replace(ctx, tainted_reason='x')
    assert tainted.state_valid is False


def test_preflop_decision_unresolved_when_amount_missing():
    hand = {'players': [{'pos': 'UTG'}],
            'streets': {'preflop': {'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': None},
            ]}}}
    d = preflop_decision(hand, 'UTG')
    assert d.status == 'unresolved'
    assert d.decision_plan is None
    assert d.range_query is None


def test_preflop_decision_invalid_state_combinations():
    with pytest.raises(ValueError):
        PreflopDecision(status='resolved', sequence_status='maybe')
    with pytest.raises(ValueError):
        RangeQuery(query_id='q', player_position='UTG',
                   decision_category='OPEN', table_key='k',
                   status='available', approximation_used='yes')


def test_amount_source_does_not_imply_exactness():
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5,
         'amount_type': 'observed'},
    ]}}}
    a = normalize_actions(hand)[0]
    assert a.amount_source == 'observed'
    assert a.amount_exactness == 'unknown'


def test_pot_contribution_delta_none_without_semantics():
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
    ]}}}
    a = normalize_actions(hand)[0]
    assert a.pot_contribution_delta is None


def test_pot_contribution_delta_with_cumulative_semantics():
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5,
         'amount_semantics': 'absoluta'},
    ]}}}
    a = normalize_actions(hand)[0]
    assert a.pot_contribution_delta == 2.5


def test_blind_recognition_structural_no_ante_or_straddle():
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
    ]}}}
    out = normalize_actions(hand)
    assert out[0].event_type == 'small_blind'
    assert out[1].event_type == 'big_blind'


def test_unknown_post_for_nonblind_p():
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'CO', 'action': 'p', 'amount': 3.0},
    ]}}}
    out = normalize_actions(hand)
    assert out[0].event_type == 'unknown_post'


def test_prior_actions_prefix():
    hand = {'players': [{'pos': 'UTG'}, {'pos': 'MP'}],
            'streets': {'preflop': {'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
                {'pos': 'MP', 'action': 'c', 'amount': 2.5},
            ]}}}
    d = preflop_decision(hand, 'MP')
    assert d.status == 'resolved'
    assert len(d.prior_actions) == 1
    assert d.prior_actions[0].pos == 'UTG'


def test_all_six_action_codes_normalize():
    codes = ['f', 'x', 'c', 'p', 'b', 'r']
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'UTG', 'action': c, 'amount': 1.0} for c in codes
    ]}}}
    out = normalize_actions(hand)
    assert [a.action for a in out] == codes


def test_player_id_no_collision_with_missing_pos():
    hand = {'players': [{'pos': 'UTG'}, {'pos': ''}],
            'streets': {'preflop': {'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
            ]}}}
    out = normalize_actions(hand)
    assert out[0].player_id == 'hero'


def test_original_metadata_preserved():
    hand = {'streets': {'preflop': {'actions': [
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5,
         'amount_semantics': 'absoluta', 'inferred': True},
    ]}}}
    a = normalize_actions(hand)[0]
    assert a.metadata.get('inferred') is True
    assert a.metadata.get('amount_semantics') == 'absoluta'
    assert a.amount == 2.5


def test_sequence_status_not_evaluated_without_legal_validation():
    hand = {'players': [{'pos': 'UTG'}],
            'streets': {'preflop': {'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
            ]}}}
    d = preflop_decision(hand, 'UTG')
    assert d.sequence_status == 'not_evaluated'
