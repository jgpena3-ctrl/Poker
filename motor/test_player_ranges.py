"""test_player_ranges.py — ProfileRangeModel (P(A|H, spot, perfil))."""
import json
import os

import numpy as np
import pytest

from motor import player_ranges as pr
from motor import ranges as rng

HAND_OPEN = {
    'hand_id': 't-open',
    'players': [
        {'pos': 'BTN', 'name': 'Alfa', 'cards': ['As', 'Ad']},
        {'pos': 'BB', 'name': 'Beta', 'cards': []},
    ],
    'streets': {
        'preflop': {'actions': [
            {'pos': 'BTN', 'action': 'r', 'amount': 2.5},
            {'pos': 'BB', 'action': 'f', 'amount': 0},
        ]},
    },
}

HAND_LIMP_CALL = {
    'hand_id': 'H-limp',
    'players': [
        {'pos': 'UTG', 'name': 'Alfa', 'cards': ['7c', '7d']},
        {'pos': 'BB', 'name': 'Beta', 'cards': []},
    ],
    'streets': {
        'preflop': {'actions': [
            {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
            {'pos': 'BB', 'action': 'x', 'amount': 0},
        ]},
    },
}


def test_cell_of_hand_conventions():
    assert pr._cell_('AsAs') == (0, 0)
    assert pr._cell_('AsKs') == (0, 1)          # suited
    assert pr._cell_('AsKd') == (1, 0)          # off
    assert pr._cell_('7c2d') == (12, 7)         # off, menor col
    assert pr._cell_('') is None
    assert pr._cell_('As') is None


def test_from_hands_conteos_y_labels():
    profs = {'Alfa': 'Regular', 'Beta': 'Regular'}
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels=profs)
    opp = m.opp[('Regular', 'no_raise')]
    assert int(opp.sum()) == 1                    # 1 decisión con cartas
    assert opp[0, 0] == 1.0                       # AsAs en BTN
    assert m.cnt[('Regular', 'no_raise', 'open')][0, 0] == 1.0
    assert ('Regular', 'no_raise', 'limp') not in m.cnt


def test_shrinkage_a_la_base():
    # perfil sin datos -> grid = base (OR_BTN) pura
    m0 = pr.ProfileRangeModel()
    b = m0._prior_grid('open', 'BTN')
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'Unknown'})
    got = m.p_matrix('Unknown', 'no_raise', 'open', 'BTN')
    assert got.shape == (13, 13)
    assert np.allclose(got, b, atol=0.01)          # sin datos → prior puro


def test_shrinkage_mezcla():
    # con 1 hora epoch: P = (1 + a·p0)/(1+a); p0(AA)>=p0(72) y p0(AA)>0
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'Regular'})
    pAA = m.p_hand('Regular', 'no_raise', 'open', 'AsAs')
    p72 = m.p_hand('Regular', 'no_raise', 'open', '7c2d')
    assert 0.5 < pAA <= 1.0
    assert p72 < pAA


def test_prob_vec_consistente_con_p_hand():
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'R'})
    v = m.prob_vec('R', 'no_raise', 'open', 'BTN')
    assert v.shape == (rng.N_COMBOS,)
    assert np.all(v >= 0.0) and np.all(v <= 1.0)
    # AsAs = combos AA: todos los AA valen la celda (0,0)
    aa = [i for i, l in enumerate(rng.HAND_LABELS) if l[0] == 'A' and l[2] == 'A']
    assert aa
    cell_val = float(v[aa[0]])
    assert cell_val == pytest.approx(
        m.p_hand('R', 'no_raise', 'open', 'AsAs'), abs=1e-6)


def test_prob_vec_rango_estado_update():
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'R'})
    v = m.prob_vec('R', 'no_raise', 'open', 'BTN')
    rs = rng.uniform_range()
    rs.update(v)
    assert float(rs.reach.sum()) > 0.0              # algo del rango pasa


def test_save_load_roundtrip(tmp_path):
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'R'})
    p = tmp_path / 'ranges.json'
    m.save(str(p))
    m2 = pr.ProfileRangeModel.load(str(p))
    assert m2.alpha == m.alpha
    assert m2.perfil['Alfa'] == 'R'
    k = ('R', 'no_raise')
    assert np.array_equal(m2.opp[k], m.opp[k])


