"""Tests de Fase 10.1: paridad HU, polling y comparacion de estado.

Todos los tests usan directorios temporales. No escriben en ``data/`` ni
inician una sesion real de captura.
"""
from __future__ import annotations

import hashlib
import builtins
import json
import os
import sys
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import motor.asistente_live as live
from motor.hu_experimental.capture import CapturedFrame, HUCaptureAdapter
from motor.hu_experimental.config import PROJECT_ROOT, ExperimentalConfig
from motor.hu_parity.automation import HUPollingController, PollEvent
from motor.hu_parity.comparison import (
    DISCREPANCY, EXACT, NOT_COMPARABLE, SEMANTIC, FieldComparison,
    StateComparison, compare_frame_state,
)
from motor.hu_parity.concurrency import CaptureSessionGuard, ConcurrencyError
from motor.hu_parity.fixtures import hu_state_fixtures
from motor.hu_parity.gui_parity import HUParityGUI, PARITY_WARNING
from motor.hu_parity.parity import LiveParityAssistant, SnapshotCollector
from motor.rules import MULTIWAY_SOPORTADO


def _state(**overrides):
    state = {
        'btn': 'hero',
        'hero_state': 'activo',
        'p1_state': 'activo',
        'p2_state': 'sin jugador',
        'p3_state': 'sin jugador',
        'p4_state': 'sin jugador',
        'p5_state': 'sin jugador',
        'hero_stake': 100.0,
        'p1_stake': 100.0,
        'hero_bet': 0.5,
        'p1_bet': 1.0,
        'pot': 1.5,
        'hero_cards': ['As', 'Kd'],
        'community': [],
        'hand_state': 'in_progress',
    }
    state.update(overrides)
    return state


def _config(tmp_path: Path, **overrides) -> ExperimentalConfig:
    kwargs = {
        'runtime_dir': tmp_path,
        'registry_name': 'registro_parity.jsonl',
        'parity_hands_path': tmp_path / 'hands_parity.jsonl',
    }
    kwargs.update(overrides)
    return ExperimentalConfig.default().with_paths(**kwargs)


@pytest.fixture(autouse=True)
def _no_live_readers(monkeypatch):
    monkeypatch.setattr(live, 'get_readers', lambda: (None, None))


def _assistant(tmp_path: Path, state=None, **config_overrides):
    state = state or _state()
    capture = HUCaptureAdapter(capture_fn=lambda: state)
    return LiveParityAssistant(
        _config(tmp_path, **config_overrides),
        capture=capture,
        models=SimpleNamespace(oracle=None),
    )


def test_parity_uses_live_engine_and_keeps_recommendation_provisional(tmp_path):
    assert MULTIWAY_SOPORTADO is False
    assistant = _assistant(tmp_path)
    analysis = assistant.analyze()

    assert analysis.has_decision
    assert analysis.prediction is not None
    assert analysis.selected_action is None
    assert analysis.provisional_selected_action in ('retirar', 'subir',
                                                    'igualar')
    assert analysis.canonical_status == 'unresolved'
    assert analysis.snapshot['preflop_table_audit'][0]['key'] == 'OR_SB'
    assert analysis.state.hero_position == 'SB'
    assert analysis.snapshot['hero_position'] == 'SB'
    assert analysis.prediction.hero_position == 'SB'
    assert analysis.prediction.metadata['position_mode'] == 'hu_sb_bb'
    assert analysis.prediction.metadata['position_correction'] == (
        'button_is_sb_and_hu_postflop_order_overridden')
    assert 'position_mode_hu_correction_not_exact_live_parity' in (
        analysis.uncertainty_reasons)
    assert 'live_engine_recommendation_not_certified' in (
        analysis.uncertainty_reasons)
    assert analysis.prediction.metadata['multiway'] is False
    assert analysis.prediction.metadata['multiway_soportado'] is False
    assert analysis.prediction.metadata['live_snapshot_multiway_soportado'] is True

    registration = assistant.register_analysis(analysis)
    assert registration.prediction_id == analysis.prediction.prediction_id
    assert assistant.verify().ok
    assert assistant.verify().event_count == 1

    duplicate = assistant.register_analysis(analysis)
    assert duplicate.prediction_id == registration.prediction_id
    assert assistant.verify().event_count == 1
    # Sin finalizacion de mano no se escribe el hand_db de paridad.
    assert not (tmp_path / 'hands_parity.jsonl').exists()


