"""Contratos del recorder en vivo contra el formato canonico de hands_db.

Cubre los defectos que la normalizacion tuvo que reparar a mano:

  - las ciegas se escriben como `p`, no como `b` con `blind: True`;
  - SB y BB se asignan por geometria de asientos, no por el importe que
    aparezca en la casilla de apuesta;
  - una apuesta que ya pertenece a la calle nueva no se graba en la vieja;
  - los checks que el autocompletado reconstruye por posición son inferidos,
    pero no ambiguos;
  - cada ambigüedad conserva la captura que la originó.
"""
import json
from pathlib import Path

import pytest

import recorder.recorder_live as rl
from recorder.recorder_live import LiveRecorder, PLAYER_IDS

POS = {'p1': 'BTN', 'p2': 'SB', 'p3': 'BB',
       'p4': 'UTG', 'p5': 'MP', 'hero': 'CO'}
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _sin_overrides(monkeypatch):
    monkeypatch.setattr(rl, 'MANUAL_INACTIVE', set())
    monkeypatch.setattr(rl, 'MANUAL_POSITIONS', {})
    monkeypatch.setattr(rl, 'MANUAL_CARDS', {})
    monkeypatch.setattr(rl, 'MANUAL_WINNER', None)


def _state(btn='p1', bets=None, stakes=None, states=None,
           community=None, pot=0.0):
    bets = bets or {}
    stakes = stakes or {}
    states = states or {}
    st = {'btn': btn, 'pot': pot, 'community': community or []}
    for p in PLAYER_IDS:
        st[f'{p}_state'] = states.get(p, 'activo')
        st[f'{p}_stake'] = stakes.get(p, 100.0)
        st[f'{p}_bet'] = bets.get(p, 0.0)
    return st


def _preflop_recorder():
    r = LiveRecorder()
    r.hand = {'hand_id': 'X', 'comunitarias': {}, 'streets': {
        s: {'actions': [], 'board': []}
        for s in ('preflop', 'flop', 'turn', 'river')}}
    r._hand_positions = dict(POS)
    return r



def test_sb_y_bb_por_asiento_aunque_mp_tenga_1_0():
    """Un MP con 1.0 en la casilla no puede robarle el BB al asiento real."""
    st = _state(btn='p1', bets={'p2': 1.0, 'p3': 0.5})
    pos = LiveRecorder()._assign_positions(st)
    assert pos['p2'] == 'SB'
    assert pos['p3'] == 'BB'


def test_sb_y_bb_saltan_asiento_vacio():
    """Con un asiento vacio entre BTN y SB, la geometria sigue mandando."""
    st = _state(btn='hero', bets={'p2': 1.0})
    st['p1_state'] = 'sin jugador'
    st['p1_stake'] = None
    pos = LiveRecorder()._assign_positions(st)
    assert pos['p2'] == 'SB'
    assert pos['p3'] == 'BB'


def test_inactivo_sin_ciega_visible_no_recibe_posicion_ni_post():
    st = _state(
        btn='p5',
        bets={'hero': 0.5, 'p2': 1.0},
        states={'p1': 'inactivo', 'p3': 'inactivo'},
    )
    r = LiveRecorder()
    r.hand_id = 0

    positions = r._assign_positions(st)
    r.start_hand(st)

    assert 'p1' not in positions
    assert positions['p2'] == 'BB'
    p1 = next(player for player in r.hand['players']
              if player['_id'] == 'p1')
    assert p1['active'] is False
    assert p1['pos'] == ''
    preflop = r.hand['streets']['preflop']['actions']
    assert _acts(preflop) == [('SB', 'p', 0.5), ('BB', 'p', 1.0)]


def test_inactivo_con_ciega_visible_conserva_posicion_y_post():
    st = _state(
        btn='p5',
        bets={'hero': 0.5, 'p1': 1.0},
        states={'p1': 'inactivo'},
    )
    r = LiveRecorder()
    r.hand_id = 0

    positions = r._assign_positions(st)
    r.start_hand(st)

    assert positions['p1'] == 'BB'
    assert ('BB', 'p', 1.0) in _acts(r.hand['streets']['preflop']['actions'])



def _acts(actions):
    return [(a['pos'], a['action'], a['amount']) for a in actions]


def test_preflop_emite_sb_y_bb_como_p():
    r = _preflop_recorder()
    st = _state(bets={'p2': 0.5, 'p3': 1.0, 'p4': 2.5})
    r._reconstruct_preflop(st)
    acts = r.hand['streets']['preflop']['actions']
    assert _acts(acts) == [
        ('SB', 'p', 0.5),
        ('BB', 'p', 1.0),
        ('UTG', 'r', 2.5),
    ], _acts(acts)
    assert all('blind' not in a for a in acts[:2])


def test_sb_que_completa_es_una_decision_despues_de_su_p():
    r = _preflop_recorder()
    st = _state(bets={'p2': 1.0, 'p3': 1.0, 'p4': 1.0})
    r._reconstruct_preflop(st)
    assert _acts(r.hand['streets']['preflop']['actions']) == [
        ('SB', 'p', 0.5),
        ('BB', 'p', 1.0),
        ('UTG', 'c', 1.0),
        ('SB', 'c', 1.0),
    ]


def test_bb_que_iguala_una_subida_guarda_su_importe_absoluto():
    r = _preflop_recorder()
    st = _state(bets={'p2': 0.5, 'p3': 2.5, 'p4': 2.5})
    r._reconstruct_preflop(st)
    assert _acts(r.hand['streets']['preflop']['actions']) == [
        ('SB', 'p', 0.5),
        ('BB', 'p', 1.0),
        ('UTG', 'r', 2.5),
        ('BB', 'c', 2.5),
    ]



