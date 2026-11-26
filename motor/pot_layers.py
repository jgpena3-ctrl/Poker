"""Contribution layers and side pots for experimental poker calculations.

Inputs are total committed contributions for the hand, not current stacks or
street bets. Folded players contribute to pot sizes but are never eligible to
win. Unmatched top contributions are returned rather than counted as a pot.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Tuple


class PotLayerError(ValueError):
    """Contradictory or incomplete contribution/eligibility state."""


@dataclass(frozen=True)
class PotLayer:
    amount: float
    cap: float
    contributors: Tuple[str, ...]
    eligible: Tuple[str, ...]


@dataclass(frozen=True)
class PotLayers:
    pots: Tuple[PotLayer, ...]
    returned_uncalled: Tuple[Tuple[str, float], ...]
    total_contributed: float
    total_pot: float

    def as_dict(self) -> dict:
        return {
            'pots': [
                {'amount': p.amount, 'cap': p.cap,
                 'contributors': list(p.contributors),
                 'eligible': list(p.eligible)}
                for p in self.pots
            ],
            'returned_uncalled': [
                {'player': player, 'amount': amount}
                for player, amount in self.returned_uncalled
            ],
            'total_contributed': self.total_contributed,
            'total_pot': self.total_pot,
        }


@dataclass(frozen=True)
class PotSettlement:
    payouts: Tuple[Tuple[str, float], ...]
    total_awarded: float

    def as_dict(self) -> dict:
        return {'payouts': dict(self.payouts),
                'total_awarded': self.total_awarded}


def build_pot_layers(contributions: Mapping[str, float],
                     folded=()) -> PotLayers:
    """Split committed chips into a main pot and side-pot layers.

    A tranche with only one contributor at the current level is an uncalled
    excess and is returned. Tranches with multiple contributors remain pots
    even if folds leave only one eligible player to collect them.
    """
    if not isinstance(contributions, Mapping) or not contributions:
        raise PotLayerError('contributions debe ser un mapping no vacío')
    folded = set(folded or ())
    normalized = {}
    for player, raw_amount in contributions.items():
        if not isinstance(player, str) or not player.strip():
            raise PotLayerError('cada contribuyente requiere identidad')
        if isinstance(raw_amount, bool) or not isinstance(raw_amount, (int, float)):
            raise PotLayerError(f'contribución inválida para {player}')
        amount = float(raw_amount)
        if not math.isfinite(amount) or amount < 0:
            raise PotLayerError(f'contribución inválida para {player}')
        normalized[player] = amount
    unknown_folded = folded - set(normalized)
    if unknown_folded:
        raise PotLayerError(
            'folded contiene jugadores sin contribución: %s' %
            ', '.join(sorted(unknown_folded)))
    if not any(amount > 0 for amount in normalized.values()):
        raise PotLayerError('no hay contribuciones positivas')
    if all(player in folded or amount <= 0
           for player, amount in normalized.items()):
        raise PotLayerError('no hay ningún jugador elegible en el bote')

    levels = sorted({amount for amount in normalized.values() if amount > 0})
    previous = 0.0
    pots = []
    returns = {}
    for cap in levels:
        contributors = tuple(
            player for player, amount in normalized.items()
            if amount >= cap)
        tranche = (cap - previous) * len(contributors)
        if len(contributors) == 1:
            player = contributors[0]
            if player in folded:
                raise PotLayerError(
                    'una contribución no igualada no puede devolverse a un '
                    'jugador que foldeó')
            returns[player] = returns.get(player, 0.0) + tranche
        else:
            eligible = tuple(p for p in contributors if p not in folded)
            if not eligible:
                raise PotLayerError(
                    'una capa de bote no tiene jugadores elegibles')
            pots.append(PotLayer(
                amount=tranche, cap=cap, contributors=contributors,
                eligible=eligible))
        previous = cap

    total_contributed = sum(normalized.values())
    returned = sum(returns.values())
    total_pot = sum(p.amount for p in pots)
    if not math.isclose(total_contributed, returned + total_pot,
                        rel_tol=1e-12, abs_tol=1e-9):
        raise PotLayerError('conservación de fichas inconsistente')
    return PotLayers(
        pots=tuple(pots),
        returned_uncalled=tuple(sorted(returns.items())),
        total_contributed=total_contributed,
        total_pot=total_pot)


def settle_pot_layers(layers: PotLayers,
                      winners_by_cap: Mapping[float, Tuple[str, ...]]) \
        -> PotSettlement:
    """Split each layer equally among declared winners and include returns.

    This is a mechanical payout helper; it does not evaluate hands or infer
    winners. The caller must supply a non-empty, eligible winner set for every
    contested layer.
    """
    if not isinstance(layers, PotLayers):
        raise TypeError('layers debe ser PotLayers')
    if not isinstance(winners_by_cap, Mapping):
        raise PotLayerError('winners_by_cap debe ser Mapping')
    payouts = {}
    for player, amount in layers.returned_uncalled:
        payouts[player] = payouts.get(player, 0.0) + amount
    expected_caps = {layer.cap for layer in layers.pots}
    if set(winners_by_cap) != expected_caps:
        raise PotLayerError('debe declarar ganadores para cada capa, sin extras')
    for layer in layers.pots:
        winners = tuple(winners_by_cap[layer.cap] or ())
        if not winners or len(set(winners)) != len(winners):
            raise PotLayerError('cada capa requiere ganadores distintos')
        if set(winners) - set(layer.eligible):
            raise PotLayerError('ganador no elegible para su capa')
        share = layer.amount / len(winners)
        for player in winners:
            payouts[player] = payouts.get(player, 0.0) + share
    total = sum(payouts.values())
    if not math.isclose(total, layers.total_contributed,
                        rel_tol=1e-12, abs_tol=1e-9):
        raise PotLayerError('settlement no conserva las contribuciones')
    return PotSettlement(tuple(sorted(payouts.items())), total)
