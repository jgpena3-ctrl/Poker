"""Capa pura de evaluación HU (HU-P4, experimental).

No activa live ni serving. Conecta el contexto preflop canónico con el
contrato de EV, conservando la procedencia y la incertidumbre.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

import math

from .hu_ev import EVInput, EVResult, VillainResponse, calculate_ev
from .hu_range_contracts import (
    EstimatedRange, GenericPrior, ObservedRange, equity_to_showdown)
from .preflop_canonical import CanonicalPreflopDecision


CONTRACT = 'hu_evaluation_v1'


@dataclass(frozen=True)
class HUEvaluationInput:
    canonical: CanonicalPreflopDecision
    pot: float
    to_call: float = 0.0
    hero_stack: float = 0.0
    villain_stack: float = 0.0
    equity: Optional[float] = None
    coverage: str = 'unknown'
    coverage_reason: Optional[str] = None
    response: Optional[VillainResponse] = None
    bet_fractions: Tuple[float, ...] = (0.25, 0.5, 0.75)
    allow_all_in: bool = True
    range_kind: Optional[str] = None
    range_source: Optional[str] = None
    range_provenance: Optional[Mapping[str, Any]] = None
    equity_scenario: Optional[str] = None
    response_equities: Optional[Mapping[str, Any]] = None
    metadata: Optional[Mapping[str, Any]] = None
    hero_hand: Optional[Tuple[str, str]] = None
    board: Tuple[str, ...] = ()
    villain_range: Any = None
    response_ranges: Optional[Mapping[str, Any]] = None
    equity_n_runouts: int = 100
    equity_n_combos: int = 200
    equity_seed: int = 7

    def __post_init__(self):
        for name in ('pot', 'to_call', 'hero_stack', 'villain_stack'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f'{name} debe ser numérico')
            value = float(value)
            if value < 0 or not math.isfinite(value):
                raise ValueError(f'{name} debe ser finito y no negativo')
        if self.equity is not None:
            if isinstance(self.equity, bool) or not isinstance(self.equity,
                                                              (int, float)):
                raise ValueError('equity debe ser numérica o None')
            if not math.isfinite(float(self.equity)) or not 0.0 <= float(
                    self.equity) <= 1.0:
                raise ValueError('equity debe estar en [0,1]')
        if self.response is not None and not isinstance(self.response,
                                                       VillainResponse):
            raise TypeError('response debe ser VillainResponse o None')
        if not isinstance(self.canonical, CanonicalPreflopDecision):
            raise TypeError('canonical debe ser CanonicalPreflopDecision')
        if self.range_provenance is not None:
            object.__setattr__(self, 'range_provenance',
                               dict(self.range_provenance))
        if self.response_equities is not None:
            object.__setattr__(self, 'response_equities',
                               dict(self.response_equities))
        if self.metadata is not None:
            object.__setattr__(self, 'metadata', dict(self.metadata))
        if self.hero_hand is not None:
            if (not isinstance(self.hero_hand, tuple) or len(self.hero_hand) != 2
                    or any(not isinstance(c, str) or not c for c in self.hero_hand)):
                raise ValueError('hero_hand debe tener 2 cartas')
        if not isinstance(self.board, tuple):
            raise ValueError('board debe ser tupla')
        if self.response_ranges is not None:
            object.__setattr__(self, 'response_ranges',
                               dict(self.response_ranges))
        if self.range_kind is not None and self.range_kind not in (
                'observed', 'estimated', 'prior', 'statistics', 'unknown'):
            raise ValueError('range_kind inválido')


@dataclass(frozen=True)
class HUEvaluationResult:
    status: str
    canonical_status: str
    legal_actions: Tuple[str, ...]
    ev_result: Optional[EVResult]
    uncertainty_reasons: Tuple[str, ...]
    supported: bool
    trace: dict
    comparable: bool = False
    comparability_reasons: Tuple[str, ...] = ()
    selection_status: str = 'none'
    best_action: Optional[str] = None
    provisional_best_action: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            'contract': CONTRACT,
            'status': self.status,
            'canonical_status': self.canonical_status,
            'legal_actions': list(self.legal_actions),
            'ev': self.ev_result.as_dict() if self.ev_result is not None else None,
            'uncertainty_reasons': list(self.uncertainty_reasons),
            'supported': self.supported,
            'trace': self.trace,
            'comparable': self.comparable,
            'comparability_reasons': list(self.comparability_reasons),
            'selection_status': self.selection_status,
            'best_action': self.best_action,
            'provisional_best_action': self.provisional_best_action,
        }


def _equity_compatible(inp: HUEvaluationInput) -> bool:
    return _equity_compatible_with(inp, inp.response_equities, inp.equity)


def _equity_compatible_with(inp: HUEvaluationInput,
                            response_equities, equity) -> bool:
    if not response_equities:
        return True
    values = [v for v in response_equities.values() if v is not None]
    if equity is None:
        return not values
    return all(
        (isinstance(v, (int, float)) and not isinstance(v, bool)
         and abs(float(v) - float(equity)) <= 1e-12)
        for v in values)


def _range_reach(range_obj):
    if range_obj is None:
        return None
    if isinstance(range_obj, ObservedRange):
        return None
    if isinstance(range_obj, EstimatedRange):
        return range_obj.posterior if range_obj.usable else None
    if isinstance(range_obj, GenericPrior):
        return range_obj.vector
    if hasattr(range_obj, 'posterior') and getattr(range_obj, 'posterior',
                                                  None) is not None:
        return range_obj.posterior
    if hasattr(range_obj, 'vector'):
        return range_obj.vector
    if hasattr(range_obj, 'reach'):
        return range_obj.reach
    return None


def _compute_range_equity(inp: HUEvaluationInput, range_obj, hero_hand, board):
    reach = _range_reach(range_obj)
    if reach is None:
        return None, 'range_not_usable_for_equity'
    if hero_hand is None:
        return None, 'hero_hand_required_for_range_equity'
    try:
        result = equity_to_showdown(
            hero_hand, board, villain_reach=reach,
            n_runouts=inp.equity_n_runouts,
            n_combos=inp.equity_n_combos,
            seed=inp.equity_seed)
    except (ValueError, TypeError):
        return None, 'range_equity_calculation_failed'
    if result.value is None:
        return None, (result.uncertainty_reason or
                      'range_equity_unavailable')
    return float(result.value), (result.uncertainty_reason or
                                 'range_equity_available')


def evaluate_hu(inp: HUEvaluationInput) -> HUEvaluationResult:
    if not isinstance(inp, HUEvaluationInput):
        raise TypeError('inp debe ser HUEvaluationInput')

    reasons = []
    if inp.canonical.status != 'resolved':
        reasons.append(f'canonical_{inp.canonical.status}')

    equity = inp.equity
    coverage = inp.coverage
    coverage_reason = inp.coverage_reason
    equity_scenario = inp.equity_scenario
    if inp.villain_range is None and coverage != 'usable':
        reasons.append(coverage_reason or 'equity_coverage_not_usable')
    computed_response_equities = dict(inp.response_equities or {})

    # Integracion de rangos: la equity se calcula desde el rango cuando es
    # posible; si no, se conserva la equity declarada o unknown.
    if inp.villain_range is not None:
        if isinstance(inp.villain_range, ObservedRange):
            reasons.append('observed_range_not_distribution')
            if equity is None:
                coverage = 'unknown'
                coverage_reason = 'observed_range_not_distribution'
        else:
            value, reason = _compute_range_equity(
                inp, inp.villain_range, inp.hero_hand, inp.board)
            if value is None:
                reasons.append(reason)
                equity = None
                coverage = 'unknown'
                coverage_reason = reason
            else:
                equity = value
                coverage = 'usable'
                coverage_reason = None
                if equity_scenario is None:
                    equity_scenario = 'showdown_vs_villain_range'

    if inp.response_ranges:
        for label, range_obj in inp.response_ranges.items():
            if isinstance(range_obj, ObservedRange):
                computed_response_equities[label] = None
                reasons.append(f'response_range_not_distribution:{label}')
                continue
            value, reason = _compute_range_equity(
                inp, range_obj, inp.hero_hand, inp.board)
            computed_response_equities[label] = value
            if value is None:
                reasons.append(f'response_equity_unavailable:{label}:{reason}')

    # Fusion de equities por respuesta: las calculadas tienen precedencia.
    response_equities = dict(inp.response_equities or {})
    response_equities.update(
        {k: v for k, v in computed_response_equities.items() if v is not None})

    if coverage != 'usable':
        equity = None
    if inp.response is None:
        reasons.append('villain_response_unknown')
    if not _equity_compatible_with(inp, response_equities, equity):
        reasons.append('equity_response_mismatch')
        equity = None
        coverage = 'unknown'
        coverage_reason = 'equity_response_mismatch'

    if inp.canonical.status != 'resolved':
        return HUEvaluationResult(
            status='unknown',
            canonical_status=inp.canonical.status,
            legal_actions=(),
            ev_result=None,
            uncertainty_reasons=tuple(reasons),
            supported=False,
            trace=_trace(inp, None, equity_scenario=equity_scenario,
                         equity=equity),
            comparable=False,
            comparability_reasons=('canonical_not_resolved',),
            selection_status='none',
            best_action=None,
            provisional_best_action=None,
        )

    ev_input = EVInput(
        pot=inp.pot,
        to_call=inp.to_call,
        hero_stack=inp.hero_stack,
        villain_stack=inp.villain_stack,
        equity=equity,
        equity_call=(response_equities.get('call') if response_equities else None),
        equity_raise=(response_equities.get('raise') if response_equities else None),
        coverage=coverage,
        coverage_reason=coverage_reason,
        response=inp.response,
        bet_fractions=inp.bet_fractions,
        allow_all_in=inp.allow_all_in,
    )
    ev_result = calculate_ev(ev_input)

    legal = tuple(a.action for a in ev_result.actions)
    if coverage != 'usable' and ev_result.best_action == 'fold':
        status = 'usable'
        supported = True
    elif coverage != 'usable':
        status = 'unknown'
        supported = False
    else:
        status = ev_result.status
        supported = True

    comparability_reasons = []
    if coverage != 'usable':
        comparability_reasons.append('coverage_not_usable')
    if inp.response is None:
        comparability_reasons.append('response_unknown')
    if not _equity_compatible(inp):
        comparability_reasons.append('equity_response_mismatch')
    if (inp.range_kind == 'prior'
            or isinstance(inp.villain_range, GenericPrior)):
        comparability_reasons.append('generic_prior_not_demonstrated')
    if inp.response_ranges:
        if any(isinstance(r, GenericPrior) for r in inp.response_ranges.values()):
            comparability_reasons.append('generic_prior_response_not_demonstrated')
    comparable = (len(comparability_reasons) == 0)
    non_fold_usable = [a for a in ev_result.actions
                       if a.status == 'usable' and a.action != 'fold']
    if not comparable or not non_fold_usable:
        selection_status = 'provisional' if ev_result.best_action is not None else 'none'
        best_action = None
        provisional = ev_result.best_action
    else:
        selection_status = 'demonstrated'
        best_action = ev_result.best_action
        provisional = None

    return HUEvaluationResult(
        status=status,
        canonical_status=inp.canonical.status,
        legal_actions=legal,
        ev_result=ev_result,
        uncertainty_reasons=tuple(reasons),
        supported=supported,
        trace=_trace(inp, ev_result, response_equities, equity_scenario,
                    equity),
        comparable=comparable,
        comparability_reasons=tuple(comparability_reasons),
        selection_status=selection_status,
        best_action=best_action,
        provisional_best_action=provisional,
    )


def _trace(inp: HUEvaluationInput, ev_result: Optional[EVResult],
           response_equities=None, equity_scenario=None,
           equity=None) -> dict:
    canonical = inp.canonical
    plan = canonical.decision_plan
    coverage_state = None
    if canonical.coverage is not None:
        coverage_state = canonical.coverage.coverage_state
    response = None
    if inp.response is not None:
        response = {
            'p_fold': inp.response.p_fold,
            'p_call': inp.response.p_call,
            'p_raise': inp.response.p_raise,
        }
    return {
        'canonical_status': canonical.status,
        'sequence_status': canonical.sequence_status,
        'coverage_state': coverage_state,
        'plan_label': getattr(plan, 'label', None),
        'table_raise': getattr(plan, 'table_raise', None),
        'table_call': getattr(plan, 'table_call', None),
        'range_kind': inp.range_kind,
        'range_source': inp.range_source,
        'range_provenance': inp.range_provenance,
        'equity': (equity if equity is not None else inp.equity),
        'equity_scenario': (equity_scenario if equity_scenario is not None
                            else inp.equity_scenario),
        'response': response,
        'response_equities': response_equities if response_equities is not None
        else inp.response_equities,
        'pot': inp.pot,
        'to_call': inp.to_call,
        'hero_stack': inp.hero_stack,
        'villain_stack': inp.villain_stack,
        'legal_actions': (tuple(a.action for a in ev_result.actions)
                          if ev_result is not None else ()),
        'best_action': (ev_result.best_action if ev_result is not None else None),
        'best_ev': (ev_result.best_ev if ev_result is not None else None),
    }