def test_check_inferido_lleva_inferred_pero_no_ambiguous():
    r = _preflop_recorder()
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'BB', 'action': 'b', 'amount': 2.0, 'amount_type': 'delta'}]
    r._add_implied_checks('flop', _state())
    checks = [a for a in r.hand['streets']['flop']['actions']
              if a['action'] == 'x']
    assert checks, 'BB aposto: SB ha tenido que hablar antes'
    assert checks[0]['pos'] == 'SB'
    assert checks[0].get('inferred') is True
    # Los checks deducidos por posición son la única reconstrucción válida:
    # no son ambiguos, aunque se hayan inferido.
    assert checks[0].get('ambiguous') is False


def test_infiere_checks_anteriores_al_bet_aunque_stack_no_se_leyo():
    """Un bet de BTN no borra los checks previos de SB/MP por OCR faltante."""
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.hand['players'] = [
        {'_id': 'p1', 'pos': 'BTN', 'active': True},
        {'_id': 'p2', 'pos': 'SB', 'active': True},
        {'_id': 'p5', 'pos': 'MP', 'active': True},
    ]
    r._hand_positions = {'p1': 'BTN', 'p2': 'SB', 'p5': 'MP'}
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'BTN', 'action': 'b', 'amount': 1.9}]
    state = _state(bets={'p1': 1.9}, stakes={'p1': 90.0, 'p2': None,
                                           'p5': None},
                   states={'p2': 'inactivo', 'p5': 'inactivo'})

    r._add_implied_checks('flop', state)

    checks = {a['pos'] for a in r.hand['streets']['flop']['actions']
              if a['action'] == 'x'}
    assert checks == {'SB', 'MP'}



def _started():
    r = LiveRecorder()
    r.hand_id = 0
    r._assign_positions = lambda state: dict(POS)
    st = _state(btn='p1', bets={'p2': 0.5, 'p3': 1.0}, pot=1.5)
    r.start_hand(st)
    return r, st


def test_apuesta_del_board_nuevo_no_queda_en_la_calle_vieja():
    r, preflop = _started()

    limp = _state(btn='p1', bets={'p2': 0.5, 'p3': 1.0, 'p4': 2.5},
                  stakes={'p2': 99.5, 'p3': 99.0, 'p4': 97.5}, pot=3.5)
    r.process_frame(limp, None, log=lambda *a, **k: None)

    flop = _state(btn='p1', bets={'p2': 2.0},
                  stakes={'p2': 96.0, 'p3': 99.0, 'p4': 97.5},
                  pot=5.5,
                  community=[{'rank': '2', 'suit': 'h'},
                             {'rank': '7', 'suit': 'd'},
                             {'rank': '9', 'suit': 'c'}])
    r.process_frame(flop, None, log=lambda *a, **k: None)

    pre = _acts(r.hand['streets']['preflop']['actions'])
    flop_acts = _acts(r.hand['streets']['flop']['actions'])
    assert ('SB', 'b', 2.0) in flop_acts, flop_acts
    assert ('SB', 'b', 2.0) not in pre, pre


def test_sesion_de_prueba_guarda_frame_y_resultado_fuera_de_la_mano(tmp_path):
    output = tmp_path / 'resultados' / 'hands_db.jsonl'
    captures = tmp_path / 'capturas'
    r = LiveRecorder(str(output), str(captures), str(tmp_path), ['H_0141'])
    image = __import__('numpy').zeros((2, 2, 3), dtype='uint8')
    path = r.save_frame({'pot': 1.5}, image, log=lambda _: None)
    assert path and (captures / 'index.jsonl').exists()
    metadata = json.loads((captures / 'index.jsonl').read_text(encoding='utf-8'))
    assert metadata['seq'] == 1
    assert metadata['test_targets'] == ['H_0141']

    r.hand_id = 0
    r._assign_positions = lambda state: dict(POS)
    state = _state(btn='p1', bets={'p2': 0.5, 'p3': 1.0}, pot=1.5)
    r.start_hand(state)
    r._last_log = lambda _: None
    r.finalize_hand(state)
    assert output.exists()
    session_log = tmp_path / 'resultados' / 'registro_sesion.jsonl'
    assert json.loads(session_log.read_text(encoding='utf-8'))['test_targets'] == ['H_0141']


