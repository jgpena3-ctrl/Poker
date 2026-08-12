"""Test de motor/situation.py — equity vs rango, pot odds, SPR, textura."""
import numpy as np
import pytest

from motor.cards import card_id, cards_to_bits
from motor.hand_evaluator import evaluate_batch, evaluate_hand, legal_hands
from motor.ranges import COMBO0, COMBO1, RangeState
from motor.situation import (
    Situation, board_texture, equity_vs_range, hero_percentile, pot_odds,
    situation, spr,
)


def _brute_force_equity(hero_codes, board_codes):
    """Oracle independiente: componentes del equity vía única evaluación."""
    known = cards_to_bits(hero_codes + board_codes)
    ids = legal_hands(known)
    hero = evaluate_hand(hero_codes, board_codes)
    pairs = np.column_stack([COMBO0[ids], COMBO1[ids]])
    scores = evaluate_batch(pairs, [card_id(c) for c in board_codes])
    w = int((scores < hero).sum())
    t = int((scores == hero).sum())
    l = int((scores > hero).sum())
    n = len(ids)
    return (w + 0.5 * t) / n, w / n, t / n, l / n


def test_equity_matches_brute_force_flop():
    hero, board = ['As', 'Kd'], ['Qh', '7s', '2c']
    eq = equity_vs_range(hero, board)
    oracle = _brute_force_equity(hero, board)
    assert eq == pytest.approx(oracle, abs=1e-9)


def test_equity_vs_river_board():
    hero, board = ['As', 'Kd'], ['Qh', '7s', '2c', '9d', '5h']
    eq = equity_vs_range(hero, board)
    oracle = _brute_force_equity(hero, board)
    assert eq == pytest.approx(oracle, abs=1e-9)


def test_equity_weighted_by_reach():
    # Villain con reach concentrado en KK → equity de la pareja 22 baja.
    hero, board = ['2d', '2h'], ['Qh', '7s', '3c']
    rs = RangeState(reach=np.zeros(1326, dtype=np.float32))
    for i, (a, b) in enumerate(zip(COMBO0, COMBO1)):
        if a // 4 == 12 and b // 4 == 12:  # KK
            rs.reach[i] = 1.0
    eq = equity_vs_range(hero, board, villain_reach=rs)[0]
    assert eq < 0.05, f'22 vs rango solo-KK debería estar muy abajo, equity={eq}'


def test_equity_weighted_vs_uniform():
    # El mismo 22 vs rango uniforme: la masa en KK es 6/1225 → equity sube.
    hero, board = ['2d', '2h'], ['Qh', '7s', '3c']
    reach = np.zeros(1326, dtype=np.float32)
    ids = legal_hands(cards_to_bits(hero + board))
    reach[ids] = 1.0
    eq_kk = equity_vs_range(hero, board, villain_reach=kk_reach())[0]
    eq_all = equity_vs_range(hero, board, villain_reach=reach)[0]
    assert eq_all > eq_kk


def test_equity_valid_range():
    for _ in range(3):
        hero, board = ['As', 'Kd'], ['Qh', '7s', '2c']
        eq = equity_vs_range(hero, board)[0]
        assert 0.0 <= eq <= 1.0


def test_hero_percentile_is_equity():
    hero, board = ['As', 'Kd'], ['Qh', '7s', '2c']
    assert hero_percentile(hero, board) == equity_vs_range(hero, board)[0]


def test_hero_loses_to_narrow_range():
    # 22 vs solo AA → equity 0.0 exacta
    hero, board = ['2d', '2h'], ['Qh', '7s', '3c']
    reach = np.zeros(1326, dtype=np.float32)
    for i, (a, b) in enumerate(zip(COMBO0, COMBO1)):
        if a // 4 == 12 and b // 4 == 12:  # AA
            reach[i] = 1.0
    eq = equity_vs_range(hero, board, villain_reach=reach)[0]
    assert eq == pytest.approx(0.0, abs=1e-9)


def test_hero_beats_narrow_range():
    # AA vs KK (6 combos) + QQ (3 legales: Qh en board) → 6 wins / 9
    hero, board = ['As', 'Ah'], ['Qh', '7s', '2c']
    reach = np.zeros(1326, dtype=np.float32)
    for i, (a, b) in enumerate(zip(COMBO0, COMBO1)):
        if a // 4 in (11, 10) and b // 4 in (11, 10) and a // 4 == b // 4:  # KK, QQ
            reach[i] = 1.0
    eq = equity_vs_range(hero, board, villain_reach=reach)[0]
    assert eq == pytest.approx(6 / 9, abs=1e-9)


def test_pot_odds():
    assert pot_odds(50, 100) == pytest.approx(50 / 150)
    assert pot_odds(25, 75) == pytest.approx(25 / 100)
    assert pot_odds(0, 100) == 0.0
    with pytest.raises(ValueError):
        pot_odds(10, -5)


def test_spr():
    assert spr(200, 100) == 2.0
    assert spr(0, 100) == 0.0
    assert spr(200, 0) is None


def test_board_texture():
    mono = board_texture(['Ah', 'Kh', 'Th', '7h', '2h'])
    assert mono['monotone'] is True
    assert mono['flush_suits'] == {'h': 5}

    paired = board_texture(['Qh', 'Qs', '2h'])
    assert paired['pairs'] == {10: 2}  # Q = rank 10 (23456789TJ QKA)
    assert paired['two_tone'] is True

    rainbow = board_texture(['Qh', '7s', '2c'])
    assert rainbow['rainbow'] is True
    assert rainbow['straight_run'] == 1

    connected = board_texture(['7h', '8s', '9d'])
    assert connected['straight_run'] == 3

    trips = board_texture(['Qh', 'Qs', 'Qd'])
    assert trips['trips'] is True


def test_situation_builder():
    sit = situation(
        ['As', 'Kd'], ['Qh', '7s', '2c'],
        pot_before_call=100, to_call=50, stack_effective=200,
        position='BTN', street='flop',
    )
    assert isinstance(sit, Situation)
    assert sit.equity == pytest.approx(sit.wins + 0.5 * sit.ties, abs=1e-9)
    assert sit.pot_odds == pytest.approx(50 / 150)
    assert sit.spr == 2.0
    assert sit.combos_evaluados == 1081  # C(47,2): hero + 3 del board conocidos
    assert sit.position == 'BTN'


def test_situation_no_pot_odds():
    sit = situation(['As', 'Kd'], ['Qh', '7s', '2c'], to_call=0, pot_before_call=0)
    assert sit.pot_odds is None
    assert sit.spr is None


def kk_reach():
    reach = np.zeros(1326, dtype=np.float32)
    for i, (a, b) in enumerate(zip(COMBO0, COMBO1)):
        if a // 4 == 12 and b // 4 == 12:
            reach[i] = 1.0
    return reach