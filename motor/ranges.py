"""ranges.py — 1326 combinaciones preflop, RangeState (reach/weight) y update bayesiano.

Convención matemática (ARQUITECTURA §5.2):

    weight_h = reach_h / Σ_j reach_j      (tras blockers y normalización)

- `reach` (float32, 1326) es la única masa que se actualiza: cada update multiplica
  por P(A|H, context) y pone a 0 los combos que chocan con blockers.
- `weight` es una vista normalizada derivada de `reach`, nunca se edita sola.

`mask` queda reservado para binarios: known_cards_mask (blockers), hand_mask,
legal_mask.
"""
import numpy as np
from typing import Dict

from .cards import RANK_ORDER, card_id, card_label

N_CARDS = 52
N_COMBOS = 1326


def _build_all_hands():
    """Genera las 1326 combinaciones (c0 < c1) con sus máscaras y etiquetas."""
    c0s, c1s, labels, masks = [], [], [], []
    for i in range(N_CARDS):
        for j in range(i + 1, N_CARDS):
            c0s.append(i)
            c1s.append(j)
            labels.append(card_label(i) + card_label(j))
            masks.append((1 << i) | (1 << j))
    return (
        np.array(c0s, dtype=np.uint8),
        np.array(c1s, dtype=np.uint8),
        np.array(labels),
        np.array(masks, dtype=np.int64),
    )


COMBO0, COMBO1, HAND_LABELS, HAND_MASKS = _build_all_hands()

# Filtro legal: legal_mask[i] = (HAND_MASKS[i] & known) == 0  (a aplicar por el RangeState)
IS_PAIR = COMBO0 // 4 == COMBO1 // 4         # par de manos
IS_SUITED = COMBO0 % 4 == COMBO1 % 4        # del mismo palo

# Cache: mano índice -> combos que la contienen (usado por blockers)
_cards_to_combos = {c: [] for c in range(52)}
for _i, (a, b) in enumerate(zip(COMBO0, COMBO1)):
    _cards_to_combos[int(a)].append(_i)
    _cards_to_combos[int(b)].append(_i)


def combos_with_card(card_idx):
    """Índices de los combos (0..1325) que contienen la carta `card_idx`."""
    return _cards_to_combos[card_idx]


# ---------------------------------------------------------------------------
# Jerarquía de hand classes (pegar.txt §1.1)
#
# La jerarquía produce pesos para las 1326 combinaciones, no solo una
# etiqueta: cada combo tiene una clase, una sub-clase y un peso base
# que determina su prior en el rango.
#
#   hand_class → base_weight[combo] → P(A|combo, context)
# ---------------------------------------------------------------------------

_RANKS = list(RANK_ORDER)                        # ['2','3',...,'A']
_RANK_IDX = {r: i for i, r in enumerate(_RANKS)} # rank -> índice 0..12


def _rank_of_idx(card_idx: int) -> int:
    """Índice de rango (0=2, ..., 12=A) de un card 0..51."""
    return card_idx // 4


def _cards_to_rank_pair(c0: int, c1: int) -> tuple:
    """(rank_idx_high, rank_idx_low) para un combo (c0, c1) con c0 < c1."""
    r0, r1 = _rank_of_idx(c0), _rank_of_idx(c1)
    return (max(r0, r1), min(r0, r1))