def test_ambiguedad_guarda_captura_causal_y_no_duplica(tmp_path):
    import numpy as np

    captures = tmp_path / 'ambiguedades'
    r = _preflop_recorder()
    r.hand['hand_id'] = 'H_EVIDENCIA'
    r.hand['current_street'] = 'flop'
    r.ambiguity_capture_dir = str(captures)
    r.ambiguity_index_path = str(captures / 'index.jsonl')
    r._ambiguity_frame_state = _state(pot=7.3)
    r._ambiguity_frame_img = np.zeros((4, 4, 3), dtype='uint8')
    r._last_log = lambda _msg: None

    r._add_ambiguity('pot_read_vs_contributions', 'flop', difference=0.7)
    r._add_ambiguity('pot_read_vs_contributions', 'flop', difference=0.8)

    row = r._hand_ambiguities[0]
    entries = [json.loads(x) for x in
               (captures / 'index.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(entries) == 1
    assert entries[0]['code'] == 'pot_read_vs_contributions'
    assert entries[0]['details']['difference'] == 0.7
    image = captures / entries[0]['frame']
    assert image.exists()
    assert entries[0]['sha256']


def test_apuestas_de_varios_frames_se_guardan_como_importes_absolutos():
    r, _ = _started()
    first = _state(
        bets={'p2': 0.5, 'p3': 1.0, 'p4': 2.0},
        stakes={'p2': 99.5, 'p3': 99.0, 'p4': 98.0}, pot=3.5)
    r.process_frame(first, None, log=lambda *a, **k: None)
    second = _state(
        bets={'p2': 0.5, 'p3': 1.0, 'p4': 4.0},
        stakes={'p2': 99.5, 'p3': 99.0, 'p4': 96.0}, pot=5.5)
    r.process_frame(second, None, log=lambda *a, **k: None)
    actions = [a for a in r.hand['streets']['preflop']['actions']
               if a['pos'] == 'UTG']
    assert [a['amount'] for a in actions] == [2.0, 4.0]
    assert all(a.get('amount_type') == 'observed' for a in actions)


def test_stack_deductions_with_inferred_bet_call_mark_order_ambiguous():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.last_state = _state(bets={}, stakes={})
    r.street_has_bet = False
    state = _state(
        bets={'p4': None, 'hero': None},
        stakes={'p4': 97.0, 'hero': 97.0})
    got = r.detect_actions(state)
    assert [(x[1], x[2], x[3]) for x in got] == [
        ('UTG', 'b', 3.0), ('CO', 'c', 3.0)]
    acts = r.hand['streets']['flop']['actions']
    inferred_bets = [a for a in acts if a['action'] in ('b', 'c', 'r')]
    assert all(a.get('inferred') and a.get('ambiguous')
               for a in inferred_bets)
    assert any(a['code'] == 'bet_call_order_inferred'
               for a in r._hand_ambiguities)


def test_bet_overlay_con_premio_no_se_registra_como_apuesta():
    r, _ = _started()
    r.last_state = _state(stakes={'p1': 100.0}, bets={})
    state = _state(stakes={'p1': 150.0}, bets={'p1': 150.0})
    assert r._detect_deltas(state) == []
    assert 'p1' in r._award_display_pids
    assert not any(a['pos'] == 'BTN' and a['action'] in ('b', 'c', 'r')
                   for a in r.hand['streets']['preflop']['actions'])


def test_premio_en_la_casilla_no_se_reutiliza_como_apuesta_de_mano_nueva():
    r, _ = _started()
    r._assign_positions = lambda _state: {'p1': 'UTG'}
    r.last_state = _state(stakes={'p1': 100.0}, bets={})
    payout_frame = _state(stakes={'p1': 150.0}, bets={'p1': 50.0})
    candidates = r._award_overlay_candidates(payout_frame)
    clean = r._without_award_bet_overlay(payout_frame, candidates)
    assert candidates['p1']['after'] == 150.0
    assert clean['p1_bet'] is None


def test_comision_solo_aplica_a_importes_igualados_y_calle_completada():
    r = _preflop_recorder()
    r.hand['current_street'] = 'preflop'
    r.hand['streets']['preflop']['actions'] = [
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 2.0},
        {'pos': 'BTN', 'action': 'c', 'amount': 2.0},
    ]
    # Sin flop no hay comisión, aunque existan aportes igualados.
    preflop_only = r._pot_breakdown(final=True, fold_win=True)
    assert preflop_only['rake'] == 0.0
    assert preflop_only['pot_calculated'] == 5.5

    r.hand['current_street'] = 'flop'
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 10.0},
        {'pos': 'BTN', 'action': 'c', 'amount': 10.0},
    ]
    r.hand['streets']['flop']['board'] = ['Ah', 'Kd', '2c']
    rake = r._pot_breakdown(final=True, fold_win=False)
    assert rake['rake_basis'] == 25.5
    assert rake['rake'] == 0.3
    assert rake['pot_calculated'] == 25.2


def test_raise_fold_conserva_excedente_en_bote_y_calcula_rake_sobre_igualado():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 10.0},
        {'pos': 'BTN', 'action': 'r', 'amount': 30.0},
        {'pos': 'UTG', 'action': 'f', 'amount': 0.0},
    ]
    r.hand['streets']['flop']['board'] = ['Ah', 'Kd', '2c']
    result = r._pot_breakdown(final=True, fold_win=True)
    assert result['gross_contributions'] == 40.0
    assert result['matched_contributions'] == 20.0
    assert result['uncalled'] == 20.0
    assert result['rake'] == 0.3
    assert result['pot_calculated'] == 39.7
    assert result['pot_calculated_noninflated'] == 19.7


def test_diferencia_de_bote_mayor_a_dos_decimas_se_marca_ambigua():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 5.0},
        {'pos': 'BTN', 'action': 'c', 'amount': 5.0},
    ]
    r._audit_live_pot(_state(pot=20.0))
    assert any(a['code'] == 'pot_read_vs_contributions'
               for a in r._hand_ambiguities)


def test_diferencia_apuesta_vs_stack_se_marca_y_prefiere_nivel_del_stack():
    r, _ = _started()
    r.last_state = _state(bets={'p4': 0.0}, stakes={'p4': 100.0})
    state = _state(bets={'p4': 3.5}, stakes={'p4': 97.0})
    got = r._detect_deltas(state)
    assert ('preflop', 'UTG', 'r', 3.0) in got
    assert any(a['code'] == 'bet_vs_stack_disagreement'
               and a['difference'] == 0.5 for a in r._hand_ambiguities)


