"""field_eligibility.py — política explícita de elegibilidad por campo (P0-2).

El problema que cierra
----------------------
`data/hands_db.jsonl` es la base canónica del registro, pero no todos sus
campos son aptos para todos los consumidores. Un tablero ausente no invalida
una observación marginal de `facing`; una acción imposible sí invalida la
observación de esa acción y las que dependen de ella; un stack nulo no
convierte una etiqueta en canónica; un bote `NADA` no puede alimentar EV/ROI.

La regla de este módulo es una sola:

> **El defecto se aplica por campo y por observación, nunca por mano entera.**

Este módulo NO filtra nada en producción. Calcula, en sombra, qué observación
usa cada consumidor y cuáles quedarían restringidas si la política se
activara. `build_models()` sigue construyendo exactamente los mismos modelos.

Vocabulario
-----------
Campo (`FIELD_*`): la unidad del dato —acciones, orden, posición, identidad,
cartas, tablero, bote, stack, allin, showdown, ganador, resultado económico.

Estado (`VALID`, `INVALID`, `ABSENT`, `DERIVED`, `AMBIGUOUS`):
- `valid`: el campo está y es utilizable.
- `invalid`: el campo está, pero se contradice con la secuencia o el formato.
- `absent`: el campo no está. No es lo mismo que cero.
- `derived`: hay un valor reconstruido, pero no es canónico.
- `ambiguous`: hay un valor, pero no se puede determinar si es correcto.

Consumidor (`CONSUMER_*`): el modelo que usa la observación.
- `preflop_stats`: VPIP/PFR/3BET/4BET de `TransitionStats`.
- `profile_range`: `ProfileRangeModel` (P(A|H) preflop).
- `oracle_marginal`: `Oracle` por `facing`, sin textura.
- `oracle_granular`: `Oracle` con textura.
- `postflop_range`: `PostflopRangeModel` (P(A|H) postflop).
- `showdown`: WTSD/W$SD.
- `stack`: media de stack y etiqueta PEZ/TIBURON.
- `economic`: bote/EV/ROI/pot odds.

Granularidad
------------
Una observación puede ser válida para un consumidor marginal y no para uno
condicionado. El tablero ausente es el caso canónico: `oracle_marginal` puede
usar la acción y el `facing`; `oracle_granular` y `postflop_range` no.

Fuente declarada
----------------
`DOCS/B1_EXCEPCION_INVENTARIO.json` contiene los defectos ya auditados por
B1-R/B1-E. La política los carga como fuente declarada y, además, ejecuta
detectores estructurales. Un detector que encuentra algo no declarado NO se
activa: se reporta como `ambiguous` / `no determinable`, para no inventar una
restricción. Los tests sintéticos sí cubren los detectores.
"""
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .action_amount import (
    ABSENT as AMOUNT_ABSENT,
    INVALID as AMOUNT_INVALID,
    classify_amount,
)
from .behavior import build as build_behavior
from .learn import HERO_NAMES, load_hands, preflop_events
from .observations import _seq, extract_hand, extract_hands
from .preflop_contract import walk_preflop

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INVENTORY_PATH = os.path.join(ROOT, 'DOCS', 'B1_EXCEPCION_INVENTARIO.json')

# ---------------------------------------------------------------------------
# Campos
# ---------------------------------------------------------------------------
FIELD_ACTIONS = 'actions'
FIELD_ACTION_ORDER = 'action_order'

# Defectos que afectan al ORDEN de las acciones, no solo a la acción en sí.
ORDER_CODES = frozenset({'posta_repetida', 'ordeno_codigo',
                         'preflop_no_resuelto'})
FIELD_POSITION = 'position'
FIELD_PLAYER_IDENTITY = 'player_identity'
FIELD_PLAYER_CARDS = 'player_cards'
FIELD_BOARD = 'board'
FIELD_POT = 'pot'
FIELD_STACK = 'stack'
FIELD_ALLIN = 'allin'
FIELD_SHOWDOWN = 'showdown'
FIELD_WINNER = 'winner'
FIELD_ECONOMIC_RESULTS = 'economic_results'

FIELDS = (
    FIELD_ACTIONS, FIELD_ACTION_ORDER, FIELD_POSITION,
    FIELD_PLAYER_IDENTITY, FIELD_PLAYER_CARDS, FIELD_BOARD, FIELD_POT,
    FIELD_STACK, FIELD_ALLIN, FIELD_SHOWDOWN, FIELD_WINNER,
    FIELD_ECONOMIC_RESULTS,
)

VALID = 'valid'
INVALID = 'invalid'
ABSENT = 'absent'
DERIVED = 'derived_non_canonical'
AMBIGUOUS = 'ambiguous'

# ---------------------------------------------------------------------------
# Consumidores
# ---------------------------------------------------------------------------
CONSUMER_PREFLOP_STATS = 'preflop_stats'
CONSUMER_POSTFLOP_STATS = 'postflop_stats'
CONSUMER_PROFILE_RANGE = 'profile_range'
CONSUMER_ORACLE_MARGINAL = 'oracle_por_facing'
CONSUMER_ORACLE_GRANULAR = 'oracle_granular'
CONSUMER_POSTFLOP_RANGE = 'postflop_range'
CONSUMER_SHOWDOWN = 'showdown'
CONSUMER_STACK = 'stack'
CONSUMER_ECONOMIC = 'economic'

CONSUMERS = (
    CONSUMER_PREFLOP_STATS, CONSUMER_POSTFLOP_STATS,
    CONSUMER_PROFILE_RANGE,
    CONSUMER_ORACLE_MARGINAL, CONSUMER_ORACLE_GRANULAR,
    CONSUMER_POSTFLOP_RANGE, CONSUMER_SHOWDOWN, CONSUMER_STACK,
    CONSUMER_ECONOMIC,
)

TOL = 1e-6


# ---------------------------------------------------------------------------
# Inventario declarado
# ---------------------------------------------------------------------------
@dataclass
class DeclaredDefects:
    """Defectos ya auditados, cargados desde el inventario B1-E."""
    path: str = ''
    hard_sequence: Dict[str, dict] = field(default_factory=dict)
    order_or_code: Dict[str, str] = field(default_factory=dict)
    board_contradiction: Dict[str, str] = field(default_factory=dict)
    board_missing: Dict[str, str] = field(default_factory=dict)
    comunitarias_truncated: set = field(default_factory=set)
    pot_nada: set = field(default_factory=set)
    pot_unreliable: set = field(default_factory=set)
    pot_internal_conflict: Dict[str, dict] = field(default_factory=dict)
    missing_allin: set = field(default_factory=set)
    active_null_stack: Dict[str, set] = field(default_factory=dict)
    active_no_position_hands: set = field(default_factory=set)
    split_display_incomplete: set = field(default_factory=set)
    field_level_exclusions: Dict[str, list] = field(default_factory=dict)
    recovered_values: Dict[str, dict] = field(default_factory=dict)

    def empty(self) -> bool:
        return not any((
            self.hard_sequence, self.order_or_code,
            self.board_contradiction, self.board_missing,
            self.pot_nada, self.pot_unreliable, self.active_null_stack,
        ))


def load_declared(path: Optional[str] = None) -> DeclaredDefects:
    """Carga el inventario B1-E. Si falta, devuelve una política vacía."""
    path = path or INVENTORY_PATH
    out = DeclaredDefects(path=path)
    if not os.path.exists(path):
        return out
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return out
    det = data.get('actual_defects') or {}
    out.hard_sequence = dict(det.get('hard_sequence') or {})
    out.order_or_code = dict(det.get('order_or_code') or {})
    out.board_contradiction = dict(det.get('board_contradiction') or {})
    out.board_missing = dict(det.get('board_missing') or {})
    out.comunitarias_truncated = set(det.get('comunitarias_truncated') or [])
    out.pot_nada = set(det.get('pot_nada') or [])
    out.pot_unreliable = set(det.get('pot_unreliable') or [])
    conflicts = det.get('pot_internal_conflict') or []
    out.pot_internal_conflict = {
        c.get('hand_id'): c for c in conflicts if isinstance(c, dict)
    }
    out.missing_allin = set(det.get('missing_allin') or [])
    for item in det.get('active_null_stack') or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out.active_null_stack.setdefault(item[0], set()).add(item[1])
    no_pos = det.get('active_no_position') or {}
    out.active_no_position_hands = set(no_pos.get('hands') or [])
    splits = det.get('split_display_incomplete') or []
    out.split_display_incomplete = set(splits)
    adoption = data.get('adoption_1344') or {}
    out.field_level_exclusions = dict(
        adoption.get('field_level_exclusions') or {})
    out.recovered_values = dict(data.get('recovered_values') or {})
    return out


# ---------------------------------------------------------------------------
# Estructuras
# ---------------------------------------------------------------------------
@dataclass
class FieldEligibility:
    field: str
    status: str
    reasons: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    canonical: bool = False
    marginal_usable: bool = False
    conditioned_usable: bool = False
    detail: dict = field(default_factory=dict)


@dataclass
class ActionIssue:
    """Una acción concreta que no se puede leer sin inventar información."""
    street: str
    index: int                  # índice crudo dentro de street.actions
    seq_index: int              # índice dentro de _seq() (alineado con obs)
    pos: str
    action: str
    amount: Optional[float]
    code: str
    detail: str
    severity: str = INVALID     # invalid | ambiguous | code_ambiguous
    source: str = 'detected'    # detected | declared | declared+detected
    taints_context: bool = True
    amount_value_status: Optional[str] = None
    amount_origin_status: Optional[str] = None
    amount_type: Optional[str] = None
    action_inferred: bool = False

    @property
    def key(self):
        return (self.street, self.seq_index)


@dataclass
class DependentAction:
    """Acción posterior cuyo contexto depende de una acción restringida."""
    street: str
    index: int
    seq_index: int
    pos: str
    action: str
    amount: Optional[float]
    root: ActionIssue
    scope: str = 'same_street'   # same_street | later_streets
    amount_value_status: Optional[str] = None
    amount_origin_status: Optional[str] = None


@dataclass
class BoardStatus:
    street: str
    raw: Tuple[str, ...] = ()
    comunitarias: Tuple[str, ...] = ()
    effective: Tuple[str, ...] = ()
    status: str = ABSENT
    reasons: List[str] = field(default_factory=list)
    marginal_usable: bool = False
    granular_usable: bool = False
    bucket_usable: bool = False
    contradiction: bool = False
    comunitarias_usable: bool = False
    has_actions: bool = False


