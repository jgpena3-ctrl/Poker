"""Per-opponent MW range state using the existing HU range contracts."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Optional, Sequence, Tuple

import numpy as np

from .cards import card_id
from .hu_range_contracts import EstimatedRange
from .mw_equity import (
    MultiwayEquityResult, OpponentRange, calculate_multiway_equity,
)
from .ranges import COMBO0, COMBO1, HAND_MASKS, N_COMBOS


class MWRangeError(ValueError):
    """A rival range is unknown, incomplete, or has invalid provenance."""


def _checked_cards(cards):
    cards = tuple(cards or ())
    if len(cards) not in (0, 2):
        raise MWRangeError('known hole cards debe tener cero o dos cartas')
    ids = tuple(card_id(c) for c in cards)
    if len(set(ids)) != len(ids):
        raise MWRangeError('known hole cards repetidas')
    return cards


@dataclass(frozen=True)
class RangeUpdate:
    action: str
    source: Optional[str]
    coverage: str
    status: str
    reason: Optional[str] = None
    event_index: Optional[int] = None
    context_key: Optional[str] = None
    event_kind: str = 'observed'

    def __post_init__(self):
        if self.event_kind not in ('observed', 'already_conditioned',
                                   'simulated_response', 'simulated_board'):
            raise MWRangeError('event_kind de RangeUpdate inválido')


@dataclass(frozen=True)
class ActionLikelihood:
    source: Optional[str]
    coverage: str
    weights: Optional[np.ndarray]
    player_id: str
    action: str
    street: str
    position: str
    board: Tuple[str, ...]
    facing: Optional[str]
    amount: float
    context_key: str

    def __post_init__(self):
        if not self.player_id or self.action not in (
                'check', 'bet', 'call', 'raise', 'all_in', 'fold', 'post'):
            raise MWRangeError('ActionLikelihood requiere jugador/acción válidos')
        if self.street not in ('preflop', 'flop', 'turn', 'river'):
            raise MWRangeError('ActionLikelihood street inválida')
        if not self.position or not self.context_key:
            raise MWRangeError('likelihood requiere posición y context_key')
        if self.facing not in (None, 'check', 'bet', 'raise', 'all_in'):
            raise MWRangeError('ActionLikelihood facing inválido')
        if isinstance(self.amount, bool) or not isinstance(self.amount, (int, float)) \
                or not np.isfinite(self.amount) or self.amount < 0:
            raise MWRangeError('ActionLikelihood amount inválido')
        if self.coverage not in ('exact', 'alias', 'coverage_gap',
                                 'impossible', 'unknown'):
            raise MWRangeError('ActionLikelihood coverage inválida')
        if self.weights is not None and not self.source:
            raise MWRangeError('likelihood disponible requiere source')


@dataclass(frozen=True)
class DeadCardInfo:
    known_cards: Tuple[str, ...]
    folded_with_unknown_cards: Tuple[str, ...]

    @property
    def complete(self):
        return not self.folded_with_unknown_cards


@dataclass(frozen=True)
class OpponentRangeState:
    identity: str
    position: Optional[str]
    posterior: np.ndarray
    source: str
    source_kind: str
    coverage: str
    complete: bool
    known_cards: Tuple[str, ...] = ()
    updates: Tuple[RangeUpdate, ...] = ()

    def __post_init__(self):
        if not isinstance(self.identity, str) or not self.identity.strip():
            raise MWRangeError('identidad estable del rival requerida')
        if not isinstance(self.source, str) or not self.source.strip():
            raise MWRangeError('procedencia requerida')
        if self.source_kind not in ('estimated', 'prior', 'known', 'synthetic'):
            raise MWRangeError('source_kind inválido')
        if self.coverage not in ('exact', 'alias', 'coverage_gap',
                                 'impossible', 'unknown'):
            raise MWRangeError('coverage inválida')
        arr = np.asarray(self.posterior, dtype=np.float64).copy()
        if arr.shape != (N_COMBOS,) or not np.all(np.isfinite(arr)) \
                or np.any(arr < 0):
            raise MWRangeError('posterior inválido')
        scale = float(arr.max())
        if scale <= 0:
            raise MWRangeError('posterior sin masa')
        arr /= scale
        arr /= float(arr.sum())
        arr.setflags(write=False)
        object.__setattr__(self, 'posterior', arr)
        object.__setattr__(self, 'known_cards', _checked_cards(self.known_cards))
        if self.complete and self.coverage not in ('exact', 'alias'):
            raise MWRangeError('rango completo requiere cobertura exact/alias')

    @classmethod
    def from_estimated(cls, identity: str, position: Optional[str],
                       estimated: EstimatedRange, *, known_cards=()
                       ) -> 'OpponentRangeState':
        if not isinstance(estimated, EstimatedRange):
            raise TypeError('estimated debe ser EstimatedRange')
        if estimated.player != identity:
            raise MWRangeError(
                f'EstimatedRange de {estimated.player} no corresponde a {identity}')
        if not estimated.usable or estimated.posterior is None:
            raise MWRangeError(
                'estimated range incompleto: %s' %
                (estimated.empty_reason or estimated.empty_status))
        cards = _checked_cards(known_cards)
        weights = np.asarray(estimated.posterior, dtype=np.float64).copy()
        complete = estimated.coverage in ('exact', 'alias')
        if cards:
            weights = _restrict_to_known_combo(weights, cards)
        return cls(
            identity=identity, position=position, posterior=weights,
            source=(f'estimated:{estimated.prior_source}:'
                    f'{estimated.prior_key}:{estimated.likelihood_model}'),
            source_kind=('prior' if estimated.prior_source in
                         ('flat', 'preflop_table', 'profile_template',
                          'alias', 'fallback', 'manual') else 'estimated'),
            coverage=estimated.coverage, complete=complete,
            known_cards=cards)

    @classmethod
    def from_known_cards(cls, identity: str, position: Optional[str],
                         cards: Sequence[str], *, source: str
                         ) -> 'OpponentRangeState':
        cards = _checked_cards(cards)
        if len(cards) != 2:
            raise MWRangeError('dos cartas conocidas requeridas')
        weights = np.zeros(N_COMBOS, dtype=np.float64)
        idx = _combo_index(*cards)
        weights[idx] = 1.0
        return cls(identity, position, weights, source, 'known', 'exact', True,
                   cards)

    @property
    def usable_distribution(self) -> bool:
        return self.complete and float(self.posterior.sum()) > 0

    def apply_action_likelihood(
            self, action: str, likelihood: Optional[Sequence[float]], *,
            source: Optional[str], coverage: str,
            event_index: Optional[int] = None,
            context_key: Optional[str] = None,
            event_kind: str = 'observed') -> 'OpponentRangeState':
        """Update only this opponent; absent evidence marks it incomplete."""
        if not action:
            raise MWRangeError('acción observada requerida')
        if likelihood is None:
            update = RangeUpdate(
                action, source, coverage, 'incomplete',
                'action_likelihood_unavailable', event_index, context_key,
                event_kind)
            return self._copy(
                self.posterior, self.complete and False, coverage,
                self.source + f'|{action}:unavailable', self.updates + (update,))
        if not source or coverage not in ('exact', 'alias', 'coverage_gap',
                                           'impossible', 'unknown'):
            raise MWRangeError('likelihood requiere fuente y cobertura válida')
        values = np.asarray(likelihood, dtype=np.float64)
        if values.shape != (N_COMBOS,) or not np.all(np.isfinite(values)) \
                or np.any(values < 0) or np.any(values > 1.0 + 1e-12):
            raise MWRangeError('likelihood debe estar en [0,1]')
        updated = self.posterior * values
        total = float(updated.sum())
        complete = self.complete and coverage in ('exact', 'alias') and total > 0
        if total > 0:
            updated /= total
        else:
            # Preserve a valid normalized vector for diagnostics, but mark it
            # unusable; never turn a zero-likelihood observation into a prior.
            updated = self.posterior.copy()
        reason = None if complete else (
            'zero_mass_after_action_likelihood' if total <= 0 else
            'action_likelihood_coverage_incomplete')
        update = RangeUpdate(
            action, source, coverage,
            'complete' if complete else 'incomplete', reason,
            event_index, context_key, event_kind)
        return self._copy(updated, complete, coverage,
                          self.source + f'|{action}:{source}',
                          self.updates + (update,))

    def to_equity_range(self) -> OpponentRange:
        if not self.usable_distribution:
            raise MWRangeError(
                f'rango de {self.identity} incompleto/no utilizable: '
                f'coverage={self.coverage}')
        return OpponentRange(self.identity, self.posterior, self.source,
                             self.source_kind)

    def condition_on_public_card(self, card: str, *,
                                 event_index: Optional[int] = None
                                 ) -> 'OpponentRangeState':
        """Remove combos blocked by a newly dealt public card."""
        card_idx = card_id(card)
        blocked = (HAND_MASKS & (1 << card_idx)) != 0
        posterior = self.posterior.copy()
        posterior[blocked] = 0.0
        if float(posterior.max()) <= 0:
            raise MWRangeError(
                f'board card {card} vacía el rango de {self.identity}')
        context = f'public_card:{card}'
        update = RangeUpdate(
            'board_card', 'public_board', self.coverage,
            'conditioned', None, event_index, context, 'simulated_board')
        return self._copy(
            posterior, self.complete, self.coverage,
            self.source + '|' + context, self.updates + (update,))

    def _copy(self, posterior, complete, coverage, source, updates):
        return OpponentRangeState(
            identity=self.identity, position=self.position,
            posterior=posterior, source=source, source_kind=self.source_kind,
            coverage=coverage, complete=complete,
            known_cards=self.known_cards, updates=updates)


def update_range_for_action(
        ranges: Mapping[str, OpponentRangeState], player_id: str, action: str,
        likelihood: Optional[Sequence[float]], *, source: Optional[str],
        coverage: str, event_index: Optional[int] = None,
        context_key: Optional[str] = None,
        event_kind: str = 'observed') -> dict:
    """Return a mapping with exactly the acting player's range updated."""
    if player_id not in ranges:
        raise MWRangeError(f'rango no encontrado para actor {player_id}')
    updated = dict(ranges)
    updated[player_id] = ranges[player_id].apply_action_likelihood(
        action, likelihood, source=source, coverage=coverage,
        event_index=event_index, context_key=context_key,
        event_kind=event_kind)
    return updated


