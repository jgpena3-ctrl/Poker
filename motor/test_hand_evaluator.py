"""Test de motor/hand_evaluator.py — ranking exacto de manos."""
import numpy as np
import pytest

from motor.cards import card_id, cards_to_bits
from motor.hand_evaluator import (
    CATEGORY_NAMES, category_name, compare_ranks, evaluate5, evaluate7,
    evaluate_batch, evaluate_five_batch, evaluate_hand, evaluate_n_batch,
    hero_vs_range, legal_hands,
)
from motor.ranges import HAND_MASKS, N_COMBOS


def s(*codes):
    return evaluate5([card_id(c) for c in codes])


def _ids(codes):
    return [card_id(c) for c in codes]


# ----------------------------------------------------------------------
# Jerarquía de categorías y tiebreaks
# ----------------------------------------------------------------------
def test_categories_strictly_ordered():
    royal = s('As', 'Ks', 'Qs', 'Js', 'Ts')          # straight flush
    quads = s('As', 'Ah', 'Ad', 'Ac', 'Kd')          # quads A
    full = s('As', 'Ah', 'Ad', 'Kc', 'Kd')           # full house AAA KK
    flush = s('As', 'Ks', 'Qs', 'Js', '9s')          # flush A-high
    straight = s('As', 'Kc', 'Qd', 'Jh', 'Ts')       # straight A-high, sin flush
    trips = s('As', 'Ah', 'Ad', 'Kc', '2d')          # trips A kickers K,2
    twop = s('As', 'Ad', 'Kc', 'Kd', '2h')           # two pair A K
    pair = s('As', 'Ad', 'Kc', 'Qh', 'Jd')           # pair A kickers K,Q,J
    high = s('As', 'Kd', 'Qh', 'Jc', '8s')           # high card
    manos = [high, pair, twop, trips, straight, flush, full, quads, royal]
    for lo, hi in zip(manos, manos[1:]):
        assert lo < hi, f'{category_name(lo)} debe < {category_name(hi)}'


def test_category_names():
    scores = [s('As', 'Kd', 'Qh', 'Jc', '8s'),
              s('As', 'Ad', 'Kc', 'Qh', 'Jd'),
              s('As', 'Ad', 'Kc', 'Kd', '2h'),
              s('As', 'Ah', 'Ad', 'Kc', '2d'),
              s('As', 'Kc', 'Qd', 'Jc', 'Ts'),
              s('As', 'Ks', 'Qs', 'Js', '9s'),
              s('As', 'Ah', 'Ad', 'Kc', 'Kd'),
              s('As', 'Ah', 'Ad', 'Ac', 'Kd'),
              s('As', 'Ks', 'Qs', 'Js', 'Ts')]
    assert [category_name(x) for x in scores] == CATEGORY_NAMES


def test_straight_tiebreak_and_wheel():
    straight = s('As', 'Kc', 'Qd', 'Jh', 'Ts')
    wheel = s('As', '2d', '3h', '4c', '5s')
    straight23456 = s('2s', '3d', '4h', '5c', '6s')
    assert wheel < straight23456 < straight
    assert category_name(wheel) == 'straight'


def test_tiebreak_within_category():
    assert s('As', 'Ad', 'Kc', 'Kd', '2h') < s('As', 'Ad', 'Kc', 'Kd', '3h')
    assert s('Ah', 'Ad', 'Kc', 'Qd', 'Td') < s('Ah', 'Ad', 'Kc', 'Qd', 'Jh')
    assert s('As', 'Ah', 'Ad', 'Kc', 'Kd') > s('Kh', 'Kd', 'Kc', 'As', 'Ah')  # AAA > KKK
    assert s('As', 'Ah', 'Ad', 'Ac', 'Kd') > s('Ks', 'Kh', 'Kd', 'Kc', 'Ad')  # AAAA > KKKK
    assert s('As', 'Ks', 'Qs', 'Js', '9s') == s('Ah', 'Kh', 'Qh', 'Jh', '9h')  # mismo flush


# ----------------------------------------------------------------------
# Manos de 6/7 cartas: mejor subconjunto de 5
# ----------------------------------------------------------------------
def test_evaluate7_uses_best_five():
    royal7 = _ids(['As', 'Ks', 'Qs', 'Js', 'Ts', '2c', '3d'])
    assert evaluate7(royal7) == s('As', 'Ks', 'Qs', 'Js', 'Ts')