@dataclass
class HandEligibility:
    hand_id: str
    fields: Dict[str, FieldEligibility] = field(default_factory=dict)
    issues: List[ActionIssue] = field(default_factory=list)
    dependent: List[DependentAction] = field(default_factory=list)
    boards: Dict[str, BoardStatus] = field(default_factory=dict)
    players_by_pos: Dict[str, dict] = field(default_factory=dict)
    positions_by_name: Dict[str, List[str]] = field(default_factory=dict)
    null_stack_names: set = field(default_factory=set)
    declared: Optional[DeclaredDefects] = None

    def _issue_maps(self):
        direct = {}
        for issue in self.issues:
            direct[issue.key] = issue
        dep = {}
        for d in self.dependent:
            dep.setdefault((d.street, d.seq_index), d)
        return direct, dep

    def issue_at(self, street: str, seq_index: int) -> Optional[ActionIssue]:
        for issue in self.issues:
            if issue.street == street and issue.seq_index == seq_index:
                return issue
        return None

    def dependent_at(self, street: str,
                     seq_index: int) -> Optional[DependentAction]:
        for d in self.dependent:
            if d.street == street and d.seq_index == seq_index:
                return d
        return None

    def field(self, name: str) -> FieldEligibility:
        return self.fields.get(
            name, FieldEligibility(name, AMBIGUOUS, ['campo no evaluado']))


@dataclass
class ObservationEligibility:
    hand_id: str
    street: str
    seq_index: int
    player: str
    action: str
    consumer: str
    usable: bool
    restricted: bool
    reasons: List[str] = field(default_factory=list)
    direct: bool = False
    dependent: bool = False
    root_code: Optional[str] = None
    board_warning: bool = False
    label_warning: bool = False
    cards_required: bool = False
    cards_present: bool = False
    not_applicable: bool = False
    amount_value_status: Optional[str] = None
    amount_origin_status: Optional[str] = None
    amount_type: Optional[str] = None
    action_inferred: bool = False
    amount_usable: bool = True


# ---------------------------------------------------------------------------
# Utilidades de secuencia
# ---------------------------------------------------------------------------
def _indexed_seq(hand, street):
    """[(seq_index, raw_index, pos, action, amount)] de una calle.

    Reproduce el filtrado de `observations._seq` (pos y action no vacíos),
    pero conserva también el índice crudo de `street.actions`. El índice
    crudo es el que usan los defectos declarados; el índice de secuencia es
    el que alinea con `extract_hand`.
    """
    raw = ((hand.get('streets') or {}).get(street) or {}).get('actions') or []
    out = []
    seq_i = 0
    for raw_i, a in enumerate(raw):
        if isinstance(a, dict):
            pos, act = a.get('pos'), a.get('action')
            amt = classify_amount(a).value
        else:
            try:
                pos, act = a[0], a[1]
                raw_amount = a[2] if len(a) > 2 else None
                amt = classify_amount(raw_amount).value
            except (IndexError, TypeError):
                continue
        if not pos or not act:
            continue
        out.append((seq_i, raw_i, pos, act, amt))
        seq_i += 1
    return out


def _amount_evidence_at(hand, street, raw_idx):
    raw = ((hand.get('streets') or {}).get(street) or {}).get('actions') or []
    if raw_idx is None or raw_idx < 0 or raw_idx >= len(raw):
        return classify_amount({}).as_dict()
    action = raw[raw_idx]
    if isinstance(action, dict):
        return classify_amount(action).as_dict()
    try:
        value = action[2] if len(action) > 2 else None
    except (IndexError, TypeError):
        value = None
    return classify_amount(value).as_dict()


def _amount_issue_fields(hand, street, raw_idx):
    evidence = _amount_evidence_at(hand, street, raw_idx)
    return {
        'amount_value_status': evidence['value_status'],
        'amount_origin_status': evidence['origin_status'],
        'amount_type': evidence['amount_type'],
        'action_inferred': evidence['action_inferred'],
    }


def _fmt_amount(amount):
    return 'ausente' if amount is None else ('%g' % amount)


def _street_names(hand):
    return {p.get('pos'): (p.get('name') or p.get('pos'))
            for p in hand.get('players', [])}


def _board_raw(hand, street):
    s = ((hand.get('streets') or {}).get(street) or {})
    return tuple(s.get('board') or ())


def _comunitarias_raw(hand, street):
    c = (hand.get('comunitarias') or {}).get(street)
    if isinstance(c, str):
        return tuple(x for x in c.split(',') if x)
    return tuple(c or ())


def _has_actions(hand, street):
    return bool(((hand.get('streets') or {}).get(street) or {})
                .get('actions'))


def _action_alignment(hand):
    """(acciones no-ciegas, acciones cuyo `pos` no tiene jugador).

    `extract_hand` descarta las acciones de una posición que no está en
    `players`. No es lo mismo que un tablero ausente: la observación no queda
    mal etiquetada, simplemente no existe. Se cuenta para no confundir
    "ausente" con "válida".
    """
    names = _street_names(hand)
    total = skipped = 0
    for street in ('preflop', 'flop', 'turn', 'river'):
        for _si, _ri, pos, act, _amt in _indexed_seq(hand, street):
            if act == 'p':
                continue
            total += 1
            if pos not in names:
                skipped += 1
    return total, skipped


# ---------------------------------------------------------------------------
# Detección de acciones
# ---------------------------------------------------------------------------
def _is_blind_like(pos, act, amt, live_level, voluntary_before):
    """Ciega/visible: `p`, o `BB b` sin acción voluntaria previa."""
    if act == 'p':
        return True
    return (pos == 'BB' and act == 'b' and not voluntary_before
            and (amt is None or live_level <= amt + TOL))


def detect_action_issues(hand):
    """Detectores estructurales conservadores.

    Devuelve `(issues, dependent)`. Solo marca `invalid` lo que no se puede
    leer sin contradecir la secuencia. Lo dudoso (importe corto, call que
    podría ser all-in, orden) queda `ambiguous` y NO se activa en sombra.
    """
    issues: List[ActionIssue] = []
    dependent: List[DependentAction] = []
    folded = set()
    posted = set()

    # ---------- preflop ----------
    seq = _indexed_seq(hand, 'preflop')
    live_level = 0.0
    last_raiser = None
    acted = set()
    level_at = {}
    voluntary_before = False
    preflop_taint = None
    for seq_i, raw_i, pos, act, amt in seq:
        if preflop_taint is not None:
            dependent.append(DependentAction(
                'preflop', raw_i, seq_i, pos, act, amt,
                preflop_taint, 'same_street'))
            if act == 'f':
                folded.add(pos)
            if act in ('b', 'r', 'c', 'x'):
                voluntary_before = True
            continue
        code = None
        detail = ''
        severity = INVALID
        taints = True
        if _is_blind_like(pos, act, amt, live_level, voluntary_before):
            if pos in posted and act != 'p':
                code = 'posta_repetida'
                detail = ('%s %s %s después de una posta previa del mismo '
                          'jugador' % (pos, act, _fmt_amount(amt)))
            elif act == 'p' and pos in posted:
                code = 'posta_repetida'
                detail = '%s p %s repetida' % (pos, _fmt_amount(amt))
            else:
                posted.add(pos)
                if amt is not None:
                    live_level = max(live_level, amt)
                if act in ('b', 'r', 'c'):
                    voluntary_before = True
                continue
        if code is None:
            if act == 'x':
                # El contrato estricto decide si un check preflop es legal.
                # Aquí solo se marca lo que el contrato no resuelve.
                pass
            elif act in ('b', 'r'):
                if amt is None:
                    evidence = _amount_evidence_at(hand, 'preflop', raw_i)
                    code = ('importe_ausente'
                            if evidence['value_status'] == AMOUNT_ABSENT
                            else 'importe_invalido')
                    detail = '%s %s con importe %s' % (
                        pos, act, evidence['value_status'])
                    severity = 'ambiguous'
                    taints = False
                elif amt <= TOL:
                    code = 'apuesta_cero'
                    detail = f'{pos} {act} {amt:g}'
                elif live_level > TOL and amt <= live_level + TOL:
                    # Un limp corto grabado como b no es una subida. Es un
                    # defecto de código/importe declarado (H_0832, H_0834).
                    code = 'subida_sin_incremento'
                    detail = (f'{pos} {act} {amt:g} con nivel vivo '
                              f'{live_level:g}')
                    severity = 'code_ambiguous'
                    taints = False
                elif pos in acted and live_level <= level_at.get(pos, -1) + TOL:
                    code = 'accion_sin_nueva_apuesta'
                    detail = (f'{pos} {act} {amt:g} sin nueva apuesta desde '
                              f'su acción anterior')
                elif last_raiser == pos:
                    code = 'sube_su_propia_apuesta'
                    detail = f'{pos} {act} {amt:g} sobre su propia apuesta'
                else:
                    last_raiser = pos
                    live_level = amt
            elif act == 'c':
                if amt is None:
                    evidence = _amount_evidence_at(hand, 'preflop', raw_i)
                    code = ('importe_ausente'
                            if evidence['value_status'] == AMOUNT_ABSENT
                            else 'importe_invalido')
                    detail = '%s c con importe %s' % (
                        pos, evidence['value_status'])
                    severity = 'ambiguous'
                    taints = False
                elif live_level <= TOL:
                    code = 'call_sin_apuesta'
                    detail = f'{pos} c {amt:g} sin apuesta viva'
                elif last_raiser == pos:
                    code = 'call_su_propia_apuesta'
                    detail = f'{pos} c {amt:g} sobre su propia apuesta'
                elif pos in acted and live_level <= level_at.get(pos, -1) + TOL:
                    code = 'accion_sin_nueva_apuesta'
                    detail = (f'{pos} c {amt:g} sin nueva apuesta desde '
                              f'su acción anterior')
                elif amt + TOL < live_level:
                    # No se marca invalid: puede ser un all-in corto sin
                    # marca. Se reporta como ambiguo.
                    code = 'call_insuficiente'
                    detail = (f'{pos} c {amt:g} con nivel vivo '
                              f'{live_level:g}; puede ser all-in sin marca')
                    severity = 'ambiguous'
                    taints = False
            elif act == 'f':
                if pos in acted and live_level <= level_at.get(pos, -1) + TOL:
                    code = 'fold_sin_nueva_apuesta'
                    detail = (f'{pos} f 0 sin nueva apuesta desde su '
                              f'acción anterior')
            else:
                code = 'accion_desconocida'
                detail = f'{pos} {act!r}'
        if code is not None:
            issue = ActionIssue(
                'preflop', raw_i, seq_i, pos, act, amt, code, detail,
                severity=severity, taints_context=taints,
                **_amount_issue_fields(hand, 'preflop', raw_i))
            issues.append(issue)
            if severity == INVALID and taints:
                preflop_taint = issue
            if act == 'f':
                folded.add(pos)
            if act in ('b', 'r', 'c'):
                voluntary_before = True
            continue
        if act in ('b', 'r'):
            last_raiser = pos
        if act in ('b', 'r', 'c', 'x'):
            voluntary_before = True
        acted.add(pos)
        level_at[pos] = live_level
        if act == 'f':
            folded.add(pos)

    # El contrato estricto añade los checks preflop que no puede resolver
    # (p. ej. un SB que checkea la ciega del BB). No se activan: son
    # `ambiguous` hasta que exista una decisión explícita.
    raw_seq = None
    try:
        raw_seq = [(p, a, amt, False)
                   for _si, _ri, p, a, amt in seq]
        steps = list(walk_preflop(raw_seq, legacy=False))
    except Exception:
        steps = []
    for step in steps:
        cls = step.classification
        if cls.status != 'unresolved':
            continue
        key = (step.raw.index,)
        if any(i.street == 'preflop' and i.seq_index == step.raw.index
               for i in issues):
            continue
        if any(d.street == 'preflop' and d.seq_index == step.raw.index
               for d in dependent):
            continue
        issues.append(ActionIssue(
            'preflop', step.raw.index, step.raw.index, step.raw.pos,
            step.raw.action, step.raw.amount,
            'preflop_no_resuelto', cls.reason or 'sin razón',
            severity='ambiguous', source='detected', taints_context=False,
            **_amount_issue_fields(hand, 'preflop', step.raw.index)))

    # ---------- postflop ----------
    for street in ('flop', 'turn', 'river'):
        acts = _indexed_seq(hand, street)
        live_level = 0.0
        last_raiser = None
        acted = set()
        level_at = {}
        taint = None
        for seq_i, raw_i, pos, act, amt in acts:
            if taint is not None:
                dependent.append(DependentAction(
                    street, raw_i, seq_i, pos, act, amt, taint,
                    'same_street'))
                if act == 'f':
                    folded.add(pos)
                continue
            code = None
            detail = ''
            severity = INVALID
            taints = True
            if pos in folded:
                code = 'accion_tras_fold'
                detail = '%s %s %s después de retirarse' % (
                    pos, act, _fmt_amount(amt))
                # La acción de un jugador retirado no cambia el contexto
                # posterior: es un no-op. No se propaga taint.
                taints = False
            elif act == 'x':
                if live_level > TOL:
                    code = 'check_enfrentando_apuesta'
                    detail = (f'{pos} x con apuesta viva {live_level:g}')
                elif pos in acted:
                    code = 'check_repetido_sin_apuesta'
                    detail = f'{pos} x repetido sin nueva apuesta'
            elif act in ('b', 'r'):
                if amt is None:
                    evidence = _amount_evidence_at(hand, street, raw_i)
                    code = ('importe_ausente'
                            if evidence['value_status'] == AMOUNT_ABSENT
                            else 'importe_invalido')
                    detail = '%s %s con importe %s' % (
                        pos, act, evidence['value_status'])
                    severity = 'ambiguous'
                    taints = False
                elif amt <= TOL:
                    code = 'apuesta_cero'
                    detail = f'{pos} {act} {amt:g}'
                elif live_level > TOL and amt <= live_level + TOL:
                    code = 'subida_sin_incremento'
                    detail = (f'{pos} {act} {amt:g} con nivel vivo '
                              f'{live_level:g}; puede ser call mal codificado')
                    severity = 'ambiguous'
                    taints = False
                elif pos in acted and live_level <= level_at.get(pos, -1) + TOL:
                    code = 'accion_sin_nueva_apuesta'
                    detail = (f'{pos} {act} {amt:g} sin nueva apuesta desde '
                              f'su acción anterior')
                elif last_raiser == pos:
                    code = 'sube_su_propia_apuesta'
                    detail = f'{pos} {act} {amt:g} sobre su propia apuesta'
                else:
                    last_raiser = pos
                    live_level = amt
            elif act == 'c':
                if amt is None:
                    evidence = _amount_evidence_at(hand, street, raw_i)
                    code = ('importe_ausente'
                            if evidence['value_status'] == AMOUNT_ABSENT
                            else 'importe_invalido')
                    detail = '%s c con importe %s' % (
                        pos, evidence['value_status'])
                    severity = 'ambiguous'
                    taints = False
                elif live_level <= TOL:
                    code = 'call_sin_apuesta'
                    detail = f'{pos} c {amt:g} sin apuesta viva'
                elif last_raiser == pos:
                    code = 'call_su_propia_apuesta'
                    detail = f'{pos} c {amt:g} sobre su propia apuesta'
                elif pos in acted and live_level <= level_at.get(pos, -1) + TOL:
                    code = 'accion_sin_nueva_apuesta'
                    detail = (f'{pos} c {amt:g} sin nueva apuesta desde '
                              f'su acción anterior')
                elif amt + TOL < live_level:
                    code = 'call_insuficiente'
                    detail = (f'{pos} c {amt:g} con nivel vivo '
                              f'{live_level:g}; puede ser all-in sin marca')
                    severity = 'ambiguous'
                    taints = False
            elif act == 'f':
                if pos in acted and live_level <= level_at.get(pos, -1) + TOL:
                    code = 'fold_sin_nueva_apuesta'
                    detail = (f'{pos} f 0 sin nueva apuesta desde su '
                              f'acción anterior')
            else:
                code = 'accion_desconocida'
                detail = f'{pos} {act!r}'
            if code is not None:
                issue = ActionIssue(
                    street, raw_i, seq_i, pos, act, amt, code, detail,
                    severity=severity, taints_context=taints,
                    **_amount_issue_fields(hand, street, raw_i))
                issues.append(issue)
                if severity == INVALID and taints:
                    taint = issue
                if act == 'f':
                    folded.add(pos)
                continue
            if act in ('b', 'r'):
                last_raiser = pos
            acted.add(pos)
            level_at[pos] = live_level
            if act == 'f':
                folded.add(pos)
    return issues, dependent


