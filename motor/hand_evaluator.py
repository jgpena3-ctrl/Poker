"""hand_evaluator.py — fuerza de manos de 5/7 cartas (backend aislado).

Interfaz estable (ARQUITECTURA §6):

    evaluate5(cards)                       -> score int (mayor = mejor)
    evaluate_batch(pairs, board)           -> (N,) scores  (pares rivales + board)
    evaluate_hand(hero_codes, board_codes) -> score int    (códigos 'Ah')
    compare_ranks(hero_score, scores)      -> (wins, ties, losses)
    legal_hands(known_mask)                -> índices de combos legales (0..1325)

Backend actual: evaluación exacta vectorizada con numpy (sin tabla precomputada).
Para rankear 7 cartas se toman sus C(7,5)=21 subconjuntos de 5 y el máximo.
Si el benchmark (python -m motor.hand_evaluator) exigiera aceleración, se
sustituye el backend por una tabla C(52,5) sin tocar la interfaz (fase 3).

Scores: entero con jerarquía base 13:
    score = category * 13**5 + tiebreak   (category 8..0, tiebreak < 13**5)
"""
import itertools

import numpy as np

from .cards import card_id
from .ranges import COMBO0, COMBO1, HAND_MASKS, N_COMBOS

# ----------------------------------------------------------------------
# Subconjuntos de 5 cartas para evaluar manos de n>5 cartas
# ----------------------------------------------------------------------
_SUBSETS = {n: np.array(list(itertools.combinations(range(n), 5)), dtype=np.intp)
            for n in (5, 6, 7)}

# Constantes de base 13
_B4, _B3, _B2, _B1 = 13 ** 4, 13 ** 3, 13 ** 2, 13
_BASE = 13 ** 5

# Patrones de escalera (9 corridas 2..6 -> T..A) + rueda A2345
_STRAIGHT_MASKS = [((1 << 5) - 1) << s for s in range(9)]
_WHEEL_MASK = (1 << 12) | 0b1111  # A 2 3 4 5

CATEGORY_NAMES = ['high card', 'pair', 'two pair', 'trips', 'straight',
                  'flush', 'full house', 'quads', 'straight flush']

# ----------------------------------------------------------------------
# Tabla C(52,5) de scores (fase 3): lookup exacto, cache en disco
# ----------------------------------------------------------------------

N_FIVE = 2_598_960

# Triángulo combinatorio C(n, k) para k <= 5, n <= 52
_COMB: np.ndarray = None  # (53, 6) int64, construido la primera vez


def _build_comb_table():
    global _COMB
    t = np.zeros((53, 6), dtype=np.int64)
    for n in range(53):
        t[n, 0] = 1
        for k in range(1, 6):
            t[n, k] = (t[n - 1, k - 1] + t[n - 1, k]) if n >= k else 0
    _COMB = t
    return t


def _five_table_path():
    import os
    from pathlib import Path
    base = Path(os.environ.get('POKER_MOTOR_CACHE', Path.home() / '.poker_motor'))
    if base.exists() and not base.is_dir():
        base = Path.home() / '.poker_motor'
    return base / 'five_table.npy'


def _five_index(five):
    """(N,5) índices de carta -> (N,) índice lexicográfico 0..2_598_959.

    Las filas deben estar ordenadas ASC. Índice = Σ C(51 - c_i, 5 - i).
    """
    five = np.asarray(five)
    t = _COMB if _COMB is not None else _build_comb_table()
    n = 51 - five
    ks = np.array([5, 4, 3, 2, 1], dtype=np.intp)
    return t[n, ks].sum(axis=1)


def _lookup5(five, table):
    """(N,5) cartas (cualquier orden) -> (N,) scores vía la tabla."""
    s = np.sort(np.asarray(five, dtype=np.intp), axis=1)
    return table[_five_index(s)]


def _build_five_table():
    """Evalúa todas las C(52,5)=2 598 960 combinaciones (una sola vez, ~4 s)."""
    import itertools
    it = itertools.combinations(range(52), 5)
    combos = np.fromiter(it, dtype='i1,i1,i1,i1,i1', count=N_FIVE)
    combos = np.stack([combos['f0'], combos['f1'], combos['f2'], combos['f3'],
                       combos['f4']], axis=1).astype(np.int16)
    scores = np.zeros(N_FIVE, dtype=np.int32)
    chunk = 400_000
    for start in range(0, N_FIVE, chunk):
        end = min(start + chunk, N_FIVE)
        vals = evaluate_five_batch(combos[start:end].astype(np.intp))
        col = _five_index(combos[start:end])
        scores[col] = vals
    return scores


