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
    r.hand = {'hand_id': 'X', 'streets': {
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
                  stakes={'p2': 97.5, 'p3': 99.0, 'p4': 97.5},
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