# Pesos base por sub-clase: determinan la prior P(H) de cada combo
# dentro de su clase. AA=1.0 (máximo), 72o=0.2 (mínimo).
BASE_WEIGHT_MAP = {
    # PAIR
    'premium_pair': 1.0,     # AA, KK, QQ
    'strong_pair': 0.9,      # JJ, TT, 99
    'medium_pair': 0.7,      # 88, 77, 66, 55
    'small_pair': 0.4,       # 44 down to 22
    # SUITED_ACE
    'premium_suited_ace': 1.0,  # AKs, AQs
    'strong_suited_ace': 0.90,  # AJs, ATs
    'weak_suited_ace': 0.75,    # A9s-A2s
    # SUITED_BROADWAY
    'premium_suited_broadway': 0.95,  # KQs
    'strong_suited_broadway': 0.85,   # KJs, KTs, QJs
    'medium_suited_broadway': 0.70,   # QTs, JTs
    # SUITED_CONNECTOR
    'high_suited_connector': 0.65,    # T9s, 98s
    'medium_suited_connector': 0.5,   # 87s, 76s
    'low_suited_connector': 0.35,     # 65s, 54s
    # SUITED_GAPPER
    'suited_gapper': 0.50,            # J9s, T8s, 97s, ...
    'medium_suited_gapper_1': 0.45,   # J9s, T8s, 97s, 65s
    'low_suited_gapper_1': 0.35,      # 53s, 43s, 32s
    'medium_suited_gapper_2': 0.40,   # T7s, 96s, 85s
    'low_suited_gapper_2': 0.30,      # 52s, 42s, 31s
    'medium_suited_gapper_3': 0.35,   # 95s, 84s, 73s
    'low_suited_gapper_3': 0.25,      # 51s, 41s
    # OFFSUIT_ACE
    'premium_offsuit_ace': 0.85,      # AKo, AQo
    'strong_offsuit_ace': 0.60,       # AJo, ATo
    'medium_offsuit_ace': 0.40,       # A9o, A8o
    'weak_offsuit_ace': 0.25,         # A7o-A2o
    # OFFSUIT_BROADWAY
    'premium_offsuit_broadway': 0.75, # KQo
    'strong_offsuit_broadway': 0.60,  # KJo, KTo
    'medium_offsuit_broadway': 0.50,  # QJo, QTo, JTo
    # OFFSUIT_CONNECTOR
    'high_offsuit_connector': 0.45,   # T9o, 98o
    'medium_offsuit_connector': 0.35, # 87o, 76o
    'low_offsuit_connector': 0.25,    # 65o, 54o, 43o, 32o
    # OFFSUIT_GAPPER
    'offsuit_gapper': 0.30,           # 64o, 75o, 86o, 97o, T8o, J9o
    'medium_offsuit_gapper_1': 0.25,  # J9o, T8o, 97s
    'low_offsuit_gapper_1': 0.18,     # 53o, 43o, 32o
    'medium_offsuit_gapper_2': 0.20,  # T7o, 96o, 85o
    'low_offsuit_gapper_2': 0.15,     # 52o, 42o, 31o
    'medium_offsuit_gapper_3': 0.18,  # 95o, 84o, 73o
    'low_offsuit_gapper_3': 0.12,     # 51o, 41o
    'other': 0.25,
}

# ---------------------------------------------------------------------------
# Arrays pre-computados: clase, sub-clase y peso base por cada combo
# ---------------------------------------------------------------------------

# U32: 'premium_offsuit_broadway' (25 chars) no debe truncarse
_HAND_CLASS_NAME = np.empty(N_COMBOS, dtype='U32')
_HAND_SUB_CLASS = np.empty(N_COMBOS, dtype='U32')
_BASE_WEIGHT = np.ones(N_COMBOS, dtype=np.float32)
# Lookup (hi, lo, suited) → combo idx para que
# _preflop_category() use la MISMA clasificación que _compute_hand_classes()
_HILO_IDX: Dict[tuple, int] = {}


def _compute_hand_classes():
    """Llena _HAND_CLASS_NAME, _HAND_SUB_CLASS y _BASE_WEIGHT para los 1326 combos."""
    for idx in range(N_COMBOS):
        c0, c1 = int(COMBO0[idx]), int(COMBO1[idx])
        hi, lo = _cards_to_rank_pair(c0, c1)
        suited = (c0 % 4 == c1 % 4)
        _HILO_IDX[(hi, lo, suited)] = idx

        assigned = False
        if hi == lo:
            # Pair
            for sub, pred in _PAIR_SUBS.items():
                if pred(hi, lo):
                    _HAND_CLASS_NAME[idx] = 'pair'
                    _HAND_SUB_CLASS[idx] = sub
                    _BASE_WEIGHT[idx] = BASE_WEIGHT_MAP[sub]
                    assigned = True
                    break
        if not assigned:
            # No pair: buscar la mejor sub-clase no-pair por prioridad.
            # El orden importa: las categorías más específicas primero
            # (suited aces → suited broadway → suited connector → gapper
            # → offsuit ace → offsuit broadway → offsuit connector → gapper)
            # para evitar que categorías anchas como offsuit_gapper
            # eclipsen sub-clases más específicas.
            _nonpair_priority = [
                ('suited_ace', 'premium_suited_ace'),
                ('suited_ace', 'strong_suited_ace'),
                ('suited_ace', 'weak_suited_ace'),
            ]
            # suited_broadway: KQs, KJs, KTs, QJs, QTs, JTs
            for bc in ('premium_suited_broadway', 'strong_suited_broadway',
                        'medium_suited_broadway'):
                _nonpair_priority.append(('suited_broadway', bc))
            # suited_connector
            for sc in ('high_suited_connector', 'medium_suited_connector',
                        'low_suited_connector'):
                _nonpair_priority.append(('suited_connector', sc))
            # suited_gapper: iterar todas las sub-clases
            for sc in _NONPAIR_SUBS['suited_gapper']:
                _nonpair_priority.append(('suited_gapper', sc))
            # offsuit: offsuit_ace, offsuit_broadway, offsuit_connector,
            # offsuit_gapper
            for sc in ('premium_offsuit_ace', 'strong_offsuit_ace',
                        'medium_offsuit_ace', 'weak_offsuit_ace'):
                _nonpair_priority.append(('offsuit_ace', sc))
            for sc in ('premium_offsuit_broadway', 'strong_offsuit_broadway',
                        'medium_offsuit_broadway'):
                _nonpair_priority.append(('offsuit_broadway', sc))
            for sc in ('high_offsuit_connector', 'medium_offsuit_connector',
                        'low_offsuit_connector'):
                _nonpair_priority.append(('offsuit_connector', sc))
            for sc in _NONPAIR_SUBS['offsuit_gapper']:
                _nonpair_priority.append(('offsuit_gapper', sc))
            # other como fallback
            _nonpair_priority.append(('other', 'other'))

            for class_name, sub in _nonpair_priority:
                subs = _NONPAIR_SUBS.get(class_name, {})
                pred = subs.get(sub)
                if pred is None:
                    continue
                if not pred(hi, lo):
                    continue
                if suited and 'suited' not in sub:
                    continue
                if not suited and 'suited' in sub:
                    continue
                _HAND_CLASS_NAME[idx] = class_name
                _HAND_SUB_CLASS[idx] = sub
                _BASE_WEIGHT[idx] = BASE_WEIGHT_MAP[sub]
                assigned = True
                break

        if not assigned:
            # Fallback genérico: manos de muy bajo rango
            # que no encajan en ninguna categoría específica.
            _HAND_CLASS_NAME[idx] = 'other'
            _HAND_SUB_CLASS[idx] = 'other'
            _BASE_WEIGHT[idx] = BASE_WEIGHT_MAP['other']


