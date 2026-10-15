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
from .hierarchy import shadow_equity, shadow_record
from .panel import format_insight
from .preflop import opening_range_or_fallback
from .ranges import RangeError, RangeState, SIN_POSITION
from .situation import Situation, situation
from . import rules
from .rules import MOTIVO_MULTIWAY, MULTIWAY_SOPORTADO, POLITICA_MULTIWAY
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
    # Jerarquía de rivales en modo sombra. `shadow` es lo que HABRÍA dado
    # la equity ajustada por checkers; no interviene en `action` ni en
    # `value`, que son siempre los de producción. Ver hierarchy.py.
    shadow: Optional[Dict] = None
    hierarchy: Optional[Dict] = None

    # --- F7.2.b: alcance de la recomendación -------------------------------
    # `multiway_soportado=False` NO significa "el motor no recomienda": el
    # motor sigue recomendando exactamente lo mismo que antes. Significa que la
    # equity que hay detrás es heads-up contra UN rival, y que en un spot con
    # más de uno esa equity no es la equity del spot. Ver CONTRATO_F72A.md §6.
    #
    # `multiway` es el HECHO (el spot tiene más de un rival) y
    # `multiway_soportado` la CONSECUENCIA (sabemos o no decidir en él). Son
    # campos distintos a propósito: el día que haya equity conjunta, el
    # segundo caducará solo y el primero seguirá siendo un hecho.
    multiway: bool = False
    multiway_soportado: bool = True
    multiway_motivo: Optional[str] = None
    politica_multiway: str = POLITICA_MULTIWAY

    @property
    def text(self) -> str:
        return format_insight(self.situation, self.evs, self.villain_label,
                              runout=self.runout)


def _build_villain_range(hero_codes, board_codes, villain_pos='UTG',
                          villain_cards=(), range_model=None,
                          villain_player='',
                          villain_spot='no_raise', villain_action='open',
                          extra_blockers=()):
    """RangeState del rival: OR preflop + blockers, o rango perfilado si se
    pasa un ProfileRangeModel + jugador (player_ranges.py).

    `villain_spot` / `villain_action` describen lo que el rival HA HECHO
    (denominador y categoría en la nomenclatura de learn.py). Antes se
    pasaban fijos como ('no_raise', 'open'), así que un rival que pagaba
    o hacía 3-bet recibía un rango de apertura: numéricamente válido,
    pero estrategicamente incorrecto.

    Las dos operaciones sobre cartas son DISTINTAS y antes se confundían
    (pegar_2 §2.B, pegar_3 §5):

      - `extra_blockers` : cartas de OTROS jugadores conocidos que no
        pueden tener los villanos. En online son las del SEGUNDO HERO
        (y las del propio hero, que ya se añaden aparte). Estas sí se
        bloquean.

      - `villain_cards`  : las 2 cartas reales de UN rival concreto
        cuando se conocen. NO debe usarse en online: allí no hay
        conocimiento de la mano rival antes del showdown, y restrict_to_combo
        fabricaría una certeza que no existe. Su único uso legítimo es el
        estudio posterior de la base de datos, donde el showdown sí
        registró las cartas. Se conserva por eso, fuera del path online.

    Bloquear `villain_cards` eliminaba justo la mano que sabemos que tiene.
    """
    source = 'profile'
    if range_model is not None and villain_player:
        reach = range_model.prob_vec_player(
            villain_player, villain_spot, villain_action, villain_pos)
    else:
        reach, source = opening_range_or_fallback(villain_pos)
    rs = RangeState(reach=np.asarray(reach, dtype=np.float32))
    rs.set_known_cards(list(hero_codes) + list(board_codes))
    if extra_blockers:
        rs.set_known_cards(list(extra_blockers))
    if villain_cards:
        rs.restrict_to_combo(list(villain_cards))
    # Valida sobre el rango que se consumirá de verdad, es decir tras
    # blockers. Un rango con masa cruta pero toda bloqueada es tan inválido
    # como uno con ceros (p. ej. si villain_cards chocan con el board).
    rs.validate()
    if rs.is_empty:
        raise RangeError(
            'rango rival vacío tras blockers '
            f'(villain_cards={list(villain_cards) if villain_cards else None}, '
            f'extra_blockers={list(extra_blockers) if extra_blockers else None})')
    rs.source = source
    return rs


