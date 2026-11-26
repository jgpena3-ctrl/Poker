"""Joint multiway range sampling and showdown equity (experimental core).

This module is deliberately not wired into recommendation/serving.  It treats
each opponent range as a separate marginal and uses their product, conditioned
on a legal deal, as an explicitly labelled independent-baseline joint model.
It never combines ranges with ``RangeState.union`` and never interprets an
observed hand as a probability distribution.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
import math
from typing import Optional, Sequence, Tuple

import numpy as np

from .cards import card_id, card_label
from .hand_evaluator import evaluate_five_batch
from .ranges import COMBO0, COMBO1, HAND_MASKS, N_COMBOS


class MultiwayEquityError(ValueError):
    """Invalid or unsupported inputs; callers should abstain, not fall back."""


@dataclass(frozen=True)
class OpponentRange:
    """A marginal distribution for exactly one named, active opponent.

    ``weights`` may be unnormalized reach. ``source_kind`` distinguishes
    estimated distributions, explicit priors, and synthetic test fixtures;
    observed combos/statistics are intentionally not accepted as such.
    """

    identity: str
    weights: np.ndarray
    source: str
    source_kind: str = 'estimated'

    def __post_init__(self):
        if not isinstance(self.identity, str) or not self.identity.strip():
            raise MultiwayEquityError('cada rival requiere identidad estable')
        if not isinstance(self.source, str) or not self.source.strip():
            raise MultiwayEquityError('cada rango requiere procedencia')
        if self.source_kind not in ('estimated', 'prior', 'synthetic', 'known'):
            raise MultiwayEquityError(
                'source_kind debe ser estimated, prior, synthetic o known; '
                'ObservedRange/ActionStatistics no son distribuciones')
        try:
            weights = np.asarray(self.weights, dtype=np.float64).copy()
        except (TypeError, ValueError) as exc:
            raise MultiwayEquityError('pesos del rango inválidos') from exc
        if weights.shape != (N_COMBOS,):
            raise MultiwayEquityError(
                f'cada rango debe tener {N_COMBOS} pesos, recibió {weights.shape}')
        if not np.all(np.isfinite(weights)) or np.any(weights < 0):
            raise MultiwayEquityError('pesos deben ser finitos y no negativos')
        if float(weights.max()) <= 0:
            raise MultiwayEquityError('rango sin masa positiva')
        weights.setflags(write=False)
        object.__setattr__(self, 'weights', weights)


@dataclass(frozen=True)
class MultiwayEquityResult:
    equity: float
    exact: bool
    opponents: Tuple[str, ...]
    model: str
    samples: int
    proposals: int
    rejected_blocker_proposals: int
    valid_joint_assignments: Optional[int]
    rejected_joint_assignments: Optional[int]
    valid_joint_mass: Optional[float]
    removed_combos_by_known_blockers: Tuple[int, ...]
    runouts_per_assignment: int
    standard_error: Optional[float]
    dead_cards: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    blocking_players: Tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            'equity': self.equity,
            'exact': self.exact,
            'opponents': list(self.opponents),
            'joint_model': self.model,
            'samples': self.samples,
            'proposals': self.proposals,
            'rejected_blocker_proposals': self.rejected_blocker_proposals,
            'valid_joint_assignments': self.valid_joint_assignments,
            'rejected_joint_assignments': self.rejected_joint_assignments,
            'valid_joint_mass': self.valid_joint_mass,
            'removed_combos_by_known_blockers': list(
                self.removed_combos_by_known_blockers),
            'runouts_per_assignment': self.runouts_per_assignment,
            'standard_error': self.standard_error,
            'dead_cards': list(self.dead_cards),
            'limitations': list(self.limitations),
            'blocking_players': list(self.blocking_players),
        }


@dataclass(frozen=True)
class PublicCardSamples:
    cards: Tuple[str, ...]
    probabilities: Tuple[float, ...]
    exact: bool
    proposals: int
    rejected_blocker_deals: int
    seed: int
    model: str


@dataclass(frozen=True)
class PublicBoardSamples:
    boards: Tuple[Tuple[str, ...], ...]
    probabilities: Tuple[float, ...]
    exact: bool
    proposals: int
    rejected_blocker_deals: int
    seed: int
    model: str


def _ids(cards: Sequence[str], label: str, allowed_lengths) -> Tuple[int, ...]:
    if not isinstance(cards, (tuple, list)):
        raise MultiwayEquityError(f'{label} debe ser lista/tupla de cartas')
    if len(cards) not in allowed_lengths:
        raise MultiwayEquityError(f'{label} tiene longitud inválida: {len(cards)}')
    try:
        ids = tuple(card_id(c) for c in cards)
    except (TypeError, ValueError) as exc:
        raise MultiwayEquityError(f'{label} contiene una carta inválida') from exc
    if len(set(ids)) != len(ids):
        raise MultiwayEquityError(f'{label} repite cartas')
    return ids


def _prepare(hero_hand, board, opponents, dead_cards, dead_ranges=()):
    hero = _ids(hero_hand, 'hero_hand', (2,))
    board_ids = _ids(board, 'board', (0, 3, 4, 5))
    dead_ids = _ids(dead_cards, 'dead_cards', tuple(range(53)))
    if set(hero) & set(board_ids):
        raise MultiwayEquityError('hero y board contienen cartas repetidas')
    if set(dead_ids) & (set(hero) | set(board_ids)):
        raise MultiwayEquityError('dead_cards solapa hero o board')
    opponents = tuple(opponents)
    dead_ranges = tuple(dead_ranges)
    if len(opponents) < 1:
        raise MultiwayEquityError('se requiere al menos un rival')
    if any(not isinstance(r, OpponentRange) for r in opponents):
        raise MultiwayEquityError('cada rival debe tener su propio OpponentRange')
    if any(not isinstance(r, OpponentRange) for r in dead_ranges):
        raise MultiwayEquityError('cada blocker range debe ser OpponentRange')
    identities = [r.identity for r in opponents + dead_ranges]
    if len(set(identities)) != len(identities):
        raise MultiwayEquityError('identidades de rivales duplicadas')

    known_mask = sum(1 << c for c in hero + board_ids + dead_ids)
    legal = (HAND_MASKS & known_mask) == 0
    ids_by_range, p_by_range, removed = [], [], []
    all_ranges = opponents + dead_ranges
    for opponent in all_ranges:
        positive = opponent.weights > 0
        kept = positive & legal
        ids = np.flatnonzero(kept)
        if ids.size == 0:
            raise MultiwayEquityError(
                f"rango de {opponent.identity} vacío tras blockers conocidos")
        masses = opponent.weights[ids]
        ids_by_range.append(ids)
        scaled = masses / float(masses.max())
        p_by_range.append(scaled / scaled.sum())
        removed.append(int(np.count_nonzero(positive & ~legal)))
    return (hero, board_ids, dead_ids, opponents, dead_ranges,
            ids_by_range, p_by_range, tuple(removed))


def _score7(two_cards, board5):
    """Evaluate seven cards without invoking the evaluator's disk-cache writer."""
    cards = tuple(two_cards) + tuple(board5)
    scores = []
    for five in combinations(cards, 5):
        scores.append(five)
    return int(evaluate_five_batch(np.asarray(scores, dtype=np.intp)).max())


