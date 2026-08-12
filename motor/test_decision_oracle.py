"""Tests: OracleResponse -> capa de EV (decision.py + behavior.Oracle)."""
import pytest

from motor.behavior import Oracle, build
from motor.decision import OracleResponse, compute_evs, default_response

AH = ['As', 'Kd']
DRY_BOARD = ['3d', '6d', '9s']


def _street(actions, board=None):
    d = {'actions': actions}
    if board:
        d['board'] = board
    return d


def _hand(hid):
    return {
        'hand_id': hid,
        'players': [
            {'pos': 'BTN', 'name': 'X', 'stack': 100, 'cards': ''},
            {'pos': 'BB', 'name': 'Y', 'stack': 100, 'cards': ''},
        ],
        'streets': {
            'preflop': _street([
                {'pos': 'BTN', 'action': 'b', 'amount': 2.0},
                {'pos': 'BB', 'action': 'c', 'amount': 2.0},
            ]),
            'flop': _street([
                {'pos': 'BTN', 'action': 'b', 'amount': 4.0},
                {'pos': 'BB', 'action': 'f', 'amount': 0.0},
            ], board=DRY_BOARD),
        },
    }


def _oracle(n=20):
    labels = {'X': 'Foldy', 'Y': 'LAG'}
    data = build([_hand(f'H{i:03d}') for i in range(n)],
                 labels=labels, min_n=n)
    return Oracle(data), labels


def test_alpha_cero_con_perfil_sin_celda():
    oracle, _ = _oracle()
    resp = OracleResponse(oracle, 'Otro', ('flop', 'cbet', 'two_tone'))
    assert resp.source == 'poblacion'          # desconocido -> población
    assert resp.alpha == 0.0                   # sin n -> heurística pura
    pf, pc, pr = resp([0.5], 50.0, 100.0)
    pf_d, pc_d, pr_d = default_response(0.5, 50.0, 100.0)
    assert pf == pytest.approx(pf_d)
    assert pc == pytest.approx(pc_d)
    assert pr == pytest.approx(pr_d)


def test_perfil_foldero_se_usa_en_el_ev():
    oracle, labels = _oracle()
    # celda (LAG, flop, facing cbet, textura two_tone): granular n=20, f=1.0
    resp = OracleResponse(oracle, 'LAG', ('flop', 'cbet', 'two_tone'))
    assert resp.source == 'granular'
    assert resp.alpha == 1.0
    assert resp.pf_p > 0.9

    ev_def = compute_evs(AH, DRY_BOARD, pot=100.0, stack=50.0)
    ev_perf = compute_evs(AH, DRY_BOARD, pot=100.0, stack=50.0,
                          response_fn=resp)
    assert ev_perf.ev['bet_50'] > ev_def.ev['bet_50']


def test_ev_con_respuesta_perfil_coherente():
    oracle, labels = _oracle()
    resp = OracleResponse(oracle, 'LAG', ('flop', 'cbet', 'two_tone'))
    table = compute_evs(AH, DRY_BOARD, pot=100.0, stack=50.0,
                        response_fn=resp)
    # con fold 100% el EV de cualquier bet = pot asegurado
    for label in ('bet_25', 'bet_50', 'bet_75'):
        assert table.ev[label] >= 99.0


def test_response_firma_igual_que_default():
    oracle, labels = _oracle()
    resp = OracleResponse(oracle, 'LAG', ('flop', 'cbet', 'two_tone'))
    pf, pc, pr = resp([0.5, 0.7], 50.0, 100.0)
    assert pf.shape == (2,) and pc.shape == (2,) and pr.shape == (2,)
    assert (pf + pc + pr).max() <= 1.0 + 1e-9