def _build_multiway_range(hero_codes, board_codes,
                           villain_ranges: Dict[str, RangeState]):
    """Combina múltiples RangeState en uno unión con blockers.

    Para multiway: el rango rival combinado es la unión de todos
    los rangos individuales (cada villain juega independientemente).
    Se aplican blockers (hero + board) a cada rango antes de combinar.
    `union()` suma masas y NO normaliza: la normalización ocurre en
    `weights`, en el punto donde hace falta una distribución.
    el modelo multiway sigue siendo aproximado.
    """
    if not villain_ranges:
        return RangeState()
    combined = None
    known = list(hero_codes) + list(board_codes)
    for rs in villain_ranges.values():
        rs.validate(allow_empty=True)
        r = rs.copy()
        r.set_known_cards(known)
        r.nullify_blocked()                      # blockers aplicados ANTES de unir
        # Se valida cada rango por separado: si uno se queda sin masa legal,
        # se dice CUÁL, no se descubre al final como un total vacío.
        if r.is_empty:
            raise RangeError(
                'rango de un villano vacío tras blockers en multiway')
        combined = r if combined is None else combined.union(r)
    if combined is None or combined.is_empty:
        raise RangeError('rango multiway vacío tras blockers')
    return combined


def build_villain_range(hero_codes, board_codes, villain_pos='UTG',
                          villain_cards=(), range_model=None,
                          villain_player='',
                          villain_spot='no_raise', villain_action='open',
                          extra_blockers=(),
                          villain_ranges: Optional[Dict[str, RangeState]] = None):
    """Público: construye RangeState para HU o multiway."""
    if villain_ranges is not None and len(villain_ranges) > 0:
        return _build_multiway_range(hero_codes, board_codes, villain_ranges)
    return _build_villain_range(hero_codes, board_codes, villain_pos,
                                   villain_cards, range_model, villain_player,
                                   villain_spot, villain_action,
                                   extra_blockers)


# `SIN_POSITION` vive en `ranges.py` (es un concepto de `RangeState`) y se
# re-exporta aqui para quien ya importa de este modulo.


def _equity_vs_rival(range_builder, hero_codes, board_codes):
    """Equity del hero contra un rango rival construido aparte.

    Para la `equity_main` del modo sombra: el rango del rival principal de
    la jerarquía, que puede NO ser el que usa producción.

    `range_builder` es un RangeState ya bloqueado con las cartas del hero
    y del board. Si no es utilizable, se prefiere la ausencia explícita a
    un valor calculado contra el rival equivocado (pegar_3 §2).

    Devuelve (equity, fuente, nota_error). equity es None si no se pudo.

    CONTRATO DE `nota_error` — documentado porque `equity_main_note` lo
    parsea separando código y detalle por el PRIMER ':':

      None                                 todo correcto
      'main_range_unavailable'              sin rango            (SIN ':')
      'empty_range_after_blockers'          rango vacío          (SIN ':')
      'equity_calculation_failed: <texto>'  excepción al calcular

    El separador NO es obligatorio: un código sin `: ` es legítimo y el
    detalle es opcional. Por eso el parseo es `partition(':')`, que parte una
    sola vez, y no `split(':', 1)`.

    CONTRATO DE `fuente`: es `rs.position`, la posición del rival. Si el
    rango no la lleva, se devuelve `SIN_POSITION` en vez de inventar un
    nombre. `_rango_main` la fija siempre; el centinela solo aparece si otro
    llamador construye un rango sin posición.
    """
    from .situation import equity_vs_range

    rs = range_builder
    if rs is None:
        return None, None, 'main_range_unavailable'
    if getattr(rs, 'is_empty', True):
        return None, None, 'empty_range_after_blockers'
    try:
        # equity_vs_range devuelve (equity, wins, ties, losses)
        eq = equity_vs_range(hero_codes, board_codes, villain_reach=rs)[0]
        return float(eq), getattr(rs, 'position', '') or SIN_POSITION, None
    except RangeError as e:
        return None, None, f'equity_calculation_failed: {e}'
    except Exception as e:      # no debe tumbar la recomendación
        return None, None, f'equity_calculation_failed: {e}'


