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
            # (suited aces, suited connectors, broadway) para evitar
            # que categorías anchas como weak_broadway_suited eclipsen
            # sub-clases más específicas (high_suited_connector, suited_ace).
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
            # suited_gapper
            _nonpair_priority.append(('suited_gapper', 'suited_gapper'))
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
            _nonpair_priority.append(('offsuit_gapper', 'offsuit_gapper'))
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
            # Fallback genérico
            if suited:
                _HAND_CLASS_NAME[idx] = 'suited_connector'
                _HAND_SUB_CLASS[idx] = 'other'
            else:
                _HAND_CLASS_NAME[idx] = 'offsuit_connector'
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
    # SUITED_GAPPER: suited with gap >= 2 (J9s, T8s, 97s, etc.)
    'suited_gapper': {
        'suited_gapper': lambda hi, lo: hi >= 4 and 2 <= (hi - lo) <= 3 and lo < 8,
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
    # OFFSUIT_GAPPER: offsuit with gap >= 2 (J9o, T8o, 97o, etc.)
    'offsuit_gapper': {
        'offsuit_gapper': lambda hi, lo: hi >= 9 and 2 <= (hi - lo) <= 3 and lo < 8,
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
    """reach normalizado ponderado por clase base."""
    w = reach.copy()
    w *= _BASE_WEIGHT
    total = w.sum()
    if total <= 0:
        return np.zeros(N_COMBOS, dtype=np.float32)
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

    __slots__ = ('reach', 'blockers', 'position', 'confidence')

    def __init__(self, reach=None, blockers=0, position='', confidence=0.5):
        self.reach = np.zeros(N_COMBOS, dtype=np.float32) if reach is None \
            else np.asarray(reach, dtype=np.float32).copy()
        self.blockers = int(blockers)
        self.position = position
        self.confidence = float(confidence)

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
        """
        p = np.asarray(prob_action, dtype=np.float32)
        if p.shape != (N_COMBOS,):
            raise ValueError(f'P(A|H) debe tener forma ({N_COMBOS},), tiene {p.shape}')
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