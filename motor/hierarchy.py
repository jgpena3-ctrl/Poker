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
AGGRESSOR = 'aggressor'      #[ELECCIONADO] modelado, no penalizado
CHECKER = 'checker'          # actuó y pasó: penalización pequeña
PENDING = 'pending'          # no ha actuado: amenaza activa


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
    """Penalización ABSOLUTA por `n_checker` jugadores que checkearon.

    ABSOLUTA, no relativa. El dato es 69% -> 67%: dos puntos
    porcentuales. Aplicarlo como factor (eq * (1-0.02) = 0.6762) daría
    1.38 puntos, no 2. Es la diferencia entre reproducir la medición y
    reproducir una regla parecida (pegar_3 §1, P1).

    Lineal y pequeña a propósito. NO es `eq ** n`: esa forma es
    exponencial y con rango uniforme quitaría ~50 puntos cuando el dato
    medido dice ~2.

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
# Ancla empírica de la penalización
# ---------------------------------------------------------------------------
# Qué significa exactamente 'measured'. No es "una observación": es UNA
# celda concreta de una medición sobre la DB real (1269 manos con hero
# identificado, tools/medir_multiway.py):
#
#     escenario                                      n    gana el hero
#     turn, apuesta, sin agresor ni checker          36      69%
#     turn, apuesta, 1 checker + 1 pendiente         36      67%
#     turn, check, agresor enfrente                  30      23%
#
# De ahí sale 0.02 de reducción ABSOLUTA. Es el ÚNICO escenario con
# respaldo. Todo lo demás es hipótesis de trabajo.
#
# `uncertainty` es None a propósito: no se ha calculado el intervalo de
# confianza. Decirlo evita que el número se lea más firme de lo que es.
PENALTY_ANCHOR = {
    'street': 'turn',
    'texture': 'rainbow',
    'n_per_cell': 36,
    'eq_without_checker': 0.69,
    'eq_with_checker': 0.67,
    'delta_absolute': 0.02,
    'uncertainty': None,
    'criterion': ('exactamente una celda con n>=30 en la medición de '
                  'tools/medir_multiway.py; el resto es extrapolación'),
    'source': 'data/hands_db.jsonl (1269 manos con hero identificado)',
}


def penalty_source(board_codes, street: str) -> str:
    """'measured' si la combinación tiene dato directo; si no, extrapolada.

    Solo turn + board liso está anclado a una medición. Ver
    PENALTY_ANCHOR para el tamaño de muestra y el criterio exacto.
    """
    if street == 'turn' and texture_key(board_codes) == 'rainbow':
        return 'measured'
    return 'extrapolated'


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
        'penalty_basis': 'absolute',
        'penalty_source': penalty_source(board_codes, street),
        'penalty_anchor': dict(PENALTY_ANCHOR)
        if penalty_source(board_codes, street) == 'measured' else None,
        'n_checker': n_chk,
        'n_pending': n_pend,
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
        'penalty_source': shadow.get('penalty_source'),
        'penalty_anchor': shadow.get('penalty_anchor'),
        'n_checker': shadow.get('n_checker'),
        'n_pending': shadow.get('n_pending'),
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