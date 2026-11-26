"""HU/MW experimental action-evaluation router; never used by live serving."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from .hu_evaluation import HUEvaluationInput, evaluate_hu
from .mw_response_tree import (
    ActionSpec, MWTreeInput, MWTreeLimits, MWTreeResult,
    ResponseProvider, evaluate_mw_action_tree,
)


@dataclass(frozen=True)
class ActionEvaluation:
    mode: Optional[str]
    status: str
    result: Any
    reason: Optional[str]

    def as_dict(self) -> dict:
        payload = (self.result.as_dict() if self.result is not None
                   and callable(getattr(self.result, 'as_dict', None)) else None)
        return {'mode': self.mode, 'status': self.status,
                'reason': self.reason, 'result': payload}


def _hu_status(result) -> str:
    status = getattr(result, 'status', None)
    if status in ('complete', 'provisional', 'incomplete', 'not_calculable'):
        return status
    if status == 'usable':
        if (getattr(result, 'supported', False)
                and getattr(result, 'ev_result', None) is not None):
            # HU evidence coverage does not establish strategic correctness.
            return 'provisional'
        return 'incomplete'
    return 'not_calculable' if result is None else 'incomplete'


def evaluate_experimental_actions(
        state, *, hu_runner: Optional[Callable] = None,
        hu_input: Optional[HUEvaluationInput] = None,
        mw_input: Optional[MWTreeInput] = None,
        mw_provider: Optional[ResponseProvider] = None,
        hero_actions: Sequence[ActionSpec] = (),
        limits: MWTreeLimits = MWTreeLimits()) -> ActionEvaluation:
    """Route by resolved active-player count before invoking either evaluator.

    ``hu_runner`` adapts the shared interpreted state to the existing HU
    contracts. It is mandatory for HU; the MW tree is never used as a HU
    fallback. Likewise, a MW state is never passed to HU when MW inputs or
    response evidence are missing.
    """
    if not getattr(state, 'ready', False) or not getattr(
            state, 'can_proceed_strategically', False):
        return ActionEvaluation(None, 'incomplete', None,
                                'ambiguous_or_nondecision_state')
    mode = getattr(state, 'mode', None)
    if mode not in ('HU', 'MW'):
        return ActionEvaluation(None, 'incomplete', None,
                                'active_opponent_count_unresolved')
    if mode == 'HU':
        if callable(hu_runner):
            try:
                result = hu_runner(state)
            except Exception as exc:
                return ActionEvaluation(
                    'HU', 'incomplete', None,
                    f'hu_evaluator_error:{type(exc).__name__}')
            return ActionEvaluation('HU', _hu_status(result), result,
                                    None if _hu_status(result) != 'incomplete'
                                    else 'hu_evaluation_incomplete')
        if not isinstance(hu_input, HUEvaluationInput):
            return ActionEvaluation(
                'HU', 'not_calculable', None, 'hu_evaluator_not_supplied')
        hero = state.hero
        opponent = state.active_opponents[0]
        if state.street != 'preflop':
            return ActionEvaluation(
                'HU', 'not_calculable', None,
                'postflop_hu_runner_adapter_required')
        if (hero is None or hero.position.source == 'unknown'
                or hero.hole_cards.source == 'unknown'
                or hero.stack.source == 'unknown'
                or opponent.stack.source == 'unknown'
                or state.pot.source == 'unknown'
                or state.to_call.source == 'unknown'):
            return ActionEvaluation(
                'HU', 'incomplete', None, 'hu_state_fields_unknown')
        if (hu_input.canonical.hero_position != hero.position.value
                or tuple(hu_input.hero_hand or ()) != tuple(hero.hole_cards.value)
                or tuple(hu_input.board) != tuple(state.board)
                or abs(float(hu_input.pot) - float(state.pot.value)) > 1e-6
                or abs(float(hu_input.to_call) - float(state.to_call.value)) > 1e-6
                or abs(float(hu_input.hero_stack) - float(hero.stack.value)) > 1e-6
                or abs(float(hu_input.villain_stack)
                       - float(opponent.stack.value)) > 1e-6):
            return ActionEvaluation(
                'HU', 'incomplete', None, 'hu_input_state_mismatch')
        try:
            result = evaluate_hu(hu_input)
        except Exception as exc:
            return ActionEvaluation(
                'HU', 'incomplete', None,
                f'hu_evaluator_error:{type(exc).__name__}')
        return ActionEvaluation('HU', _hu_status(result), result,
                                None if _hu_status(result) != 'incomplete'
                                else 'hu_evaluation_incomplete')

    # MW never silently degrades to HU, even if a HU callback was supplied.
    if mw_input is None or mw_input.state != state:
        return ActionEvaluation('MW', 'incomplete', None,
                                'matching_mw_tree_input_required')
    if mw_provider is None:
        return ActionEvaluation('MW', 'incomplete', None,
                                'multiway_response_provider_missing')
    try:
        result = evaluate_mw_action_tree(
            mw_input, hero_actions, mw_provider, limits=limits)
    except Exception as exc:
        return ActionEvaluation(
            'MW', 'incomplete', None,
            f'mw_tree_input_or_execution_error:{type(exc).__name__}')
    if not isinstance(result, MWTreeResult):
        return ActionEvaluation('MW', 'incomplete', None,
                                'mw_tree_returned_invalid_result')
    return ActionEvaluation('MW', result.status, result,
                            None if result.status != 'incomplete'
                            else 'multiway_tree_incomplete')