# Definiciones internas para el cómputo
_PAIR_SUBS = {
    'premium_pair':   lambda hi, lo: hi >= 10,          # QQ, KK, AA
    'strong_pair':    lambda hi, lo: hi >= 7,           # 99, TT, JJ
    'medium_pair':    lambda hi, lo: hi >= 3,           # 55, 66, 77, 88
    'small_pair':     lambda hi, lo: hi < 3,            # 22, 33, 44
}
_NONPAIR_SUBS = {
    # SUITED_ACE: A-K suit combos
    'suited_ace': {
        'premium_suited_ace': lambda hi, lo: hi == 12 and lo >= 10,  # AKs, AQs
        'strong_suited_ace':  lambda hi, lo: hi == 12 and 8 <= lo <= 9,  # AJs, ATs
        'weak_suited_ace':    lambda hi, lo: hi == 12 and lo <= 7,  # A9s-A2s
    },
    # SUITED_BROADWAY: suited broadway (A,K,Q,J,T suits)
    'suited_broadway': {
        'premium_suited_broadway': lambda hi, lo: hi == 11 and lo == 10,  # KQs
        'strong_suited_broadway':  lambda hi, lo: hi >= 10 and lo >= 8 and hi < 12,  # KJs, KTs, QJs, QTs
        'medium_suited_broadway':  lambda hi, lo: hi == 9 and lo >= 8,   # JTs
    },
    # SUITED_CONNECTOR: suited consecutive non-broadway
    'suited_connector': {
        'high_suited_connector':    lambda hi, lo: hi in (7, 8) and lo == hi - 1,  # 98s, T9s
        'medium_suited_connector':  lambda hi, lo: hi in (6, 5) and lo == hi - 1,
        'low_suited_connector':     lambda hi, lo: hi in (4, 3, 2, 1) and lo == hi - 1,
    },
    # SUITED_GAPPER: suited with gap = 1, 2, 3 (J9s, T7s, 95s, etc.)
    'suited_gapper': {
        'medium_suited_gapper_1': lambda hi, lo: hi in (9, 8, 7, 6) and lo == hi - 2,
        'low_suited_gapper_1': lambda hi, lo: hi in (5, 4, 3, 2) and lo == hi - 2,
        'medium_suited_gapper_2': lambda hi, lo: hi in (9, 8, 7, 6) and lo == hi - 3,
        'low_suited_gapper_2': lambda hi, lo: hi in (5, 4, 3) and lo == hi - 3,
        'medium_suited_gapper_3': lambda hi, lo: hi in (9, 8, 7) and lo == hi - 4,
        'low_suited_gapper_3': lambda hi, lo: hi in (5, 4) and lo == hi - 4,
    },
    # OFFSUIT_ACE: offsuit A-x combos
    'offsuit_ace': {
        'premium_offsuit_ace': lambda hi, lo: hi == 12 and lo >= 10,  # AKo, AQo
        'strong_offsuit_ace':  lambda hi, lo: hi == 12 and 8 <= lo <= 9,  # AJo, ATo
        'medium_offsuit_ace':  lambda hi, lo: hi == 12 and 6 <= lo <= 7,  # A9o, A8o
        'weak_offsuit_ace':    lambda hi, lo: hi == 12 and lo <= 5,  # A7o-A2o
    },
    # OFFSUIT_BROADWAY: offsuit broadway (J-T, K-Q, etc.)
    'offsuit_broadway': {
        'premium_offsuit_broadway': lambda hi, lo: hi == 11 and lo == 10,  # KQo
        'strong_offsuit_broadway':  lambda hi, lo: hi == 11 and lo >= 8,   # KJo, KTo
        'medium_offsuit_broadway':  lambda hi, lo: hi == 10 and lo >= 8,   # QJo, QTo
    },
    # OFFSUIT_CONNECTOR: offsuit consecutive non-broadway
    'offsuit_connector': {
        'high_offsuit_connector':    lambda hi, lo: hi in (8, 7) and lo == hi - 1,  # T9o, 98o
        'medium_offsuit_connector':  lambda hi, lo: hi in (6, 5) and lo == hi - 1,  # 87o, 76o
        'low_offsuit_connector':     lambda hi, lo: hi in (4, 3, 2, 1) and lo == hi - 1,  # 32o, 43o, 54o, 65o
    },
    # OFFSUIT_GAPPER: offsuit with gap = 1, 2, 3 (J9o, T7o, 95o, etc.)
    'offsuit_gapper': {
        'medium_offsuit_gapper_1': lambda hi, lo: hi in (9, 8, 7, 6) and lo == hi - 2,
        'low_offsuit_gapper_1': lambda hi, lo: hi in (5, 4, 3, 2) and lo == hi - 2,
        'medium_offsuit_gapper_2': lambda hi, lo: hi in (9, 8, 7, 6) and lo == hi - 3,
        'low_offsuit_gapper_2': lambda hi, lo: hi in (5, 4, 3) and lo == hi - 3,
        'medium_offsuit_gapper_3': lambda hi, lo: hi in (9, 8, 7) and lo == hi - 4,
        'low_offsuit_gapper_3': lambda hi, lo: hi in (5, 4) and lo == hi - 4,
    },
}

