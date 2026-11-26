"""Experimental, fail-closed tree for sequential multiway responses.

The tree accepts a response provider with explicit conditional evidence. It
does not fabricate a response prior. The currently available legacy response
models are exposed through an audit provider that abstains where their context
does not match the node (in particular sizing and prior-response history).
Nothing here is connected to live recommendation or action selection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import time
from typing import Mapping, Optional, Protocol, Sequence, Tuple

import numpy as np

from .mw_equity import (
    MultiwayEquityError, calculate_multiway_equity, sample_next_public_board,
)
from .hu_range_contracts import equity_to_showdown
from .mw_ranges import (
    MWRangeError, OpponentRangeState, condition_ranges_on_public_card,
    dead_cards_for_state,
)
from .pot_layers import PotLayerError, build_pot_layers


TREE_CONTRACT = 'mw_sequential_response_tree_v1'
_ACTIONS = ('fold', 'check', 'call', 'bet', 'raise', 'all_in')
_POSTFLOP_POSITIONS = ('SB', 'BB', 'UTG', 'MP', 'CO', 'BTN')
_STREET_SUCCESSOR = {'flop': 'turn', 'turn': 'river'}


class ResponseTreeError(ValueError):
    """Invalid tree input or response evidence."""


@dataclass(frozen=True, order=True)
class ActionSpec:
    """Action and additional chips committed at this node."""

    action: str
    amount: float = 0.0

    def __post_init__(self):
        if self.action not in _ACTIONS:
            raise ResponseTreeError('acción desconocida')
        if isinstance(self.amount, bool) or not isinstance(
                self.amount, (int, float)):
            raise ResponseTreeError('amount debe ser numérico')
        if not math.isfinite(float(self.amount)) or self.amount < 0:
            raise ResponseTreeError('amount debe ser finito y no negativo')
        if self.action in ('fold', 'check') and self.amount != 0:
            raise ResponseTreeError('fold/check no comprometen fichas')


@dataclass(frozen=True)
class ResponseOutcome:
    spec: ActionSpec
    probability: Optional[float]
    numerator: Optional[int]
    denominator: Optional[int]
    source: str
    coverage: str
    range_likelihood: object = None
    range_source: Optional[str] = None
    range_coverage: Optional[str] = None
    uncertainty: str = 'not_quantified'
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    ci_method: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.spec, ActionSpec):
            raise ResponseTreeError('outcome requiere ActionSpec')
        if not self.source:
            raise ResponseTreeError('respuesta requiere fuente')
        if self.probability is not None:
            if (isinstance(self.probability, bool)
                    or not isinstance(self.probability, (int, float))
                    or not math.isfinite(float(self.probability))
                    or not 0.0 < float(self.probability) <= 1.0):
                raise ResponseTreeError(
                    'probabilidad de rama debe estar en (0,1]; '
                    'cero requiere soporte estructural, no ausencia de datos')
        if self.numerator is not None and (
                isinstance(self.numerator, bool)
                or not isinstance(self.numerator, int) or self.numerator < 0):
            raise ResponseTreeError('numerator inválido')
        if self.denominator is not None and (
                isinstance(self.denominator, bool)
                or not isinstance(self.denominator, int) or self.denominator < 0):
            raise ResponseTreeError('denominator inválido')
        if self.coverage not in ('exact', 'alias', 'prior_only', 'unknown',
                                 'incomplete'):
            raise ResponseTreeError('coverage de respuesta inválida')
        if self.uncertainty not in ('quantified', 'not_quantified'):
            raise ResponseTreeError('uncertainty inválida')
        if self.range_likelihood is not None:
            if not self.range_source or self.range_coverage not in (
                    'exact', 'alias'):
                raise ResponseTreeError(
                    'range_likelihood necesita fuente y cobertura propia')
        elif self.range_source is not None or self.range_coverage is not None:
            raise ResponseTreeError(
                'metadata de range likelihood sin likelihood')
        if (self.ci_low is None) != (self.ci_high is None):
            raise ResponseTreeError('CI requiere ambos límites')
        if self.uncertainty == 'quantified':
            if (self.probability is None or self.ci_low is None
                    or not self.ci_method
                    or not math.isfinite(float(self.ci_low))
                    or not math.isfinite(float(self.ci_high))
                    or not (0 <= self.ci_low <= self.probability <= self.ci_high <= 1)):
                raise ResponseTreeError(
                    'incertidumbre cuantificada requiere CI y método')
        elif self.ci_low is not None or self.ci_high is not None \
                or self.ci_method is not None:
            raise ResponseTreeError('CI sin uncertainty=quantified')


@dataclass(frozen=True)
class ResponseDistribution:
    player_id: str
    context_key: str
    source: str
    source_kind: str
    outcomes: Tuple[ResponseOutcome, ...]
    conditional_on_history: bool
    action_space_complete: bool
    coverage: str
    uncertainty: str = 'not_quantified'
    reasons: Tuple[str, ...] = ()

    def __post_init__(self):
        if not self.player_id or not self.context_key or not self.source:
            raise ResponseTreeError('respuesta requiere identidad/contexto/fuente')
        if self.source_kind not in ('empirical', 'prior', 'synthetic'):
            raise ResponseTreeError('source_kind inválido')
        if self.coverage not in ('exact', 'alias', 'prior_only', 'unknown',
                                 'incomplete'):
            raise ResponseTreeError('coverage inválida')
        if len({outcome.spec for outcome in self.outcomes}) != len(self.outcomes):
            raise ResponseTreeError('ActionSpec duplicada en la distribución')
        if self.complete:
            for outcome in self.outcomes:
                if (outcome.numerator is None or outcome.denominator is None
                        or outcome.denominator <= 0
                        or outcome.numerator <= 0
                        or outcome.coverage not in ('exact', 'alias')):
                    raise ResponseTreeError(
                        'rama completa necesita soporte observado no nulo')
            ps = [float(o.probability) for o in self.outcomes]
            if not ps or abs(sum(ps) - 1.0) > 1e-9:
                raise ResponseTreeError('probabilidades completas deben sumar 1')
            denominators = {o.denominator for o in self.outcomes}
            if len(denominators) != 1:
                raise ResponseTreeError('denominador distinto entre ramas')
            denominator = next(iter(denominators))
            if sum(o.numerator for o in self.outcomes) != denominator:
                raise ResponseTreeError('conteos de ramas no suman el denominador')
            for outcome in self.outcomes:
                if abs(float(outcome.probability)
                       - outcome.numerator / outcome.denominator) > 1e-9:
                    raise ResponseTreeError(
                        'probabilidad no coincide con numerador/denominador')
            if self.coverage not in ('exact', 'alias'):
                raise ResponseTreeError('distribución completa sin cobertura')
        else:
            known = [o for o in self.outcomes
                     if o.numerator is not None and o.denominator is not None
                     and o.denominator > 0]
            if known and len({o.denominator for o in known}) == 1:
                if sum(o.numerator for o in known) > known[0].denominator:
                    raise ResponseTreeError('masa parcial excede denominador')

    @property
    def complete(self) -> bool:
        return (self.action_space_complete and self.conditional_on_history
                and self.source_kind in ('empirical', 'synthetic')
                and self.coverage in ('exact', 'alias')
                and bool(self.outcomes)
                and all(o.probability is not None for o in self.outcomes))

    @property
    def provisional(self) -> bool:
        return (self.source_kind != 'empirical'
                or self.uncertainty != 'quantified'
                or any(o.uncertainty != 'quantified' for o in self.outcomes))


@dataclass(frozen=True)
class ResponseAssessment:
    status: str
    distribution: Optional[ResponseDistribution]
    reason: Optional[str]
    evidence: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in ('available', 'incomplete', 'unavailable'):
            raise ResponseTreeError('assessment status inválido')
        if self.status == 'available' and self.distribution is None:
            raise ResponseTreeError('available requiere distribution')
        if self.status != 'available' and not self.reason:
            raise ResponseTreeError('assessment incompleto requiere reason')


@dataclass(frozen=True)
class ResponseContext:
    player_id: str
    position: Optional[str]
    profile: Optional[str]
    street: str
    board: Tuple[str, ...]
    pot: float
    to_call: float
    stack: float
    current_bet: float
    action_order: Tuple[str, ...]
    action_order_source: str
    pending_source: str
    statuses: Tuple[Tuple[str, str], ...]
    contributions: Tuple[Tuple[str, float], ...]
    stacks: Tuple[Tuple[str, float], ...]
    street_bets: Tuple[Tuple[str, float], ...]
    history: Tuple[Tuple[str, str, str, float, Optional[str]], ...]
    range_state: OpponentRangeState
    all_ranges: Tuple[Tuple[str, str, str, str], ...]
    all_range_states: Tuple[Tuple[str, OpponentRangeState], ...]
    legal_actions: Tuple[ActionSpec, ...]
    context_key: str


class ResponseProvider(Protocol):
    def assess(self, context: ResponseContext) -> ResponseAssessment:
        """Return branch probabilities and provenance for this exact node."""


class LegacyResponseProvider:
    """Audit adapter for current Oracle/PostflopRangeModel APIs.

    These models have useful action/bucket evidence, but neither a bet-size
    conditional distribution nor a joint response model conditioned on prior
    multiway responses. The adapter makes those gaps explicit rather than
    invoking ``OracleResponse``'s heuristic fallback.
    """

    def __init__(self, *, oracle=None, postflop_model=None,
                 profiles: Optional[Mapping[str, str]] = None):
        self.oracle = oracle
        self.postflop_model = postflop_model
        self.profiles = dict(profiles or {})

    def assess(self, context: ResponseContext) -> ResponseAssessment:
        profile = self.profiles.get(context.player_id)
        # No lookup is made: a generic ``bet``/``none`` proxy would silently
        # mismatch the Oracle's cbet/barrel/donk facing labels.
        return ResponseAssessment(
            status='incomplete', distribution=None,
            reason='legacy_response_context_insufficient',
            evidence={
                'player_id': context.player_id,
                'profile': profile,
                'oracle_api': ('profile/street/facing/texture'
                               if self.oracle is not None else None),
                'oracle_lookup_performed': False,
                'oracle_candidate_source': None,
                'oracle_candidate_support': None,
                'oracle_denominator': None,
                'oracle_minimum_cell_n': (
                    'cell n is returned; behavior_table default min_n=3'
                    if self.oracle is not None else None),
                'postflop_api': (
                    'profile/street/facing/bucket likelihood'
                    if self.postflop_model is not None else None),
                'postflop_model_available': self.postflop_model is not None,
                'postflop_alpha': getattr(self.postflop_model, 'alpha', None),
                'postflop_bucket_count': getattr(
                    self.postflop_model, 'n_buckets', None),
                'available_action_categories': ['check', 'bet', 'call',
                                                 'fold', 'raise'],
                'identity_scope': 'profile_group_not_individual_postflop',
                'postflop_bucket_evidence': None,
                'candidate_context': {
                    'street': context.street,
                    'facing_label': None,
                    'texture': None,
                    'amount_to_call': context.to_call,
                    'pot': context.pot,
                    'stack': context.stack,
                    'history_length': len(context.history),
                    'context_key': context.context_key,
                },
                'coverage': 'not_compatible_with_exact_response_node',
                'denominator': None,
                'uncertainty': 'not_quantified',
                'unmodeled': [
                    'bet_sizing_conditional',
                    'joint_response_conditioned_on_prior_opponent_actions',
                    'identity_specific_postflop_probability',
                    'all_in_response_category',
                ],
                'heuristic_fallback_used': False,
            })


@dataclass(frozen=True)
class MWTreeLimits:
    max_depth: int = 18
    max_nodes: int = 2_000
    max_branches_per_node: int = 32
    timeout_seconds: float = 2.0
    exact_equity: bool = True
    equity_samples: int = 20_000
    seed: int = 7
    max_exact_equity_work: int = 100_000
    runout_samples: int = 8

    def __post_init__(self):
        for name in ('max_depth', 'max_nodes', 'max_branches_per_node',
                     'equity_samples', 'max_exact_equity_work',
                     'runout_samples'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f'{name} debe ser entero positivo')
        if (not math.isfinite(self.timeout_seconds)
                or self.timeout_seconds <= 0):
            raise ValueError('timeout_seconds debe ser positivo')
        if not isinstance(self.exact_equity, bool):
            raise ValueError('exact_equity debe ser bool')


@dataclass(frozen=True)
class MWTreeInput:
    state: object
    ranges: Mapping[str, OpponentRangeState]
    street_bets: Mapping[str, float]
    action_order: Tuple[str, ...]
    pending_opponents: Tuple[str, ...]
    min_bet: float
    min_raise: float
    action_order_source: Optional[str]
    pending_source: Optional[str]
    response_sizes: Mapping[str, Mapping[str, Tuple[float, ...]]]
    hero_future_sizes: Mapping[str, Tuple[float, ...]] = field(default_factory=dict)
    profiles: Mapping[str, str] = field(default_factory=dict)
    action_space_complete: bool = False
    action_space_scope: Optional[str] = None

    def __post_init__(self):
        if not getattr(self.state, 'can_proceed_strategically', False):
            raise ResponseTreeError('estado no está listo para decisión del héroe')
        if self.state.sequence_complete.value is not True:
            raise ResponseTreeError('secuencia completa requerida para árbol')
        if self.action_order_source not in ('observed', 'inferred', 'synthetic'):
            raise ResponseTreeError('action_order_source desconocida')
        if self.pending_source not in ('observed', 'inferred', 'synthetic'):
            raise ResponseTreeError('pending_source desconocida')
        if self.action_space_complete and not self.action_space_scope:
            raise ResponseTreeError(
                'action_space_complete requiere declarar action_space_scope')
        if any(action.amount.source == 'unknown' for action in self.state.actions):
            raise ResponseTreeError('action amount unknown en historial')
        if any(action.facing.source == 'unknown' for action in self.state.actions):
            raise ResponseTreeError('action facing unknown en historial')
        if (self.state.to_call.source == 'unknown'
                or self.state.facing_action.source == 'unknown'
                or self.state.pot.source == 'unknown'):
            raise ResponseTreeError('pot/facing/to_call desconocido')
        if set(self.ranges) != {
                p.identity for p in self.state.active_opponents}:
            raise ResponseTreeError('rangos no coinciden con rivales activos')
        active_players = {p.identity: p for p in self.state.active_opponents}
        for identity, player in active_players.items():
            if player.position.source == 'unknown':
                raise ResponseTreeError(f'posición desconocida para {identity}')
            if self.ranges[identity].position != player.position.value:
                raise ResponseTreeError(f'posición/rango inconsistente para {identity}')
        for player in self.state.players:
            if player.stack.source == 'unknown' \
                    or player.contribution.source == 'unknown' \
                    or player.status.source == 'unknown':
                raise ResponseTreeError(
                    f'estado financiero incompleto para {player.identity}')
        active_can_act = {p.identity for p in self.state.active_opponents
                          if p.status.value == 'active'}
        if (len(set(self.action_order)) != len(self.action_order)
                or set(self.action_order) != active_can_act):
            raise ResponseTreeError('action_order debe incluir activos que pueden actuar')
        if (len(set(self.pending_opponents)) != len(self.pending_opponents)
                or set(self.pending_opponents) - active_can_act):
            raise ResponseTreeError('pending_opponents inválido')
        if set(self.street_bets) != {p.identity for p in self.state.players}:
            raise ResponseTreeError('street_bets debe incluir todos los jugadores')
        for player, amount in self.street_bets.items():
            _nonnegative(amount, f'street_bets[{player}]')
        hero = self.state.hero_id
        max_current_bet = max(
            (amount for identity, amount in self.street_bets.items()
             if next(p for p in self.state.players
                     if p.identity == identity).status.value != 'folded'),
            default=0.0)
        expected_to_call = max(
            0.0, max_current_bet - self.street_bets[hero])
        if not math.isclose(expected_to_call, self.state.to_call.value,
                            rel_tol=1e-9, abs_tol=1e-6):
            raise ResponseTreeError('to_call no coincide con street_bets')
        total_contributions = sum(
            p.contribution.value for p in self.state.players
            if p.contribution.source != 'unknown')
        if any(p.contribution.source == 'unknown' for p in self.state.players) \
                or not math.isclose(total_contributions, self.state.pot.value,
                                    rel_tol=1e-9, abs_tol=1e-6):
            raise ResponseTreeError('pot/contributions incompletos o inconsistentes')
        if tuple(p for p in self.action_order if p in self.pending_opponents) \
                != self.pending_opponents:
            raise ResponseTreeError('pending_opponents no respeta action_order')
        _positive(self.min_bet, 'min_bet')
        _positive(self.min_raise, 'min_raise')
        for player, action_sizes in self.response_sizes.items():
            if player not in active_can_act or not isinstance(action_sizes, Mapping):
                raise ResponseTreeError('response_sizes asociado a jugador inválido')
            for action, amounts in action_sizes.items():
                if action not in ('bet', 'raise'):
                    raise ResponseTreeError('solo se configuran bet/raise sizes')
                for amount in amounts:
                    _positive(amount, 'response size')
        for action, amounts in self.hero_future_sizes.items():
            if action not in ('bet', 'raise'):
                raise ResponseTreeError('hero_future_sizes solo bet/raise')
            for amount in amounts:
                _positive(amount, 'hero future size')
        for identity, range_state in self.ranges.items():
            if identity != range_state.identity or not range_state.usable_distribution:
                raise ResponseTreeError(f'rango incompleto/inconsistente: {identity}')
            if range_state.source_kind != 'known':
                applied = {update.event_index for update in range_state.updates
                           if update.event_index is not None}
                missing = [event.index for event in self.state.actions
                           if event.player_id == identity
                           and event.action not in ('fold', 'post')
                           and event.index not in applied]
                if missing:
                    raise ResponseTreeError(
                        f'rango de {identity} no refleja acciones {missing}')

    @property
    def input_uncertainty(self) -> Tuple[str, ...]:
        uncertain = []
        for player in self.state.players:
            for name in ('status', 'stack', 'contribution'):
                if getattr(player, name).source == 'inferred':
                    uncertain.append(f'{player.identity}:{name}_inferred')
        if self.state.pot.source == 'inferred':
            uncertain.append('pot_inferred')
        if self.state.to_call.source == 'inferred':
            uncertain.append('to_call_inferred')
        if self.state.hero.hole_cards.source == 'inferred':
            uncertain.append('hero_cards_inferred')
        if self.state.board_evidence.source == 'inferred':
            uncertain.append('board_inferred')
        if self.action_order_source != 'observed':
            uncertain.append('action_order_' + self.action_order_source)
        if self.pending_source != 'observed':
            uncertain.append('pending_' + self.pending_source)
        return tuple(uncertain)


@dataclass(frozen=True)
class MWActionTreeEV:
    action: ActionSpec
    status: str
    ev: Optional[float]
    reason: Optional[str]
    terminal_nodes: int
    covered_probability: float
    response_evidence: Tuple[Mapping[str, object], ...] = ()
    equity_error_bound: Optional[float] = None
    chance_evidence: Tuple[Mapping[str, object], ...] = ()


@dataclass(frozen=True)
class MWTreeResult:
    status: str
    actions: Tuple[MWActionTreeEV, ...]
    nodes: int
    elapsed_seconds: float
    limitations: Tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            'contract': TREE_CONTRACT,
            'status': self.status,
            'nodes': self.nodes,
            'elapsed_seconds': self.elapsed_seconds,
            'limitations': list(self.limitations),
            'actions': [{
                'action': a.action.action, 'amount': a.action.amount,
                'status': a.status, 'ev': a.ev, 'reason': a.reason,
                'terminal_nodes': a.terminal_nodes,
                'covered_probability': a.covered_probability,
                'equity_error_bound': a.equity_error_bound,
                'response_evidence': [dict(x) for x in a.response_evidence],
                'chance_evidence': [dict(x) for x in a.chance_evidence],
            } for a in self.actions],
        }


@dataclass
class _Game:
    statuses: dict
    contributions: dict
    street_bets: dict
    stacks: dict
    ranges: dict
    pending: tuple
    hero_added: float
    history: tuple
    min_raise: float
    next_event_index: int
    street: str
    board: tuple
    action_order: tuple
    action_order_source: str
    pending_source: str
    chance_trace: tuple
    chance_model_complete: bool


@dataclass(frozen=True)
class _Value:
    value: Optional[float]
    provisional: bool
    reason: Optional[str]
    terminals: int
    covered_probability: float
    equity_error_bound: Optional[float] = None


class _LimitReached(Exception):
    pass


def _nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(float(value)) or value < 0:
        raise ResponseTreeError(f'{name} debe ser finito y no negativo')
    return float(value)


def _positive(value, name):
    value = _nonnegative(value, name)
    if value <= 0:
        raise ResponseTreeError(f'{name} debe ser positivo')
    return value


def _call_amount(game: _Game, actor: str) -> float:
    current = max((amount for player, amount in game.street_bets.items()
                   if game.statuses[player] != 'folded'), default=0.0)
    return max(0.0, current - game.street_bets.get(actor, 0.0))


def _legal_kind_set(game: _Game, actor: str, min_bet: float,
                    min_raise: float, size_options):
    stack = game.stacks[actor]
    to_call = _call_amount(game, actor)
    legal = set()
    if to_call > 1e-9:
        legal.add('fold')
        if stack > 0:
            legal.add('call')
        if stack > to_call + 1e-9:
            legal.add('raise')
    else:
        legal.add('check')
        if stack > 0:
            legal.add('bet')
    if stack > 0:
        legal.add('all_in')
    for action, amounts in size_options.items():
        if action in ('bet', 'raise') and any(float(amount) > 0 for amount in amounts):
            legal.add(action)
    return legal


def _candidate_specs(game: _Game, actor: str, min_bet: float,
                     size_options: Mapping[str, Sequence[float]], *,
                     include_basics=True):
    stack = game.stacks[actor]
    to_call = _call_amount(game, actor)
    can_be_called = any(
        player != actor and status == 'active' and game.stacks[player] > 0
        for player, status in game.statuses.items())
    specs = []
    if include_basics:
        if to_call > 1e-9:
            specs.append(ActionSpec('fold', 0.0))
            if stack > to_call + 1e-9:
                specs.append(ActionSpec('call', to_call))
        else:
            specs.append(ActionSpec('check', 0.0))
    for action in ('bet', 'raise'):
        if not can_be_called:
            continue
        for raw_amount in size_options.get(action, ()):
            amount = float(raw_amount)
            if amount > 0 and amount <= stack + 1e-9:
                specs.append(ActionSpec(action, min(amount, stack)))
    if stack > 0 and (can_be_called or
                      (to_call > 0 and stack <= to_call + 1e-9)):
        specs.append(ActionSpec('all_in', stack))
    # Keep physically distinct response labels, but remove duplicate specs.
    return tuple(dict.fromkeys(specs))


def _apply(game: _Game, actor: str, spec: ActionSpec, *, hero_id: str,
           min_bet: float, allow_range_update=True,
           outcome: Optional[ResponseOutcome] = None,
           response_context_key: Optional[str] = None):
    if game.statuses[actor] != 'active':
        raise ResponseTreeError('jugador que ya no puede actuar')
    amount = _nonnegative(spec.amount, 'action amount')
    stack = game.stacks[actor]
    to_call = _call_amount(game, actor)
    current_bet = max((v for p, v in game.street_bets.items()
                       if game.statuses[p] != 'folded'), default=0.0)
    old_bet = game.street_bets[actor]
    old_current = current_bet
    if to_call > 1e-9:
        preceding_wager = next(
            (event for event in reversed(game.history)
             if event[0] == game.street and event[2] in ('bet', 'raise', 'all_in')),
            None)
        if preceding_wager is None:
            raise ResponseTreeError('facing_action_missing_from_tree_history')
        facing_before = preceding_wager[2]
    else:
        facing_before = 'none'
    can_be_called = any(
        player != actor and status == 'active' and game.stacks[player] > 0
        for player, status in game.statuses.items())
    if amount > stack + 1e-9:
        raise ResponseTreeError('acción supera stack restante')
    full_raise = False
    if spec.action == 'fold':
        if to_call <= 1e-9 or amount != 0:
            raise ResponseTreeError('fold ilegal sin cantidad que enfrentar')
        game.statuses[actor] = 'folded'
    elif spec.action == 'check':
        if to_call > 1e-9 or amount != 0:
            raise ResponseTreeError('check ilegal frente a apuesta')
    elif spec.action == 'call':
        if to_call <= 1e-9 or abs(amount - min(to_call, stack)) > 1e-8:
            raise ResponseTreeError('call amount no coincide con lo necesario')
        game.contributions[actor] += amount
        game.street_bets[actor] += amount
        game.stacks[actor] -= amount
        if game.stacks[actor] <= 1e-9:
            game.stacks[actor] = 0.0
            game.statuses[actor] = 'all_in'
    elif spec.action in ('bet', 'raise'):
        if not can_be_called:
            raise ResponseTreeError('no_active_opponent_can_call_bet')
        if spec.action == 'bet' and to_call > 1e-9:
            raise ResponseTreeError('bet ilegal; existe apuesta que enfrentar')
        if spec.action == 'raise' and to_call <= 1e-9:
            raise ResponseTreeError('raise ilegal sin apuesta vigente')
        new_bet = old_bet + amount
        increment = new_bet - old_current
        minimum = min_bet if spec.action == 'bet' else game.min_raise
        is_allin = amount >= stack - 1e-9
        if increment <= 1e-9 or (increment + 1e-9 < minimum and not is_allin):
            raise ResponseTreeError('bet/raise menor al mínimo legal')
        game.contributions[actor] += amount
        game.street_bets[actor] = new_bet
        game.stacks[actor] -= amount
        if game.stacks[actor] <= 1e-9:
            game.stacks[actor] = 0.0
            game.statuses[actor] = 'all_in'
        if increment + 1e-9 >= minimum:
            game.min_raise = increment
            full_raise = True
    elif spec.action == 'all_in':
        if stack <= 0 or abs(amount - stack) > 1e-8:
            raise ResponseTreeError('all-in debe comprometer el stack restante')
        new_bet = old_bet + amount
        increment = new_bet - old_current
        if to_call > 1e-9 and amount <= to_call + 1e-9:
            pass  # all-in call, including a short call
        else:
            if not can_be_called:
                raise ResponseTreeError('no_active_opponent_can_call_raise')
            minimum = min_bet if to_call <= 1e-9 else game.min_raise
            if increment <= 1e-9:
                raise ResponseTreeError('all-in no incrementa la apuesta')
            if increment + 1e-9 >= minimum:
                game.min_raise = increment
                full_raise = True
            # A short all-in raise is legal but does not reopen action.
        game.contributions[actor] += amount
        game.street_bets[actor] = new_bet
        game.stacks[actor] = 0.0
        game.statuses[actor] = 'all_in'
    else:
        raise ResponseTreeError('acción no implementada')

    if outcome is not None and actor != hero_id:
        range_state = game.ranges.get(actor)
        if range_state is not None and range_state.source_kind != 'known':
            if outcome.range_likelihood is None:
                raise ResponseTreeError('range_likelihood_missing')
            game.ranges[actor] = range_state.apply_action_likelihood(
                spec.action, outcome.range_likelihood,
                source=outcome.range_source,
                coverage=outcome.range_coverage,
                event_index=game.next_event_index,
                context_key=response_context_key,
                event_kind='simulated_response')
    if actor == hero_id:
        game.hero_added += amount
    game.history += ((game.street, actor, spec.action, amount, facing_before),)
    game.next_event_index += 1
    return full_raise


def _rotate_after(order: Tuple[str, ...], actor: str):
    if actor not in order:
        return order
    index = order.index(actor)
    return order[index + 1:] + order[:index + 1]


def _chance_seed(seed: int, game: _Game) -> int:
    ranges = tuple(sorted((identity,
                           hashlib.sha256(value.posterior.tobytes()).hexdigest())
                          for identity, value in game.ranges.items()))
    payload = repr((seed, game.street, game.board, game.history,
                    tuple(sorted(game.statuses.items())), ranges))
    digest = hashlib.sha256(payload.encode('utf-8')).digest()
    return (int(seed) + int.from_bytes(digest[:4], 'big')) & 0xFFFFFFFF


def _reopened_pending(game: _Game, order: Tuple[str, ...], actor: str,
                      full_raise: bool, previous_pending: Tuple[str, ...]):
    actionable = {p for p, status in game.statuses.items() if status == 'active'}
    if full_raise:
        return tuple(p for p in _rotate_after(order, actor)
                     if p in actionable and p != actor
                     and _call_amount(game, p) > 1e-9)
    return tuple(p for p in previous_pending
                 if p in actionable and p != actor
                 and _call_amount(game, p) > 1e-9)


def _outstanding_actor(order, pending):
    return next((p for p in pending if p in order), None)


def _context_key(game: _Game, actor: str, data: MWTreeInput, legal):
    player = next(p for p in data.state.players if p.identity == actor)
    range_state = game.ranges[actor]
    range_hash = hashlib.sha256(
        range_state.posterior.tobytes()).hexdigest()
    ranges_context = tuple(sorted((
        identity, current.source, current.coverage,
        hashlib.sha256(current.posterior.tobytes()).hexdigest())
        for identity, current in game.ranges.items()))
    return repr((
        game.street, game.board, actor,
        (player.position.value, player.position.source),
        data.profiles.get(actor), range_state.source, range_state.coverage,
        range_state.complete, range_hash, ranges_context,
        tuple(game.history), tuple(sorted(game.statuses.items())),
        tuple(sorted(game.contributions.items())),
        tuple(sorted(game.street_bets.items())),
        tuple(sorted(game.stacks.items())), sum(game.contributions.values()),
        _call_amount(game, actor), game.min_raise, tuple(legal),
        game.action_order, game.action_order_source, game.pending_source))


def _response_context(game: _Game, actor: str, data: MWTreeInput,
                      legal_actions: Tuple[ActionSpec, ...]):
    player = next(p for p in data.state.players if p.identity == actor)
    return ResponseContext(
        player_id=actor,
        position=(player.position.value if player.position.source != 'unknown'
                  else None),
        profile=data.profiles.get(actor), street=game.street,
        board=game.board,
        pot=sum(game.contributions.values()),
        to_call=_call_amount(game, actor), stack=game.stacks[actor],
        current_bet=max((amount for player, amount in game.street_bets.items()
                         if game.statuses[player] != 'folded'), default=0.0),
        action_order=game.action_order,
        action_order_source=game.action_order_source,
        pending_source=game.pending_source,
        statuses=tuple(sorted(game.statuses.items())),
        contributions=tuple(sorted(game.contributions.items())),
        stacks=tuple(sorted(game.stacks.items())),
        street_bets=tuple(sorted(game.street_bets.items())),
        history=game.history, range_state=game.ranges[actor],
        all_ranges=tuple(sorted((
            identity, range_state.source, range_state.coverage,
            hashlib.sha256(range_state.posterior.tobytes()).hexdigest())
            for identity, range_state in game.ranges.items())),
        all_range_states=tuple(sorted(game.ranges.items())),
        legal_actions=legal_actions,
        context_key=_context_key(game, actor, data, legal_actions))


def _new_game(data: MWTreeInput):
    state = data.state
    statuses, contributions, stacks = {}, {}, {}
    for player in state.players:
        if (player.status.source == 'unknown'
                or player.contribution.source == 'unknown'
                or player.stack.source == 'unknown'):
            raise ResponseTreeError(f'estado financiero incompleto: {player.identity}')
        statuses[player.identity] = player.status.value
        contributions[player.identity] = float(player.contribution.value)
        stacks[player.identity] = float(player.stack.value)
    for player, bet in data.street_bets.items():
        if bet > contributions[player] + 1e-9:
            raise ResponseTreeError('street bet excede contribución acumulada')
    return _Game(
        statuses=statuses, contributions=contributions,
        street_bets=dict(data.street_bets), stacks=stacks,
        ranges=dict(data.ranges), pending=(), hero_added=0.0,
        history=tuple((event.street, event.player_id, event.action,
                       float(event.amount.value), event.facing.value)
                      for event in state.actions),
        min_raise=float(data.min_raise),
        next_event_index=max((event.index for event in state.actions),
                             default=-1) + 1,
        street=state.street, board=tuple(state.board),
        action_order=tuple(data.action_order) + (state.hero_id,),
        action_order_source=data.action_order_source,
        pending_source=data.pending_source, chance_trace=(),
        chance_model_complete=True)


def _terminal_value(game: _Game, data: MWTreeInput, limits: MWTreeLimits,
                    hero_folded=False):
    hero = data.state.hero_id
    if hero_folded:
        return -game.hero_added, False, None, 0.0
    alive = [p for p, status in game.statuses.items() if status != 'folded']
    if len(alive) == 1 and alive[0] == hero:
        try:
            layers = build_pot_layers(
                game.contributions,
                folded={p for p, s in game.statuses.items() if s == 'folded'})
        except PotLayerError as exc:
            return None, False, f'pot_layers_invalid:{exc}', None
        payout = sum(layer.amount for layer in layers.pots
                     if hero in layer.eligible)
        payout += sum(amount for player, amount in layers.returned_uncalled
                      if player == hero)
        return payout - game.hero_added, False, None, 0.0
    actionable = sum(
        status == 'active' and game.stacks[player] > 0
        for player, status in game.statuses.items())
    no_future_betting = (game.street == 'river' or actionable <= 1)
    if not no_future_betting:
        return None, False, 'future_street_or_betting_tree_unmodeled', None
    try:
        layers = build_pot_layers(
            game.contributions,
            folded={p for p, s in game.statuses.items() if s == 'folded'})
    except PotLayerError as exc:
        return None, False, f'pot_layers_invalid:{exc}', None
    dead = dead_cards_for_state(data.state)
    expected = 0.0
    provisional = (not dead.complete or not game.chance_model_complete
                   or game.action_order_source != 'observed'
                   or game.pending_source != 'observed')
    equity_error_bound = 0.0
    for layer in layers.pots:
        if hero not in layer.eligible:
            continue
        eligible = [p for p in layer.eligible if p != hero]
        if not eligible:
            expected += layer.amount
            continue
        if any(p not in game.ranges or not game.ranges[p].usable_distribution
               for p in eligible):
            return None, False, 'eligible_range_incomplete', None
        # Players who block this side pot still hold cards and must remain in
        # the joint deal, although they cannot collect this particular layer.
        initially_folded = {
            p.identity for p in data.state.players if p.status.value == 'folded'}
        blockers = [p for p, status in game.statuses.items()
                    if p != hero and p not in eligible
                    and (status != 'folded' or p not in initially_folded)]
        if (len(eligible) == 1 and not blockers and not dead.known_cards
                and dead.complete):
            try:
                hu_equity = equity_to_showdown(
                    data.state.hero.hole_cards.value, game.board,
                    villain_reach=game.ranges[eligible[0]].posterior,
                    n_runouts=limits.equity_samples, n_combos=200,
                    seed=limits.seed)
            except (ValueError, TypeError) as exc:
                return None, False, f'hu_equity_unavailable:{exc}', None
            if hu_equity.value is None:
                return None, False, (
                    'hu_equity_unavailable:' +
                    str(hu_equity.uncertainty_reason)), None
            expected += layer.amount * hu_equity.value
            if hu_equity.method != 'river_exact' \
                    or hu_equity.uncertainty_reason:
                provisional = True
                equity_error_bound = None
            continue
        try:
            result = calculate_multiway_equity(
                data.state.hero.hole_cards.value, game.board,
                tuple(game.ranges[p].to_equity_range() for p in eligible),
                dead_cards=dead.known_cards, dead_ranges=tuple(
                    game.ranges[p].to_equity_range() for p in blockers),
                dead_cards_complete=dead.complete,
                exact=limits.exact_equity, samples=limits.equity_samples,
                seed=limits.seed, max_exact_work=limits.max_exact_equity_work)
        except (MultiwayEquityError, MWRangeError, ValueError) as exc:
            return None, False, f'equity_unavailable:{exc}', None
        expected += layer.amount * result.equity
        if result.standard_error is None:
            if not result.exact:
                equity_error_bound = None
        elif equity_error_bound is not None:
            equity_error_bound += layer.amount * result.standard_error
        provisional |= (not result.exact or bool(result.limitations)
                        or result.model ==
                        'independent_marginals_conditioned_on_no_card_collision')
    hero_returns = sum(amount for player, amount in layers.returned_uncalled
                       if player == hero)
    return (expected + hero_returns - game.hero_added, provisional, None,
            equity_error_bound)


def _next_street_order(game: _Game, data: MWTreeInput):
    """Infer postflop seat order from explicit positions; reject unknown seats."""
    participating = [p for p, status in game.statuses.items()
                     if status != 'folded']
    positions = {p.identity: p.position.value
                 for p in data.state.players if p.identity in participating
                 and p.position.source != 'unknown'}
    if set(positions) != set(participating) \
            or len(set(positions.values())) != len(positions):
        raise ResponseTreeError('postflop_position_order_unresolved')
    preflop_participants = {
        event.player_id for event in data.state.actions
        if event.street == 'preflop'
        and event.action in ('post', 'fold', 'call', 'bet', 'raise', 'all_in')}
    true_heads_up = (len(participating) == 2
                     and len(preflop_participants) == 2
                     and preflop_participants == set(participating))
    seats_only_two = (len(participating) == 2
                      and len(data.state.players) == 2)
    if true_heads_up or seats_only_two:
        button = next((p for p in participating
                       if positions[p] in ('BTN', 'SB')), None)
        big_blind = next((p for p in participating
                          if positions[p] == 'BB'), None)
        if button is None or big_blind is None or button == big_blind:
            raise ResponseTreeError('heads_up_button_order_unresolved')
        seat_order = (button, big_blind)
    else:
        if (len(participating) == 2 and len(data.state.players) > 2
                and len(preflop_participants) < 2):
            raise ResponseTreeError(
                'heads_up_vs_folded_field_order_ambiguous_without_preflop_history')
        unknown = set(positions.values()) - set(_POSTFLOP_POSITIONS)
        if unknown:
            raise ResponseTreeError(
                'postflop_positions_unsupported:' + ','.join(sorted(unknown)))
        seat_order = tuple(sorted(participating,
                                  key=lambda p: _POSTFLOP_POSITIONS.index(
                                      positions[p])))
    return tuple(p for p in seat_order
                 if game.statuses[p] == 'active' and game.stacks[p] > 0)


class _Solver:
    def __init__(self, data, provider, limits, deadline):
        self.data = data
        self.provider = provider
        self.limits = limits
        self.deadline = deadline
        self.nodes = 0
        self.response_traces = []
        self.chance_traces = []

    def _tick(self, depth):
        self.nodes += 1
        if self.nodes > self.limits.max_nodes:
            raise _LimitReached('max_nodes_exceeded')
        if depth > self.limits.max_depth:
            raise _LimitReached('max_depth_exceeded')
        if time.monotonic() > self.deadline:
            raise _LimitReached('timeout')

    def _response_sizes(self, actor):
        return self.data.response_sizes.get(actor, {})

    def _legal_specs(self, game, actor):
        options = self._response_sizes(actor)
        to_call = _call_amount(game, actor)
        stack = game.stacks[actor]
        other_can_call = any(
            player != actor and status == 'active' and game.stacks[player] > 0
            for player, status in game.statuses.items())
        if (other_can_call and to_call <= 1e-9 and stack > self.data.min_bet
                and not options.get('bet')):
            raise ResponseTreeError('response_bet_sizing_space_incomplete')
        if (other_can_call and to_call > 1e-9
                and stack > to_call + game.min_raise + 1e-9
                and not options.get('raise')):
            raise ResponseTreeError('response_raise_sizing_space_incomplete')
        return _candidate_specs(game, actor, self.data.min_bet, options)

    def _hero_specs(self, game):
        hero = self.data.state.hero_id
        return _candidate_specs(game, hero, self.data.min_bet,
                                self.data.hero_future_sizes)

    def _advance_street(self, game, depth):
        if game.street not in ('flop', 'turn'):
            value, provisional, reason, error_bound = _terminal_value(
                game, self.data, self.limits)
            return _Value(value, provisional, reason,
                          1 if value is not None else 0,
                          1.0 if value is not None else 0.0, error_bound)
        if (not self.limits.exact_equity
                and self.limits.runout_samples > self.limits.max_branches_per_node):
            return _Value(None, False, 'runout_sample_branch_limit_exceeded',
                          0, 0.0)
        dead = dead_cards_for_state(self.data.state)
        if not dead.complete:
            return _Value(None, False,
                          'folded_hole_cards_unknown_at_street_transition',
                          0, 0.0)
        hero = self.data.state.hero_id
        opponents = [p for p, status in game.statuses.items()
                     if p != hero and status != 'folded']
        initial_folded = {
            p.identity for p in self.data.state.players
            if p.status.value == 'folded'}
        dynamic_folded = [p for p, status in game.statuses.items()
                          if p != hero and status == 'folded'
                          and p not in initial_folded]
        if any(p not in game.ranges or not game.ranges[p].usable_distribution
               for p in opponents + dynamic_folded):
            return _Value(None, False, 'range_incomplete_at_street_transition',
                          0, 0.0)
        try:
            draw = sample_next_public_board(
                self.data.state.hero.hole_cards.value, game.board,
                tuple(game.ranges[p].to_equity_range() for p in opponents),
                dead_cards=dead.known_cards,
                dead_ranges=tuple(game.ranges[p].to_equity_range()
                                  for p in dynamic_folded),
                exact=self.limits.exact_equity,
                max_exact_work=self.limits.max_exact_equity_work,
                samples=self.limits.runout_samples,
                seed=_chance_seed(self.limits.seed, game),
                max_proposals=self.limits.runout_samples * 100)
        except (MultiwayEquityError, MWRangeError, ValueError) as exc:
            return _Value(None, False, f'public_card_sampling_failed:{exc}',
                          0, 0.0)
        if len(draw.boards) > self.limits.max_branches_per_node:
            return _Value(None, False, 'public_card_branch_limit_exceeded',
                          0, 0.0)
        next_street = _STREET_SUCCESSOR[game.street]
        try:
            action_order = _next_street_order(game, self.data)
        except ResponseTreeError as exc:
            return _Value(None, False, str(exc), 0, 0.0)
        counts = {}
        for public_cards in draw.boards:
            key = '|'.join(public_cards)
            counts[key] = counts.get(key, 0) + 1
        trace = {
            'from_street': game.street, 'to_street': next_street,
            'samples': draw.boards, 'probabilities': draw.probabilities,
            'exact': draw.exact, 'card_counts': counts,
            'proposals': draw.proposals,
            'rejected_blocker_deals': draw.rejected_blocker_deals,
            'seed': draw.seed, 'joint_model': draw.model,
            'action_order': action_order,
            'action_order_source': 'inferred_position_order',
        }
        self.chance_traces.append(trace)
        branch_values = []
        for public_cards in draw.boards:
            child = _clone(game)
            child.street = next_street
            child.board = tuple(game.board) + tuple(public_cards)
            try:
                for card in public_cards:
                    child.ranges = condition_ranges_on_public_card(
                        child.ranges, card)
            except MWRangeError as exc:
                branch_values.append(_Value(
                    None, False, f'range_blocker_update_failed:{exc}', 0, 0.0))
                continue
            child.street_bets = {player: 0.0 for player in child.statuses}
            child.min_raise = self.data.min_bet
            child.action_order = action_order
            child.action_order_source = 'inferred'
            child.pending_source = 'inferred'
            child.pending = action_order
            child.chance_trace += ((next_street, tuple(public_cards)),)
            child.chance_model_complete = (
                child.chance_model_complete and draw.exact
                and draw.model == 'single_opponent_marginal')
            branch_values.append(self.solve(child, depth + 1))
        terminals = sum(result.terminals for result in branch_values)
        covered_fraction = sum(
            probability * result.covered_probability
            for probability, result in zip(draw.probabilities, branch_values)
            if result.value is not None)
        if any(result.value is None for result in branch_values):
            reasons = sorted(set(result.reason for result in branch_values
                                 if result.value is None and result.reason))
            return _Value(None, False,
                          'public_card_branch_incomplete:' + ';'.join(reasons),
                          terminals, covered_fraction)
        values = np.asarray([result.value for result in branch_values],
                            dtype=np.float64)
        probabilities = np.asarray(draw.probabilities, dtype=np.float64)
        mean = float(np.dot(probabilities, values))
        sampling_error = (
            float(values.std(ddof=1) / math.sqrt(len(values)))
            if not draw.exact and len(values) > 1 else
            (0.0 if draw.exact else None))
        inner_errors = [result.equity_error_bound for result in branch_values]
        if sampling_error is None or any(error is None for error in inner_errors):
            error_bound = None
        else:
            error_bound = sampling_error + float(np.dot(probabilities, inner_errors))
        reasons = ({'public_card_enumeration'} if draw.exact else
                   {'public_card_sampling'})
        if draw.model == 'independent_marginals_conditioned_on_no_card_collision':
            reasons.add('independent_marginals_baseline')
        provisional = (not draw.exact
                       or draw.model ==
                       'independent_marginals_conditioned_on_no_card_collision'
                       or any(result.provisional for result in branch_values))
        return _Value(mean, provisional, ';'.join(sorted(reasons)),
                      terminals, 1.0, error_bound)

    def solve(self, game: _Game, depth=0):
        self._tick(depth)
        hero = self.data.state.hero_id
        if game.statuses[hero] == 'folded':
            value, provisional, reason, error_bound = _terminal_value(
                game, self.data, self.limits, hero_folded=True)
            return _Value(value, provisional, reason, 1, 1.0, error_bound)
        pending = tuple(p for p in game.pending
                        if game.statuses.get(p) == 'active')
        if not pending:
            active_with_stack = sum(
                status == 'active' and game.stacks[player] > 0
                for player, status in game.statuses.items())
            if (game.street in ('flop', 'turn')
                    and active_with_stack >= 2):
                return self._advance_street(game, depth)
            if game.street == 'preflop' and active_with_stack >= 2:
                return _Value(None, False,
                              'preflop_to_flop_transition_not_implemented',
                              0, 0.0)
            value, provisional, reason, error_bound = _terminal_value(
                game, self.data, self.limits)
            return _Value(value, provisional, reason, 1 if value is not None else 0,
                          1.0 if value is not None else 0.0, error_bound)
        actor = pending[0]
        tail = pending[1:]
        if actor == hero:
            if not self.data.action_space_complete:
                return _Value(None, False, 'hero_future_action_space_incomplete',
                              0, 0.0)
            to_call = _call_amount(game, hero)
            stack = game.stacks[hero]
            other_can_call = any(
                player != hero and status == 'active'
                and game.stacks[player] > 0
                for player, status in game.statuses.items())
            if (other_can_call and to_call <= 1e-9
                    and stack > self.data.min_bet
                    and not self.data.hero_future_sizes.get('bet')):
                return _Value(None, False,
                              'hero_future_bet_sizing_space_incomplete', 0, 0.0)
            if (other_can_call and to_call > 1e-9
                    and stack > to_call + game.min_raise + 1e-9
                    and not self.data.hero_future_sizes.get('raise')):
                return _Value(None, False,
                              'hero_future_raise_sizing_space_incomplete', 0, 0.0)
            specs = self._hero_specs(game)
            candidates = []
            for spec in specs:
                child = _clone(game)
                try:
                    full_raise = _apply(
                        child, actor, spec, hero_id=hero,
                        min_bet=self.data.min_bet)
                except ResponseTreeError:
                    continue
                child.pending = _reopened_pending(
                    child, child.action_order, actor,
                    full_raise, tail)
                candidates.append(self.solve(child, depth + 1))
            if not candidates or any(c.value is None for c in candidates):
                return _Value(None, False, 'hero_continuation_unresolved',
                              sum(c.terminals for c in candidates), 0.0)
            best = max(candidates, key=lambda c: c.value)
            return best

        try:
            legal_specs = self._legal_specs(game, actor)
        except ResponseTreeError as exc:
            return _Value(None, False, str(exc), 0, 0.0)
        context = _response_context(game, actor, self.data, legal_specs)
        if not self.data.action_space_complete:
            return _Value(None, False, 'opponent_action_space_not_exhaustive',
                          0, 0.0)
        try:
            assessment = self.provider.assess(context)
        except Exception as exc:
            self.response_traces.append({
                'player_id': actor, 'context_key': context.context_key,
                'status': 'provider_error',
                'reason': f'{type(exc).__name__}:{exc}',
                'history': list(game.history),
            })
            return _Value(None, False,
                          f'response_provider_error:{type(exc).__name__}',
                          0, 0.0)
        trace = {
            'player_id': actor, 'context_key': context.context_key,
            'status': assessment.status, 'reason': assessment.reason,
            'history': list(game.history),
            'action_order_source': context.action_order_source,
            'pending_source': context.pending_source,
            'position': context.position, 'profile': context.profile,
            'street': context.street, 'board': list(context.board),
            'pot': context.pot, 'to_call': context.to_call,
            'stack': context.stack, 'current_bet': context.current_bet,
            'action_order': list(context.action_order),
            'statuses': list(context.statuses),
            'contributions': list(context.contributions),
            'stacks': list(context.stacks),
            'street_bets': list(context.street_bets),
            'all_ranges': list(context.all_ranges),
            'range_update_provenance': {
                identity: [{
                    'action': update.action, 'source': update.source,
                    'coverage': update.coverage, 'status': update.status,
                    'event_index': update.event_index,
                    'context_key': update.context_key,
                    'event_kind': update.event_kind,
                } for update in range_state.updates]
                for identity, range_state in context.all_range_states
            },
            'legal_actions': [
                {'action': spec.action, 'amount': spec.amount}
                for spec in context.legal_actions],
            'evidence': dict(assessment.evidence or {}),
        }
        if assessment.distribution is not None:
            trace['distribution'] = {
                'source': assessment.distribution.source,
                'source_kind': assessment.distribution.source_kind,
                'coverage': assessment.distribution.coverage,
                'conditional_on_history':
                    assessment.distribution.conditional_on_history,
                'action_space_complete':
                    assessment.distribution.action_space_complete,
                'outcomes': [{
                    'action': o.spec.action, 'amount': o.spec.amount,
                    'probability': o.probability,
                    'numerator': o.numerator, 'denominator': o.denominator,
                    'source': o.source, 'coverage': o.coverage,
                    'range_source': o.range_source,
                    'range_coverage': o.range_coverage,
                    'uncertainty': o.uncertainty,
                } for o in assessment.distribution.outcomes],
            }
        self.response_traces.append(trace)
        self._tick(depth)  # soft timeout check after provider returns
        if assessment.status != 'available' or assessment.distribution is None:
            return _Value(None, False,
                          assessment.reason or 'response_distribution_unknown',
                          0, 0.0)
        distribution = assessment.distribution
        if (distribution.player_id != actor
                or distribution.context_key != context.context_key):
            return _Value(None, False, 'response_context_mismatch', 0, 0.0)
        if not distribution.complete:
            known = [o for o in distribution.outcomes
                     if o.probability is not None]
            denominators = {o.denominator for o in known
                            if o.denominator is not None and o.denominator > 0}
            covered = 0.0
            if len(denominators) == 1 and all(o.numerator is not None
                                               for o in known):
                denominator = next(iter(denominators))
                covered = min(1.0, sum(o.numerator for o in known) / denominator)
            return _Value(None, False,
                          ';'.join(distribution.reasons)
                          or 'response_distribution_incomplete', 0, covered)
        legal_set = set(legal_specs)
        observed_set = {outcome.spec for outcome in distribution.outcomes}
        if not distribution.action_space_complete or observed_set != legal_set:
            return _Value(None, False, 'response_action_space_not_exhaustive',
                          0, 0.0)
        if len(distribution.outcomes) > self.limits.max_branches_per_node:
            return _Value(None, False, 'max_branches_per_node_exceeded', 0, 0.0)
        branches = []
        for outcome in distribution.outcomes:
            if outcome.probability is None:
                branches.append((0.0, _Value(
                    None, False, 'response_probability_unknown', 0, 0.0)))
                continue
            child = _clone(game)
            try:
                full_raise = _apply(
                    child, actor, outcome.spec, hero_id=hero,
                    min_bet=self.data.min_bet, outcome=outcome,
                    response_context_key=distribution.context_key)
            except ResponseTreeError as exc:
                reason = (str(exc) if str(exc) == 'range_likelihood_missing'
                          else f'illegal_or_unmodeled_response:{exc}')
                branches.append((float(outcome.probability), _Value(
                    None, False, reason, 0, 0.0)))
                continue
            prior_pending = tail
            child.pending = _reopened_pending(
                child, child.action_order, actor,
                full_raise, prior_pending)
            if (actor != hero and child.ranges[actor].source_kind != 'known'
                    and not child.ranges[actor].usable_distribution):
                branches.append((float(outcome.probability), _Value(
                    None, False, 'range_likelihood_unavailable', 0, 0.0)))
            else:
                branches.append((float(outcome.probability),
                                 self.solve(child, depth + 1)))
        terminals = sum(result.terminals for _, result in branches)
        covered_probability = sum(
            p * result.covered_probability
            for p, result in branches if result.value is not None)
        if any(result.value is None for _, result in branches):
            reasons = sorted(set(result.reason for _, result in branches
                                 if result.value is None and result.reason))
            return _Value(None, False,
                          'unknown_branch:' + ';'.join(reasons), terminals,
                          covered_probability)
        expected = sum(p * result.value for p, result in branches)
        if all(result.equity_error_bound is not None for _, result in branches):
            error_bound = sum(
                p * result.equity_error_bound for p, result in branches)
        else:
            error_bound = None
        provisional = distribution.provisional or any(
            result.provisional for _, result in branches)
        return _Value(expected, provisional, None, terminals, 1.0,
                      error_bound)


def _clone(game):
    return _Game(
        statuses=dict(game.statuses), contributions=dict(game.contributions),
        street_bets=dict(game.street_bets), stacks=dict(game.stacks),
        ranges=dict(game.ranges), pending=tuple(game.pending),
        hero_added=game.hero_added, history=tuple(game.history),
        min_raise=game.min_raise, next_event_index=game.next_event_index,
        street=game.street, board=tuple(game.board),
        action_order=tuple(game.action_order),
        action_order_source=game.action_order_source,
        pending_source=game.pending_source,
        chance_trace=tuple(game.chance_trace),
        chance_model_complete=game.chance_model_complete)


def legal_hero_actions(data: MWTreeInput, *, raise_sizes=(), bet_sizes=()) \
        -> Tuple[ActionSpec, ...]:
    """Generate only legal root candidates; sizing choices are caller supplied."""
    game = _new_game(data)
    hero = data.state.hero_id
    options = {'bet': tuple(bet_sizes), 'raise': tuple(raise_sizes)}
    return _candidate_specs(game, hero, data.min_bet, options)


def evaluate_mw_action_tree(
        data: MWTreeInput, hero_actions: Sequence[ActionSpec], provider: ResponseProvider,
        *, limits: MWTreeLimits = MWTreeLimits()) -> MWTreeResult:
    """Evaluate each hero candidate via conditional sequential response nodes.

    Unknown branches remain unknown; their probability mass is never removed
    or used to renormalize other paths. The timeout is cooperative around
    provider calls (it cannot interrupt a blocking third-party provider).
    """
    if not isinstance(data, MWTreeInput):
        raise TypeError('data debe ser MWTreeInput')
    if provider is None or not callable(getattr(provider, 'assess', None)):
        raise TypeError('provider debe implementar assess(context)')
    if not hero_actions:
        raise ResponseTreeError('hero_actions vacío')
    started = time.monotonic()
    deadline = started + limits.timeout_seconds
    solver = _Solver(data, provider, limits, deadline)
    results = []
    limitations = set()
    for hero_action in hero_actions:
        trace_start = len(solver.response_traces)
        chance_start = len(solver.chance_traces)
        if not isinstance(hero_action, ActionSpec):
            raise TypeError('hero_actions debe contener ActionSpec')
        game = _new_game(data)
        try:
            full_raise = _apply(
                game, data.state.hero_id, hero_action,
                hero_id=data.state.hero_id, min_bet=data.min_bet)
        except ResponseTreeError as exc:
            results.append(MWActionTreeEV(
                hero_action, 'not_calculable', None,
                f'illegal_hero_action:{exc}', 0, 0.0,
                tuple(solver.response_traces[trace_start:]), None,
                tuple(solver.chance_traces[chance_start:])))
            continue
        # If the hero bet/raised, everyone in the response order must respond.
        # A call/check preserves only players who still had a turn at the
        # snapshot. Full raises later reopen the correct players in the solver.
        if hero_action.action == 'fold':
            value, provisional, reason, error_bound = _terminal_value(
                game, data, limits, hero_folded=True)
            results.append(MWActionTreeEV(
                hero_action, 'complete', value, reason, 1, 1.0,
                tuple(solver.response_traces[trace_start:]), error_bound,
                tuple(solver.chance_traces[chance_start:])))
            continue
        if full_raise:
            game.pending = tuple(
                p for p in game.action_order
                if p != data.state.hero_id
                if game.statuses[p] == 'active'
                and _call_amount(game, p) > 1e-9)
        else:
            game.pending = tuple(data.pending_opponents)
        try:
            value = solver.solve(game)
        except _LimitReached as exc:
            value = _Value(None, False, str(exc), 0, 0.0)
        if time.monotonic() > deadline:
            value = _Value(None, False, 'timeout', 0, 0.0)
        action_space_limited = bool(data.action_space_scope)
        input_uncertainty = data.input_uncertainty
        status = ('incomplete' if value.value is None else
                  'provisional'
                  if value.provisional or action_space_limited
                  or input_uncertainty else 'complete')
        reason = value.reason
        if action_space_limited:
            scope_reason = f'declared_action_space:{data.action_space_scope}'
            limitations.add(scope_reason)
            if reason is None:
                reason = scope_reason
        if input_uncertainty:
            limitations.update(input_uncertainty)
            if reason is None:
                reason = 'input_state_inferred:' + ','.join(input_uncertainty)
        if reason:
            limitations.add(reason)
        results.append(MWActionTreeEV(
            hero_action, status, value.value, reason,
            value.terminals, value.covered_probability,
            tuple(solver.response_traces[trace_start:]),
            value.equity_error_bound,
            tuple(solver.chance_traces[chance_start:])))
    statuses = {r.status for r in results}
    if 'incomplete' in statuses or 'not_calculable' in statuses:
        overall = 'incomplete'
    elif 'provisional' in statuses:
        overall = 'provisional'
    else:
        overall = 'complete'
    return MWTreeResult(
        overall, tuple(results), solver.nodes, time.monotonic() - started,
        tuple(sorted(limitations)))
