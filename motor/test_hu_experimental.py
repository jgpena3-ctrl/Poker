"""Pruebas del asistente experimental HU (Fase 10).

Todas las observaciones son sinteticas. No se usa ``data/hands_db.jsonl`` como
fixture de escritura ni se captura una pantalla real.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from motor.hu_experimental import (
    CaptureError,
    CapturedFrame,
    ExperimentalConfig,
    HUCaptureAdapter,
    HUExperimentalAssistant,
    interpret_state,
)
from motor.hu_prospective import HUPrediction


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = PROJECT_ROOT / 'motor' / 'hu_experimental'


def _hu_state(**overrides):
    state = {
        'hero_state': 'activo',
        'p1_state': 'activo',
        'p2_state': 'inactivo',
        'p3_state': 'inactivo',
        'p4_state': 'inactivo',
        'p5_state': 'inactivo',
        'btn': 'hero',
        'hero_cards': ['As', 'Kd'],
        'community': [],
        'pot': 1.5,
        'hero_stake': 100.0,
        'p1_stake': 100.0,
        'hero_bet': 0.5,
        'p1_bet': 1.0,
    }
    state.update(overrides)
    return state


def _assistant(tmp_path, **kwargs):
    config = ExperimentalConfig.with_paths(runtime_dir=str(tmp_path), **kwargs)
    return HUExperimentalAssistant(config)


def test_capture_adapter_injected_state_is_explicit_and_does_not_write(tmp_path):
    state = _hu_state()
    adapter = HUCaptureAdapter(capture_fn=lambda: (state, 'image'))
    frame = adapter.capture()
    assert isinstance(frame, CapturedFrame)
    assert frame.state == state
    assert frame.source == 'injected'
    assert frame.captured_at.endswith('+00:00')
    assert list(tmp_path.iterdir()) == []


def test_capture_adapter_rejects_bad_payload():
    adapter = HUCaptureAdapter(capture_fn=lambda: 42)
    with pytest.raises(CaptureError):
        adapter.capture()


def test_interpret_state_hu_ready_positions_and_to_call():
    state = interpret_state(_hu_state())
    assert state.status == 'ready'
    assert state.hero_position == 'SB'
    assert state.villain_position == 'BB'
    assert state.villain_seat == 'p1'
    assert state.to_call == pytest.approx(0.5)
    assert state.street == 'preflop'


def test_interpret_state_three_active_is_not_heads_up():
    state = interpret_state(_hu_state(p2_state='activo'))
    assert state.status == 'no_decision'
    assert state.reason == 'not_heads_up'


def test_interpret_state_missing_hero_cards_is_unresolved():
    state = interpret_state(_hu_state(hero_cards=[]))
    assert state.status == 'unresolved'
    assert state.reason == 'hero_cards_not_observed'


def test_interpret_state_invalid_board_is_no_decision():
    state = interpret_state(_hu_state(community=['2c', '7h']))
    assert state.status == 'no_decision'
    assert state.reason == 'invalid_board'


def test_interpret_state_duplicate_cards_is_no_decision():
    state = interpret_state(_hu_state(hero_cards=['As', 'As']))
    assert state.status == 'no_decision'
    assert state.reason == 'duplicate_cards'


def test_engine_preflop_does_not_invent_equity(tmp_path):
    assistant = _assistant(tmp_path)
    analysis = assistant.analyze(_hu_state())
    assert analysis.state.status == 'ready'
    assert analysis.equity is None
    assert 'preflop_equity_not_computed_without_fast_contract' in (
        analysis.uncertainty_reasons)
    assert analysis.selected_action is None
    assert analysis.provisional_selected_action is None
    assert analysis.ev_result is not None
    assert analysis.ev_result.best_action == 'fold'


def test_engine_postflop_uses_prior_but_never_demonstrates(tmp_path):
    assistant = _assistant(tmp_path)
    state = _hu_state(
        community=['2c', '7h', 'Qs'],
        pot=10.0,
        hero_bet=0.0,
        p1_bet=0.0,
    )
    analysis = assistant.analyze(state)
    assert analysis.state.street == 'flop'
    assert analysis.equity is not None
    # El prior plano declara cobertura desconocida aunque la equity sea
    # calculable contra ese prior. No es cobertura exacta del rival.
    assert analysis.coverage_state == 'unknown'
    assert analysis.selected_action is None
    assert analysis.provisional_selected_action is not None
    assert analysis.range_kind == 'prior'
    assert 'generic_flat_prior_not_opponent_specific' in (
        analysis.uncertainty_reasons)
    assert analysis.ev_result is not None
    assert analysis.ev_result.best_action is not None


def test_engine_uses_canonical_preflop_when_actions_are_present(tmp_path):
    assistant = _assistant(tmp_path)
    state = _hu_state(preflop_actions=[
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
    ])
    analysis = assistant.analyze(state)
    assert analysis.canonical_status == 'resolved'
    assert analysis.coverage_state == 'complete_exact'
    assert analysis.selected_action is None
    assert analysis.ev_result is not None
    # Aunque el plan canonico este completo, la equity preflop no se inventa.
    assert analysis.equity is None


def test_prediction_is_persisted_before_outcome_and_does_not_change(tmp_path):
    assistant = _assistant(tmp_path)
    state = _hu_state(community=['2c', '7h', 'Qs'], hero_bet=0.0, p1_bet=0.0)
    registration = assistant.predict_and_register(
        CapturedFrame(state=state, captured_at='2026-01-01T00:00:00+00:00'),
        prediction_id='pred-1',
        emitted_at='2026-01-01T00:00:01+00:00',
    )
    assert registration.prediction_id == 'pred-1'
    before = assistant.registry.get_prediction('pred-1')
    assert before is not None
    assert before['payload']['hero_cards'] == ['As', 'Kd']

    assistant.record_outcome(
        'pred-1', outcome_id='out-1',
        observed_at='2026-01-01T00:05:00+00:00',
        observed_action='check',
    )
    after = assistant.registry.get_prediction('pred-1')
    assert after == before
    assert assistant.verify().ok is True
    assert [e['event_type'] for e in assistant.registry.read_events()] == [
        'HU_PREDICTION', 'HU_OUTCOME']


def test_duplicate_prediction_id_is_rejected(tmp_path):
    assistant = _assistant(tmp_path)
    state = _hu_state()
    assistant.predict_and_register(
        state, prediction_id='same',
        emitted_at='2026-01-01T00:00:00+00:00')
    with pytest.raises(ValueError):
        assistant.predict_and_register(
            state, prediction_id='same',
            emitted_at='2026-01-01T00:01:00+00:00')


def test_non_hu_observation_is_preserved_with_reason(tmp_path):
    assistant = _assistant(tmp_path)
    registration = assistant.predict_and_register(
        _hu_state(p2_state='activo'), prediction_id='non-hu',
        emitted_at='2026-01-01T00:00:00+00:00')
    payload = assistant.registry.get_prediction('non-hu')['payload']
    assert registration.analysis.state.status == 'no_decision'
    assert payload['canonical_status'] == 'no_decision'
    assert any(reason.startswith('not_heads_up')
               for reason in payload['uncertainty_reasons'])
    assert payload['equity'] is None


def test_prediction_rejects_posterior_fields_in_metadata(tmp_path):
    assistant = _assistant(tmp_path)
    analysis = assistant.analyze(_hu_state())
    prediction = assistant.build_prediction(
        analysis, prediction_id='bad', emitted_at='2026-01-01T00:00:00+00:00')
    assert isinstance(prediction, HUPrediction)
    payload = prediction.to_payload()
    payload['metadata'] = dict(payload['metadata'])
    payload['metadata']['observed_action'] = 'call'
    with pytest.raises(ValueError):
        assistant.registry.register_prediction(payload)


def test_experimental_package_reuses_only_the_capture_pipeline():
    """El unico modulo live permitido es capture_live (lectura de pantalla).

    El motor, el recorder y la GUI originales siguen prohibidos: el asistente
    experimental no debe poder escribir manos/decisiones ni ejecutar acciones.
    """
    forbidden = {
        'asistente_live', 'asistente_live_gui', 'recommend_loop',
        'serving', 'recorder_live', 'hands_db',
    }
    capture_imports = []
    for path in PACKAGE.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or '']
            for name in names:
                parts = set(name.split('.'))
                assert not (parts & forbidden), path
                if 'capture_live' in parts:
                    capture_imports.append(path.name)
    assert set(capture_imports) == {'capture.py'}


def test_gui_module_does_not_define_action_buttons():
    path = PACKAGE / 'gui.py'
    source = path.read_text(encoding='utf-8')
    for forbidden in ('Fold', 'Call', 'Raise', 'All-in', 'All in'):
        assert ("text='%s'" % forbidden) not in source
        assert ('text="%s"' % forbidden) not in source
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert not any('asistente_live' in name for name in imported)
    assert not any('recommend_loop' in name for name in imported)


def test_data_hands_db_hash_is_unchanged_by_experimental_tests(tmp_path):
    target = PROJECT_ROOT / 'data' / 'hands_db.jsonl'
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    assistant = _assistant(tmp_path)
    assistant.analyze(_hu_state())
    assistant.predict_and_register(
        _hu_state(), prediction_id='hash-check',
        emitted_at='2026-01-01T00:00:00+00:00')
    after = hashlib.sha256(target.read_bytes()).hexdigest()
    assert before == after