def recommend(hero_codes, board_codes, *, pot: float, to_call: float = 0.0,
               stack: float = 0.0, street: str = 'flop', position: str = '',
               villain_pos: str = 'UTG', villain_cards: tuple = (),
               extra_blockers: tuple = (),
               villain_reach: Union[None, RangeState, np.ndarray] = None,
               villain_ranges: Optional[Dict[str, RangeState]] = None,
               range_model=None, villain_player: str = '',
               villain_spot: str = 'no_raise',
               villain_action: str = 'open',
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
               range_advantage_str: str = None,
               hierarchy: Optional[Dict] = None,
               main_range_builder=None,
               shadow_log=None,
               hand_id: str = '') -> Recommendation:
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
        # La unión de reaches NO es una equity multiway (mezcla un rival
        # elegido al azar). Se deja constancia en la etiqueta (pegar_2 §5).
        n_rivales = len(villain_ranges)
        etiqueta = (f'multiway aprox. ({n_rivales} rivales, '
                    f'no es equity multiway)')
        # Los pendientes también son relevantes: son amenaza activa, y
        # callarlos daría a entender que solo hay checkers (pegar_2 §2.6).
        if hierarchy:
            n_chk = len(hierarchy.get('checkers_secondary') or ())
            n_pend = len(hierarchy.get('pending') or ())
            if n_chk or n_pend:
                etiqueta += f' +{n_chk} checker(s), {n_pend} pendiente(s)'
        villain_label = etiqueta
    elif villain_reach is None:
        villain = _build_villain_range(hero_codes, board_codes, villain_pos,
                                        villain_cards, range_model,
                                        villain_player,
                                        villain_spot, villain_action,
                                        extra_blockers)
        if range_model is not None and villain_player:
            perfil = range_model.perfil.get(villain_player, '?')
            villain_label = f'{perfil} wJ {villain_player}' \
                if range_model.player_omega(villain_player, villain_spot) != 1.0 \
                else f'{perfil} {villain_player}'
        elif villain.source == 'uniform':
            # Sin tabla poblacional para esa posición (p. ej. no hay OR_BB).
            # Se marca en la etiqueta para que no se lea como un rango estimado.
            villain_label = f'OR {villain_pos} (uniforme, sin tabla)'
        else:
            villain_label = f'OR {villain_pos}'
    else:
        rs = (villain_reach if isinstance(villain_reach, RangeState)
              else RangeState(reach=villain_reach))
        rs.set_known_cards(list(hero_codes) + list(board_codes))
        # Aunque el llamador pase su propio rango, las cartas de otros
        # heroes conocidos tampoco pueden estar en él: es la misma regla
        # que en la rama anterior (pegar_2 §2.3).
        if extra_blockers:
            rs.set_known_cards(list(extra_blockers))
        rs.validate()
        if rs.is_empty:
            raise RangeError('rango rival vacío tras blockers '
                             f'(extra_blockers={list(extra_blockers)})')
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

    # --- F7.2.b: el alcance de lo que se va a recomendar -------------------
    #
    # Se calcula AQUÍ y no en el return, para que sea lo mismo que consume el
    # panel (que lo lee de `rp`). La rama de `rp is None` no es un caso
    # defensivo: `rules.plan` lanza en `street='preflop'` y eso lo transforma
    # en `rp=None` en el `except` de arriba, que es un camino de producción.
    # Si aquí se escribiera `multiway = rp.multiway`, ese camino reventaría.
    # La sombra de `n_players` es la MISMA que usa `rules.plan`.
    multiway = rp.multiway if rp is not None else n_players > 2
    multiway_soportado = (not multiway) or MULTIWAY_SOPORTADO
    multiway_motivo = (rp.multiway_motivo if rp is not None
                       else (None if multiway_soportado else MOTIVO_MULTIWAY))

    # --- Anytime: EV en dos pasadas (rápido → refinado con runout) ---
    best_action, best_value, best_evs = None, -999.0, None
    best_runout = False

    # Guardar board actual para situation() (no se modifica)
    current_board_codes = board_codes

    # compute_evs() calcula TODAS las acciones (bet_sizes completo).
    # El filtro lógico va en rules.select_best() vía rp.candidates.
    # NO usar bet_sizes=() para "desactivar" acciones: usar candidates.
    # bet_sizes y raise_to SÍ vienen de RulePlan cuando existen;
    # si rp.bet_sizes es vacío, se usan valores por defecto.
    if rp is not None and rp.bet_sizes:
        bet_sizes = rp.bet_sizes
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
        # Sin plan NO se decide con `evs.best()`. Ese metodo es de PINTADO:
        # devuelve nan en vez de lanzar, porque sus llamadores son el panel
        # y la GUI, y pintar un hueco no es lo mismo que decidir sobre el.
        # Decidir aqui con el es el bug que C4 arregla en `select_best` y
        # que se colaba por la puerta de `rp=None`. Ver CONTRATO_C4.md §4.
        action, value = rules.select_best(evs, None)
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
                action2, value2 = rules.select_best(evs_runout, None)
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

    # --- Jerarquía de rivales: MODO SOMBRA ---
    # NO altera `best_action` ni `best_value`. Solo estima qué cambiaría
    # si los checkers se penalizaran, y lo registra para poder compararlo
    # contra resultados reales. Activarlo sin muestra sería calibrar a
    # ciegas, así que por ahora es solo un instrumento de medición.
    shadow_info = None
    if hierarchy:
        try:
            # `sit.equity` se calculó contra el rival que construyó el
            # llamador, que puede NO ser `hierarchy['main']`. Se deja
            # constancia con un IDENTIFICADOR estable, no con la etiqueta
            # de usuario: si cambia el formato del texto, el
            # identificador no debe cambiar con él (pegar_2 §2.3).
            if villain_ranges:
                eq_source = f'multiway:{len(villain_ranges)}'
            else:
                eq_source = str(villain_pos or 'desconocido')
            shadow_info = shadow_equity(sit.equity, current_board_codes,
                                       street, hierarchy,
                                       equity_source=eq_source)
            # equity_main: equity contra el rango del rival PRINCIPAL de la
            # jerarquía, calculada aparte. Sin ella no se puede medir el
            # efecto de los rivales secundarios. Es opcional y NUNCA toca
            # la decisión (pegar_2 §2.2, §3.3).
            if main_range_builder is not None and hierarchy.get('main'):
                try:
                    eq_main, main_src, main_err = _equity_vs_rival(
                        main_range_builder, hero_codes, current_board_codes)
                    shadow_info['equity_main'] = eq_main
                    shadow_info['equity_main_available'] = eq_main is not None
                    shadow_info['equity_main_source'] = main_src
                    shadow_info['equity_main_note'] = main_err
                except Exception as e:
                    shadow_info['equity_main'] = None
                    shadow_info['equity_main_available'] = False
                    shadow_info['equity_main_source'] = None
                    shadow_info['equity_main_note'] = f'error: {e}'
            # F7.2.b: el alcance, en el registro. Se escribe SOBRE
            # `shadow_info`, igual que las claves de `equity_main`: ni `evs`
            # ni `rp` se tocan, así que la acción no puede cambiar.
            #
            # Va en el log porque el flag es la forma de CONTAR cuántos puntos
            # de decisión entran al motor siendo multiway. Sin esto, la
            # medición de CONTRATO_F72A §5.5 (45,9 % de las decisiones) no
            # tiene con qué contrastar en producción.
            shadow_info['multiway'] = multiway
            shadow_info['multiway_soportado'] = multiway_soportado
            shadow_info['multiway_motivo'] = multiway_motivo
            shadow_info['politica_multiway'] = POLITICA_MULTIWAY
            shadow_info['n_players'] = n_players
            # El registro es opcional; el cálculo no. Con `hierarchy` el
            # llamador ya pidió la comparación, aunque no la persista.
            if shadow_log is not None:
                shadow_log.append(shadow_record(
                    hand_id=hand_id or '', street=street,
                    board_codes=current_board_codes, hero_codes=hero_codes,
                    hierarchy=hierarchy, shadow=shadow_info, pot=pot,
                    to_call=to_call, stack=stack,
                    action_production=best_action))
        except Exception as e:      # nunca romper la recomendación
            import sys
            print(f'[hierarchy.sombra] error: {e}', file=sys.stderr)

    return Recommendation(action=best_action, value=best_value,
                          situation=sit, evs=best_evs,
                          villain_label=villain_label,
                          elapsed_ms=elapsed_ms,
                          stages=stages, runout=best_runout,
                          rule_plan=rp, shadow=shadow_info,
                          hierarchy=hierarchy,
                          multiway=multiway,
                          multiway_soportado=multiway_soportado,
                          multiway_motivo=multiway_motivo,
                          politica_multiway=POLITICA_MULTIWAY)


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