_compute_hand_classes()


def hand_class(idx: int) -> tuple:
    """Clase, sub-clase y peso base de un combo por su índice (0..1325).

    Returns:
        (hand_class_name, sub_class, base_weight)
        Ej: ('pair', 'premium_pair', 1.0) para AA
    """
    return (_HAND_CLASS_NAME[idx], _HAND_SUB_CLASS[idx],
            float(_BASE_WEIGHT[idx]))


def hand_class_name(idx: int) -> str:
    """Nombre de clase del combo."""
    return _HAND_CLASS_NAME[idx]


def hand_sub_class(idx: int) -> str:
    """Nombre de sub-clase del combo."""
    return _HAND_SUB_CLASS[idx]


def base_weight(idx: int) -> float:
    """Peso base P(H) del combo dentro de su clase."""
    return float(_BASE_WEIGHT[idx])


# Cache para uso por etiqueta
_HAND_LABEL_TO_IDX = {lab: i for i, lab in enumerate(HAND_LABELS)}


# Metadatos por sub-clase: (clase, peso base)
_SUBCLASS_META = {}
for _cls, _subs in _NONPAIR_SUBS.items():
    for _sub in _subs:
        _SUBCLASS_META[_sub] = (_cls, BASE_WEIGHT_MAP[_sub])
for _sub in _PAIR_SUBS:
    _SUBCLASS_META[_sub] = ('pair', BASE_WEIGHT_MAP[_sub])
_SUBCLASS_META['other'] = ('other', BASE_WEIGHT_MAP['other'])


def hand_class_of_label(label: str) -> tuple:
    """Clase/sub-clase/peso de una mano por etiqueta ('AhKh' o 'AKs')."""
    idx = _HAND_LABEL_TO_IDX.get(label)
    if idx is not None:
        return hand_class(idx)
    try:
        sub = _preflop_category(label)
    except Exception:
        return ('other', 'other', 0.25)
    cls, w = _SUBCLASS_META.get(sub, ('other', 0.25))
    return (cls, sub, w)


def class_weights_vector() -> np.ndarray:
    """Vector (1326,) con los pesos base por clase para cada combo."""
    return _BASE_WEIGHT.copy()


def combos_by_sub_class(sub_class: str) -> np.ndarray:
    """Índices de combos que pertenecen a una sub-clase."""
    return np.where(_HAND_SUB_CLASS == sub_class)[0]


def combos_by_class(hand_class_name: str) -> np.ndarray:
    """Índices de combos que pertenecen a una clase."""
    return np.where(_HAND_CLASS_NAME == hand_class_name)[0]