_FIVE_TABLE = None


def _reset_five_table():
    """Invalida la tabla en memoria (solo tests)."""
    global _FIVE_TABLE
    _FIVE_TABLE = None


def _five_table():
    """Tabla C(52,5) cargada (cache de una sesión) o None si no disponible.

    Busca/guarda en `POKER_MOTOR_CACHE`/`~/.poker_motor/five_table.npy`
    (10.4 MB). El build (~4-6 s) ocurre una sola vez; si no hay permiso de
    escritura se queda en memoria.
    """
    global _FIVE_TABLE
    if _FIVE_TABLE is not None:
        return _FIVE_TABLE
    if _COMB is None:
        _build_comb_table()
    path = _five_table_path()
    try:
        _FIVE_TABLE = np.load(path, mmap_mode=None)
        if _FIVE_TABLE.shape != (N_FIVE,):
            raise ValueError('tabla corrupta')
        return _FIVE_TABLE
    except (FileNotFoundError, ValueError):
        pass
    scores = _build_five_table()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, scores)
    except OSError:
        pass
    _FIVE_TABLE = scores
    return _FIVE_TABLE


def evaluate_five_batch(five):
    """(N,5) card ids -> (N,) scores. Núcleo vectorizado del evaluador.

    Las entradas deben tener dtype de al menos 32 bits (los kickers y las
    bases 13^k se multiplican y desbordan en int16).
    """
    five = np.asarray(five)
    n = five.shape[0]
    r = five // 4                       # (N,5) ranks 0..12
    s = five % 4                        # (N,5) suits

    # counts por rank (13) y por suit (4)
    c = np.bincount((np.arange(n)[:, None] * 13 + r).ravel(),
                    minlength=n * 13).reshape(n, 13)
    sc = np.bincount((np.arange(n)[:, None] * 4 + s).ravel(),
                     minlength=n * 4).reshape(n, 4)

    c_sorted = np.sort(c, axis=1)[:, ::-1]
    maxcnt = c_sorted[:, 0]
    cnt2 = c_sorted[:, 1]
    is_flush = sc.max(axis=1) == 5

    # escaleras
    bits = np.bitwise_or.reduce(1 << r, axis=1)
    tops = np.full(n, -1, dtype=np.int8)
    for start, mask in enumerate(_STRAIGHT_MASKS):
        ok = (bits & mask) == mask
        tops = np.maximum(tops, np.where(ok, start + 4, -1))
    ok_wheel = (bits & _WHEEL_MASK) == _WHEEL_MASK
    tops = np.maximum(tops, np.where(ok_wheel, 3, -1))
    is_straight = tops >= 0

    # kickers: cartas únicas de la mano, ordenadas desc (relleno -1)
    freq = np.take_along_axis(c, r, axis=1)
    a = np.where(freq == 1, r, -1)
    a_sorted = np.sort(a, axis=1)[:, ::-1]
    k0, k1, k2, k3, k4 = (a_sorted[:, i] for i in range(5))

    # ranks de parejas
    rng13 = np.arange(13)
    p2 = np.where(c == 2, rng13, -1)
    hp = p2.max(axis=1)
    lp = np.where(p2 == hp[:, None], -1, p2).max(axis=1)
    trip = np.where(c == 3, rng13, -1).max(axis=1)
    quad = np.where(c == 4, rng13, -1).max(axis=1)

    # categoría
    sf = is_flush & is_straight
    quads = maxcnt == 4
    full = (maxcnt == 3) & (cnt2 == 2)
    trips = maxcnt == 3
    twopair = (c == 2).sum(axis=1) == 2
    pair = maxcnt == 2
    cat = np.select(
        [sf, quads, full, is_flush & ~sf, is_straight & ~sf, trips & ~full,
         twopair & ~full, pair & ~twopair],
        [8, 7, 6, 5, 4, 3, 2, 1],
        default=0,
    )

    # tiebreaks por categoría
    s_high = k0 * _B4 + k1 * _B3 + k2 * _B2 + k3 * _B1 + k4
    s_pair = hp * _B4 + k0 * _B3 + k1 * _B2 + k2 * _B1
    s_twop = hp * _B4 + lp * _B3 + k0 * _B2
    s_trip = trip * _B4 + k0 * _B3 + k1 * _B2
    s_full = trip * _B4 + hp * _B3
    s_quad = quad * _B4 + k0 * _B3
    s_straight = tops.astype(np.int64) * _B4

    tb = np.select(
        [sf, quads, full, is_flush & ~sf, is_straight & ~sf, trips & ~full,
         twopair & ~full, pair & ~twopair],
        [s_straight, s_quad, s_full, s_high, s_straight, s_trip, s_twop, s_pair],
        default=s_high,
    )
    return cat.astype(np.int64) * _BASE + tb