def condition_ranges_on_public_card(
        ranges: Mapping[str, OpponentRangeState], card: str, *,
        event_index: Optional[int] = None) -> dict:
    """Apply a community-card blocker to every tracked rival independently."""
    if not ranges:
        raise MWRangeError('sin rangos para bloquear con la carta pública')
    return {
        identity: range_state.condition_on_public_card(
            card, event_index=event_index)
        for identity, range_state in ranges.items()
    }


def build_ranges_from_state(state, initial_ranges: Mapping[str, EstimatedRange],
                            action_likelihoods: Mapping[int, ActionLikelihood],
                            *, conditioned_action_indices=None):
    """Build one range per active rival and replay only that rival's actions.

    ``action_likelihoods`` is keyed by action-sequence index. Missing
    likelihood marks that actor's range incomplete; it never means a neutral
    likelihood. Revealed hole cards create a deterministic known-card range.
    ``conditioned_action_indices`` explicitly identifies events already
    included in an initial posterior; those events are recorded, not applied
    twice.
    """
    if not getattr(state, 'ready', False):
        raise MWRangeError('estado MW no está resuelto')
    active = {p.identity: p for p in state.active_opponents}
    conditioned_action_indices = dict(conditioned_action_indices or {})
    if set(initial_ranges) - set(active):
        raise MWRangeError('rango inicial asociado a un jugador no activo')
    events_by_index = {event.index: event for event in state.actions}
    if set(action_likelihoods) - set(events_by_index):
        raise MWRangeError('likelihood asociado a acción inexistente')
    for identity, indices in conditioned_action_indices.items():
        if identity not in active:
            raise MWRangeError('condicionamiento declarado para jugador no activo')
        for index in indices:
            if index not in events_by_index \
                    or events_by_index[index].player_id != identity:
                raise MWRangeError(
                    'acción ya condicionada no coincide con identidad/índice')
    ranges = {}
    for identity, player in active.items():
        position = (player.position.value
                    if player.position.source != 'unknown' else None)
        if player.hole_cards.source == 'inferred' and player.hole_cards.value:
            raise MWRangeError(
                f'cartas inferidas de {identity} no pueden cerrar su rango')
        if player.hole_cards.source == 'observed' and player.hole_cards.value:
            ranges[identity] = OpponentRangeState.from_known_cards(
                identity, position, player.hole_cards.value,
                source='observed_hole_cards')
            continue
        estimated = initial_ranges.get(identity)
        if estimated is None:
            raise MWRangeError(f'rango inicial ausente para {identity}')
        if not isinstance(estimated, EstimatedRange):
            raise TypeError(f'rango inicial de {identity} debe ser EstimatedRange')
        if estimated.player != identity:
            raise MWRangeError(
                f'EstimatedRange de {estimated.player} no corresponde a {identity}')
        if estimated.street != state.street or tuple(estimated.board) != tuple(
                state.board):
            raise MWRangeError(
                f'EstimatedRange de {identity} pertenece a otra calle/board')
        ranges[identity] = OpponentRangeState.from_estimated(
            identity, position, estimated)

    for event in state.actions:
        if event.player_id not in ranges or event.action == 'fold':
            continue
        if event.index in set(conditioned_action_indices.get(event.player_id, ())):
            old = ranges[event.player_id]
            update = RangeUpdate(
                event.action, 'initial_range_provenance', old.coverage,
                'already_conditioned', None, event.index,
                event_kind='already_conditioned')
            ranges[event.player_id] = old._copy(
                old.posterior, old.complete, old.coverage,
                old.source + f'|{event.action}:already_conditioned',
                old.updates + (update,))
            continue
        if event.action == 'post':
            continue
        if ranges[event.player_id].source_kind == 'known':
            # Exact revealed cards dominate the behavioral likelihood. A
            # missing likelihood cannot make a known combo probabilistic.
            continue
        likelihood = action_likelihoods.get(event.index)
        if likelihood is None:
            ranges = update_range_for_action(
                ranges, event.player_id, event.action, None,
                source=None, coverage='unknown', event_index=event.index)
            continue
        if not isinstance(likelihood, ActionLikelihood):
            raise TypeError('action likelihood debe ser ActionLikelihood')
        if event.amount.source == 'unknown' or event.facing.source == 'unknown':
            ranges = update_range_for_action(
                ranges, event.player_id, event.action, None,
                source=None, coverage='unknown', event_index=event.index)
            continue
        expected_position = ranges[event.player_id].position
        if (likelihood.player_id != event.player_id
                or likelihood.action != event.action
                or likelihood.street != event.street
                or likelihood.position != expected_position
                or tuple(likelihood.board) != tuple(state.board)
                or not math.isclose(float(likelihood.amount),
                                    float(event.amount.value),
                                    rel_tol=1e-9, abs_tol=1e-9)
                or likelihood.facing != event.facing.value):
            raise MWRangeError(
                f'likelihood/contexto no corresponde a evento {event.index}')
        ranges = update_range_for_action(
            ranges, event.player_id, event.action, likelihood.weights,
            source=likelihood.source, coverage=likelihood.coverage,
            event_index=event.index, context_key=likelihood.context_key)
    if state.sequence_complete.value is not True:
        for identity, range_state in tuple(ranges.items()):
            if range_state.source_kind != 'known':
                ranges = update_range_for_action(
                    ranges, identity, 'sequence_incomplete', None,
                    source=None, coverage='unknown')
    return ranges


