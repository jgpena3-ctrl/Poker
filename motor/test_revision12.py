# -*- coding: utf-8 -*-
"""Regresiones de los tres puntos que ambas revisiones marcaron.

  P1 - squeeze: la condicion debe ser `callers >= 1`, sin `limps_before`.
  P2 - `_pf_rival_pos`: un 'b' posterior a un 'r' no se pierde.
  P3 - `_reconstruct_preflop`: la accion voluntaria del BB no se pierde.

P1 vive en `test_orden_preflop.py` (no necesita cv2). P2 y P3 van aqui porque
`asistente_live` y `recorder_live` importan cv2.
"""
import sys
import types

import pytest

from motor import learn


# ---------------------------------------------------------------------------
# P1 - squeeze (sin cv2)
# ---------------------------------------------------------------------------

def test_p1_squeeze_no_usa_limps_before():
    """Un limp anterior al open NO convierte en squeeze el 3bet posterior."""
    assert learn.classify_first_action('r', 4.0, 1, 1, callers=0) == \
        ('3bet', 'facing_open')
    assert learn.classify_first_action('r', 4.0, 1, 0, callers=1) == \
        ('squeeze', 'facing_open')


def test_p1_cero_squeezes_falsos_en_las_900():
    """Ningun squeeze puede tener callers == 0."""
    malos = 0
    for h in learn.load_hands(reliable_only=True):
        seq = learn._preflop_sequence(h)
        raises = limps = callers = 0
        voluntary = False
        for i, (pos, act, amt, blind) in enumerate(seq):
            if learn._es_ciega_bb(i, pos, act, amt, blind, voluntary):
                continue
            cat, _ = learn.classify_first_action(act, amt, raises, limps,
                                                 learn.BB, callers)
            if act in ('b', 'r') and raises == 1:
                if cat == 'squeeze' and callers == 0:
                    malos += 1
            if act in ('b', 'r'):
                raises += 1
                voluntary = True
            elif act == 'c':
                if raises == 0:
                    limps += 1
                else:
                    callers += 1
                voluntary = True
    assert malos == 0, '%d squeezes sin caller real' % malos


# ---------------------------------------------------------------------------
# P2 - _pf_rival_pos (requiere cv2)
# ---------------------------------------------------------------------------

def test_p2_b_tras_raise_no_se_pierde():
    """revision_2 §2: un 'b' posterior a un 'r' no debe perderse."""
    pytest.importorskip('cv2')
    from motor.asistente_live import _pf_rival_pos
    h = {'streets': {'preflop': {'actions': [
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},   # open
        {'pos': 'MP', 'action': 'c', 'amount': 2.5},    # call -> 1er agresor UTG
        {'pos': 'CO', 'action': 'b', 'amount': 1.0},    # b<=BB DESPUES del call
        {'pos': 'BTN', 'action': 'c', 'amount': 2.5},
    ]}}}
    # CO cuenta como agresor pese a ser <=BB: ya hubo accion previa
    # facing_open -> primer agresor real (UTG); facing_3bet -> segundo (CO)
    assert _pf_rival_pos(h, 'BTN', 'facing_open') == 'UTG'
    assert _pf_rival_pos(h, 'BTN', 'facing_3bet') == 'CO'


def test_p2_b_antes_de_cualquier_raise_si_se_descarta():
    """Sin subida previa, un 'b' de <=BB sigue siendo limpe y no cuenta."""
    pytest.importorskip('cv2')
    from motor.asistente_live import _pf_rival_pos
    h = {'streets': {'preflop': {'actions': [
        {'pos': 'MP', 'action': 'b', 'amount': 1.0},    # limpe
        {'pos': 'CO', 'action': 'b', 'amount': 3.0},    # open
        {'pos': 'BTN', 'action': 'c', 'amount': 3.0},
    ]}}}
    assert _pf_rival_pos(h, 'BTN', 'facing_open') == 'CO'


# ---------------------------------------------------------------------------
# P3 - _reconstruct_preflop recupera la accion voluntaria del BB
# ---------------------------------------------------------------------------

def test_p3_el_bb_no_pierde_su_accion_voluntaria():
    """revision_2 §3: la rama del BB hacia continue y perdia su call/raise."""
    pytest.importorskip('cv2')          # el modulo real necesita cv2
    from recorder.recorder_live import LiveRecorder
    r = LiveRecorder()
    r._blind_bb = 1.0
    r._blinds_by_pos = {}
    r.hand = {'hand_id': 'X', 'streets': {
        'preflop': {'actions': []}, 'flop': {'actions': []},
        'turn': {'actions': []}, 'river': {'actions': []}}}

    pos_map = {'UTG': 'p1', 'MP': 'p2', 'CO': 'p3',
               'BTN': 'p4', 'SB': 'p5', 'BB': 'p6'}

    def _get_pos_map(_state):
        return dict(pos_map)

    r._get_pos_map = _get_pos_map

    state = {
        'p1_bet': 2.5, 'p1_state': 'activo',
        'p2_bet': 2.5, 'p2_state': 'activo',
        'p3_bet': 0.0, 'p3_state': 'retirarse',
        'p4_bet': 0.0, 'p4_state': 'retirarse',
        'p5_bet': 0.0, 'p5_state': 'retirarse',
        'p6_bet': 2.5, 'p6_state': 'activo',   # el BB PAGA la subida
    }
    r._reconstruct_preflop(state)

    acts = r.hand['streets']['preflop']['actions']
    bb = [(a['action'], a['amount']) for a in acts if a['pos'] == 'BB']
    assert ('b', 1.0) in bb, 'la ciega del BB debe registrarse'
    assert any(act == 'c' and amt >= 2.5 for act, amt in bb), \
        'el call voluntario del BB se ha perdido: %s' % (bb,)