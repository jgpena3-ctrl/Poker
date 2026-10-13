"""hierarchy.py — jerarquía de rivales y ajuste multiway en MODO SOMBRA.

Por qué existe
--------------
`RangeState.union()` suma las masas de varios rangos. Eso representa "un
rival elegido al azar entre los presentes", no "todos los rivales en la
mesa". Medido con rangos de un combo: la mezcla da 0.500 donde el valor
real (ganar a los dos) es 0.000.

El módulo NO arregla eso. El motor sigue calculando contra un único rango,
porque hacerlo bien exige la distribución conjunta de las manos de todos
los rivales y no hay muestra para calibrarla. Lo que hace es **instrumentar**
el problema:

  1. Elige un rival principal por jerarquía, sin mezclar rangos.
  2. Clasifica a los demás en agresor / checker / pendiente.
  3. Estima el efecto marginal de los checkers.
  4. Lo registra en un log para comparar contra el resultado real.

Nada de esto altera el EV de producción. Ver `shadow_equity`.

De dónde salen los números
-------------------------
La penalización está anclada a una medición sobre `data/hands_db.jsonl`
(1269 manos con hero identificado, `tools/medir_multiway.py`):

    escenario                                    n    gana el hero
    turn, apuesta, sin agresor ni checker       36      69%
    turn, apuesta, 1 checker + 1 pendiente      36      67%   <- este
    turn, check, agresor enfrente               30      23%

Añadir un checker en el turno baja la probabilidad de ganar ~2 puntos.
Ese es el ancla de `TEX_FACTOR['dry']`.

ADVERTENCIA: 36 manos por celda. No es una constante calibrada, es un
orden de magnitud medido. Sirve para investigar, no para fijar un
parámetro de producción. `pegar_3` es explícito en esto: el modo sombra
no debe presentar una penalización inventada como estimación fiable.
"""
import json
import os
from typing import Dict, List, Optional

from .situation import board_texture

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHADOW_PATH = os.path.join(REPO_DIR, 'data', 'shadow_hierarchy.jsonl')

# Categorías de rival respecto al hero en la calle actual.
AGGRESSOR = 'aggressor'      # modelado, no penalizado
CHECKER = 'checker'          # actuó y pasó (x): penalización pequeña
CALLER = 'caller'            # igualó (c): registrado, sin penalizar
PENDING = 'pending'          # no ha actuado: amenaza activa

# El ajuste NO está validado. `penalty_source()` clasifica el respaldo
# real de cada registro; con los datos actuales NINGUNO coincide con el
# escenario del ancla. Ver OBSERVED_ANCHOR['support_note'].


# ---------------------------------------------------------------------------
# Penalización por checkers
# ---------------------------------------------------------------------------

# Efecto marginal por UN checker, sobre la probabilidad de ganar.
# Ancla: turn+seco medido ≈0.02 (69% -> 67%, n=36 por celda).
TEX_FACTOR = {
    'monotone': 0.06,     # board conectado: outs reales y frecuentes
    'two_tone': 0.04,
    'rainbow': 0.02,      # <-- el único con dato directo
}

# Factor por calle. Flop deja dos cartas por salir (más riesgo); river
# ninguna: la amenaza no son outs nuevos sino manos que ya ganan.
STREET_FACTOR = {
    'flop': 1.5,
    'turn': 1.0,          # <-- calibrado contra la medición
    'river': 0.5,
}

# Un board con pareja es más peligroso que uno liso.
PAIR_FACTOR = 1.5


def texture_key(board_codes) -> str:
    """'monotone' | 'two_tone' | 'rainbow' para `board_codes`."""
    if not board_codes or len(board_codes) < 3:
        return 'rainbow'
    t = board_texture(list(board_codes))
    if t.get('monotone'):
        return 'monotone'
    if t.get('two_tone'):
        return 'two_tone'
    return 'rainbow'