def test_comision_tiene_tope_de_dos_y_medio_bb():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.hand['streets']['flop']['board'] = ['Ah', 'Kd', '2c']
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 100.0},
        {'pos': 'BTN', 'action': 'c', 'amount': 100.0},
    ]
    result = r._pot_breakdown(final=True, fold_win=False)
    assert result['rake_basis'] == 200.0
    assert result['rake'] == 0.3


def test_fold_lee_bote_no_inflado_pero_guarda_el_inflado_calculado(tmp_path):
    r = LiveRecorder(output_path=str(tmp_path / 'hands.jsonl'))
    r.hand_id = 0
    r._assign_positions = lambda _state: dict(POS)
    state = _state(btn='p1', stakes={p: 100.0 for p in PLAYER_IDS}, pot=24.23,
                   community=[{'rank': 'A', 'suit': 'h'},
                              {'rank': 'K', 'suit': 'd'},
                              {'rank': '2', 'suit': 'c'}])
    r.start_hand(state)
    r.hand['current_street'] = 'flop'
    r.hand['comunitarias']['flop'] = ['Ah', 'Kd', '2c']
    r.hand['streets']['flop']['board'] = ['Ah', 'Kd', '2c']
    r.hand['streets']['preflop']['actions'] = [
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 2.0},
        {'pos': 'BTN', 'action': 'c', 'amount': 2.0},
    ]
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 10.0},
        {'pos': 'BTN', 'action': 'r', 'amount': 30.0},
        {'pos': 'UTG', 'action': 'f', 'amount': 0.0},
    ]
    r._folded_positions.update({'UTG', 'SB', 'BB', 'CO', 'MP'})
    r.finalize_hand(state)
    saved = json.loads((tmp_path / 'hands.jsonl').read_text(encoding='utf-8'))
    assert saved['final_pot'] == 45.2
    assert saved['recorder_audit']['pot_read'] == 24.2
    assert saved['recorder_audit']['pot_resolution'] == 'ambiguous_read_mismatch'
    assert saved['recorder_audit']['ambiguous'] is True


def test_fold_win_conserva_la_apuesta_no_igualada_en_el_bote():
    """La devolucion de la apuesta no igualada no debe vaciar el bote final.

    H_1357: CO apuesta 8.8 en el river y SB foldea. La mesa devuelve el
    excedente al ganador, pero el bote historico debe seguir inflado e incluir
    esa apuesta; el bote en vivo si descuenta la devolucion.
    """
    r = _preflop_recorder()
    r.hand['current_street'] = 'river'
    r.hand['comunitarias'] = {'flop': ['6s', '2d', '8c'],
                              'turn': ['4d'], 'river': ['8s']}
    r.hand['streets']['preflop']['actions'] = [
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'MP', 'action': 'f', 'amount': 0.0},
        {'pos': 'CO', 'action': 'c', 'amount': 1.0},
        {'pos': 'BTN', 'action': 'f', 'amount': 0.0},
        {'pos': 'SB', 'action': 'c', 'amount': 1.0},
        {'pos': 'BB', 'action': 'x', 'amount': 0.0},
    ]
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'SB', 'action': 'x', 'amount': 0.0},
        {'pos': 'BB', 'action': 'x', 'amount': 0.0},
        {'pos': 'CO', 'action': 'b', 'amount': 1.5},
        {'pos': 'SB', 'action': 'c', 'amount': 1.5},
        {'pos': 'BB', 'action': 'f', 'amount': 0.0},
    ]
    r.hand['streets']['turn']['actions'] = [
        {'pos': 'SB', 'action': 'x', 'amount': 0.0},
        {'pos': 'CO', 'action': 'b', 'amount': 3.8},
        {'pos': 'SB', 'action': 'c', 'amount': 3.8},
    ]
    r.hand['streets']['river']['actions'] = [
        {'pos': 'SB', 'action': 'x', 'amount': 0.0},
        {'pos': 'CO', 'action': 'b', 'amount': 8.8},
        {'pos': 'SB', 'action': 'f', 'amount': 0.0},
    ]
    # La mesa devuelve los 8.8 no igualados al ganador (CO).
    r._returned_by_pos[('river', 'CO')] = 8.8

    bd = r._pot_breakdown(final=True, fold_win=True)

    assert bd['uncalled'] == 8.8
    assert bd['pot_calculated'] == 22.1
    assert bd['pot_calculated_noninflated'] == 13.3
    # El bote en vivo si descuenta la devolucion para casar con la mesa.
    assert bd['pot_live_calculated'] == 13.3


def test_call_pendiente_en_cambio_de_calle_no_se_suma_al_bet_nuevo():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.street_has_bet = True
    r._street_pot = 1.5
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 17.0,
         'amount_type': 'observed'}]

    flop = _state(btn='p1', bets={'p4': 17.0},
                  stakes={'p1': 100.0, 'p4': 83.0}, pot=18.5)
    turn = _state(btn='p1', bets={'p1': 28.0},
                  stakes={'p1': 55.0, 'p4': 83.0}, pot=63.5,
                  community=[{'rank': 'A', 'suit': 'h'},
                             {'rank': 'K', 'suit': 'd'},
                             {'rank': '2', 'suit': 'c'},
                             {'rank': '9', 'suit': 's'}])
    r.last_state = flop
    r.change_street('turn', turn, carryover=True)

    flop_acts = _acts(r.hand['streets']['flop']['actions'])
    assert ('BTN', 'c', 17.0) in flop_acts, flop_acts
    assert not any(pos == 'BTN' and act == 'f'
                   for pos, act, _amt in flop_acts)

    r.detect_actions(turn)
    turn_acts = _acts(r.hand['streets']['turn']['actions'])
    assert ('BTN', 'b', 28.0) in turn_acts, turn_acts
    assert not any(pos == 'BTN' and amt == 45.0
                   for pos, _act, amt in turn_acts)


