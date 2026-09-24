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
    """Índice de rango (0=A, ..., 12=2) de un card 0..51."""
    return card_idx // 4


def _cards_to_rank_pair(c0: int, c1: int) -> tuple:
    """(rank_idx_high, rank_idx_low) para un combo (c0, c1) con c0 < c1."""
    r0, r1 = _rank_of_idx(c0), _rank_of_idx(c1)
    return (max(r0, r1), min(r0, r1))


# Pesos base por sub-clase: determinan la prior P(H) de cada combo
# dentro de su clase. AA=1.0 (máximo), 72o=0.2 (mínimo).
BASE_WEIGHT_MAP = {
    'premium_pair': 1.0,     # AA, KK, QQ, AKs
    'strong_pair': 0.9,      # JJ, TT, 99
    'medium_pair': 0.7,      # 88, 77, 66, 55
    'small_pair': 0.4,       # 44 down to 22
    'premium_broadway_suited': 1.0,  # AKs, AQs
    'premium_broadway': 0.95,        # AKo, AQo
    'strong_broadway_suited': 0.90,  # AJs, KQs, KJs
    'strong_broadway': 0.80,         # AJT, KQo
    'medium_broadway_suited': 0.65,  # ATs, QJs, JTs
    'medium_broadway': 0.55,         # ATo, QJo
    'weak_broadway_suited': 0.45,    # 98s, T9s, 87s
    'weak_broadway': 0.35,           # 98o, T9o
    'high_suited_connector': 0.65,   # 98s, 87s
    'medium_suited_connector': 0.5,  # 76s, 65s
    'low_suited_connector': 0.35,    # 54s, 43s
    'suited_ace': 0.90,              # A9s+, A8s+ (no broadway match)
    'offsuit_broadway': 0.55,        # AKo, AQo, KQo
    'offsuit_connector': 0.45,       # 98o, 87o, ...
    'suited_one_gapper': 0.5,        # A9s, K9s, Q9s, ...
    'offsuit_one_gapper': 0.3,
    'other': 0.25,
}

# ---------------------------------------------------------------------------
# Arrays pre-computados: clase, sub-clase y peso base por cada combo
# ---------------------------------------------------------------------------

_HAND_CLASS_NAME = np.empty(N_COMBOS, dtype='U24')
_HAND_SUB_CLASS = np.empty(N_COMBOS, dtype='U24')
_BASE_WEIGHT = np.ones(N_COMBOS, dtype=np.float32)