def class_weights_for_reach(reach: np.ndarray) -> np.ndarray:
    """reach normalizado ponderado por la clase base.

    DEPRECADO: no se invoca desde ningún punto de producción. Se conserva
    como utilería y mantiene el contrato viejo (devuelve ceros si el rango
    es vacío) en lugar de lanzar, para no romper callers externos; por eso
    NO debe usarse en el motor: devolver ceros reproduce el P0 de "rango
    vacío silencioso". Lo que debe usarse es `villain_weights()`.

    Si algún día se conecta a producción, migrar antes a RangeError.
    """
    w = reach.copy()
    w *= _BASE_WEIGHT
    total = w.sum()
    if total <= 0:
        return np.zeros(N_COMBOS, dtype=np.float32)
    return w / total


# ---------------------------------------------------------------------------
# Contrato de validación de pesos (Fase A — robustez numérica)
# ---------------------------------------------------------------------------

# Índice (carta_a, carta_b) -> combo idx, para restrict_to_combo().
_PAIR_IDX: Dict[tuple, int] = {
    (int(COMBO0[i]), int(COMBO1[i])): i for i in range(N_COMBOS)
}


class RangeError(ValueError):
    """Rango rival inválido o degenerado.

    Se distingue de un ValueError genérico para que el llamador pueda
    tratar "no pude evaluar una distribución" de forma distinta a un
    fallo de programación. Un rango vacío NUNCA debe convertirse
    silenciosamente en una equity de 0.0.
    """


def validate_reach(reach, *, allow_empty: bool = False):
    """Valida un vector de pesos y devuelve (array float64, suma).

    Comprueba forma (N_COMBOS,), finitud, no negatividad y suma positiva.
    Lanza RangeError si algo falla, salvo que `allow_empty` y la única
    falla sea la suma nula.

    Usar en cualquier punto donde un vector de reach entre al motor: así
    "no hay distribución" nunca se confunde con "el rival no tiene mano".
    """
    arr = np.asarray(reach, dtype=np.float64)
    if arr.shape != (N_COMBOS,):
        raise RangeError(
            f'reach debe tener forma ({N_COMBOS},), tiene {arr.shape}')
    if not np.all(np.isfinite(arr)):
        raise RangeError('reach contiene NaN o infinito')
    if np.any(arr < 0):
        raise RangeError('reach contiene valores negativos')
    total = float(arr.sum())
    if total <= 0 and not allow_empty:
        raise RangeError('reach vacío (suma cero)')
    return arr, total


def villain_weights(villain_reach, villain_ids):
    """Pesos normalizados sobre `villain_ids`. Fuente única de verdad.

    - None → uniforme (1/N)
    - RangeState → reach_blocked[ids] (respeta sus blockers)
    - vector (N_COMBOS,) → valores en bruto, normalizados sobre `ids`

    La usan tanto `situation.equity_vs_range` (panel) como
    `decision.compute_evs` (motor de EV). Antes cada una tenía su propia
    copia y podían divergir: una devolvía ceros en rango vacío y la otra
    lanzaba. Aquí el rango vacío es siempre un RangeError.
    """
    ids = np.asarray(villain_ids, dtype=np.intp)
    n = int(ids.size)
    if n == 0:
        raise RangeError('villain_ids vacío')
    if villain_reach is None:
        return np.full(n, 1.0 / n, dtype=np.float64)
    if isinstance(villain_reach, RangeState):
        # Se valida el reach COMPLETO antes de indexar, no solo los ids
        # pedidos: si el RangeState llega corrupto en una zona que esta
        # llamada no lee, debe seguir siendo un error visible (pegar_3,
        # paso 1: contrato uniforme objeto vs vector).
        villain_reach.validate(allow_empty=True)
        w = villain_reach.reach_blocked[ids].astype(np.float64)
    else:
        arr, _total = validate_reach(villain_reach, allow_empty=True)
        w = arr[ids]
    if not np.all(np.isfinite(w)):
        raise RangeError('pesos del rango con NaN o infinito')
    if np.any(w < 0):
        raise RangeError('pesos del rango negativos')
    total = float(w.sum())
    if total <= 0:
        raise RangeError('rango rival vacío tras blockers')
    return w / total


