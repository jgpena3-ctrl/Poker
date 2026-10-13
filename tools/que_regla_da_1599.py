"""¿Qué regla del doc §6.1 da realmente 1599/825/64?

revision_1 §1 señala que `comparar_folds.doc_events` implementa la TERCERA
regla del doc ("sólo importes > 1.0") pero la etiqueta como la SEGUNDA
("ignorando sólo la ciega del BB"). Este script mide las TRES por separado
para ver cuál —o cuáles— producen 1599/825/64.

Reglas de PROYECTO.md §6.1
--------------------------
R1 "Actual"        : cuenta como subida todo 'b'/'r' (incluida la ciega).
R2 "Ignorando sólo la ciega del BB" : la ciega NO cuenta como subida, pero
                     SÍ se emite como evento (decisión del BB).
R3 "Sólo importes > 1.0" : cuenta como subida los 'b'/'r' con importe > 1BB.
                     La ciega (1.0) deja de contar, pero tampoco se salta.
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

OBJETIVO = (1599, 825, 64)   # tabla "Corregida" del doc §6.1


def _seq(hand):
    return [(p, a, m) for p, a, m, _b in learn._preflop_sequence(hand)]


def _run(hand, is_raise):
    seq = _seq(hand)
    out, decided = [], set()
    for i, (pos, act, amount) in enumerate(seq):
        if pos in decided:
            continue
        decided.add(pos)
        raises = sum(1 for k, (_p, a, m) in enumerate(seq[:i])
                     if a in ('b', 'r') and is_raise(k, _p, a, m))
        limps = sum(1 for _p, a, _m in seq[:i] if a == 'c')
        cat, den = learn.classify_first_action(act, amount, raises, limps,
                                              learn.BB)
        out.append((cat, den))
    return out


def r1_actual(k, p, a, m):
    """Toda 'b'/'r' cuenta como subida, ciega incluida."""
    return a in ('b', 'r')


def r2_sin_ciega(k, p, a, m):
    """Ignora SÓLO la ciega del BB; la ciega sigue siendo un evento emitido."""
    return a in ('b', 'r') and not (k == 0 and p == 'BB'
                                    and m <= learn.BB + 1e-9)


def r3_importes(k, p, a, m):
    """Sólo 'b'/'r' con importe > 1BB cuentan como subida."""
    return a in ('b', 'r') and m > learn.BB + 1e-9


REGLAS = (('R1 actual (con ciega)', r1_actual),
          ('R2 ignorando ciega BB', r2_sin_ciega),
          ('R3 importes > 1.0', r3_importes))


def main():
    hands = learn.load_hands(reliable_only=True)
    print(f'ventana: {len(hands)} manos\n')
    print(f'{"regla":<26}{"fold/nr":>9}{"vs_open":>9}{"vs_3bet":>9}'
          f'{"eventos":>9}   ¿objetivo?')
    print('-' * 78)
    for name, fn in REGLAS:
        c = collections.Counter()
        for h in hands:
            for cat, den in _run(h, fn):
                c[(cat, den)] += 1
        f1 = c[('fold', 'no_raise')]
        f2 = c[('fold_vs_open', 'facing_open')]
        f3 = c[('fold_vs_3bet', 'facing_3bet')]
        tot = sum(c.values())
        hit = 'SÍ' if (f1, f2, f3) == OBJETIVO else 'no'
        print(f'{name:<26}{f1:>9}{f2:>9}{f3:>9}{tot:>9}   {hit}')
    print(f'\nObjetivo del doc §6.1 ("Corregida"): '
          f'{OBJETIVO[0]} / {OBJETIVO[1]} / {OBJETIVO[2]}')

    print('\n--- mano de control: dónde R2 y R3 divergen ---')
    mostradas = 0
    for h in hands:
        r2 = _run(h, r2_sin_ciega)
        r3 = _run(h, r3_importes)
        if r2 != r3:
            hid = h.get('hand_id')
            print(f'{hid}: seq={[(p, a, m) for p, a, m in _seq(h)]}')
            print(f'   R2 {[c for c, _d in r2]}')
            print(f'   R3 {[c for c, _d in r3]}')
            mostradas += 1
            if mostradas >= 3:
                break
    if mostradas == 0:
        print('R2 y R3 coinciden en todas las manos de la ventana fiable.')

    print('\n--- ¿difieren R2 y R3 sólo porque la ciega es la primera acción? ---')
    dif_por_tipo = collections.Counter()
    for h in hands:
        if _run(h, r2_sin_ciega) != _run(h, r3_importes):
            for (p, a, m) in _seq(h):
                if a in ('b', 'r') and m <= learn.BB + 1e-9:
                    dif_por_tipo['b<=1BB (limpe corto o ciega)'] += 1
                    break
    for k, v in dif_por_tipo.items():
        print(f'  {k}: {v} manos')
    return 0


if __name__ == '__main__':
    sys.exit(main())