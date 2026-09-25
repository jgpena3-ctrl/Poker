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
from . import rules
from .hand_state import classify as classify_hand, range_advantage as ha_range_adv

# Orden postflop: primero en actuar → último
# (BTN actúa último, UTG primero)
_POSTFLOP_ORDER = ('SB', 'BB', 'UTG', 'MP', 'CO', 'BTN')

BB = 1.0  # big blind nominal (BB del juego); ajustarla en caso real


def _hero_oop(hero_pos: str, villain_pos: str) -> bool:
    """¿Hero actúa primero postflop (OOP)?

    Usa el orden de posición: hero es OOP si está antes que
    villain en _POSTFLOP_ORDER (primer actuador = OOP).
    Desconocido → True (OOP) por defecto: asumir IP sesga hacia
    call/raise; OOP es la suposición conservadora.
    """
    try:
        return _POSTFLOP_ORDER.index(hero_pos) < _POSTFLOP_ORDER.index(villain_pos)
    except (ValueError, TypeError):
        return True


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
    rule_plan: Optional[rules.RulePlan] = None

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


def _build_multiway_range(hero_codes, board_codes,
                           villain_ranges: Dict[str, RangeState]):
    """Combina múltiples RangeState en uno unión con blockers.

    Para multiway: el rango rival combinado es la unión de todos
    los rangos individuales (cada villain juega independientemente).
    Se aplican blockers (hero + board) a cada rango antes de combinar.
    el modelo multiway sigue siendo aproximado.
    """
    if not villain_ranges:
        return RangeState()
    combined = None
    known = list(hero_codes) + list(board_codes)
    for rs in villain_ranges.values():
        r = rs.copy() if hasattr(rs, 'copy') else RangeState(reach=rs.reach)
        r.set_known_cards(known)
        r.nullify_blocked()                      # blockers aplicados ANTES de unir
        combined = r if combined is None else combined.union(r)
    return combined if combined is not None else RangeState()


def build_villain_range(hero_codes, board_codes, villain_pos='UTG',
                          villain_cards=(), range_model=None,
                          villain_player='',
                          villain_ranges: Optional[Dict[str, RangeState]] = None):
    """Público: construye RangeState para HU o multiway."""
    if villain_ranges is not None and len(villain_ranges) > 0:
        return _build_multiway_range(hero_codes, board_codes, villain_ranges)
    return _build_villain_range(hero_codes, board_codes, villain_pos,
                                   villain_cards, range_model, villain_player)