def test_cierre_de_calle_no_inventa_calls_a_quien_foldeara_despues():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 17.0,
         'amount_type': 'observed'},
        {'pos': 'BTN', 'action': 'c', 'amount': 17.0,
         'amount_type': 'observed'}]
    r.hand['streets']['turn']['actions'] = [
        {'pos': 'BTN', 'action': 'b', 'amount': 28.0,
         'amount_type': 'observed'},
        {'pos': 'MP', 'action': 'f', 'amount': 0.0,
         'amount_type': 'observed'}]
    r._folded_positions.add('MP')

    r._finalize_street('flop', _state(btn='p1', pot=18.5))
    flop_pos = [a['pos'] for a in r.hand['streets']['flop']['actions']]
    assert 'MP' not in flop_pos, flop_pos
    assert not any(a['pos'] == 'MP' for a in r.hand['streets']['flop']['actions'])


def test_fold_en_cambio_de_calle_se_registra_en_la_calle_anterior():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 17.0,
         'amount_type': 'observed'}]

    flop = _state(btn='p1', bets={'p4': 17.0},
                  stakes={'p4': 83.0}, pot=18.5)
    turn = _state(btn='p1', stakes={'p4': 83.0}, pot=18.5,
                  states={'p5': 'retirarse'})
    r.last_state = flop
    r.change_street('turn', turn, carryover=True)

    flop_acts = _acts(r.hand['streets']['flop']['actions'])
    assert ('MP', 'f', 0.0) in flop_acts, flop_acts
    assert 'MP' in r._folded_positions
    assert not any(a['pos'] == 'MP'
                   for a in r.hand['streets']['turn']['actions'])


def test_fold_en_calle_nueva_no_se_adelanta_a_la_anterior():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 17.0,
         'amount_type': 'observed'}]

    flop = _state(btn='p1', bets={'p4': 17.0},
                  stakes={'p4': 83.0, 'p1': 100.0}, pot=18.5)
    turn = _state(btn='p1', stakes={'p4': 83.0, 'p1': 83.0}, pot=35.5,
                  states={'p1': 'retirarse'})
    r.hand['streets']['turn']['actions'] = [
        {'pos': pos, 'action': 'x', 'amount': 0.0}
        for pos in ('SB', 'BB', 'UTG', 'MP', 'CO')]
    r.last_state = flop
    r.change_street('turn', turn, carryover=True)

    flop_acts = _acts(r.hand['streets']['flop']['actions'])
    assert ('BTN', 'c', 17.0) in flop_acts, flop_acts
    assert not any(pos == 'BTN' and act == 'f'
                   for pos, act, _amt in flop_acts)
    assert 'BTN' not in r._folded_positions

    r.detect_actions(turn)
    turn_acts = _acts(r.hand['streets']['turn']['actions'])
    assert ('BTN', 'f', 0.0) in turn_acts, turn_acts


def test_calle_sin_capturas_se_reconstruye_y_no_infla_la_siguiente():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.street_has_bet = True
    r._street_pot = 1.5
    # No hay ninguna acción de flop capturada.
    flop = _state(btn='p1', stakes={'p4': 100.0, 'p1': 100.0}, pot=1.5)
    turn = _state(btn='p1', bets={'p4': 28.0, 'p1': 28.0},
                  stakes={'p4': 55.0, 'p1': 55.0}, pot=91.5,
                  community=[{'rank': 'A', 'suit': 'h'},
                             {'rank': 'K', 'suit': 'd'},
                             {'rank': '2', 'suit': 'c'},
                             {'rank': '9', 'suit': 's'}])
    r.last_state = flop
    r.change_street('turn', turn, carryover=True)

    flop_acts = _acts(r.hand['streets']['flop']['actions'])
    assert ('UTG', 'b', 17.0) in flop_acts, flop_acts
    assert ('BTN', 'c', 17.0) in flop_acts, flop_acts

    r.detect_actions(turn)
    turn_acts = _acts(r.hand['streets']['turn']['actions'])
    assert ('UTG', 'b', 28.0) in turn_acts, turn_acts
    assert ('BTN', 'c', 28.0) in turn_acts, turn_acts
    assert not any(amt == 45.0 for _pos, _act, amt in turn_acts), turn_acts


def _live_started(path):
    r = LiveRecorder(output_path=str(path))
    r.hand_id = 0
    r._assign_positions = lambda state: dict(POS)
    st = _state(btn='p1', bets={'p2': 0.5, 'p3': 1.0}, pot=1.5)
    r.start_hand(st)
    return r


def test_no_arranca_mano_fantasma_mientras_queda_el_board_anterior(tmp_path):
    r = _live_started(tmp_path / 'hands.jsonl')
    flop = _state(bets={}, pot=1.5, community=[
        {'rank': '4', 'suit': 'h'}, {'rank': '6', 'suit': 's'},
        {'rank': '8', 'suit': 'd'}])
    r.process_frame(flop, None, log=lambda *a, **k: None)
    r.finalize_hand(flop)
    assert r.hand is None

    r.process_frame(flop, None, log=lambda *a, **k: None)
    assert r.hand is None

    new = _state(btn='p2', bets={'p1': 0.5, 'p2': 1.0}, pot=1.5)
    r.process_frame(new, None, log=lambda *a, **k: None)
    assert r.hand is not None
    assert r.hand['hand_id'] == 'H_0002'
    assert r.hand['comunitarias']['flop'] == []