def passive_penalty(board_codes, street: str, n_checker: int) -> float:
    """Penalización por `n_checker` jugadores que checkearon.

    NO ESTÁ CALIBRADA COMO EQUITY (pegar_3 §1). El 0.02 procede de una
    diferencia en tasa de victorias; reconstruida como equity, la
    diferencia cambia de signo. Ver OBSERVED_ANCHOR. Se mantiene porque el
    modo sombra no altera ninguna decisión, pero no debe reutilizarse
    como corrección de equity.

    ABSOLUTA, no relativa, por la misma razón que arriba: el efecto se
    observada, no como factor multiplicativo.

    Lineal y pequeña. NO es `eq ** n`: esa forma es exponencial y con
    rango uniforme quitaría ~50 puntos cuando el orden de magnitud
    observado es ~2.

    Se satura en 0.5 para que un número absurdo de checkers no pueda
    invertir la equity.
    """
    n = max(0, int(n_checker))
    if n == 0:
        return 0.0
    base = TEX_FACTOR[texture_key(board_codes)]
    if board_codes and len(board_codes) >= 3 and board_texture(
            list(board_codes)).get('pairs'):
        base *= PAIR_FACTOR
    sf = STREET_FACTOR.get(street, 1.0)
    return min(0.5, base * sf * n)


# ---------------------------------------------------------------------------
# Ancla observada — NO es una corrección de equity calibrada
# ---------------------------------------------------------------------------
# Advertencia metodológica (pegar_3 §1, P0). Lo medido es FRECUENCIA DE
# VICTORIAS, no equity. Son magnitudes distintas: la equity es la parte
# esperada del bote e incluye empates y repartos; el win rate es
# binario por mano. Y el campo `winner` del DB es la lista de TODOS los
# que cobran: 18% de las manos tienen más de un ganador, así que contar
# "el hero está en la lista" infla el resultado.
#
# Al reconstruir la misma medición como equity (repartos = 1/n), el
# sentido de la diferencia SE INVIERTE:
#
#     escenario                                    n    WIN%   EQUITY
#     turn, apuesto, sin agresor ni checker         36     69%     58.3%
#     turn, apuesto, 1 checker + 1 pendiente        36     67%     61.1%
#     ------------------------------------------------------------------
#     delta al añadir un checker            WIN -2.0 pts   EQUITY +2.8 pts
#
# (Ninguna de las dos es una comparación controlada: son manos
# distintas, no el mismo grupo antes y después. Pero el punto se
# mantiene: no puede affirmed que un checker REDUCE la equity en 0.02.
# Lo único respaldado es una diferencia en|win rate| sobre dos muestras
# de 36 manos que podrían diferir por muestreo.)
#
# `uncertainty` es None porque no se ha calculado. Y el intervalo de
# confianza de un delta de 2 puntos sobre 36 manos es aproximadamente
# ±16 puntos, muy por encima del efecto. Es decir: el dato no
# distingue ni el signo.
OBSERVED_ANCHOR = {
    'quantity': 'observed_win_rate',
    'is_equity': False,
    'street': 'turn',
    'texture': 'rainbow',
    'hero_action': 'bet',
    'n_per_cell': 36,
    'win_rate_without_checker': 0.69,
    'win_rate_with_checker': 0.67,
    'delta_win_rate': -0.02,
    'equity_without_checker': 0.583,
    'equity_with_checker': 0.611,
    'delta_equity': +0.028,
    'signs_agree': False,
    'uncertainty': None,
    'ci_note': ('con n=36 el intervalo del delta de win rate es de '
                'orden ±0.16, muy por encima del efecto medido'),
    'criterion': ('las seis condiciones deben cumplirse a la vez: calle '
                  'turn, textura rainbow, hero que apuesta, sin agresor, '
                  'exactamente 1 checker y 1 pendiente'),
    'source': 'data/hands_db.jsonl (1269 manos con hero identificado)',
    'used_as_equity_penalty': False,
    'verdict': ('observación de win rate con signo distinto en equity; '
                'NO justifica una penalización de equity'),
    # Verificado sobre las 654 observaciones de la DB (tools/auditar_anchor.py):
    'records_matching_anchor': 0,
    'records_previously_labelled_measured': 199,
    'support_note': (
        'label_measured exigía solo calle+textura, así que 199 registros '
        'lo resultaron siendo. Al exigir las SEIS condiciones del ancla '
        '(turn, rainbow, hero que apuesta, sin agresor, 1 checker, '
        '1 pendiente) ninguno coincide: la forma más frecuente es '
        '(hero_apuesta, 0 agresores, 0 checkers, 3-4 pendientes). '
        'El escenario medido no aparece en los datos.'),
}