def _share(hero, villains, board5):
    hero_score = _score7(hero, board5)
    scores = [_score7(v, board5) for v in villains]
    best = max([hero_score] + scores)
    if hero_score != best:
        return 0.0
    return 1.0 / (1 + sum(score == best for score in scores))


def _cards_for_combo(index):
    return int(COMBO0[index]), int(COMBO1[index])


def _runout_count(n_known, n_opponents, n_dead=0):
    missing = 5 - n_known
    # n_known counts board cards; the two hero cards also leave the deck.
    remaining = 52 - 2 - n_known - n_dead - 2 * n_opponents
    if missing < 0 or remaining < missing:
        raise MultiwayEquityError('no quedan cartas suficientes para el runout')
    return math.comb(remaining, missing)


def calculate_multiway_equity(
        hero_hand: Sequence[str], board: Sequence[str],
        opponents: Sequence[OpponentRange], *, exact: bool = False,
        dead_cards: Sequence[str] = (),
        dead_ranges: Sequence[OpponentRange] = (),
        dead_cards_complete: bool = True,
        model_limitations: Sequence[str] = (),
        samples: int = 10_000, seed: int = 7,
        max_exact_work: int = 100_000,
        max_proposals: Optional[int] = None) -> MultiwayEquityResult:
    """Compute hero's multiway showdown share against separate ranges.

    The joint baseline is ``independent_marginals_conditioned_on_no_card
    _collision``. Exact mode enumerates all supported joint assignments and
    all runouts; Monte Carlo uses rejection sampling from that same conditional
    distribution and reports its standard error. Limits fail closed.
    """
    (hero, board_ids, dead_ids, opponents, dead_ranges, ids_by_range,
     p_by_range, removed) = _prepare(
         hero_hand, board, opponents, dead_cards, dead_ranges)
    if not isinstance(exact, bool):
        raise MultiwayEquityError('exact debe ser bool')
    if not isinstance(dead_cards_complete, bool):
        raise MultiwayEquityError('dead_cards_complete debe ser bool')
    if isinstance(max_exact_work, bool) or not isinstance(max_exact_work, int) \
            or max_exact_work < 1:
        raise MultiwayEquityError('max_exact_work debe ser entero positivo')
    if any(not isinstance(item, str) or not item
           for item in (model_limitations or ())):
        raise MultiwayEquityError('model_limitations debe contener razones')
    all_ranges = opponents + dead_ranges
    runout_count = _runout_count(len(board_ids), len(all_ranges), len(dead_ids))
    deck_known = set(hero) | set(board_ids) | set(dead_ids)
    missing = 5 - len(board_ids)
    limitations = list(model_limitations or ())
    if not dead_cards_complete:
        limitations.append('unobserved_folded_hole_cards_not_integrated')
    limitations = tuple(sorted(set(limitations)))
    joint_model = (
        'independent_marginals_conditioned_on_no_card_collision'
        if len(all_ranges) > 1 else 'single_opponent_marginal')

    if exact:
        upper_assignments = math.prod(len(ids) for ids in ids_by_range)
        work_bound = upper_assignments * runout_count
        if work_bound > max_exact_work:
            raise MultiwayEquityError(
                f'enumeración exacta excede límite: {work_bound} > '
                f'{max_exact_work}; usar muestreo explícito o abstenerse')
        ranges_by_id = [dict(zip(ids.tolist(), probs.tolist()))
                        for ids, probs in zip(ids_by_range, p_by_range)]
        deck = [c for c in range(52) if c not in deck_known]
        total_share = 0.0
        total_mass = 0.0
        valid_assignments = rejected_assignments = 0
        eligible_count = len(opponents)
        for assignment in product(*ids_by_range):
            hole_cards = [_cards_for_combo(int(idx)) for idx in assignment]
            used = set(deck_known)
            legal_assignment = True
            for hand in hole_cards:
                if used.intersection(hand):
                    legal_assignment = False
                    break
                used.update(hand)
            if not legal_assignment:
                rejected_assignments += 1
                continue
            valid_assignments += 1
            mass = math.prod(ranges_by_id[i][int(idx)]
                             for i, idx in enumerate(assignment))
            total_mass += mass
            runout_deck = [c for c in deck if c not in used]
            boards = (combinations(runout_deck, missing) if missing else [()])
            for runout in boards:
                total_share += mass * _share(
                    hero, hole_cards[:eligible_count],
                    board_ids + tuple(runout))
        if valid_assignments == 0 or total_mass <= 0:
            raise MultiwayEquityError(
                'los rangos no admiten ninguna asignación conjunta válida')
        return MultiwayEquityResult(
            equity=total_share / (total_mass * runout_count), exact=True,
            opponents=tuple(r.identity for r in opponents),
            model=joint_model,
            samples=valid_assignments * runout_count,
            proposals=valid_assignments + rejected_assignments,
            rejected_blocker_proposals=rejected_assignments,
            valid_joint_assignments=valid_assignments,
            rejected_joint_assignments=rejected_assignments,
            valid_joint_mass=total_mass,
            removed_combos_by_known_blockers=removed,
            runouts_per_assignment=runout_count, standard_error=0.0,
            dead_cards=tuple(dead_cards or ()), limitations=limitations,
            blocking_players=tuple(r.identity for r in dead_ranges))

    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
        raise MultiwayEquityError('samples debe ser entero positivo')
    if max_proposals is None:
        max_proposals = max(samples * 100, samples + 1)
    if isinstance(max_proposals, bool) or not isinstance(max_proposals, int) \
            or max_proposals < samples:
        raise MultiwayEquityError('max_proposals debe ser >= samples')
    rng = np.random.default_rng(seed)
    deck = np.arange(52, dtype=np.int16)
    shares = np.empty(samples, dtype=np.float64)
    proposals = rejected = accepted = 0
    while accepted < samples and proposals < max_proposals:
        proposals += 1
        assignment = [int(rng.choice(ids, p=probs))
                      for ids, probs in zip(ids_by_range, p_by_range)]
        hole_cards = [_cards_for_combo(idx) for idx in assignment]
        used = set(deck_known)
        collision = False
        for hand in hole_cards:
            if used.intersection(hand):
                collision = True
                break
            used.update(hand)
        if collision:
            rejected += 1
            continue
        if missing:
            remaining = np.asarray([c for c in deck if int(c) not in used],
                                   dtype=np.int16)
            runout = tuple(int(c) for c in rng.choice(
                remaining, size=missing, replace=False))
        else:
            runout = ()
        shares[accepted] = _share(
            hero, hole_cards[:len(opponents)], board_ids + runout)
        accepted += 1
    if accepted != samples:
        raise MultiwayEquityError(
            f'muestreo condicionado incompleto: {accepted}/{samples} muestras '
            f'en {proposals} propuestas; {rejected} rechazadas por blockers')
    return MultiwayEquityResult(
        equity=float(shares.mean()), exact=False,
        opponents=tuple(r.identity for r in opponents),
        model=joint_model,
        samples=samples, proposals=proposals,
        rejected_blocker_proposals=rejected, valid_joint_assignments=None,
        rejected_joint_assignments=None, valid_joint_mass=None,
        removed_combos_by_known_blockers=removed,
        runouts_per_assignment=runout_count,
        standard_error=(float(shares.std(ddof=1) / math.sqrt(samples))
                        if samples > 1 else None),
        dead_cards=tuple(dead_cards or ()), limitations=limitations,
        blocking_players=tuple(r.identity for r in dead_ranges))


