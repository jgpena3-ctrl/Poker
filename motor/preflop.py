"""preflop.py — tablas de decisión preflop (data/preflop_matrices.json).

Cada tabla es un grid 13x13 (filas/cols en orden GRID_RANKS = 'AKQJT98765432'):
    - celda (i, i)         -> pares        (6 combos)
    - celda (i, j), i < j  -> SUITED       (4 combos)
    - celda (i, j), i > j  -> OFFSUIT      (12 combos)
El valor de la celda es la frecuencia con la que se ejecuta la acción con esa
mano (1.0 = siempre, 0.25 = 25%).

El grid completo 13x13 codifica las 169 manos; el mapeo a los 1326 combos
reales se resuelve una vez (índices de celda por combo, CELL_ROW/CELL_COL)
para producir P(A|H) vectorizada (1326,) sin bucles.

Estas frecuencias alimentan el update bayesiano del RangeState: ante una
acción observada del rival en `pos` enfrentando a `vs`, multiplicamos el reach
por P(A|H) = vector de la tabla correspondiente. Más adelante, los perfiles de
jugador escalarán estos vectores con la frecuencia esperada vs real observada
en hands_db.jsonl.
"""
import json
import os

import numpy as np

from .cards import RANK_ORDER
from .ranges import COMBO0, COMBO1, N_COMBOS

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRICES_PATH = os.path.join(REPO_DIR, 'data', 'preflop_matrices.json')

GRID_RANKS = 'AKQJT98765432'
GRID_INDEX = {rank: i for i, rank in enumerate(GRID_RANKS)}

