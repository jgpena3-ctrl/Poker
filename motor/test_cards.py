"""Test de motor/cards.py — encoding y bitmasks."""
import pytest

from motor.cards import (
    RANK_ORDER, SUIT_ORDER,
    card_id, card_label, card_bit,
    parse_hand, hand_mask, cards_to_bits, mask_to_cards,
    rank_of, suit_of, is_pair, is_suited,
)


def _popcount(x):
    return bin(x).count('1')


def test_card_id_roundtrip_52():
    assert card_id('2c') == 0
    assert card_id('As') == 51
    for rank in RANK_ORDER:
        for suit in SUIT_ORDER:
            code = f'{rank}{suit}'
            assert card_label(card_id(code)) == code


def test_card_id_full_roundtrip():
    for i in range(52):
        label = card_label(i)
        assert card_id(label) == i


def test_card_id_case_insensitive():
    assert card_id('ah') == card_id('Ah')
    assert card_id('AH') == card_id('Ah')


def test_card_id_invalid():
    with pytest.raises(ValueError):
        card_id('1x')
    with pytest.raises(ValueError):
        card_id('Hola')
    with pytest.raises(ValueError):
        card_id('')


def test_card_bitmask_is_single_bit():
    for code in ('2c', 'As', 'Td', 'Qh'):
        idx = card_id(code)
        assert card_bit(idx) == 1 << idx
        assert _popcount(1 << idx) == 1


def test_hand_mask_and_parse():
    a, b = parse_hand('JdTd')
    assert a < b
    assert set(mask_to_cards(hand_mask('JdTd'))) == {'Jd', 'Td'}
    assert _popcount(hand_mask('AsKd')) == 2
    assert _popcount(cards_to_bits(['2c', '3c', 'As'])) == 3
    with pytest.raises(ValueError):
        parse_hand('AcAc')  # misma carta dos veces
    with pytest.raises(ValueError):
        parse_hand('corto')


def test_rank_suit_helpers():
    ah = card_id('Ah')
    assert card_label(ah) == 'Ah'
    assert rank_of(ah) == rank_of(card_id('Ad'))
    assert suit_of(ah) == suit_of(card_id('5h'))
    assert is_pair((card_id('Ah'), card_id('Ad')))
    assert not is_pair((card_id('Ah'), card_id('Kd')))
    assert is_suited((card_id('Ah'), card_id('5h')))
    assert not is_suited((card_id('Ah'), card_id('5d')))