def recommend(hero_codes, board_codes, *, pot: float, to_call: float = 0.0,
               stack: float = 0.0, street: str = 'flop', position: str = '',
               villain_pos: str = 'UTG', villain_cards: tuple = (),
               villain_reach: Union[None, RangeState, np.ndarray] = None,
               villain_ranges: Optional[Dict[str, RangeState]] = None,
               range_model=None, villain_player: str = '',
               postflop_model=None, villain_postflop=None,
               deadline_s: float = 8.0,
               runout: bool = True,
               on_progress: Optional[Callable[[str], None]] = None,
               hero_initiator: bool = False,
               n_players: int = 2,
               facing_raise: bool = False,
               hero_bet_flop: bool = False,
               flop_checked: bool = False,
               villain_bet_flop: bool = False,
               hand_role: str = None,
               range_advantage_str: str = None) -> Recommendation:
    """Recomienda acción para el hero con la mano y el estado dados.

    hero_codes  : ['Ah', 'Kd'] — 2 cartas conocidas
    board_codes : hasta 5 cartas del board (puede ser parcial según street)
    street      : 'flop' | 'turn' | 'river' (informativo/cap de board)
    pot / to_call / stack : números del bote y de la acción en curso
    villain_pos : posición del rival para su rango base (OR)
    villain_reach : RangeState único del rival (HU)
    villain_ranges : dict {jugador: RangeState} para multiway
    range_model : ProfileRangeModel (player_ranges) opcional; con él y
                  `villain_player` el rango rival es el perfilado (perfil·ω)
                  en lugar de la población.
    postflop_model : PostflopRangeModel (postflop_ranges) opcional; con
                     `villain_postflop` (lista de
                     (street, facing, action, board) ya observadas del
                     rival, e.g. [('flop', 'none', 'b', 'Qh,7s,2c')])
                     el rango rival se refina por calle con P(A|H).
    runout      : si True (predeterminado) y faltan cartas del board, todas
                  las acciones usan equity a showdown por combo con sorteo
                  determinista de turn+river. `False` habilita el modo rápido
                  de fuerza actual.
    deadline_s  : presupuesto anytime máximo (métrico, rápido hoy)
    hero_initiator: hero fue el último agresor preflop (§3 rules.py)
    n_players   : jugadores activos en la mano
    facing_raise: True si la apuesta rival es un raise
    hero_bet_flop: hero apostó en el flop
    flop_checked: flop fue check-check
    villain_bet_flop: rival apostó en el flop
    hand_role   : STRONG_VALUE/VALUE/MEDIUM/STRONG_DRAW/WEAK_DRAW/AIR
    range_advantage_str: 'HERO'|'NEUTRAL'|'VILLAIN' (si None se computa)
    """
    t0 = time.perf_counter()
    stages: Dict[str, float] = {}

    def _stage(name, t_ref):
        stages[name] = (time.perf_counter() - t_ref) * 1000

    # --- Validaciones de input (evitan EVs absurdos aguas abajo) ---
    if pot < 0 or to_call < 0 or stack < 0:
        raise ValueError(f'pot/to_call/stack negativos: {pot}, {to_call}, {stack}')
    if to_call > stack:
        # all-in efectivo: no se puede pagar más de lo que hay
        to_call = stack
    if facing_raise and to_call <= 0:
        raise ValueError('facing_raise=True con to_call=0')
    if villain_ranges:
        n_players = max(n_players, len(villain_ranges) + 1)

    t = time.perf_counter()
    villain_labels = []
    if villain_ranges is not None and len(villain_ranges) > 0:
        # Multiway: combinar rangos de todos los villains
        villain = _build_multiway_range(hero_codes, board_codes,
                                           villain_ranges)
        villain_labels = list(villain_ranges.keys())
        villain_label = 'multiway (' + ', '.join(villain_labels) + ')'
    elif villain_reach is None:
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
            for sp, facing, action, board_str in villain_postflop:
                board_for_update = ([c.strip() for c in board_str.split(',')]
                                     if board_str else [])
                vec = postflop_model.prob_vec(perfil, sp, facing,
                                              board_for_update, action)
                villain.update(vec)
    _stage('postflop', t)

    t = time.perf_counter()
    sit = situation(hero_codes, board_codes, villain_reach=villain,
                    pot_before_call=pot, to_call=to_call,
                    stack_effective=stack, position=position, street=street)
    _stage('situation', t)

    if on_progress:
        on_progress(f'  ... situación {stages["situation"]:.1f} ms')

    # --- Reglas y clasificación de la situación ---
    rp = None
    if hand_role is None or range_advantage_str is None:
        hs = classify_hand(hero_codes, board_codes)
        if hand_role is None:
            hand_role = hs.role
        if range_advantage_str is None:
            range_advantage_str = ha_range_adv(sit.equity)

    # Intentar plan de reglas (fase 5)
    # Durante desarrollo: excepciones visibles.
    # Producción: fallback controlado + logging.
    try:
        rp = rules.plan(
            street=street,
            hero_initiator=hero_initiator,
            to_call=to_call,
            board_codes=board_codes,
            pot=pot,
            stack=stack,
            n_players=n_players,
            facing_raise=facing_raise,
            hero_bet_flop=hero_bet_flop,
            hero_oop=_hero_oop(position, villain_pos) if street != 'preflop' else False,
            flop_checked=flop_checked,
            villain_bet_flop=villain_bet_flop,
            hand_role=hand_role,
            range_advantage=range_advantage_str,
        )
    except Exception as e:
        import sys
        print(f'[rules.plan] error: {e}', file=sys.stderr)
        rp = None

    candidates = rp.candidates if rp is not None else None

    # --- Anytime: EV en dos pasadas (rápido → refinado con runout) ---
    best_action, best_value, best_evs = None, -999.0, None
    best_runout = False

    # Guardar board actual para situation() (no se modifica)
    current_board_codes = board_codes

    # compute_evs() calcula TODAS las acciones; candidates se pasa
    # solo a rules.select_best(), NO aquí (para no filtrar prematuramente).
    # bet_sizes y raise_to SÍ vienen de RulePlan para que el EV
    # corresponda a los sizings que las reglas consideran razonables.
    if rp is not None and rp.bet_sizes:
        bet_sizes = rp.bet_sizes
        raise_to = rp.raise_to
    elif rp is not None and rp.kind_facing():
        # spot "facing": no hay bets pasivas; solo call/raise/all_in/fold
        bet_sizes = ()
        raise_to = rp.raise_to
    else:
        bet_sizes = (0.25, 0.5, 0.75)
        raise_to = rp.raise_to if rp is not None else None

    t = time.perf_counter()

    # Pasada 1: EV rápido (sin runout) → resultado provisional
    evs = compute_evs(hero_codes, current_board_codes,
                        villain_reach=villain,
                        pot=pot, to_call=to_call, stack=stack, runout=False,
                        bet_sizes=bet_sizes, raise_to=raise_to)
    _stage('ev', t)

    if rp is not None:
        action, value = rules.select_best(evs, rp)
    else:
        action, value = evs.best()
    best_action, best_value, best_evs, best_runout = action, value, evs, False

    # Pasada 2 (opcional): runout para refinar si hay tiempo
    if runout:
        budget_ms = deadline_s * 1000
        elapsed_ms = (time.perf_counter() - t0) * 1000
        remaining = budget_ms - elapsed_ms
        t_pass1_ms = stages.get('ev', 0.0)
        if remaining > max(200.0, 2.5 * t_pass1_ms):
            t = time.perf_counter()
            evs_runout = compute_evs(hero_codes, current_board_codes,
                                        villain_reach=villain,
                                        pot=pot, to_call=to_call,
                                        stack=stack, runout=True,
                                        bet_sizes=bet_sizes,
                                        raise_to=raise_to)
            _stage('ev_runout', t)
            if rp is not None:
                action2, value2 = rules.select_best(evs_runout, rp)
            else:
                action2, value2 = evs_runout.best()
            # Anytime honesto: la pasada 2 refina, se reporta siempre.
            # Si la acción cambia, se registra para telemetría.
            if action2 != best_action:
                stages['runout_action_changed'] = 1.0
            else:
                stages['runout_action_changed'] = 0.0
            stages['runout_delta'] = value2 - best_value
            best_action, best_value, best_evs, best_runout = \
                action2, value2, evs_runout, True
    else:
        stages['ev_runout'] = 0.0

    elapsed_ms = (time.perf_counter() - t0) * 1000
    stages['total'] = elapsed_ms
    stages['budget'] = deadline_s * 1000 - elapsed_ms
    stages['anytime'] = True

    return Recommendation(action=best_action, value=best_value,
                          situation=sit, evs=best_evs,
                          villain_label=villain_label,
                          elapsed_ms=elapsed_ms,
                          stages=stages, runout=best_runout,
                          rule_plan=rp)


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