def _compute_hand_classes():
    """Llena _HAND_CLASS_NAME, _HAND_SUB_CLASS y _BASE_WEIGHT para los 1326 combos."""
    for idx in range(N_COMBOS):
        c0, c1 = int(COMBO0[idx]), int(COMBO1[idx])
        hi, lo = _cards_to_rank_pair(c0, c1)
        suited = (c0 % 4 == c1 % 4)

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
            # Se recorre _NONPAIR_SUBS en orden; el primer predicado que
            # coincida (con compatibilidad suited/offsuit) gana.
            for class_name, subs in _NONPAIR_SUBS.items():
                for sub, pred in subs.items():
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
                if assigned:
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
    'premium_pair':   lambda hi, lo: hi >= 11,          # AA, KK
    'strong_pair':    lambda hi, lo: hi >= 8,            # QQ, JJ, TT
    'medium_pair':    lambda hi, lo: hi >= 4,            # 99, 88, 77, 66, 55
    'small_pair':     lambda hi, lo: hi < 4,             # 44 down to 22
}
_NONPAIR_SUBS = {
    'broadway': {
        'premium_broadway_suited':  lambda hi, lo: hi >= 11 and lo >= 10,
        'premium_broadway':         lambda hi, lo: hi >= 11 and lo >= 10,
        'strong_broadway_suited':    lambda hi, lo: hi >= 11 and lo >= 9,
        'strong_broadway':           lambda hi, lo: hi >= 11 and lo >= 9,
        'medium_broadway_suited':    lambda hi, lo: hi >= 10 and lo >= 8,
        'medium_broadway':           lambda hi, lo: hi >= 10 and lo >= 8,
        'weak_broadway_suited':      lambda hi, lo: hi >= 7 and lo >= 5,
        'weak_broadway':             lambda hi, lo: hi >= 7 and lo >= 5,
    },
    'suited_connector': {
        'high_suited_connector':    lambda hi, lo: hi == 9 and lo == 8,
        'medium_suited_connector':  lambda hi, lo: hi <= 8 and hi >= 5 and lo == hi - 1,
        'low_suited_connector':     lambda hi, lo: hi <= 4 and hi >= 3 and lo == hi - 1,
    },
    'suited_aces': {
        'suited_ace': lambda hi, lo: hi == 12 and lo >= 6,
    },
    'offsuit_broadway': {
        'offsuit_broadway': lambda hi, lo: hi >= 11 and lo >= 8 and lo <= 9,
    },
    'offsuit_connector': {
        'offsuit_connector': lambda hi, lo: hi >= 8 and hi >= 6 and lo == hi - 1 and hi < 12,
    },
    'suited_one_gapper': {
        'suited_one_gapper': lambda hi, lo: hi >= 10 and 2 <= (hi - lo) <= 3,
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


# Propiedad derivada de RangeState para pesos de clase
def class_weights_for_reach(reach: np.ndarray) -> np.ndarray:
    """reach normalizado ponderado por clase base.
    
    Útil para inicializar ranges donde cada clase debe tener
    representación proporcional a su peso base."""
    w = reach.copy()
    w *= _BASE_WEIGHT
    total = w.sum()
    if total <= 0:
        return np.zeros(N_COMBOS, dtype=np.float32)
    return w / total


# Cache para uso por etiqueta
_HAND_LABEL_TO_IDX = {lab: i for i, lab in enumerate(HAND_LABELS)}


def hand_class_of_label(label: str) -> tuple:
    """Clase/sub-clase/peso de una mano por su etiqueta ('AhKh')."""
    idx = _HAND_LABEL_TO_IDX.get(label)
    if idx is None:
        return ('other', 'other', 0.25)
    return hand_class(idx)


# Propiedad derivada: weight ponderado por clase para normalización
# weight_class[idx] = base_weight[idx] * (1.0 si es la clase base)
# Se usa para el scaling del reach inicial


def class_weights_vector() -> np.ndarray:
    """Vector (1326,) con los pesos base por clase para cada combo."""
    return _BASE_WEIGHT.copy()


def combos_by_sub_class(sub_class: str) -> np.ndarray:
    """Índices de combos que pertenecen a una sub-clase."""
    return np.where(_HAND_SUB_CLASS == sub_class)[0]


def combos_by_class(hand_class_name: str) -> np.ndarray:
    """Índices de combos que pertenecen a una clase."""
    return np.where(_HAND_CLASS_NAME == hand_class_name)[0]


# Propiedad derivada de RangeState para pesos de clase
def class_weights_for_reach(reach: np.ndarray) -> np.ndarray:
    """reach normalizado ponderado por clase base.
    
    Útil para inicializar ranges donde cada clase debe tener
    representación proporcional a su peso base."""
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
    'premium_broadway_suited': {'r': 0.90, 'b': 1.00, 'c': 0.95, 'f': 0.05},
    'premium_broadway':       {'r': 0.85, 'b': 0.95, 'c': 0.90, 'f': 0.10},
    'strong_broadway_suited': {'r': 0.50, 'b': 0.85, 'c': 0.85, 'f': 0.15},
    'strong_broadway':        {'r': 0.45, 'b': 0.80, 'c': 0.85, 'f': 0.15},
    'medium_broadway_suited': {'r': 0.25, 'b': 0.60, 'c': 0.70, 'f': 0.30},
    'medium_broadway':        {'r': 0.20, 'b': 0.55, 'c': 0.70, 'f': 0.35},
    'weak_broadway_suited':   {'r': 0.12, 'b': 0.45, 'c': 0.55, 'f': 0.40},
    'weak_broadway':          {'r': 0.08, 'b': 0.35, 'c': 0.55, 'f': 0.60},
    'high_suited_connector':  {'r': 0.10, 'b': 0.45, 'c': 0.60, 'f': 0.50},
    'medium_suited_connector':{'r': 0.05, 'b': 0.35, 'c': 0.55, 'f': 0.60},
    'low_suited_connector':   {'r': 0.03, 'b': 0.25, 'c': 0.45, 'f': 0.70},
    'suited_ace':       {'r': 0.70, 'b': 0.85, 'c': 0.85, 'f': 0.15},
    'offsuit_broadway': {'r': 0.40, 'b': 0.75, 'c': 0.80, 'f': 0.20},
    'offsuit_connector':{'r': 0.05, 'b': 0.30, 'c': 0.45, 'f': 0.65},
    'suited_one_gapper':{'r': 0.20, 'b': 0.50, 'c': 0.65, 'f': 0.35},
    'offsuit_one_gapper':{'r': 0.08, 'b': 0.30, 'c': 0.40, 'f': 0.65},
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
    for _class_name, subs in _NONPAIR_SUBS.items():
        for sub, pred in subs.items():
            if pred(hi, lo):
                if suited and 'suited' in sub:
                    return sub
                if not suited and 'suited' not in sub:
                    return sub
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