"""Flujo integral con fixtures: decisión → resolución → evaluador.

Los datos son sintéticos y viven en `tmp_path`; no tocan `data/decisions.jsonl`
ni `data/hands_db.jsonl`.
"""
import json

from motor.decision_log import DecisionLog
from tools.evaluar_decisiones import evaluate_file


def _positions():
    return {'hero': 'BTN', 'p1': 'UTG', 'p2': 'SB', 'p3': 'BB',
            'p4': 'CO', 'p5': 'MP'}


def _preflop_snapshot():
    actions = [
        {'street': 'preflop', 'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'street': 'preflop', 'pos': 'BB', 'action': 'b', 'amount': 1.0},
    ]
    return {
        'street': 'preflop',
        'hero_id': 'hero',
        'villain_id': 'p1',
        'hero_position': 'BTN',
        'villain_position': 'UTG',
        'positions': _positions(),
        'stacks': {'hero': 100.0, 'p1': 100.0},
        'bets': {'hero': 0.0, 'p1': 1.0},
        'pot': 1.5,
        'to_call': 1.0,
        'effective_stack': 100.0,
        'cards_known': {'hero': ['As', 'Kd'], 'board': [],
                        'other_hole_cards': {},
                        'unknown_opponent_holes': ['p1'],
                        'opponent_hole_cards_complete': False},
        'actions_before_decision': actions,
        'actions_seen_count': len(actions),
        'villain_range': None,
        'villain_range_status': 'not_exposed_preflop',
        'equity': None,
        'pot_odds': 0.4,
        'spr': 40.0,
        'candidate_actions': ['retirar', 'subir'],
        'ev_by_action': None,
        'preflop_action_frequencies': {'retirar': 0.4, 'subir': 0.6},
        'action_values_kind': 'frequency',
        'recommended_action': 'subir',
        'villain_label': 'TIBURON Villain',
        'n_players': 3,
        'multiway': True,
        'multiway_soportado': False,
        'multiway_policy': 'F7.2.b/hu-contra-un-rival',
        'preflop_table_audit': [
            {'key': 'OR_BTN', 'action': 'OR', 'position': 'BTN', 'vs': '',
             'source': 'OR_BTN', 'status': 'exact'},
        ],
        'preflop_sampling': {
            'mechanism': 'weighted_choice_with_replacement',
            'rng': 'random.Random',
            'seed': 424242,
            'distribution': {'retirar': 0.4, 'subir': 0.6},
            'candidates': ['retirar', 'subir'],
        },
        'reproducibility': {
            'version': 3,
            'rules_inputs': {'street': 'preflop', 'n_players': 3},
            'ev_inputs': {'pot': 1.5, 'to_call': 1.0},
            'villain_range_inputs': None,
            'response_model_inputs': None,
            'motor_settings': {'runout': False},
            'reach_vector': None,
            'reach_combo_order': None,
            'runout': False,
        },
    }


def _flop_snapshot():
    actions = [
        {'street': 'preflop', 'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'street': 'preflop', 'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'street': 'preflop', 'pos': 'BTN', 'action': 'r', 'amount': 3.0},
        {'street': 'flop', 'pos': 'UTG', 'action': 'b', 'amount': 2.0},
    ]
    return {
        'street': 'flop',
        'hero_id': 'hero',
        'villain_id': 'p1',
        'hero_position': 'BTN',
        'villain_position': 'UTG',
        'positions': _positions(),
        'stacks': {'hero': 99.0, 'p1': 98.0},
        'bets': {'hero': 0.0, 'p1': 2.0},
        'pot': 6.5,
        'to_call': 2.0,
        'effective_stack': 98.0,
        'cards_known': {'hero': ['As', 'Kd'], 'board': ['Qh', '7s', '2c'],
                        'other_hole_cards': {},
                        'unknown_opponent_holes': ['p1'],
                        'opponent_hole_cards_complete': False},
        'actions_before_decision': actions,
        'actions_seen_count': len(actions),
        'villain_range': {
            'representation': 'combo_probability_by_hand_label',
            'normalized': True,
            'source': 'test',
            'position': 'UTG',
            'confidence': None,
            'combo_weights': [['QhQs', 1.0]],
        },
        'villain_range_status': 'available',
        'equity': 0.55,
        'pot_odds': 0.235,
        'spr': 15.0,
        'candidate_actions': ['fold', 'call'],
        'ev_by_action': {'fold': 0.0, 'call': 1.0},
        'preflop_action_frequencies': None,
        'action_values_kind': 'ev',
        'recommended_action': 'call',
        'villain_label': 'TIBURON Villain',
        'n_players': 2,
        'multiway': False,
        'multiway_soportado': True,
        'multiway_policy': 'F7.2.b/hu-contra-un-rival',
        'preflop_table_audit': None,
        'preflop_sampling': None,
        'reproducibility': {
            'version': 3,
            'rules_inputs': {'street': 'flop', 'n_players': 2},
            'ev_inputs': {'pot': 6.5, 'to_call': 2.0},
            'villain_range_inputs': {'source': 'test'},
            'response_model_inputs': {'profile': 'TIBURON'},
            'motor_settings': {'runout': True},
            'reach_vector': [1.0],
            'reach_combo_order': 'HAND_LABELS',
            'runout': True,
        },
    }


def _hand():
    return {
        'hand_id': 'H_FLOW',
        'final_pot': 12.5,
        'winner': ['hero'],
        'showdown': {'winner1': 'BTN (Hero)'},
        'players': [
            {'pos': 'BTN', 'cards': 'AsKd'},
            {'pos': 'UTG', 'cards': 'QhQs'},
        ],
        'streets': {
            'preflop': {'actions': [
                {'pos': 'SB', 'action': 'p', 'amount': 0.5},
                {'pos': 'BB', 'action': 'b', 'amount': 1.0},
                {'pos': 'BTN', 'action': 'r', 'amount': 3.0},
            ]},
            'flop': {'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': 2.0},
                {'pos': 'BTN', 'action': 'c', 'amount': 2.0},
            ]},
            'turn': {'actions': []},
            'river': {'actions': []},
        },
    }


