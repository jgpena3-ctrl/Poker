"""learn.py — extracción de frecuencias preflop desde hands_db.jsonl.

Especificación: DOCS/APRENDIZAJE.md (pegar4 · perfiles pegar5 §5).

Principios:
- Dos tipos de evidencia que NO se mezclan: mano conocida (P(A|H, contexto))
  y mano desconocida (P(A|contexto)). `hand_known` se guarda por evento.
- `hand_known` es True SI Y SOLO SI hay cartas registradas. Un hero sin
  cartas NO cuenta como mano conocida (F2.6): asumirlo seria inventar
  informacion que el recorder no registro.
- Cada jugador entra UNA vez por mano con su primera decisión preflop; el
  estado del bote en ese momento (raises/limps previos) define la categoría
  (limp / open / RIL / 3bet / squeeze / 4bet / fold...) y el denominador
  (oportunidad) al que aporta.

Categorías y sus denominadores (CATEGORY_DENOM):
    no_raise      : fold, limp, open, call_limp, rol, bb_check
    facing_open   : call_open, 3bet, squeeze, fold_vs_open
    facing_3bet   : call_3bet, 4bet, fold_vs_3bet

Taxonomía completa y racional: docs/APRENDIZAJE.md §6.
"""
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Tuple

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_DIR, 'data', 'hands_db.jsonl')

BB = 1.0                                  # big blind nominal del juego
HERO_NAMES = ('Jarduan',)                 # el usuario real: mano siempre conocida

CATEGORY_DENOM = {
    'fold': 'no_raise', 'limp': 'no_raise', 'open': 'no_raise',
    'call_limp': 'no_raise', 'rol': 'no_raise', 'bb_check': 'no_raise',
    'call_open': 'facing_open', '3bet': 'facing_open',
    'squeeze': 'facing_open', 'fold_vs_open': 'facing_open',
    'call_3bet': 'facing_3bet', '4bet': 'facing_3bet',
    'fold_vs_3bet': 'facing_3bet',
}
DENOM_ORDER = ('no_raise', 'facing_open', 'facing_3bet')
CATEGORY_ORDER = ('open', 'limp', 'rol', 'call_limp', 'call_open', '3bet',
                  'squeeze', '4bet', 'call_3bet', 'fold', 'fold_vs_open',
                  'fold_vs_3bet', 'bb_check')


# ---------------------------------------------------------------------------
# Carga y lectura del historial
# ---------------------------------------------------------------------------

RELIABLE_HANDS = 900


def load_hands(path=None, *, max_hands=None, reliable_only=False):
    """Carga las manos válidas (dicts) de data/hands_db.jsonl.

    Descartadas: líneas rotas o faltan `players`/`streets`.

    max_hands: límite duro de manos válidas (None = todas).
    reliable_only: si True, corta en las primeras RELIABLE_HANDS manos.
    """
    if max_hands is not None and max_hands <= 0:
        return []
    path = path or DB_PATH
    if reliable_only:
        limit = RELIABLE_HANDS if max_hands is None \
            else min(max_hands, RELIABLE_HANDS)
    else:
        limit = max_hands
    hands = []
    with open(path, encoding='utf-8') as f:
        for line_no, line in enumerate(f, start=1):
            if limit is not None and line_no > limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                hand = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(hand, dict) and hand.get('streets') is not None \
                    and hand.get('players') is not None:
                hands.append(hand)
    return hands


def player_of_pos(hand, pos):
    """Nombre del jugador sentado en `pos` ('' si no está)."""
    for p in hand.get('players', []):
        if p.get('pos') == pos:
            return p.get('name') or ''
    return ''


def cards_of_pos(hand, pos):
    """Cartas registradas del jugador en `pos` ('' si ninguna)."""
    for p in hand.get('players', []):
        if p.get('pos') == pos and p.get('cards'):
            c = p['cards']
            return ''.join(c) if isinstance(c, (list, tuple)) else str(c)
    return ''


