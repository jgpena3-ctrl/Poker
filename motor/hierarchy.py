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
    """Penalización por `n_checker` jugadores que checkearon.

    Lineal y pequeña a propósito. NO es `eq ** n`: esa forma es
    exponencial y con rango uniforme quitaría ~50 puntos cuando el dato
    medido dice ~2.

    Devuelve 0.0 si no hay checkers. El resultado se satura en 0.5 para
    que un número absurdo de checkers no pueda invertir la equity.
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
# Clasificación de rivales
# ---------------------------------------------------------------------------

def classify_villains(acts: List[dict], hero_pos: str,
                      pending_positions=()) -> Dict:
    """Elige el rival principal y clasifica al resto.

    `acts` son las acciones de la calle en orden, tal como las guarda el
    recorder: [{'pos': 'UTG', 'action': 'b', ...}, ...].

    Jerarquía (pegar_2 §4, con el matiz de pegar_3 §1):

      1. El agresor más reciente que está ENFRENTANDO al hero. Si el hero
         ya actuar (check), ese agresor es el rival principal.
      2. Si no hay ninguna acción hasta el hero, no hay agresor: se usa
         posición relativa, primero IP y luego el OOP más cercano al IP.
      3. Los pendientes NO compiten: pueden resubir, así que se marcan
         como amenaza activa en vez de penalizarlos como si hubieran
         checkeado.

    Devuelve dict con `main`, `main_reason`, `aggressors`, `checkers`,
    `pending`, `other_positions`.
    """
    antes, despues = [], []
    corte = None
    for i, a in enumerate(acts):
        if a.get('pos') == hero_pos:
            corte = i
            break
    if corte is None:
        antes = list(acts)
        despues = []
    else:
        antes = list(acts[:corte])
        despues = list(acts[corte + 1:])

    agresores, checkers = [], []
    for a in antes:
        pos, acc = a.get('pos'), a.get('action')
        if not pos:
            continue
        if acc in ('b', 'r'):
            agresores.append(pos)
        elif acc == 'x':
            checkers.append(pos)

    pending = []
    for a in despues:
        pos = a.get('pos')
        if pos and pos != hero_pos:
            pending.append(pos)
    # los pendientes declarados por el llamador y que aún no aparecen
    for pos in (pending_positions or ()):
        if pos and pos != hero_pos and pos not in pending:
            pending.append(pos)

    main, reason = None, 'sin rivales identificados'
    if agresores:
        main = agresores[-1]
        reason = ('agresor más reciente que enfrenta al hero'
                  if corte is not None
                  else 'agresor más reciente de la calle')
    elif checkers:
        main = checkers[-1]
        reason = 'sin agresión: el último que	checkeó, por posición'

    return {
        'main': main,
        'main_reason': reason,
        'aggressors': agresores,
        'checkers': [c for c in checkers if c != main],
        'pending': pending,
    }


# ---------------------------------------------------------------------------
# Cálculo sombra
# ---------------------------------------------------------------------------

def shadow_equity(equity_main: float, board_codes, street: str,
                  hierarchy: Dict) -> Dict:
    """Equity ajustada por los checkers. NO se usa para decidir.

    Estructura (pegar_2 §2.1): lineal y pequeña, no `eq ** n`.

        eq_shadow = eq_vs_principal * (1 - penalización)

    El agresor principal ya está dentro de `equity_main` (su rango se
    modeló, no se corrigió). Los pendientes no entran: siguen siendo
    amenaza activa y registrarlos es más honesto que inventarles una
    penalización.
    """
    n_chk = len(hierarchy.get('checkers') or ())
    n_pend = len(hierarchy.get('pending') or ())
    pen = passive_penalty(board_codes, street, n_chk)
    adjusted = float(equity_main) * (1.0 - pen)
    return {
        'equity_main': float(equity_main),
        'penalty': round(pen, 5),
        'n_checker': n_chk,
        'n_pending': n_pend,
        'equity_shadow': round(adjusted, 5),
        'delta': round(adjusted - float(equity_main), 5),
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
        'aggressors': hierarchy.get('aggressors'),
        'checkers': hierarchy.get('checkers'),
        'pending': hierarchy.get('pending'),
        'texture': texture_key(board_codes),
        'equity_production': shadow.get('equity_main'),
        'equity_shadow': shadow.get('equity_shadow'),
        'penalty': shadow.get('penalty'),
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