"""test_db_health.py — validación de ingesta y health-check (db_health.py)."""
import json

from motor import db_health as dh


def _hand(hid, players=None, streets=None, **over):
    h = {
        'hand_id': hid,
        'players': players or [
            {'pos': 'BTN', 'name': 'Hero', 'stack': 100, 'cards': 'JdJh'},
            {'pos': 'BB', 'name': 'Rival', 'stack': 100, 'cards': ''},
        ],
        'streets': streets or {'preflop': {'actions': [
            {'pos': 'BTN', 'action': 'b', 'amount': 2.0},
            {'pos': 'BB', 'action': 'c', 'amount': 2.0}]}},
    }
    h.update(over)
    return h


def _flop_street(board):
    return {'preflop': {'actions': [
        {'pos': 'BTN', 'action': 'b', 'amount': 2.0},
        {'pos': 'BB', 'action': 'c', 'amount': 2.0}]},
        'flop': {'board': board, 'actions': [
            {'pos': 'BTN', 'action': 'b', 'amount': 3.0},
            {'pos': 'BB', 'action': 'f', 'amount': 0.0}]}}


def test_validate_sana():
    v = dh.validate_hands([_hand('A1', streets=_flop_street(['Qh', '7s', '2c'])),
                           _hand('A2', streets=_flop_street(['5h', '6d', '4d']))])
    assert v['n_hands'] == 2
    assert v['n_hands_con_board'] == 2
    assert not any(v['issues'].values())


def test_validate_dup_board():
    v = dh.validate_hands([_hand('B1', streets=_flop_street(['Js', '2c', '2c']))])
    assert v['issues']['dup_board'] == 1
    assert v['examples']['dup_board'][0]['hand_id'] == 'B1'


def test_validate_carta_repetida_turn():
    h = _hand('C1', streets={
        'preflop': {'actions': [{'pos': 'BTN', 'action': 'b', 'amount': 2.0},
                                {'pos': 'BB', 'action': 'c', 'amount': 2.0}]},
        'flop': {'board': ['Qh', '7s', '2c'], 'actions': [
            {'pos': 'BTN', 'action': 'b', 'amount': 3.0},
            {'pos': 'BB', 'action': 'c', 'amount': 3.0}]},
        'turn': {'board': ['Qh'], 'actions': [
            {'pos': 'BB', 'action': 'b', 'amount': 3.0},
            {'pos': 'BTN', 'action': 'c', 'amount': 3.0}]}})
    v = dh.validate_hands([h])
    assert v['issues']['carta_repetida'] == 1


def test_validate_flop_corto_y_hand_id_dup():
    h1 = _hand('D1', streets=_flop_street(['5d']))
    v = dh.validate_hands([h1, h1])
    assert v['issues']['flop_corto'] == 1
    assert v['issues']['hand_id_dup'] == 1
    assert v['n_hands'] == 2


def test_validate_pos_desconocida_y_amount():
    h1 = _hand('E1', streets={
        'preflop': {'actions': [{'pos': 'SB', 'action': 'b', 'amount': 2.0},
                                {'pos': 'BB', 'action': 'c', 'amount': 2.0}]}})
    h2 = _hand('E2', players=[
        {'pos': 'BTN', 'name': 'Hero', 'stack': 'xx', 'cards': ''},
        {'pos': 'BB', 'name': 'Rival', 'stack': 100, 'cards': ''}])
    v = dh.validate_hands([h1, h2])
    assert v['issues']['pos_desconocida'] == 1
    assert v['issues']['amount_invalido'] == 1


def test_coverage_conteos(tmp_path):
    hands = [_hand(f'F{i}',
                   streets=_flop_street(['Qh', '7s', '2c'])) for i in range(3)]
    cov = dh.coverage(hands, min_n=3)
    assert cov['hands'] == 3
    assert cov['players'] == 2
    assert cov['conocidas'] >= 3
    assert cov['by_street']['flop']['obs'] == 6
    assert cov['by_street']['preflop']['obs'] == 6
    # 2 jugadores x 2 spots con n>=3: Hero(no_raise) y Rival(no_raise)
    assert 'preflop_celdas_n3' in cov


def test_snapshot_delta(tmp_path, monkeypatch):
    h1 = _hand('G1')
    h2 = _hand('G2')
    monkeypatch.setattr(dh, 'SNAPSHOT_PATH', str(tmp_path / 'snap.json'))
    d = dh.snapshot_delta([h1])
    assert d.get('sin_snapshot')
    dh.save_snapshot([h1])
    d = dh.snapshot_delta([h1, h2])
    assert d['nuevas'] == 1
    assert d['nuevo_por_jugador'].get('Hero') == 1
    # persistida la nueva mano, otra corrida sin cambios: 0 nuevas
    dh.save_snapshot([h1, h2])
    d = dh.snapshot_delta([h1, h2])
    assert d['nuevas'] == 0