def test_parity_outcome_is_a_separate_posterior_event(tmp_path):
    assistant = _assistant(tmp_path)
    first = assistant.register_analysis(assistant.analyze())

    after = _state(hero_stake=99.5, hero_bet=1.0, p1_bet=1.0, pot=2.5)
    assistant.capture_adapter = HUCaptureAdapter(capture_fn=lambda: after)
    event = assistant.poll_once()
    assert event.error is None
    assert not assistant._pending

    events = assistant.registry.read_events()
    assert [e['event_type'] for e in events] == [
        'HU_PREDICTION', 'HU_OUTCOME']
    outcome = events[1]['payload']
    assert outcome['prediction_id'] == first.prediction_id
    assert outcome['observed_action'] == 'c'
    assert outcome['observed_at']
    assert assistant.verify().ok


def test_hu_sb_bb_mode_uses_sb_table_and_declares_no_mismatch(tmp_path):
    assistant = _assistant(tmp_path, parity_position_mode='hu_sb_bb')
    analysis = assistant.analyze()
    assert analysis.has_decision
    assert analysis.state.hero_position == 'SB'
    assert analysis.snapshot['hero_position'] == 'SB'
    assert analysis.snapshot['preflop_table_audit'][0]['key'] == 'OR_SB'
    assert 'position_mapping_live_btn_vs_hu_sb' not in (
        analysis.uncertainty_reasons)
    assert analysis.prediction.hero_position == 'SB'


def test_hu_gate_blocks_three_active_players_without_building_engine(tmp_path):
    state = _state(p2_state='activo')
    assistant = _assistant(tmp_path, state=state)
    analysis = assistant.analyze()
    assert analysis.prediction is None
    assert analysis.canonical_status == 'no_decision'
    assert analysis.canonical_reason.startswith('not_heads_up')
    assert assistant.engine is None


def test_hu_gate_blocks_less_than_two_and_ignores_live_multiway_flag(tmp_path):
    state = _state(p1_state='sin jugador', multiway_soportado=True)
    assistant = _assistant(tmp_path, state=state)
    analysis = assistant.analyze()
    assert analysis.prediction is None
    assert analysis.canonical_status == 'no_decision'
    assert assistant.engine is None


def test_comparison_reports_live_btn_vs_hu_sb_and_manual_override(tmp_path):
    state = _state()
    result = compare_frame_state(state, work_dir=tmp_path / 'default')
    codes = {d['code'] for d in result.discrepancies}
    assert 'position_mapping_btn_vs_sb' in codes
    assert result.live['positions']['hero'] == 'BTN'
    assert result.live['pot'] == pytest.approx(1.5)
    assert result.live['hero_cards'] == ('As', 'Kd')

    corrected = compare_frame_state(
        state, work_dir=tmp_path / 'corrected',
        manual_positions={'hero': 'SB', 'p1': 'BB'})
    assert not corrected.discrepancies
    assert corrected.classification == 'not_comparable_insufficient_information'
    assert corrected.live['positions']['hero'] == 'SB'


def test_poll_once_persists_prediction_and_no_duplicate(tmp_path):
    assistant = _assistant(tmp_path)
    event = assistant.poll_once()
    assert event.error is None
    assert event.analysis is not None and event.analysis.has_decision
    assert event.registration is not None
    assert event.elapsed_ms >= 0
    assert event.phase_times_ms['total'] == pytest.approx(event.elapsed_ms)
    assert assistant.verify().event_count == 1

    event2 = assistant.poll_once()
    assert event2.error is None
    # El motor live deduplica por estado: no se persiste otra prediccion.
    assert assistant.verify().event_count == 1


def test_automation_controller_reports_errors():
    class Boom:
        def poll_once(self):
            raise RuntimeError('fallo simulado')

    events = []
    controller = HUPollingController(Boom(), interval_s=0.1,
                                     on_event=events.append)
    event = controller.run_once()
    assert event.error == 'fallo simulado'
    assert events and events[0].error == 'fallo simulado'