class RangeState:
    """Estado de rango bayesiano sobre las 1326 combinaciones.

    Parámetros
    ----------
    reach : vector float32 (1326,) o None (rango vacío)
    blockers : bitmask 52 bits o 0
    position : posición del jugador (solo informativa)
    confidence : 0..1 — confianza en el modelo del rival
    """

    __slots__ = ('reach', 'blockers', 'position', 'confidence', 'source')

    def __init__(self, reach=None, blockers=0, position='', confidence=0.5,
                 source=''):
        self.reach = np.zeros(N_COMBOS, dtype=np.float32) if reach is None \
            else np.asarray(reach, dtype=np.float32).copy()
        self.blockers = int(blockers)
        self.position = position
        self.confidence = float(confidence)
        # Procedencia del reach: 'table', 'uniform', 'profile', '' (sin marcar).
        # Permite auditar si un rango viene de una estimación real o de un
        # fallback técnico.
        self.source = source

    # ---------------------------------------------------------------
    # derivadas
    # ---------------------------------------------------------------

    @property
    def known_mask(self):
        """Máscara binaria de cartas conocidas (hero + board)."""
        return self.blockers

    @property
    def legal_mask(self):
        """bool (1326,): combos que no chocan con cartas conocidas."""
        return (HAND_MASKS & self.blockers) == 0

    @property
    def reach_blocked(self):
        """reach con 0 en los combos que chocan con blockers."""
        r = self.reach.copy()
        r[~self.legal_mask] = 0.0
        return r

    @property
    def weights(self):
        """float32 (1326,): weight_h = reach_h / Σ reach (tras blockers)."""
        r = self.reach_blocked
        total = r.sum()
        if total <= 0:
            return np.zeros(N_COMBOS, dtype=np.float32)
        return r / total

    def set_known_cards(self, cards):
        """Aplica blockers (códigos 'As', 'Kd', ...) marcando combos inválidos."""
        for c in cards:
            self.blockers |= 1 << card_id(c)
        return self

    def nullify_blocked(self):
        """Reach a 0 en combos que chocan con blockers (inlines)."""
        self.reach[~self.legal_mask] = 0.0
        return self

    # ---------------------------------------------------------------
    # construcción y combinación (Fase B.3)
    # ---------------------------------------------------------------

    def copy(self):
        """Copia independiente del estado (reach, blockers y metadatos)."""
        return RangeState(reach=self.reach.copy(), blockers=self.blockers,
                          position=self.position, confidence=self.confidence,
                          source=self.source)

    def union(self, other):
        """Unión de dos reaches: suma de pesos, SIN normalizar.

        Cada rango representa a un rival distinto que actúa de forma
        independiente, así que las masas se suman. La suma resultante
        no es 1 y no debe serlo: la normalización ocurre en `weights`,
        en el punto donde se necesita una distribución.
        """
        if not isinstance(other, RangeState):
            raise TypeError('union exige otro RangeState')
        return RangeState(reach=self.reach + other.reach,
                          blockers=self.blockers | other.blockers,
                          position=self.position,
                          confidence=min(self.confidence, other.confidence))

    def restrict_to_combo(self, cards):
        """Restringe el rango al combo exacto formado por 2 cartas.

        Operación opuesta a `set_known_cards`: aquí las cartas SÍ son
        del jugador, así que no se bloquean, se conservan. Es lo que
        corresponde cuando se conoce la mano real del rival.

        Si el prior daba peso 0 a ese combo, se le asigna un peso
        positivo mínimo: la información del llamador ("el rival tiene
        esta mano") es más fuerte que una estimación poblacional, y sin
        esto restringir un combo ausente produciría un rango vacío.
        """
        codes = list(cards)
        if len(codes) != 2:
            raise ValueError('restrict_to_combo exige exactamente 2 cartas')
        ids = sorted(card_id(c) for c in codes)
        idx = _PAIR_IDX.get((ids[0], ids[1]))
        if idx is None:
            raise ValueError(f'combo no encontrado para {list(cards)}')
        mask = np.zeros(N_COMBOS, dtype=bool)
        mask[idx] = True
        self.reach[~mask] = 0.0
        if self.reach[idx] <= 0:
            self.reach[idx] = 1.0
        return self

    def validate(self, *, allow_empty: bool = False) -> float:
        """Valida el reach y devuelve su suma. Lanza RangeError si falla."""
        _, total = validate_reach(self.reach, allow_empty=allow_empty)
        return total

    @property
    def is_empty(self) -> bool:
        """True si no queda ninguna combinación con peso positivo."""
        return bool(not np.any(self.reach_blocked > 0))

    def top_hands(self, k=10):
        """Top-k combos por weight con (etiqueta, weight)."""
        w = self.weights
        idx = np.argsort(w)[::-1][:k]
        return [(HAND_LABELS[i], float(w[i])) for i in idx if w[i] > 0]

    # ---------------------------------------------------------------
    # update bayesiano
    # ---------------------------------------------------------------

    def update(self, prob_action):
        """P(H|A) ∝ P(A|H)·P(H): reach = reach * P(A|H) por combo.

        prob_action: vector float (1326,) con P(A|H) por combinación.
        Debe ser finito, no negativo y estar en [0, 1]: es una
        probabilidad, no un peso. Un NaN o un valor > 1 aquí
        contaminaría todo el rango de forma silenciosa.
        """
        p = np.asarray(prob_action, dtype=np.float32)
        if p.shape != (N_COMBOS,):
            raise RangeError(
                f'P(A|H) debe tener forma ({N_COMBOS},), tiene {p.shape}')
        if not np.all(np.isfinite(p)):
            raise RangeError('P(A|H) contiene NaN o infinito')
        if np.any(p < 0):
            raise RangeError('P(A|H) contiene valores negativos')
        if np.any(p > 1.0 + 1e-6):
            raise RangeError(
                f'P(A|H) fuera de [0,1]: max={float(p.max()):.4f}')
        self.reach = self.reach * p
        return self

    def update_with_action(self, action, context, action_prob_fn):
        """Versión contextual: p_h = action_prob_fn(hand_label, action, context)."""
        probs = np.array(
            [float(action_prob_fn(label, action, context)) for label in HAND_LABELS],
            dtype=np.float32,
        )
        return self.update(probs)

    def norm_to(self):
        """Renormaliza reach para que Σ reach (sobre combos legales) = 1."""
        self.reach = self.weights
        return self

    def __repr__(self):
        return (f'<RangeState reach_sum={self.reach.sum():.3f} '
                f'legal={int(self.legal_mask.sum())}/1326 '
                f'conf={self.confidence:.2f}>')


