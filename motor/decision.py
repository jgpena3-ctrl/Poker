"""decision.py — EV de acciones (MVP 1 + sorteo de runout en la equity, MVP 2).

DecisionEngine (ARQUITECTURA §8.2): se operan los pesos individuales por combo
(masas), nunca la RangeDistribution (esa va solo al panel).

Etapa MVP 1 (§8.3): EV inmediato con **una respuesta modelada** del rival
(fold/call/raise). No hay árbol futuro aún.

    FOLD            → 0
    CHECK           → equity × pot
    CALL            → equity × (pot + 2·to_call) − to_call
    BET s           → Σ_v w_v · [ pf·pot + pc·(eq_v·(pot+2b) − b) + pr·(−b) ]
    ALL_IN          → Σ_v w_v · [ pf·pot + (pc+pr)·(eq_v·(pot+2S) − S) ]

donde (pf, pc, pr) = `default_response` (heurística, por equity) o bien la
respuesta del perfil del rival vía `OracleResponse` (P(A|C) de la fase de
aprendizaje, mezclada con fade-in según la muestra de su celda) y
`equity_v` es la fracción de bote que gana el hero contra el combo rival v.

Etapa MVP 2: `compute_evs` usa por defecto **equity a showdown con sorteo de
runout** para cada acción. `runout=False` conserva el modo rápido de fuerza
actual, útil solo para diagnósticos o presupuestos muy cortos.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np

from .cards import card_id, cards_to_bits
from .hand_evaluator import (evaluate_batch, evaluate_hand, evaluate_n_batch,
                             legal_hands)
from .ranges import COMBO0, COMBO1, RangeState

BET_LABELS = ('bet_25', 'bet_50', 'bet_75')
ACTIONS = ('fold', 'check', 'call') + BET_LABELS + ('raise', 'all_in')


def _bet_label(frac):
    """Label de un sizing: 0.25 → 'bet_25', 0.33 → 'bet_33', 0.66 → 'bet_66'."""
    return f'bet_{int(round(frac * 100))}'


# ---------------------------------------------------------------------------
# Modelo de respuesta del rival (heurística tuneable; fase 4: perfiles)
# ---------------------------------------------------------------------------

def _response_array(villain_equity, amount, pot):
    """(pf, pc, pr) vectorizados — núcleo de `default_response`."""
    e = np.clip(np.asarray(villain_equity, dtype=np.float64), 0.0, 1.0)
    if amount <= 0:
        return np.zeros_like(e), np.ones_like(e), np.zeros_like(e)
    breakeven = amount / (pot + 2 * amount)
    pf = np.where(
        e >= breakeven + 0.02,               # le llegan las odds de sobra
        np.clip(0.05 + 0.10 * (breakeven + 0.02 - e), 0.02, 0.30),
        np.where(
            e >= breakeven,
            0.30,
            np.clip(0.30 + 0.65 * (breakeven - e) / max(breakeven, 1e-9),
                    0.30, 0.98),
        ),
    )
    pf = np.clip(pf, 0.02, 0.98)
    pr = np.clip((e - 0.55) * 1.6, 0.0, 0.30)
    pr = np.minimum(pr, 1.0 - pf - 0.05)
    pc = 1.0 - pf - pr
    return pf, pc, pr


def default_response(villain_equity, amount, pot):
    """(p_fold, p_call, p_raise) ante una apuesta de `amount` sobre `pot`.

    Pliega si su equity no llega a las odds; sube con manos muy fuertes.
    Toda cifra es heurística de arranque; con perfiles disponibles la
    sustituye `OracleResponse` (fase 4).
    """
    pf, pc, pr = _response_array(villain_equity, amount, pot)
    return float(pf.ravel()[0]), float(pc.ravel()[0]), float(pr.ravel()[0])


class OracleResponse:
    """Respuesta del rival desde `Oracle` (P(A|C) del perfil, §7).

    Funde la distribución del perfil con la heurística `default_response`:
    cuanto mayor la n de la celda (celda `n` del Oracle), más peso del
    perfil (fade-in 1 − n/fade_in; n=0 → heurística pura).

    context: (street, facing, texture) — facing es lo que ve el rival
    cuando el hero apuesta (cbet si el hero es el iniciador en flop, etc.).
    """

    def __init__(self, oracle, label, context, fade_n=20.0):
        self.oracle = oracle
        self.label = label
        street, facing, texture = context
        self.street, self.facing, self.texture = street, facing, texture
        dist = oracle.p_action(label, street, facing, texture) \
            if oracle is not None else None
        if dist:
            a = dist['actions']
            total = (a.get('c', 0.0) + a.get('f', 0.0) + a.get('r', 0.0))
            self.pf_p = a.get('f', 0.0) / total if total else 0.0
            self.pc_p = a.get('c', 0.0) / total if total else 0.0
            self.pr_p = a.get('r', 0.0) / total if total else 0.0
            self.alpha = min(1.0, dist.get('n', 0) / fade_n)
            self.source = dist['source']
            self.sizing = dist.get('sizing')
        else:
            self.pf_p = self.pc_p = self.pr_p = 0.0
            self.alpha = 0.0
            self.source = 'default'
            self.sizing = None

    def __call__(self, villain_equity, amount, pot):
        if amount <= 0:
            e = np.asarray(villain_equity, dtype=np.float64)
            return np.zeros_like(e), np.ones_like(e), np.zeros_like(e)
        pf_e, pc_e, pr_e = _response_array(villain_equity, amount, pot)
        if self.alpha <= 0:
            return pf_e, pc_e, pr_e
        base = np.column_stack((pf_e, pc_e, pr_e))
        profile = np.clip(np.asarray((self.pf_p, self.pc_p, self.pr_p)),
                          0.05, 0.90)
        scale = np.power(3.0 * profile, self.alpha)
        adjusted = base * scale
        adjusted /= adjusted.sum(axis=-1, keepdims=True)
        return adjusted[:, 0], adjusted[:, 1], adjusted[:, 2]


# ---------------------------------------------------------------------------
# Sorteo de runout (MVP 2, parcial): equity a showdown con turn+river
# ---------------------------------------------------------------------------

DEFAULT_RUNOUTS = 100
DEFAULT_RUNOUT_COMBOS = 200


def _vector_runout(p0, p1, deck, rng, r, extra=None):
    """(k, r) cartas de runout por rival, sin sus cartas ni las del hero/board
    (ni, si se da `extra` (k,), las cartas ya repartidas en la primera calle).

    Fisher–Yates parcial vectorizado: los slots excluidos se marcan con
    rand = inf, se ordenan las columnas y se toman las r primeras.
    """
    k = len(p0)
    cols = [p0, p1]
    if extra is not None:
        cols.append(np.asarray(extra))
    cols = np.column_stack(cols)[:, :, None]
    excl = np.any(cols == deck[None, None, :], axis=1)
    rvals = np.where(excl, np.inf, rng.random((k, len(deck))))
    order = np.argsort(rvals, axis=1)
    return np.take_along_axis(np.broadcast_to(deck, (k, len(deck))),
                              order[:, :r], axis=1)


def runout_equity(hero_codes, board_codes, villain_reach=None,
                  n_runouts: int = DEFAULT_RUNOUTS,
                  n_combos: int = DEFAULT_RUNOUT_COMBOS, seed: int = 7) -> float:
    """Equity a showdown del hero vs el rango rival con sorteo del runout.

    MC conjunto (insesgado): en cada sorteo se muestrean `n_combos` rivales
    con pesos del reach y a cada uno se le reparten las cartas restantes
    (turn+river en flop; river en turn) de su propio deck privado (sin sus
    cartas ni las del hero ni del board). En river no hay sorteo y la equity
    es exacta. Determinístico (seed fija) para reproducibilidad.

    La equity se calcula por combo rival para que también pueda usarse en las
    ramas agresivas y en la respuesta del rival.
    """
    ids, weights, current_equity = _villain_arrays(
        hero_codes, board_codes, villain_reach)
    if len(board_codes) >= 5:
        return float((current_equity * weights).sum())
    equity = _showdown_equity_by_combo(
        hero_codes, board_codes, ids, n_runouts=n_runouts, seed=seed)
    return float((equity * weights).sum())


def _showdown_equity_by_combo(hero_codes, board_codes, villain_ids,
                              n_runouts=DEFAULT_RUNOUTS, seed=7):
    """Equity a showdown de hero frente a cada combo rival legal.

    Cada combo recibe sus propios runouts legales. Esto es importante para
    valorar draws y para que el modelo de respuesta no confunda una mano que
    va por detrás hoy con una mano sin equity. Se procesa en lotes para no
    construir un array grande en flop.
    """
    hero = [card_id(c) for c in hero_codes]
    board = [card_id(c) for c in board_codes]
    remaining = 5 - len(board)
    ids = np.asarray(villain_ids, dtype=np.intp)
    if remaining <= 0:
        pairs = np.column_stack([COMBO0[ids], COMBO1[ids]])
        scores = evaluate_batch(pairs, board)
        hero_score = evaluate_hand(hero_codes, board_codes)
        return 1.0 * (scores < hero_score) + 0.5 * (scores == hero_score)

    known = cards_to_bits(list(hero_codes) + list(board_codes))
    deck = np.asarray([card for card in range(52)
                       if not (known >> card) & 1], dtype=np.intp)
    p0, p1 = COMBO0[ids], COMBO1[ids]
    n = len(ids)
    if n == 0:
        raise ValueError('rango rival sin combos legales')
    rng = np.random.default_rng(seed)
    hero_pair = np.asarray(hero, dtype=np.intp)
    board_array = np.asarray(board, dtype=np.intp)
    wins = np.zeros(n, dtype=np.float64)
    samples = max(1, int(np.ceil(
        min(n, DEFAULT_RUNOUT_COMBOS) * max(1, int(n_runouts)) / n)))
    batch = 8

    for start in range(0, samples, batch):
        count = min(batch, samples - start)
        p0_batch = np.tile(p0, count)
        p1_batch = np.tile(p1, count)
        run = _vector_runout(p0_batch, p1_batch, deck, rng, remaining)
        rows = len(p0_batch)
        villain_hands = np.column_stack([
            p0_batch, p1_batch,
            np.broadcast_to(board_array, (rows, len(board_array))), run,
        ])
        hero_hands = np.column_stack([
            np.broadcast_to(hero_pair, (rows, 2)),
            np.broadcast_to(board_array, (rows, len(board_array))), run,
        ])
        villain_scores = evaluate_n_batch(villain_hands)
        hero_scores = evaluate_n_batch(hero_hands)
        outcome = 1.0 * (villain_scores < hero_scores) + \
            0.5 * (villain_scores == hero_scores)
        wins += outcome.reshape(count, n).sum(axis=0)
    return wins / samples


# ---------------------------------------------------------------------------
# Arrays de apoyo sobre los combos rivales legales
# ---------------------------------------------------------------------------

def _villain_arrays(hero_codes, board_codes, villain_reach):
    """(ids, w, hero_eq) — combos rivales legales, masas normalizadas y
    equity del hero contra cada combo (0/0.5/1 según la fuerza actual)."""
    known = cards_to_bits(list(hero_codes) + list(board_codes))
    ids = legal_hands(known)
    pairs = np.column_stack([COMBO0[ids], COMBO1[ids]])
    scores = evaluate_batch(pairs, [card_id(c) for c in board_codes])
    hero = evaluate_hand(hero_codes, board_codes)

    if villain_reach is None:
        w = np.full(len(ids), 1.0 / len(ids), dtype=np.float64)
    elif isinstance(villain_reach, RangeState):
        w = villain_reach.reach_blocked[ids].astype(np.float64)
    else:
        arr = np.asarray(villain_reach, dtype=np.float64)
        if arr.shape != (1326,):
            raise ValueError(f'reach debe tener forma (1326,), tiene {arr.shape}')
        w = arr[ids]
    total = w.sum()
    if total > 0:
        w = w / total

    hero_eq = 1.0 * (scores < hero) + 0.5 * (scores == hero)
    return ids, w, hero_eq


def _branch_ev(amount, pot, hero_eq, villain_eq, w, all_in=False,
               response=None):
    """EV agregado de "hero apuesta `amount`": Σ_v w_v · rama_v."""
    if amount <= 0:
        return 0.0
    if response is None:
        pf, pc, pr = _response_array(villain_eq, amount, pot)
    else:
        pf, pc, pr = response(villain_eq, amount, pot)
    branch_call = hero_eq * (pot + 2 * amount) - amount
    if all_in:
        branch = pf * pot + (pc + pr) * branch_call
    else:
        branch = pf * pot + pc * branch_call - pr * amount
    return float((w * branch).sum())


def _raise_ev(amount_to, pot, hero_eq, villain_eq, w, to_call,
              response=None):
    """EV de "hero sube a TOTAL `amount_to`" con una apuesta en curso.

    `pot` ya incluye la apuesta rival; el hero compromete `amount_to`
    (que incluye sus `to_call`) y el rival paga `amount_to - to_call` más
    para igualar (pegar.txt §12): bote final = pot + amount_to + extra.
    La respuesta del rival se evalúa contra la subida `extra`, no contra el
    total (es lo que el rival debe pagar de más).
    """
    extra = amount_to - to_call
    if extra <= 0:
        return 0.0
    if response is None:
        pf, pc, pr = _response_array(villain_eq, extra, pot)
    else:
        pf, pc, pr = response(villain_eq, extra, pot)
    branch_call = hero_eq * (pot + amount_to + extra) - amount_to
    branch = pf * pot + pc * branch_call - pr * amount_to
    return float((w * branch).sum())


# ---------------------------------------------------------------------------
# Árbol de una calle (MVP 2 completo): pagos intermedios de la calle siguiente
# ---------------------------------------------------------------------------

TREE_STREET = 60      # sorteos de la carta siguiente por rama
TREE_FINALS = 6       # cartas finales (river) muestreadas por sorteo
TREE_FRAC = 0.5       # sizing del hero en la siguiente calle


def _tree_values(hero_ids, board_ids, ids0, w, pot, stack, response_fn,
                 n_street: int = TREE_STREET, n_finals: int = TREE_FINALS,
                 frac: float = TREE_FRAC, seed: int = 21):
    """E[F_v] de la calle siguiente (check vs bet) por combo rival.

    MC conjunto determinista: se sortean (v, carta_siguiente) y, para cada
    uno, `n_finals` cartas finales del deck privado de v. Para cada muestra:
        eq6  : equity inmediata en la nueva calle (mueve la respuesta rival)
        eqF  : equity a showdown con la carta final repartida
        F_v  : max(check_v, bet_v), con
                check_v = eqF · pot
                bet_v  = pf'·pot + pc'·(eqF·(pot+2b') − b') − pr'·b'
    donde (pf', pc', pr') responde a la equity del rival en la nueva calle y
    b' = frac·pot. Devuelve τ_v = E[F_v] por combo muestreado (los combos
    sin muestra usan la media global) y la media ponderada τ̄.
    """
    n_cartas = len(board_ids)
    restantes = 5 - n_cartas
    known = 0
    for c in hero_ids + board_ids:
        known |= 1 << c
    deck = np.asarray([c for c in range(52) if not (known >> c) & 1],
                      dtype=np.intp)
    rng = np.random.default_rng(seed)
    rng_f = np.random.default_rng(seed + 101)
    k = min(int(n_street), len(ids0))
    amount = min(frac * pot, stack) if pot > 0 else 0.0
    hero_pair = np.asarray([[hero_ids[0], hero_ids[1]]], dtype=np.intp)
    brd = np.asarray(board_ids, dtype=np.intp)

    sums = np.zeros(len(ids0), dtype=np.float64)
    counts = np.zeros(len(ids0), dtype=np.intp)
    acc, total = 0.0, 0
    for _ in range(n_street):
        sel = ids0[rng.choice(len(ids0), size=k, replace=True, p=w)]
        p0, p1 = COMBO0[sel], COMBO1[sel]
        card1 = _vector_runout(p0, p1, deck, rng, 1)[:, 0]
        full6 = np.column_stack([p0, p1,
                                 np.broadcast_to(brd, (k, n_cartas)), card1])
        hero6 = np.column_stack([
            np.broadcast_to(hero_pair, (k, 2)),
            np.broadcast_to(brd, (k, n_cartas)), card1])
        sc6 = evaluate_n_batch(full6)
        eq6 = 1.0 * (sc6 < evaluate_n_batch(hero6)) + \
            0.5 * (sc6 == evaluate_n_batch(hero6))
        villain_eq6 = 1.0 - eq6
        if response_fn is None:
            pf, pc, pr = _response_array(villain_eq6, amount, pot)
        else:
            pf, pc, pr = response_fn(villain_eq6, amount, pot)

        if restantes == 1:
            eq7 = eq6
            F = np.maximum(eq7 * pot,
                           pf * pot + pc * (eq7 * (pot + 2 * amount) - amount)
                           - pr * amount)
        else:
            finals = max(1, int(n_finals))
            p0_final = np.repeat(p0, finals)
            p1_final = np.repeat(p1, finals)
            card1_final = np.repeat(card1, finals)
            card2 = _vector_runout(p0_final, p1_final, deck, rng_f, 1,
                                    extra=card1_final)[:, 0]
            rows = len(p0_final)
            full7 = np.column_stack([
                p0_final, p1_final,
                np.broadcast_to(brd, (rows, n_cartas)),
                card1_final, card2])
            hero7 = np.column_stack([
                np.broadcast_to(hero_pair, (rows, 2)),
                np.broadcast_to(brd, (rows, n_cartas)), card1_final, card2])
            sc7 = evaluate_n_batch(full7)
            hero7_scores = evaluate_n_batch(hero7)
            eq7 = 1.0 * (sc7 < hero7_scores) + 0.5 * (sc7 == hero7_scores)
            eq7 = eq7.reshape(k, finals)
            check_v = eq7 * pot
            bet_v = (pf[:, None] * pot + pc[:, None] *
                     (eq7 * (pot + 2 * amount) - amount) - pr[:, None] * amount)
            F = np.maximum(check_v, bet_v).mean(axis=1)
        idx = np.searchsorted(ids0, sel)
        np.add.at(sums, idx, F)
        np.add.at(counts, idx, 1)
        acc += float(F.sum())
        total += k

    tau_global = acc / total if total else 0.0
    sampled = counts > 0
    tau = np.full(len(ids0), tau_global, dtype=np.float64)
    tau[sampled] = sums[sampled] / counts[sampled]
    tau_mean = float((w * tau).sum())
    return tau, tau_mean


# ---------------------------------------------------------------------------
# EV de las acciones
# ---------------------------------------------------------------------------

@dataclass
class EvTable:
    """EV inmediato por acción (MVP 1) + recomendación derivada."""
    ev: Dict[str, float] = field(default_factory=dict)
    pot: float = 0.0
    hero_equity: float = 0.0

    def best(self) -> Tuple[str, float]:
        """La mejor acción por EV (fold si nada supera 0)."""
        best_label, best_ev = 'fold', self.ev.get('fold', 0.0)
        for label, value in self.ev.items():
            if value > best_ev:
                best_label, best_ev = label, value
        return best_label, best_ev


def compute_evs(hero_codes, board_codes, villain_reach=None,
                pot=0.0, to_call=0.0, stack=0.0,
                villain_stack=None,
                bet_sizes=(0.25, 0.5, 0.75),
                raise_to=None,
                candidates=None,
                response_fn=None, runout=True,
                n_runouts: int = DEFAULT_RUNOUTS,
                tree: bool = False,
                tree_n_street: int = TREE_STREET,
                tree_n_finals: int = TREE_FINALS,
                tree_frac: float = TREE_FRAC) -> EvTable:
    """EV (MVP 1) de cada acción para la mano conocida del hero; con `tree`
    (MVP 2 completo) una calle futura con pagos intermedios.

    hero_codes    : ['As', 'Kd']
    board_codes   : 3..5 cartas
    villain_reach : None (uniforme) | RangeState | vector (1326,)
    pot           : bote antes de actuar el hero (ya incluye la apuesta rival)
    to_call       : fichas a pagar si hay un bet en curso (0 = sin bet)
    stack         : stack restante del hero antes de actuar
    villain_stack : stack restante del rival que hizo/aplicará el call;
                    limita el stack efectivo. None conserva compatibilidad
                    con el supuesto de stacks iguales.
    bet_sizes     : fracciones del bote para las bets (0 < to_call: solo call)
    raise_to      : opcional — si hay bet en curso, el TOTAL al que se sube
                    (incluye to_call; pegar.txt §12). Si no se da, no hay
                    acción 'raise'. Si el importe no supera to_call, se omite.
    candidates    : opcional — restraints de pegar.txt §21/§22: solo se
                    conservan en `ev` estas acciones (¿qué tiene sentido?).
                    El EV ya se calculó; esto filtra la tabla para el panel
                    y para `best()`.
    response_fn   : (villain_eq, amount, pot) -> (pf, pc, pr) vectorizado;
                    None = `_response_array` (heurística). Perfiles:
                    `OracleResponse` (motor.behavior) con P(A|C) del rival.
    runout        : si True y faltan cartas del board, todas las acciones usan
                    equity a showdown por combo con sorteo de turn+river.
    n_runouts     : número de sorteos del runout (MC determinista).
    tree          : MVP 2 completo — si True (y faltan cartas del board),
                    cada rama con jugada futura (check/call, y las ramas de
                    call de cada bet) resuelve la calle siguiente con pagos
                    intermedios: MC conjunto (rival, carta siguiente, carta
                    final) donde el hero juega check vs bet 50% del bote en
                    la nueva calle y el rival responde con `response_fn`
                    usando su equity inmediata en ella. el all_in conserva
                    la liquidación inmediata (efectivo comprometido).
    tree_n_street : sorteos de la carta siguiente por rama (MC determinista).
    tree_n_finals : cartas finales muestreadas por sorteo.
    tree_frac     : sizing (fracción del bote) del bet en la calle siguiente.
    """
    if len(hero_codes) < 2:
        raise ValueError('MVP 1 exige la mano del hero conocida (2 códigos)')
    stack = max(0.0, float(stack))
    if villain_stack is not None:
        villain_stack = max(0.0, float(villain_stack))
        effective_stack = min(stack, villain_stack)
    else:
        effective_stack = stack
    call_amount = min(max(0.0, float(to_call)), stack)
    call_pot = pot - max(0.0, float(to_call) - call_amount)
    ids, w, current_hero_eq = _villain_arrays(
        hero_codes, board_codes, villain_reach)
    hero_ids = [card_id(c) for c in hero_codes]
    board_ids = [card_id(c) for c in board_codes]
    has_next = len(board_ids) < 5
    if runout and has_next:
        hero_eq = _showdown_equity_by_combo(
            hero_codes, board_codes, ids, n_runouts=n_runouts)
    else:
        hero_eq = current_hero_eq
    villain_eq = 1.0 - hero_eq
    equity_mean = float((hero_eq * w).sum())

    ev: Dict[str, float] = {'fold': 0.0}

    if tree and has_next:
        def tree_tau(pot_s, stack_s, seed):
            tau, _mean = _tree_values(
                hero_ids, board_ids, ids, w, pot_s, stack_s, response_fn,
                n_street=tree_n_street, n_finals=tree_n_finals,
                frac=tree_frac, seed=seed)
            return tau

        if to_call <= 0:
            ev['check'] = float((w * tree_tau(pot, effective_stack, 21)).sum())
        if to_call > 0:
            ev['call'] = float((w * tree_tau(call_pot + 2 * call_amount,
                                              effective_stack - call_amount,
                                              22)).sum()) - call_amount

        for idx, frac in enumerate(bet_sizes):
            amount = min(frac * pot, effective_stack) if pot > 0 else 0.0
            label = _bet_label(frac)
            if amount <= 0:
                ev[label] = 0.0
                continue
            if response_fn is None:
                pf, pc, pr = _response_array(villain_eq, amount, pot)
            else:
                pf, pc, pr = response_fn(villain_eq, amount, pot)
            tau = tree_tau(pot + 2 * amount, effective_stack - amount, 30 + idx)
            branch = pf * pot + pc * tau - pr * amount
            ev[label] = float((w * branch).sum())
    else:
        if to_call <= 0:
            ev['check'] = equity_mean * pot
        if to_call > 0:
            ev['call'] = equity_mean * (call_pot + 2 * call_amount) - call_amount
            max_raise_to = min(stack, to_call + (villain_stack if villain_stack is not None
                                                 else stack))
            if raise_to is not None and to_call < raise_to <= max_raise_to:
                ev['raise'] = float((w * _raise_ev(
                    raise_to, pot, hero_eq, villain_eq, w, to_call,
                    response=response_fn)).sum())

        for frac in bet_sizes:
            label = _bet_label(frac)
            amount = min(frac * pot, effective_stack) if pot > 0 else 0.0
            ev[label] = _branch_ev(amount, pot, hero_eq, villain_eq, w,
                                   response=response_fn)

    ev['all_in'] = _branch_ev(effective_stack, pot, hero_eq, villain_eq, w,
                               all_in=True, response=response_fn)

    if to_call > 0 and raise_to is not None and to_call < raise_to <= min(
            stack, to_call + (villain_stack if villain_stack is not None else stack)) \
            and tree and has_next:
        # raise también disponible en el árbol (usando la equity inmediata)
        ev['raise'] = float((w * _raise_ev(
            raise_to, pot, hero_eq, villain_eq, w, to_call,
            response=response_fn)).sum())

    if candidates is not None:
        ok = set(candidates) | {'fold'}
        ev = {k: v for k, v in ev.items() if k in ok}

    return EvTable(ev=ev, pot=pot, hero_equity=equity_mean)