def test_polling_controller_never_starts_second_thread_while_stopping():
    entered = threading.Event()
    release = threading.Event()

    class Blocking:
        def poll_once(self):
            entered.set()
            release.wait(timeout=2.0)
            return PollEvent()

    controller = HUPollingController(Blocking(), interval_s=0.01)
    controller.start()
    assert entered.wait(timeout=1.0)
    assert controller.stop(timeout=0.01) is False
    with pytest.raises(RuntimeError, match='aun esta terminando'):
        controller.start()
    release.set()
    assert controller._thread.join(timeout=1.0) is None
    assert controller.stop(timeout=1.0) is True
    assert not controller.is_alive


def test_gui_does_not_release_capture_lock_until_worker_stops():
    class Guard:
        released = False

        def release(self):
            self.released = True

    class Controller:
        def stop(self):
            return False

    class Root:
        destroyed = False

        def destroy(self):
            self.destroyed = True

    gui = object.__new__(HUParityGUI)
    gui._capture_guard = Guard()
    gui._controller = Controller()
    gui.root = Root()
    gui.destroy()
    assert not gui._capture_guard.released
    assert gui.root.destroyed


def test_capture_preserves_pil_for_live_turn_detection():
    marker = object()
    capture = HUCaptureAdapter(
        capture_fn=lambda: (_state(), 'image-array', marker))
    frame = capture.capture()
    assert frame.image == 'image-array'
    assert frame.pil is marker


def test_default_capture_timestamp_is_taken_before_ocr(monkeypatch):
    from PIL import Image, ImageGrab

    events = []
    captured_at = '2026-11-16T12:00:00+00:00'
    monkeypatch.setattr(ImageGrab, 'grab', lambda: events.append('grab') or
                        Image.new('RGB', (1, 1)))
    state_reader_module = ModuleType('lector_estado')
    card_reader_module = ModuleType('lector_unificado')

    class StateReader:
        def __init__(self):
            pass

        def read_all(self, _pil):
            events.append('state_ocr')
            return _state()

    class CardReader:
        def __init__(self):
            pass

        def read_all(self, _image):
            events.append('card_ocr')
            return {}

    state_reader_module.StateReader = StateReader
    card_reader_module.CardReader = CardReader
    monkeypatch.setitem(sys.modules, 'lector_estado', state_reader_module)
    monkeypatch.setitem(sys.modules, 'lector_unificado', card_reader_module)

    def clock():
        events.append('screenshot_timestamp')
        return captured_at

    frame = HUCaptureAdapter(clock=clock).capture()
    assert frame.captured_at == captured_at
    assert events.index('screenshot_timestamp') < events.index('state_ocr')
    assert events.index('screenshot_timestamp') < events.index('card_ocr')


def test_parity_hand_db_requires_explicit_authorization():
    historical = PROJECT_ROOT / 'data' / 'hands_db.jsonl'
    with pytest.raises(ValueError, match='Fase 10.2'):
        ExperimentalConfig.default().with_paths(parity_hands_path=historical)


def test_parity_tests_do_not_modify_historical_hand_db(tmp_path):
    historical = PROJECT_ROOT / 'data' / 'hands_db.jsonl'
    before = (hashlib.sha256(historical.read_bytes()).hexdigest()
              if historical.exists() else None)
    assistant = _assistant(tmp_path)
    assistant.register_analysis(assistant.analyze())
    after = (hashlib.sha256(historical.read_bytes()).hexdigest()
             if historical.exists() else None)
    assert after == before


def test_hu_positions_blinds_stacks_and_action_order(tmp_path):
    config = _config(tmp_path)
    assert config.parity_position_mode == 'hu_sb_bb'
    assistant = _assistant(tmp_path)
    analysis = assistant.analyze()
    hand = assistant.engine.rec.hand
    positions = {p['_id']: p['pos'] for p in hand['players'] if p['active']}
    assert positions == {'hero': 'SB', 'p1': 'BB'}
    assert assistant.engine.rec._get_street_order(None, 'preflop')[-2:] == [
        'SB', 'BB']
    assert assistant.engine.rec._get_street_order(None, 'flop')[:2] == [
        'BB', 'SB']
    posts = [(a['pos'], a['action'], a['amount']) for a in
             hand['streets']['preflop']['actions']]
    assert ('SB', 'p', 0.5) in posts
    assert ('BB', 'p', 1.0) in posts
    # LiveRecorder almacena stack=stake+bet; el comparador resta la apuesta.
    players = {p['_id']: p for p in hand['players']}
    assert players['hero']['stack'] == pytest.approx(100.5)
    assert analysis.state.hero_stack == pytest.approx(100.0)
    assert analysis.state.hero_position == 'SB'
    assert analysis.state.villain_position == 'BB'