def uniform_range(cards=()):
    """Rango uniforme sobre los combos legales (sin blockers acumulados)."""
    rs = RangeState()
    if cards:
        rs.set_known_cards(cards)
    rs.reach[rs.legal_mask] = 1.0
    return rs


# ---------------------------------------------------------------------------
# Heurística base P(A|H, context) — editable sin datos (fase 2)
# ---------------------------------------------------------------------------

# Tablas de probabilidad por sub-clase (no solo por clase plana).
# Cada sub-clase tiene su propia distribución de acciones.
_ACTION_PROBS = {
    'premium_pair':       {'r': 0.95, 'b': 1.00, 'c': 0.95, 'f': 0.05},
    'strong_pair':        {'r': 0.80, 'b': 0.95, 'c': 0.85, 'f': 0.15},
    'medium_pair':        {'r': 0.40, 'b': 0.70, 'c': 0.75, 'f': 0.35},
    'small_pair':         {'r': 0.15, 'b': 0.40, 'c': 0.50, 'f': 0.60},
    # SUITED_ACE
    'premium_suited_ace': {'r': 0.90, 'b': 1.00, 'c': 0.95, 'f': 0.05},
    'strong_suited_ace':  {'r': 0.50, 'b': 0.85, 'c': 0.85, 'f': 0.15},
    'weak_suited_ace':    {'r': 0.12, 'b': 0.45, 'c': 0.55, 'f': 0.40},
    # SUITED_BROADWAY
    'premium_suited_broadway': {'r': 0.85, 'b': 0.95, 'c': 0.90, 'f': 0.10},
    'strong_suited_broadway': {'r': 0.25, 'b': 0.60, 'c': 0.70, 'f': 0.30},
    'medium_suited_broadway': {'r': 0.20, 'b': 0.55, 'c': 0.70, 'f': 0.35},
    # SUITED_CONNECTOR
    'high_suited_connector':  {'r': 0.10, 'b': 0.45, 'c': 0.60, 'f': 0.50},
    'medium_suited_connector':{'r': 0.05, 'b': 0.35, 'c': 0.55, 'f': 0.60},
     'low_suited_connector':   {'r': 0.03, 'b': 0.25, 'c': 0.45, 'f': 0.70},
     # SUITED_GAPPER
     'suited_gapper':      {'r': 0.20, 'b': 0.50, 'c': 0.65, 'f': 0.35},
     'medium_suited_gapper_1': {'r': 0.18, 'b': 0.45, 'c': 0.60, 'f': 0.38},
     'low_suited_gapper_1':  {'r': 0.08, 'b': 0.30, 'c': 0.45, 'f': 0.55},
     'medium_suited_gapper_2': {'r': 0.12, 'b': 0.38, 'c': 0.55, 'f': 0.45},
     'low_suited_gapper_2':  {'r': 0.05, 'b': 0.22, 'c': 0.35, 'f': 0.65},
     'medium_suited_gapper_3': {'r': 0.10, 'b': 0.35, 'c': 0.50, 'f': 0.50},
     'low_suited_gapper_3':  {'r': 0.04, 'b': 0.18, 'c': 0.30, 'f': 0.62},
    # OFFSUIT_ACE
    'premium_offsuit_ace': {'r': 0.85, 'b': 0.95, 'c': 0.90, 'f': 0.10},
    'strong_offsuit_ace':  {'r': 0.45, 'b': 0.70, 'c': 0.80, 'f': 0.20},
    'medium_offsuit_ace':  {'r': 0.20, 'b': 0.50, 'c': 0.65, 'f': 0.35},
    'weak_offsuit_ace':    {'r': 0.08, 'b': 0.30, 'c': 0.45, 'f': 0.60},
    # OFFSUIT_BROADWAY
    'premium_offsuit_broadway': {'r': 0.45, 'b': 0.80, 'c': 0.85, 'f': 0.15},
    'strong_offsuit_broadway': {'r': 0.20, 'b': 0.55, 'c': 0.70, 'f': 0.35},
    'medium_offsuit_broadway': {'r': 0.15, 'b': 0.45, 'c': 0.60, 'f': 0.50},
    # OFFSUIT_CONNECTOR
    'high_offsuit_connector':  {'r': 0.05, 'b': 0.30, 'c': 0.45, 'f': 0.65},
    'medium_offsuit_connector':{'r': 0.03, 'b': 0.25, 'c': 0.45, 'f': 0.70},
    'low_offsuit_connector':   {'r': 0.02, 'b': 0.20, 'c': 0.35, 'f': 0.75},
    # OFFSUIT_GAPPER
     'offsuit_gapper': {'r': 0.08, 'b': 0.30, 'c': 0.40, 'f': 0.65},
     'medium_offsuit_gapper_1': {'r': 0.07, 'b': 0.28, 'c': 0.38, 'f': 0.68},
     'low_offsuit_gapper_1': {'r': 0.04, 'b': 0.18, 'c': 0.25, 'f': 0.78},
     'medium_offsuit_gapper_2': {'r': 0.05, 'b': 0.22, 'c': 0.30, 'f': 0.72},
     'low_offsuit_gapper_2': {'r': 0.03, 'b': 0.15, 'c': 0.20, 'f': 0.80},
     'medium_offsuit_gapper_3': {'r': 0.04, 'b': 0.20, 'c': 0.28, 'f': 0.75},
     'low_offsuit_gapper_3': {'r': 0.02, 'b': 0.12, 'c': 0.18, 'f': 0.82},
     'other':              {'r': 0.05, 'b': 0.20, 'c': 0.35, 'f': 0.75},
 }