def evaluate5(cards):
    """Una mano de 5 cartas (ids 0..51) -> score."""
    five = np.asarray(cards, dtype=np.intp).reshape(1, 5)
    return int(evaluate_five_batch(five)[0])


def evaluate7(cards):
    """Una mano de 7 cartas (ids) -> score (mejor subconjunto de 5)."""
    return int(evaluate_n_batch(np.asarray(cards).reshape(1, -1))[0])


def evaluate_n_batch(hands):
    """(N, n) con n en (5,6,7) -> (N,) scores (máximo de los subconjuntos).

    Si la tabla C(52,5) está disponible (véase `_five_table`), la usa en
    lugar del evaluador por-fila: mismo resultado exacto, mucho más rápido
    en batches grandes (p. ej. los sorteos del runout de decision.py).
    """
    hands = np.asarray(hands, dtype=np.intp)
    n = hands.shape[1]
    sub = _SUBSETS[n]
    five = hands[:, sub].reshape(-1, 5)
    table = _five_table()
    if table is not None:
        return _lookup5(five, table).reshape(hands.shape[0], sub.shape[0]).max(axis=1)
    scores = evaluate_five_batch(five).reshape(hands.shape[0], sub.shape[0])
    return scores.max(axis=1)


def evaluate_batch(pairs, board):
    """Pares rivales (N,2) + board (b ids, 3..5) -> (N,) scores."""
    pairs = np.asarray(pairs)
    b = np.asarray(board, dtype=np.intp).reshape(1, -1)
    n_cards = pairs.shape[1] + b.shape[1]
    hands = np.concatenate([pairs, np.broadcast_to(b, (pairs.shape[0], b.shape[1]))],
                           axis=1)
    return evaluate_n_batch(hands)


def evaluate_hand(hero_codes, board_codes):
    """Códigos 'Ah' de hero (2) y board (3..5) -> score int."""
    ids = [card_id(c) for c in list(hero_codes) + list(board_codes)]
    pairs = np.asarray(ids[:2], dtype=np.intp).reshape(1, 2)
    return int(evaluate_batch(pairs, ids[2:])[0])


def compare_ranks(hero_score, villain_scores):
    """(wins, ties, losses) de villain_scores contra hero_score."""
    vs = np.asarray(villain_scores)
    return int((vs < hero_score).sum()), int((vs == hero_score).sum()), int(
        (vs > hero_score).sum())


def legal_hands(known_mask):
    """Índices (0..1325) de los combos que no chocan con `known_mask` (bitmask)."""
    return np.where((HAND_MASKS & int(known_mask)) == 0)[0]


