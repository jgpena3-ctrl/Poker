"""Vista canónica preflop para el desarrollo HU (HU-P1A).

Une tres piezas que deben permanecer separadas:

1. `classification`: lectura contextual de una acción histórica del héroe.
2. `decision_plan`: tablas a consultar en el nodo previo a su decisión.
3. `range_query`: consulta de rango del modelo, si la categoría la admite.

No reorganiza el motor ni cambia recomendaciones live. Toda consulta de
cobertura se hace con fallback desactivado: un hueco se declara, no se rellena
con otra tabla.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .preflop import TABLE_ALIASES, table_key
from .preflop_contract import (
    BB_NOMINAL,
    PreflopClassification,
    PreflopContext,
    PreflopTablePlan,
    RangeQuery,
    actions_before,
    context_at,
    preflop_decision,
    last_decision,
    plan_from_context,
)
from .preflop_coverage import (
    CoverageAggregate,
    CoverageRequest,
    CoverageResolution,
    aggregate_coverage,
    resolve_coverage,
)

CONTRACT = 'hu_preflop_canonical_v1'


@dataclass(frozen=True)
class PlanCoverage:
    """Cobertura de una de las tablas del plan (`raise` o `call`)."""
    slot: str
    requested_key: str
    resolution: CoverageResolution

    def __post_init__(self):
        if self.slot not in ('raise', 'call'):
            raise ValueError('slot debe ser raise o call')
        if not self.requested_key:
            raise ValueError('requested_key no puede estar vacío')
        if self.resolution.requested_key != self.requested_key:
            raise ValueError('la resolución no corresponde a requested_key')

    def as_dict(self) -> Dict[str, Any]:
        return {
            'slot': self.slot,
            'requested_key': self.requested_key,
            'coverage_state': self.resolution.coverage_state,
            'source_key': self.resolution.source_key,
            'fallback_used': self.resolution.fallback_used,
            'approximation_used': self.resolution.approximation_used,
            'reason': self.resolution.reason,
        }


@dataclass(frozen=True)
class CanonicalPreflopDecision:
    """Decisión/consulta canónica, siempre en sombra."""
    status: str
    mode: str
    hero_position: str
    context: PreflopContext
    decision_plan: Optional[PreflopTablePlan]
    classification: Optional[PreflopClassification]
    range_query: Optional[RangeQuery]
    plan_coverage: Tuple[PlanCoverage, ...]
    coverage: Optional[CoverageAggregate]
    sequence_status: str
    reasons: Tuple[str, ...] = ()
    observed_action_index: Optional[int] = None
    at_index: Optional[int] = None
    contract: str = CONTRACT

    def __post_init__(self):
        if self.status not in ('resolved', 'unresolved', 'no_decision'):
            raise ValueError('status canónico inválido')
        if self.mode not in ('historical', 'current'):
            raise ValueError('mode debe ser historical o current')
        if self.sequence_status not in ('valid', 'tainted', 'not_evaluated',
                                       'incomplete'):
            raise ValueError('sequence_status inválido')
        if self.status != 'resolved':
            if (self.decision_plan is not None or self.range_query is not None
                    or self.coverage is not None or self.plan_coverage):
                raise ValueError(
                    'unresolved/no_decision no produce plan, cobertura ni rango')
        else:
            if self.decision_plan is None:
                raise ValueError('resolved exige decision_plan')
            if self.decision_plan.status != 'resolved':
                raise ValueError('resolved exige un plan resuelto')
            if self.coverage is None:
                raise ValueError('resolved exige cobertura agregada')
            if not isinstance(self.plan_coverage, tuple):
                raise TypeError('plan_coverage debe ser una tupla')

    @property
    def action_ready(self) -> bool:
        """Hay al menos una tabla de acción consultable sin huecos."""
        if self.status != 'resolved' or self.coverage is None:
            return False
        plan = self.decision_plan
        if plan is None or not (plan.table_raise or plan.table_call):
            return False
        return self.coverage.complete

    @property
    def complete(self) -> bool:
        return bool(self.coverage and self.coverage.complete)

    def as_dict(self) -> Dict[str, Any]:
        return {
            'contract': self.contract,
            'status': self.status,
            'mode': self.mode,
            'hero_position': self.hero_position,
            'sequence_status': self.sequence_status,
            'reasons': list(self.reasons),
            'observed_action_index': self.observed_action_index,
            'at_index': self.at_index,
            'context': self.context.as_dict(),
            'classification': (
                self.classification.as_dict()
                if self.classification is not None else None),
            'decision_plan': (
                self.decision_plan.as_dict()
                if self.decision_plan is not None else None),
            'range_query': (
                {
                    'status': self.range_query.status,
                    'category': self.range_query.decision_category,
                    'table_key': self.range_query.table_key,
                }
                if self.range_query is not None else None),
            'plan_coverage': [q.as_dict() for q in self.plan_coverage],
            'coverage': self.coverage.as_dict() if self.coverage else None,
            'action_ready': self.action_ready,
        }


def _sequence_status(context: PreflopContext) -> str:
    if context.tainted_reason:
        return 'tainted'
    return 'not_evaluated'


def _plan_queries(plan: PreflopTablePlan, hero_pos: str,
                  context: PreflopContext,
                  tables: Optional[Dict[str, Any]],
                  approved_aliases: Optional[Dict[Any, str]],
                  allow_fallback: bool) -> Tuple[PlanCoverage, ...]:
    if not hero_pos:
        raise ValueError('se requiere hero_position para consultar tablas')
    source_context = {'sequence_status': _sequence_status(context)}
    out = []
    for slot, action in (('raise', plan.table_raise),
                         ('call', plan.table_call)):
        if not action:
            continue
        key = table_key(action, hero_pos, plan.vs_pos)
        resolution = resolve_coverage(
            CoverageRequest(requested_key=key, action=action, pos=hero_pos,
                            vs=plan.vs_pos, source_context=source_context),
            tables=tables,
            approved_aliases=(TABLE_ALIASES if approved_aliases is None
                              else approved_aliases),
            fallback_policy_permits=allow_fallback,
        )
        out.append(PlanCoverage(slot=slot, requested_key=key,
                                resolution=resolution))
    return tuple(out)


def _resolved_view(*, mode: str, hero_pos: str, context: PreflopContext,
                   plan: PreflopTablePlan,
                   classification: Optional[PreflopClassification],
                   range_query: Optional[RangeQuery],
                   observed_action_index: Optional[int],
                   at_index: Optional[int],
                   tables: Optional[Dict[str, Any]],
                   approved_aliases: Optional[Dict[Any, str]],
                   allow_fallback: bool) -> CanonicalPreflopDecision:
    if plan.status != 'resolved':
        return CanonicalPreflopDecision(
            status='unresolved', mode=mode, hero_position=hero_pos,
            context=context, decision_plan=None,
            classification=classification, range_query=None,
            plan_coverage=(), coverage=None,
            sequence_status=_sequence_status(context),
            reasons=((plan.reason or 'plan_no_resuelto'),),
            observed_action_index=observed_action_index, at_index=at_index,
        )
    plan_queries = _plan_queries(plan, hero_pos, context, tables,
                                 approved_aliases, allow_fallback)
    coverage = aggregate_coverage(
        tuple(q.resolution for q in plan_queries))
    return CanonicalPreflopDecision(
        status='resolved', mode=mode, hero_position=hero_pos,
        context=context, decision_plan=plan,
        classification=classification, range_query=range_query,
        plan_coverage=plan_queries, coverage=coverage,
        sequence_status=_sequence_status(context),
        reasons=(), observed_action_index=observed_action_index,
        at_index=at_index,
    )


def canonical_preflop(source: Any, hero_pos: str, *,
                      mode: str = 'historical',
                      at_index: Optional[int] = None,
                      bb: float = BB_NOMINAL,
                      tables: Optional[Dict[str, Any]] = None,
                      approved_aliases: Optional[Dict[Any, str]] = None,
                      allow_fallback: bool = False) -> CanonicalPreflopDecision:
    """Construye la vista canónica HU de un nodo preflop.

    `mode='historical'` replica la primera decisión voluntaria del héroe.
    `mode='current'` reconstruye el nodo previo a `at_index` (o al final de las
    acciones observadas) sin exigir que el héroe ya haya actuado. La decisión
    se deriva del estado relativo al héroe, no de la última acción global.
    """
    if mode not in ('historical', 'current'):
        raise ValueError('mode debe ser historical o current')
    if mode == 'historical' and at_index is not None:
        raise ValueError('at_index no aplica a mode=historical')

    if mode == 'historical':
        decision = preflop_decision(source, hero_pos, bb=bb)
        context = decision.context or PreflopContext.initial(bb)
        classification = (
            decision.decision_plan
            if isinstance(decision.decision_plan, PreflopClassification)
            else None)
        if decision.status == 'no_decision':
            return CanonicalPreflopDecision(
                status='no_decision', mode=mode, hero_position=hero_pos,
                context=context, decision_plan=None, classification=None,
                range_query=None, plan_coverage=(), coverage=None,
                sequence_status=decision.sequence_status,
                reasons=(), observed_action_index=None, at_index=at_index,
            )
        if decision.status == 'unresolved':
            return CanonicalPreflopDecision(
                status='unresolved', mode=mode, hero_position=hero_pos,
                context=context, decision_plan=None,
                classification=classification, range_query=None,
                plan_coverage=(), coverage=None,
                sequence_status=decision.sequence_status,
                reasons=decision.unresolved_reasons,
                observed_action_index=decision.hero_action_index,
                at_index=at_index,
            )
        plan = plan_from_context(context)
        return _resolved_view(
            mode=mode, hero_pos=hero_pos, context=context, plan=plan,
            classification=classification, range_query=decision.range_query,
            observed_action_index=decision.hero_action_index,
            at_index=at_index, tables=tables,
            approved_aliases=approved_aliases, allow_fallback=allow_fallback)

    context = context_at(source, at_index, bb=bb)
    if not hero_pos:
        return CanonicalPreflopDecision(
            status='unresolved', mode=mode, hero_position=hero_pos,
            context=context, decision_plan=None, classification=None,
            range_query=None, plan_coverage=(), coverage=None,
            sequence_status=_sequence_status(context),
            reasons=('posicion_heroe_ausente',), observed_action_index=None,
            at_index=at_index,
        )
    prefix = actions_before(source, at_index)
    last = last_decision(prefix, hero_pos, bb=bb)
    classification = (last if last.status != 'unresolved'
                      or last.reason != 'sin_decision' else None)
    plan = plan_from_context(context)
    return _resolved_view(
        mode=mode, hero_pos=hero_pos, context=context, plan=plan,
        classification=classification, range_query=None,
        observed_action_index=(last.raw.index
                               if classification is not None else None),
        at_index=at_index, tables=tables, approved_aliases=approved_aliases,
        allow_fallback=allow_fallback)
