"""Motor experimental HU: estado observado -> prediccion -> registro.

La prediccion es siempre experimental. Un prior plano no se presenta como
evidencia especifica del rival y una seleccion basada en el queda como
``provisional``, nunca como ``demonstrated``.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Tuple

import numpy as np

from ..hu_ev import EVInput, EVResult, calculate_ev
from ..hu_evaluation import HUEvaluationInput, HUEvaluationResult, evaluate_hu
from ..hu_prospective import (
    HUPrediction,
    HUOutcome,
    ProspectiveHURegistry,
    VerificationResult,
)
from ..hu_range_contracts import (
    GenericPrior,
    KnownCards,
    N_COMBOS,
    build_estimated_range,
    equity_to_showdown,
)
from ..preflop import load_tables
from ..preflop_canonical import canonical_preflop
from .capture import CapturedFrame, HUCaptureAdapter
from .config import ExperimentalConfig
from .state import HUState, interpret_state


EXPERIMENTAL_VERSION = 'hu_experimental_v1'
FLAT_PRIOR_KEY = 'hu_experimental_flat_prior'


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ExperimentalAnalysis:
    state: HUState
    canonical_status: str
    canonical_reason: Optional[str]
    sequence_status: str
    coverage_state: str
    range_kind: str
    range_source: str
    range_provenance: Mapping[str, Any]
    equity: Optional[float]
    equity_method: Optional[str]
    equity_uncertainty: Optional[str]
    ev_result: Optional[EVResult]
    selected_action: Optional[str]
    provisional_selected_action: Optional[str]
    legal_actions: Tuple[str, ...]
    uncertainty_reasons: Tuple[str, ...]
    assumptions: Tuple[str, ...]
    warnings: Tuple[str, ...]
    capture_source: str
    captured_at: str
    elapsed_ms: Mapping[str, float] = field(default_factory=dict)

    @property
    def has_decision(self) -> bool:
        return self.state.ready and self.state.can_estimate

    def as_dict(self) -> dict:
        return {
            'experimental_version': EXPERIMENTAL_VERSION,
            'state': self.state.as_dict(),
            'canonical_status': self.canonical_status,
            'canonical_reason': self.canonical_reason,
            'sequence_status': self.sequence_status,
            'coverage_state': self.coverage_state,
            'range_kind': self.range_kind,
            'range_source': self.range_source,
            'range_provenance': dict(self.range_provenance),
            'equity': self.equity,
            'equity_method': self.equity_method,
            'equity_uncertainty': self.equity_uncertainty,
            'ev': self.ev_result.as_dict() if self.ev_result else None,
            'selected_action': self.selected_action,
            'provisional_selected_action': self.provisional_selected_action,
            'legal_actions': list(self.legal_actions),
            'uncertainty_reasons': list(self.uncertainty_reasons),
            'assumptions': list(self.assumptions),
            'warnings': list(self.warnings),
            'capture_source': self.capture_source,
            'captured_at': self.captured_at,
            'elapsed_ms': dict(self.elapsed_ms),
        }


@dataclass(frozen=True)
class PredictionRegistration:
    analysis: ExperimentalAnalysis
    prediction: HUPrediction
    event: Mapping[str, Any]
    registry_path: str

    @property
    def prediction_id(self) -> str:
        return self.prediction.prediction_id


class HUExperimentalAssistant:
    """Asistente experimental HU con persistencia prospectiva aislada."""

    def __init__(self, config: Optional[ExperimentalConfig] = None,
                 *, capture: Optional[HUCaptureAdapter] = None,
                 registry: Optional[ProspectiveHURegistry] = None,
                 clock: Optional[Callable[[], str]] = None):
        self.config = config or ExperimentalConfig.default()
        self.capture_adapter = capture or HUCaptureAdapter(clock=clock)
        self.registry = registry or ProspectiveHURegistry(
            self.config.registry_path)
        self._clock = clock or _now_iso

    @property
    def registry_path(self) -> Path:
        return self.registry.storage_path

    def capture(self) -> CapturedFrame:
        return self.capture_adapter.capture()

    def prepare(self) -> float:
        """Inicializa los lectores originales fuera del coste de captura."""
        prepare = getattr(self.capture_adapter, 'prepare', None)
        if prepare is None:
            return 0.0
        return prepare() or 0.0

    def analyze(self, source: Any = None) -> ExperimentalAnalysis:
        started = time.perf_counter()
        if source is None:
            frame = self.capture()
        elif isinstance(source, CapturedFrame):
            frame = source
        elif isinstance(source, Mapping):
            frame = CapturedFrame(state=dict(source), captured_at=self._clock(),
                                  source='mapping')
        else:
            raise TypeError('source debe ser None, CapturedFrame o mapping')

        state = interpret_state(frame.state, hero_seat=self.config.hero_seat)
        reasons = list(state.uncertainty_reasons)
        warnings = list(frame.warnings)
        if state.status == 'no_decision':
            return self._empty_analysis(
                state, frame, reasons, warnings, started,
                canonical_reason=state.reason or 'no_decision')
        if not state.can_estimate:
            return self._empty_analysis(
                state, frame, reasons, warnings, started,
                canonical_reason=state.reason or 'insufficient_state')

        prior = GenericPrior.flat(key=FLAT_PRIOR_KEY, coverage='unknown')
        known = KnownCards(hero_hand=state.hero_cards, board=state.board)
        likelihood = np.ones(N_COMBOS, dtype=np.float64)

        estimated = None
        equity = None
        equity_method = None
        equity_uncertainty = None
        try:
            estimated = build_estimated_range(
                player=state.villain_seat or 'villain',
                street=state.street,
                board=state.board,
                prior=prior,
                likelihood=likelihood,
                known_cards=known,
                n_obs=0,
                n_opp=0,
                likelihood_model='flat_prior_likelihood',
            )
            if not estimated.usable:
                reasons.append('range_not_usable:%s'
                               % (estimated.empty_reason or 'empty'))
            elif state.street == 'preflop':
                # El contrato preflop exacto enumera todos los runouts por
                # combo y tarda decenas de segundos incluso con pocos combos.
                # No se lanza desde la interfaz ni se sustituye por una
                # aproximacion no contratada: la equity queda unknown.
                equity_uncertainty = (
                    'preflop_equity_not_computed_without_fast_contract')
                reasons.append(equity_uncertainty)
            else:
                eq_result = equity_to_showdown(
                    state.hero_cards, state.board,
                    villain_reach=estimated.posterior,
                    n_runouts=self.config.equity_n_runouts,
                    n_combos=self.config.equity_n_combos,
                    seed=self.config.equity_seed,
                )
                equity = eq_result.value
                equity_method = eq_result.method
                equity_uncertainty = eq_result.uncertainty_reason
                if equity is None:
                    reasons.append('equity_not_usable:%s'
                                   % (equity_uncertainty or 'unknown'))
                elif equity_uncertainty:
                    reasons.append('equity_uncertainty:%s'
                                   % equity_uncertainty)
        except (ValueError, TypeError) as exc:
            reasons.append('range_or_equity_failed:%s' % exc)

        coverage = 'usable' if equity is not None else 'unknown'
        coverage_reason = None if coverage == 'usable' else (
            'flat_prior_equity_unavailable')
        response = None
        reasons.append('villain_response_unknown')
        reasons.append('generic_flat_prior_not_opponent_specific')

        canonical, canonical_reason = self._try_canonical(state, reasons)
        if canonical is not None and canonical.status == 'resolved':
            eval_result: HUEvaluationResult = evaluate_hu(HUEvaluationInput(
                canonical=canonical,
                pot=state.pot or 0.0,
                to_call=state.to_call or 0.0,
                hero_stack=state.hero_stack or 0.0,
                villain_stack=state.villain_stack or 0.0,
                equity=equity,
                coverage=coverage,
                coverage_reason=coverage_reason,
                response=response,
                response_equities=None,
                range_kind='prior',
                range_source='hu_experimental_flat_prior',
                range_provenance=(estimated.as_dict() if estimated else None),
                equity_scenario='showdown_vs_flat_prior',
                hero_hand=state.hero_cards,
                board=state.board,
                equity_n_runouts=self.config.equity_n_runouts,
                equity_n_combos=self.config.equity_n_combos,
                equity_seed=self.config.equity_seed,
            ))
            ev_result = eval_result.ev_result
            selected = eval_result.best_action
            non_fold_usable = (
                [a for a in ev_result.actions
                 if a.status == 'usable' and a.ev is not None
                 and a.action != 'fold']
                if ev_result is not None else [])
            provisional = (eval_result.provisional_best_action
                           if non_fold_usable else None)
            legal = eval_result.legal_actions
            coverage_state = (canonical.coverage.coverage_state
                              if canonical.coverage is not None else 'unknown')
            sequence_status = canonical.sequence_status
            canonical_status = canonical.status
            reasons.extend(eval_result.uncertainty_reasons)
            reasons.extend(eval_result.comparability_reasons)
        else:
            ev_input = EVInput(
                pot=state.pot or 0.0,
                to_call=state.to_call or 0.0,
                hero_stack=state.hero_stack or 0.0,
                villain_stack=state.villain_stack or 0.0,
                equity=equity,
                coverage=coverage,
                coverage_reason=coverage_reason,
                response=response,
            )
            ev_result = calculate_ev(ev_input)
            selected = None
            non_fold_usable = [a for a in ev_result.actions
                               if a.status == 'usable' and a.ev is not None
                               and a.action != 'fold']
            provisional = (ev_result.best_action
                           if non_fold_usable else None)
            legal = tuple(a.action for a in ev_result.actions)
            coverage_state = 'unknown'
            sequence_status = 'not_evaluated'
            canonical_status = 'unresolved'
            if canonical_reason:
                reasons.append(canonical_reason)

        range_provenance = {
            'prior': prior.as_dict(),
            'estimated': (estimated.as_dict() if estimated is not None else None),
            'note': 'prior plano uniforme; no es un rango especifico del rival',
        }
        assumptions = (
            'EV se calcula en el momento de la decision con el estado observado.',
            'El rango del rival es un prior plano uniforme, no evidencia especifica.',
            'La respuesta del rival no se modela; las apuestas quedan unknown.',
            'La equity se calcula contra el prior plano y no demuestra ventaja estrategica.',
            'La seleccion es provisional y no una decision demostrada.',
        )
        elapsed = (time.perf_counter() - started) * 1000.0
        return ExperimentalAnalysis(
            state=state,
            canonical_status=canonical_status,
            canonical_reason=canonical_reason,
            sequence_status=sequence_status,
            coverage_state=coverage_state,
            range_kind='prior',
            range_source='hu_experimental_flat_prior',
            range_provenance=range_provenance,
            equity=equity,
            equity_method=equity_method,
            equity_uncertainty=equity_uncertainty,
            ev_result=ev_result,
            selected_action=selected,
            provisional_selected_action=provisional,
            legal_actions=legal,
            uncertainty_reasons=tuple(dict.fromkeys(reasons)),
            assumptions=assumptions,
            warnings=tuple(dict.fromkeys(warnings)),
            capture_source=frame.source,
            captured_at=frame.captured_at,
            elapsed_ms={'analysis': elapsed},
        )

    def _empty_analysis(self, state: HUState, frame: CapturedFrame,
                        reasons, warnings, started,
                        *, canonical_reason: str) -> ExperimentalAnalysis:
        elapsed = (time.perf_counter() - started) * 1000.0
        return ExperimentalAnalysis(
            state=state,
            canonical_status=('no_decision' if state.status == 'no_decision'
                              else 'unresolved'),
            canonical_reason=canonical_reason,
            sequence_status='not_evaluated',
            coverage_state='unknown',
            range_kind='unknown',
            range_source='none',
            range_provenance={},
            equity=None,
            equity_method=None,
            equity_uncertainty=None,
            ev_result=None,
            selected_action=None,
            provisional_selected_action=None,
            legal_actions=(),
            uncertainty_reasons=tuple(dict.fromkeys(reasons)),
            assumptions=(
                'No se calcula EV cuando falta informacion estructural o el estado no es HU.',
            ),
            warnings=tuple(dict.fromkeys(warnings)),
            capture_source=frame.source,
            captured_at=frame.captured_at,
            elapsed_ms={'analysis': elapsed},
        )

    @staticmethod
    def _try_canonical(state: HUState, reasons: list):
        actions = state.raw_state.get('preflop_actions')
        if state.street != 'preflop' or actions is None:
            return None, 'action_sequence_not_observed'
        if not state.hero_position:
            return None, 'hero_position_not_observed'
        try:
            canonical = canonical_preflop(
                actions, state.hero_position, mode='current',
                tables=load_tables(),
            )
            return canonical, None
        except (ValueError, TypeError) as exc:
            reasons.append('canonical_preflop_failed:%s' % exc)
            return None, 'canonical_preflop_failed'

    def build_prediction(self, analysis: ExperimentalAnalysis, *,
                         prediction_id: Optional[str] = None,
                         emitted_at: Optional[str] = None) -> HUPrediction:
        if not isinstance(analysis, ExperimentalAnalysis):
            raise TypeError('analysis debe ser ExperimentalAnalysis')
        pid = prediction_id or uuid.uuid4().hex
        emitted = emitted_at or self._clock()
        action_ev = None
        if analysis.ev_result is not None:
            action_ev = [
                {'action': a.action, 'amount': a.amount, 'ev': a.ev,
                 'status': a.status, 'reason': a.reason}
                for a in analysis.ev_result.actions
            ]
        metadata = {
            'source': 'hu_experimental_capture',
            'hero_seat': analysis.state.hero_seat,
            'villain_seat': analysis.state.villain_seat,
            'state_status': analysis.state.status,
            'state_reason': analysis.state.reason,
            'observed_fields': list(analysis.state.observed_fields),
            'capture_source': analysis.capture_source,
            'warnings': list(analysis.warnings),
            'elapsed_ms': dict(analysis.elapsed_ms),
            'experimental_only': True,
        }
        return HUPrediction(
            prediction_id=pid,
            emitted_at=emitted,
            hero_position=analysis.state.hero_position or 'UNKNOWN',
            canonical_status=analysis.canonical_status,
            coverage_state=analysis.coverage_state,
            sequence_status=analysis.sequence_status,
            range_kind=analysis.range_kind,
            range_source=analysis.range_source,
            range_provenance=analysis.range_provenance or None,
            response_distribution=None,
            equity=analysis.equity,
            equity_scenario=('showdown_vs_flat_prior'
                             if analysis.equity is not None else None),
            equity_method=analysis.equity_method,
            action_ev=action_ev,
            selected_action=analysis.selected_action,
            provisional_selected_action=(
                analysis.provisional_selected_action
                if analysis.provisional_selected_action != analysis.selected_action
                else None),
            legal_actions=list(analysis.legal_actions),
            uncertainty_reasons=list(analysis.uncertainty_reasons),
            pot=analysis.state.pot,
            to_call=analysis.state.to_call,
            hero_stack=analysis.state.hero_stack,
            villain_stack=analysis.state.villain_stack,
            board=list(analysis.state.board),
            hero_cards=list(analysis.state.hero_cards),
            prior_actions=(list(analysis.state.raw_state.get('preflop_actions'))
                           if analysis.state.raw_state.get('preflop_actions')
                           is not None else None),
            code_version=EXPERIMENTAL_VERSION,
            data_snapshot_id=None,
            assumptions=list(analysis.assumptions),
            metadata=metadata,
        )

    def register_analysis(self, analysis: ExperimentalAnalysis, *,
                          prediction_id: Optional[str] = None,
                          emitted_at: Optional[str] = None
                          ) -> PredictionRegistration:
        """Persiste una analisis ya calculado, sin volver a capturar.

        Permite que la GUI congele la prediccion mostrada y la registre despues
        sin recalcularla (importante en preflop, donde el motor live muestrea).
        """
        if not isinstance(analysis, ExperimentalAnalysis):
            raise TypeError('analysis debe ser ExperimentalAnalysis')
        prediction = self.build_prediction(
            analysis, prediction_id=prediction_id, emitted_at=emitted_at)
        event = self.registry.register_prediction(prediction)
        return PredictionRegistration(
            analysis=analysis,
            prediction=prediction,
            event=event,
            registry_path=str(self.registry_path),
        )

    def predict_and_register(self, source: Any = None, *,
                             prediction_id: Optional[str] = None,
                             emitted_at: Optional[str] = None
                             ) -> PredictionRegistration:
        analysis = self.analyze(source)
        return self.register_analysis(
            analysis, prediction_id=prediction_id, emitted_at=emitted_at)

    def record_outcome(self, prediction_id: str, *,
                       outcome_id: Optional[str] = None,
                       observed_at: Optional[str] = None,
                       observed_action: Optional[str] = None,
                       new_information: Optional[Mapping[str, Any]] = None,
                       result: Optional[Mapping[str, Any]] = None,
                       exclusion_reason: Optional[str] = None,
                       notes: Optional[str] = None) -> Mapping[str, Any]:
        outcome = HUOutcome(
            outcome_id=outcome_id or uuid.uuid4().hex,
            prediction_id=prediction_id,
            observed_at=observed_at or self._clock(),
            observed_action=observed_action,
            new_information=new_information,
            result=result,
            exclusion_reason=exclusion_reason,
            notes=notes,
        )
        return self.registry.register_outcome(outcome)

    def verify(self) -> VerificationResult:
        return self.registry.verify_integrity()

    def create_backup(self, backup_path: Optional[Any] = None):
        if backup_path is None:
            self.config.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup_path = self.config.backup_dir / (
                '%s.%s.jsonl' % (self.registry_path.stem, stamp))
        return self.registry.create_backup(backup_path)

    def restore_backup(self, backup_path: Any, *, destination: Optional[Any] = None,
                       overwrite: bool = False) -> Path:
        return self.registry.restore_backup(backup_path, destination,
                                            overwrite=overwrite)