# ---------------------------------------------------------------------------
# Tablero
# ---------------------------------------------------------------------------
def assess_board(hand, street, prev_effective, declared=None):
    raw = _board_raw(hand, street)
    com = _comunitarias_raw(hand, street)
    has_actions = _has_actions(hand, street)
    out = BoardStatus(street=street, raw=raw, comunitarias=com,
                      has_actions=has_actions)
    if street == 'preflop':
        out.status = VALID
        out.marginal_usable = True
        out.granular_usable = False
        out.bucket_usable = False
        return out
    effective = list(raw)
    if (street in ('turn', 'river') and len(raw) == 1
            and len(prev_effective) >= 3 and raw[0] not in prev_effective):
        effective = list(prev_effective) + list(raw)
    out.effective = tuple(effective)
    expected = {'flop': 3, 'turn': 4, 'river': 5}[street]
    if not raw:
        out.status = ABSENT
        out.reasons.append('tablero ausente en streets.%s' % street)
    elif len(effective) != expected:
        out.status = INVALID
        out.reasons.append(
            'tablero %s con %d cartas; se esperaban %d'
            % (street, len(effective), expected))
    elif len(set(effective)) != len(effective):
        out.status = INVALID
        out.reasons.append('tablero %s con cartas duplicadas' % street)
    else:
        out.status = VALID

    # Comunitarias: es una fuente paralela. Si contradice a `streets`, el
    # board live (streets) sigue siendo el que usan observations/Oracle/
    # postflop, pero se declara la contradicción.
    if com:
        if raw and tuple(com) != tuple(raw):
            out.contradiction = True
            out.reasons.append(
                'comunitarias.%s=%s contradice streets.%s=%s'
                % (street, ','.join(com), street, ','.join(raw)))
        else:
            out.comunitarias_usable = True
    else:
        if raw:
            out.reasons.append('comunitarias.%s ausente' % street)
    if declared and hand.get('hand_id') in declared.board_contradiction:
        if not out.contradiction:
            out.contradiction = True
            out.reasons.append('contradicción declarada por B1-E')
    if declared and hand.get('hand_id') in declared.board_missing:
        if out.status == VALID and not raw:
            out.status = ABSENT
    out.marginal_usable = True   # el `facing` no necesita tablero
    out.granular_usable = (out.status == VALID)
    out.bucket_usable = (out.status == VALID)
    return out


def assess_boards(hand, declared=None):
    out = {}
    prev = ()
    for street in ('preflop', 'flop', 'turn', 'river'):
        st = assess_board(hand, street, prev, declared)
        out[street] = st
        if st.effective:
            prev = st.effective
    return out