def _preflop_category_from_idx(idx: int) -> str:
    """Sub-clase del combo para P(A|H). Usa la jerarquía completa."""
    return _HAND_SUB_CLASS[idx]


def _preflop_category(hand_code) -> str:
    """Sub-clase jerárquica de un combo (pegar.txt §1.1).

    Devuelve la sub-clase (p.ej. 'premium_pair', 'strong_broadway')
    Acepta 'AhKh', 'AK' o 'AKs'.
    """
    code = hand_code
    if isinstance(code, (list, tuple)):
        code = ''.join(code)
    if len(code) == 4:          # 'AhKh'
        r0, r1 = code[0], code[2]
        i0, i1 = _RANKS.index(r0), _RANKS.index(r1)
        hi, lo = max(i0, i1), min(i0, i1)
        suited = (code[1] == code[3])
    elif len(code) == 3:        # 'AKs' / '72o'
        r0, r1 = code[0], code[1]
        i0, i1 = _RANKS.index(r0), _RANKS.index(r1)
        hi, lo = max(i0, i1), min(i0, i1)
        suited = (code[2] == 's')
    elif len(code) == 2:        # 'AK' / '72' -> sin info de palo
        r0, r1 = code[0], code[1]
        i0, i1 = _RANKS.index(r0), _RANKS.index(r1)
        hi, lo = max(i0, i1), min(i0, i1)
        suited = False
    else:
        raise ValueError(f'código de mano inválido: {hand_code!r}')

    if hi == lo:
        for sub, pred in _PAIR_SUBS.items():
            if pred(hi, lo):
                return sub
    # Usar la clasificación precomputada por _compute_hand_classes()
    # para garantizar coherencia con _HAND_SUB_CLASS.
    key = (hi, lo, suited)
    if key in _HILO_IDX:
        return _preflop_category_from_idx(_HILO_IDX[key])
    return 'other'


def default_action_prob(hand_code, action, context):
    """P(A|H, context) de arranque con jerarquía completa (pegar.txt §1.1).

    context: dict con 'street', 'position', 'sizing', 'pot', 'players',
             'history'. En preflop se usa la sub-clase jerárquica;
             en postflop aún neutro (0.5) hasta conectar el evaluador.

    El peso base del combo se aplica implícitamente a través de
    RangeState.reach: cada combo llega con su base_weight como reach inicial.
    """
    if isinstance(hand_code, (list, tuple)):
        hand_code = ''.join(hand_code)
    street = context.get('street', 'preflop')
    if street == 'preflop':
        sub = _preflop_category(hand_code)
        table = _ACTION_PROBS.get(sub, _ACTION_PROBS['other'])
        return table.get(action, 0.5)
    return 0.5