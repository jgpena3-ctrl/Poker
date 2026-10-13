"""Divergencia de cifras: implementación actual vs simulación de PROYECTO.md §6.1.

revision_1 §6 pide exactamente esto antes de dar por buenas las cifras nuevas:
sin saber dónde divergen los folds, no se puede afirmar si el arreglo es
correcto o si hay un bug.

Salida
------
- Totales por categoría (no_raise / facing_open / facing_3bet) de ambas reglas.
- Listado de manos y eventos donde divergen, con el motivo.

Reglas comparadas
-----------------
LEGACY  : la simulación del doc — cuenta como subida cualquier 'b'/'r', incluida
          la ciega del BB, y NO salta la ciega como evento.
CURRENT : el código actual (`learn.preflop_events`).
"""
import collections
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    'learn', os.path.join(ROOT, 'motor', 'learn.py'))
learn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(learn)

CIEGA_FOLDS = ('fold', 'fold_vs_open', 'fold_vs_3bet')


def legacy_events(hand, bb=learn.BB):
    """Simulación de PROYECTO.md §6.1 (prefijo `sum(1 for ... if a in ('b','r'))`).

    Devuelve [(pos, category, denom)] con la ciega del BB contada como
    apertura y como decisión del jugador.
    """
    seq = [(p, a, m) for p, a, m, _b in learn._preflop_sequence(hand)]
    out, decided = [], set()
    for i, (pos, act, amount) in enumerate(seq):
        if pos in decided:
            continue
        decided.add(pos)
        raises = sum(1 for _p, a, _m in seq[:i] if a in ('b', 'r'))
        limps = sum(1 for _p, a, _m in seq[:i] if a == 'c')
        cat, den = learn.classify_first_action(act, amount, raises, limps, bb)
        out.append((pos, cat, den))
    return out


def current_events(hand, bb=learn.BB):
    """El código actual: salta la ciega y acumula limps correctamente."""
    return [(ev.pos, ev.category, ev.denom) for ev in
            learn.preflop_events(hand, bb)]


def doc_events(hand, bb=learn.BB):
    """Simulación EXACTA de PROYECTO.md §6.1 tabla "Corregida".

    Regla del doc: "Contando una subida sólo cuando el importe supera la ciega"
    → `a in ('b','r') and m > bb`. NO salta la ciega del BB como evento (la
    cuenta como `open`), por eso la tabla del doc da 1599/825/64.
    """
    seq = [(p, a, m) for p, a, m, _b in learn._preflop_sequence(hand)]
    out, decided = [], set()
    for i, (pos, act, amount) in enumerate(seq):
        if pos in decided:
            continue
        decided.add(pos)
        raises = sum(1 for _p, a, m in seq[:i]
                     if a in ('b', 'r') and m > bb + 1e-9)
        limps = sum(1 for _p, a, m in seq[:i] if a == 'c')
        cat, den = learn.classify_first_action(act, amount, raises, limps, bb)
        out.append((pos, cat, den))
    return out


def trace_hand(hand_id):
    """Traza una mano concreta por las tres reglas (p.ej. H_0340)."""
    for h in learn.load_hands(reliable_only=True):
        if h.get('hand_id') != hand_id:
            continue
        print(f'--- {hand_id} ---')
        seq = learn._preflop_sequence(h)
        for i, (p, a, m, b) in enumerate(seq):
            print(f'  seq[{i}] = ({p!r}, {a!r}, {m}, blind={b})')
        for name, fn in (('legacy', legacy_events), ('doc', doc_events),
                         ('current', current_events)):
            print(f'  {name:<8}: {[(p, c, d) for p, c, d in fn(h)]}')
        return 0
    print(f'{hand_id} no encontrada en la ventana fiable')
    return 1