# ---------------------------------------------------------------------------
# Evaluación por mano
# ---------------------------------------------------------------------------
def assess_hand(hand, declared: Optional[DeclaredDefects] = None,
                detect: bool = True) -> HandEligibility:
    hid = hand.get('hand_id', '?')
    he = HandEligibility(hand_id=hid, declared=declared)
    players = list(hand.get('players') or [])
    by_pos = {}
    by_name = defaultdict(list)
    pos_reasons = []
    identity_reasons = []
    for p in players:
        pos = p.get('pos')
        name = p.get('name') or ''
        if not pos:
            pos_reasons.append('jugador sin posición: %r' % (name or p))
            continue
        if pos in by_pos:
            pos_reasons.append('posición duplicada: %s' % pos)
        by_pos[pos] = p
        if not name:
            identity_reasons.append('posición %s sin nombre' % pos)
        else:
            by_name[name].append(pos)
    for name, poss in by_name.items():
        if len(poss) > 1:
            identity_reasons.append(
                'nombre %r en varias posiciones: %s' % (name, poss))
    he.players_by_pos = by_pos
    he.positions_by_name = dict(by_name)
    total_actions, skipped_actions = _action_alignment(hand)
    active_no_pos = bool(declared and hid in declared.active_no_position_hands)
    duplicate_pos = any('duplicada' in r for r in pos_reasons)
    if duplicate_pos:
        pos_status = INVALID
    elif active_no_pos:
        pos_status = ABSENT
        pos_reasons.append(
            'posición ausente en jugador activo declarado por B1-E')
    elif skipped_actions:
        # Posición ausente no declarada: no se inventa la restricción, pero
        # se reporta que esas acciones no llegan a `extract_hand`.
        pos_status = AMBIGUOUS
        pos_reasons.append(
            '%d acciones sin posición de jugador; no se activan' %
            skipped_actions)
    else:
        pos_status = VALID
    he.fields[FIELD_POSITION] = FieldEligibility(
        FIELD_POSITION, pos_status, pos_reasons,
        canonical=pos_status == VALID,
        marginal_usable=pos_status != INVALID,
        conditioned_usable=pos_status == VALID,
        detail={'total_actions': total_actions,
                'skipped_actions': skipped_actions,
                'active_no_position_declared': active_no_pos})
    he.fields[FIELD_PLAYER_IDENTITY] = FieldEligibility(
        FIELD_PLAYER_IDENTITY,
        INVALID if identity_reasons else VALID,
        identity_reasons,
        canonical=not identity_reasons,
        marginal_usable=not identity_reasons,
        conditioned_usable=not identity_reasons)

    # Cartas por jugador.
    card_reasons = []
    known = 0
    for p in players:
        cards = p.get('cards') or ''
        if isinstance(cards, (list, tuple)):
            cards = ''.join(str(c) for c in cards)
        cards = str(cards)
        if not cards:
            continue
        if len(cards) not in (4, 5):
            card_reasons.append(
                'cartas mal formadas en %s: %r' % (p.get('pos'), cards))
        else:
            known += 1
    he.fields[FIELD_PLAYER_CARDS] = FieldEligibility(
        FIELD_PLAYER_CARDS,
        VALID if known and not card_reasons else
        (AMBIGUOUS if card_reasons else ABSENT),
        card_reasons,
        canonical=not card_reasons,
        marginal_usable=True,           # la mayoría de consumidores no las exige
        conditioned_usable=bool(known) and not card_reasons,
        detail={'players_with_cards': known,
                'players_without_cards': len(players) - known})

    # Acciones.
    issues, dependent = ([], [])
    if detect:
        issues, dependent = detect_action_issues(hand)
    if declared:
        issues, dependent = _merge_declared_actions(
            hand, declared, issues, dependent)
        if not declared.empty():
            # Solo se activan los defectos DECLARADOS. Un detector que
            # encuentra algo nuevo no se convierte en restricción: se
            # reporta como `ambiguous` para que alguien lo decida.
            declared_keys = set()
            d = declared.hard_sequence.get(hid)
            if d:
                street = d.get('street')
                idx = _resolve_declared_index(
                    hand, street, d.get('index'), d.get('evidence') or '')
                declared_keys.add((street, _seq_index_for_raw(
                    hand, street, idx)))
            code = declared.order_or_code.get(hid)
            if code:
                import re
                m = re.match(r'\s*(\w+)\.actions', code or '')
                street = m.group(1) if m else 'preflop'
                idx = _index_from_text(code)
                declared_keys.add((street, _seq_index_for_raw(
                    hand, street, idx)))
            for issue in issues:
                if issue.source == 'detected' and issue.severity == INVALID \
                        and issue.key not in declared_keys:
                    issue.severity = AMBIGUOUS
                    issue.taints_context = False
            active_roots = {i.key for i in issues
                            if i.severity == INVALID}
            dependent = [d for d in dependent
                         if d.root.key in active_roots]
    he.issues = issues
    he.dependent = dependent
    if issues:
        invalid = [i for i in issues if i.severity == INVALID]
        ambiguous = [i for i in issues if i.severity != INVALID]
        status = INVALID if invalid else AMBIGUOUS
        he.fields[FIELD_ACTIONS] = FieldEligibility(
            FIELD_ACTIONS, status,
            [i.detail for i in invalid] or [i.detail for i in ambiguous],
            canonical=False,
            marginal_usable=not invalid,
            conditioned_usable=not invalid,
            detail={'issues': issues})
        # El orden de acciones es un campo distinto: una acción imposible por
        # importe/contexto no invalida automáticamente el orden, y viceversa.
        order_invalid = [i for i in invalid if i.code in ORDER_CODES]
        order_ambiguous = [i for i in ambiguous if i.code in ORDER_CODES]
        order_reasons = [i.detail for i in order_invalid + order_ambiguous]
        if not order_reasons:
            order_reasons = ['otras acciones inválidas; el orden no se '
                             'considera afectado']
        order_status = INVALID if order_invalid else (
            AMBIGUOUS if order_ambiguous else VALID)
        he.fields[FIELD_ACTION_ORDER] = FieldEligibility(
            FIELD_ACTION_ORDER, order_status, order_reasons,
            canonical=order_status == VALID,
            marginal_usable=order_status != INVALID,
            conditioned_usable=order_status == VALID,
            detail={'order_issues': order_invalid + order_ambiguous})
    else:
        he.fields[FIELD_ACTIONS] = FieldEligibility(
            FIELD_ACTIONS, VALID, canonical=True,
            marginal_usable=True, conditioned_usable=True)
        he.fields[FIELD_ACTION_ORDER] = FieldEligibility(
            FIELD_ACTION_ORDER, VALID, canonical=True,
            marginal_usable=True, conditioned_usable=True)

    # Tablero.
    he.boards = assess_boards(hand, declared)
    board_reasons = []
    for st in ('flop', 'turn', 'river'):
        b = he.boards[st]
        board_reasons.extend(b.reasons)
    board_bad = any(he.boards[s].status == INVALID for s in
                    ('flop', 'turn', 'river'))
    board_absent = any(he.boards[s].status == ABSENT and _has_actions(hand, s)
                       for s in ('flop', 'turn', 'river'))
    he.fields[FIELD_BOARD] = FieldEligibility(
        FIELD_BOARD,
        INVALID if board_bad else (ABSENT if board_absent else VALID),
        board_reasons,
        canonical=not board_bad and not board_absent,
        marginal_usable=True,
        conditioned_usable=not board_bad and not board_absent,
        detail={'streets': he.boards})

    # Bote.
    pot_reasons = []
    final_pot = hand.get('final_pot')
    pot_status = VALID
    try:
        pot_val = float(final_pot)
    except (TypeError, ValueError):
        pot_val = None
    nada_marker = str(final_pot).strip().upper() == 'NADA'
    if final_pot is None:
        pot_status, pot_reasons = ABSENT, ['final_pot ausente']
    elif nada_marker:
        pot_status, pot_reasons = ABSENT, ['final_pot=NADA']
    elif pot_val is None:
        pot_status, pot_reasons = INVALID, ['final_pot no numérico']
    elif pot_val <= 0:
        pot_status, pot_reasons = INVALID, ['final_pot<=0']
    # `NADA` y un bote ausente/<=0 son marcas objetivas: siempre restringen
    # EV/ROI, estén o no en la lista declarada. Un conflicto interno
    # declarado pero fuera de la exclusión de bote aceptada (39) no se
    # activa: se reporta como no determinable.
    if declared and hid in declared.pot_nada:
        pot_status = ABSENT
        pot_reasons.append('NADA declarado por B1-E')
    elif declared and hid in declared.pot_unreliable:
        pot_status = DERIVED
        pot_reasons.append('bote no fiable declarado por B1-E')
    elif declared and hid in declared.pot_internal_conflict:
        pot_status = AMBIGUOUS
        pot_reasons.append(
            'conflicto interno declarado, fuera de la exclusión de bote; '
            'no se activa en sombra')
    he.fields[FIELD_POT] = FieldEligibility(
        FIELD_POT, pot_status, pot_reasons,
        canonical=(pot_status == VALID),
        marginal_usable=(pot_status == VALID),
        conditioned_usable=(pot_status == VALID))

    # Stacks.
    stack_reasons = []
    null_names = set()
    derived_stack = False
    for p in players:
        name = p.get('name') or ''
        raw = p.get('stack')
        if raw is None:
            stack_reasons.append('stack nulo en %s' % (p.get('pos') or name))
            if name:
                null_names.add(name)
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            stack_reasons.append('stack no numérico en %s' % p.get('pos'))
            continue
        if val < 0:
            stack_reasons.append('stack negativo en %s' % p.get('pos'))
    if declared:
        for name in declared.active_null_stack.get(hid, set()):
            null_names.add(name)
            stack_reasons.append('stack nulo declarado: %s' % name)
        rec = declared.recovered_values.get(hid) or {}
        if rec.get('stack_initial_candidate') is not None:
            derived_stack = True
            stack_reasons.append(
                'stack %s es derivado, no canónico: %s'
                % (rec.get('stack_initial_candidate'), rec.get('status')))
    he.null_stack_names = null_names
    stack_status = VALID
    if stack_reasons:
        if null_names or derived_stack:
            stack_status = DERIVED
        else:
            stack_status = INVALID
    he.fields[FIELD_STACK] = FieldEligibility(
        FIELD_STACK, stack_status, stack_reasons,
        canonical=(stack_status == VALID),
        marginal_usable=(stack_status == VALID),
        conditioned_usable=(stack_status == VALID),
        detail={'null_names': sorted(null_names)})

    # Allin.
    allin_reasons = []
    if declared and hid in declared.missing_allin:
        allin_reasons.append('marca allin ausente declarada por B1-E')
    he.fields[FIELD_ALLIN] = FieldEligibility(
        FIELD_ALLIN, ABSENT if allin_reasons else VALID, allin_reasons,
        canonical=not allin_reasons,
        marginal_usable=True,      # los modelos actuales no lo usan
        conditioned_usable=False)  # EV/SPR futuro sí lo necesita

    # Showdown / ganador / resultado económico.
    sd = hand.get('showdown') or {}
    has_sd = bool(sd)
    winners = []
    for v in sd.values():
        m = _SHOWDOWN_RE.search(str(v))
        if m:
            winners.append(m.group(1).strip())
    winner_reasons = []
    if not has_sd:
        # Sin showdown no hay W$SD; el ganador de fold (`winner: ['p4']`)
        # no se usa para esa estadística y no se inventa un nombre.
        winner_status = ABSENT
        winner_reasons.append(
            'sin showdown; ganador de fold no usado por W$SD')
    elif not winners:
        winner_status = AMBIGUOUS
        winner_reasons.append('showdown sin ganador legible')
    else:
        unknown = []
        for w in winners:
            if w in he.positions_by_name or w in he.players_by_pos:
                continue
            unknown.append(w)
        if unknown:
            winner_status = AMBIGUOUS
            winner_reasons.append(
                'ganador no identificable como nombre/posición: %r' % unknown)
        else:
            winner_status = VALID
    if declared and hid in declared.split_display_incomplete:
        winner_reasons.append('texto de split incompleto declarado por B1-E')
        winner_status = INVALID
    showdown_status = ABSENT if not has_sd else (
        INVALID if winner_status == INVALID else (
            AMBIGUOUS if winner_status == AMBIGUOUS else VALID))
    he.fields[FIELD_SHOWDOWN] = FieldEligibility(
        FIELD_SHOWDOWN, showdown_status,
        winner_reasons if showdown_status != VALID else [],
        canonical=showdown_status == VALID,
        marginal_usable=has_sd,       # WTSD puede usar un showdown incompleto
        conditioned_usable=showdown_status == VALID)
    he.fields[FIELD_WINNER] = FieldEligibility(
        FIELD_WINNER, winner_status, winner_reasons,
        canonical=winner_status == VALID,
        marginal_usable=winner_status == VALID,
        conditioned_usable=winner_status == VALID,
        detail={'winners': winners})

    # EV/ROI/pot odds se apoyan en el bote. El ganador es otro campo: su
    # ausencia limita W$SD/ROI de showdown, pero no invalida un bote de una
    # mano ganada sin showdown. Solo NADA / no fiable / conflicto restringen
    # el resultado económico.
    eco_bad = pot_status in (INVALID, ABSENT, DERIVED)
    he.fields[FIELD_ECONOMIC_RESULTS] = FieldEligibility(
        FIELD_ECONOMIC_RESULTS,
        INVALID if eco_bad else VALID,
        pot_reasons,
        canonical=not eco_bad,
        marginal_usable=not eco_bad,
        conditioned_usable=not eco_bad)

    # Cada evaluación conserva evidencia concreta y reproducible, además de
    # la razón de política. La evidencia apunta al campo fuente; no transforma
    # valores derivados ni rellena ausencias.
    actions_by_street = hand.get('streets') or {}
    player_evidence = [
        'players[%d]: pos=%r name=%r active=%r cards=%r stack=%r' %
        (i, p.get('pos'), p.get('name'), p.get('active'), p.get('cards'),
         p.get('stack'))
        for i, p in enumerate(players)
    ]
    issue_evidence = [
        '%s.actions[%d] %s %s %s [%s/%s; amount=%s/%s type=%r]' %
        (i.street, i.index, i.pos, i.action, _fmt_amount(i.amount),
         i.code, i.source, i.amount_value_status, i.amount_origin_status,
         i.amount_type)
        for i in he.issues
    ]
    evidence_by_field = {
        FIELD_ACTIONS: issue_evidence or [
            'streets.*.actions; sin incidencias detectadas'],
        FIELD_ACTION_ORDER: [
            x for x, i in zip(issue_evidence, he.issues)
            if i.code in ORDER_CODES] or [
                'secuencias streets.*.actions alineadas sin defecto de orden'],
        FIELD_POSITION: player_evidence or ['players: ausente'],
        FIELD_PLAYER_IDENTITY: player_evidence or ['players: ausente'],
        FIELD_PLAYER_CARDS: player_evidence or ['players.cards: ausente'],
        FIELD_BOARD: [
            '%s.board=%r; comunitarias.%s=%r' %
            (st, he.boards[st].raw, st, he.boards[st].comunitarias)
            for st in ('flop', 'turn', 'river')],
        FIELD_POT: ['final_pot=%r' % final_pot],
        FIELD_STACK: player_evidence,
        FIELD_ALLIN: [
            'players all-in markers=%r; declaradas=%s' %
            ([{k: p.get(k) for k in ('pos', 'name', 'allin', 'all_in')
              if k in p} for p in players],
             'B1-E' if declared and hid in declared.missing_allin
             else 'ninguna')],
        FIELD_SHOWDOWN: ['showdown=%r' % (hand.get('showdown') or {})],
        FIELD_WINNER: ['showdown=%r; winner_raw=%r; parseados=%r' %
                       (hand.get('showdown') or {}, hand.get('winner'),
                        winners)],
        FIELD_ECONOMIC_RESULTS: ['final_pot=%r; estado_bote=%s' %
                                 (final_pot, pot_status)],
    }
    for name, field_result in he.fields.items():
        field_result.evidence = evidence_by_field.get(
            name, ['evidencia raw no disponible'])
    return he


