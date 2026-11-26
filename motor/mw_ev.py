"""Fail-closed multiway EV for forced-showdown decision nodes.

This first EV scope handles check/call/fold only when every remaining rival is
already all-in or folded. Nodes where an opponent can still choose an action
are explicitly incomplete until a supported response tree is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Optional, Tuple

from .mw_equity import MultiwayEquityResult
from .mw_ranges import MWRangeError
from .pot_layers import PotLayerError, PotLayers, build_pot_layers


CONTRACT = 'mw_ev_forced_showdown_v1'
INDEPENDENT_BASELINE = \
    'independent_marginals_conditioned_on_no_card_collision'


@dataclass(frozen=True)
class EquityEvidence:
    equity: float
    exact: bool
    standard_error: Optional[float]
    model: str
    model_complete: bool = True
    opponents: Tuple[str, ...] = ()

    @classmethod
    def from_result(cls, result: MultiwayEquityResult):
        if not isinstance(result, MultiwayEquityResult):
            raise TypeError('result debe ser MultiwayEquityResult')
        return cls(result.equity, result.exact, result.standard_error,
                   result.model,
                   not result.limitations and result.model != INDEPENDENT_BASELINE,
                   tuple(sorted(result.opponents)))

    def __post_init__(self):
        if not math.isfinite(float(self.equity)) or not 0 <= self.equity <= 1:
            raise ValueError('equity debe estar en [0,1]')
        if not self.model:
            raise ValueError('model es obligatorio')
        if tuple(sorted(self.opponents)) != self.opponents:
            raise ValueError('opponents de EquityEvidence debe estar ordenado')
        if not self.opponents:
            raise ValueError('EquityEvidence requiere identidades de rivales')
        if not isinstance(self.model_complete, bool):
            raise ValueError('model_complete debe ser bool')
        if self.model == INDEPENDENT_BASELINE and self.model_complete:
            object.__setattr__(self, 'model_complete', False)
        if self.standard_error is not None and (
                not math.isfinite(self.standard_error)
                or self.standard_error < 0):
            raise ValueError('standard_error inválido')
        if self.exact and self.standard_error not in (None, 0, 0.0):
            raise ValueError('equity exacta no debe declarar error muestral')


@dataclass(frozen=True)
class MWActionEV:
    action: str
    amount: float
    ev: Optional[float]
    status: str
    reason: Optional[str] = None


@dataclass(frozen=True)
class MWGameEVInput:
    hero_id: str
    contributions: Mapping[str, float]
    player_status: Mapping[str, str]
    hero_stack: float
    to_call: float
    # Key is the sorted tuple of eligible opponents in each pot layer.
    equity_by_opponents: Mapping[Tuple[str, ...], EquityEvidence]
    input_uncertainty: Tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.hero_id, str) or not self.hero_id.strip():
            raise ValueError('hero_id obligatorio')
        if self.hero_id not in self.contributions:
            raise ValueError('hero debe tener contribución declarada')
        if set(self.contributions) != set(self.player_status):
            raise ValueError('contributions y player_status deben coincidir')
        for player, amount in self.contributions.items():
            if (not isinstance(player, str) or not player.strip()
                    or isinstance(amount, bool)
                    or not isinstance(amount, (int, float))
                    or not math.isfinite(float(amount)) or amount < 0):
                raise ValueError('contribución inválida')
        if any(status not in ('active', 'all_in', 'folded')
               for status in self.player_status.values()):
            raise ValueError('player_status inválido/ambiguo')
        if self.player_status[self.hero_id] != 'active':
            raise ValueError('hero debe poder tomar la decisión')
        for name, value in (('hero_stack', self.hero_stack),
                            ('to_call', self.to_call)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(float(value)) or value < 0:
                raise ValueError(f'{name} debe ser finito y no negativo')
        if not isinstance(self.equity_by_opponents, Mapping):
            raise ValueError('equity_by_opponents debe ser Mapping')
        for key, evidence in self.equity_by_opponents.items():
            if (not isinstance(key, tuple) or not key
                    or any(not isinstance(player, str) for player in key)
                    or tuple(sorted(key)) != key or self.hero_id in key
                    or set(key) - set(self.player_status)):
                raise ValueError('claves de equity deben ser rivales ordenados')
            if not isinstance(evidence, EquityEvidence):
                raise TypeError('equity debe ser EquityEvidence')
            if evidence.opponents != key:
                raise ValueError('identidades de equity no coinciden con su clave')
        if self.to_call > 0 and self.hero_stack <= 0:
            raise ValueError('hero sin stack no puede afrontar call positivo')


@dataclass(frozen=True)
class MWGameEVResult:
    status: str
    actions: Tuple[MWActionEV, ...]
    reason: Optional[str]
    pot_layers: Optional[PotLayers]
    response_scope: str
    input_uncertainty: Tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            'contract': CONTRACT,
            'status': self.status,
            'reason': self.reason,
            'response_scope': self.response_scope,
            'input_uncertainty': list(self.input_uncertainty),
            'actions': [
                {'action': action.action, 'amount': action.amount,
                 'ev': action.ev, 'status': action.status,
                 'reason': action.reason}
                for action in self.actions
            ],
            'pot_layers': (self.pot_layers.as_dict()
                           if self.pot_layers is not None else None),
        }


def _payout_expectation(hero_id, layers, evidence_by_opponents):
    expected = 0.0
    provisional = False
    limitations = set()
    for layer in layers.pots:
        if hero_id not in layer.eligible:
            continue
        eligible_opponents = tuple(sorted(
            p for p in layer.eligible if p != hero_id))
        if not eligible_opponents:
            share = 1.0
        else:
            evidence = evidence_by_opponents.get(eligible_opponents)
            if evidence is None:
                return None, False, (
                    'equity_missing_for_eligible_subset:' +
                    ','.join(eligible_opponents)), ()
            if evidence.opponents and evidence.opponents != eligible_opponents:
                return None, False, 'equity_opponent_identity_mismatch', ()
            share = evidence.equity
            if not evidence.exact:
                provisional = True
                limitations.add('sampled_equity_uncertainty')
            if not evidence.model_complete:
                provisional = True
                limitations.add(
                    'independent_marginals_baseline'
                    if evidence.model == INDEPENDENT_BASELINE else
                    'equity_model_incomplete')
        expected += layer.amount * share
    hero_returns = sum(amount for player, amount in layers.returned_uncalled
                       if player == hero_id)
    return expected + hero_returns, provisional, None, tuple(sorted(limitations))


def calculate_mw_ev(inp: MWGameEVInput) -> MWGameEVResult:
    """Compute only showdown-locked check/call/fold outcomes.

    Fold EV is incremental and therefore zero. If one or more opponents can
    still act, check/call values are withheld; no independent response
    probabilities or HU EV formula is introduced.
    """
    if not isinstance(inp, MWGameEVInput):
        raise TypeError('inp debe ser MWGameEVInput')
    opponent_status = {p: status for p, status in inp.player_status.items()
                       if p != inp.hero_id}
    responses_locked = all(status in ('all_in', 'folded')
                           for status in opponent_status.values())
    actions = [MWActionEV('fold', 0.0, 0.0, 'complete')]
    if not responses_locked:
        if inp.to_call <= 0:
            actions.append(MWActionEV(
                'check', 0.0, None, 'incomplete',
                'opponent_response_tree_unavailable'))
        else:
            amount = min(float(inp.to_call), float(inp.hero_stack))
            if amount > 0:
                actions.append(MWActionEV(
                    'call', amount, None, 'incomplete',
                    'opponent_response_tree_unavailable'))
        return MWGameEVResult(
            'incomplete', tuple(actions),
            'no_supported_multiway_response_likelihood', None,
            'responses_not_locked')

    if inp.to_call > inp.hero_stack + 1e-12:
        amount = float(inp.hero_stack)
    else:
        amount = float(inp.to_call)
    contributions = dict(inp.contributions)
    contributions[inp.hero_id] = float(contributions[inp.hero_id]) + amount
    folded = {p for p, status in inp.player_status.items() if status == 'folded'}
    try:
        layers = build_pot_layers(contributions, folded=folded)
    except PotLayerError as exc:
        return MWGameEVResult(
            'incomplete', tuple(actions), f'pot_layers_invalid:{exc}', None,
            'forced_showdown_only')
    if amount > 0:
        action_name = 'call' if amount >= inp.to_call else 'all_in_call'
    else:
        action_name = 'check'
    payout, provisional, error, limitations = _payout_expectation(
        inp.hero_id, layers, inp.equity_by_opponents)
    if error:
        actions.append(MWActionEV(action_name, amount, None, 'incomplete', error))
        return MWGameEVResult('incomplete', tuple(actions), error, layers,
                              'forced_showdown_only')
    value = payout - amount
    provisional = provisional or bool(inp.input_uncertainty)
    action_status = 'provisional' if provisional else 'complete'
    actions.append(MWActionEV(action_name, amount, value, action_status))
    overall = 'provisional' if provisional else 'complete'
    reason = ('state_fields_inferred' if inp.input_uncertainty else
              ';'.join(limitations) if limitations else None)
    return MWGameEVResult(
        overall, tuple(actions), reason, layers,
        'all_remaining_rivals_all_in_or_folded', inp.input_uncertainty)


def mw_ev_input_from_state(state, equity_by_opponents) -> MWGameEVInput:
    """Adapt an interpreted MW state; missing chips/stack evidence fails closed."""
    if not getattr(state, 'can_proceed_strategically', False):
        raise MWRangeError('estado MW no permite evaluar decisión estratégica')
    hero = state.hero
    if hero is None or hero.stack.source == 'unknown' \
            or hero.contribution.source == 'unknown' \
            or state.to_call.source == 'unknown' \
            or state.pot.source == 'unknown':
        raise MWRangeError('stack/contribución/to_call/pot desconocido')
    contributions = {}
    statuses = {}
    for player in state.players:
        if player.contribution.source == 'unknown' \
                or player.status.source == 'unknown':
            raise MWRangeError(
                f'contribución/estado desconocido para {player.identity}')
        contributions[player.identity] = player.contribution.value
        statuses[player.identity] = player.status.value
    if not math.isclose(sum(contributions.values()), state.pot.value,
                        rel_tol=1e-9, abs_tol=1e-6):
        raise MWRangeError('pot no coincide con las contribuciones observadas')
    inferred = []
    for player in state.players:
        for field_name in ('status', 'stack', 'contribution'):
            if getattr(player, field_name).source == 'inferred':
                inferred.append(f'{player.identity}:{field_name}')
    for field_name, evidence in (('to_call', state.to_call),
                                 ('pot', state.pot),
                                 ('hero_stack', hero.stack)):
        if evidence.source == 'inferred':
            inferred.append(field_name)
    if state.actor.source == 'inferred':
        inferred.append('actor')
    if state.facing_action.source == 'inferred':
        inferred.append('facing_action')
    return MWGameEVInput(
        hero_id=state.hero_id, contributions=contributions,
        player_status=statuses, hero_stack=hero.stack.value,
        to_call=state.to_call.value,
        equity_by_opponents=equity_by_opponents,
        input_uncertainty=tuple(inferred))