def main():
    if '--traza' in sys.argv:
        i = sys.argv.index('--traza')
        return trace_hand(sys.argv[i + 1])
    hands = learn.load_hands(reliable_only=True)
    tot_leg = collections.Counter()
    tot_doc = collections.Counter()
    tot_cur = collections.Counter()
    divergen = []

    for h in hands:
        hid = h.get('hand_id', '?')
        leg = legacy_events(h)
        doc = doc_events(h)
        cur = current_events(h)
        for _p, cat, den in leg:
            tot_leg[(cat, den)] += 1
        for _p, cat, den in doc:
            tot_doc[(cat, den)] += 1
        for _p, cat, den in cur:
            tot_cur[(cat, den)] += 1
        if [(p, c) for p, c, _d in leg] != [(p, c) for p, c, _d in cur]:
            divergen.append((hid, leg, cur))

    print(f'manos: {len(hands)}   con divergencia: {len(divergen)}')
    print()
    print(f'{"categoria":<14}{"denominador":<14}{"doc":>8}{"legacy":>8}'
          f'{"current":>8}')
    print('-' * 52)
    for cat, den in (('fold', 'no_raise'),
                     ('fold_vs_open', 'facing_open'),
                     ('fold_vs_3bet', 'facing_3bet')):
        d = tot_doc.get((cat, den), 0)
        a = tot_leg.get((cat, den), 0)
        b = tot_cur.get((cat, den), 0)
        print(f'{cat:<14}{den:<14}{d:>8}{a:>8}{b:>8}')
    tot_d = sum(tot_doc.values())
    tot_a = sum(tot_leg.values())
    tot_b = sum(tot_cur.values())
    print('-' * 52)
    print(f'{"EVENTOS":<28}{tot_d:>8}{tot_a:>8}{tot_b:>8}')

    print()
    print('denominadores:')
    print(f'{"":<16}{"doc":>7}{"legacy":>8}{"current":>9}')
    for dn in learn.DENOM_ORDER:
        d = sum(v for (_c, dd), v in tot_doc.items() if dd == dn)
        a = sum(v for (_c, dd), v in tot_leg.items() if dd == dn)
        b = sum(v for (_c, dd), v in tot_cur.items() if dd == dn)
        print(f'  {dn:<16}{d:>7}{a:>8}{b:>9}')

    print()
    print('categorías (doc -> legacy -> current), sólo las que cambian:')
    cats = sorted({c for c, _d in list(tot_leg) + list(tot_cur)
                   + list(tot_doc)})
    for cat in cats:
        d = sum(v for (c, _d), v in tot_doc.items() if c == cat)
        a = sum(v for (c, _d), v in tot_leg.items() if c == cat)
        b = sum(v for (c, _d), v in tot_cur.items() if c == cat)
        if a != b or d != b:
            print(f'  {cat:<14}{d:>6} -> {a:>6} -> {b:>6}')

    print()
    print('causas de divergencia legacy -> current (por par pos+categoria):')
    causas = collections.Counter()
    for hid, leg, cur in divergen:
        lp = {(p, c) for p, c, _d in leg}
        cp = {(p, c) for p, c, _d in cur}
        for item in lp - cp:
            causas[('solo_legacy', item[1])] += 1
        for item in cp - lp:
            causas[('solo_actual', item[1])] += 1
    for (kind, cat), n in causas.most_common():
        print(f'  {kind:<12}{cat:<14}{n:>5}')

    print()
    print('doc -> current: diferencias exactas (posicion + categoria):')
    diff = collections.Counter()
    for h in hands:
        dp = {(p, c) for p, c, _d in doc_events(h)}
        cp = {(p, c) for p, c, _d in current_events(h)}
        for item in dp - cp:
            diff[('solo_doc',) + item] += 1
        for item in cp - dp:
            diff[('solo_current',) + item] += 1
    for key, n in diff.most_common(24):
        print(f'  {key[0]:<13}{key[1]:<6}{key[2]:<14}{n:>5}')

    print()
    print('primeras 12 manos divergentes:')
    for hid, leg, cur in divergen[:12]:
        print(f'  {hid}')
        print(f'    legacy : {[(p, c) for p, c, _d in leg]}')
        print(f'    actual : {[(p, c) for p, c, _d in cur]}')

    if '--detalle' in sys.argv:
        print()
        print('=== TODAS las divergencias ===')
        for hid, leg, cur in divergen:
            print(f'{hid}\n  legacy {[(p, c) for p, c, _d in leg]}'
                  f'\n  actual {[(p, c) for p, c, _d in cur]}')

    return 0


if __name__ == '__main__':
    sys.exit(main())