def _merge_declared_actions(hand, declared, issues, dependent):
    """Añade los defectos declarados que el detector no haya encontrado."""
    hid = hand.get('hand_id')
    out = list(issues)
    deps = list(dependent)
    d = declared.hard_sequence.get(hid)
    if d:
        street = d.get('street')
        raw_idx = _resolve_declared_index(
            hand, street, d.get('index'), d.get('evidence') or '')
        seq_i = _seq_index_for_raw(hand, street, raw_idx)
        existing = next((i for i in out
                         if i.street == street and i.index == raw_idx), None)
        if existing is None:
            pos, act, amt = _raw_action(hand, street, raw_idx)
            issue = ActionIssue(
                street, raw_idx, seq_i, pos, act, amt,
                _declared_code(d, act),
                d.get('evidence') or 'secuencia declarada',
                severity=INVALID, source='declared',
                taints_context=_declared_taints(d, act),
                **_amount_issue_fields(hand, street, raw_idx))
            out.append(issue)
            if issue.taints_context:
                deps.extend(_dependent_after(hand, street, seq_i, issue))
        else:
            # El detector ya lo había visto (a veces como ambiguo). El
            # inventario lo declara imposible: se eleva a invalid y se
            # conserva la evidencia declarada.
            existing.severity = INVALID
            existing.source = 'declared+detected'
            existing.taints_context = _declared_taints(d, existing.action)
            existing.detail = (existing.detail + ' | '
                               + (d.get('evidence') or '')).strip(' |')
            if existing.taints_context:
                deps.extend(_dependent_after(
                    hand, street, existing.seq_index, existing))
    code = declared.order_or_code.get(hid)
    if code:
        existing = next((i for i in out if i.code == 'subida_sin_incremento'
                         or i.code == 'ordeno_codigo'), None)
        if existing is None:
            # H_0832: limp corto codificado como b. No es una acción
            # imposible; es una categoría que hay que leer como limp.
            import re
            m = re.match(r'\s*(\w+)\.actions', code or '')
            street = m.group(1) if m else 'preflop'
            raw_idx = _index_from_text(code)
            seq_i = _seq_index_for_raw(hand, street, raw_idx)
            pos, act, amt = _raw_action(hand, street, raw_idx)
            out.append(ActionIssue(
                street, raw_idx, seq_i, pos, act, amt,
                'ordeno_codigo', code, severity='code_ambiguous',
                source='declared', taints_context=False,
                **_amount_issue_fields(hand, street, raw_idx)))
        elif existing is not None:
            existing.source = 'declared+detected'
            if code and code not in existing.detail:
                existing.detail = (existing.detail + ' | ' + code).strip(' |')
    # Deduplicar dependencias: el detector y el declarado pueden señalar la
    # misma acción posterior.
    seen = set()
    unique = []
    for d in deps:
        key = (d.street, d.seq_index)
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)
    return out, unique


_SHOWDOWN_RE = __import__('re').compile(r'\(([^)]+)\)')


def _declared_code(d, act):
    text = (d.get('evidence') or '').lower()
    if 'importe cero' in text or 'b 0.0' in text:
        return 'apuesta_cero'
    if 'check' in text and 'no puede' in text:
        return 'preflop_no_resuelto'
    if 'check' in text:
        return 'check_enfrentando_apuesta'
    if 'all-in' in text or 'apuesta viva' in text:
        return 'call_insuficiente'
    if 'se retiran' in text or 'sin apuesta viva' in text:
        return 'call_su_propia_apuesta'
    if 'ya retirado' in text:
        return 'accion_tras_fold'
    if 'nueva apuesta' in text:
        return 'accion_sin_nueva_apuesta'
    return 'hard_sequence'


def _declared_taints(d, act):
    text = (d.get('evidence') or '').lower()
    if 'retir' in text:
        # Acción de un jugador ya retirado: no cambia el contexto posterior.
        return False
    if act == 'f':
        return False
    return True


def _resolve_declared_index(hand, street, raw_idx, evidence):
    """El índice declarado puede estar desplazado; la evidencia manda.

    H_0327 declara `index: 2`, pero la acción descrita (`MP b 0.0`) está en
    el índice 1. Se resuelve por posición + acción + importe, no por fe.
    """
    import re
    m = re.search(r'([A-Z]{2,3})\s+([fxcbrp])\s+([0-9]+(?:\.[0-9]+)?)',
                  evidence or '')
    if not m:
        return raw_idx
    want_pos, want_act, want_amt = m.group(1), m.group(2), float(m.group(3))
    raw = ((hand.get('streets') or {}).get(street) or {}).get('actions') or []
    candidates = []
    if isinstance(raw_idx, int) and 0 <= raw_idx < len(raw):
        candidates.append(raw_idx)
    candidates.extend(i for i in range(len(raw)) if i not in candidates)
    for i in candidates:
        pos, act, amt = _raw_action(hand, street, i)
        if pos == want_pos and act == want_act \
                and abs(amt - want_amt) <= 1e-6:
            return i
    return raw_idx


def _seq_index_for_raw(hand, street, raw_idx):
    for seq_i, raw_i, _p, _a, _m in _indexed_seq(hand, street):
        if raw_i == raw_idx:
            return seq_i
    return raw_idx if raw_idx is not None else -1


def _raw_action(hand, street, raw_idx):
    raw = ((hand.get('streets') or {}).get(street) or {}).get('actions') or []
    if raw_idx is None or raw_idx < 0 or raw_idx >= len(raw):
        return '', '', None
    a = raw[raw_idx]
    if isinstance(a, dict):
        amt = classify_amount(a).value
        return a.get('pos') or '', a.get('action') or '', amt
    try:
        pos, act = a[0], a[1]
    except (IndexError, TypeError):
        return '', '', None
    amount = a[2] if len(a) > 2 else None
    return pos, act, classify_amount(amount).value


def _index_from_text(text):
    import re
    m = re.search(r'actions\[(\d+)\]', text or '')
    return int(m.group(1)) if m else -1


def _dependent_after(hand, street, seq_i, issue):
    """Acciones posteriores que heredan el contexto de una acción inválida."""
    deps = []
    if street == 'preflop':
        # Toda la secuencia preflop posterior y todas las calles posteriores
        # heredan el estado del bote/iniciativa.
        for st in ('preflop', 'flop', 'turn', 'river'):
            for si, ri, pos, act, amt in _indexed_seq(hand, st):
                if st == 'preflop' and si <= seq_i:
                    continue
                deps.append(DependentAction(
                    st, ri, si, pos, act, amt, issue,
                    'same_street' if st == 'preflop' else 'later_streets',
                    _amount_evidence_at(hand, st, ri)['value_status'],
                    _amount_evidence_at(hand, st, ri)['origin_status']))
        return deps
    for si, ri, pos, act, amt in _indexed_seq(hand, street):
        if si > seq_i:
            deps.append(DependentAction(
                street, ri, si, pos, act, amt, issue, 'same_street',
                _amount_evidence_at(hand, street, ri)['value_status'],
                _amount_evidence_at(hand, street, ri)['origin_status']))
    # La iniciativa postflop (último bettor) puede cambiar las calles
    # posteriores; se declara como dependencia de alcance amplio para
    # `TransitionStats`, aunque Oracle/postflop no la consuman.
    later = ('flop', 'turn', 'river')
    if street in later:
        for st in later[later.index(street) + 1:]:
            for si, ri, pos, act, amt in _indexed_seq(hand, st):
                deps.append(DependentAction(
                    st, ri, si, pos, act, amt, issue, 'later_streets',
                    _amount_evidence_at(hand, st, ri)['value_status'],
                    _amount_evidence_at(hand, st, ri)['origin_status']))
    return deps


# ---------------------------------------------------------------------------
# Alineación con observaciones y eventos
# ---------------------------------------------------------------------------
def iter_observation_contexts(hand, obs=None):
    """[(Observation, street, seq_index, raw_index, pos, act, amount)].

    `extract_hand` usa `_seq`; se reconstruye exactamente el mismo filtro
    (`p` fuera; posición sin jugador fuera) para alinear observación y acción
    sin duplicar la semántica del extractor.
    """
    obs = extract_hand(hand) if obs is None else list(obs)
    names = _street_names(hand)
    ctx = []
    for street in ('preflop', 'flop', 'turn', 'river'):
        for seq_i, raw_i, pos, act, amt in _indexed_seq(hand, street):
            if act == 'p':
                continue
            if pos not in names:
                continue
            ctx.append((street, seq_i, raw_i, pos, act, amt))
    if len(ctx) != len(obs):
        raise RuntimeError(
            'alineación rota en %s: %d observaciones, %d acciones'
            % (hand.get('hand_id'), len(obs), len(ctx)))
    return list(zip(obs, ctx))


