"""Contrato puro de EV para HU (HU-P3, preparación).

Este módulo no activa live ni serving. Fija una frontera mínima entre:

- estado del bote y stacks;
- equity disponible o incierta;
- respuesta modelada del rival;
- EV por acción;
- selección de la mejor acción disponible.

Un EV no se inventa cuando falta equity, cobertura o respuesta del rival: la
acción queda `unknown` con una razón inspeccionable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import math

CONTRACT = 'hu_ev_contract_v1'

EV_CONVENTION = (
    'EV se calcula desde el momento de decision del heroe. '
    'pot es el bote actual antes de su accion e incluye contribuciones '
    'anteriores del heroe y del rival. to_call es el importe adicional '
    'necesario para igualar una apuesta vigente. Las acciones devuelven EV neto '
    'de la decision (fold=0). Equity es la probabilidad de ganar el showdown '
    'relevante para la accion; no se mezcla con equity actual cuando la accion '
    'llega a showdown. Unidades: fichas/BB; precision de punto flotante de Python.'
)

EV_ASSUMPTIONS = (
    'Bet EV asume abandono obligatorio del heroe ante un raise rival '
    '(pr * -amount). No modela una respuesta posterior del heroe al raise; '
    'si se requiere esa respuesta, el escenario no esta soportado por este '
    'contrato y debe quedar unknown en una capa superior.',
    'All-in del heroe usa stack efectivo min(hero_stack, villain_stack).',
    'All-in del rival se representa con to_call igual al stack comprometido '
    'por el rival; el heroe puede igualar si hero_stack >= to_call.',
    'En HU no hay bote lateral entre dos jugadores; escenarios con bote '
    'lateral no estan representados por este contrato.',
)


def _finite_nonnegative(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} debe ser numérico')
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} debe ser finito y no negativo')
    return value


def _optional_equity(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('equity debe ser numérica o None')
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError('equity debe estar en [0,1]')
    return value


@dataclass(frozen=True)
class VillainResponse:
    """Probabilidades modeladas de respuesta a una apuesta."""
    p_fold: float
    p_call: float
    p_raise: float

    def __post_init__(self):
        for name in ('p_fold', 'p_call', 'p_raise'):
            value = _finite_nonnegative(getattr(self, name), name)
            object.__setattr__(self, name, value)
        total = self.p_fold + self.p_call + self.p_raise
        if abs(total - 1.0) > 1e-9:
            raise ValueError('las probabilidades del rival deben sumar 1')


@dataclass(frozen=True)
class EVInput:
    pot: float
    to_call: float = 0.0
    hero_stack: float = 0.0
    villain_stack: float = 0.0
    equity: Optional[float] = None
    equity_call: Optional[float] = None
    equity_raise: Optional[float] = None
    coverage: str = 'unknown'
    coverage_reason: Optional[str] = None
    response: Optional[VillainResponse] = None
    bet_fractions: Tuple[float, ...] = (0.25, 0.5, 0.75)
    allow_all_in: bool = True

    def __post_init__(self):
        object.__setattr__(self, 'pot', _finite_nonnegative(self.pot, 'pot'))
        object.__setattr__(self, 'to_call',
                           _finite_nonnegative(self.to_call, 'to_call'))
        object.__setattr__(self, 'hero_stack',
                           _finite_nonnegative(self.hero_stack, 'hero_stack'))
        object.__setattr__(self, 'villain_stack',
                           _finite_nonnegative(self.villain_stack,
                                               'villain_stack'))
        object.__setattr__(self, 'equity', _optional_equity(self.equity))
        object.__setattr__(self, 'equity_call',
                           _optional_equity(self.equity_call))
        object.__setattr__(self, 'equity_raise',
                           _optional_equity(self.equity_raise))
        if self.coverage not in ('usable', 'unknown', 'coverage_gap',
                                 'impossible', 'alias', 'exact'):
            raise ValueError('coverage inválida')
        if self.coverage != 'usable' and self.equity is not None:
            raise ValueError('equity disponible exige coverage usable')
        if self.coverage == 'usable' and self.equity is None:
            raise ValueError('coverage usable exige equity')
        if self.response is not None and not isinstance(self.response,
                                                       VillainResponse):
            raise TypeError('response debe ser VillainResponse o None')
        fractions = tuple(float(x) for x in (self.bet_fractions or ()))
        for value in fractions:
            if not math.isfinite(value) or not 0.0 < value <= 1.0:
                raise ValueError('bet_fractions debe contener valores en (0,1]')
        object.__setattr__(self, 'bet_fractions', fractions)
        object.__setattr__(self, 'allow_all_in', bool(self.allow_all_in))


@dataclass(frozen=True)
class ActionEV:
    action: str
    amount: float
    ev: Optional[float]
    status: str
    reason: Optional[str] = None

    def __post_init__(self):
        if not self.action:
            raise ValueError('action no puede estar vacío')
        if self.amount < 0:
            raise ValueError('amount no puede ser negativo')
        if self.status not in ('usable', 'unknown', 'unavailable'):
            raise ValueError('status de acción inválido')
        if self.ev is not None:
            if not math.isfinite(self.ev):
                raise ValueError('ev debe ser finito')
            if self.status != 'usable':
                raise ValueError('ev disponible exige status usable')
        elif self.status == 'usable':
            raise ValueError('status usable exige ev')


@dataclass(frozen=True)
class EVResult:
    inputs: EVInput
    actions: Tuple[ActionEV, ...]
    best_action: Optional[str]
    best_ev: Optional[float]
    status: str

    def as_dict(self) -> dict:
        return {
            'contract': CONTRACT,
            'status': self.status,
            'best_action': self.best_action,
            'best_ev': self.best_ev,
            'actions': [
                {'action': a.action, 'amount': a.amount, 'ev': a.ev,
                 'status': a.status, 'reason': a.reason}
                for a in self.actions
            ],
        }


def _bet_ev(inp: EVInput, amount: float, *, all_in: bool = False) -> Optional[float]:
    if inp.response is None:
        return None
    pf = inp.response.p_fold
    pc = inp.response.p_call
    pr = inp.response.p_raise
    pot = inp.pot
    eq_call = inp.equity_call if inp.equity_call is not None else inp.equity
    if eq_call is None:
        return None
    if all_in:
        return (pf * pot
                + (pc + pr) * (eq_call * (pot + 2.0 * amount) - amount))
    ev = pf * pot + pc * (eq_call * (pot + 2.0 * amount) - amount)
    # El raise rival sigue asumiendo abandono obligatorio del heroe.
    ev += pr * (-amount)
    return ev


def calculate_ev(inp: EVInput) -> EVResult:
    if not isinstance(inp, EVInput):
        raise TypeError('inp debe ser EVInput')

    pot = inp.pot
    to_call = inp.to_call
    equity = inp.equity
    actions = []

    # Fold: EV cero por definición, sin depender de equity.
    actions.append(ActionEV(action='fold', amount=0.0, ev=0.0,
                           status='usable', reason=None))

    # Check solo tiene sentido sin apuesta pendiente.
    if to_call <= 0:
        if equity is None:
            actions.append(ActionEV(action='check', amount=0.0, ev=None,
                                   status='unknown',
                                   reason=inp.coverage_reason or 'equity_unknown'))
        else:
            actions.append(ActionEV(action='check', amount=0.0,
                                   ev=equity * pot, status='usable',
                                   reason=None))

    # Call / all-in call.
    if to_call > 0:
        if inp.hero_stack > 0 and to_call > inp.hero_stack + 1e-12:
            amount = inp.hero_stack
            if equity is None:
                actions.append(ActionEV(action='call', amount=amount, ev=None,
                                       status='unknown',
                                       reason=inp.coverage_reason or
                                       'equity_unknown'))
            else:
                ev = equity * (pot + 2.0 * amount) - amount
                actions.append(ActionEV(action='call', amount=amount, ev=ev,
                                       status='usable', reason='all_in_call'))
        elif inp.hero_stack <= 0:
            pass
        else:
            if equity is None:
                actions.append(ActionEV(action='call', amount=to_call, ev=None,
                                       status='unknown',
                                       reason=inp.coverage_reason or
                                       'equity_unknown'))
            else:
                ev = equity * (pot + 2.0 * to_call) - to_call
                actions.append(ActionEV(action='call', amount=to_call, ev=ev,
                                       status='usable', reason=None))

    # Bets a fracciones del bote.
    for frac in inp.bet_fractions:
        amount = pot * frac
        if amount <= 0:
            continue
        if inp.hero_stack > 0:
            amount = min(amount, inp.hero_stack)
        if inp.villain_stack > 0:
            amount = min(amount, inp.villain_stack)
        if amount <= 0:
            continue
        if inp.response is None:
            actions.append(ActionEV(action=f'bet_{int(round(frac * 100))}',
                                   amount=amount, ev=None, status='unknown',
                                   reason='villain_response_unknown'))
            continue
        if equity is None:
            actions.append(ActionEV(action=f'bet_{int(round(frac * 100))}',
                                   amount=amount, ev=None, status='unknown',
                                   reason=inp.coverage_reason or
                                   'equity_unknown'))
            continue
        ev = _bet_ev(inp, amount)
        if ev is None:
            actions.append(ActionEV(action=f'bet_{int(round(frac * 100))}',
                                   amount=amount, ev=None, status='unknown',
                                   reason='bet_ev_unavailable'))
        else:
            actions.append(ActionEV(action=f'bet_{int(round(frac * 100))}',
                                   amount=amount, ev=ev, status='usable',
                                   reason=None))

    # All-in.
    if inp.allow_all_in:
        if inp.hero_stack > 0 and inp.villain_stack > 0:
            amount = min(inp.hero_stack, inp.villain_stack)
        else:
            amount = 0.0
        if amount > 0:
            if inp.response is None or equity is None:
                reason = ('villain_response_unknown' if inp.response is None
                          else (inp.coverage_reason or 'equity_unknown'))
                actions.append(ActionEV(action='all_in', amount=amount, ev=None,
                                       status='unknown', reason=reason))
            else:
                ev = _bet_ev(inp, amount, all_in=True)
                if ev is None:
                    actions.append(ActionEV(action='all_in', amount=amount,
                                           ev=None, status='unknown',
                                           reason='all_in_ev_unavailable'))
                else:
                    actions.append(ActionEV(action='all_in', amount=amount,
                                           ev=ev, status='usable',
                                           reason=None))

    usable = [a for a in actions if a.status == 'usable' and a.ev is not None]
    if usable:
        best = max(usable, key=lambda a: a.ev)
        best_action = best.action
        best_ev = best.ev
        status = 'usable'
    else:
        best_action = None
        best_ev = None
        status = 'unknown'

    return EVResult(inputs=inp, actions=tuple(actions),
                    best_action=best_action, best_ev=best_ev, status=status)