def hand_known(player, cards):
    """Mano conocida si hay cartas registradas."""
    return bool(cards)


# ---------------------------------------------------------------------------
# Clasificación de la primera decisión preflop
# ---------------------------------------------------------------------------

@dataclass
class PreflopEvent:
    """Primera decisión preflop de un jugador en una mano."""
    hand_id: str
    player: str
    pos: str
    category: str                 # clave en CATEGORY_DENOM
    denom: str                    # no_raise | facing_open | facing_3bet
    amount: float
    hand_known: bool
    cards: str
    prereq: Tuple[str, ...]       # acciones previas ('POS:a')


def classify_first_action(action, amount, raises_before, limps_before, bb=BB, callers=0):
    """Categoría + denominador de la primera decisión preflop de un jugador.

    action: 'f' | 'x' | 'c' | 'b' | 'r'   (formato del recorder)
    """
    if action == 'x':
        return 'bb_check', 'no_raise'
    if action == 'f':
        if raises_before == 0:
            return 'fold', 'no_raise'
        if raises_before == 1:
            return 'fold_vs_open', 'facing_open'
        return 'fold_vs_3bet', 'facing_3bet'
    if action == 'c':
        if raises_before == 0:
            return ('limp' if limps_before == 0 else 'call_limp'), 'no_raise'
        if raises_before == 1:
            return 'call_open', 'facing_open'
        return 'call_3bet', 'facing_3bet'
    if action in ('b', 'r'):
        # Un 'b'/'r' de a lo sumo 1BB sin subida previa es un limpe corto grabado
        # como bet (ver PROYECTO.md §6.1). No se cuenta como subida real.
        if raises_before == 0 and (amount is not None) and amount <= bb + 1e-9:
            return 'limp', 'no_raise'
        if raises_before == 0:
            return 'open' if limps_before == 0 else 'rol', 'no_raise'
        if raises_before == 1:
            # squeeze = subir cuando ALGUIEN YA HA PAGADO la apuesta
            # vigente. Ese es exactamente `callers` (calls con subida
            # previa).
            #
            # `limps_before` NO cuenta: un limpe ocurre ANTES del open,
            # asi que el open se hizo 'sobre limp' y quien paga la subida
            # actual no se esta levantando por nadie -> es un 3bet normal.
            #   UTG c1.0 (limp) | MP r3.0 (open over limp) | CO r8.0
            #     -> raises=1, limps=1, callers=0 -> 3bet, NO squeeze.
            # Mezclar ambos daba 13 falsos squeezes en las 900 fiables.
            return ('squeeze' if callers >= 1 else '3bet'), 'facing_open'
        return '4bet', 'facing_3bet'
    raise ValueError(f'acción preflop desconocida: {action!r}')