def preflop_event_contexts(hand):
    """[(PreflopEvent, seq_index, step)] en el orden de `preflop_events`."""
    seq = [(_p, _a, _m, False)
           for _si, _ri, _p, _a, _m in _indexed_seq(hand, 'preflop')]
    steps = list(walk_preflop(seq, legacy=True))
    events = preflop_events(hand)
    out = []
    decided = set()
    step_by_pos = []
    for step in steps:
        cls = step.classification
        if cls.status == 'non_decision':
            continue
        pos = step.raw.pos
        if pos in decided:
            continue
        decided.add(pos)
        step_by_pos.append((step.raw.index, step))
    for ev, (idx, step) in zip(events, step_by_pos):
        out.append((ev, idx, step))
    return out


def _preflop_taint(he, seq_i):
    """Primera acción preflop inválida anterior a `seq_i`, si existe."""
    for issue in he.issues:
        if issue.street != 'preflop':
            continue
        if issue.severity != INVALID or not issue.taints_context:
            continue
        if issue.seq_index < seq_i:
            return issue
    for d in he.dependent:
        if d.street == 'preflop' and d.seq_index == seq_i:
            return d.root
    return None


def _declared_limp_context(he, issue):
    """True solo si B1-E declaró el limp corto de esta acción concreta.

    Algunas evidencias citan el limp como contexto de otra secuencia (p. ej.
    H_0834: `BTN b 1.0` antes del raise duplicado). No se activa cualquier
    hallazgo del detector por pertenecer a una mano declarada.
    """
    import re
    if 'declared' in (issue.source or ''):
        return True
    declared = he.declared
    if declared is None:
        return False
    evidence = []
    hard = declared.hard_sequence.get(he.hand_id)
    if hard:
        evidence.append(hard.get('evidence') or '')
    code = declared.order_or_code.get(he.hand_id)
    if code:
        evidence.append(code)
    for text in evidence:
        for match in re.finditer(
                r'([A-Z]{2,3})\s+([fxcbrp])\s+'
                r'([0-9]+(?:\.[0-9]+)?)', text):
            pos, action, amount = match.group(1), match.group(2), float(
                match.group(3))
            if (pos == issue.pos and action == issue.action == 'b'
                    and issue.amount is not None
                    and abs(amount - issue.amount) <= TOL):
                return True
    return False


# ---------------------------------------------------------------------------
# Elegibilidad de observaciones y eventos
# ---------------------------------------------------------------------------
def observation_eligibility(he: HandEligibility, obs, street, seq_i,
                            consumer: str) -> ObservationEligibility:
    name = obs.player or ''
    amount_meta = (getattr(obs, 'amount_evidence', None)
                   or classify_amount({
                       'amount': getattr(obs, 'amount', None)}).as_dict())
    amount_usable = amount_meta.get('value_status') not in (
        AMOUNT_ABSENT, AMOUNT_INVALID)
    reasons = []
    direct = he.issue_at(street, seq_i)
    dep = he.dependent_at(street, seq_i)
    root = direct or (dep.root if dep else None)
    restricted = False
    if direct is not None and direct.severity == INVALID:
        restricted = True
        reasons.append('%s: %s' % (direct.code, direct.detail))
    elif dep is not None:
        # Una dependencia de alcance `later_streets` solo restringe a los
        # consumidores que usan iniciativa/bote; Oracle y postflop usan
        # `facing`/textura y no la heredan. La excepción es un defecto
        # preflop: cambia el iniciador y el pot_type de todas las calles.
        if (dep.scope == 'same_street'
                or dep.root.street == 'preflop'
                or consumer in (CONSUMER_PREFLOP_STATS,
                                CONSUMER_POSTFLOP_STATS,
                                CONSUMER_SHOWDOWN, CONSUMER_ECONOMIC)):
            restricted = True
            reasons.append('depende de %s: %s'
                           % (dep.root.code, dep.root.detail))
    if (direct is not None and direct.severity != INVALID
            and consumer in (CONSUMER_PROFILE_RANGE,
                             CONSUMER_PREFLOP_STATS)
            and direct.code == 'subida_sin_incremento'):
        # Limp corto: se puede usar como limp, no como subida.
        reasons.append('categoría corregida a limp: %s' % direct.detail)
    if (direct is not None and direct.severity == 'code_ambiguous'
            and direct.code == 'subida_sin_incremento'
            and street == 'preflop'
            and _declared_limp_context(he, direct)
            and consumer in (CONSUMER_ORACLE_MARGINAL,
                             CONSUMER_ORACLE_GRANULAR)):
        # La celda preflop del Oracle agrupa por acción cruda (`b`); un limp
        # corto grabado como b no se puede contar como subida. Se restringe
        # solo esa observación; la mano y el resto de sus calles siguen.
        restricted = True
        reasons.append(
            'limp corto codificado como b; la celda Oracle b no lo '
            'distingue de una subida')

    cards_required = consumer in (CONSUMER_PROFILE_RANGE,
                                  CONSUMER_POSTFLOP_RANGE)
    cards_present = bool(obs.hand_known and obs.cards)
    if cards_required and not cards_present:
        restricted = True
        reasons.append('requiere cartas conocidas y no las hay')

    if (consumer == CONSUMER_PROFILE_RANGE and street == 'preflop'
            and obs.action in ('b', 'r') and not amount_usable):
        restricted = True
        reasons.append('categoría de rango preflop requiere importe; valor '
                       'ausente o inválido')
    elif not amount_usable:
        reasons.append('importe %s; no se usa como cero' %
                       amount_meta.get('value_status'))

    # Tablero.
    board = he.boards.get(street)
    board_warning = False
    if consumer == CONSUMER_ORACLE_GRANULAR and street != 'preflop':
        if board is None or not board.granular_usable:
            restricted = True
            reasons.append('textura granular sin tablero válido')
        if board is not None and board.contradiction:
            board_warning = True
            reasons.append('contradicción streets/comunitarias; '
                           'se usa streets')
    elif consumer == CONSUMER_POSTFLOP_RANGE:
        if street != 'preflop':
            if board is None or not board.bucket_usable:
                restricted = True
                reasons.append('bucket postflop sin tablero válido')
            if board is not None and board.contradiction:
                board_warning = True
                reasons.append('contradicción streets/comunitarias; '
                               'se usa streets')
    elif consumer == CONSUMER_ORACLE_MARGINAL:
        if board is not None and board.contradiction:
            board_warning = True
            reasons.append('contradicción streets/comunitarias; '
                           'el marginal usa streets')
    # El consumidor marginal no exige tablero ausente: no se restringe.

    label_warning = name in he.null_stack_names
    if label_warning and consumer in (CONSUMER_POSTFLOP_RANGE,
                                      CONSUMER_ORACLE_MARGINAL,
                                      CONSUMER_ORACLE_GRANULAR,
                                      CONSUMER_PROFILE_RANGE):
        reasons.append('etiqueta de perfil con stack nulo; no canónica')

    not_applicable = False
    if consumer == CONSUMER_POSTFLOP_RANGE and street == 'preflop':
        not_applicable = True
    if consumer == CONSUMER_ORACLE_GRANULAR and street == 'preflop':
        # El Oracle granular materializa preflop con textura '-', pero la
        # política granular se define para postflop. No se cuenta como
        # restricción: simplemente no es una observación condicionada.
        not_applicable = True
    return ObservationEligibility(
        hand_id=he.hand_id, street=street, seq_index=seq_i,
        player=name, action=obs.action, consumer=consumer,
        usable=not restricted, restricted=restricted, reasons=reasons,
        direct=direct is not None and direct.severity == INVALID,
        dependent=dep is not None,
        root_code=root.code if root else None,
        board_warning=board_warning, label_warning=label_warning,
        cards_required=cards_required, cards_present=cards_present,
        not_applicable=not_applicable,
        amount_value_status=amount_meta.get('value_status'),
        amount_origin_status=amount_meta.get('origin_status'),
        amount_type=amount_meta.get('amount_type'),
        action_inferred=bool(amount_meta.get('action_inferred')),
        amount_usable=amount_usable)


def preflop_event_eligibility(he: HandEligibility, event, seq_i,
                              consumer: str) -> ObservationEligibility:
    direct = he.issue_at('preflop', seq_i)
    taint = _preflop_taint(he, seq_i)
    restricted = False
    reasons = []
    if direct is not None and direct.severity == INVALID:
        restricted = True
        reasons.append('%s: %s' % (direct.code, direct.detail))
    elif taint is not None:
        restricted = True
        reasons.append('depende de %s: %s' % (taint.code, taint.detail))
    if (direct is not None and direct.code == 'subida_sin_incremento'
            and consumer in (CONSUMER_PROFILE_RANGE,
                             CONSUMER_PREFLOP_STATS)):
        reasons.append('categoría corregida a limp: %s' % direct.detail)
    cards_required = consumer == CONSUMER_PROFILE_RANGE
    cards_present = bool(event.hand_known and event.cards)
    if cards_required and not cards_present:
        restricted = True
        reasons.append('requiere cartas conocidas y no las hay')
    amount_meta = event.amount_evidence.as_dict()
    amount_usable = amount_meta['value_status'] not in (
        AMOUNT_ABSENT, AMOUNT_INVALID)
    if (consumer in (CONSUMER_PROFILE_RANGE, CONSUMER_PREFLOP_STATS)
            and event.category == 'unknown' and not amount_usable):
        restricted = True
        reasons.append('acción preflop sin categoría por importe ausente o '
                       'inválido')
    elif not amount_usable:
        reasons.append('importe %s; no se usa como cero' %
                       amount_meta['value_status'])
    label_warning = event.player in he.null_stack_names
    if label_warning and consumer == CONSUMER_PROFILE_RANGE:
        reasons.append('etiqueta de perfil con stack nulo; no canónica')
    evidence_root = (direct if direct is not None and direct.severity == INVALID
                     else taint or direct)
    return ObservationEligibility(
        hand_id=he.hand_id, street='preflop', seq_index=seq_i,
        player=event.player, action=event.category, consumer=consumer,
        usable=not restricted, restricted=restricted, reasons=reasons,
        direct=direct is not None and direct.severity == INVALID,
        dependent=taint is not None,
        root_code=evidence_root.code if evidence_root else None,
        label_warning=label_warning, cards_required=cards_required,
        cards_present=cards_present,
        amount_value_status=amount_meta['value_status'],
        amount_origin_status=amount_meta['origin_status'],
        amount_type=amount_meta['amount_type'],
        action_inferred=amount_meta['action_inferred'],
        amount_usable=amount_usable)


# ---------------------------------------------------------------------------
# Recuentos en sombra
# ---------------------------------------------------------------------------
def _new_counter():
    return Counter()


