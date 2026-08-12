"""Tests de behavior tables por perfil (motor/behavior.py)."""
import pytest

from motor.behavior import (Oracle, _key, behavior_table, build,
                            labels_from_hands, report)


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
            ], board=['5d', '6d', '9s']),
        },
    }


def _hands(n=3):
    return [_hand(f'H{x:03d}') for x in range(n)]


def test_build_estructura_y_min_n():
    data = build(_hands(), labels={'X': 'Regular', 'Y': 'LAG'}, min_n=3)
    assert data['hands'] == 3
    assert data['observaciones'] == 12            # 4 por mano
    assert data['profiles'] == {'X': 'Regular', 'Y': 'LAG'}
    g = data['granular']
    # X: 3 raise (bet) preflop sin enfrentar y 3 bet en flop (initiator)
    assert g[('Regular', 'preflop', '-', 'none')]['b'] == 1.0
    assert g[('Regular', 'preflop', '-', 'none')]['n'] == 3
    # X flop: apuesta en two_tone sin enfrentar (sizing 4/4 = 1.0)
    cell = g[('Regular', 'flop', 'two_tone', 'none')]
    assert cell['b'] == 1.0 and cell['sizing_mean'] == 1.0
    # Y: 3 calls preflop vs raise, 3 folds vs cbet
    assert g[('LAG', 'preflop', '-', 'bet')]['c'] == 1.0
    assert g[('LAG', 'flop', 'two_tone', 'cbet')]['f'] == 1.0
    # min_n=4 deja vacío
    data2 = build(_hands(3), labels={'X': 'Regular', 'Y': 'LAG'}, min_n=4)
    assert not data2['granular']
    assert not data2['por_facing']


def test_jugador_sin_perfil_cae_en_unknown():
    hands = _hands(5)
    data = build(hands, labels={'X': 'Regular'}, min_n=2)   # Y sin label
    keys = set(data['granular'])
    assert any(k[0] == '?' for k in keys)                   # Y -> '?'
    assert 'Regular' in {k[0] for k in keys}


def test_report_contiene_cabeceras():
    data = build(_hands(), labels={'X': 'Regular', 'Y': 'LAG'}, min_n=2)
    text = report(data, min_n=2)
    assert 'POR FACING' in text and 'GRANULAR' in text
    assert 'Regular' in text
    assert 'flop' in text

def test_key_serializa_tupla():
    assert _key(('Regular', 'flop', 'two_tone', 'cbet')) == \
        'Regular|flop|two_tone|cbet'
    assert _key(('a', 3, 'b')) == 'a|3|b'


def test_labels_from_hands_deriva_perfiles():
    hands = _hands(6)
    labels = labels_from_hands(hands)
    assert set(labels) == {'X', 'Y'}
    assert all(isinstance(v, str) and v for v in labels.values())


# ---------------------------------------------------------------------------
# Oracle: P(A|C) con fallbacks escalonados
# ---------------------------------------------------------------------------

def _oracle():
    labels = {'X': 'Regular', 'Y': 'LAG'}
    data = build(_hands(4), labels=labels, min_n=4)
    return Oracle(data), labels


def test_oracle_granular():
    oracle, _ = _oracle()
    p = oracle.p_action('Regular', 'flop', 'none', texture='two_tone')
    assert p['source'] == 'granular'
    assert p['actions']['b'] == 1.0
    assert p['sizing'] == 1.0
    assert abs(sum(p['actions'].values()) - 1.0) < 1e-6


def test_oracle_fallback_a_por_facing():
    oracle, _ = _oracle()
    # Regular nunca se enfrenta a cbet en flop (su tablero es su propia
    # apuesta); la celda por-facing tampoco existe -> label -> poblacion
    p = oracle.p_action('Regular', 'flop', 'cbet')
    assert p is not None
    assert p['source'] in ('label', 'poblacion')


def test_oracle_label_level_para_lag():
    oracle, _ = _oracle()
    # LAG: por-facing de preflop existe ('bet'), consulta sin el del flop:
    p = oracle.p_action('LAG', 'flop', 'bet')
    assert p['source'] == 'label' or p['source'] == 'por_facing'


def test_oracle_perfil_desconocido_usa_poblacion():
    oracle, _ = _oracle()
    p = oracle.p_action('NUEVO', 'flop', 'none')
    assert p['source'] == 'poblacion'
    assert sum(p['actions'].values()) == pytest.approx(1.0, abs=1e-6)


def test_oracle_normaliza_siempre():
    oracle, _ = _oracle()
    for label in ('Regular', 'LAG', 'Otro'):
        for street in ('preflop', 'flop', 'turn', 'river'):
            for facing in ('none', 'bet', 'cbet', 'raise'):
                p = oracle.p_action(label, street, facing)
                if p:
                    assert sum(p['actions'].values()) == \
                        pytest.approx(1.0, abs=1e-6)


def test_oracle_to_dict_contextos():
    oracle, _ = _oracle()
    d = oracle.to_dict()
    assert 'Regular' in d
    flop = d['Regular']['flop']
    assert 'none' in flop
    celda = flop['none']
    assert 'actions' in celda and 'texturas' in celda
    assert 'two_tone' in celda['texturas']