"""implied_odds.py — matematica de outs, pot odds e implied odds.

Dado un numero de outs, la calle y lo que hay que pagar, calcula la equity
real del draw (cartas desconocidas exactas), las pot odds necesarias, el EV
directo del call y cuanto dinero extra habria que cobrarle al rival en calles
posteriores para que el call quede a EV 0 (implied odds).
"""
from dataclasses import dataclass

DESCONOCIDAS_FLOP = 47  # 52 - 2 propias - 3 tablero
DESCONOCIDAS_TURN = 46  # tras ver la turn


@dataclass(frozen=True)
class AnalisisCall:
    outs: int
    cartas_por_venir: int
    equity: float                 # probabilidad de completar el draw
    equity_regla_42: float        # referencia: regla del 4 y 2
    pot_odds: float               # fraccion del bote final que aporta el call
    ev_directo: float             # equity * (bote + call) - call
    rentable_directo: bool
    extra_necesario: float        # 0.0 si el call ya es rentable
    extra_pct_bote_call: float    # extra / (bote + call), como fraccion
    cobro_minimo_al_completar: float  # bote + call + extra


def equity_desde_outs(outs: int, cartas_por_venir: int) -> float:
    """Probabilidad exacta de completar al menos un out."""
    if outs <= 0:
        return 0.0
    outs = min(outs, DESCONOCIDAS_FLOP)
    if cartas_por_venir >= 2:
        no_outs = DESCONOCIDAS_FLOP - outs
        p_miss = (no_outs * (no_outs - 1)) / \
                 (DESCONOCIDAS_FLOP * (DESCONOCIDAS_FLOP - 1))
        return 1.0 - p_miss
    return outs / DESCONOCIDAS_TURN


def equity_regla(outs: int, cartas_por_venir: int) -> float:
    """Aproximacion rapida 'regla del 4 y 2'."""
    if outs <= 0:
        return 0.0
    multiplicador = 4 if cartas_por_venir >= 2 else 2
    return min(outs * multiplicador / 100.0, 1.0)


def pot_odds_necesarias(call: float, bote: float) -> float:
    """Fraccion del bote final que representa el call: call / (bote + call)."""
    bote_final = bote + call
    if bote_final <= 0:
        return 0.0
    return call / bote_final


def analizar_call(outs: int, cartas_por_venir: int, call: float,
                  bote: float) -> AnalisisCall:
    """Analiza el call: equity, pot odds, EV directo e implied odds."""
    e = equity_desde_outs(outs, cartas_por_venir)
    po = pot_odds_necesarias(call, bote)
    ev = e * (bote + call) - call
    rentable = ev >= 0
    if rentable:
        extra = 0.0
    elif e > 0:
        extra = call / e - (bote + call)
    else:
        extra = float('inf')
    if e > 0:
        cobro_minimo = call / e
    else:
        cobro_minimo = 0.0 if call <= 0 else float('inf')
    bote_final = bote + call
    extra_pct = extra / bote_final if bote_final > 0 else float('inf')
    return AnalisisCall(
        outs=outs,
        cartas_por_venir=cartas_por_venir,
        equity=e,
        equity_regla_42=equity_regla(outs, cartas_por_venir),
        pot_odds=po,
        ev_directo=ev,
        rentable_directo=rentable,
        extra_necesario=extra,
        extra_pct_bote_call=extra_pct,
        cobro_minimo_al_completar=cobro_minimo,
    )
