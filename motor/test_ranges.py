"""Test de motor/ranges.py — 1326 combos, RangeState (reach/weight), update bayesiano."""
import numpy as np
import pytest

from motor.cards import card_id, hand_mask
from motor.ranges import (
    N_COMBOS, COMBO0, COMBO1, HAND_LABELS, HAND_MASKS, IS_PAIR, IS_SUITED,
    RangeState, uniform_range, default_action_prob,
)


# ---------------------------------------------------------------
# ALL_HANDS
# ---------------------------------------------------------------

def test_all_hands_count_and_structure():
    assert N_COMBOS == 1326
    assert len(COMBO0) == 1326
    assert len(COMBO1) == 1326
    assert len(HAND_LABELS) == 1326
    # cada combo: dos cartas distintas, c0 < c1
    assert (COMBO0 < COMBO1).all()


def test_all_hands_masks_single_bits():
    for c0, c1, m in zip(COMBO0[:200], COMBO1[:200], HAND_MASKS[:200]):
        assert m == (1 << int(c0)) | (1 << int(c1))
        assert bin(m).count('1') == 2


def test_all_hands_no_duplicates():
    assert len(set(HAND_LABELS)) == 1326
    assert len(set(map(int, HAND_MASKS))) == 1326


def test_suited_and_pair_counts():
    # Suited: C(13,2) pares de rangos x 4 palos = 312
    assert int(IS_SUITED.sum()) == 78 * 4 == 312
    # Pares: 13 rangos x C(4,2)=6 combos = 78
    assert int(IS_PAIR.sum()) == 13 * 6 == 78
    # Offsuit no-par: 1326 - 312 - 78 = 936
    assert int((~IS_SUITED & ~IS_PAIR).sum()) == 936


def test_labels_format():
    for lab in HAND_LABELS[:50]:
        assert len(lab) == 4
        assert lab[0] in '23456789TJQKA'
        assert lab[1] in 'cdhs'
        assert lab[2] in '23456789TJQKA'
        assert lab[3] in 'cdhs'


# ---------------------------------------------------------------
# RangeState: reach / weight
# ---------------------------------------------------------------

def test_uniform_weights_normalized():
    rs = uniform_range()
    w = rs.weights
    assert w.shape == (N_COMBOS,)
    assert np.isclose(w.sum(), 1.0)
    assert np.allclose(w, 1 / 1326)


def test_weights_are_view_of_reach():
    rs = uniform_range()
    rs.reach[0] *= 3.0
    w = rs.weights
    expected = rs.reach.copy()
    expected = expected / expected.sum()
    assert np.allclose(w, expected)


def test_legal_mask_filters_blockers():
    rs = uniform_range()
    rs.set_known_cards(['As'])
    legal = rs.legal_mask
    # 51 cartas restantes -> C(51,2) = 1275 combos legales
    assert legal.sum() == 1275
    as_mask = 1 << card_id('As')
    for i, m in enumerate(HAND_MASKS):
        if m & as_mask:
            assert not legal[i]


def test_reach_blocked_and_normalization():
    rs = uniform_range()
    rs.reach[:] = 1.0
    rs.set_known_cards(['As', 'Kd'])
    # C(50,2) = 1225 legales
    assert rs.legal_mask.sum() == 1225
    rb = rs.reach_blocked
    assert rb[~rs.legal_mask].sum() == 0
    w = rs.weights
    assert np.isclose(w.sum(), 1.0)
    assert w[~rs.legal_mask].sum() == 0


def test_update_bayes():
    """reach nuevo = reach * P(A|H); weight renormalizado."""
    rs = uniform_range()
    w0 = rs.weights
    probs = np.full(N_COMBOS, 0.1, dtype=np.float32)
    probs[0] = 10.0
    rs.update(probs)
    w1 = rs.weights
    assert np.isclose(w1.sum(), 1.0)
    assert w1[0] > 10 * w0[0]


def test_update_action_zero_combos():
    rs = uniform_range()
    probs = np.ones(N_COMBOS, dtype=np.float32)
    probs[5] = 0.0
    rs.update(probs)
    assert rs.weights[5] == 0.0
    assert np.isclose(rs.weights.sum(), 1.0)


def test_update_length_check():
    rs = uniform_range()
    with pytest.raises(ValueError):
        rs.update(np.ones(100))


# ---------------------------------------------------------------
# Heurística P(A|H)
# ---------------------------------------------------------------

def test_default_action_prob_premium_raises():
    ctx = {'street': 'preflop'}
    p_prem_r = default_action_prob('AA', 'r', ctx)
    p_weak_r = default_action_prob('72o', 'r', ctx)
    assert p_prem_r > p_weak_r
    assert p_prem_r > 0.5
    assert p_weak_r <= 0.05


def test_default_action_prob_fold():
    ctx = {'street': 'preflop'}
    assert default_action_prob('72o', 'f', ctx) > 0.5
    assert default_action_prob('AA', 'f', ctx) < 0.1


def test_default_action_prob_context_neutral_postflop():
    ctx = {'street': 'flop'}
    assert default_action_prob('AA', 'c', ctx) == 0.5
    assert default_action_prob('72o', 'f', ctx) == 0.5


# ---------------------------------------------------------------
# Escenario adhesivo del doc: AA domina el rango tras un 3bet
# (sin evaluador aún; validamos el mecanismo de actualización)
# ---------------------------------------------------------------

def test_reach_history_race():
    rs = uniform_range()
    probs_first = np.array(
        [default_action_prob(lab, 'r', {'street': 'preflop'}) for lab in HAND_LABELS],
        dtype=np.float32,
    )
    rs.update(probs_first)
    w_first = rs.weights
    labels_top = [HAND_LABELS[i] for i in np.argsort(w_first)[::-1][:3]]
    # El combo dominante tras 3bet debe ser un par de Ases ('AhAd', etc.)
    assert labels_top[0][0] == labels_top[0][2] == 'A'