def penalty_source(board_codes, street: str, hierarchy: Dict = None) -> str:
    """Clasifica el respaldo de la penalización para ESTE registro.

    Antes solo comprobaba calle y textura, así que etiquetaba como
    'measured' a cualquier turn con board rainbow. Eso inflaba la cifra:
    el ancla es un escenario concreto, con seis condiciones a la vez
    (pegar_3 §2, P0).

    Reglas:
      - 'anchor_match'    : se cumplen las seis condiciones del ancla.
      - 'partial_support' : misma calle, pero otra textura.
      - 'none'            : otra calle. Sin ninguna medición.
    """
    if street != 'turn':
        return 'none'
    if texture_key(board_codes) != 'rainbow':
        return 'partial_support'
    if hierarchy is None:
        return 'partial_support'   # no hay contexto para verificar
    if not hierarchy.get('hero_bet'):
        return 'partial_support'
    if hierarchy.get('aggressors'):
        return 'partial_support'
    if len(hierarchy.get('checkers') or ()) != 1:
        return 'partial_support'
    if len(hierarchy.get('pending') or ()) != 1:
        return 'partial_support'
    return 'anchor_match'


# ---------------------------------------------------------------------------
# Clasificación de rivales
# ---------------------------------------------------------------------------

def classify_villains(acts: List[dict], hero_pos: str,
                      pending_positions=()) -> Dict:
    """Elige el rival principal y clasifica al resto.

    `acts`: acciones de la calle en orden, tal como las guarda el recorder.
    TODAS las posiciones son POSICIONES (UTG, CO, BTN...). Los pids
    ('hero', 'p1'...) no mezclan aquí: el llamador traduce.

    Jerarquía (pegar_2 §4 con el matiz de pegar_3 §1 y §P0):

      1. El agresor MÁS RECIENTE de la calle. Da igual que venga antes o
         después de la acción del hero: en una ronda que vuelve a pasar,
         la resubida que se produce después es precisamente la que el
         hero enfrenta. Por eso no se parte la lista en la posición del
         hero, sino que se recorre entera.
      2. Si nadie ha hecho agresión, el último que checkeó, por posición.
      3. Los pendientes solo son los que NO han actuado en la calle. Estar
         activo no significa tener una decisión pendiente.

    Hay CUATRO categorías, no tres: además de agresor / checker /
    pendiente está `callers`. Un 'c' (igualar) NO es un 'x' (pasar):
    quien igualó aporta fichas voluntariamente y su rango no está capado
    como el de un check. No entra en la penalización porque no hay
    ninguna medición para él, pero se registra para que no desaparezca
    del análisis.

    `pending_positions`: posiciones candidatas a pendiente. Se filtra
    contra quienes ya actuaron en `acts`. Son POSICIONES, no pids; el
    llamador traduce antes de llamar.
    """
    hero_pos = hero_pos or ''
    hero_acts = [i for i, a in enumerate(acts) if a.get('pos') == hero_pos]
    hero_last = hero_acts[-1] if hero_acts else None

    agresores, checkers, callers = [], [], []
    acted = set()
    for a in acts:
        pos, acc = a.get('pos'), a.get('action')
        if not pos or pos == hero_pos:
            continue
        acted.add(pos)
        if acc in ('b', 'r'):
            agresores.append(pos)
        elif acc == 'x':
            checkers.append(pos)
        elif acc == 'c':
            callers.append(pos)

    main, reason = None, 'sin rivales identificados'
    if agresores:
        main = agresores[-1]
        pos_agresion = max(i for i, a in enumerate(acts)
                           if a.get('pos') == main
                           and a.get('action') in ('b', 'r'))
        if hero_last is None:
            reason = 'agresor más reciente de la calle'
        elif pos_agresion > hero_last:
            reason = 'agresor posterior al hero (ronda que vuelve)'
        else:
            reason = 'agresor más reciente que enfrenta al hero'
    elif checkers:
        main = checkers[-1]
        reason = 'sin agresión: último que checkeó, por posición'

    # Quien checkeó y LUEGO apuesto es agresor, no un pasivo: checkear en
    # una ronda no compromete la mano si después hay resubida. La última
    # acción agresiva manda sobre el check anterior.
    checkers = [c for c in checkers if c not in agresores]
    callers = [c for c in callers if c not in agresores]

    # Pendientes = candidatos que además NO han actuado en esta calle.
    pending = []
    for pos in (pending_positions or ()):
        if pos and pos != hero_pos and pos not in acted \
                and pos not in pending:
            pending.append(pos)

    return {
        'main': main,
        'main_reason': reason,
        # El ancla observada exige que el hero APUESTE. Es una condición
        # más del experimento original, no una suposición.
        'hero_bet': bool(hero_acts
                         and acts[hero_last].get('action') in ('b', 'r')),
        'aggressors': agresores,
        'checkers': [c for c in checkers if c != main],
        # Un 'c' NO es un 'x'. Quien igualó ha aportado fichas
        # voluntariamente: su rango no está capado como el de un check y
        # no entra en la penalización (no hay dato). Se registra aparte
        # para que no desaparezca del análisis.
        'callers': [c for c in callers if c != main],
        'pending': pending,
        'hero_pos': hero_pos,
    }