def test_manual_positions_are_restored_after_experimental_step(tmp_path):
    previous = dict(live_recorder_positions := __import__(
        'recorder_live').MANUAL_POSITIONS)
    live_recorder_positions.clear()
    live_recorder_positions['p5'] = 'CO'
    try:
        _assistant(tmp_path).analyze()
        assert live_recorder_positions == {'p5': 'CO'}
    finally:
        live_recorder_positions.clear()
        live_recorder_positions.update(previous)


def test_assistant_turn_order_is_hu_preflop_and_postflop(tmp_path):
    assistant = _assistant(tmp_path)
    assistant.analyze()
    engine = assistant.engine
    state = _state()
    # Preflop: button/SB acts before BB despite owing half a blind.
    assert engine._next_to_act(state, 'hero') is True
    assert engine._next_to_act(state, 'p1') is False
    engine.rec.hand['streets']['preflop']['actions'].append(
        {'pos': 'SB', 'action': 'c', 'amount': 1.0})
    state.update(hero_bet=1.0, p1_bet=1.0)
    assert engine._next_to_act(state, 'hero') is False
    assert engine._next_to_act(state, 'p1') is True

    # Postflop: BB acts first; after BB checks, SB/button acts.
    engine.rec.hand['current_street'] = 'flop'
    engine.rec.hand['streets']['flop']['actions'] = []
    state.update(hero_bet=0.0, p1_bet=0.0)
    assert engine._next_to_act(state, 'p1') is True
    assert engine._next_to_act(state, 'hero') is False
    engine.rec.hand['streets']['flop']['actions'].append(
        {'pos': 'BB', 'action': 'x', 'amount': 0.0})
    assert engine._next_to_act(state, 'hero') is True


def test_postflop_prediction_abstains_without_order_evidence(tmp_path):
    state = hu_state_fixtures()['turn_hero_facing_bet']
    assistant = _assistant(tmp_path, state=state)
    analysis = assistant.analyze()
    assert analysis.prediction is None
    assert analysis.canonical_reason.startswith(
        'postflop_position_order_unverified')


def test_live_default_is_diagnostic_only_and_discrepancy_is_explicit(tmp_path):
    assistant = _assistant(tmp_path, parity_position_mode='live_default')
    analysis = assistant.analyze()
    assert analysis.snapshot['hero_position'] == 'BTN'
    assert analysis.prediction.metadata['live_default_position'] == 'BTN'
    assert analysis.prediction.metadata['position_mode'] == 'live_default'
    assert 'position_mapping_live_btn_vs_hu_sb' in analysis.uncertainty_reasons
    with pytest.raises(ValueError, match='solo diagnostico'):
        assistant.register_analysis(analysis)


def test_comparison_fixtures_cover_fields_and_preserve_unknowns(tmp_path):
    required = {
        'active_count', 'active_players', 'hero_identity', 'villain_identity',
        'hero_position', 'villain_position', 'hero_private_cards',
        'villain_private_cards', 'board', 'hero_stack', 'villain_stack',
        'pot', 'hero_bet', 'villain_bet', 'hero_contribution',
        'villain_contribution', 'pending_action', 'player_to_act',
        'hand_state', 'street',
    }
    statuses = set()
    fixtures = hu_state_fixtures()
    assert {'preflop_sb_to_act', 'preflop_bb_option', 'flop_bb_first_checked',
            'turn_hero_facing_bet', 'river_no_bet'} <= set(fixtures)
    for name, state in fixtures.items():
        result = compare_frame_state(
            state, work_dir=tmp_path / name,
            manual_positions={'hero': 'SB', 'p1': 'BB'})
        assert required <= {item.field for item in result.comparisons}
        statuses.update(item.status for item in result.comparisons)
        hero_stack = next(item for item in result.comparisons
                          if item.field == 'hero_stack')
        assert hero_stack.status == SEMANTIC
    assert NOT_COMPARABLE in statuses
    assert DISCREPANCY in {
        item.status for item in compare_frame_state(
            fixtures['preflop_sb_to_act'], work_dir=tmp_path / 'diagnostic'
        ).comparisons
    }
    turn = compare_frame_state(
        fixtures['turn_hero_facing_bet'], work_dir=tmp_path / 'turn',
        manual_positions={'hero': 'SB', 'p1': 'BB'})
    assert next(x for x in turn.comparisons if x.field == 'board').status == 'exact'
    assert next(x for x in turn.comparisons
                if x.field == 'to_call').status == NOT_COMPARABLE
    assert 'to_call' in {x['field'] for x in turn.not_comparable}


