"""Resolvedor puro de cobertura preflop (PR-02A).

Este módulo no modifica consumidores ni tablas. Solo resuelve cobertura para
una clave solicitada, conservando la procedencia y la incertidumbre.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .preflop import (
    TABLE_ALIASES,
    classify_missing_table,
    load_tables,
    table_key,
)


@dataclass(frozen=True)
class CoverageRequest:
    requested_key: str
    action: str
    pos: str
    vs: str = ''
    source_context: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.source_context is None:
            object.__setattr__(self, 'source_context', {})
        else:
            object.__setattr__(self, 'source_context',
                               copy.deepcopy(self.source_context))

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        if name == 'source_context':
            return copy.deepcopy(value)
        return value


@dataclass(frozen=True)
class CoverageResolution:
    requested_key: str
    action: str
    pos: str
    vs: str
    coverage_state: str
    source_key: Optional[str]
    alias_of: Optional[str]
    fallback_used: bool
    fallback_key: Optional[str]
    fallback_reason: Optional[str]
    approximation_used: bool
    reason: str
    resolved_by: str

    def __post_init__(self):
        if self.coverage_state not in ('exact', 'alias', 'coverage_gap',
                                     'impossible', 'unknown'):
            raise ValueError('coverage_state inválido')
        if self.coverage_state == 'exact':
            if self.source_key != self.requested_key:
                raise ValueError('exact requiere source_key == requested_key')
            if self.approximation_used or self.fallback_used:
                raise ValueError('exact no usa aproximación ni fallback')
            if self.alias_of is not None:
                raise ValueError('exact no tiene alias_of')
        if self.coverage_state == 'alias':
            if self.alias_of is None or self.source_key != self.alias_of:
                raise ValueError('alias requiere alias_of y source_key coherentes')
            if self.approximation_used or self.fallback_used:
                raise ValueError('alias no es aproximación ni fallback')
        else:
            if self.alias_of is not None:
                raise ValueError('alias_of solo aplica a alias')
        if self.coverage_state in ('impossible', 'unknown'):
            if (self.source_key is not None or self.fallback_used
                    or self.approximation_used or self.alias_of is not None):
                raise ValueError(
                    'impossible/unknown no usan source_key, fallback, '
                    'aproximación ni alias')
        if self.fallback_used != self.approximation_used:
            raise ValueError(
                'fallback_used y approximation_used deben ser equivalentes')
        if self.fallback_used:
            if self.fallback_key is None or self.fallback_reason is None:
                raise ValueError('fallback requiere fallback_key y fallback_reason')
            if self.coverage_state != 'coverage_gap':
                raise ValueError('fallback solo aplica a coverage_gap')
            if self.source_key is None or self.source_key != self.fallback_key:
                raise ValueError('source_key debe coincidir con fallback_key')
        else:
            if self.fallback_key is not None or self.fallback_reason is not None:
                raise ValueError(
                    'sin fallback, fallback_key y fallback_reason deben ser null')
            if (self.coverage_state == 'coverage_gap'
                    and self.source_key is not None):
                raise ValueError(
                    'coverage_gap sin fallback requiere source_key null')


def _find_fallback_table(tables: Dict[str, Any], action: str, pos: str,
                         vs: str) -> Optional[str]:
    requested = table_key(action, pos, vs)
    for key, table in sorted(tables.items()):
        if (table.get('action') == action and table.get('pos') == pos
                and key != requested):
            return key
    return None


def _is_structurally_impossible(action: str, pos: str, vs: str,
                                source_context: Dict[str, Any]) -> bool:
    # Imposibilidades definicionales independientes del orden.
    if (action, pos, vs) in (('OR', 'BB', ''), ('ROL', 'UTG', '')):
        return True
    reason = classify_missing_table(action, pos, vs)
    if reason == 'impossible_action_order':
        return source_context.get('sequence_status') == 'valid'
    if reason.startswith('intentional_'):
        return True
    return False


def _impossibility_reason(action: str, pos: str, vs: str,
                          source_context: Dict[str, Any]) -> str:
    if (action, pos, vs) == ('OR', 'BB', ''):
        return 'intentional_check_option'
    if (action, pos, vs) == ('ROL', 'UTG', ''):
        return 'intentional_no_prior_limp'
    reason = classify_missing_table(action, pos, vs)
    if reason == 'impossible_action_order':
        if source_context.get('sequence_status') == 'valid':
            return 'impossible_action_order'
        return 'sequence_not_validated'
    return reason


def _classify_absence(action: str, pos: str, vs: str,
                      source_context: Dict[str, Any]) -> str:
    reason = classify_missing_table(action, pos, vs)
    if reason == 'impossible_action_order':
        if source_context.get('sequence_status') != 'valid':
            return 'unknown'
        return 'impossible'
    if reason.startswith('intentional_'):
        return 'impossible'
    if reason == 'coverage_gap':
        return 'coverage_gap'
    return 'unknown'


def resolve_coverage(request: CoverageRequest,
                     tables: Optional[Dict[str, Any]] = None,
                     approved_aliases: Optional[Dict[Any, str]] = None,
                     fallback_policy_permits: bool = True) -> CoverageResolution:
    if tables is None:
        tables = load_tables()
    if approved_aliases is None:
        approved_aliases = TABLE_ALIASES

    source_context = request.source_context or {}
    canonical_key = table_key(request.action, request.pos, request.vs)

    # 1. Coherencia de clave
    if request.requested_key != canonical_key:
        return CoverageResolution(
            requested_key=request.requested_key,
            action=request.action,
            pos=request.pos,
            vs=request.vs,
            coverage_state='unknown',
            source_key=None,
            alias_of=None,
            fallback_used=False,
            fallback_key=None,
            fallback_reason=None,
            approximation_used=False,
            reason='key_mismatch',
            resolved_by='coverage_resolver',
        )

    # 2. Imposibilidad con precedencia
    if _is_structurally_impossible(request.action, request.pos, request.vs,
                                   source_context):
        return CoverageResolution(
            requested_key=request.requested_key,
            action=request.action,
            pos=request.pos,
            vs=request.vs,
            coverage_state='impossible',
            source_key=None,
            alias_of=None,
            fallback_used=False,
            fallback_key=None,
            fallback_reason=None,
            approximation_used=False,
            reason=_impossibility_reason(request.action, request.pos, request.vs,
                                        source_context),
            resolved_by='coverage_resolver',
        )

    # 3. Tabla exacta
    if request.requested_key in tables:
        return CoverageResolution(
            requested_key=request.requested_key,
            action=request.action,
            pos=request.pos,
            vs=request.vs,
            coverage_state='exact',
            source_key=request.requested_key,
            alias_of=None,
            fallback_used=False,
            fallback_key=None,
            fallback_reason=None,
            approximation_used=False,
            reason='exact_table',
            resolved_by='coverage_resolver',
        )

    # 4. Alias aprobado
    alias = approved_aliases.get((request.action, request.pos, request.vs))
    if alias is not None and alias in tables:
        return CoverageResolution(
            requested_key=request.requested_key,
            action=request.action,
            pos=request.pos,
            vs=request.vs,
            coverage_state='alias',
            source_key=alias,
            alias_of=alias,
            fallback_used=False,
            fallback_key=None,
            fallback_reason=None,
            approximation_used=False,
            reason='approved_alias',
            resolved_by='coverage_resolver',
        )

    # 5. Ausencia clasificable
    classification = _classify_absence(request.action, request.pos, request.vs,
                                      source_context)

    if classification == 'unknown':
        return CoverageResolution(
            requested_key=request.requested_key,
            action=request.action,
            pos=request.pos,
            vs=request.vs,
            coverage_state='unknown',
            source_key=None,
            alias_of=None,
            fallback_used=False,
            fallback_key=None,
            fallback_reason=None,
            approximation_used=False,
            reason=classification,
            resolved_by='coverage_resolver',
        )

    # 6. coverage_gap
    fallback_used = False
    fallback_key = None
    fallback_reason = None
    approximation_used = False

    if (classification == 'coverage_gap' and fallback_policy_permits):
        candidate = _find_fallback_table(tables, request.action, request.pos,
                                         request.vs)
        if candidate is not None:
            fallback_used = True
            fallback_key = candidate
            fallback_reason = 'fallback_to_other_vs'
            approximation_used = True

    return CoverageResolution(
        requested_key=request.requested_key,
        action=request.action,
        pos=request.pos,
        vs=request.vs,
        coverage_state='coverage_gap',
        source_key=fallback_key,
        alias_of=None,
        fallback_used=fallback_used,
        fallback_key=fallback_key,
        fallback_reason=fallback_reason,
        approximation_used=approximation_used,
        reason='coverage_gap' if not fallback_used else 'fallback_to_other_vs',
        resolved_by='coverage_resolver',
    )