def test_checks_de_flop_se_registran_sin_esperar_al_turn(tmp_path):
    r = _live_started(tmp_path / 'hands.jsonl')
    flop = _state(bets={}, pot=1.5, community=[
        {'rank': 'A', 'suit': 'h'}, {'rank': 'K', 'suit': 'd'},
        {'rank': '2', 'suit': 'c'}])
    r.process_frame(flop, None, log=lambda *a, **k: None)
    r.process_frame(flop, None, log=lambda *a, **k: None)

    checks = {a['pos'] for a in r.hand['streets']['flop']['actions']
              if a['action'] == 'x'}
    assert checks == set(POS.values())


def test_allin_no_inventa_checks_al_que_todavia_tiene_stack(tmp_path):
    r = _live_started(tmp_path / 'hands.jsonl')
    for pos in ('UTG', 'MP', 'CO', 'BTN'):
        r._folded_positions.add(pos)
    r._allin_players.add('p2')
    flop = _state(bets={}, pot=1.5, states={'p2': 'apostar todo'},
                  community=[{'rank': 'A', 'suit': 'h'},
                             {'rank': 'K', 'suit': 'd'},
                             {'rank': '2', 'suit': 'c'}])
    r.process_frame(flop, None, log=lambda *a, **k: None)
    r.process_frame(flop, None, log=lambda *a, **k: None)

    flop_actions = r.hand['streets']['flop']['actions']
    assert not any(a['action'] == 'x' for a in flop_actions), flop_actions


def test_victoria_por_fold_completa_los_folds_que_faltaban(tmp_path):
    out = tmp_path / 'hands.jsonl'
    r = _live_started(out)
    final = _state(bets={}, pot=1.5, states={
        'p1': 'retirarse', 'p2': 'retirarse', 'p4': 'retirarse',
        'p5': 'inactivo', 'hero': 'retirarse'})
    r.finalize_hand(final)
    saved = json.loads(out.read_text(encoding='utf-8'))
    assert saved['winner'] == ['p3']
    assert saved['recorder_audit']['fold_win'] is True
    folds = {a['pos'] for a in saved['streets']['preflop']['actions']
             if a['action'] == 'f'}
    assert folds == {'SB', 'UTG', 'MP', 'CO', 'BTN'}


def test_preflop_no_registra_call_por_debajo_de_la_apuesta_viva():
    r = _preflop_recorder()
    st = _state(bets={'p2': 1.0, 'p3': 1.0, 'p4': 2.5, 'p1': 2.5},
                stakes={'p2': 99.5, 'p3': 99.0, 'p4': 97.5, 'p1': 97.5})
    r._reconstruct_preflop(st)
    acts = _acts(r.hand['streets']['preflop']['actions'])
    assert ('SB', 'c', 1.0) not in acts, acts
    assert any(a['code'] == 'preflop_bet_below_live_bet'
               for a in r._hand_ambiguities)


def test_inactivo_despues_de_apostar_no_es_fold():
    r = _preflop_recorder()
    r.hand['current_street'] = 'river'
    r.hand['streets']['river']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 10.4}]
    r.last_state = _state(bets={'p4': 10.4}, stakes={'p4': 89.6}, pot=12.0)
    dimmed = _state(bets={'p4': 10.4}, stakes={'p4': 89.6}, pot=12.0,
                    states={'p4': 'inactivo'})
    dimmed_actions = r._detect_deltas(dimmed)
    assert not any(a[2] == 'f' for a in dimmed_actions)

    # Ahora sí hay una subida de BB a 20; UTG es el siguiente en responder.
    folded = _state(bets={'p4': 10.4, 'p3': 20.0},
                    stakes={'p4': 89.6, 'p3': 80.0}, pot=32.0,
                    states={'p4': 'retirarse'})
    r.last_state = _state(bets={'p4': 10.4, 'p3': 10.4},
                          stakes={'p4': 89.6, 'p3': 89.6}, pot=22.4)
    folded_actions = r._detect_deltas(folded)
    assert ('river', 'UTG', 'f', 0.0) in folded_actions


def test_agresor_no_puede_foldear_despues_de_que_el_rival_se_retire():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.hand['players'] = [
        {'_id': pid, 'pos': pos, 'active': True}
        for pid, pos in POS.items()]
    # La mano ya se redujo a UTG contra CO; CO foldeó ante la apuesta de UTG.
    r._folded_positions.update({'BTN', 'SB', 'BB', 'MP'})
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'CO', 'action': 'f', 'amount': 0.0}]
    # La lectura del bet desaparece en el frame oscuro y la acción todavía
    # no llegó a persistirse: el frame previo conserva que UTG apostó 5.5.
    previous = _state(bets={'p4': 5.5}, stakes={'p4': 94.5}, pot=7.3)
    r.last_state = previous
    dimmed = _state(stakes={'p4': 94.5}, states={
        'p1': 'retirarse', 'p2': 'retirarse', 'p3': 'retirarse',
        'p4': 'inactivo', 'p5': 'retirarse', 'hero': 'retirarse'}, pot=7.3)

    detected = r._detect_deltas(dimmed)
    assert not any(a[1] == 'UTG' and a[2] == 'f' for a in detected)
    assert 'p4' in [p['_id'] for p in r._survivors(dimmed)]
    r._complete_missing_folds(dimmed)
    assert not any(a['pos'] == 'UTG' and a['action'] == 'f'
                   for a in r.hand['streets']['flop']['actions'])