def test_comparison_classifies_all_four_equivalence_levels(tmp_path):
    sample = compare_frame_state(_state(), work_dir=tmp_path)
    def classification(status):
        return StateComparison(
            hu=sample.hu, live=sample.live,
            comparisons=(FieldComparison(
                field='synthetic', status=status, experimental=1, live=1),),
        ).classification

    assert classification(EXACT) == 'exact_equivalence'
    assert classification(SEMANTIC) == 'semantic_equivalence'
    assert classification(DISCREPANCY) == 'relevant_discrepancy'
    assert classification(NOT_COMPARABLE) == (
        'not_comparable_insufficient_information')


def test_comparison_card_normalization_and_missing_data_are_not_equivalent(tmp_path):
    state = _state(p1_cards=['QH', '10d'], player_to_act='hero')
    result = compare_frame_state(
        state, work_dir=tmp_path,
        manual_positions={'hero': 'SB', 'p1': 'BB'})
    villain_cards = next(x for x in result.comparisons
                         if x.field == 'villain_private_cards')
    assert villain_cards.status == SEMANTIC
    assert villain_cards.experimental == ('Qh', 'Td')
    assert villain_cards.normalization == (
        'rank upper-case, suit lower-case, 10→T')
    state.pop('p1_cards')
    missing = compare_frame_state(
        state, work_dir=tmp_path / 'missing',
        manual_positions={'hero': 'SB', 'p1': 'BB'})
    villain_cards = next(x for x in missing.comparisons
                         if x.field == 'villain_private_cards')
    assert villain_cards.status == NOT_COMPARABLE


def test_unknown_seat_state_abstains_before_engine(tmp_path):
    state = _state()
    state.pop('p5_state')
    analysis = _assistant(tmp_path, state=state).analyze()
    assert analysis.prediction is None
    assert analysis.state.status == 'unresolved'
    assert analysis.canonical_reason == 'active_player_count_uncertain'


def test_missing_board_observation_abstains(tmp_path):
    state = _state()
    state.pop('community')
    analysis = _assistant(tmp_path, state=state).analyze()
    assert analysis.prediction is None
    assert analysis.canonical_reason == 'board_not_observed'