def ranges_for_state(state, ranges: Mapping[str, OpponentRangeState]):
    """Validate exact active-opponent coverage and return equity marginals.

    Folded players must be absent. All-in players remain in the deal/range
    set but have no action opportunity. No fallback range is synthesized.
    """
    if not getattr(state, 'ready', False):
        raise MWRangeError('estado MW no está resuelto')
    active = {p.identity: p for p in state.active_opponents}
    if set(ranges) != set(active):
        raise MWRangeError(
            'rangos deben corresponder exactamente a rivales activos: '
            f'estado={sorted(active)}, rangos={sorted(ranges)}')
    output = []
    for identity, player in active.items():
        range_state = ranges[identity]
        if range_state.identity != identity:
            raise MWRangeError(f'identidad/rango inconsistente para {identity}')
        if player.position.source == 'unknown':
            raise MWRangeError(f'posición de {identity} no está observada')
        if range_state.position != player.position.value:
            raise MWRangeError(f'posición/rango inconsistente para {identity}')
        output.append(range_state.to_equity_range())
    return tuple(output)


def dead_cards_for_state(state) -> DeadCardInfo:
    """Separate observed muck blockers from folded seats with unknown cards."""
    if not getattr(state, 'ready', False):
        raise MWRangeError('estado MW no está resuelto')
    known, unknown = [], []
    for player in state.players:
        if player.identity == state.hero_id or player.status.value != 'folded':
            continue
        if player.hole_cards.source == 'observed' and player.hole_cards.value:
            known.extend(player.hole_cards.value)
        elif player.hole_cards.source == 'inferred' and player.hole_cards.value:
            unknown.append(player.identity)
        else:
            unknown.append(player.identity)
    return DeadCardInfo(tuple(known), tuple(unknown))