def field_summary(hands, declared=None) -> dict:
    """Conteo de estados por campo: valid/invalid/absent/derived/ambiguous."""
    out = {}
    for hand in hands:
        he = assess_hand(hand, declared)
        for name, f in he.fields.items():
            out.setdefault(name, Counter())[f.status] += 1
    return {k: dict(v) for k, v in out.items()}


def stats_counts(hands, declared=None) -> dict:
    """Conteos de `TransitionStats` antes/después, por estadística.

    Reproduce la lógica de `motor/stats.py` sin reconstruir el modelo: cada
    oportunidad/acción se cuenta una vez y se marca si la observación que la
    origina pasaría la política.
    """
    from .stats import MONEY_CATS, RAISE_CATS

    before = Counter()
    after = Counter()
    for hand in hands:
        he = assess_hand(hand, declared)
        ev_ctx = preflop_event_contexts(hand)
        ev_elig = {}
        last_aggressor = None
        last_aggressor_ok = True
        for ev, seq_i, step in ev_ctx:
            if not ev.player:
                continue
            e = preflop_event_eligibility(
                he, ev, seq_i, CONSUMER_PREFLOP_STATS)
            ev_elig[ev.pos] = e
            before['vpip_opp'] += 1
            before['pfr_opp'] += 1
            if e.usable:
                after['vpip_opp'] += 1
                after['pfr_opp'] += 1
            if ev.category in MONEY_CATS:
                before['vpip_act'] += 1
                if e.usable:
                    after['vpip_act'] += 1
            if ev.category in RAISE_CATS:
                before['pfr_act'] += 1
                if e.usable:
                    after['pfr_act'] += 1
                last_aggressor = ev.pos
                last_aggressor_ok = e.usable
            if ev.category in ('call_open', '3bet', 'squeeze',
                               'fold_vs_open'):
                before['b3_opp'] += 1
                if e.usable:
                    after['b3_opp'] += 1
            if ev.category in ('3bet', 'squeeze'):
                before['b3_act'] += 1
                if e.usable:
                    after['b3_act'] += 1
            if ev.category in ('call_3bet', '4bet', 'fold_vs_3bet'):
                before['b4_opp'] += 1
                if e.usable:
                    after['b4_opp'] += 1
            if ev.category == '4bet':
                before['b4_act'] += 1
                if e.usable:
                    after['b4_act'] += 1

        # Showdown (WTSD / W$SD).
        has_sd = bool(hand.get('showdown'))
        revealed = {p.get('name') for p in (hand.get('players') or [])
                    if p.get('cards')}
        winners = set()
        for v in (hand.get('showdown') or {}).values():
            m = _SHOWDOWN_RE.search(str(v))
            if m:
                winners.add(m.group(1).strip())
        # WTSD solo necesita que exista showdown. W$SD necesita, además,
        # que el ganador sea legible: un texto de split incompleto no debe
        # borrar la llegada al showdown (WTSD) ni el denominador de W$SD.
        sd_ok = has_sd
        winner_ok = he.field(FIELD_WINNER).status == VALID
        for ev, seq_i, step in ev_ctx:
            if ev.category == 'fold' or ev.player in HERO_NAMES:
                continue
            if not has_sd or not ev.player:
                continue
            e = ev_elig.get(ev.pos)
            ok = bool(e and e.usable and sd_ok)
            before['wtsd_opp'] += 1
            if ok:
                after['wtsd_opp'] += 1
            if ev.player in revealed:
                before['wtsd_act'] += 1
                before['wsd_opp'] += 1
                if ok:
                    after['wtsd_act'] += 1
                    after['wsd_opp'] += 1
                if ev.player in winners:
                    before['wsd_act'] += 1
                    if ok and winner_ok:
                        after['wsd_act'] += 1

        # Postflop: iniciativa y defensas.
        initiator = last_aggressor
        initiator_ok = last_aggressor_ok
        contexts = iter_observation_contexts(hand)
        for street in ('flop', 'turn', 'river'):
            street_ctx = [(o, c) for o, c in contexts if c[0] == street]
            if not street_ctx:
                continue
            first_bettor = None
            first_bettor_ok = True
            last_bet_ctx = None
            for o, (st, seq_i, raw_i, pos, act, amt) in street_ctx:
                e = observation_eligibility(
                    he, o, st, seq_i, CONSUMER_POSTFLOP_STATS)
                ok = e.usable
                if act in ('b', 'r'):
                    last_bet_ctx = (o, (st, seq_i, raw_i, pos, act, amt), e)
                if first_bettor is None:
                    if pos == initiator:
                        stat = {'flop': 'cbet', 'turn': 'bar',
                                'river': 'rb'}[street]
                        before[stat + '_opp'] += 1
                        if ok and initiator_ok:
                            after[stat + '_opp'] += 1
                    if act in ('b', 'r'):
                        first_bettor = pos
                        first_bettor_ok = ok and initiator_ok
                        if pos == initiator:
                            stat = {'flop': 'cbet', 'turn': 'bar',
                                    'river': 'rb'}[street]
                            before[stat + '_act'] += 1
                            if first_bettor_ok:
                                after[stat + '_act'] += 1
                elif act != 'x':
                    if street == 'flop' and first_bettor == initiator:
                        if act == 'f':
                            before['f2cb_opp'] += 1
                            before['f2cb_act'] += 1
                            if ok and first_bettor_ok and initiator_ok:
                                after['f2cb_opp'] += 1
                                after['f2cb_act'] += 1
                        elif act == 'c':
                            before['c2cb_opp'] += 1
                            before['c2cb_act'] += 1
                            if ok and first_bettor_ok and initiator_ok:
                                after['c2cb_opp'] += 1
                                after['c2cb_act'] += 1
                        elif act == 'r':
                            before['r2cb_opp'] += 1
                            before['r2cb_act'] += 1
                            if ok and first_bettor_ok and initiator_ok:
                                after['r2cb_opp'] += 1
                                after['r2cb_act'] += 1
                    elif street != 'flop' and first_bettor == initiator:
                        before['f2bar_opp'] += 1
                        if ok and first_bettor_ok and initiator_ok:
                            after['f2bar_opp'] += 1
                        if act == 'f':
                            before['f2bar_act'] += 1
                            if ok and first_bettor_ok and initiator_ok:
                                after['f2bar_act'] += 1
            if last_bet_ctx is not None:
                o, c, e = last_bet_ctx
                initiator = c[3]
                initiator_ok = e.usable
    stats = {}
    for k in sorted(set(before) | set(after)):
        stats[k] = {'before': before[k], 'after': after[k],
                    'restricted': before[k] - after[k]}
    return stats


def oracle_breakdown(hands, declared=None) -> dict:
    """Desglose individual de las observaciones Oracle de las manos con
    acciones restringidas. No descarta la mano: clasifica cada observación.
    """
    per_hand = {}
    for hand in hands:
        hid = hand.get('hand_id')
        if declared and hid not in declared.hard_sequence \
                and hid not in declared.order_or_code:
            continue
        he = assess_hand(hand, declared)
        rows = []
        for obs, (street, seq_i, raw_i, pos, act, amt) in \
                iter_observation_contexts(hand):
            direct = he.issue_at(street, seq_i)
            dep = he.dependent_at(street, seq_i)
            marginal = observation_eligibility(
                he, obs, street, seq_i, CONSUMER_ORACLE_MARGINAL)
            granular = observation_eligibility(
                he, obs, street, seq_i, CONSUMER_ORACLE_GRANULAR)
            if direct is not None and direct.severity == INVALID:
                cls = 'directa'
            elif dep is not None and dep.scope == 'same_street':
                cls = 'dependiente'
            elif (direct is not None and direct.code ==
                  'subida_sin_incremento' and street == 'preflop'):
                if _declared_limp_context(he, direct):
                    # La celda Oracle `b` no distingue limp corto de subida.
                    cls = 'codigo_restringido'
                else:
                    # Detector no declarado: se mantiene en sombra y no se
                    # cuenta como una restricción efectiva.
                    cls = 'ambigua_no_activada'
            else:
                cls = 'independiente'
            root = direct or (dep.root if dep else None)
            reasons = list(marginal.reasons)
            reasons.extend(r for r in granular.reasons if r not in reasons)
            rows.append({
                'street': street, 'pos': pos, 'action': act,
                'amount': amt, 'facing': obs.facing,
                'amount_value_status': marginal.amount_value_status,
                'amount_origin_status': marginal.amount_origin_status,
                'amount_type': marginal.amount_type,
                'action_inferred': marginal.action_inferred,
                'amount_usable': marginal.amount_usable,
                'texture': obs.texture_class,
                'known': obs.hand_known, 'class': cls,
                'code': (direct or (dep.root if dep else None)).code
                if (direct or dep) else None,
                'direct': marginal.direct,
                'dependent': marginal.dependent,
                'dependency_scope': dep.scope if dep else None,
                'marginal_usable': marginal.usable,
                'granular_usable': granular.usable,
                'reason': root.detail if root else '',
                'evidence': '%s.actions[%d] %s %s %s amount=%s/%s' %
                            (street, raw_i, pos, act, _fmt_amount(amt),
                             marginal.amount_value_status,
                             marginal.amount_origin_status),
                'consumer_reasons': reasons,
            })
        per_hand[hid] = {
            'total': len(rows),
            'directas': sum(1 for r in rows if r['class'] == 'directa'),
            'dependientes': sum(1 for r in rows
                                if r['class'] == 'dependiente'),
            'codigo_restringido': sum(
                1 for r in rows if r['class'] == 'codigo_restringido'),
            'ambiguas_no_activadas': sum(
                1 for r in rows if r['class'] == 'ambigua_no_activada'),
            'independientes': sum(1 for r in rows
                                  if r['class'] == 'independiente'),
            'rows': rows,
        }
    return per_hand


