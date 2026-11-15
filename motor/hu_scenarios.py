"""Arnés mínimo de escenarios HU (HU-P5, preparación).

Los escenarios reales y sintéticos se declaran en colecciones separadas. Los
reales llevan `hand_id` y hash del snapshot; los sintéticos no pueden llevar
esos campos. El arnés sólo ejecuta contratos puros en sombra y no lee ni
escribe datos históricos.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from .preflop_canonical import CanonicalPreflopDecision, canonical_preflop

SCENARIO_CONTRACT = 'hu_preflop_scenario_v1'
DATA_SNAPSHOT_SHA256 = (
    '3F0E7E5EA0D5C2D06AA9B8629817984AB9B4BCCF057371823FDE60370818262E')
EXPECTED_KEYS = frozenset({
    'canonical_status', 'category', 'plan_label', 'table_raise',
    'table_call', 'coverage_state', 'action_ready',
})


@dataclass(frozen=True)
class PreflopScenario:
    scenario_id: str
    source_kind: str
    hero_position: str
    actions: Tuple[Mapping[str, Any], ...]
    expected: Mapping[str, Any]
    mode: str = 'historical'
    at_index: Optional[int] = None
    hand_id: Optional[str] = None
    data_snapshot_hash: Optional[str] = None
    source_document: Optional[str] = None
    notes: str = ''
    contract: str = SCENARIO_CONTRACT

    def __post_init__(self):
        if not self.scenario_id:
            raise ValueError('scenario_id no puede estar vacío')
        if self.source_kind not in ('real', 'synthetic'):
            raise ValueError('source_kind debe ser real o synthetic')
        if self.mode not in ('historical', 'current'):
            raise ValueError('mode inválido')
        if self.at_index is not None:
            if isinstance(self.at_index, bool) or not isinstance(self.at_index, int):
                raise ValueError('at_index debe ser entero o None')
            if self.at_index < 0:
                raise ValueError('at_index no puede ser negativo')
            if self.mode == 'historical':
                raise ValueError(
                    'at_index no aplica a historical: usa mode=current')
        if self.source_kind == 'real':
            if not self.hand_id or not self.data_snapshot_hash:
                raise ValueError('escenario real exige hand_id y snapshot hash')
        else:
            if self.hand_id is not None or self.data_snapshot_hash is not None:
                raise ValueError('escenario sintético no lleva identidad real')
        actions = tuple(dict(a) for a in self.actions)
        if not actions:
            raise ValueError('el escenario necesita acciones')
        expected = dict(self.expected)
        unknown = set(expected) - EXPECTED_KEYS
        if unknown:
            raise ValueError('expectativas desconocidas: %s'
                             % ', '.join(sorted(unknown)))
        if not expected:
            raise ValueError('el escenario necesita al menos una expectativa')
        object.__setattr__(self, 'actions', actions)
        object.__setattr__(self, 'expected', MappingProxyType(expected))

    def as_dict(self) -> dict:
        return {
            'contract': self.contract,
            'scenario_id': self.scenario_id,
            'source_kind': self.source_kind,
            'hand_id': self.hand_id,
            'data_snapshot_hash': self.data_snapshot_hash,
            'source_document': self.source_document,
            'mode': self.mode,
            'at_index': self.at_index,
            'hero_position': self.hero_position,
            'actions': list(self.actions),
            'expected': dict(self.expected),
            'notes': self.notes,
        }


@dataclass(frozen=True)
class ScenarioCheck:
    field: str
    expected: Any
    actual: Any
    passed: bool

    def as_dict(self) -> dict:
        return {
            'field': self.field,
            'expected': self.expected,
            'actual': self.actual,
            'passed': self.passed,
        }


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    source_kind: str
    passed: bool
    checks: Tuple[ScenarioCheck, ...]
    actual: Mapping[str, Any]
    decision: CanonicalPreflopDecision

    def as_dict(self) -> dict:
        return {
            'scenario_id': self.scenario_id,
            'source_kind': self.source_kind,
            'passed': self.passed,
            'checks': [c.as_dict() for c in self.checks],
            'actual': dict(self.actual),
            'decision': self.decision.as_dict(),
        }


def _actual_fields(decision: CanonicalPreflopDecision) -> Dict[str, Any]:
    plan = decision.decision_plan
    return {
        'canonical_status': decision.status,
        'category': (decision.classification.category
                     if decision.classification is not None else None),
        'plan_label': plan.label if plan is not None else None,
        'table_raise': plan.table_raise if plan is not None else None,
        'table_call': plan.table_call if plan is not None else None,
        'coverage_state': (decision.coverage.coverage_state
                           if decision.coverage is not None else None),
        'action_ready': decision.action_ready,
    }


def run_preflop_scenario(
        scenario: PreflopScenario,
        *,
        tables: Optional[Dict[str, Any]] = None) -> ScenarioResult:
    if not isinstance(scenario, PreflopScenario):
        raise TypeError('scenario debe ser PreflopScenario')
    decision = canonical_preflop(
        list(scenario.actions), scenario.hero_position, mode=scenario.mode,
        at_index=scenario.at_index, tables=tables, allow_fallback=False)
    actual = _actual_fields(decision)
    checks = tuple(
        ScenarioCheck(field=key, expected=expected, actual=actual.get(key),
                      passed=actual.get(key) == expected)
        for key, expected in scenario.expected.items())
    return ScenarioResult(
        scenario_id=scenario.scenario_id, source_kind=scenario.source_kind,
        passed=all(c.passed for c in checks), checks=checks,
        actual=MappingProxyType(actual), decision=decision)


REAL_PREFLOP_SCENARIOS: Tuple[PreflopScenario, ...] = (
    PreflopScenario(
        scenario_id='R01_open_utg',
        source_kind='real', hand_id='H_0001',
        data_snapshot_hash=DATA_SNAPSHOT_SHA256,
        source_document='DOCS/ESCENARIOS_REFERENCIA_HU_2026-11-13.md',
        hero_position='UTG',
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
            {'pos': 'MP', 'action': 'c', 'amount': 2.5},
        ),
        expected={
            'canonical_status': 'resolved',
            'category': 'open',
            'plan_label': 'apertura (sin raise previo)',
            'table_raise': 'OR', 'table_call': None,
            'coverage_state': 'complete_exact', 'action_ready': True,
        },
        notes='Secuencia real recortada; no se lee la base desde el arnés.',
    ),
    PreflopScenario(
        scenario_id='R02_mp_vs_utg_open',
        source_kind='real', hand_id='H_0001',
        data_snapshot_hash=DATA_SNAPSHOT_SHA256,
        source_document='DOCS/ESCENARIOS_REFERENCIA_HU_2026-11-13.md',
        hero_position='MP',
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
            {'pos': 'MP', 'action': 'c', 'amount': 2.5},
        ),
        expected={
            'canonical_status': 'resolved',
            'category': 'call_open',
            'plan_label': 'vs apertura',
            'table_raise': '3B', 'table_call': 'Call_OR',
            'coverage_state': 'partial', 'action_ready': False,
        },
        notes='3B_MP_vs_UTG existe; Call_OR_MP_vs_UTG es hueco real.',
    ),
    PreflopScenario(
        scenario_id='R05_sb_call_limp',
        source_kind='real', hand_id='H_0005',
        data_snapshot_hash=DATA_SNAPSHOT_SHA256,
        source_document='DOCS/ESCENARIOS_REFERENCIA_HU_2026-11-13.md',
        hero_position='SB',
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'f', 'amount': 0.0},
            {'pos': 'MP', 'action': 'b', 'amount': 1.0},
            {'pos': 'CO', 'action': 'c', 'amount': 1.0},
            {'pos': 'BTN', 'action': 'c', 'amount': 1.0},
            {'pos': 'SB', 'action': 'c', 'amount': 1.0},
        ),
        expected={
            'canonical_status': 'resolved',
            'category': 'call_limp',
            'plan_label': 'vs limp',
            'table_raise': 'ROL', 'table_call': None,
            'coverage_state': 'complete_exact', 'action_ready': True,
        },
        notes='El b de 1BB es limpe corto, no apertura.',
    ),
    PreflopScenario(
        scenario_id='R06_bb_check_after_short_limp',
        source_kind='real', hand_id='H_0012',
        data_snapshot_hash=DATA_SNAPSHOT_SHA256,
        source_document='DOCS/ESCENARIOS_REFERENCIA_HU_2026-11-13.md',
        hero_position='BB',
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'b', 'amount': 1.0},
            {'pos': 'MP', 'action': 'f', 'amount': 0.0},
            {'pos': 'CO', 'action': 'f', 'amount': 0.0},
            {'pos': 'BTN', 'action': 'f', 'amount': 0.0},
            {'pos': 'SB', 'action': 'c', 'amount': 1.0},
            {'pos': 'BB', 'action': 'x', 'amount': 0.0},
        ),
        expected={
            'canonical_status': 'resolved',
            'category': 'bb_check',
            'plan_label': 'vs limp',
            'table_raise': 'ROL', 'table_call': None,
            'coverage_state': 'complete_exact', 'action_ready': True,
        },
        notes='Check de BB tras limpe corto; la categoría no tiene rango.',
    ),
    PreflopScenario(
        scenario_id='R10_sb_open_after_folds',
        source_kind='real', hand_id='H_0066',
        data_snapshot_hash=DATA_SNAPSHOT_SHA256,
        source_document='DOCS/ESCENARIOS_REFERENCIA_HU_2026-11-13.md',
        hero_position='SB',
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'f', 'amount': 0.0},
            {'pos': 'MP', 'action': 'f', 'amount': 0.0},
            {'pos': 'CO', 'action': 'f', 'amount': 0.0},
            {'pos': 'BTN', 'action': 'f', 'amount': 0.0},
            {'pos': 'SB', 'action': 'r', 'amount': 3.0},
            {'pos': 'BB', 'action': 'c', 'amount': 3.0},
        ),
        expected={
            'canonical_status': 'resolved',
            'category': 'open',
            'plan_label': 'apertura (sin raise previo)',
            'table_raise': 'OR', 'table_call': None,
            'coverage_state': 'complete_exact', 'action_ready': True,
        },
        notes='R10 de la referencia: H_0066/SB; los folds previos no abren.',
    ),
    PreflopScenario(
        scenario_id='R18_h0032_bb_vs_sb_3bet',
        source_kind='real', hand_id='H_0032',
        data_snapshot_hash=DATA_SNAPSHOT_SHA256,
        source_document='DOCS/ESCENARIOS_REFERENCIA_HU_2026-11-13.md',
        hero_position='BB',
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'MP', 'action': 'f', 'amount': 0.0},
            {'pos': 'CO', 'action': 'c', 'amount': 1.0},
            {'pos': 'BTN', 'action': 'f', 'amount': 0.0},
            {'pos': 'SB', 'action': 'r', 'amount': 5.0,
             'amount_semantics': 'absoluta'},
            {'pos': 'BB', 'action': 'r', 'amount': 9.0},
            {'pos': 'CO', 'action': 'f', 'amount': 0.0},
            {'pos': 'SB', 'action': 'c', 'amount': 9.0},
        ),
        expected={
            'canonical_status': 'resolved',
            'category': '3bet',
            'plan_label': 'vs apertura',
            'table_raise': '3B', 'table_call': 'Call_OR',
            'coverage_state': 'complete_exact', 'action_ready': True,
        },
        notes='Identificador adicional: H_0032/BB; conserva la fuente completa.',
    ),
)


SYNTHETIC_PREFLOP_SCENARIOS: Tuple[PreflopScenario, ...] = (
    PreflopScenario(
        scenario_id='S_open_r',
        source_kind='synthetic', hero_position='UTG',
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        ),
        expected={
            'canonical_status': 'resolved',
            'category': 'open',
            'table_raise': 'OR', 'table_call': None,
            'coverage_state': 'complete_exact', 'action_ready': True,
        },
        notes='D-01: r de apertura no es 3bet.',
    ),
    PreflopScenario(
        scenario_id='S_short_limp_then_raise',
        source_kind='synthetic', hero_position='MP',
        actions=(
            {'pos': 'UTG', 'action': 'b', 'amount': 1.0},
            {'pos': 'MP', 'action': 'b', 'amount': 3.0},
        ),
        expected={
            'canonical_status': 'resolved',
            'category': 'rol',
            'table_raise': 'ROL', 'table_call': None,
            'coverage_state': 'complete_exact', 'action_ready': True,
        },
        notes='D-03: b <= BB es limpe corto; la subida posterior es ROL.',
    ),
    PreflopScenario(
        scenario_id='S_current_relative_node',
        source_kind='synthetic', hero_position='CO', mode='current',
        at_index=4,
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
            {'pos': 'MP', 'action': 'c', 'amount': 2.5},
        ),
        expected={
            'canonical_status': 'resolved',
            'category': None,
            'plan_label': 'vs apertura',
            'table_raise': '3B', 'table_call': 'Call_OR',
            'coverage_state': 'partial', 'action_ready': False,
        },
        notes='D-02: el nodo actual usa el contexto, no la última acción.',
    ),
    PreflopScenario(
        scenario_id='S_no_decision_historical',
        source_kind='synthetic', hero_position='CO',
        actions=(
            {'pos': 'SB', 'action': 'p', 'amount': 0.5},
            {'pos': 'BB', 'action': 'p', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
        ),
        expected={
            'canonical_status': 'no_decision',
            'category': None,
            'plan_label': None,
            'table_raise': None, 'table_call': None,
            'coverage_state': None, 'action_ready': False,
        },
        notes='Sin acción histórica del héroe no se inventa plan.',
    ),
    PreflopScenario(
        scenario_id='S_unresolved_invalid_raise',
        source_kind='synthetic', hero_position='MP',
        actions=(
            {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
            {'pos': 'MP', 'action': 'r', 'amount': 2.5},
        ),
        expected={
            'canonical_status': 'unresolved',
            'category': None,
            'plan_label': None,
            'table_raise': None, 'table_call': None,
            'coverage_state': None, 'action_ready': False,
        },
        notes='Subida sin incremento: no se produce plan ni rango.',
    ),
)


def all_preflop_scenarios() -> Tuple[PreflopScenario, ...]:
    return REAL_PREFLOP_SCENARIOS + SYNTHETIC_PREFLOP_SCENARIOS


def run_all_preflop_scenarios(*, tables: Optional[Dict[str, Any]] = None
                              ) -> Tuple[ScenarioResult, ...]:
    return tuple(run_preflop_scenario(s, tables=tables)
                 for s in all_preflop_scenarios())
