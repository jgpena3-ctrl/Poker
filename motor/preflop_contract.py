"""preflop_contract.py — contrato único de interpretación preflop.

Por qué existe
--------------
Entrenamiento y serving no estaban mirando la misma secuencia. `learn.py`
clasificaba una acción con el estado anterior (raises, limps, callers,
importe), pero `asistente_live._preflop_spot` decidía por el ÚLTIMO carácter:
`r` -> 3bet, `b` -> open, `c` -> call_open. Eso confunde un `r` que abre el
bote con un `r` que resube, un `b` de 1BB (limpe corto) con una apertura y un
`c` después de limpes con un call contra un open.

Este módulo es la única implementación nueva de esa interpretación. No se
activa todavía en las recomendaciones: el camino live sigue usando sus
funciones antiguas y este contrato se ejecuta en sombra para comparar.

Reglas que NO se negocian
-------------------------
- La categoría sale del estado de la secuencia y del importe, no del carácter
  aislado de la última acción.
- Una `p` es una POSTA, no una decisión. La ciega del BB puede venir como `b`
  o como `p`, y se reconoce por la marca `blind` o por la estructura (BB, sin
  acción voluntaria anterior).
- Un `b`/`r` de importe <= BB sin subida previa es un LIMPE CORTO: categoría
  `limp`, y NO sube el contador de subidas. En el estado estricto también
  cuenta como limpe para el jugador siguiente.
- Si falta el importe de una acción agresiva, la posición en un check, o la
  secuencia está rota, se devuelve `unresolved`. No se inventa una categoría.
- El estado se conserva en cada clasificación (`PreflopContext`) para que cada
  consumidor pueda decidir qué tabla/categoría consultar. Una categoría sin
  tabla no se convierte en otra: se declara ausente en el consumidor.

Modo legado
-----------
`legacy=True` reproduce el estado que usaba `learn.preflop_events` antes de
este contrato, incluida su deuda conocida: un limpe corto `b` se clasifica
`limp` pero se cuenta como subida para el jugador siguiente, y un `x` de
cualquier posición se lee como `bb_check`. Ese modo existe solo para que el
entrenamiento actual no cambie de comportamiento y para poder comparar contra
la referencia. El camino estricto (`legacy=False`) es el que se usará cuando
se autorice la activación.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

from .action_amount import (
    ABSENT as AMOUNT_ABSENT,
    AmountEvidence,
    classify_amount,
)

BB_NOMINAL = 1.0
TOL = 1e-9

# Vocabulario de categorías. Las categorías 5bet+ existen en el contrato
# aunque `ProfileRangeModel` todavía no tenga celdas para ellas: esa ausencia
# la declara el consumidor, no se disfraza de `4bet`.
CATEGORY_DENOM: Dict[str, str] = {
    'fold': 'no_raise',
    'limp': 'no_raise',
    'open': 'no_raise',
    'call_limp': 'no_raise',
    'rol': 'no_raise',
    'bb_check': 'no_raise',
    'call_open': 'facing_open',
    '3bet': 'facing_open',
    'squeeze': 'facing_open',
    'fold_vs_open': 'facing_open',
    'call_3bet': 'facing_3bet',
    'call_4bet': 'facing_3bet',
    'call_5bet_plus': 'facing_3bet',
    '4bet': 'facing_3bet',
    '5bet': 'facing_3bet',
    '6bet_plus': 'facing_3bet',
    'fold_vs_3bet': 'facing_3bet',
    'fold_vs_4bet': 'facing_3bet',
    'fold_vs_5bet_plus': 'facing_3bet',
}
DENOM_ORDER = ('no_raise', 'facing_open', 'facing_3bet')
CATEGORY_ORDER = (
    'open', 'limp', 'rol', 'call_limp', 'call_open', '3bet', 'squeeze',
    '4bet', '5bet', '6bet_plus', 'call_3bet', 'call_4bet', 'call_5bet_plus',
    'fold', 'fold_vs_open', 'fold_vs_3bet', 'fold_vs_4bet',
    'fold_vs_5bet_plus', 'bb_check',
)

# La clasificación del entrenamiento no tenía 5bet/call_4bet/fold_vs_4bet.
# Para comparar contra esa referencia sin convertir en silencio, se expone el
# mapeo explícito. El consumidor elige: `category` es la lectura exacta,
# `training_category` es la etiqueta histórica.
TRAINING_CATEGORY = {
    '5bet': '4bet',
    '6bet_plus': '4bet',
    'call_4bet': 'call_3bet',
    'call_5bet_plus': 'call_3bet',
    'fold_vs_4bet': 'fold_vs_3bet',
    'fold_vs_5bet_plus': 'fold_vs_3bet',
}

UNRESOLVED_CATEGORIES = ('unknown', 'check_non_bb', 'check_bb_facing_raise',
                         'check_pos_unknown')

# Categorías que `ProfileRangeModel.CAT_TABLE` sabe consultar hoy. Las que
# quedan fuera NO se convierten: se declaran `no_range` (un fold/check no tiene
# rango que muestrear) o `no_table` (5bet+, donde el modelo todavía no tiene
# celda). La cobertura de tablas concreta la sigue declarando
# `preflop.classify_missing_table`.
RANGE_MODEL_CATEGORIES = frozenset({
    'open', 'rol', 'call_open', '3bet', 'squeeze', '4bet', 'call_3bet',
    'limp', 'call_limp',
})
NO_RANGE_CATEGORIES = frozenset({
    'fold', 'fold_vs_open', 'fold_vs_3bet', 'fold_vs_4bet',
    'fold_vs_5bet_plus', 'bb_check',
})


@dataclass(frozen=True)
class PreflopAction:
    """Una acción cruda ya normalizada, sin interpretarla."""
    index: int
    pos: str
    action: str
    amount: Optional[float]
    is_blind: bool
    raw_amount: Any = None
    amount_evidence: AmountEvidence = field(
        default_factory=lambda: classify_amount({}))


@dataclass(frozen=True)
class PreflopContext:
    """Estado preflop ANTES de una acción (o después, en `walk_preflop`)."""
    bb: float
    current_level: float
    raises_before: int
    limps_before: int
    callers_before: int
    aggressors: Tuple[str, ...] = ()
    aggressor_amounts: Tuple[float, ...] = ()
    voluntary_actions: int = 0
    bb_posted: bool = False
    blind_posts: Tuple[str, ...] = ()
    players_acted: Tuple[str, ...] = ()
    tainted_reason: Optional[str] = None

    @classmethod
    def initial(cls, bb: float = BB_NOMINAL) -> 'PreflopContext':
        # La ciega del BB es una regla del juego, no una invención del parser.
        # Si la secuencia no la trae, el nivel nominal sigue siendo BB.
        return cls(bb=float(bb), current_level=float(bb),
                   raises_before=0, limps_before=0, callers_before=0)

    @property
    def last_aggressor(self) -> str:
        return self.aggressors[-1] if self.aggressors else ''

    @property
    def last_aggressor_amount(self) -> float:
        return self.aggressor_amounts[-1] if self.aggressor_amounts else 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            'bb': self.bb,
            'current_level': self.current_level,
            'raises_before': self.raises_before,
            'limps_before': self.limps_before,
            'callers_before': self.callers_before,
            'aggressors': list(self.aggressors),
            'aggressor_amounts': list(self.aggressor_amounts),
            'voluntary_actions': self.voluntary_actions,
            'bb_posted': self.bb_posted,
            'blind_posts': list(self.blind_posts),
            'players_acted': list(self.players_acted),
            'tainted_reason': self.tainted_reason,
        }


@dataclass(frozen=True)
class PreflopClassification:
    """Lectura contextual de UNA acción preflop."""
    raw: PreflopAction
    category: str
    denom: Optional[str]
    status: str                 # resolved | unresolved | non_decision
    reason: Optional[str]
    context: PreflopContext
    short_limp: bool = False
    raise_number: Optional[int] = None

    @property
    def resolved(self) -> bool:
        return self.status == 'resolved'

    @property
    def training_category(self) -> str:
        return TRAINING_CATEGORY.get(self.category, self.category)

    @property
    def training_denom(self) -> Optional[str]:
        return CATEGORY_DENOM.get(self.training_category)

    @property
    def bet_label(self) -> Optional[str]:
        """Etiqueta exacta de profundidad: 1=open, 2=3bet, 3=4bet, ..."""
        if self.raise_number is None:
            return None
        if self.raise_number == 1:
            return 'open'
        if self.raise_number == 2:
            return '3bet'
        if self.raise_number == 3:
            return '4bet'
        if self.raise_number == 4:
            return '5bet'
        return '6bet_plus'

    @property
    def range_query_status(self) -> str:
        """¿Esta categoría se puede consultar en el modelo de rangos?

        - `available`: hay celda de entrenamiento para la categoría.
        - `no_range`: un fold/check no define un rango que muestrear.
        - `no_table`: la categoría es válida, pero el modelo no tiene celda
          (p. ej. 5bet+). No se mapea a 4bet.
        - `unresolved`: la acción no se pudo leer.
        """
        if self.status != 'resolved':
            return 'unresolved'
        if self.category in RANGE_MODEL_CATEGORIES:
            return 'available'
        if self.category in NO_RANGE_CATEGORIES:
            return 'no_range'
        return 'no_table'

    @property
    def range_query(self) -> Optional[Tuple[str, str]]:
        if self.range_query_status != 'available':
            return None
        return self.denom or '', self.category

    def as_dict(self) -> Dict[str, Any]:
        return {
            'index': self.raw.index,
            'pos': self.raw.pos,
            'action': self.raw.action,
            'amount': self.raw.amount,
            'amount_evidence': self.raw.amount_evidence.as_dict(),
            'category': self.category,
            'training_category': self.training_category,
            'denom': self.denom,
            'status': self.status,
            'reason': self.reason,
            'short_limp': self.short_limp,
            'raise_number': self.raise_number,
            'bet_label': self.bet_label,
            'range_query': list(self.range_query) if self.range_query else None,
            'range_query_status': self.range_query_status,
            'context': self.context.as_dict(),
        }


@dataclass(frozen=True)
class PreflopStep:
    """Acción + estado anterior + estado posterior."""
    raw: PreflopAction
    classification: PreflopClassification
    after: PreflopContext


@dataclass(frozen=True)
class PreflopTablePlan:
    """Consulta de tablas del héroe derivada del contrato estricto.

    No es una decisión: es qué tablas habría que consultar. `PROFILE` no se
    usa aquí; el consumidor sigue eligiendo el perfil.
    """
    raises_before: int
    limps_before: int
    callers_before: int
    vs_pos: str
    vs_amount: float
    table_raise: Optional[str]
    table_call: Optional[str]
    label: str
    status: str
    reason: Optional[str]
    context: PreflopContext

    def as_dict(self) -> Dict[str, Any]:
        return {
            'raises_before': self.raises_before,
            'limps_before': self.limps_before,
            'callers_before': self.callers_before,
            'vs_pos': self.vs_pos,
            'vs_amount': self.vs_amount,
            'table_raise': self.table_raise,
            'table_call': self.table_call,
            'label': self.label,
            'status': self.status,
            'reason': self.reason,
            'context': self.context.as_dict(),
        }


# ---------------------------------------------------------------------------
# Normalización y estado
# ---------------------------------------------------------------------------

def actions_of(hand: Optional[Dict[str, Any]]) -> List[Any]:
    """Acciones preflop crudas de una mano (o [])."""
    if not isinstance(hand, dict):
        return []
    streets = hand.get('streets') or {}
    preflop = streets.get('preflop') or {}
    return list(preflop.get('actions') or [])


def _coerce_source(source: Any) -> List[Any]:
    if isinstance(source, dict) and 'streets' in source:
        return actions_of(source)
    if source is None:
        return []
    return list(source)


def normalize_actions(source: Any, *, keep_invalid: bool = False) -> List[PreflopAction]:
    """Normaliza dicts del recorder o tuplas `(pos, action, amount, blind)`.

    `amount` queda en `None` cuando falta o no es numérico. `amount_evidence`
    distingue ausencia, valor inválido, cero conocido y valor positivo, además
    de la procedencia declarada. Ningún modo convierte la ausencia a 0.0.

    `keep_invalid=True` conserva acciones sin posición o sin código para que
    el camino estricto las declare `unresolved`. El camino legado las descarta,
    igual que `learn._preflop_sequence`, para no mover los eventos históricos.
    """
    out: List[PreflopAction] = []
    for i, a in enumerate(_coerce_source(source)):
        if isinstance(a, dict):
            pos = a.get('pos') or ''
            act = a.get('action') or ''
            raw_amount = a.get('amount')
            is_blind = bool(a.get('blind') or a.get('is_blind'))
            amount_evidence = classify_amount(a)
        else:
            try:
                pos, act = a[0], a[1]
            except (IndexError, TypeError):
                if not keep_invalid:
                    continue
                pos, act, raw_amount = '', '', None
                is_blind = False
                amount_evidence = classify_amount({})
            else:
                raw_amount = a[2] if len(a) > 2 else None
                is_blind = bool(a[3]) if len(a) > 3 else False
                amount_evidence = classify_amount(raw_amount)
        if (not pos or not act) and not keep_invalid:
            continue
        amount = amount_evidence.value
        out.append(PreflopAction(index=i, pos=str(pos or ''), action=str(act or ''),
                                 amount=amount, is_blind=is_blind,
                                 raw_amount=raw_amount,
                                 amount_evidence=amount_evidence))
    return out


def is_blind_post(action: PreflopAction, voluntary_before: bool) -> bool:
    """La ciega del BB, con la misma prioridad que `learn._es_ciega_bb`.

    1. Marca explícita del recorder.
    2. BB + `b`/`p` + ninguna acción voluntaria anterior.

    `amount` e `i` NO deciden: una ciega real puede tener cualquier importe y
    no depende de su posición en la lista.
    """
    if action.is_blind:
        return True
    return (action.pos == 'BB' and action.action in ('b', 'p')
            and not voluntary_before)


def _legacy_amount(action: PreflopAction) -> Optional[float]:
    """Valor numérico disponible; no rellena una ausencia con cero."""
    return None if action.amount is None else float(action.amount)


def _classify(context: PreflopContext, action: PreflopAction,
              *, is_blind: bool = False,
              legacy: bool = False) -> PreflopClassification:
    """Clasifica una acción contra el estado anterior."""
    repeated_bb_post = (not legacy and not context.voluntary_actions
                        and action.pos == 'BB'
                        and action.pos in context.blind_posts)
    if (repeated_bb_post and action.action == 'p'):
        return PreflopClassification(
            raw=action, category='unknown', denom=None, status='unresolved',
            reason='posta_repetida', context=context)
    if (repeated_bb_post and action.action == 'b'
            and (action.amount is None
                 or action.amount <= context.current_level + TOL)):
        reason = ('importe_ausente' if action.amount is None else
                  'subida_sin_incremento')
        return PreflopClassification(
            raw=action, category='unknown', denom=None, status='unresolved',
            reason=reason, context=context)

    if is_blind or action.action == 'p':
        category = 'blind' if is_blind else 'post'
        return PreflopClassification(
            raw=action, category=category, denom=None,
            status='non_decision', reason=None, context=context)

    if context.tainted_reason and not legacy:
        return PreflopClassification(
            raw=action, category='unknown', denom=None, status='unresolved',
            reason='secuencia_ambigua:%s' % context.tainted_reason,
            context=context)

    act = action.action
    amount = _legacy_amount(action) if legacy else action.amount

    if not act and not legacy:
        return PreflopClassification(
            raw=action, category='unknown', denom=None, status='unresolved',
            reason='accion_ausente', context=context)

    if act == 'x':
        if legacy:
            return PreflopClassification(
                raw=action, category='bb_check', denom='no_raise',
                status='resolved', reason=None, context=context)
        if not action.pos:
            return PreflopClassification(
                raw=action, category='check_pos_unknown', denom=None,
                status='unresolved', reason='check_sin_posicion',
                context=context)
        if action.pos != 'BB':
            return PreflopClassification(
                raw=action, category='check_non_bb', denom=None,
                status='unresolved', reason='check_fuera_de_BB',
                context=context)
        if context.raises_before > 0:
            return PreflopClassification(
                raw=action, category='check_bb_facing_raise', denom=None,
                status='unresolved', reason='BB_no_puede_pasar_con_subida',
                context=context)
        return PreflopClassification(
            raw=action, category='bb_check', denom='no_raise',
            status='resolved', reason=None, context=context)

    if not legacy and not action.pos:
        # Sin posición no se puede atribuir la acción ni elegir tabla. No se
        # supone una posición por el orden de la secuencia.
        return PreflopClassification(
            raw=action, category='unknown', denom=None, status='unresolved',
            reason='pos_ausente', context=context)

    if act == 'f':
        if context.raises_before == 0:
            category = 'fold'
        elif context.raises_before == 1:
            category = 'fold_vs_open'
        elif context.raises_before == 2:
            category = 'fold_vs_3bet'
        elif context.raises_before == 3:
            category = 'fold_vs_4bet'
        else:
            category = 'fold_vs_5bet_plus'
        return PreflopClassification(
            raw=action, category=category,
            denom=CATEGORY_DENOM[category], status='resolved',
            reason=None, context=context)

    if act == 'c':
        if context.raises_before == 0:
            category = 'limp' if context.limps_before == 0 else 'call_limp'
        elif context.raises_before == 1:
            category = 'call_open'
        elif context.raises_before == 2:
            category = 'call_3bet'
        elif context.raises_before == 3:
            category = 'call_4bet'
        else:
            category = 'call_5bet_plus'
        return PreflopClassification(
            raw=action, category=category,
            denom=CATEGORY_DENOM[category], status='resolved',
            reason=None, context=context)

    if act in ('b', 'r'):
        if amount is None:
            reason = ('importe_ausente'
                      if action.amount_evidence.value_status == AMOUNT_ABSENT
                      else 'importe_invalido')
            return PreflopClassification(
                raw=action, category='unknown', denom=None,
                status='unresolved', reason=reason,
                context=context)
        if not legacy and amount <= TOL:
            return PreflopClassification(
                raw=action, category='unknown', denom=None,
                status='unresolved', reason='importe_cero',
                context=context)

        # Limpe corto: <= BB sin subida previa. No se mira el carácter para
        # decidir: un `r` de 1BB también es un limpe corto si nadie subió.
        if context.raises_before == 0 and amount <= context.bb + TOL:
            return PreflopClassification(
                raw=action, category='limp', denom='no_raise',
                status='resolved', reason=None, context=context,
                short_limp=True, raise_number=1)

        if context.raises_before == 0:
            category = 'open' if context.limps_before == 0 else 'rol'
            return PreflopClassification(
                raw=action, category=category, denom='no_raise',
                status='resolved', reason=None, context=context,
                raise_number=1)

        # Una subida tiene que subir el nivel vigente. Si no, el dato no dice
        # qué pasó; no se convierte en 3bet/4bet por el carácter.
        if not legacy and amount <= context.current_level + TOL:
            return PreflopClassification(
                raw=action, category='unknown', denom=None,
                status='unresolved', reason='subida_sin_incremento',
                context=context)

        raise_number = context.raises_before + 1
        if context.raises_before == 1:
            category = 'squeeze' if context.callers_before >= 1 else '3bet'
        elif context.raises_before == 2:
            category = '4bet'
        elif context.raises_before == 3:
            category = '5bet'
        else:
            category = '6bet_plus'
        return PreflopClassification(
            raw=action, category=category,
            denom=CATEGORY_DENOM[category], status='resolved',
            reason=None, context=context, raise_number=raise_number)

    return PreflopClassification(
        raw=action, category='unknown', denom=None, status='unresolved',
        reason='accion_desconocida', context=context)


def _advance(context: PreflopContext, action: PreflopAction,
             classification: PreflopClassification,
             *, is_blind: bool, legacy: bool) -> PreflopContext:
    """Estado posterior. `legacy=True` reproduce los contadores antiguos."""
    amount = action.amount

    if (not legacy and classification.reason == 'posta_repetida'):
        return replace(context, tainted_reason='posta_repetida')

    if is_blind or action.action == 'p':
        bb_posted = context.bb_posted or (
            action.pos == 'BB' and (is_blind or action.action == 'p'))
        posts = context.blind_posts
        if is_blind or action.action == 'p':
            posts = posts + ((action.pos or '?'),)
        # La ciega real es el nivel vigente, aunque venga con un importe
        # anómalo. En modo legado no hay validación de subida, pero el
        # contexto debe conservar lo que el dato dice.
        level = (context.current_level if amount is None else
                 max(context.current_level, amount))
        return replace(context, current_level=level,
                       bb_posted=bb_posted, blind_posts=posts)

    if legacy and classification.status == 'resolved':
        raises = context.raises_before
        limps = context.limps_before
        callers = context.callers_before
        voluntary = context.voluntary_actions
        aggressors = context.aggressors
        aggressor_amounts = context.aggressor_amounts
        if action.action in ('b', 'r'):
            # Deuda histórica deliberada: el limpe corto `b` se clasifica
            # `limp` pero aquí cuenta como subida, exactamente como hacía
            # `preflop_events` antes de este contrato.
            raises += 1
            voluntary += 1
            aggressors = aggressors + ((action.pos or '?'),)
            aggressor_amounts = aggressor_amounts + (amount,)
        elif action.action == 'c':
            if raises == 0:
                limps += 1
            else:
                callers += 1
            voluntary += 1
        return replace(
            context,
            current_level=(context.current_level if amount is None else
                           max(context.current_level, amount)),
            raises_before=raises, limps_before=limps,
            callers_before=callers, voluntary_actions=voluntary,
            aggressors=aggressors, aggressor_amounts=aggressor_amounts,
            players_acted=context.players_acted + ((action.pos or '?'),))

    raises = context.raises_before
    limps = context.limps_before
    callers = context.callers_before
    voluntary = context.voluntary_actions
    aggressors = context.aggressors
    aggressor_amounts = context.aggressor_amounts
    tainted = context.tainted_reason
    level = context.current_level

    if classification.status != 'resolved':
        # La acción no se pudo leer. El estado posterior ya no es fiable; se
        # marca para que las acciones siguientes no hereden una categoría
        # inventada. Un check inválido no mueve dinero, así que no contamina
        # el estado: solo la acción agresiva/desconocida lo hace.
        if classification.reason in ('subida_sin_incremento',
                                     'importe_ausente', 'importe_invalido',
                                     'importe_cero', 'posta_repetida',
                                     'accion_desconocida',
                                     'accion_ausente',
                                     'pos_ausente'):
            tainted = classification.reason
            if action.action in ('b', 'r', 'c'):
                voluntary += 1
    elif action.action in ('b', 'r'):
        voluntary += 1
        if classification.short_limp:
            # Un limpe corto es un limpe para el que viene detrás.
            limps += 1
            level = max(level, amount)
        else:
            raises += 1
            level = amount
            aggressors = aggressors + ((action.pos or '?'),)
            aggressor_amounts = aggressor_amounts + (amount,)
            # Los callers de una subida anterior ya no enfrentan la nueva.
            callers = 0
    elif action.action == 'c':
        voluntary += 1
        if raises == 0:
            limps += 1
        else:
            callers += 1

    return replace(
        context, current_level=level, raises_before=raises,
        limps_before=limps, callers_before=callers,
        voluntary_actions=voluntary, aggressors=aggressors,
        aggressor_amounts=aggressor_amounts, players_acted=(
            context.players_acted + ((action.pos or '?'),)),
        tainted_reason=tainted)


def walk_preflop(source: Any, *, bb: float = BB_NOMINAL,
                 legacy: bool = False) -> Tuple[PreflopStep, ...]:
    """Recorre la secuencia y devuelve cada acción con su estado anterior.

    `source` puede ser una mano, una lista de dicts del recorder o la lista de
    tuplas de `learn._preflop_sequence`. No modifica la entrada.
    """
    context = PreflopContext.initial(bb)
    steps: List[PreflopStep] = []
    for action in normalize_actions(source, keep_invalid=not legacy):
        repeated_bb_post = (not legacy and not context.voluntary_actions
                            and action.pos == 'BB'
                            and action.pos in context.blind_posts
                            and (action.action == 'p'
                                 or (action.action == 'b'
                                     and (action.amount is None
                                          or action.amount <=
                                          context.current_level + TOL))))
        blind = (False if repeated_bb_post else
                 is_blind_post(action, bool(context.voluntary_actions)))
        cls = _classify(context, action, is_blind=blind, legacy=legacy)
        after = _advance(context, action, cls, is_blind=blind, legacy=legacy)
        steps.append(PreflopStep(raw=action, classification=cls, after=after))
        context = after
    return tuple(steps)


def final_context(source: Any, *, bb: float = BB_NOMINAL,
                  legacy: bool = False) -> PreflopContext:
    steps = walk_preflop(source, bb=bb, legacy=legacy)
    if steps:
        return steps[-1].after
    return PreflopContext.initial(bb)


def classify_action(action: str, amount: Optional[float],
                    raises_before: int = 0, limps_before: int = 0,
                    callers: int = 0, bb: float = BB_NOMINAL,
                    *, pos: str = '', current_level: Optional[float] = None,
                    bb_posted: bool = False,
                    legacy: bool = False) -> PreflopClassification:
    """Atajo para clasificar una acción con un contexto ya resumido.

    Sirve para fixtures y para el adaptador del clasificador histórico. Para
    secuencias completas, usar `walk_preflop`, que además actualiza el estado.
    """
    level = bb if current_level is None else current_level
    context = PreflopContext(
        bb=float(bb), current_level=float(level),
        raises_before=int(raises_before), limps_before=int(limps_before),
        callers_before=int(callers), bb_posted=bool(bb_posted))
    amount_evidence = classify_amount({'amount': amount})
    raw = PreflopAction(index=0, pos=pos or '', action=action,
                        amount=amount_evidence.value, is_blind=False,
                        raw_amount=amount,
                        amount_evidence=amount_evidence)
    return _classify(context, raw, legacy=legacy)


def first_decision(source: Any, pos: str, *, bb: float = BB_NOMINAL,
                   legacy: bool = False) -> PreflopClassification:
    """Primera decisión voluntaria del jugador en `pos` (incluye fold)."""
    steps = walk_preflop(source, bb=bb, legacy=legacy)
    for step in steps:
        if (step.raw.pos == pos
                and step.classification.status != 'non_decision'):
            return step.classification
    context = steps[-1].after if steps else PreflopContext.initial(bb)
    raw = PreflopAction(index=-1, pos=pos or '', action='', amount=None,
                        is_blind=False, amount_evidence=classify_amount({}))
    return PreflopClassification(
        raw=raw, category='unknown', denom=None, status='unresolved',
        reason='sin_decision', context=context)


def last_decision(source: Any, pos: str, *, bb: float = BB_NOMINAL,
                  legacy: bool = False) -> PreflopClassification:
    """Última decisión voluntaria del jugador en `pos` (para diagnóstico)."""
    steps = walk_preflop(source, bb=bb, legacy=legacy)
    found = None
    for step in steps:
        if (step.raw.pos == pos
                and step.classification.status != 'non_decision'):
            found = step.classification
    if found is not None:
        return found
    context = steps[-1].after if steps else PreflopContext.initial(bb)
    raw = PreflopAction(index=-1, pos=pos or '', action='', amount=None,
                        is_blind=False, amount_evidence=classify_amount({}))
    return PreflopClassification(
        raw=raw, category='unknown', denom=None, status='unresolved',
        reason='sin_decision', context=context)


def table_plan(source: Any, hero_pos: str = '', *,
               bb: float = BB_NOMINAL) -> PreflopTablePlan:
    """Plan de tablas del héroe a partir del estado estricto (shadow)."""
    context = final_context(source, bb=bb, legacy=False)
    raises = context.raises_before
    limps = context.limps_before
    vs_pos = context.last_aggressor if raises else ''
    vs_amount = context.last_aggressor_amount if raises else 0.0

    if context.tainted_reason:
        return PreflopTablePlan(
            raises, limps, context.callers_before, vs_pos, vs_amount,
            None, None, 'secuencia ambigua', 'unresolved',
            context.tainted_reason, context)
    if raises == 0:
        if limps == 0:
            return PreflopTablePlan(
                raises, limps, context.callers_before, '', 0.0,
                'OR', None, 'apertura (sin raise previo)', 'resolved',
                None, context)
        return PreflopTablePlan(
            raises, limps, context.callers_before, '', 0.0,
            'ROL', None, 'vs limp', 'resolved', None, context)
    if raises == 1:
        return PreflopTablePlan(
            raises, limps, context.callers_before, vs_pos, vs_amount,
            '3B', 'Call_OR', 'vs apertura', 'resolved', None, context)
    if raises == 2:
        return PreflopTablePlan(
            raises, limps, context.callers_before, vs_pos, vs_amount,
            '4B', 'Call_3B', 'vs 3-bet', 'resolved', None, context)
    if raises == 3:
        return PreflopTablePlan(
            raises, limps, context.callers_before, vs_pos, vs_amount,
            '5B', 'Call_4B', 'vs 4-bet', 'resolved', None, context)
    if raises == 4:
        return PreflopTablePlan(
            raises, limps, context.callers_before, vs_pos, vs_amount,
            None, 'Call_5B', 'vs 5-bet', 'resolved', None, context)
    return PreflopTablePlan(
        raises, limps, context.callers_before, vs_pos, vs_amount,
        None, None, 'vs multi-raise', 'unsupported',
        'sin_tabla_para_%d_raises' % raises, context)


def legacy_training_category(action: str, amount: Optional[float],
                             raises_before: int = 0,
                             limps_before: int = 0,
                             callers: int = 0,
                             bb: float = BB_NOMINAL) -> Tuple[str, str]:
    """Adaptador exacto de `learn.classify_first_action`.

    Devuelve `(categoría, denominador)` y lanza `ValueError` ante una acción
    desconocida, igual que la función histórica. No se usa en serving.
    """
    cls = classify_action(action, amount, raises_before, limps_before,
                          callers, bb, legacy=True)
    # `classify_first_action` clasifica DECISIONES. Una posta `p` (o una
    # acción desconocida) no es una decisión y la función histórica lanzaba.
    # `preflop_events` salta las postas antes de llamar aquí.
    if cls.status == 'non_decision' or cls.reason == 'accion_desconocida':
        raise ValueError('acción preflop desconocida: %r' % (action,))
    return cls.category, cls.denom or CATEGORY_DENOM.get(cls.category, '')


# ---------------------------------------------------------------------------
# Registro de sombra
# ---------------------------------------------------------------------------

class ShadowPreflopLog:
    """Registro de comparación viejo-vs-nuevo.

    Por defecto solo guarda en memoria: `path=None`. Escribir un fichero es
    una decisión explícita del que arranca la sesión (`POKER_PREFLOP_SHADOW_LOG`
    o `path=`). Así los tests y la suite no tocan `data/` por accidente.
    """
    def __init__(self, path: Optional[str] = None, enabled: bool = True):
        self.path = path
        self.enabled = bool(enabled)
        self.records: List[Dict[str, Any]] = []
        self._n_file = 0

    def append(self, record: Dict[str, Any]) -> bool:
        if not self.enabled or not record:
            return False
        self.records.append(record)
        if not self.path:
            return True
        try:
            parent = os.path.dirname(os.path.abspath(self.path))
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            with open(self.path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
            self._n_file += 1
            return True
        except (OSError, TypeError, ValueError):
            # El log es instrumento, no motor: un fallo no rompe la reco.
            return False

    @property
    def count(self) -> int:
        return len(self.records)

    def differences(self) -> List[Dict[str, Any]]:
        return [r for r in self.records if r.get('difference')]

    def unresolved(self) -> List[Dict[str, Any]]:
        return [r for r in self.records if r.get('unresolved')]