# ---------------------------------------------------------------------------
# Cálculo sombra
# ---------------------------------------------------------------------------

def shadow_equity(equity_production: float, board_codes, street: str,
                  hierarchy: Dict, equity_source: str = '') -> Dict:
    """Equity ajustada por los checkers. NO se usa para decidir.

    Estructura ABSOLUTA, que es la que reproduce el dato medido:

        eq_shadow = eq_produccion - penalización

    LAS TRES EQUITY SON DISTINTAS (pegar_3 §2, P0):

      equity_production : la que el motor usó para decidir. Es la única
                         disponible aquí. `equity_source` dice contra qué
                         rival se calculó.
      equity_main       : contra el rango del rival principal de la
                         jerarquía. NO SE CALCULA. Es None, y
                         `equity_main_available` es False. Antes este
                         campo se llamaba igual que el de producción y
                         sugería una equivalencia que no existe.
      equity_shadow     : la estimación experimental.

    Que `equity_source` coincida o no con `hierarchy['main']` NO convierte
    la equity de producción en la de referencia: solo indica que se usó
    el mismo rango. Even cuando coinciden, son cálculos distintos en
    propósito: uno estima contra un rival, el otro contra una mesa.

    Los pendientes no entran en la penalización: pueden resubir, y
    penalizarlos como si fueran draws sobrevaloraría la apuesta.
    """
    n_chk = len(hierarchy.get('checkers') or ())
    n_pend = len(hierarchy.get('pending') or ())
    pen = passive_penalty(board_codes, street, n_chk)
    eq_prod = float(equity_production)
    adjusted = max(0.0, eq_prod - pen)
    src = equity_source or 'desconocido'
    main = hierarchy.get('main')
    coincide = bool(main) and src == main
    psource = penalty_source(board_codes, street, hierarchy)
    return {
        # la que el motor usó de verdad
        'equity_production': eq_prod,
        'equity_source': src,
        'equity_source_is_hierarchy_main': coincide,
        # la que NO tenemos: contra el rango del principal de la jerarquía
        'equity_main': None,
        'equity_main_available': False,
        'equity_main_note': (
            'no se calcula: el motor solo produce una equity de producción. '
            'Para medir el efecto de los rivales secundarios hay que '
            'calcularla contra hierarchy["main"] explícitamente.'),
        'equity_shadow': round(adjusted, 5),
        'penalty': round(pen, 5),
        'penalty_basis': 'absolute_unvalidated',
        'penalty_basis_note': (
            'el 0.02 procede de una diferencia en TASA DE VICTORIAS, no '
            'de equity. Reconstruido como equity el signo se invierte. '
            'No usar como corrección de equity (pegar_3 §1).'),
        'penalty_source': psource,
        'penalty_anchor': dict(OBSERVED_ANCHOR)
        if psource == 'anchor_match' else None,
        'n_checker': n_chk,
        'n_pending': n_pend,
        'n_caller': len(hierarchy.get('callers') or ()),
        'delta': round(adjusted - eq_prod, 5),
        # unmistakable: esto NO es una equity multiway
        'experimental': True,
    }