# ---------------------------------------------------------------
# Mapeo celda -> combos (una sola vez)
# ---------------------------------------------------------------
_rank_grid = np.array([GRID_INDEX[r] for r in RANK_ORDER])  # rango 2..A -> grid
_g0 = _rank_grid[COMBO0 // 4]
_g1 = _rank_grid[COMBO1 // 4]
_is_pair = COMBO0 // 4 == COMBO1 // 4
_is_suited = COMBO0 % 4 == COMBO1 % 4
_rmin = np.minimum(_g0, _g1)
_rmax = np.maximum(_g0, _g1)
CELL_ROW = np.where(_is_pair, _g0, np.where(_is_suited, _rmin, _rmax))
CELL_COL = np.where(_is_pair, _g0, np.where(_is_suited, _rmax, _rmin))

del _rank_grid, _g0, _g1, _is_pair, _is_suited, _rmin, _rmax


def matrix_to_probs(matrix):
    """Grid 13x13 -> vector (1326,) con la frecuencia de cada combo."""
    m = np.asarray(matrix, dtype=np.float32)
    if m.shape != (13, 13):
        raise ValueError(f'matriz preflop debe ser 13x13, recibida {m.shape}')
    return m[CELL_ROW, CELL_COL].copy()


# ---------------------------------------------------------------
# Carga de tablas
# ---------------------------------------------------------------
_TABLES = None


def load_tables():
    """Carga única de data/preflop_matrices.json con vectores ya mapeados."""
    global _TABLES
    if _TABLES is None:
        with open(MATRICES_PATH) as f:
            raw = json.load(f)
        tables = {}
        for name, t in raw['tables'].items():
            tables[name] = {
                'action': t['action'],
                'pos': t['pos'],
                'vs': t.get('vs', ''),
                'probs': matrix_to_probs(t['matrix']),
            }
        _TABLES = tables
    return _TABLES


def table_key(action, pos, vs=''):
    """Clave canónica: 'OR_UTG', '3B_BB_vs_SB'..."""
    return f'{action}_{pos}_vs_{vs}' if vs else f'{action}_{pos}'


#: Alias históricos del fichero. En 6-max ``HJ`` es el asiento que el motor
#: llama ``MP``; la única tabla afectada es ``4B_UTG_vs_HJ``. Se declara aquí
#: para que el alias sea explícito y auditable, no un fallback silencioso.
TABLE_ALIASES = {
    ('4B', 'UTG', 'MP'): '4B_UTG_vs_HJ',
}

_PREFLOP_ORDER = ('UTG', 'MP', 'CO', 'BTN', 'SB', 'BB')
_ENGINE_PAIR_ACTIONS = ('3B', 'Call_OR', '4B', 'Call_3B', '5B',
                        'Call_4B', 'Call_5B')
#: Raises que deben haber ocurrido antes de la decisión. Como en una ronda
#: preflop cada asiento actúa una sola vez, el héroe necesita al menos este
#: número de asientos anteriores; si no, el spot es imposible.
_MIN_PRIOR_RAISERS = {
    '3B': 1, 'Call_OR': 1,
    '4B': 2, 'Call_3B': 2,
    '5B': 3, 'Call_4B': 3,
    'Call_5B': 4,
}


def lookup_table(action, pos, vs=''):
    """(tabla, clave_usada, estado) para una consulta EXACTA.

    estado ∈ {'exact', 'alias', 'missing'}. No aplica el fallback "misma
    acción + misma posición, otro rival" del asistente: ese fallback es una
    decisión distinta y se audita por separado.
    """
    tables = load_tables()
    key = table_key(action, pos, vs)
    if key in tables:
        return tables[key], key, 'exact'
    alias = TABLE_ALIASES.get((action, pos, vs))
    if alias and alias in tables:
        return tables[alias], alias, 'alias'
    return None, None, 'missing'


def classify_missing_table(action, pos, vs=''):
    """Clasifica una ausencia exacta según el contrato preflop.

    No decide qué frecuencia usar; solo dice POR QUÉ no hay tabla. Las
    ausencias intencionales y las imposibles por orden de acción no son
    huecos de cobertura; los huecos reales sí.
    """
    if action == 'OR' and pos == 'BB' and not vs:
        return 'intentional_check_option'
    if action == 'ROL' and pos == 'UTG' and not vs:
        return 'intentional_no_prior_limp'
    if pos in _PREFLOP_ORDER:
        hero_index = _PREFLOP_ORDER.index(pos)
        required = _MIN_PRIOR_RAISERS.get(action)
        if required is not None and hero_index < required:
            return 'impossible_action_order'
        if vs and vs in _PREFLOP_ORDER:
            vs_index = _PREFLOP_ORDER.index(vs)
            # El último raiser de n subidas no puede estar en los primeros
            # n-1 asientos: harían falta n raisers distintos antes de él.
            if vs_index >= hero_index:
                return 'impossible_action_order'
            if required is not None and vs_index < required - 1:
                return 'impossible_action_order'
    if action in ('OR', 'ROL', '3B', 'Call_OR', '4B', 'Call_3B',
                  '5B', 'Call_4B', 'Call_5B'):
        return 'coverage_gap'
    return 'unclassified'


def audit_engine_coverage():
    """Inventario de las claves que el motor preflop puede consultar.

    Devuelve listas separadas: ``exact``, ``alias`` y las tres clases de
    ausencia. Es puramente informativo: no genera tablas ni toca frecuencias.
    """
    checks = []
    for pos in _PREFLOP_ORDER:
        checks.append(('OR', pos, ''))
        checks.append(('ROL', pos, ''))
        for vs in _PREFLOP_ORDER:
            if vs == pos:
                continue
            for action in _ENGINE_PAIR_ACTIONS:
                checks.append((action, pos, vs))

    out = {
        'exact': [],
        'alias': [],
        'intentional_missing': [],
        'impossible_missing': [],
        'coverage_gap': [],
        'unclassified_missing': [],
    }
    for action, pos, vs in checks:
        _table, source, status = lookup_table(action, pos, vs)
        if status == 'exact':
            out['exact'].append(source)
        elif status == 'alias':
            out['alias'].append({
                'key': table_key(action, pos, vs),
                'source': source,
            })
        else:
            reason = classify_missing_table(action, pos, vs)
            missing = table_key(action, pos, vs)
            if reason.startswith('intentional_'):
                out['intentional_missing'].append({
                    'key': missing, 'reason': reason})
            elif reason == 'impossible_action_order':
                out['impossible_missing'].append({
                    'key': missing, 'reason': reason})
            elif reason == 'coverage_gap':
                out['coverage_gap'].append({
                    'key': missing, 'reason': reason})
            else:
                out['unclassified_missing'].append({
                    'key': missing, 'reason': reason})
    return out


def has_table(action, pos, vs='') -> bool:
    """True si existe una tabla válida para (action, pos, vs)."""
    return lookup_table(action, pos, vs)[0] is not None


def prob(action, pos, vs=''):
    """Vector P(A|H) (1326,) para (action, pos, vs), o None si no hay tabla.

    Distingue tres estados (pegar_2 §3):

      - tabla presente y válida -> se usa;
      - tabla AUSENTE           -> None. La ausencia de una estimación no
        es una estimación: devolver ceros hacía que el update bayesiano
        vaciara el rango entero, convirtiendo "no modelado" en "imposible";
      - tabla inválida          -> matrix_to_probs() lanza al cargar.

    Quien necesite un valor numérico debe llamar a
    `prob_or_fallback()` y registrar de dónde salió el valor.
    """
    t, _source, _status = lookup_table(action, pos, vs)
    return None if t is None else t['probs']


def prob_or_fallback(action, pos, vs='', fallback=None):
    """Como `prob`, pero devuelve un vector usable. Devuelve (vec, fuente).

    fuente ∈ {'table', 'uniform'}. Permite que el consumidor registre
    cuándo está usando un rango uniforme en lugar de una estimación,
    en vez de indistinguishable de un rango real.
    """
    v = prob(action, pos, vs)
    if v is not None:
        return v, 'table'
    if fallback is None:
        fallback = np.full(N_COMBOS, 1.0 / N_COMBOS, dtype=np.float32)
    return np.asarray(fallback, dtype=np.float32).copy(), 'uniform'


def opening_range(pos):
    """Rango de apertura (OR) de `pos` -> vector (1326,) de masas, o None.

    Devuelve None si no hay tabla OR para esa posición. Notar que la BB
    no "abre" en el mismo sentido que el resto: no existe OR_BB en
    preflop_matrices.json, y no debe inventarse una. Quien necesite un
    vector debe usar `opening_range_or_fallback()`.
    """
    return prob('OR', pos, '')


def opening_range_or_fallback(pos, fallback=None):
    """(vector, fuente) del rango de apertura; fuente ∈ {'table','uniform'}."""
    return prob_or_fallback('OR', pos, '', fallback)


def preload():
    """Fuerza la carga para evitar latencia en el primer uso."""
    return load_tables()