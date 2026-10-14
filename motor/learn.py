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

# ---------------------------------------------------------------------------
# ESTADO CANONICO DE hands_db.jsonl
# ---------------------------------------------------------------------------
# `hands_db.jsonl` solo se modifica con un SCRIPT VERSIONADO, nunca a mano.
# Este es el estado declarado, y `motor/test_canal_manual.py` lo vigila.
#
# Un cambio manual no rompe este archivo: rompe el HASH. Y el hash esta aqui,
# al lado de la ventana que usa el motor, para que no pueda haber dos verdades.
#
# Cuando el cambio sea legitimo, hay que actualizar ESTA constante Y el
# documento que explica por que. Subir el hash sin el motivo es tan malo como
# editar a mano: es dejar constancia de algo que no se sabe por que paso.
#
#   version   estado
#   --------  ------------------------------------------------------------
#   e314f74   referencia. cm-001, cm-003 y la ventana de 877.
#   75bbdb7   estado vigente: 1280 -> 1258 (22 manos borradas) + 74
#             modificadas a mano sobre 02fc641. SIN DECLARAR TODAVIA:
#             `DOCS/CAMBIOS_MANUALES_68.md`. Ver `CANAL_MANUAL_CERRADO.md`.
#   e314f74   salida de `tools/aplicar_reinterpretacion.py`
#             (sha256 173a7274...). Estado ALTERNATIVO, al que se puede volver
#             con `--apply --descartar-cambios`.
#
# Este sha256 es el del FICHERO EN DISCO, y coincide con el blob del repositorio
# porque `.gitattributes` marca `data/hands_db.jsonl -text`. Sin eso, git
# normalizaba a LF y el blob nunca podia coincidir con el disco: medido,
# blob `7d972b2b` (0 CRLF) contra disco `202a1f54` (1258 CRLF). Un hash que
# no se puede reproducir no es un hash.
#
# Documentacion: `DOCS/CANAL_MANUAL_CERRADO.md`, `DOCS/RANGO_VIGENTE.md`.
HANDS_DB_COMMIT = '75bbdb7'
HANDS_DB_SHA256 = (
    '202a1f548fc60bac3d0d4b7a225429083e22298d97a5f6f38cb28d24435b0634')
HANDS_DB_LINEAS = 1258

# El rango AUDITADO no es el de calibracion. Son dos cosas distintas y
# confundirlas es lo que produjo tres cifras conviviendo:
# `RELIABLE_HANDS` = 900, ventana real = 877 (900 - 23 de CM-004), y rango
# auditado = 991. Ver `DOCS/RANGO_VIGENTE.md`.
RANGO_AUDITADO_HASTA = 'H_1014'
RANGO_AUDITADO_LINEAS = 991

# Manos que la ventana fiable EXCLUYE, y por que.
#
# No es una poda de rango: la exclusion es por defecto de DATO, y la mano
# sigue intacta en `hands_db.jsonl` y en `load_hands(reliable_only=False)`.
# Se excluyen de la CALIBRACION porque su defecto esta identificado y su
# efecto no esta cuantificado; mantenerlas dentro seria usar unas cifras
# que el propio proyecto ya sabe que no son fiables.
#
# CM-004 (23 manos): la entrada `BB: 'b'` —la ciega— aparecia DESPUES de
# acciones voluntarias. `_es_ciega_bb` exige `not voluntary_before`, asi que
# no la reconocia como ciega y el motor la leia como una subida que puede no
# haber ocurrido.
#
# ATUALIZADO 2026-10-14: ese defecto ya NO existe. Las 23 se reescribieron a
# mano (sin original: `DOCS/CORRELACION_CAPTURAS_CM004.md` sigue dando 0 de 23)
# y `defecto_orden_ciega_bb` da 0 de 1280.
#
# OJO: la exclusion sigue puesta, pero POR OTRO MOTIVO, y este comentario ya
# no lo describe. El texto de arriba era su fundamento y es falso; el motivo
# vigente —que el sustituto tampoco tiene original— todavia NO esta escrito,
# y decidir si las 23 vuelven a la ventana es una decision abierta del
# mantenedor de la base. Ver `DOCS/DECISION_CM004.md` §0 y
# `DOCS/CM004_REINTERPRETACION.md`.
#
# Es reversible en cuanto haya original: borrar la entrada de abajo devuelve
# las 23 a la ventana, y `tools/verificar_cm004.py` avisa si el conjunto deja
# de coincidir con lo que el motor señala.
EXCLUSIONES_VENTANA_FABLE = (
    ('CM-004',
     'ciega del BB despues de acciones voluntarias: el motor la lee como '
     'una subida que pudo no ocurrir',
     frozenset((
         'H_0031', 'H_0037', 'H_0039', 'H_0051', 'H_0067', 'H_0078',
         'H_0104', 'H_0107', 'H_0109', 'H_0127', 'H_0143', 'H_0147',
         'H_0161', 'H_0170', 'H_0183', 'H_0210', 'H_0215', 'H_0248',
         'H_0262', 'H_0263', 'H_0279', 'H_0294', 'H_0722',
     ))),
)


def manos_excluidas():
    """Set de `hand_id` que la ventana fiable deja fuera."""
    out = set()
    for _clave, _motivo, ids in EXCLUSIONES_VENTANA_FABLE:
        out |= set(ids)
    return out


def motivos_exclusion(hand_id):
    """Motivo por el que una mano queda fuera de la ventana fiable, o None."""
    motivos = []
    for clave, motivo, ids in EXCLUSIONES_VENTANA_FABLE:
        if hand_id in ids:
            motivos.append('%s: %s' % (clave, motivo))
    return '; '.join(motivos) or None