def test_flujo_integral_preflop_postflop_resolucion_y_evaluacion(
        tmp_path, monkeypatch):
    monkeypatch.setenv('POKER_MOTOR_VERSION', 'integration-test')
    path = tmp_path / 'decisions.jsonl'
    log = DecisionLog(path)

    preflop_id = log.record_decision(
        _preflop_snapshot(), hand_id='H_FLOW', street='preflop',
        hero_position='BTN', actions_seen_count=2)
    flop_id = log.record_decision(
        _flop_snapshot(), hand_id='H_FLOW', street='flop',
        hero_position='BTN', actions_seen_count=4)
    assert log.resolve_hand(_hand()) == 2

    canceled_id = log.record_decision(
        {'street': 'preflop', 'n_players': 2, 'multiway': False,
         'recommended_action': 'fold'},
        hand_id='H_CANCEL', street='preflop', hero_position='BTN')
    assert log.discard_hand('H_CANCEL') == 1

    incomplete_id = log.record_decision(
        {'street': 'preflop', 'n_players': 2, 'multiway': False,
         'recommended_action': 'call'},
        hand_id='H_INCOMPLETE', street='preflop', hero_position='BTN')
    assert log.resolve_hand({
        'hand_id': 'H_INCOMPLETE', 'streets': {'preflop': {'actions': []}},
    }) == 1

    report = evaluate_file(path)

    assert report['integrity']['malformed_events'] == []
    assert report['integrity']['linked_decisions'] == 4
    assert report['integrity']['motor_version_missing'] == 0
    assert report['integrity']['canceled_decisions'] == 1
    assert report['scope'] == {
        'heads_up': 3, 'multiway': 1, 'unknown': 0,
        'note': report['scope']['note'],
    }
    assert report['concordance']['denominator'] == 2
    assert report['concordance']['numerator'] == 2
    assert report['concordance']['excluded_by_reason'] == {
        'decision_canceled': 1,
        'observed_action_missing': 1,
    }

    by_id = {item['decision_id']: item for item in report['decisions']}
    assert by_id[preflop_id]['concordance']['status'] == 'concordant'
    assert by_id[flop_id]['concordance']['status'] == 'concordant'
    assert by_id[canceled_id]['observed_result']['status'] == 'canceled'
    assert by_id[incomplete_id]['observed_result']['status'] == 'unavailable'
    assert by_id[preflop_id]['decision_data']['preflop_sampling']['seed'] == 424242
    assert by_id[preflop_id]['decision_data']['preflop_table_audit'][0][
        'status'] == 'exact'
    assert by_id[preflop_id]['decision_data']['motor_version'] == \
        'integration-test'

    # El fixture no tocó los datos reales.
    assert not str(path).endswith('data\\decisions.jsonl')
    assert json.loads(path.read_text(encoding='utf-8').splitlines()[0])[
        'event_type'] == 'decision'
