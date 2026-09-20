"""recommend_loop.py — orquestador anytime del asistente de decisiones.

Recibe el estado de la mano (hero, board, calle, bote, stacks, rivales),
construye el rango rival, calcula Situation + EV y devuelve la recomendación
antes del deadline (por defecto 8 s, ARQUITECTURA §7). Cada etapa mide su
tiempo; si se agota el presupuesto devuelve la mejor información calculada
(anytime: nunca bloquea).

Inicialización del rango rival (MVP + pegar6):
    1. Si se pasa `range_model` (player_ranges) y `villain_player`: el
       rango rival es el del jugador (perfil · ω individual), prob_vec_player.
    2. Si no: posición del rival → OR de las tablas preflop (opening_range).
    3. Blockers: cartas hero + board.
    4. Postflop: con `postflop_model` (postflop_ranges) el rango rival se
       actualiza por calle con P(A|H) del perfil (buckets de fuerza).
"""
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Union

import numpy as np

from .decision import EvTable, compute_evs
from .panel import format_insight
from .preflop import opening_range
from .ranges import RangeState
from .situation import Situation, situation

BB = 1.0  # big blind nominal (BB del juego); ajustarla en caso real


@dataclass
class Recommendation:
    """Resultado del orquestador anytime."""
    action: str
    value: float
    situation: Situation
    evs: EvTable
    villain_label: str
    elapsed_ms: float = 0.0
    stages: Dict[str, float] = field(default_factory=dict)
    runout: bool = False

    @property
    def text(self) -> str:
        return format_insight(self.situation, self.evs, self.villain_label,
                              runout=self.runout)


def _build_villain_range(hero_codes, board_codes, villain_pos='UTG',
                         villain_cards=(), range_model=None,
                         villain_player=''):
    """RangeState del rival: OR preflop + blockers, o rango perfilado si se
    pasa un ProfileRangeModel + jugador (player_ranges.py)."""
    if range_model is not None and villain_player:
        reach = range_model.prob_vec_player(
            villain_player, 'no_raise', 'open', villain_pos)
    else:
        reach = opening_range(villain_pos)
    rs = RangeState(reach=reach)
    rs.set_known_cards(list(hero_codes) + list(board_codes))
    if villain_cards:
        rs.set_known_cards(list(villain_cards))
    return rs


def build_villain_range(hero_codes, board_codes, villain_pos='UTG',
                        villain_cards=(), range_model=None,
                        villain_player=''):
    """Público: igual que el interno pero devolviendo RangeState con `weights`."""
    return _build_villain_range(hero_codes, board_codes, villain_pos,
                                villain_cards, range_model, villain_player)


def recommend(hero_codes, board_codes, *, pot: float, to_call: float = 0.0,
              stack: float = 0.0, street: str = 'flop', position: str = '',
              villain_pos: str = 'UTG', villain_cards: tuple = (),
              villain_reach: Union[None, RangeState, np.ndarray] = None,
              range_model=None, villain_player: str = '',
              postflop_model=None, villain_postflop=None,
              deadline_s: float = 8.0,
              runout: bool = True,
              on_progress: Optional[Callable[[str], None]] = None) -> Recommendation:
    """Recomienda acción para el hero con la mano y el estado dados.

    hero_codes  : ['Ah', 'Kd'] — 2 cartas conocidas
    board_codes : hasta 5 cartas del board (puede ser parcial según street)
    street      : 'flop' | 'turn' | 'river' (informativo/cap de board)
    pot / to_call / stack : números del bote y de la acción en curso
    villain_pos : posición del rival para su rango base (OR)
    range_model : ProfileRangeModel (player_ranges) opcional; con él y
                  `villain_player` el rango rival es el perfilado (perfil·ω)
                  en lugar de la población.
    postflop_model : PostflopRangeModel (postflop_ranges) opcional; con
                     `villain_postflop` (lista de (street, facing, action)
                     ya observadas del rival, e.g. [('flop', 'none', 'b')])
                     el rango rival se refina por calle con P(A|H).
    runout      : si True (predeterminado) y faltan cartas del board, todas
                  las acciones usan equity a showdown por combo con sorteo
                  determinista de turn+river. `False` habilita el modo rápido
                  de fuerza actual.
    deadline_s  : presupuesto anytime máximo (métrico, rápido hoy)
    """
    t0 = time.perf_counter()
    stages: Dict[str, float] = {}

    def _stage(name, t_ref):
        stages[name] = (time.perf_counter() - t_ref) * 1000

    t = time.perf_counter()
    if villain_reach is None:
        villain = _build_villain_range(hero_codes, board_codes, villain_pos,
                                       villain_cards, range_model,
                                       villain_player)
        if range_model is not None and villain_player:
            perfil = range_model.perfil.get(villain_player, '?')
            villain_label = f'{perfil} wJ {villain_player}' \
                if range_model.player_omega(villain_player, 'no_raise') != 1.0 \
                else f'{perfil} {villain_player}'
        else:
            villain_label = f'OR {villain_pos}'
    else:
        rs = (villain_reach if isinstance(villain_reach, RangeState)
              else RangeState(reach=villain_reach))
        rs.set_known_cards(list(hero_codes) + list(board_codes))
        villain = rs
        villain_label = 'rango dado'
    _stage('range', t)

    t = time.perf_counter()
    if postflop_model is not None and villain_postflop:
        perfil = getattr(postflop_model, 'labels', {}).get(villain_player)
        if perfil:
            for street, facing, action in villain_postflop:
                board = board_codes
                vec = postflop_model.prob_vec(perfil, street, facing,
                                              board, action)
                villain.update(vec)
    _stage('postflop', t)

    t = time.perf_counter()
    sit = situation(hero_codes, board_codes, villain_reach=villain,
                    pot_before_call=pot, to_call=to_call,
                    stack_effective=stack, position=position, street=street)
    _stage('situation', t)

    if on_progress:
        on_progress(f'  ... situación {stages["situation"]:.1f} ms')

    t = time.perf_counter()
    evs = compute_evs(hero_codes, board_codes, villain_reach=villain,
                      pot=pot, to_call=to_call, stack=stack, runout=runout)
    _stage('ev', t)

    action, value = evs.best()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    stages['total'] = elapsed_ms
    stages['budget'] = deadline_s * 1000 - elapsed_ms  # margen restante

    return Recommendation(action=action, value=value, situation=sit, evs=evs,
                          villain_label=villain_label, elapsed_ms=elapsed_ms,
                          stages=stages, runout=runout)


def run_demo(runout: bool = False):
    """Demo: JdJh vs OR UTG en flop Qh 7s 2c (misma mano del banco de pruebas).

    Con `runout=True` las ramas pasivas usan la equity a showdown con sorteo
    de turn+river (~1-2 s con rango completo; el presupuesto anytime de 8 s
    queda cubierto).
    """
    rec = recommend(
        ['Jd', 'Jh'], ['Qh', '7s', '2c'],
        street='flop', position='BB', villain_pos='UTG',
        pot=12.5, to_call=5.0, stack=90.0,
        runout=runout,
    )
    print(rec.text)
    print(f'\n->> {rec.action} (+{rec.value:.2f} BB) · {rec.elapsed_ms:.1f} ms '
          f'| tiempos {rec.stages}')
    return rec


if __name__ == '__main__':
    import sys
    from motor.preflop import preload
    preload()
    run_demo(runout='--runout' in sys.argv)