def test_fold_inferido_es_valido_si_el_agresor_reabre_la_apuesta():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.hand['players'] = [
        {'_id': pid, 'pos': pos, 'active': True}
        for pid, pos in POS.items()]
    r._folded_positions.update({'BTN', 'SB', 'BB', 'MP'})
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 5.5},
        {'pos': 'CO', 'action': 'r', 'amount': 15.0},
    ]
    r.last_state = _state(bets={'p4': 5.5, 'hero': 15.0},
                          stakes={'p4': 94.5, 'hero': 85.0}, pot=22.3)
    dimmed = _state(bets={'p4': 5.5, 'hero': 15.0},
                    stakes={'p4': 94.5, 'hero': 85.0},
                    states={'p4': 'inactivo'}, pot=22.3)

    detected = r._detect_deltas(dimmed)
    assert ('flop', 'UTG', 'f', 0.0) in detected


def test_fold_inferido_al_cerrar_es_inferido_pero_no_ambiguo():
    """Un fold que la mesa ya aplicó no es una duda que requiera revisión."""
    r = _preflop_recorder()
    r.hand['current_street'] = 'river'
    r.hand['players'] = [
        {'_id': 'p1', 'pos': 'BTN', 'active': True},
        {'_id': 'p3', 'pos': 'BB', 'active': True},
    ]
    r._hand_positions = {'p1': 'BTN', 'p3': 'BB'}
    r.hand['streets']['river']['actions'] = [
        {'pos': 'BTN', 'action': 'b', 'amount': 5.0},
    ]
    state = _state(btn='p1', states={'p3': 'retirarse'},
                   stakes={'p1': 95.0, 'p3': 100.0})

    r._complete_missing_folds(state)

    folds = [a for a in r.hand['streets']['river']['actions']
             if a['action'] == 'f' and a['pos'] == 'BB']
    assert len(folds) == 1
    assert folds[0].get('inferred') is True
    assert 'ambiguous' not in folds[0]
    assert not any(x.get('code') == 'fold_missing_at_close'
                   for x in r._hand_ambiguities)


def test_bb_check_inferido_tras_limps_no_es_ambiguo():
    """La opción del BB tras los limps es una regla, no una duda."""
    r = _preflop_recorder()
    r.hand['current_street'] = 'preflop'
    r.hand['players'] = [
        {'_id': pid, 'pos': pos, 'active': True} for pid, pos in POS.items()]
    r.hand['streets']['preflop']['actions'] = [
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
        {'pos': 'MP', 'action': 'c', 'amount': 1.0},
        {'pos': 'SB', 'action': 'c', 'amount': 1.0},
    ]

    r._finalize_street('preflop', _state(btn='p1'))

    checks = [a for a in r.hand['streets']['preflop']['actions']
              if a['action'] == 'x' and a['pos'] == 'BB']
    assert len(checks) == 1
    assert checks[0].get('inferred') is True
    assert 'ambiguous' not in checks[0]


def test_ganador_manual_no_foldea_a_un_jugador_que_sigue_activo(
        monkeypatch):
    """Ganar a mano no implica que el rival haya abandonado: pudo showdown."""
    monkeypatch.setattr(rl, 'MANUAL_WINNER', ['p3'])
    r = _preflop_recorder()
    r.hand['current_street'] = 'river'
    r.hand['players'] = [
        {'_id': 'p3', 'pos': 'BB', 'active': True},
        {'_id': 'p2', 'pos': 'MP', 'active': True},
    ]
    r._hand_positions = {'p3': 'BB', 'p2': 'MP'}
    r.hand['streets']['river']['actions'] = [
        {'pos': 'BB', 'action': 'b', 'amount': 4.5},
        {'pos': 'MP', 'action': 'r', 'amount': 10.0},
        {'pos': 'BB', 'action': 'c', 'amount': 10.0},
    ]

    r._complete_missing_folds(
        _state(btn='p1', states={'p2': 'activo', 'p3': 'activo'}))

    assert not any(a['action'] == 'f' and a['pos'] == 'MP'
                   for a in r.hand['streets']['river']['actions'])


def test_aviso_de_mesa_no_se_resta_como_devolucion_en_showdown(
        monkeypatch):
    """Un salto de stack con dos jugadores vivos es premio, no devolución."""
    monkeypatch.setattr(rl, 'RAKE_RATE', 0.05)
    monkeypatch.setattr(rl, 'RAKE_CAP_BB', 2.5)
    r = _preflop_recorder()
    r.hand['current_street'] = 'river'
    r._hand_positions = {'p3': 'BB', 'p2': 'MP'}
    r.hand['comunitarias'] = {'flop': ['Ks', 'Kd', '5s'],
                              'turn': ['8c'], 'river': ['3d']}
    r.hand['streets']['preflop']['actions'] = [
        {'pos': 'SB', 'action': 'p', 'amount': 0.5},
        {'pos': 'BB', 'action': 'p', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
        {'pos': 'MP', 'action': 'c', 'amount': 1.0},
        {'pos': 'SB', 'action': 'c', 'amount': 1.0},
    ]
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'BB', 'action': 'b', 'amount': 1.9},
        {'pos': 'MP', 'action': 'c', 'amount': 1.9},
    ]
    r.hand['streets']['turn']['actions'] = [
        {'pos': 'BB', 'action': 'b', 'amount': 5.6},
        {'pos': 'MP', 'action': 'c', 'amount': 5.6},
    ]
    r.hand['streets']['river']['actions'] = [
        {'pos': 'BB', 'action': 'b', 'amount': 4.5},
        {'pos': 'MP', 'action': 'r', 'amount': 10.0},
        {'pos': 'BB', 'action': 'c', 'amount': 10.0},
    ]
    retirados = {'p1': 'retirarse', 'p4': 'retirarse',
                 'p5': 'retirarse', 'hero': 'retirarse'}
    r.last_state = _state(bets={'p2': 10.0},
                          stakes={'p2': 40.5, 'p3': 86.6},
                          states=retirados)
    state = _state(bets={'p2': 0.0},
                   stakes={'p2': 48.5, 'p3': 86.6},
                   states=retirados)

    r._detect_deltas(state)

    assert r._returned_by_pos == {}
    bd = r._pot_breakdown(final=True, fold_win=False)
    assert bd['gross_contributions'] == 39.0
    assert bd['matched_contributions'] == 39.0
    assert bd['uncalled'] == 0.0
    assert bd['rake'] == 1.95
    assert bd['pot_calculated'] == 37.1


