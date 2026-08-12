"""situation.py — lectura de la mano: equity vs rango, pot odds, SPR, textura.

Situation Engine (ARQUITECTURA §8.1): "¿Qué significa nuestra mano?".

- `equity_vs_range`: equity del hero contra el rango rival **ponderada por reach**
  (masas individuales por combo, no buckets).
- `hero_percentile`: qué fracción del rango rival estamos ganando.
- `pot_odds` / `spr`: números del bote.
- `board_texture`: pares, monotone/two-tone, corridas para escalera.
- `situation(...)`: todo junto en un `Situation` (para el panel/decision).

Todas las funciones son deterministas; el DecisionEngine (decision.py) consumirá
los resultados. La distribución agregada (nuts/valor/draws/aire) queda para la
explicación del panel, nunca como entrada del Decision (§8.2).
"""
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

from .cards import card_id, cards_to_bits, suit_of, rank_of
from .hand_evaluator import evaluate_batch, evaluate_hand, legal_hands, compare_ranks
from .ranges import COMBO0, COMBO1, RangeState

SUITS_LABEL = {0: 'c', 1: 'd', 2: 'h', 3: 's'}


# ---------------------------------------------------------------------------
# Equity vs rango (ponderada por reach)
# ---------------------------------------------------------------------------

def _range_scores(hero_codes, board_codes, villain_ids):
    """Scores (N,) de los combos rivales legales y score del hero."""
    ids = np.asarray(villain_ids, dtype=np.intp)
    pairs = np.column_stack([COMBO0[ids], COMBO1[ids]])
    scores = evaluate_batch(pairs, [card_id(c) for c in board_codes])
    hero = evaluate_hand(hero_codes, board_codes)
    return hero, scores


def _weights_for(villain_reach, villain_ids):
    """Pesos normalizados (N,) sobre los combos rivales.

    - None        → uniforme (1/N)
    - RangeState  → reach_blocked[ids] (solo combos legales para él)
    - vector (1326,) → valores en bruto, normalizados sobre `ids`
    """
    n = len(villain_ids)
    if villain_reach is None:
        return np.full(n, 1.0 / n, dtype=np.float64)
    if isinstance(villain_reach, RangeState):
        w = villain_reach.reach_blocked[villain_ids].astype(np.float64)
    else:
        arr = np.asarray(villain_reach, dtype=np.float64)
        if arr.shape != (1326,):
            raise ValueError(f'reach debe tener forma (1326,), tiene {arr.shape}')
        w = arr[villain_ids]
    total = w.sum()
    if total <= 0:
        return np.zeros(n, dtype=np.float64)
    return w / total


def equity_vs_range(hero_codes, board_codes, villain_reach=None,
                    villain_ids=None):
    """Equity del hero vs el rango rival, ponderada por reach.

    Returns (equity, wins, ties, losses) en masa (fracciones de 1.0).

    hero_codes  : ['As', 'Kd']
    board_codes : 3..5 cartas
    villain_reach : None (uniforme) | RangeState | vector (1326,)
    villain_ids : restringir combos (p. ej. legal_hands(known)); por defecto
                  todos los que no chocan con hero+board.
    """
    ids = _legal_ids(hero_codes, board_codes, villain_ids)
    hero, scores = _range_scores(hero_codes, board_codes, ids)
    w = _weights_for(villain_reach, ids)
    wins = float((scores < hero) @ w)
    ties = float((scores == hero) @ w)
    losses = float((scores > hero) @ w)
    return wins + 0.5 * ties, wins, ties, losses


def hero_percentile(hero_codes, board_codes, villain_reach=None,
                    villain_ids=None):
    """Fracción del rango rival que el hero está ganando (incluye ties a medias)."""
    return equity_vs_range(hero_codes, board_codes, villain_reach, villain_ids)[0]


def _legal_ids(hero_codes, board_codes, villain_ids=None):
    if villain_ids is None:
        known = cards_to_bits(list(hero_codes) + list(board_codes))
        return legal_hands(known)
    return np.asarray(villain_ids, dtype=np.intp)


