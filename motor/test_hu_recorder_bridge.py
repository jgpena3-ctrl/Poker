"""Tests de Fase 10.5: snapshot del recorder original y puerta HU.

Todos los tests usan directorios temporales. No capturan una mesa real ni
escriben en ``data/``. El fixture ``stored_frame.json`` es una lectura
sintetica guardada, no una regla especial de produccion.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest

import motor.asistente_live as live
from motor.hu_experimental.capture import CapturedFrame, HUCaptureAdapter
from motor.hu_experimental.config import PROJECT_ROOT, ExperimentalConfig
from motor.hu_parity.parity import LiveParityAssistant
from motor.hu_parity.recorder_bridge import (
    SnapshotLiveRecorder,
    _ledger_zero_contributions,
    _normalize_street_boards,
    build_recorder_snapshot,
    build_unprocessed_snapshot,
    interpret_recorder_snapshot,
)


DATA_HANDS = PROJECT_ROOT / 'data' / 'hands_db.jsonl'
DATA_DECISIONS = PROJECT_ROOT / 'data' / 'decisions.jsonl'


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
        'registry_name': 'registro_bridge.jsonl',
        'parity_hands_path': tmp_path / 'hands_bridge.jsonl',
        # Los tests del bridge usan la mesa realmente HU (SB/BB).
        'parity_position_mode': 'hu_sb_bb',
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


def _hash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def test_exactly_one_processed_frame_and_raw_state_is_preserved(tmp_path):
    state = _state()
    captures = []
    capture = HUCaptureAdapter(capture_fn=lambda: (captures.append(True), state)[1])
    assistant = LiveParityAssistant(
        _config(tmp_path), capture=capture,
        models=SimpleNamespace(oracle=None))

    analysis = assistant.analyze()
    recorder = assistant.engine.rec
    snapshot = analysis.recorder_snapshot

    assert captures == [True]
    assert recorder.process_frame_executions == 1
    assert recorder.process_frame_calls == 2  # una real + una suprimida por step
    assert recorder.suppressed_process_calls == 1
    assert snapshot is not None and snapshot.processed
    assert snapshot.sequence == 1
    assert snapshot.as_dict()['raw_state'] == state
    assert snapshot.captured_at == analysis.captured_at
    assert snapshot.capture_source == analysis.capture_source
    assert analysis.state.raw_state == state
    assert analysis.state.interpretation_source == 'recorder_snapshot'
    assert analysis.state.recorder_snapshot_sha256 == snapshot.fingerprint
    assert snapshot.hand is not None
    assert snapshot.hand['hand_id'] == recorder.hand['hand_id']
    assert recorder.hand['hand_id'] == 'H_0001'
    # El motor original puede mutar su copia interna, pero no la captura.
    assert state == _state()


def test_snapshot_preserves_positions_contributions_actions_and_provenance(
        tmp_path):
    assistant = _assistant(tmp_path)
    analysis = assistant.analyze()
    snapshot = analysis.recorder_snapshot
    state = analysis.state

    assert state.status == 'ready'
    assert state.hero_position == 'SB'
    assert state.villain_position == 'BB'
    assert dict(snapshot.positions) == {'hero': 'SB', 'p1': 'BB'}
    assert dict(snapshot.decision_view.hu_positions) == {
        'hero': 'SB', 'p1': 'BB'}
    assert snapshot.active_seats == ('hero', 'p1')
    assert snapshot.folded_seats == ()
    assert snapshot.inactive_seats == ('p2', 'p3', 'p4', 'p5')
    assert snapshot.allin_seats == ()
    assert dict(snapshot.contributions)['hero'] == pytest.approx(0.5)
    assert dict(snapshot.contributions)['p1'] == pytest.approx(1.0)
    assert snapshot.to_call == pytest.approx(0.5)
    assert snapshot.to_call_source == 'recorder_contributions'
    assert snapshot.pot_read == pytest.approx(1.5)
    assert snapshot.pot_live_calculated == pytest.approx(1.5)
    assert snapshot.street == 'preflop'
    assert snapshot.contributions_by_street['preflop']['hero'] == pytest.approx(0.5)
    assert snapshot.contributions_by_street['preflop']['p1'] == pytest.approx(1.0)
    assert [a['action'] for a in snapshot.actions_by_street['preflop']] == [
        'p', 'p']
    assert state.provenance['positions'] == 'recorded_hand'
    assert state.provenance['pot'] == 'ocr+recorded'
    assert state.provenance['to_call'] == 'recorder_contributions'
    assert set(snapshot.cards_recorded['hero']) == {'As', 'Kd'}
    assert set(snapshot.cards_read['hero']) == {'As', 'Kd'}


def test_snapshot_is_immutable(tmp_path):
    assistant = _assistant(tmp_path)
    snapshot = assistant.analyze().recorder_snapshot
    with pytest.raises(FrozenInstanceError):
        snapshot.sequence = 99  # type: ignore[misc]
    with pytest.raises(TypeError):
        snapshot.raw_state['hero_cards'][0] = 'Qh'
    with pytest.raises(AttributeError):
        snapshot.raw_state['community'].append('2c')


def test_original_engine_receives_the_unmodified_raw_state(
        tmp_path, monkeypatch):
    state = _state()
    assistant = _assistant(tmp_path)
    engine = assistant.prepare_engine()
    seen = []

    def fake_reco(self, state_arg, verbose=None, on_reco=None, runout=None,
                  **kwargs):
        seen.append(state_arg)
        return None

    monkeypatch.setattr(engine, 'recomendacion',
                        MethodType(fake_reco, engine))
    frame = CapturedFrame(
        state=state, captured_at=datetime.now(timezone.utc).isoformat(),
        source='stored_frame', image=b'frame-image')
    analysis = assistant.analyze(frame)

    assert seen and seen[0] is frame.state
    assert seen[0] == _state()
    assert analysis.prediction is None
    assert analysis.recorder_snapshot.as_dict()['raw_state'] == _state()
    assert analysis.recorder_snapshot.image_sha256 == hashlib.sha256(
        b'frame-image').hexdigest()


def test_pot_read_vs_recorder_calculated_is_blocking_not_silently_corrected(
        tmp_path, monkeypatch):
    state = _state(pot=8.0)
    assistant = _assistant(tmp_path, state=state)
    engine = assistant.prepare_engine()
    recommendations = []
    monkeypatch.setattr(
        engine, 'recomendacion',
        lambda *_args, **_kwargs: recommendations.append(True))
    analysis = assistant.analyze()
    snapshot = analysis.recorder_snapshot

    assert snapshot.pot_read == pytest.approx(8.0)
    assert snapshot.pot_live_calculated == pytest.approx(1.5)
    assert any(c.startswith('pot_read_vs_calculated')
               for c in snapshot.contradictions)
    assert analysis.prediction is None
    assert analysis.canonical_reason.startswith(
        'contradiction:pot_read_vs_calculated')
    assert analysis.state.pot is None
    assert analysis.state.status == 'unresolved'
    assert 'pot_read_vs_calculated' in analysis.state.uncertainty_reasons[0]
    assert recommendations == []


def test_cards_ocr_vs_recorded_are_preserved_and_block(tmp_path):
    assistant = _assistant(tmp_path)
    first = assistant.analyze()
    assert set(first.state.hero_cards) == {'As', 'Kd'}

    changed = _state(hero_cards=['Qh', 'Qd'])
    assistant.capture_adapter = HUCaptureAdapter(capture_fn=lambda: changed)
    before = assistant.engine.rec.process_frame_executions
    second = assistant.analyze()
    snapshot = second.recorder_snapshot

    assert assistant.engine.rec.process_frame_executions == before + 1
    assert set(snapshot.cards_read['hero']) == {'Qh', 'Qd'}
    assert set(snapshot.cards_recorded['hero']) == {'As', 'Kd'}
    assert any(c.startswith('hero_cards_ocr_vs_recorded')
               for c in snapshot.contradictions)
    assert second.prediction is None
    assert second.canonical_reason.startswith(
        'contradiction:hero_cards_ocr_vs_recorded')
    # La vista HU se abstiene; el snapshot conserva ambos valores.
    assert second.state.hero_cards == ()
    assert snapshot.decision_view.hero_cards == ()


def test_button_outside_active_players_blocks_recommendation(tmp_path):
    state = _state(btn='p2')
    assistant = _assistant(tmp_path, state=state)
    analysis = assistant.analyze()

    assert assistant.engine.rec.process_frame_executions == 1
    assert analysis.prediction is None
    assert analysis.canonical_status == 'unresolved'
    assert analysis.canonical_reason.startswith(
        'contradiction:button_not_in_active')
    assert 'button_not_in_active:p2' in (
        analysis.recorder_snapshot.contradictions)


def test_incomplete_board_blocks_after_recorder_snapshot(tmp_path):
    state = _state(community=[
        {'rank': '2', 'suit': 'c'}, {'rank': '7', 'suit': 'h'}])
    assistant = _assistant(tmp_path, state=state)
    analysis = assistant.analyze()

    assert assistant.engine.rec.process_frame_executions == 1
    assert analysis.prediction is None
    assert analysis.canonical_reason.startswith(
        'contradiction:invalid_board_count')
    assert 'invalid_board_count:2' in (
        analysis.recorder_snapshot.contradictions)


def test_duplicate_card_between_villain_and_board_is_blocking(tmp_path):
    state = _state(
        p1_cards=['Qh'],
        community=[
            {'rank': 'Q', 'suit': 'h'},
            {'rank': '2', 'suit': 'c'},
            {'rank': '3', 'suit': 'd'},
        ],
    )
    assistant = _assistant(tmp_path, state=state)
    analysis = assistant.analyze()

    assert analysis.prediction is None
    assert any(item.startswith('duplicate_cards_ocr')
               for item in analysis.recorder_snapshot.contradictions)


def test_unknown_to_call_stays_none_and_never_becomes_zero(tmp_path):
    state = _state(hero_bet=None, p1_bet=None, to_call=None)
    snapshot = build_unprocessed_snapshot(None, state, sequence=0)
    hu = interpret_recorder_snapshot(
        snapshot, require_processed=False)

    assert hu.to_call is None
    assert hu.status == 'unresolved'
    assert hu.reason == 'to_call_not_observed'
    assert 'to_call_not_observed' in hu.uncertainty_reasons


def test_postflop_hero_without_action_uses_recorder_action_ledger_zero(
        tmp_path):
    assistant = _assistant(tmp_path)
    assistant.analyze()
    recorder = assistant.engine.rec
    hand = recorder.hand
    assert hand is not None

    # El recorder ya tiene la mano preflop. Simulamos el flop con una apuesta
    # del rival y sin accion del heroe (el caso de la mesa real: el rival
    # apuesta y el heroe aun no ha actuado).
    hand['current_street'] = 'flop'
    hand['streets']['flop']['board'] = ['9c', 'Ts', 'Th']
    hand['streets']['flop']['actions'] = [
        {'pos': 'BB', 'action': 'b', 'amount': 6.7,
         'amount_type': 'observed'},
    ]
    flop_state = _state(
        community=[
            {'rank': '9', 'suit': 'c'},
            {'rank': 'T', 'suit': 's'},
            {'rank': 'T', 'suit': 'h'},
        ],
        hero_bet=None,
        p1_bet=6.7,
        pot=8.2,
    )
    snapshot = build_recorder_snapshot(
        recorder, raw_state=flop_state, recorder_state=flop_state,
        sequence=2, processed=True)
    hu = interpret_recorder_snapshot(snapshot)

    assert snapshot.street == 'flop'
    assert snapshot.to_call == pytest.approx(6.7)
    assert snapshot.to_call_source == 'recorder_action_ledger'
    assert dict(snapshot.contributions)['hero'] == pytest.approx(0.0)
    assert dict(snapshot.contributions)['p1'] == pytest.approx(6.7)
    assert snapshot.pot_read == pytest.approx(8.2)
    assert snapshot.pot_live_calculated == pytest.approx(8.2)
    assert not snapshot.contradictions
    assert hu.status == 'ready'
    assert hu.to_call == pytest.approx(6.7)
    assert hu.hero_bet == pytest.approx(0.0)
    assert hu.villain_bet == pytest.approx(6.7)
    assert hu.provenance['to_call'] == 'recorder_action_ledger'
    assert hu.provenance['hero_bet'] == 'recorder_action_ledger_zero'
    # El valor ausente del OCR se conserva: no se convierte en cero.
    assert hu.raw_state['hero_bet'] is None
    assert 'to_call_not_observed' not in hu.uncertainty_reasons


def test_allin_missing_stack_is_inferred_and_pot_reconciled(tmp_path):
    assistant = _assistant(tmp_path)
    assistant.analyze()
    recorder = assistant.engine.rec
    hand = recorder.hand
    assert hand is not None

    # Caso H_1368 captura 48: el badge All-in tapa el stack (None), la apuesta
    # viva es 13.5 y el recorder no llego a incorporarla al ledger de flop.
    hand['current_street'] = 'flop'
    hand['streets']['flop']['board'] = ['9c', 'Ts', 'Th']
    hand['streets']['flop']['actions'] = []
    # Stack inicial 14.5 = 1.0 preflop + 13.5 all-in de flop.
    next(player for player in hand['players']
         if player.get('_id') == 'p1')['stack'] = 14.5
    flop_state = _state(
        community=[
            {'rank': '9', 'suit': 'c'},
            {'rank': 'T', 'suit': 's'},
            {'rank': 'T', 'suit': 'h'},
        ],
        hero_bet=None,
        p1_stake=None,
        p1_bet=13.5,
        pot=15.0,
    )
    snapshot = build_recorder_snapshot(
        recorder, raw_state=flop_state, recorder_state=flop_state,
        sequence=2, processed=True)
    hu = interpret_recorder_snapshot(snapshot)

    assert snapshot.allin_seats == ('p1',)
    # El None bruto del OCR se conserva; solo la vista efectiva usa 0.0.
    assert snapshot.stacks_read['p1'] is None
    assert snapshot.decision_view.villain_stack == pytest.approx(0.0)
    assert snapshot.to_call == pytest.approx(13.5)
    assert snapshot.to_call_source == 'allin_bet_reconciled'
    assert snapshot.pot_read == pytest.approx(15.0)
    assert snapshot.pot_live_calculated == pytest.approx(1.5)
    assert not snapshot.contradictions
    assert any(str(a).startswith('allin_inferred_from_unreadable_stack')
               for a in snapshot.decision_view.ambiguities)
    assert any(str(a).startswith('pot_reconciled_inferred_allin')
               for a in snapshot.decision_view.ambiguities)
    assert hu.status == 'ready'
    assert hu.pot == pytest.approx(15.0)
    assert hu.to_call == pytest.approx(13.5)
    assert hu.hero_stack == pytest.approx(100.0)
    assert hu.villain_stack == pytest.approx(0.0)
    assert hu.provenance['stacks'] == 'ocr+allin_inferred'
    assert hu.raw_state['p1_stake'] is None
    assert hu.raw_state['p1_bet'] == pytest.approx(13.5)

    # Sin la confirmacion aritmetica del stack inicial, la misma ausencia no
    # se convierte en all-in ni corrige el mismatch del bote.
    next(player for player in hand['players']
         if player.get('_id') == 'p1')['stack'] = 100.0
    unconfirmed = build_recorder_snapshot(
        recorder, raw_state=flop_state, recorder_state=flop_state,
        sequence=3, processed=True)
    unconfirmed_hu = interpret_recorder_snapshot(unconfirmed)
    assert unconfirmed.allin_seats == ()
    assert any(item.startswith('pot_read_vs_calculated')
               for item in unconfirmed.contradictions)
    assert unconfirmed_hu.status == 'unresolved'


def test_ledger_zero_requires_hand_and_absence_of_player_action():
    hand = {'streets': {'flop': {'actions': [
        {'pos': 'BB', 'action': 'b', 'amount': 6.7},
    ]}}}
    positions = {'hero': 'SB', 'p1': 'BB'}
    active = ('hero', 'p1')
    contributions = {'hero': None, 'p1': 6.7}
    bets = {'hero': None, 'p1': 6.7}

    assert _ledger_zero_contributions(
        hand, 'flop', positions, active, (), (), contributions, bets) == {
        'hero'}
    # Sin mano o en preflop no hay cero implicado.
    assert _ledger_zero_contributions(
        None, 'flop', positions, active, (), (), contributions, bets) == set()
    assert _ledger_zero_contributions(
        hand, 'preflop', positions, active, (), (), contributions, bets) == set()
    # Una apuesta OCR observada nunca se pisa con el cero del ledger.
    assert _ledger_zero_contributions(
        hand, 'flop', positions, active, (), (), contributions,
        {'hero': 6.7, 'p1': 6.7}) == set()
    # Un call/raise con contribucion ausente es desconocido, no cero.
    call_hand = {'streets': {'flop': {'actions': [
        {'pos': 'SB', 'action': 'c', 'amount': 6.7},
    ]}}}
    assert _ledger_zero_contributions(
        call_hand, 'flop', positions, active, (), (), contributions,
        bets) == set()
    # Un check si es un cero conocido.
    check_hand = {'streets': {'flop': {'actions': [
        {'pos': 'SB', 'action': 'x', 'amount': 0.0},
    ]}}}
    assert _ledger_zero_contributions(
        check_hand, 'flop', positions, active, (), (), contributions,
        bets) == {'hero'}
    # Un all-in no se completa con cero.
    assert _ledger_zero_contributions(
        hand, 'flop', positions, active, (), ('hero',), contributions,
        bets) == set()


def test_normalize_street_boards_completes_turn_and_river():
    hand = {'streets': {
        'preflop': {'board': [], 'actions': []},
        'flop': {'board': ['9c', 'Ts', 'Th'], 'actions': []},
        'turn': {'board': ['5c'], 'actions': []},
        'river': {'board': ['2d'], 'actions': []},
    }}

    _normalize_street_boards(hand)
    assert hand['streets']['turn']['board'] == ['9c', 'Ts', 'Th', '5c']
    assert hand['streets']['river']['board'] == [
        '9c', 'Ts', 'Th', '5c', '2d']

    # Idempotente: un board ya acumulado no se duplica.
    _normalize_street_boards(hand)
    assert hand['streets']['turn']['board'] == ['9c', 'Ts', 'Th', '5c']
    assert hand['streets']['river']['board'] == [
        '9c', 'Ts', 'Th', '5c', '2d']


def test_explicit_to_call_is_preserved_with_provenance(tmp_path):
    state = _state(hero_bet=None, p1_bet=None, to_call=2.5, pot=2.5)
    snapshot = build_unprocessed_snapshot(None, state, sequence=0)
    hu = interpret_recorder_snapshot(
        snapshot, require_processed=False)

    assert hu.status == 'ready'
    assert hu.to_call == pytest.approx(2.5)
    assert hu.provenance['to_call'] == 'explicit'
    assert snapshot.pot_read == pytest.approx(2.5)


def test_stored_frame_fixture_is_interpreted_from_snapshot(tmp_path):
    fixture = Path(__file__).parent / 'hu_parity' / 'testdata' / \
        'stored_frame.json'
    state = json.loads(fixture.read_text(encoding='utf-8'))
    assistant = _assistant(tmp_path)
    analysis = assistant.analyze(CapturedFrame(
        state=state, captured_at=datetime.now(timezone.utc).isoformat(),
        source='stored_frame'))

    snapshot = analysis.recorder_snapshot
    assert snapshot is not None and snapshot.processed
    assert snapshot.as_dict()['raw_state'] == state
    assert snapshot.hand is not None
    assert analysis.state.status == 'ready'
    assert analysis.state.interpretation_source == 'recorder_snapshot'


def test_live_default_view_keeps_recorder_btn_and_hu_sb_explicit(tmp_path):
    assistant = _assistant(tmp_path, parity_position_mode='live_default')
    analysis = assistant.analyze()
    snapshot = analysis.recorder_snapshot

    assert dict(snapshot.positions) == {'hero': 'BTN', 'p1': 'BB'}
    assert dict(snapshot.decision_view.hu_positions) == {
        'hero': 'SB', 'p1': 'BB'}
    assert analysis.state.hero_position == 'SB'
    assert 'position_mapping_live_btn_vs_hu_sb' in (
        analysis.uncertainty_reasons)


def test_finalized_hand_snapshot_keeps_final_pot_actions_and_street_contributions(
        tmp_path):
    assistant = _assistant(tmp_path)
    assert assistant.analyze().prediction is not None

    folded = _state(hero_state='retirarse', hero_bet=0.0)
    assistant.capture_adapter = HUCaptureAdapter(capture_fn=lambda: folded)
    analysis = assistant.analyze()
    snapshot = analysis.recorder_snapshot

    assert analysis.prediction is None
    assert analysis.canonical_reason == 'hand_finalized_during_capture_cycle'
    assert len(snapshot.finalized_hands) == 1
    assert snapshot.pot_read == pytest.approx(1.5)
    assert snapshot.pot_live_calculated == pytest.approx(1.5)
    assert snapshot.pot_final_calculated == pytest.approx(1.5)
    assert snapshot.contributions_by_street['preflop']['hero'] == pytest.approx(0.5)
    assert snapshot.contributions_by_street['preflop']['p1'] == pytest.approx(1.0)
    assert snapshot.actions_by_street['preflop']


def test_diagnostic_run_does_not_write_and_ledger_requires_explicit_record(
        tmp_path):
    before_hands = _hash(DATA_HANDS)
    before_decisions = _hash(DATA_DECISIONS)
    assistant = _assistant(
        tmp_path, parity_enable_live_decision_log=True)
    analysis = assistant.analyze()
    registration = assistant.register_analysis(analysis)
    recorder = assistant.engine.rec

    assert isinstance(recorder, SnapshotLiveRecorder)
    assert assistant.engine.decision_log.secondary is None
    recorder.finalize_hand(_state())
    assert recorder.finalized_hands
    # El outcome no se registra automaticamente al finalizar la mano.
    assistant._flush_post_capture_observations()
    assert [e['event_type'] for e in assistant.registry.read_events()] == [
        'HU_PREDICTION']

    assert not (tmp_path / 'hands_bridge.jsonl').exists()
    assert not (tmp_path / 'decisions_parity.jsonl').exists()
    assert not (tmp_path / 'ambiguedades').exists()
    assert recorder.suppressed_write_attempts
    assert _hash(DATA_HANDS) == before_hands
    assert _hash(DATA_DECISIONS) == before_decisions

    assistant.record_outcome(
        registration.prediction_id, observed_action='c',
        notes='registro explicito de prueba')
    assert [e['event_type'] for e in assistant.registry.read_events()] == [
        'HU_PREDICTION', 'HU_OUTCOME']