def load_hands(path=None, *, max_hands=None, reliable_only=False):
    """Carga las manos válidas (dicts) de data/hands_db.jsonl.

    Descartadas: líneas rotas o faltan `players`/`streets`.

    max_hands: límite duro de manos válidas (None = todas).
    reliable_only: si True, corta en las primeras RELIABLE_HANDS lineas Y
        excluye las manos de `EXCLUSIONES_VENTANA_FABLE` (hoy las 23 de
        CM-004). Las manos NO se borran: siguen en el fichero y en
        `load_hands(reliable_only=False)`. Se excluyen de la calibracion
        porque su defecto esta identificado y su efecto sin cuantificar.
    """
    if max_hands is not None and max_hands <= 0:
        return []
    path = path or DB_PATH
    excluir = manos_excluidas() if reliable_only else frozenset()
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
                if hand.get('hand_id') in excluir:
                    continue
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

    Parámetros conservados por compatibilidad con las llamadas existentes, que
    NO participan en la decisión:
      - `i`: la detección no depende de la posición en la secuencia
             (revision_2, Hallazgo 3).
      - `amount`: ver "Por qué el importe ya NO decide".
      - `bb`: constante nominal, sin uso desde que el importe dejó de decidir.

    Por qué se conservan en vez de borrarse: los 19 llamadores actuales
    (1 en producción, el resto en tests y auditorías) pasan la tupla
    desempacada de `_preflop_sequence` de forma POSICIONAL:
    `_es_ciega_bb(i, pos, act, amount, is_blind, voluntary_before, bb)`.
    Quitar `i`, `amount` y `bb` obligaría a reescribir los 19 para descartar
    elementos, en 6 ficheros, sin cambiar ni una línea de comportamiento.
    Es deuda con coste de mantenimiento, no deuda de corrección; mientras
    todo el mundo pase la tupla entera, el churn no compensa.

    MEDIDO: 19 llamadas en 6 ficheros (`learn.py`, `test_ciega_bb.py`,
    `test_orden_preflop.py`, `test_revision12.py`, `auditar_bb_check.py`,
    `auditar_orden_folds.py`). Si algún día se borran, el cambio es puramente
    mecánico y la suite lo comprueba.

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

    LIMITACIÓN CONOCIDA
    -------------------
    La regla exige `act == 'b'`, así que una subida registrada correctamente
    como `'r'` NUNCA se lee como ciega, aunque venga después de solo folds. El
    riesgo real es más estrecho: que el recorder escribiera una subida
    voluntaria del BB como `'b'` y sin ninguna acción voluntaria antes. Entonces
    sí se leería como ciega.

    Medido sobre las 900 manos fiables: **0 casos**. Es una medición, no una
    prueba, y por eso hay un test que la fija.
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
# CM-004: la ciega del BB puesta donde no puede estar
# ---------------------------------------------------------------------------
# Vive aqui y no en `tools/auditar_bb_check.py` porque es una REGLA QUE
# DECIDE, y la regla no puede vivir en un script de auditoria: la copia se
# queda vieja y el motor acaba usando la otra (el mismo motivo por el que
# `no_puede_actuar` esta en `motor/multiway.py` y no en su script).
# `auditar_bb_check` importa estas funciones; no las reimplementa.

CAUSA_ORDEN = 'tras_accion_voluntaria'
CAUSA_IMPORTE = 'importe_sobre_nominal'


def entradas_bb_rechazadas(hand, bb=BB):
    """Entradas `BB b` que el motor NO reconocio como ciega obligatoria.

    Se reproduce el recorrido de `preflop_events` (que mantiene
    `voluntary_before`) usando la propia funcion `_es_ciega_bb`, en vez de
    mirar el campo `blind` del dato: los datos antiguos no lo traen y la
    ciega se reconoce estructuralmente. Mirar el campo daria ~523 falsos
    positivos.

    Devuelve [(indice, importe, causa)]. El indice es de `_preflop_sequence`
    y coincide con el de `streets.preflop.actions` (lo fija
    `test_el_indice_apunta_a_la_accion_cruda`).

    `CAUSA_IMPORTE` no es un defecto de dato: era un defecto del motor, ya
    corregido. `CAUSA_ORDEN` si lo es, y es lo que se conoce como CM-004.
    """
    seq = _preflop_sequence(hand)
    rechazadas = []
    voluntary_before = False
    for i, (pos, act, amount, is_blind) in enumerate(seq):
        if _es_ciega_bb(i, pos, act, amount, is_blind, voluntary_before, bb):
            if act in ('b', 'r', 'c'):
                voluntary_before = True
            continue
        if pos == 'BB' and act == 'b':
            causa = CAUSA_ORDEN if voluntary_before else CAUSA_IMPORTE
            rechazadas.append((i, amount, causa))
        if act in ('b', 'r', 'c'):
            voluntary_before = True
    return rechazadas


def defecto_orden_ciega_bb(hand, bb=BB):
    """True si alguna `BB b` de esta mano no puede ser la ciega (CM-004).

    El INVARIANTE del bloque. Importa la funcion el hecho de que sea el motor
    quien lo decida: una cuenta hecha fuera podria discrepar de `_es_ciega_bb`
    y volver a publicar un numero que el motor no sostiene.
    """
    return any(causa == CAUSA_ORDEN
               for _i, _amt, causa in entradas_bb_rechazadas(hand, bb))


def manos_con_orden_ciega_malo(hands=None):
    """`hand_id` de las manos de la lista que violan el invariante CM-004."""
    if hands is None:
        hands = load_hands(reliable_only=False)
    return [h.get('hand_id') for h in hands if defecto_orden_ciega_bb(h)]


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