def sample_next_public_board(
        hero_hand: Sequence[str], board: Sequence[str],
        opponents: Sequence[OpponentRange], *,
        dead_cards: Sequence[str] = (),
        dead_ranges: Sequence[OpponentRange] = (),
        exact: bool = False, max_exact_work: int = 100_000,
        samples: int = 1, seed: int = 7,
        max_proposals: Optional[int] = None) -> PublicBoardSamples:
    """Sample or enumerate the next flop/turn public card under the joint deal.

    Private hands are jointly sampled from separate marginals conditioned on
    legal blockers, then the public card is dealt uniformly from the remaining
    deck. Preflop-to-flop is not part of this experimental scope.
    """
    hero, board_ids, dead_ids, _eligible, _dead, ids_by, probs_by, _removed = \
        _prepare(hero_hand, board, opponents, dead_cards, dead_ranges)
    all_ranges = tuple(opponents) + tuple(dead_ranges)
    if not isinstance(exact, bool):
        raise MultiwayEquityError('exact debe ser bool')
    if isinstance(max_exact_work, bool) or not isinstance(max_exact_work, int) \
            or max_exact_work < 1:
        raise MultiwayEquityError('max_exact_work debe ser entero positivo')
    if len(board_ids) not in (3, 4):
        raise MultiwayEquityError('board debe estar en flop o turn')
    n_to_deal = 1
    all_known = set(hero) | set(board_ids) | set(dead_ids)
    n_remaining = 52 - len(all_known) - 2 * len(all_ranges)
    if n_remaining < n_to_deal:
        raise MultiwayEquityError('no quedan cartas suficientes para la calle')
    model = ('independent_marginals_conditioned_on_no_card_collision'
             if len(all_ranges) > 1 else 'single_opponent_marginal')

    if exact:
        runouts_per_deal = math.comb(n_remaining, n_to_deal)
        work = math.prod(len(ids) for ids in ids_by) * runouts_per_deal
        if work > max_exact_work:
            raise MultiwayEquityError(
                f'enumeración exacta de board excede límite: {work} > '
                f'{max_exact_work}')
        ranges_by_id = [dict(zip(ids.tolist(), probs.tolist()))
                        for ids, probs in zip(ids_by, probs_by)]
        deck = set(range(52))
        board_mass = {}
        valid_mass = 0.0
        proposals = rejected = 0
        for assignment in product(*ids_by):
            proposals += 1
            private = [_cards_for_combo(int(idx)) for idx in assignment]
            used = set(all_known)
            legal_assignment = True
            for hand in private:
                if used.intersection(hand):
                    legal_assignment = False
                    break
                used.update(hand)
            if not legal_assignment:
                rejected += 1
                continue
            mass = math.prod(ranges_by_id[i][int(idx)]
                             for i, idx in enumerate(assignment))
            remaining = sorted(deck - used)
            runouts = math.comb(len(remaining), n_to_deal)
            if not runouts:
                continue
            valid_mass += mass
            per_runout_mass = mass / runouts
            for public_cards in combinations(remaining, n_to_deal):
                key = tuple(int(c) for c in public_cards)
                board_mass[key] = board_mass.get(key, 0.0) + per_runout_mass
        if valid_mass <= 0:
            raise MultiwayEquityError(
                'no hay joint deal válido para la siguiente calle')
        boards = tuple(tuple(card_label(c) for c in key)
                       for key in sorted(board_mass))
        probabilities = tuple(board_mass[key] / valid_mass
                              for key in sorted(board_mass))
        return PublicBoardSamples(
            boards=boards, probabilities=probabilities, exact=True,
            proposals=proposals, rejected_blocker_deals=rejected,
            seed=seed, model=model)

    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
        raise MultiwayEquityError('samples debe ser entero positivo')
    if max_proposals is None:
        max_proposals = max(samples * 100, samples + 1)
    if isinstance(max_proposals, bool) or not isinstance(max_proposals, int) \
            or max_proposals < samples:
        raise MultiwayEquityError('max_proposals debe ser >= samples')
    rng = np.random.default_rng(seed)
    deck = set(range(52))
    output = []
    proposals = rejected = 0
    while len(output) < samples and proposals < max_proposals:
        proposals += 1
        assignment = [int(rng.choice(ids, p=probs))
                      for ids, probs in zip(ids_by, probs_by)]
        private = [_cards_for_combo(idx) for idx in assignment]
        used = set(all_known)
        collision = False
        for hand in private:
            if used.intersection(hand):
                collision = True
                break
            used.update(hand)
        if collision:
            rejected += 1
            continue
        remaining = np.asarray(sorted(deck - used), dtype=np.int16)
        public_cards = tuple(sorted(int(c) for c in rng.choice(
            remaining, size=n_to_deal, replace=False)))
        output.append(tuple(card_label(c) for c in public_cards))
    if len(output) != samples:
        raise MultiwayEquityError(
            f'muestreo de board incompleto: {len(output)}/{samples} en '
            f'{proposals} propuestas; {rejected} deals bloqueados')
    return PublicBoardSamples(
        boards=tuple(output), probabilities=tuple(1.0 / samples
                                                 for _ in output),
        exact=False, proposals=proposals,
        rejected_blocker_deals=rejected, seed=seed, model=model)


def sample_next_public_card(
        hero_hand: Sequence[str], board: Sequence[str],
        opponents: Sequence[OpponentRange], *,
        dead_cards: Sequence[str] = (),
        dead_ranges: Sequence[OpponentRange] = (),
        exact: bool = False, max_exact_work: int = 100_000,
        samples: int = 1, seed: int = 7,
        max_proposals: Optional[int] = None) -> PublicCardSamples:
    """Compatibility API for a single turn/river card."""
    if len(board) not in (3, 4):
        raise MultiwayEquityError('next public card solo aplica a flop/turn')
    sampled = sample_next_public_board(
        hero_hand, board, opponents, dead_cards=dead_cards,
        dead_ranges=dead_ranges, exact=exact,
        max_exact_work=max_exact_work, samples=samples, seed=seed,
        max_proposals=max_proposals)
    return PublicCardSamples(
        cards=tuple(runout[0] for runout in sampled.boards),
        probabilities=sampled.probabilities, exact=sampled.exact,
        proposals=sampled.proposals,
        rejected_blocker_deals=sampled.rejected_blocker_deals,
        seed=sampled.seed, model=sampled.model)