# ---------------------------------------------------------------------------
# Bote y stacks
# ---------------------------------------------------------------------------

def pot_odds(to_call, pot_before_call):
    """Odds mínimas para pagar con equity: to_call / (pot + to_call).

    `pot_before_call` = bote antes de poner las fichas del call.
    """
    if to_call <= 0:
        return 0.0
    if pot_before_call < 0:
        raise ValueError('el bote no puede ser negativo')
    return to_call / (pot_before_call + to_call)


def spr(stack_effective, pot):
    """Stack-to-pot ratio: stack efectivo / bote."""
    if pot <= 0:
        return None
    return stack_effective / pot


# ---------------------------------------------------------------------------
# Textura del board
# ---------------------------------------------------------------------------

def board_texture(board_codes):
    """Dict con features deterministas del board (3..5 cartas).

    - 'pairs'        : {rank: n_cartas} para ranks repetidos
    - 'trips'        : bool — trío sobre el board
    - 'flush_suits'  : {suit: n_cartas}
    - 'rainbow' / 'two_tone' / 'monotone' : bools (3+ cartas)
    - 'straight_run' : corrida de ranks consecutivos más larga (en length)
    """
    n = len(board_codes)
    if n not in (3, 4, 5):
        raise ValueError(f'board de 3..5 cartas, tiene {n}')
    ranks = [rank_of(card_id(c)) for c in board_codes]
    suits = [suit_of(card_id(c)) for c in board_codes]

    counts = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    pairs = {r: c for r, c in counts.items() if c >= 2}

    suit_counts = {}
    for s in suits:
        suit_counts[SUITS_LABEL[s]] = suit_counts.get(SUITS_LABEL[s], 0) + 1
    max_suit = max(suit_counts.values())

    seen = sorted(counts)
    run, best = 1, 1
    for a, b in zip(seen, seen[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)

    return {
        'cards': list(board_codes),
        'pairs': pairs,
        'trips': any(c == 3 for c in counts.values()),
        'flush_suits': suit_counts,
        'rainbow': max_suit == 1 and n >= 3,
        'two_tone': max_suit == 2 and n >= 3,
        'monotone': max_suit == n,
        'straight_run': best,
    }


# ---------------------------------------------------------------------------
# Situación completa
# ---------------------------------------------------------------------------

@dataclass
class Situation:
    """Snapshot inspeccionable del Situation Engine (para panel y Decision)."""
    hero_codes: tuple
    board_codes: tuple
    position: str = ''
    street: str = 'postflop'
    equity: float = 0.0
    wins: float = 0.0
    ties: float = 0.0
    losses: float = 0.0
    combos_evaluados: int = 0
    pot_odds: Optional[float] = None
    spr: Optional[float] = None
    texture: dict = field(default_factory=dict)


def situation(hero_codes, board_codes, villain_reach=None, villain_ids=None,
              pot_before_call=0.0, to_call=0.0, stack_effective=0.0,
              position='', street='postflop'):
    """Construye un `Situation` completo con los parámetros indicados."""
    ids = _legal_ids(hero_codes, board_codes, villain_ids)
    hero, scores = _range_scores(hero_codes, board_codes, ids)
    w = _weights_for(villain_reach, ids)
    wins = float((scores < hero) @ w)
    ties = float((scores == hero) @ w)
    losses = float((scores > hero) @ w)
    equity = wins + 0.5 * ties
    return Situation(
        hero_codes=tuple(hero_codes),
        board_codes=tuple(board_codes),
        position=position,
        street=street,
        equity=equity,
        wins=wins,
        ties=ties,
        losses=losses,
        combos_evaluados=len(ids),
        pot_odds=pot_odds(to_call, pot_before_call) if to_call > 0 else None,
        spr=spr(stack_effective, pot_before_call) if pot_before_call > 0 else None,
        texture=board_texture(board_codes),
    )