def _preflop_sequence(hand):
    """Secuencia preflop normalizada: [(pos, action, amount, is_blind)] válidos.

    `is_blind` es la identidad explícita de una ciega obligatoria (no una
    decisión voluntaria). El recorder la marca; para datos antiguos sin marca
    se infiere estructuralmente en `_es_ciega_bb`.
    """
    actions = (hand.get('streets', {}).get('preflop', {}) or {}).get('actions', [])
    seq = []
    for a in actions:
        if isinstance(a, dict):
            pos, act = a.get('pos'), a.get('action')
            try:
                amount = float(a.get('amount') or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
            is_blind = bool(a.get('blind') or a.get('is_blind'))
        else:
            try:
                pos, act, amount = a[0], a[1], float(a[2] or 0.0)
            except (IndexError, TypeError, ValueError):
                continue
            is_blind = bool(a[3]) if len(a) > 3 else False
        if not pos or not act:
            continue
        seq.append((pos, act, amount, is_blind))
    return seq


def _es_ciega_bb(i, pos, act, amount, is_blind, voluntary_before, bb=BB):
    """True si esta acción es la ciega obligatoria del BB (no una decisión).

    `i` se conserva en la firma por compatibilidad, pero **no** se usa: la
    detección no depende de la posición en la secuencia (revision_2, Hallazgo 3).

    Orden de confianza:
      1. Marca explícita del recorder (`blind`) — identidad, no heurística.
      2. Respaldo estructural para datos antiguos: posición BB, acción 'b' y
         sin ninguna acción voluntaria anterior.

    Por qué el importe ya NO decide
    --------------------------------
    Antes exigía `amount <= bb`, con `bb` = constante nominal. Medido sobre la
    ventana fiable eso rechazaba 4 manos cuya ciega real es 2.5-92.0 y cuyo
    `BB b` estaba en el índice 0: el motor las creditaba con una SUBIDA
    (`rol`/`squeeze`/`3bet`/`open`) que probablemente no ocurrió.

    La condición era además redundante. Si no ha habido ninguna acción
    voluntaria previa, un `BB b` no puede ser una subida: nadie ha puesto
    dinero todavía, así que no hay nada que subir. `voluntary_before` ya captura
    esa información, y los folds no la activan (un fold no pone dinero).

    LIMITACIÓN CONOCIDA: si el recorder perdiera las acciones anteriores y
    entregara `UTG f, MP f, ..., BB r 6.0`, esa subida sí se leería como ciega.
    Medido: 0 casos en las 900 manos fiables, donde `BB r` nunca es la primera
    entrada BB tras solo folds. Es una medición, no una prueba; por eso hay un
    test que la fija.
    """
    if is_blind:
        return True
    if pos == 'BB' and act == 'b' and not voluntary_before:
        return True
    return False


def preflop_events(hand, bb=BB):
    """Primera decisión de cada jugador en preflop -> [PreflopEvent]."""
    seq = _preflop_sequence(hand)
    events = []
    decided = set()
    raises = 0
    limps = 0
    callers = 0        # calls que ya enfrentaban una subida (squeeze)
    voluntary_before = False   # ¿hubo ya una acción voluntaria (subida o limp)?
    for i, (pos, act, amount, is_blind) in enumerate(seq):
        es_ciega_bb = _es_ciega_bb(i, pos, act, amount, is_blind,
                                   voluntary_before, bb)
        if es_ciega_bb:
            continue
        if pos in decided:
            if act in ('b', 'r'):
                raises += 1
                voluntary_before = True
            elif act == 'c':
                # Un call con subida previa NO es limp, pero si cuenta
                # como 'ya hay gente dentro' para detectar un squeeze.
                if raises == 0:
                    limps += 1
                else:
                    callers += 1
                voluntary_before = True
            continue
        decided.add(pos)
        category, denom = classify_first_action(act, amount, raises, limps, bb, callers)
        cards = cards_of_pos(hand, pos)
        events.append(PreflopEvent(
            hand_id=hand.get('hand_id', '?'),
            player=player_of_pos(hand, pos) or pos,
            pos=pos,
            category=category,
            denom=denom,
            amount=amount,
            hand_known=hand_known(player_of_pos(hand, pos), cards),
            cards=cards,
            prereq=tuple(f'{p}:{a}' for p, a, _m, _b in seq[:i]),
        ))
        if act in ('b', 'r'):
            raises += 1
            voluntary_before = True
        elif act == 'c':
            if raises == 0:
                limps += 1
            else:
                callers += 1
            voluntary_before = True
    return events


# ---------------------------------------------------------------------------
# Agregación de frecuencias
# ---------------------------------------------------------------------------

class PreflopStats:
    """Frecuencias preflop por jugador (cats / denoms), con mano conocida o no."""

    def __init__(self):
        self.cats: Dict[str, Counter] = defaultdict(Counter)
        self.denoms: Dict[str, Counter] = defaultdict(Counter)
        self.known: Dict[str, Counter] = defaultdict(Counter)   # manos conocidas por denom
        # Agregación por (jugador, posición): validar matrices por posición
        self.cats_pos: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
        self.denoms_pos: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
        self.hands: int = 0

    @classmethod
    def from_hands(cls, hands, bb=BB):
        stats = cls()
        stats.hands = len(hands)
        for hand in hands:
            for ev in preflop_events(hand, bb):
                stats.cats[ev.player][ev.category] += 1
                stats.denoms[ev.player][ev.denom] += 1
                if ev.hand_known:
                    stats.known[ev.player][ev.denom] += 1
                # Agregación por (jugador, posición): permite validar
                # `preflop_matrices.json`, que sí es por posición, contra la DB.
                key = (ev.player, ev.pos)
                stats.cats_pos[key][ev.category] += 1
                stats.denoms_pos[key][ev.denom] += 1
        return stats

    def opportunities(self, player, category=None, pos=None):
        """Oportunidades de `player` (opcionalmente en una posición concreta).

        `category=None` devuelve la suma de los tres denominadores, que **no**
        es el denominador de ninguna columna de frecuencia: es sólo el total de
        decisiones del jugador. Para una frecuencia usar siempre la categoría
        (o su denominador explícito), nunca este total.
        """
        if pos is not None:
            d = self.denoms_pos.get((player, pos))
            if category is None:
                return sum(d.values()) if d else 0
            return (d or {})[CATEGORY_DENOM[category]]
        if category is None:
            return sum(self.denoms[player].values())
        return self.denoms[player][CATEGORY_DENOM[category]]

    def freq(self, player, category, pos=None):
        """Frecuencia de `category` sobre su denominador (None si sin opp)."""
        n = self.opportunities(player, category, pos)
        if n == 0:
            return None
        if pos is not None:
            return self.cats_pos[(player, pos)][category] / n
        return self.cats[player][category] / n

    def report(self, players=None) -> str:
        cols = ('open', 'limp', 'rol', 'call_open', '3bet', 'squeeze',
                '4bet', 'call_3bet')
        head = ('PLAYER').ljust(12) + ''.join(f'{c:>9}' for c in cols) + \
            '   nr    fo    f3   tot'
        lines = [head, '-' * len(head)]
        for name in (players or sorted(self.cats)):
            if not self.cats[name]:
                continue
            row = []
            for c in cols:
                f = self.freq(name, c)
                row.append(f'{f * 100:8.0f}%' if f is not None else '    n/a')
            d = self.denoms[name]
            opp = (f"{d['no_raise']:>5}{d['facing_open']:>6}"
                   f"{d['facing_3bet']:>6}{sum(d.values()):>6}")
            lines.append(f'{name[:12]:<12}' + ''.join(row) + '  ' + opp)
        lines.append('nr=no_raise  fo=facing_open  f3=facing_3bet  tot=suma')
        return '\n'.join(lines)

    def to_dict(self):
        return {
            'hands': self.hands,
            'denoms': {p: dict(d) for p, d in self.denoms.items()},
            'cats': {p: dict(c) for p, c in self.cats.items()},
            'known_denoms': {p: dict(d) for p, d in self.known.items()},
            'denoms_pos': {f'{p}|{pos}': dict(d)
                           for (p, pos), d in self.denoms_pos.items()},
            'cats_pos': {f'{p}|{pos}': dict(c)
                         for (p, pos), c in self.cats_pos.items()},
        }


def main(argv=None):
    """CLI: python -m motor.learn [--json] [--out PATH]."""
    import sys
    argv = list(argv or sys.argv[1:])
    write_json = '--json' in argv
    out_path = ''
    if '--out' in argv:
        out_path = argv[argv.index('--out') + 1] if len(argv) > argv.index('--out') + 1 else ''
    hands = load_hands(reliable_only=True)
    stats = PreflopStats.from_hands(hands)
    print(f'Manos cargadas: {len(hands)}\n')
    print(stats.report())
    if write_json:
        path = out_path or os.path.join(REPO_DIR, 'data', 'preflop_stats.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(stats.to_dict(), f, indent=2, ensure_ascii=False)
        print(f'\n-> {path}')


if __name__ == '__main__':
    main()