def calculate_state_equity(state, ranges: Mapping[str, OpponentRangeState], *,
                           exact: bool = False, samples: int = 10_000,
                           seed: int = 7, max_exact_work: int = 100_000,
                           max_proposals: Optional[int] = None
                           ) -> MultiwayEquityResult:
    """Integrated state -> per-rival marginals -> blocker-safe equity.

    Folded cards are included as dead blockers when observed. If folded hole
    cards remain unknown, the numeric equity is returned with an explicit
    limitation and must not be treated as a complete model result.
    """
    if not getattr(state, 'can_proceed_strategically', False):
        raise MWRangeError('estado MW no permite cálculo estratégico')
    hero = state.hero
    if hero is None or hero.hole_cards.source == 'unknown' \
            or len(hero.hole_cards.value) != 2:
        raise MWRangeError('cartas del héroe desconocidas')
    opponents = ranges_for_state(state, ranges)
    dead = dead_cards_for_state(state)
    limitations = []
    if state.board_evidence.source == 'inferred':
        limitations.append('board_inferred')
    if hero.hole_cards.source == 'inferred':
        limitations.append('hero_hole_cards_inferred')
    if state.hero.status.source == 'inferred':
        limitations.append('hero_status_inferred')
    if any(player.status.source == 'inferred'
           for player in state.active_opponents):
        limitations.append('active_player_status_inferred')
    return calculate_multiway_equity(
        hero.hole_cards.value, state.board, opponents, exact=exact,
        dead_cards=dead.known_cards, dead_cards_complete=dead.complete,
        model_limitations=limitations, samples=samples, seed=seed,
        max_exact_work=max_exact_work, max_proposals=max_proposals)


def _combo_index(card_a, card_b):
    return _combo_index_ids(card_id(card_a), card_id(card_b))


def _combo_index_ids(a, b):
    a, b = sorted((int(a), int(b)))
    matches = np.flatnonzero((COMBO0 == a) & (COMBO1 == b))
    if matches.size != 1:
        raise MWRangeError('combo exacto no localizado')
    return int(matches[0])


def _restrict_to_known_combo(weights, cards):
    ids = [card_id(c) for c in cards]
    legal = (HAND_MASKS & ((1 << ids[0]) | (1 << ids[1]))) == \
        ((1 << ids[0]) | (1 << ids[1]))
    # An exact reveal is deterministic evidence, even if the prior assigned
    # that combo zero mass; it is not a generic prior or a showdown sample.
    out = np.zeros(N_COMBOS, dtype=np.float64)
    index = _combo_index_ids(*ids)
    out[index] = float(weights[index]) if weights[index] > 0 else 1.0
    if not legal[index]:
        raise MWRangeError('known combo inválido')
    return out
