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

Etapa MVP 2 (parcial, pegar7 §14.7): `compute_evs(runout=True)` sustituye la
equity determinista por **equity a showdown con sorteo de runout** (todos los
turn+river restantes, MC), en las ramas pasivas (check/call). Sin pagos
intermedios: el árbol de decisiones de la siguiente calle queda pendiente
(anotado en ARQUITECTURA §11 #11). `runout=False` por defecto: el pipeline
de ~24 ms no cambia.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np

from .cards import card_id, cards_to_bits
from .hand_evaluator import (evaluate_batch, evaluate_hand, evaluate_n_batch,
                             legal_hands)
from .ranges import COMBO0, COMBO1, RangeState

BET_LABELS = ('bet_25', 'bet_50', 'bet_75')
ACTIONS = ('fold', 'check', 'call') + BET_LABELS + ('all_in',)


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
        pf = self.alpha * self.pf_p + (1 - self.alpha) * pf_e
        pc = self.alpha * self.pc_p + (1 - self.alpha) * pc_e
        pr = self.alpha * self.pr_p + (1 - self.alpha) * pr_e
        pr = np.clip(pr, 0.0, 0.45)
        pc = np.maximum(0.0, 1.0 - pf - pr)
        return pf, pc, pr


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

    MVP 2 parcial: el sorteo de runout se incorpora a la equity (las ramas
    pasivas de `compute_evs` la usan); no modela pagos intermedios.
    """
    hero = [card_id(c) for c in hero_codes]
    board = [card_id(c) for c in board_codes]
    restantes = 5 - len(board)
    if restantes <= 0:
        ids, w, hero_eq = _villain_arrays(hero_codes, board_codes,
                                          villain_reach)
        return float((hero_eq * w).sum())

    known = 0
    for c in hero + board:
        known |= 1 << c
    deck = np.asarray([c for c in range(52) if not (known >> c) & 1],
                      dtype=np.intp)
    legal = legal_hands(known)
    rng = np.random.default_rng(seed)
    if villain_reach is None or isinstance(villain_reach, RangeState):
        ids0 = legal
        w = np.full(len(legal), 1.0 / len(legal))
        if isinstance(villain_reach, RangeState):
            w = villain_reach.reach_blocked[ids0].astype(np.float64)
    else:
        arr = np.asarray(villain_reach, dtype=np.float64)
        if arr.shape != (1326,):
            raise ValueError(f'reach debe tener forma (1326,), tiene '
                             f'{arr.shape}')
        ids0 = legal[arr[legal] > 0]
        w = arr[ids0]
    if len(ids0) == 0:
        raise ValueError('rango rival sin combos legales')
    w = w / w.sum()
    ids0 = np.asarray(ids0, dtype=np.intp)

    k = min(int(n_combos), len(ids0))
    acc = 0.0
    total = 0
    hero_pair = np.asarray([[hero[0], hero[1]]], dtype=np.intp)
    brd = np.asarray(board, dtype=np.intp)
    for _ in range(n_runouts):
        sel = ids0[rng.choice(len(ids0), size=k, replace=True, p=w)]
        p0, p1 = COMBO0[sel], COMBO1[sel]
        run = _vector_runout(p0, p1, deck, rng, restantes)
        full = np.column_stack([p0, p1,
                                np.broadcast_to(brd, (k, len(brd))), run])
        scores = evaluate_n_batch(full)
        hero_full = np.column_stack([
            np.broadcast_to(hero_pair, (k, 2)),
            np.broadcast_to(brd, (k, len(brd))), run])
        hs = evaluate_n_batch(hero_full)
        acc += float((1.0 * (scores < hs) + 0.5 * (scores == hs)).sum())
        total += k
    return acc / total


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

        card2 = _vector_runout(p0, p1, deck, rng_f, 1, extra=card1)[:, 0]
        full7 = np.column_stack([p0, p1,
                                 np.broadcast_to(brd, (k, n_cartas)),
                                 card1, card2])
        hero7 = np.column_stack([
            np.broadcast_to(hero_pair, (k, 2)),
            np.broadcast_to(brd, (k, n_cartas)), card1, card2])
        sc7 = evaluate_n_batch(full7)
        eq7 = 1.0 * (sc7 < evaluate_n_batch(hero7)) + \
            0.5 * (sc7 == evaluate_n_batch(hero7))

        check_v = eq7 * pot
        bet_v = pf * pot + pc * (eq7 * (pot + 2 * amount) - amount) - pr * amount
        F = np.maximum(check_v, bet_v)
        np.add.at(sums, np.searchsorted(ids0, sel), F)
        counts[np.searchsorted(ids0, sel)] += 1
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
                bet_sizes=(0.25, 0.5, 0.75),
                response_fn=None, runout=False,
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
    pot           : bote antes de actuar el hero
    to_call       : fichas a pagar si hay un bet en curso (0 = sin bet)
    stack         : stack efectivo restante del hero
    response_fn   : (villain_eq, amount, pot) -> (pf, pc, pr) vectorizado;
                    None = `_response_array` (heurística). Perfiles:
                    `OracleResponse` (motor.behavior) con P(A|C) del rival.
    runout        : MVP 2 parcial — si True y faltan cartas del board, las
                    ramas pasivas (check/call) usan la equity a showdown con
                    sorteo de turn+river (`runout_equity`, MC). Las ramas
                    agresivas y el all_in conservan la equity determinista.
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
    ids, w, hero_eq = _villain_arrays(hero_codes, board_codes, villain_reach)
    villain_eq = 1.0 - hero_eq
    equity_mean = float((hero_eq * w).sum())
    hero_ids = [card_id(c) for c in hero_codes]
    board_ids = [card_id(c) for c in board_codes]
    has_next = len(board_ids) < 5

    ev: Dict[str, float] = {'fold': 0.0}

    if tree and has_next:
        def tree_tau(pot_s, stack_s, seed):
            tau, _mean = _tree_values(
                hero_ids, board_ids, ids, w, pot_s, stack_s, response_fn,
                n_street=tree_n_street, n_finals=tree_n_finals,
                frac=tree_frac, seed=seed)
            return tau

        if to_call <= 0:
            ev['check'] = float((w * tree_tau(pot, stack, 21)).sum())
        if to_call > 0:
            ev['call'] = float((w * tree_tau(pot + 2 * to_call,
                                             stack - to_call, 22)).sum()) \
                - to_call

        for idx, (frac, label) in enumerate(zip(bet_sizes, BET_LABELS)):
            amount = min(frac * pot, stack) if pot > 0 else 0.0
            if amount <= 0:
                ev[label] = 0.0
                continue
            if response_fn is None:
                pf, pc, pr = _response_array(villain_eq, amount, pot)
            else:
                pf, pc, pr = response_fn(villain_eq, amount, pot)
            tau = tree_tau(pot + 2 * amount, stack - amount, 30 + idx)
            branch = pf * pot + pc * tau - pr * amount
            ev[label] = float((w * branch).sum())
    else:
        if runout and has_next:
            equity_mean_r = runout_equity(
                hero_codes, board_codes, villain_reach,
                n_runouts=max(1, n_runouts))
        else:
            equity_mean_r = equity_mean

        if to_call <= 0:
            ev['check'] = equity_mean_r * pot
        if to_call > 0:
            ev['call'] = equity_mean_r * (pot + 2 * to_call) - to_call

        for frac, label in zip(bet_sizes, BET_LABELS):
            amount = min(frac * pot, stack) if pot > 0 else 0.0
            ev[label] = _branch_ev(amount, pot, hero_eq, villain_eq, w,
                                   response=response_fn)

    ev['all_in'] = _branch_ev(stack, pot, hero_eq, villain_eq, w,
                              all_in=True, response=response_fn)

    return EvTable(ev=ev, pot=pot, hero_equity=equity_mean)
