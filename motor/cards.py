"""cards.py — encoding de cartas y bitmasks de 52 bits.

Una carta se representa como índice 0..51 (rank*4 + suit) y su bit en una
máscara de 52 bits es `1 << idx`.

RANK_ORDER = '23456789TJQKA'  (T = 10)
SUIT_ORDER = 'cdhs'           (clubs, diamonds, hearts, spades)

Ejemplos:
    card_id('Ah')   -> 50
    card_str(50)    -> 'Ah'
    hand_mask('AhKd') -> bitmask de 52 bits con los bits de Ah y Kd
"""
import numpy as np

RANK_ORDER = '23456789TJQKA'
SUIT_ORDER = 'cdhs'

_RANK_INDEX = {r: i for i, r in enumerate(RANK_ORDER)}
_SUIT_INDEX = {s: i for i, s in enumerate(SUIT_ORDER)}

N_RANKS = len(RANK_ORDER)
N_SUITS = len(SUIT_ORDER)


def card_id(code):
    """'Ah' -> entero 0..51."""
    if not isinstance(code, str) or len(code) != 2:
        raise ValueError(f'código de carta inválido: {code!r}')
    rank, suit = code[0], code[1]
    if rank.upper() not in _RANK_INDEX:
        raise ValueError(f'rango inválido: {code!r}')
    if suit.lower() not in _SUIT_INDEX:
        raise ValueError(f'palo inválido: {code!r}')
    return _RANK_INDEX[rank.upper()] * N_SUITS + _SUIT_INDEX[suit.lower()]


def card_label(card):
    """entero 0..51 -> 'As'."""
    if not (0 <= card < 52):
        raise ValueError(f'índice de carta fuera de rango: {card}')
    rank = RANK_ORDER[card // N_SUITS]
    suit = SUIT_ORDER[card % N_SUITS]
    return f'{rank}{suit}'


def rank_of(card):
    return card // N_SUITS


def suit_of(card):
    return card % N_SUITS


def card_bit(card):
    """entero 0..51 -> bitmask 52 bits."""
    return 1 << int(card)


def cards_to_bits(cards):
    """lista de códigos ('Ah', 'Kd') -> bitmask 52 bits."""
    mask = 0
    for c in cards:
        mask |= card_bit(card_id(c))
    return mask


def parse_hand(code):
    """'JdTd' (o 'JDTD') -> tupla ordenada (idx1, idx2) con idx1 < idx2."""
    if not isinstance(code, str) or len(code) != 4:
        raise ValueError(f'formato de mano inválido: {code!r}')
    a, b = card_id(code[:2]), card_id(code[2:])
    if a == b:
        raise ValueError(f'la mano {code!r} repite la misma copia de una carta')
    return (a, b) if a < b else (b, a)


def hand_mask(code):
    """mano de 4 caracteres -> bitmask 52 bits de sus dos cartas."""
    a, b = parse_hand(code)
    return card_bit(a) | card_bit(b)


def mask_to_cards(mask):
    """bitmask -> lista de etiquetas 'As' de las cartas activas."""
    out = []
    m = int(mask)
    while m:
        lsb = m & -m
        idx = lsb.bit_length() - 1
        out.append(card_label(idx))
        m ^= lsb
    return out


def is_pair(cards):
    """Tupla (c0, c1) de índices -> True si mismo rango."""
    return rank_of(cards[0]) == rank_of(cards[1])


def is_suited(cards):
    """Tupla (c0, c1) de índices -> True si mismo palo."""
    return suit_of(cards[0]) == suit_of(cards[1])


def all_card_ids():
    return list(range(52))