"""Contratos del recorder en vivo contra el formato canonico de hands_db.

Cubre los defectos que la normalizacion tuvo que reparar a mano:

  - las ciegas se escriben como `p`, no como `b` con `blind: True`;
  - SB y BB se asignan por geometria de asientos, no por el importe que
    aparezca en la casilla de apuesta;
  - una apuesta que ya pertenece a la calle nueva no se graba en la vieja;
  - los checks que el autocompletado inventa quedan marcados como inferidos
    y ambiguos.
"""
import json

import pytest

import recorder.recorder_live as rl
from recorder.recorder_live import LiveRecorder, PLAYER_IDS

POS = {'p1': 'BTN', 'p2': 'SB', 'p3': 'BB',
       'p4': 'UTG', 'p5': 'MP', 'hero': 'CO'}


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



def test_check_inferido_lleva_inferred_y_ambiguous():
    r = _preflop_recorder()
    r.hand['streets']['flop']['actions'] = [
        {'pos': 'BB', 'action': 'b', 'amount': 2.0, 'amount_type': 'delta'}]
    r._add_implied_checks('flop', _state())
    checks = [a for a in r.hand['streets']['flop']['actions']
              if a['action'] == 'x']
    assert checks, 'BB aposto: SB ha tenido que hablar antes'
    assert checks[0]['pos'] == 'SB'
    assert checks[0].get('inferred') is True
    assert checks[0].get('ambiguous') is True



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
    assert rake['rake'] == 1.28
    assert rake['pot_calculated'] == 24.23


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
    assert result['rake'] == 1.0
    assert result['pot_calculated'] == 39.0
    assert result['pot_calculated_noninflated'] == 19.0


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
    assert result['rake'] == 2.5


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
    assert saved['final_pot'] == 44.23
    assert saved['recorder_audit']['pot_read'] == 24.23
    assert saved['recorder_audit']['pot_resolution'] == 'read_noninflated_to_inflated'
    assert saved['recorder_audit']['ambiguous'] is False


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
    r.last_state = _state(bets={'p4': 10.4}, stakes={'p4': 89.6}, pot=12.0)
    dimmed = _state(bets={'p4': 10.4}, stakes={'p4': 89.6}, pot=12.0,
                    states={'p4': 'inactivo'})
    dimmed_actions = r._detect_deltas(dimmed)
    assert not any(a[2] == 'f' for a in dimmed_actions)

    folded = _state(bets={'p4': 10.4}, stakes={'p4': 89.6}, pot=12.0,
                    states={'p4': 'retirarse'})
    folded_actions = r._detect_deltas(folded)
    assert ('river', 'UTG', 'f', 0.0) in folded_actions


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