def test_evaluate6_picks_full_house():
    hand6 = _ids(['As', 'Ah', 'Ad', 'Kc', 'Kh', '2d'])
    assert evaluate_n_batch([hand6])[0] == s('As', 'Ah', 'Ad', 'Kc', 'Kh')


def test_flush_in_seven_cards():
    assert category_name(evaluate7(_ids(['As', 'Ks', 'Qs', '4s', '2s', 'Kd', '9c']))) == 'flush'


def test_wheel_and_straight_in_seven_cards():
    assert category_name(evaluate7(_ids(['Ah', '2d', '3c', '4s', '5h', '9d', 'Jc']))) == 'straight'


# ----------------------------------------------------------------------
# Batch / interfaz pública
# ----------------------------------------------------------------------
def test_evaluate_batch_matches_individual():
    board = _ids(['Qh', '7s', '2c'])
    pairs = np.array([_ids(['As', 'Ks']), _ids(['9d', '9c']), _ids(['Th', 'Jh'])],
                     dtype=np.intp)
    batch = evaluate_batch(pairs, board)
    single = [evaluate_hand(['As', 'Ks'], ['Qh', '7s', '2c']),
              evaluate_hand(['9d', '9c'], ['Qh', '7s', '2c']),
              evaluate_hand(['Th', 'Jh'], ['Qh', '7s', '2c'])]
    assert list(batch) == single
    assert batch.shape == (3,)


def test_evaluate_hand_river():
    assert evaluate_hand(['Ah', 'Ad'], ['Qh', '7s', '2c', '9d', '5h']) > evaluate_hand(
        ['2d', '3h'], ['Qh', '7s', '2c', '9d', '5h'])


def test_compare_ranks_counts():
    scores = np.array([s('As', 'Kd', 'Qh', 'Jc', '8s')] * 2 +
                      [s('Ks', 'Kd', 'Qh', 'Jc', '8s')] +
                      [s('2s', '3d', '4h', '5c', '9d')] + [s('As', 'Kd', 'Qh', 'Jc', '8s')])
    assert compare_ranks(s('As', 'Kd', 'Qh', 'Jc', '8s'), scores) == (1, 3, 1)
    # 1 por debajo (mano baja), 3 iguales, 1 por encima (pareja de K)


def test_legal_hands_exclude_known():
    known = cards_to_bits(['As', 'Kd'])
    idx = legal_hands(known)
    assert idx.shape[0] == N_COMBOS - 2 * 51 + 1 == 1225
    assert int((HAND_MASKS[idx] & known).any()) == 0


def test_legal_hands_single_card():
    assert legal_hands(cards_to_bits(['2c'])).shape[0] == 1275


# ----------------------------------------------------------------------
# hero_vs_range
# ----------------------------------------------------------------------
def test_hero_vs_range_counts():
    board = ['Qh', '7s', '2c', '9d', '5h']
    known = cards_to_bits(['As', 'Kd'] + board)
    idx = legal_hands(known)
    w, ti, l = hero_vs_range(['As', 'Kd'], board, known, idx)
    assert w + ti + l == idx.shape[0]
    assert w + l == idx.shape[0] - ti  # los ties se cuentan aparte


def test_hero_vs_range_accepts_any_ids():
    board = ['Qh', '7s', '2c']
    known = cards_to_bits(['As', 'Kd'] + board)
    idx = legal_hands(known)
    parcial = hero_vs_range(['As', 'Kd'], board, known, idx[:37])
    assert sum(parcial) == 37


# ----------------------------------------------------------------------
# Tabla C(52,5) (fase 3): misma salida exacta que el evaluador por-fila
# ----------------------------------------------------------------------
def test_five_table_matches_exact_evaluator():
    from motor.hand_evaluator import _five_table, _SUBSETS, _lookup5
    table = _five_table()
    assert table.shape == (2_598_960,)
    rng = np.random.default_rng(11)
    hands = np.column_stack([rng.permutation(52)[:7] for _ in range(500)]).T
    sub = _SUBSETS[7]
    five = hands[:, sub].reshape(-1, 5)
    exact = evaluate_five_batch(five).reshape(hands.shape[0], 21).max(axis=1)
    fast = _lookup5(five, table).reshape(hands.shape[0], 21).max(axis=1)
    assert np.array_equal(fast, exact)
    # y a través de evaluate_n_batch (que debe usar la tabla)
    assert np.array_equal(evaluate_n_batch(hands), exact)