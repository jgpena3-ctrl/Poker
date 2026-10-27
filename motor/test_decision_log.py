import hashlib
import json
from types import SimpleNamespace

from motor.asistente_live import Asistente
from motor.decision_log import DecisionLog
from recorder.recorder_live import LiveRecorder


def _events(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def test_decision_append_and_later_resolution_are_separate(tmp_path):
    path = tmp_path / 'decisions.jsonl'
    log = DecisionLog(path)
    decision_id = log.record_decision(
        {'street': 'flop', 'equity': None, 'villain_range': None,
         'recommended_action': 'call'},
        hand_id='H_REPLAY', street='flop', hero_position='BTN',
        actions_seen_count=1)

    decision = _events(path)[0]
    assert decision['event_type'] == 'decision'
    assert decision['decision_id'] == decision_id
    assert decision['hand_id'] == 'H_REPLAY'
    assert decision['known_at_decision']['equity'] is None
    assert decision['execution'] == {'status': 'pending', 'action': None}
    assert decision['outcome'] == {'status': 'pending'}

    count = log.resolve_hand({
        'hand_id': 'H_REPLAY', 'final_pot': 18.0,
        'winner': ['hero'], 'showdown': {'winner1': 'BTN (Hero)'},
        'players': [{'pos': 'BTN', 'cards': 'AsKd'},
                    {'pos': 'UTG', 'cards': 'QhQs'}],
        'streets': {'flop': {'actions': [
            {'pos': 'UTG', 'action': 'b', 'amount': 4.0},
            {'pos': 'BTN', 'action': 'c', 'amount': 4.0,
             'amount_type': 'observed'},
        ]}},
    })
    events = _events(path)
    assert count == 1
    assert len(events) == 2
    assert events[0]['known_at_decision']['equity'] is None
    assert 'revealed_cards' not in events[0]['known_at_decision']
    assert events[1]['event_type'] == 'resolution'
    assert events[1]['decision_id'] == decision_id
    assert events[1]['execution']['action']['action'] == 'c'
    assert events[1]['outcome']['winner_ids'] == ['hero']
    assert events[1]['outcome']['revealed_cards']['UTG'] == 'QhQs'


def test_unresolved_decision_survives_reopening_log_and_keeps_unknowns(tmp_path):
    path = tmp_path / 'decisions.jsonl'
    snapshot = {
        'street': 'turn',
        'hero_position': 'BTN',
        'equity': None,
        'villain_range': None,
        'recommended_action': 'call',
        'actions_before_decision': [
            {'street': 'turn', 'pos': 'UTG', 'action': 'b', 'amount': 5.0},
        ],
    }
    first_session = DecisionLog(path)
    decision_id = first_session.record_decision(
        snapshot, hand_id='H_RESTART', street='turn',
        hero_position='BTN', actions_seen_count=1)
    del first_session  # the append was flushed before the session ended

    resumed_session = DecisionLog(path)
    assert resumed_session.resolve_hand({
        'hand_id': 'H_RESTART', 'final_pot': 20.0, 'winner': ['UTG'],
        'showdown': {'winner1': 'UTG (Villain)'},
        'players': [{'pos': 'UTG', 'cards': 'AhAd'}],
        'streets': {'turn': {'actions': [
            {'pos': 'UTG', 'action': 'b', 'amount': 5.0},
            {'pos': 'BTN', 'action': 'f', 'amount': 0.0},
        ]}},
    }) == 1

    events = _events(path)
    assert len(events) == 2
    assert events[0]['decision_id'] == decision_id
    assert events[0]['known_at_decision'] == snapshot
    assert events[0]['known_at_decision']['equity'] is None
    assert events[0]['known_at_decision']['villain_range'] is None
    assert events[1]['decision_id'] == decision_id
    assert events[1]['execution']['action']['action'] == 'f'
    assert events[1]['outcome']['revealed_cards']['UTG'] == 'AhAd'


def test_successive_same_street_decisions_have_distinct_ids_and_actions(tmp_path):
    path = tmp_path / 'decisions.jsonl'
    log = DecisionLog(path)
    first = log.record_decision(
        {'street': 'preflop', 'recommended_action': 'igualar',
         'actions_before_decision': [
             {'street': 'preflop', 'pos': 'UTG', 'action': 'r',
              'amount': 3.0}]},
        hand_id='H_MULTI', street='preflop', hero_position='BTN',
        actions_seen_count=1)
    second = log.record_decision(
        {'street': 'preflop', 'recommended_action': 'subir',
         'actions_before_decision': [
             {'street': 'preflop', 'pos': 'UTG', 'action': 'r',
              'amount': 3.0},
             {'street': 'preflop', 'pos': 'BTN', 'action': 'c',
              'amount': 3.0},
             {'street': 'preflop', 'pos': 'UTG', 'action': 'r',
              'amount': 6.0}]},
        hand_id='H_MULTI', street='preflop', hero_position='BTN',
        actions_seen_count=3)
    assert first != second

    log.resolve_hand({
        'hand_id': 'H_MULTI', 'final_pot': 0, 'winner': [], 'players': [],
        'streets': {'preflop': {'actions': [
            {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
            {'pos': 'BTN', 'action': 'c', 'amount': 3.0},
            {'pos': 'UTG', 'action': 'r', 'amount': 6.0},
            {'pos': 'BTN', 'action': 'r', 'amount': 18.0},
        ]}},
    })
    resolutions = [e for e in _events(path) if e['event_type'] == 'resolution']
    assert [e['decision_id'] for e in resolutions] == [first, second]
    assert [e['execution']['action']['action'] for e in resolutions] == ['c', 'r']


def test_recommendation_step_writes_sidecar_and_deduplicates_repeated_frame(
        tmp_path, monkeypatch):
    import recorder_live

    monkeypatch.setattr(recorder_live, 'PLAYER_NAMES', {
        'hero': 'Jarduan', 'p1': 'Villain', 'p2': 'P2', 'p3': 'P3',
        'p4': 'P4', 'p5': 'P5',
    })
    path = tmp_path / 'decisions.jsonl'
    rec = LiveRecorder()
    rec.output_path = str(tmp_path / 'replayed-hands.jsonl')
    rec.hand_id = 40
    log = DecisionLog(path)
    assistant = Asistente.__new__(Asistente)
    assistant.models = SimpleNamespace(oracle=None)
    assistant.oracle = None
    assistant.rec = rec
    assistant.decision_log = log
    assistant.hero_name = 'Jarduan'
    assistant.verbose = False
    assistant.runout = False
    assistant.live_stacks = {}
    assistant._last_seen_stake = {}
    assistant.last_reco_key = None
    assistant.last_state = None
    assistant.last_img = None

    state = {'pot': 4.0, 'btn': 'hero', 'hero_cards': [
        {'rank': 'A', 'suit': 's'}, {'rank': 'K', 'suit': 's'}],
        'community': []}
    for pid in ('hero', 'p1', 'p2', 'p3', 'p4', 'p5'):
        state[f'{pid}_state'] = 'sin jugador'
        state[f'{pid}_stake'] = 100.0
        state[f'{pid}_bet'] = 0.0
    state.update(hero_state='activo', p1_state='activo', hero_bet=0.0,
                 p1_bet=2.5)

    first = assistant.step(state, None, None, log=lambda _msg: None,
                           require_turn=False)
    again = assistant.step(state, None, None, log=lambda _msg: None,
                           require_turn=False)
    assert first is not None
    assert again is None
    events = _events(path)
    assert len(events) == 1
    event = events[0]
    assert event['event_type'] == 'decision'
    assert event['hand_id'] == 'H_0041'
    assert rec.hand['hand_id'] == event['hand_id']
    assert event['known_at_decision']['street'] == 'preflop'
    assert event['known_at_decision']['cards_known']['hero'] == ['As', 'Ks']
    actions = event['known_at_decision']['actions_before_decision']
    assert actions[0]['action'] == 'p'
    assert next(a['action'] for a in actions if a['action'] != 'p') == 'r'
    assert event['known_at_decision']['recommended_action'] == first.chosen
    assert event['known_at_decision']['equity'] is None
    assert event['known_at_decision']['villain_range'] is None
    assert event['known_at_decision']['cards_known']['unknown_opponent_holes']

    # Replay the player's observed call and finalize the hand through the real
    # recorder hook. The decision-time row remains unchanged.
    rec.hand['streets']['preflop']['actions'].append({
        'pos': 'BTN', 'action': 'c', 'amount': 2.5,
        'amount_type': 'observed',
    })
    rec.on_hand_finalized = log.resolve_hand
    rec.finalize_hand({**state, 'pot': 7.0, 'p1_state': 'retirarse'})
    final_events = _events(path)
    assert len(final_events) == 2
    assert final_events[0]['known_at_decision']['recommended_action'] == first.chosen
    assert final_events[1]['execution']['action']['action'] == 'c'
    assert (final_events[0]['known_at_decision']['recommended_action']
            != final_events[1]['execution']['action']['action'])
    assert final_events[1]['outcome']['final_pot'] == 7.0
    assert (tmp_path / 'replayed-hands.jsonl').exists()


def test_postflop_replay_persists_available_range_equity_candidates_and_evs(
        tmp_path, monkeypatch):
    import numpy as np
    import recorder_live

    monkeypatch.setattr(recorder_live, 'PLAYER_NAMES', {
        'hero': 'Jarduan', 'p1': 'Villain', 'p2': 'P2', 'p3': 'P3',
        'p4': 'P4', 'p5': 'P5',
    })
    monkeypatch.setenv('POKER_MOTOR_VERSION', 'replay-test')

    class RangeModel:
        def prob_vec(self, *args, **kwargs):
            return np.ones(1326, dtype=np.float32)

    class Oracle:
        def p_action(self, *args, **kwargs):
            return None

    class PostflopModel:
        def prob_vec(self, *args, **kwargs):
            return np.ones(1326, dtype=np.float32)

    rec = LiveRecorder()
    rec.hand = {
        'hand_id': 'H_POSTFLOP_REPLAY', 'current_street': 'flop',
        'players': [
            {'_id': 'hero', 'pos': 'BTN', 'cards': 'AsKd'},
            {'_id': 'p1', 'pos': 'UTG', 'cards': ''},
        ],
        'streets': {
            'preflop': {'actions': [
                {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
                {'pos': 'BTN', 'action': 'c', 'amount': 3.0},
            ]},
            'flop': {'board': ['Qh', '7s', '2c'], 'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': 4.0},
            ]},
            'turn': {'board': [], 'actions': []},
            'river': {'board': [], 'actions': []},
        },
    }
    rec._hand_positions = {'hero': 'BTN', 'p1': 'UTG', 'p2': 'BB',
                           'p3': 'CO', 'p4': 'MP', 'p5': 'SB'}
    rec.process_frame = lambda state, img, log=print: None

    assistant = Asistente.__new__(Asistente)
    assistant.models = SimpleNamespace(
        range_model=RangeModel(), postflop_model=PostflopModel())
    assistant.oracle = Oracle()
    assistant.rec = rec
    assistant.decision_log = DecisionLog(tmp_path / 'postflop.jsonl')
    assistant.hero_name = 'Jarduan'
    assistant.verbose = False
    assistant.runout = False
    assistant.shadow = False
    assistant.live_stacks = {}
    assistant._last_seen_stake = {}
    assistant.last_reco_key = None
    assistant.last_state = None
    assistant.last_img = None

    def cards(values):
        return [{'rank': c[:-1], 'suit': c[-1]} for c in values]

    state = {'pot': 12.5, 'hero_cards': cards(['As', 'Kd']),
             'community': cards(['Qh', '7s', '2c'])}
    for pid in ('hero', 'p1', 'p2', 'p3', 'p4', 'p5'):
        state[f'{pid}_state'] = 'inactivo'
        state[f'{pid}_stake'] = 90.0
        state[f'{pid}_bet'] = 0.0
    state.update(hero_state='activo', p1_state='activo', p1_bet=4.0)

    result = assistant.step(state, None, None, require_turn=False)
    assert result is not None
    event = _events(tmp_path / 'postflop.jsonl')[0]
    assert event['motor_version'] == 'replay-test'
    known = event['known_at_decision']
    assert known['street'] == 'flop'
    assert known['equity'] is not None
    assert known['villain_range']['combo_weights']
    assert known['candidate_actions']
    assert known['ev_by_action']
    assert known['action_values_kind'] == 'ev'
    assert known['recommended_action'] == result.chosen

    # Later in the same hand/street, a call followed by a raise creates a
    # distinct decision; subsequent identical frames remain deduplicated.
    rec.hand['streets']['flop']['actions'].extend([
        {'pos': 'BTN', 'action': 'c', 'amount': 4.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
    ])
    state.update(pot=17.5, hero_bet=4.0, p1_bet=5.0)
    second = assistant.step(state, None, None, require_turn=False)
    repeated = assistant.step(state, None, None, require_turn=False)
    assert second is not None
    assert repeated is None
    events = _events(tmp_path / 'postflop.jsonl')
    assert len(events) == 2
    assert events[0]['decision_id'] != events[1]['decision_id']
    assert events[1]['hand_id'] == 'H_POSTFLOP_REPLAY'
    assert events[1]['known_at_decision']['street'] == 'flop'


def test_decision_sidecar_never_changes_historical_hands_file(tmp_path):
    from pathlib import Path

    hands_path = Path(__file__).resolve().parents[1] / 'data' / 'hands_db.jsonl'
    before = hashlib.sha256(hands_path.read_bytes()).hexdigest()
    log = DecisionLog(tmp_path / 'separate.jsonl')
    log.record_decision({'recommended_action': 'fold'}, hand_id='H_ISOLATED')
    after = hashlib.sha256(hands_path.read_bytes()).hexdigest()
    assert after == before


def test_live_assistant_enables_sidecar_and_recorder_completion_hook(
        tmp_path, monkeypatch):
    import motor.asistente_live as live
    import recorder_live

    destination = tmp_path / 'configured.jsonl'
    monkeypatch.setenv('POKER_DECISIONS_PATH', str(destination))
    monkeypatch.setattr(recorder_live, 'PLAYER_NAMES', {
        'hero': 'Hero', 'p1': 'Player1', 'p2': 'Player2',
        'p3': 'Player3', 'p4': 'Player4', 'p5': 'Player5',
    })
    monkeypatch.setattr(live, 'get_readers', lambda: (object(), None))
    assistant = live.Asistente(models=SimpleNamespace(oracle=None),
                               verbose=False)
    assert assistant.decision_log.path == str(destination)
    assert assistant.rec.on_hand_finalized == assistant.decision_log.resolve_hand


def test_live_recorder_finalizes_sidecar_without_sharing_hands_file(tmp_path):
    decision_path = tmp_path / 'decisions.jsonl'
    hands_path = tmp_path / 'recorded-hands.jsonl'
    log = DecisionLog(decision_path)
    rec = LiveRecorder()
    rec.output_path = str(hands_path)
    rec.hand_id = 9876
    rec.hand = {
        'hand_id': 'H_FINALIZE_HOOK', 'current_street': 'flop',
        'max_pot': 8.0,
        'players': [
            {'_id': 'hero', 'pos': 'BTN', 'name': 'Hero', 'active': True,
             'cards': 'AsKd'},
            {'_id': 'p1', 'pos': 'UTG', 'name': 'Villain', 'active': True,
             'cards': ''},
        ],
        'streets': {
            'preflop': {'actions': [], 'board': []},
            'flop': {'board': ['Qh', '7s', '2c'], 'actions': [
                {'pos': 'UTG', 'action': 'b', 'amount': 4.0},
                {'pos': 'BTN', 'action': 'c', 'amount': 4.0},
            ]},
            'turn': {'actions': [], 'board': []},
            'river': {'actions': [], 'board': []},
        },
    }
    rec._hand_positions = {'hero': 'BTN', 'p1': 'UTG'}
    rec.on_hand_finalized = log.resolve_hand
    decision_id = log.record_decision(
        {'street': 'flop', 'hero_position': 'BTN',
         'actions_before_decision': [
             {'street': 'flop', 'pos': 'UTG', 'action': 'b',
              'amount': 4.0}]},
        hand_id='H_FINALIZE_HOOK', street='flop', hero_position='BTN',
        actions_seen_count=1)

    rec.finalize_hand({'pot': 8.0, 'hero_state': 'activo',
                       'p1_state': 'retirarse'})

    assert hands_path.exists()
    hand_row = json.loads(hands_path.read_text(encoding='utf-8').splitlines()[0])
    assert hand_row['hand_id'] == 'H_FINALIZE_HOOK'
    events = _events(decision_path)
    assert events[1]['event_type'] == 'resolution'
    assert events[1]['decision_id'] == decision_id
    assert events[1]['execution']['action']['action'] == 'c'
    assert events[1]['outcome']['winner_ids'] == ['hero']