def category_name(score):
    """Nombre de la categoría de un score (para explicaciones)."""
    return CATEGORY_NAMES[int(score) // _BASE]


def hero_vs_range(hero_codes, board_codes, known_mask, villain_ids):
    """Wins/ties/losses de todos los combos rivales legales contra hero.

    villain_ids: índices de combos (0..1325) a evaluar (p. ej. legal_hands()).
    """
    hero_score = evaluate_hand(hero_codes, board_codes)
    pairs = np.column_stack([COMBO0[villain_ids], COMBO1[villain_ids]])
    scores = evaluate_batch(pairs, [card_id(c) for c in board_codes])
    return compare_ranks(hero_score, scores)


# ---------------------------------------------------------------------------
# Equity preflop contra rango  (CONTRATO_PREFLOP.md, firmado)
# ---------------------------------------------------------------------------
#
# El problema que resuelve: `evaluate_batch` quiere un board COMPARTIDO por
# todas las filas y de 3 a 5 cartas. En preflop no hay board, y el que hace
# falta es un sorteo DISTINTO por fila. Por eso este camino NO reutiliza
# `evaluate_batch`: construye (N, 7) = 2 del jugador + 5 del sorteo y llama
# a `evaluate_n_batch`, que si acepta n en (5, 6, 7). `_SUBSETS` no se toca.

DEFAULT_RUNOUTS = 1
DEFAULT_RUNOUT_COMBOS = 200

_TROZO_BOARDS = 200_000

# Tope de seguridad: con 1326 combos serian 2,3 x 10^9 evaluaciones. Un
# `n_combos` equivocado tiene que fallar aqui, no durar dias en silencio.
_MAX_COMBOS = 2000


def _cards_de_hero(hero_codes):
    """(2,) de ids de carta, venga como ['As', 'Kd'] o como ndarray."""
    a = np.asarray(hero_codes).ravel()
    if a.dtype.kind in 'US' or a.dtype == object:
        return np.array([card_id(str(x)) for x in a], dtype=np.intp)
    return a.astype(np.intp)


def _boards_preflop(resto):
    """Los C(n,5) como (N,5) de ids de carta."""
    return np.fromiter((c for combo in itertools.combinations(resto, 5)
                        for c in combo),
                       dtype=np.intp).reshape(-1, 5)


def equity_preflop_contra_combo(hero, villain):
    """Equity EXACTA del hero contra UN combo rival, sin board.

    `hero` y `villain` son (2,) de ids de carta. Enumera los C(48,5) =
    1 712 304 sorteos, que es lo que hace que esto sea de segundos y no de
    microsegundos.

    Devuelve un float en [0, 1], con 0,5 en los repartos.
    """
    usados = set(int(x) for x in hero) | set(int(x) for x in villain)
    if len(usados) != 4:
        raise ValueError(
            'hero y villain tienen que ser 2 cartas distintas cada uno; '
            'hay %d cartas distintas' % len(usados))
    resto = [c for c in range(52) if c not in usados]
    boards = _boards_preflop(resto)
    n = boards.shape[0]

    h2 = np.asarray(hero, dtype=np.intp).reshape(1, 2)
    v2 = np.asarray(villain, dtype=np.intp).reshape(1, 2)
    sh = np.empty(n, dtype=np.int64)
    sv = np.empty(n, dtype=np.int64)
    for ini in range(0, n, _TROZO_BOARDS):
        b = boards[ini:ini + _TROZO_BOARDS]
        m = b.shape[0]
        sh[ini:ini + m] = evaluate_n_batch(
            np.concatenate([np.repeat(h2, m, axis=0), b], axis=1))
        sv[ini:ini + m] = evaluate_n_batch(
            np.concatenate([np.repeat(v2, m, axis=0), b], axis=1))

    # GANA EL HERO cuando SU score es MAYOR. Al reves, `sv > sh` contaria
    # al rival ganando y la equity saldria complementada: AA contra KK tiene
    # que dar ~0,82, no ~0,18.
    gana = int((sh > sv).sum())
    empata = int((sh == sv).sum())
    return (gana + 0.5 * empata) / n


def _pesos_del_rango(villain_reach):
    """Pesos (1326,) de los combos rivales, de donde venga el rango.

    Acepta None (uniforme), un ndarray de 1326, u un objeto con `.reach`.
    """
    if villain_reach is None:
        return np.full(N_COMBOS, 1.0 / N_COMBOS)
    if isinstance(villain_reach, np.ndarray):
        w = np.asarray(villain_reach, dtype=float).ravel()
        if w.shape[0] != N_COMBOS:
            raise ValueError(
                'villain_reach tiene que tener %d entradas (los %d combos); '
                'tiene %d' % (N_COMBOS, N_COMBOS, w.shape[0]))
        return w
    reach = getattr(villain_reach, 'reach', None)
    if reach is not None:
        w = np.asarray(reach, dtype=float).ravel()
        if w.shape[0] != N_COMBOS:
            raise ValueError('`.reach` tiene que tener %d entradas; tiene %d'
                             % (N_COMBOS, w.shape[0]))
        return w
    arr = np.asarray(villain_reach, dtype=float).ravel()
    if arr.shape[0] != N_COMBOS:
        raise ValueError('villain_reach tiene una forma que no entiendo: %s'
                         % (arr.shape,))
    return arr


def equity_preflop_rango(hero_codes, villain_reach=None,
                         n_runouts=DEFAULT_RUNOUTS,
                         n_combos=DEFAULT_RUNOUT_COMBOS,
                         seed=7):
    """Equity del hero en PREFLOP contra un RANGO. Sin board.

    hero_codes    : ['As', 'Kd'] o (2,) de ids de carta
    villain_reach : None (uniforme) | (1326,) pesos | objeto con `.reach`
    n_combos     : cuantos combos rivales se MUESTREAN del rango
    seed         : determinista para el mismo (hero, reach, n_combos, seed)

    Devuelve float en [0, 1], con 0,5 para los repartos.

    Lanza ValueError si el rango no tiene combos legales.

    `n_runouts` se acepta y se valida, pero **no cambia el calculo**: contra
    cada combo se enumeran TODOS los sorteos posibles, o sea que una sola
    pasada ya es exacta. Se mantiene en la firma porque el contrato la
    escribio, y para que el camino postflop y este sean intercambiables. Si
    en algun momento se pasa a muestrear tableros en vez de enumerarlos, ese
    es el parametro que habria que usar, y no antes.

    Muestreado, y es por FUERZA: contra 1326 combos serian 1326 x C(48,5)
    = 2,3 x 10^9 evaluaciones. La varianza de este estimador esta MEDIDA y
    escrita en `CONTRATO_PREFLOP.md`: con 40 combos, sigma ~ 0,09 y mueve
    el AUC 0,18x el semiancho de su propio intervalo. El estimador no es lo
    que limita la conclusion; las manos son muy pocas.

    Y no usa las cartas del rival: solo `villain_reach`, que es lo unico
    que se sabia al decidir. Por eso la equity que devuelve es OBSERVABLE.
    """
    if n_combos > _MAX_COMBOS:
        raise ValueError(
            'n_combos = %d son %d evaluaciones de C(48,5). El tope es %d: '
            'pasarse aqui cuesta dias en silencio.'
            % (n_combos, n_combos * 1712304, _MAX_COMBOS))
    if n_runouts < 1:
        raise ValueError('n_runouts tiene que ser >= 1, no %r' % (n_runouts,))
    if n_combos < 1:
        raise ValueError(
            'n_combos tiene que ser >= 1, no %r. Con 0 el muestreo queda '
            'vacio y la media seria una division por cero en vez de un '
            'error util.' % (n_combos,))

    hero = _cards_de_hero(hero_codes)
    if hero.shape[0] != 2:
        raise ValueError('hero_codes tiene que tener 2 cartas, tiene %d'
                         % hero.shape[0])

    w = _pesos_del_rango(villain_reach)

    # combos legales: los que no contienen ninguna carta del hero
    mask_hero = 0
    for c in hero:
        mask_hero |= (1 << int(c))
    ids = np.where((HAND_MASKS & mask_hero) == 0)[0]
    if ids.size == 0:
        raise ValueError('el rango no tiene combos legales del hero')

    w_leg = w[ids]
    total = float(w_leg.sum())
    if not np.isfinite(total) or total <= 0.0:
        raise ValueError(
            'el rango no tiene masa sobre los combos legales del hero '
            '(suma = %r). Con un rango todo cero no hay equity que calcular.'
            % total)

    n = int(min(n_combos, ids.size))
    rng = np.random.default_rng(seed)
    p = w_leg / total

    # MUESTREO CON REEMPLAZO SEGUN EL RANGO, Y MEDIA SIN VOLVER A PONDERAR.
    #
    # Antes se sorteaba con `p` y luego se ponderaba por `w` otra vez. Eso
    # es un DOBLE PONDERADO: el muestreo ya favorece los combos pesados y
    # ponderarlos de nuevo empuja la equity hacia ellos. `revision_2` §1.C.
    #
    # Aqui el estimador es la media simple de extracciones i.i.d. de la
    # distribucion `p`, que es INSEGADO para `sum_i p_i * equity_i`.
    #
    # Con reemplazo y no sin, a proposito: con reemplazo la media simple es
    # exactamente insesgada, y los combos repetidos salen de la cache sin
    # coste. Sin reemplazo con probabilidades desiguales habria que
    # corregir por las probabilidades de inclusion.
    elegidos = rng.choice(len(ids), size=n, replace=True, p=p)

    acc = 0.0
    for k in elegidos:
        i = int(ids[int(k)])
        acc += equity_preflop_contra_combo(
            hero, np.array([COMBO0[i], COMBO1[i]], dtype=np.intp))
    return float(acc / n)


if __name__ == '__main__':
    import time
    from .preflop import load_tables
    from .cards import cards_to_bits

    print('=== Benchmark evaluador (backend numpy, sin tabla) ===')
    load_tables()  # calentar imports

    hero_codes = ['As', 'Kd']
    board_flop = ['Qh', '7s', '2c']
    board_river = ['Qh', '7s', '2c', '9d', '5h']

    known = cards_to_bits(hero_codes + board_river)
    idx = legal_hands(known)
    pairs = np.column_stack([COMBO0[idx], COMBO1[idx]])

    print(f'  combos legales (river): {len(idx)}')

    for board in (board_flop, board_river):
        ids = [card_id(c) for c in board]
        t0 = time.perf_counter()
        scores = evaluate_batch(pairs, ids)
        t1 = time.perf_counter()
        hero = evaluate_hand(hero_codes, board)
        w, ti, l = compare_ranks(hero, scores)
        print(f'  board {len(board)} cartas: {len(idx)} manos en {(t1 - t0) * 1000:.1f} ms '
              f'| hero {category_name(hero)} | wins={w} ties={ti} losses={l}')