def shadow_record(hand_id: str, street: str, board_codes, hero_codes,
                  hierarchy: Dict, shadow: Dict, pot: float, to_call: float,
                  stack: float, action_production: str,
                  action_shadow: Optional[str] = None) -> Dict:
    """Registro estructurado de UNA evaluación.

    Se guarda ANTES de conocer el showdown (pegar_3 §3): enlazar el
    resultado después, sin sobrescribir la predicción, evita que el
    resultado contamine la estimación que supuestamente lo predice.
    """
    return {
        'hand_id': hand_id,
        'street': street,
        'hero': ''.join(hero_codes),
        'board': ''.join(board_codes),
        'pot': pot,
        'to_call': to_call,
        'stack': stack,
        'villain_main': hierarchy.get('main'),
        'main_reason': hierarchy.get('main_reason'),
        # las tres equity, explícitamente separadas (pegar_3 §2, P0)
        'villain_used_for_equity': shadow.get('equity_source'),
        'equity_source_is_main': shadow.get('equity_source_is_hierarchy_main'),
        'equity_main_available': shadow.get('equity_main_available'),
        'equity_main_note': shadow.get('equity_main_note'),
        'aggressors': hierarchy.get('aggressors'),
        'checkers': hierarchy.get('checkers'),
        'callers': hierarchy.get('callers'),
        'pending': hierarchy.get('pending'),
        'texture': texture_key(board_codes),
        'equity_production': shadow.get('equity_production'),
        'equity_main': shadow.get('equity_main'),
        'equity_shadow': shadow.get('equity_shadow'),
        'penalty': shadow.get('penalty'),
        'penalty_basis': shadow.get('penalty_basis'),
        'penalty_basis_note': shadow.get('penalty_basis_note'),
        'penalty_source': shadow.get('penalty_source'),
        'penalty_anchor': shadow.get('penalty_anchor'),
        'n_checker': shadow.get('n_checker'),
        'n_pending': shadow.get('n_pending'),
        'n_caller': shadow.get('n_caller'),
        'delta': shadow.get('delta'),
        'action_production': action_production,
        'action_shadow': action_shadow,
        'experimental': True,
    }


class ShadowLog:
    """Escritor del log de sombra. Silencioso si no hay ruta válida.

    Un fallo de escritura NUNCA debe romper la recomendación: el log es
    un instrumento de medición, no parte del motor.
    """

    def __init__(self, path: str = SHADOW_PATH, enabled: bool = True):
        self.path = path
        self.enabled = bool(enabled)
        self._n = 0

    def append(self, record: Dict) -> bool:
        if not self.enabled or not record:
            return False
        try:
            with open(self.path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
            self._n += 1
            return True
        except (OSError, TypeError, ValueError):
            # El log es accesorio: si falla, se pierde una fila, no el motor.
            return False

    @property
    def count(self) -> int:
        return self._n