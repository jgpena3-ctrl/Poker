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

def _preflop_category(hand_code):
    """Categoría burda preflop de un combo: 'premium', 'big', 'medium',
    'speculative', 'weak'. Acepta 'AhKh', 'AK' o 'AKs'. Arranque de la
    tabla heurística."""
    code = hand_code
    if len(code) == 4:          # 'AhKh' -> rangos en [0] y [2]
        r0, r1 = code[0], code[2]
    elif len(code) in (2, 3):   # 'AK' / 'AKs' / '72o'
        r0, r1 = code[0], code[1]
    else:
        raise ValueError(f'código de mano inválido: {hand_code!r}')
    i0, i1 = RANK_ORDER.index(r0), RANK_ORDER.index(r1)
    top = max(i0, i1)
    low = min(i0, i1)
    if r0 == r1:
        if top >= 12:
            return 'premium'        # AA
        if top >= 10:
            return 'big'            # KK, QQ
        if top >= 8:
            return 'medium'         # JJ, TT, 99, 88
        return 'speculative'        # pares menores
    if top >= 11 and low >= 10:
        return 'big'                # A bojad, KQ ...
    if top >= 10:
        return 'medium'
    return 'speculative' if top >= 6 else 'weak'


def default_action_prob(hand_code, action, context):
    """P(A|H, context) de arranque (tabla heurística, editable).

    context: dict con 'street', 'position', 'sizing', 'pot', 'players',
             'history'. En preflop se usa la categoría del combo; en postflop
             aún neutro (0.5) hasta conectar el evaluador en la siguiente fase.
    """
    if isinstance(hand_code, (list, tuple)):
        hand_code = ''.join(hand_code)
    street = context.get('street', 'preflop')
    if street == 'preflop':
        cat = _preflop_category(hand_code)
        table = {
            'premium':     {'r': 0.85, 'b': 0.95, 'c': 0.90, 'f': 0.05},
            'big':         {'r': 0.45, 'b': 0.80, 'c': 0.85, 'f': 0.10},
            'medium':      {'r': 0.15, 'b': 0.55, 'c': 0.70, 'f': 0.40},
            'speculative': {'r': 0.05, 'b': 0.35, 'c': 0.55, 'f': 0.65},
            'weak':        {'r': 0.01, 'b': 0.15, 'c': 0.30, 'f': 0.85},
        }
        return table[cat].get(action, 0.5)
    return 0.5