def test_stale_and_slow_frames_are_rejected_before_engine(tmp_path):
    assistant = _assistant(tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    stale = CapturedFrame(state=_state(), captured_at=old, source='fixture')
    stale_result = assistant.analyze(stale)
    assert stale_result.prediction is None
    assert stale_result.canonical_reason.startswith('stale_capture')
    assert assistant.engine is None

    slow_ocr = CapturedFrame(
        state=_state(), captured_at=datetime.now(timezone.utc).isoformat(),
        source='fixture', ocr_ms=4000.0)
    slow_result = assistant.analyze(slow_ocr)
    assert slow_result.prediction is None
    assert slow_result.canonical_reason.startswith('ocr_delay')
    assert assistant.engine is None


def test_poll_persists_before_observing_post_capture_actions(tmp_path, monkeypatch):
    assistant = _assistant(tmp_path)
    order = []
    original_register = assistant.registry.register_prediction
    original_observe = assistant._record_observed_outcomes

    def register(prediction):
        order.append('persist_prediction')
        return original_register(prediction)

    def observe():
        order.append('observe_posterior')
        return original_observe()

    monkeypatch.setattr(assistant.registry, 'register_prediction', register)
    monkeypatch.setattr(assistant, '_record_observed_outcomes', observe)
    event = assistant.poll_once()
    assert event.error is None
    assert 'persist_prediction' in order
    assert 'observe_posterior' in order
    assert order.index('persist_prediction') < order.index('observe_posterior')


def test_no_pending_hu_action_is_checked_before_live_recommendation(
        tmp_path, monkeypatch):
    assistant = _assistant(tmp_path)
    assert assistant.analyze().prediction is not None
    calls = []

    def forbidden_recommendation(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError('no debio calcularse fuera del turno HU')

    monkeypatch.setattr(assistant.engine, 'recomendacion',
                        forbidden_recommendation)
    after_call = _state(hero_stake=99.5, hero_bet=1.0,
                        p1_stake=100.0, p1_bet=1.0, pot=2.5)
    analysis = assistant.analyze(after_call, require_turn=False)
    assert analysis.prediction is None
    assert analysis.canonical_reason == 'no_hu_decision_pending'
    assert calls == []


def test_persistence_error_never_claims_prediction_registered(tmp_path, monkeypatch):
    assistant = _assistant(tmp_path)

    def fail(_prediction):
        raise OSError('disk full')

    monkeypatch.setattr(assistant.registry, 'register_prediction', fail)
    event = assistant.poll_once()
    assert event.error == 'disk full'
    assert event.registration is None
    assert assistant.verify().event_count == 0


def test_full_prediction_to_final_outcome_lifecycle_is_ordered(tmp_path):
    assistant = _assistant(tmp_path)
    prediction_event = assistant.poll_once()
    assert prediction_event.error is None
    assert prediction_event.registration is not None
    prediction_id = prediction_event.registration.prediction_id
    assert [event['event_type'] for event in assistant.registry.read_events()] == [
        'HU_PREDICTION']

    # LiveRecorder finaliza la mano en runtime; el callback solo encola el
    # resultado hasta el siguiente ciclo posterior a la prediccion durable.
    assistant.engine.rec.finalize_hand(_state())
    assert [event['event_type'] for event in assistant.registry.read_events()] == [
        'HU_PREDICTION']
    next_event = assistant.poll_once()
    assert next_event.error is None
    events = assistant.registry.read_events()
    assert [event['event_type'] for event in events] == [
        'HU_PREDICTION', 'HU_OUTCOME']
    outcome = events[1]['payload']
    assert outcome['prediction_id'] == prediction_id
    assert outcome['result'] is not None
    assert assistant.verify().ok


def test_expired_analysis_cannot_be_registered(tmp_path):
    assistant = _assistant(tmp_path)
    analysis = assistant.analyze()
    expired = replace(
        analysis,
        captured_at=(datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat())
    with pytest.raises(ValueError, match='prediccion no registrada: stale_capture'):
        assistant.register_analysis(expired)
    assert assistant.verify().event_count == 0


def test_capture_sequence_rejects_reordered_and_duplicate_timestamps(tmp_path):
    assistant = _assistant(tmp_path)
    now = datetime.now(timezone.utc)
    newest = CapturedFrame(_state(), now.isoformat(), source='sequence')
    assert assistant.analyze(newest).prediction is not None

    older = CapturedFrame(
        _state(), (now - timedelta(milliseconds=100)).isoformat(),
        source='sequence')
    out_of_order = assistant.analyze(older)
    assert out_of_order.prediction is None
    assert out_of_order.canonical_reason == 'out_of_order_capture'

    same_time = CapturedFrame(_state(), now.isoformat(), source='sequence')
    duplicate = assistant.analyze(same_time)
    assert duplicate.prediction is None
    assert duplicate.canonical_reason == 'duplicate_capture_timestamp'


def test_restart_with_unresolved_prediction_fails_closed_and_dedupes(
        tmp_path):
    first = _assistant(tmp_path)
    event = first.poll_once()
    assert event.registration is not None
    calls = []
    restarted = LiveParityAssistant(
        _config(tmp_path),
        capture=HUCaptureAdapter(capture_fn=lambda: calls.append(True) or _state()),
        models=SimpleNamespace(oracle=None))
    blocked = restarted.poll_once()
    assert blocked.error and 'reinicio bloqueado' in blocked.error
    assert calls == []
    assert first.verify().event_count == 1

    first.record_outcome(
        event.registration.prediction_id,
        exclusion_reason='controlled_restart_reconciliation')
    repeated = restarted.poll_once()
    assert repeated.error is None
    assert first.verify().event_count == 2  # prediction + outcome, no duplicate
    assert [item['event_type'] for item in first.registry.read_events()] == [
        'HU_PREDICTION', 'HU_OUTCOME']


def test_hand_change_expires_pending_prediction_without_cross_hand_join(
        tmp_path):
    assistant = _assistant(tmp_path)
    event = assistant.poll_once()
    prediction_id = event.registration.prediction_id
    assistant.engine.rec.hand['hand_id'] = 'H_DIFFERENT'
    assistant._flush_post_capture_observations()
    outcome = assistant.registry.read_events()[-1]['payload']
    assert outcome['prediction_id'] == prediction_id
    assert outcome['observed_action'] is None
    assert outcome['exclusion_reason'] == 'hand_id_changed_before_outcome'
    assert outcome['new_information']['association'] == (
        'excluded_not_joined_across_hands')


def test_prospective_registry_enforces_single_writer_lock(tmp_path):
    assistant = _assistant(tmp_path)
    analysis = assistant.analyze()
    lock_path = assistant.registry.lock_path
    lock_path.write_text(str(os.getpid()), encoding='utf-8')
    try:
        with pytest.raises(RuntimeError, match='escritor activo'):
            assistant.register_analysis(analysis)
    finally:
        lock_path.unlink(missing_ok=True)
    assert assistant.verify().event_count == 0


def test_persistence_and_recorder_outputs_are_experimental_only(
        tmp_path, monkeypatch):
    protected = [
        PROJECT_ROOT / 'data' / 'hands_db.jsonl',
        PROJECT_ROOT / 'data' / 'decisions.jsonl',
        PROJECT_ROOT / 'data' / 'preflop_matrices.json',
        PROJECT_ROOT / 'data' / 'profiles.json',
        PROJECT_ROOT / 'data' / 'profile_ranges.json',
        PROJECT_ROOT / 'data' / 'shadow_hierarchy.jsonl',
    ]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in protected if path.is_file()}
    root = (PROJECT_ROOT / 'data').resolve()
    builtin_open = builtins.open
    path_open = Path.open

    def rejects_protected_write(path, mode):
        if not any(flag in mode for flag in 'wax+'):
            return
        try:
            Path(path).resolve().relative_to(root)
        except (ValueError, OSError, TypeError):
            return
        raise AssertionError('escritura prohibida en data/: %s' % path)

    def guarded_builtin_open(file, mode='r', *args, **kwargs):
        rejects_protected_write(file, mode)
        return builtin_open(file, mode, *args, **kwargs)

    def guarded_path_open(path, mode='r', *args, **kwargs):
        rejects_protected_write(path, mode)
        return path_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', guarded_builtin_open)
    monkeypatch.setattr(Path, 'open', guarded_path_open)
    assistant = _assistant(tmp_path)
    analysis = assistant.analyze()
    assistant.register_analysis(analysis)
    recorder = assistant.engine.rec
    assert isinstance(assistant.engine.decision_log, SnapshotCollector)
    assert assistant.engine.shadow is False
    assert recorder.output_path == str(tmp_path / 'hands_parity.jsonl')
    assert Path(recorder.ambiguity_capture_dir).is_relative_to(tmp_path)
    assert recorder.capture_dir is None
    assert recorder.session_dir is None
    assert not assistant.config.parity_enable_live_decision_log
    assert not assistant.config.parity_enable_shadow_logs
    assert Path(assistant.registry_path).is_relative_to(tmp_path)
    # Fuerza una finalizacion sintetica para verificar el unico output del
    # recorder; el path, las ambigüedades y sus indices permanecen en runtime.
    recorder.finalize_hand(_state())
    assert Path(recorder.output_path).is_file()
    assert Path(recorder.output_path).is_relative_to(tmp_path)
    assert Path(recorder.ambiguity_index_path).is_relative_to(tmp_path)
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in before} == before


def test_concurrency_guard_blocks_duplicate_and_detected_original(tmp_path):
    lock = tmp_path / 'capture_session.lock'
    first = CaptureSessionGuard(lock, process_probe=lambda: [])
    second = CaptureSessionGuard(lock, process_probe=lambda: [])
    assert first.acquire() is None
    with pytest.raises(ConcurrencyError, match='ocupado'):
        second.acquire()
    first.release()

    original_running = CaptureSessionGuard(
        lock, process_probe=lambda: [{'pid': 123, 'command': 'asistente_live'}])
    with pytest.raises(ConcurrencyError, match='asistente_live detectado'):
        original_running.acquire()
    assert not lock.exists()


def test_concurrency_guard_reports_unknown_original_and_reclaims_stale_lock(
        tmp_path):
    lock = tmp_path / 'capture_session.lock'
    guard = CaptureSessionGuard(lock, process_probe=lambda: None)
    with pytest.raises(ConcurrencyError, match='inicio abortado'):
        guard.acquire()
    assert not lock.exists()

    manual_guard = CaptureSessionGuard(
        lock, process_probe=lambda: None, require_process_detection=False)
    guard_warning = manual_guard.acquire()
    assert guard_warning and 'no se pudo verificar' in guard_warning
    manual_guard.release()

    lock.write_text(json.dumps({
        'pid': 987654, 'host': __import__('socket').gethostname(),
        'token': 'stale',
    }), encoding='utf-8')
    stale_guard = CaptureSessionGuard(
        lock, process_probe=lambda: [], pid_alive=lambda _pid: False)
    assert stale_guard.acquire() is None
    stale_guard.release()
    assert not lock.exists()


def test_capture_guard_rechecks_for_original_started_after_session(tmp_path):
    responses = iter([[], [{'pid': 456, 'command': 'asistente_live'}]])
    guard = CaptureSessionGuard(
        tmp_path / 'capture_session.lock', process_probe=lambda: next(responses),
        recheck_interval_s=0)
    assert guard.acquire() is None
    with pytest.raises(ConcurrencyError, match='asistente_live detectado'):
        guard.acquire()
    assert guard.held
    guard.release()


def test_assistant_and_gui_fail_clearly_when_capture_is_busy(tmp_path):
    called = []
    guard = CaptureSessionGuard(
        tmp_path / 'capture_session.lock',
        process_probe=lambda: [{'pid': 42, 'command': 'asistente_live_gui'}])
    assistant = LiveParityAssistant(
        _config(tmp_path),
        capture=HUCaptureAdapter(capture_fn=lambda: called.append(True)),
        models=SimpleNamespace(oracle=None), capture_guard=guard)
    with pytest.raises(ConcurrencyError, match='recurso de captura ocupado'):
        assistant.capture()
    assert called == []

    class Var:
        value = ''

        def set(self, value):
            self.value = value

    class Controller:
        started = False

        def start(self):
            self.started = True

    gui = object.__new__(HUParityGUI)
    gui._capture_guard = guard
    gui._controller = Controller()
    gui.auto_status_var = Var()
    gui.decision_status_var = Var()
    gui.start_auto()
    assert 'ERROR: recurso de captura ocupado' in gui.auto_status_var.value
    assert not gui._controller.started


def test_polling_gui_integration_keeps_action_provisional(tmp_path):
    assistant = _assistant(tmp_path)
    event = assistant.poll_once()
    assert event.error is None and event.registration is not None

    class Var:
        def __init__(self):
            self.value = ''

        def set(self, value):
            self.value = value

    gui = object.__new__(HUParityGUI)
    gui.assistant = assistant
    for name in ('decision_status_var', 'equity_status_var',
                 'action_status_var', 'persist_status_var',
                 'outcome_prediction_var', 'auto_status_var'):
        setattr(gui, name, Var())
    gui._set_detail = lambda _analysis: None
    gui._refresh_registry_status = lambda: None
    gui._handle_event(PollEvent(error='fallo transitorio', elapsed_ms=12.0))
    assert 'ERROR: fallo transitorio' in gui.auto_status_var.value
    gui._handle_event(event)
    assert 'NO demostrada' in gui.action_status_var.value
    assert 'auto-persistida' in gui.persist_status_var.value
    assert gui.auto_status_var.value.startswith('activo;')
    assert 'No hay botones para ejecutar' in PARITY_WARNING


def test_default_config_is_hu_mode_and_rejects_external_hand_output(tmp_path):
    assert ExperimentalConfig.default().parity_position_mode == 'hu_sb_bb'
    with pytest.raises(ValueError, match='dentro de runtime_dir'):
        ExperimentalConfig.default().with_paths(
            runtime_dir=str(tmp_path),
            parity_hands_path=PROJECT_ROOT / 'data' / 'outside.jsonl')
    with pytest.raises(ValueError, match='shadow_logs esta prohibido'):
        ExperimentalConfig.default().with_paths(parity_enable_shadow_logs=True)