def collect_counts(hands, labels=None, declared=None) -> dict:
    """Cuenta el antes/después sombra por consumidor y categoría.

    No modifica manos, modelos ni etiquetas. `después` = observaciones que
    pasarían la política; no se reconstruye ningún modelo.
    """
    declared = declared if declared is not None else load_declared()
    if labels is None:
        labels = {}
    out = {
        'hands': len(hands),
        'fields': Counter(),
        'consumers': {},
        'oracle_by_street': {},
        'oracle_by_facing': {},
        'oracle_by_texture': {},
        'preflop_by_category': {},
        'postflop_by_facing': {},
        'stats': {},
        'undetermined': [],
        'hand_issues': {},
    }
    oracle_marg = Counter()
    oracle_gran = Counter()
    oracle_total = 0
    he_by_id = {}
    for hand in hands:
        he = assess_hand(hand, declared)
        he_by_id[he.hand_id] = he
        out['hand_issues'][he.hand_id] = [
            {'street': i.street, 'index': i.index, 'code': i.code,
             'severity': i.severity, 'source': i.source,
             'detail': i.detail, 'amount': i.amount,
             'amount_value_status': i.amount_value_status,
             'amount_origin_status': i.amount_origin_status,
             'amount_type': i.amount_type,
             'action_inferred': i.action_inferred}
            for i in he.issues
        ]
        for name, f in he.fields.items():
            out['fields'][(name, f.status)] += 1
            out.setdefault('field_summary', {}).setdefault(
                name, Counter())[f.status] += 1
        for issue in he.issues:
            if issue.severity != INVALID:
                out['undetermined'].append({
                    'hand_id': he.hand_id, 'street': issue.street,
                    'index': issue.index, 'code': issue.code,
                    'detail': issue.detail, 'source': issue.source,
                })
        obs = extract_hand(hand)
        for o, (street, seq_i, raw_i, pos, act, amt) in \
                iter_observation_contexts(hand, obs):
            oracle_total += 1
            m = observation_eligibility(
                he, o, street, seq_i, CONSUMER_ORACLE_MARGINAL)
            g = observation_eligibility(
                he, o, street, seq_i, CONSUMER_ORACLE_GRANULAR)
            oracle_marg['before'] += 1
            oracle_marg['after'] += 1 if m.usable else 0
            oracle_marg['restricted'] += 1 if m.restricted else 0
            if m.restricted:
                if any('limp corto' in r for r in m.reasons):
                    oracle_marg['restricted_code'] += 1
                elif m.direct:
                    oracle_marg['restricted_direct'] += 1
                elif m.dependent:
                    oracle_marg['restricted_dependent'] += 1
                if street == 'preflop':
                    oracle_marg['restricted_preflop'] += 1
                else:
                    oracle_marg['restricted_postflop'] += 1
            oracle_marg['warning'] += 1 if m.board_warning else 0
            oracle_marg['label_warning'] += 1 if m.label_warning else 0
            if street != 'preflop':
                oracle_gran['before'] += 1
                oracle_gran['after'] += 1 if g.usable else 0
                oracle_gran['restricted'] += 1 if g.restricted else 0
                if g.restricted:
                    if any('tablero' in r.lower() for r in g.reasons):
                        oracle_gran['restricted_board'] += 1
                    else:
                        oracle_gran['restricted_action'] += 1
                oracle_gran['warning'] += 1 if g.board_warning else 0
            out['oracle_by_street'].setdefault(
                street, Counter())['before'] += 1
            out['oracle_by_street'][street]['after'] += 1 if m.usable else 0
            out['oracle_by_street'][street]['restricted'] += \
                1 if m.restricted else 0
            out['oracle_by_facing'].setdefault(
                o.facing, Counter())['before'] += 1
            out['oracle_by_facing'][o.facing]['after'] += \
                1 if m.usable else 0
            out['oracle_by_facing'][o.facing]['restricted'] += \
                1 if m.restricted else 0
            if street != 'preflop':
                tex = o.texture_class or '-'
                out['oracle_by_texture'].setdefault(
                    tex, Counter())['before'] += 1
                out['oracle_by_texture'][tex]['after'] += \
                    1 if g.usable else 0
                out['oracle_by_texture'][tex]['restricted'] += \
                    1 if g.restricted else 0

    out['consumers'][CONSUMER_ORACLE_MARGINAL] = dict(oracle_marg)
    out['consumers'][CONSUMER_ORACLE_GRANULAR] = dict(oracle_gran)
    out['oracle_total'] = oracle_total

    # ProfileRangeModel: eventos preflop con cartas.
    prof_before = prof_after = 0
    prof_by = Counter()
    for hand in hands:
        he = he_by_id[hand.get('hand_id')]
        for ev, seq_i, step in preflop_event_contexts(hand):
            if not ev.hand_known or not ev.cards:
                continue
            prof_before += 1
            e = preflop_event_eligibility(
                he, ev, seq_i, CONSUMER_PROFILE_RANGE)
            if e.usable:
                prof_after += 1
            prof_by[ev.denom or '?'] += 1
            if not e.usable:
                prof_by[(ev.denom or '?', 'restricted')] += 1
    out['consumers'][CONSUMER_PROFILE_RANGE] = {
        'before': prof_before, 'after': prof_after,
        'restricted': prof_before - prof_after,
        'by_denom': {str(k): v for k, v in prof_by.items()},
    }

    # Preflop stats: todos los eventos (con o sin cartas).
    pre_before = pre_after = 0
    pre_by = Counter()
    for hand in hands:
        he = he_by_id[hand.get('hand_id')]
        for ev, seq_i, step in preflop_event_contexts(hand):
            if not ev.player:
                continue
            pre_before += 1
            e = preflop_event_eligibility(
                he, ev, seq_i, CONSUMER_PREFLOP_STATS)
            if e.usable:
                pre_after += 1
            pre_by[ev.category] += 1
            if not e.usable:
                pre_by[(ev.category, 'restricted')] += 1
    out['consumers'][CONSUMER_PREFLOP_STATS] = {
        'before': pre_before, 'after': pre_after,
        'restricted': pre_before - pre_after,
        'by_category': {str(k): v for k, v in pre_by.items()},
    }

    # PostflopRangeModel: observaciones postflop con cartas y board válido.
    post_before = post_after = 0
    post_known = post_board_absent = post_contradiction = 0
    for hand in hands:
        he = he_by_id[hand.get('hand_id')]
        for o, (street, seq_i, raw_i, pos, act, amt) in \
                iter_observation_contexts(hand):
            if not o.hand_known or not o.cards or street == 'preflop':
                continue
            post_known += 1
            b = he.boards.get(street)
            if b is None or not b.bucket_usable:
                post_board_absent += 1
                continue
            if b.contradiction:
                post_contradiction += 1
            post_before += 1
            e = observation_eligibility(
                he, o, street, seq_i, CONSUMER_POSTFLOP_RANGE)
            if e.usable:
                post_after += 1
    out['consumers'][CONSUMER_POSTFLOP_RANGE] = {
        'before': post_before, 'after': post_after,
        'restricted': post_before - post_after,
        'known_with_cards': post_known,
        'dropped_by_absent_board': post_board_absent,
        'contradiction_warning': post_contradiction,
    }

    # Showdown / stack / economic: conteos por mano y jugador.
    sd_before = sd_after = 0
    stack_before = stack_after = 0
    econ_before = econ_after = 0
    null_stack_hands = []
    declared_null_hands = []
    players_with_numeric = set()
    players_with_null = set()
    for hand in hands:
        he = he_by_id[hand.get('hand_id')]
        hid = hand.get('hand_id')
        if hand.get('showdown'):
            sd_before += 1
            if he.field(FIELD_WINNER).status == VALID:
                sd_after += 1
        for p in hand.get('players') or []:
            name = p.get('name')
            if not name:
                continue
            stack_before += 1
            try:
                float(p.get('stack'))
                stack_after += 1
                players_with_numeric.add(name)
            except (TypeError, ValueError):
                players_with_null.add(name)
        if he.null_stack_names:
            null_stack_hands.append(hid)
        if declared and declared.active_null_stack.get(hid):
            declared_null_hands.append(hid)
        econ_before += 1
        if he.field(FIELD_ECONOMIC_RESULTS).status == VALID:
            econ_after += 1
    out['consumers'][CONSUMER_SHOWDOWN] = {
        'before': sd_before, 'after': sd_after,
        'restricted': sd_before - sd_after,
        'hands_with_showdown': sd_before,
    }
    out['consumers'][CONSUMER_STACK] = {
        'before': stack_before, 'after': stack_after,
        'restricted': stack_before - stack_after,
        'null_stack_hands': len(null_stack_hands),
        'declared_active_null_hands': len(declared_null_hands),
        'players_with_numeric_stack': len(players_with_numeric),
        'players_with_null_stack': len(players_with_null),
    }
    out['consumers'][CONSUMER_ECONOMIC] = {
        'before': econ_before, 'after': econ_after,
        'restricted': econ_before - econ_after,
        'pot_hands_restricted': econ_before - econ_after,
    }
    out['stats'] = stats_counts(hands, declared)
    out['field_summary'] = {k: dict(v)
                            for k, v in out.get('field_summary', {}).items()}
    out['oracle_breakdown'] = oracle_breakdown(hands, declared)
    return out


# ---------------------------------------------------------------------------
# Sombra conectada a build_models
# ---------------------------------------------------------------------------
class EligibilityShadow:
    """Hook opcional de `build_models()`: registra, no filtra.

    `build_models(eligibility_shadow=EligibilityShadow())` construye los
    mismos modelos y además guarda el informe. Sin el hook, el camino es
    idéntico al actual.
    """

    def __init__(self, declared: Optional[DeclaredDefects] = None):
        self.declared = declared if declared is not None else load_declared()
        self.report = None
        self.inputs = None
        self.received_models = None

    def record_build(self, hands, labels, profs, range_model, oracle,
                     postflop_model):
        self.inputs = {'hands': len(hands), 'labels': len(labels)}
        self.received_models = (range_model, oracle, postflop_model)
        self.report = collect_counts(hands, labels, self.declared)
        return self.report


# ---------------------------------------------------------------------------
# Serialización / hashes para la prueba de no-cambio
# ---------------------------------------------------------------------------
_VOLATILE_META = {'built_at', 'generated_at', 'created_at',
                  'code_commit', 'arbol_sucio'}


def _stable_payload(obj):
    """Quita metadatos de procedencia volátiles antes de hashear.

    `to_json()` sella `built_at` con la hora de la llamada; eso no es parte
    del modelo. Se conservan `alpha`, `hands_input`, `hands_used`, tablas,
    etiquetas y omega.
    """
    if isinstance(obj, dict):
        return {k: _stable_payload(v) for k, v in obj.items()
                if k not in _VOLATILE_META}
    if isinstance(obj, (list, tuple)):
        return [_stable_payload(v) for v in obj]
    return obj


def model_fingerprint(range_model, oracle, postflop_model) -> dict:
    """Hash estable de los tres modelos, para demostrar que la sombra no
    los toca. Excluye metadatos de procedencia volátiles (`built_at`)."""
    import hashlib

    def h(obj):
        raw = json.dumps(_stable_payload(obj), sort_keys=True,
                         ensure_ascii=False, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    return {
        'profile_range': h(range_model.to_json()),
        'oracle': h(oracle.to_dict()),
        'postflop_range': h(postflop_model.to_json()),
        'oracle_inside_postflop': h(postflop_model._oracle.to_dict())
        if getattr(postflop_model, '_oracle', None) is not None else None,
    }


def shadow_report(hands=None, labels=None, declared=None) -> dict:
    """Informe completo listo para el documento/CLI."""
    hands = load_hands(reliable_only=True) if hands is None else hands
    declared = declared if declared is not None else load_declared()
    counts = collect_counts(hands, labels or {}, declared)
    try:
        data = build_behavior(hands, labels=labels)
    except Exception:
        data = {}
    counts['behavior'] = {
        'observaciones': data.get('observaciones'),
        'celdas_granular': len(data.get('granular') or {}),
        'celdas_por_facing': len(data.get('por_facing') or {}),
    }
    return counts
