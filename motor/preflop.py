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


def prob(action, pos, vs=''):
    """Vector P(A|H) (1326,) para (action, pos, vs).

    Sin tabla para esa combinación devuelve ceros: el update bayesiano
    vaciará el rango ante esa acción (no modelada).
    """
    t = load_tables().get(table_key(action, pos, vs))
    return t['probs'] if t is not None else np.zeros(N_COMBOS, dtype=np.float32)


def opening_range(pos):
    """Rango de apertura (OR) de `pos` -> vector (1326,) de masas."""
    return prob('OR', pos, '')


def preload():
    """Fuerza la carga para evitar latencia en el primer uso."""
    return load_tables()