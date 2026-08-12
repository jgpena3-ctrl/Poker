"""Test de motor/preflop.py — tablas preflop 13x13 -> vectores de 1326 combos."""
import numpy as np
import pytest

from motor.preflop import (
    GRID_INDEX, matrix_to_probs, load_tables, table_key,
    prob, opening_range,
)
from motor.ranges import N_COMBOS, HAND_MASKS, RangeState


@pytest.fixture(scope='module')
def tables():
    return load_tables()


def test_load_has_all_expected():
    t = load_tables()
    assert len(t) >= 100
    for name in ('OR_UTG', 'OR_MP', 'OR_CO', 'OR_BTN', 'OR_SB',
                 '3B_BB_vs_SB', 'SQUEEZE_BB_vs_UTG+BTN'):
        assert name in t, name


def test_shapes(tables):
    for name, t in tables.items():
        assert t['probs'].shape == (N_COMBOS,), name
        assert np.isfinite(t['probs']).all(), name
        assert (t['probs'] >= 0).all() and (t['probs'] <= 1).all(), name


def test_matrix_to_probs_shape():
    grid = [[0.5] * 13 for _ in range(13)]
    v = matrix_to_probs(grid)
    assert v.shape == (N_COMBOS,)
    assert np.allclose(v, 0.5)


def test_matrix_to_probs_bad_shape():
    with pytest.raises(ValueError):
        matrix_to_probs([[1.0]] * 12)


def test_pair_and_suited_mapping():
    """Celda (0,0)=1 -> solo los 6 combos de AA valen 1;
    celda (0,1)=1 -> los 4 combos de AKs valen 1."""
    grid = [[0.0] * 13 for _ in range(13)]
    grid[0][0] = 1.0
    v = matrix_to_probs(grid)
    from motor.ranges import HAND_LABELS
    aa = [i for i, lab in enumerate(HAND_LABELS)
          if lab[0] == 'A' and lab[2] == 'A']
    assert len(aa) == 6
    assert np.allclose(v[aa], 1.0)
    assert v.sum() == 6.0

    grid[0][1] = 1.0  # AKs
    v = matrix_to_probs(grid)
    aks = [i for i, lab in enumerate(HAND_LABELS)
           if {lab[0], lab[2]} == {'A', 'K'} and lab[1] == lab[3]]
    assert len(aks) == 4
    assert np.allclose(v[aks], 1.0)
    assert v.sum() == 10.0  # 6 de AA + 4 de AKs


def test_open_range_utg_monotonic():
    v = opening_range('UTG')
    assert v.shape == (N_COMBOS,)
    assert (v >= 0).all()
    # AA debe estar abierto (1.0)
    from motor.ranges import HAND_LABELS
    aa_idx = [i for i, lab in enumerate(HAND_LABELS)
              if lab[0] == 'A' and lab[2] == 'A']
    assert np.allclose(v[aa_idx], 1.0)
    # La frecuencia media decrece con relación a OR_BTN (más amplio)
    btn = opening_range('BTN')
    assert float(btn.mean()) > float(v.mean())


def test_table_key():
    assert table_key('OR', 'UTG') == 'OR_UTG'
    assert table_key('3B', 'BB', 'SB') == '3B_BB_vs_SB'


def test_prob_missing_table_zeros():
    v = prob('OR', 'ZZZ')  # tabla inexistente
    assert v.shape == (N_COMBOS,)
    assert np.count_nonzero(v) == 0


def test_integration_utg_open_bb_3bet():
    """Escenario real: UTG abre, BB hace 3bet vs UTG.

    El rango del 3bet debe quedar dominado por premiums (AA/KK/AK), aunque el
    rango de apertura de UTG sea amplio (tabla del usuario con muchos 1.0).
    """
    from motor.ranges import HAND_LABELS
    utg = RangeState(reach=opening_range('UTG'), position='UTG')
    utg.norm_to()

    bb3b = RangeState(reach=prob('3B', 'BB', 'UTG'), position='BB')
    bb3b.norm_to()

    top = [lab for lab, _ in bb3b.top_hands(12)]
    for lab in top:
        r0, r1 = lab[0], lab[2]
        # premium: pares AA/KK/QQ o una mano con A/K
        is_premium = r0 == r1 and r0 in 'AKQ' or 'A' in (r0, r1)
        assert is_premium, lab
    # AA domina el rango del 3bet
    assert top[0][0] == 'A' and top[0][2] == 'A'