def test_p_hand_mano_invalida():
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'R'})
    assert m.p_hand('R', 'no_raise', 'open', 'XxYy') == 0.0
    assert m.p_hand('R', 'no_raise', 'open', '') == 0.0


# ---------------------------------------------------------------------------
# Ajuste individual (paso pegar6/2): omega real/perfil + desviación por
# jugador con fade-in por muestra
# ---------------------------------------------------------------------------

def test_player_omega_desviacion_por_jugador():
    from motor.profile import PlayerProfile
    from motor.profile import Profiles

    profs = Profiles()
    base = {'vpip': 0.45, 'pfr': 0.15, 'b3': 0.04}
    profs.profiles = {
        'Alfa': PlayerProfile('Alfa', n=60, stats=base),
        'Beta': PlayerProfile('Beta', n=60, stats=dict(base, pfr=0.30)),
        'Gamma': PlayerProfile('Gamma', n=60, stats=dict(base, pfr=0.10)),
    }
    labels = {name: prof.label for name, prof in profs.profiles.items()}
    m = pr.ProfileRangeModel.from_hands([], labels=labels)
    m.profiles = profs
    wa = m.player_omega('Alfa', 'no_raise')
    wb = m.player_omega('Beta', 'no_raise')
    assert labels['Alfa'] == labels['Beta'] == labels['Gamma']
    assert wa < 1.0                    # Alfa: pfr 0.15 < media 0.18
    assert wb > 1.0                    # Beta: pfr 0.30 > media 0.18


def test_player_omega_fade_in():
    from motor.profile import PlayerProfile
    from motor.profile import Profiles

    profs = Profiles()
    base = {'vpip': 0.45, 'pfr': 0.15, 'b3': 0.04}
    profs.profiles = {
        'A': PlayerProfile('A', n=5, stats=dict(base, pfr=0.60)),
        'B': PlayerProfile('B', n=5, stats=dict(base, pfr=0.15)),
        'C': PlayerProfile('C', n=5, stats=dict(base, pfr=0.15)),
    }
    labels = {n: p.label for n, p in profs.profiles.items()}
    m = pr.ProfileRangeModel.from_hands([], labels=labels)
    m.profiles = profs
    w = m.player_omega('A', 'no_raise')
    assert 1.0 < w < 4.0               # ratio enorme → fade aprieta a 1
    w2 = m.player_omega('A', 'no_raise', fade=100.0)
    assert 1.0 < w2 < w               # más fade → más cerca de 1


def test_p_player_escala_con_omega():
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'R'})
    w = m.player_omega('Alfa', 'no_raise')
    if w == 1.0:                     # sin perfiles reales: escala trivial
        assert np.array_equal(m.p_player('Alfa', 'no_raise', 'open'),
                              m.p_matrix('R', 'no_raise', 'open'))
    else:
        m2 = m.p_matrix('R', 'no_raise', 'open') * w
        assert np.allclose(m.p_player('Alfa', 'no_raise', 'open'),
                           np.clip(m2, 0.0, 1.0), atol=1e-6)

def test_to_json_incluye_omega():
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'R'})
    d = m.to_json()
    assert 'omega' in d and 'Alfa' in d['omega']


def test_prob_vec_player_consistente():
    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'R'})
    v = m.prob_vec_player('Alfa', 'no_raise', 'open', 'BTN')
    assert v.shape == (rng.N_COMBOS,)
    assert np.all(v >= 0.0) and np.all(v <= 1.0)


def test_recommend_con_rango_perfilado():
    from motor.recommend_loop import recommend

    m = pr.ProfileRangeModel.from_hands([HAND_OPEN], labels={'Alfa': 'R'})
    rec = recommend(['Jd', 'Jh'], ['Qh', '7s', '2c'],
                    street='flop', position='BB', villain_pos='BTN',
                    pot=12.5, to_call=5.0, stack=90.0,
                    range_model=m, villain_player='Alfa')
    assert rec.action in ('fold', 'check', 'call', 'bet_25', 'bet_50',
                          'bet_75', 'all_in')
    assert 'Alfa' in rec.villain_label
    assert rec.elapsed_ms > 0