def test_showdown_no_genera_folds_aunque_el_ganador_sea_manual(monkeypatch):
    """En un showdown el juego atenua a los perdedores; no son folds."""
    monkeypatch.setattr(rl, 'MANUAL_WINNER', ['p2'])
    r = _preflop_recorder()
    r.hand['current_street'] = 'river'
    r.hand['players'] = [
        {'_id': 'p1', 'pos': 'BTN', 'active': True},
        {'_id': 'p2', 'pos': 'BB', 'active': True},
    ]
    r._hand_positions = {'p1': 'BTN', 'p2': 'BB'}
    r.hand['streets']['river']['actions'] = [
        {'pos': 'BTN', 'action': 'b', 'amount': 4.4},
        {'pos': 'BB', 'action': 'r', 'amount': 17.7},
    ]

    r._complete_missing_folds(
        _state(btn='p1', states={'p1': 'activo', 'p2': 'activo'}))

    assert not any(a['action'] == 'f'
                   for d in r.hand['streets'].values()
                   for a in d.get('actions', []))
    r.hand_id = 0
    r._assign_positions = lambda state: dict(POS)
    state = _state(bets={'p2': 0.5, 'p3': 1.0},
                   states={'p1': 'inactivo'})  # BTN, antes actúan UTG/MP/CO

    r.start_hand(state)

    assert not any(a['pos'] == 'BTN' and a['action'] == 'f'
                   for a in r.hand['streets']['preflop']['actions'])


def test_allin_preflop_no_genera_checks_postflop():
    r = _preflop_recorder()
    r.hand_id = 1
    r.hand['current_street'] = 'flop'
    r.hand['players'] = [
        {'_id': 'p2', 'pos': 'SB', 'active': True},
        {'_id': 'p4', 'pos': 'UTG', 'active': True},
    ]
    r._allin_players.add('p4')
    r._folded_positions.update({'BB', 'CO', 'BTN', 'MP'})
    flop = _state(states={'p2': 'activo', 'p4': 'apostar todo'},
                  community=[{'rank': 'A', 'suit': 'h'},
                             {'rank': 'K', 'suit': 'd'},
                             {'rank': '2', 'suit': 'c'}])
    r.last_state = flop
    r.process_frame(flop, None, log=lambda *a, **k: None)
    flop_actions = r.hand['streets']['flop']['actions']
    assert not any(a['action'] == 'x' for a in flop_actions), flop_actions


def test_stack_none_sin_etiqueta_no_se_convierte_en_allin():
    r = _preflop_recorder()
    r.hand['current_street'] = 'preflop'
    r.last_state = _state(stakes={'p4': 100.0}, bets={'p4': 0.0})
    missing = _state(stakes={'p4': None}, bets={'p4': None})
    r._detect_deltas(missing)
    assert 'p4' not in r._allin_players

    zero_bet = _state(stakes={'p4': None}, bets={'p4': 0.0})
    r._detect_deltas(zero_bet)
    assert 'p4' not in r._allin_players

    allin = _state(stakes={'p4': None}, bets={'p4': None},
                   states={'p4': 'apostar todo'})
    r._detect_deltas(allin)
    assert 'p4' in r._allin_players


def test_no_arranca_si_el_boton_no_tiene_stack_visible():
    st = _state(btn='p1')
    st['p1_stake'] = None
    assert LiveRecorder()._can_start_hand(st, log=lambda *a, **k: None) is False


def test_calle_parcialmente_capturada_no_duplica_la_apuesta():
    r = _preflop_recorder()
    r.hand['current_street'] = 'flop'
    r.street_has_bet = True
    r._street_pot = 1.5
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'UTG', 'action': 'b', 'amount': 17.0,
         'amount_type': 'observed'}]
    flop = _state(btn='p1', bets={'p4': 17.0},
                  stakes={'p4': 83.0, 'p1': 100.0}, pot=18.5)
    turn = _state(btn='p1', bets={'p4': 28.0, 'p1': 28.0},
                  stakes={'p4': 55.0, 'p1': 55.0}, pot=91.5,
                  community=[{'rank': 'A', 'suit': 'h'},
                             {'rank': 'K', 'suit': 'd'},
                             {'rank': '2', 'suit': 'c'},
                             {'rank': '9', 'suit': 's'}])
    r.last_state = flop
    r.change_street('turn', turn, carryover=True)

    flop_acts = _acts(r.hand['streets']['flop']['actions'])
    assert flop_acts.count(('UTG', 'b', 17.0)) == 1, flop_acts
    assert ('BTN', 'c', 17.0) in flop_acts, flop_acts

    r.detect_actions(turn)
    turn_acts = _acts(r.hand['streets']['turn']['actions'])
    assert ('UTG', 'b', 28.0) in turn_acts, turn_acts
    assert ('BTN', 'c', 28.0) in turn_acts, turn_acts
