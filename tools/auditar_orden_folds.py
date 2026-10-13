# -*- coding: utf-8 -*-
"""¿Contamina el orden de los folds las categorias? (revision_1 §6, T2)

`_reconstruct_preflop()` emite TODOS los folds primero, en orden fijo de
posicion, y despues los movimientos voluntarios. En el juego real un fold
puede ocurrir DESPUES de una subida (el clasico c-b-f).

Si el fold queda grabado ANTES de la subida, `preflop_events` lo cuenta con
raises_before=0 y lo clasifica `fold`/no_raise, cuando en realidad enfrentaba
una apuesta y le corresponde `fold_vs_open`.

Este script no puede saber cual era el orden real (no se graba), asi que mide
cuantos folds quedan ANTES de la primera subida existiendo subida posterior:
son los candidatos a misclasificacion. El limite inferior es cero y el
superior es este numero.
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


def main():
    hands = learn.load_hands(reliable_only=True)

    folds_antes_de_subida = 0      # candidatos: fold precedes a raise
    folds_totales = 0
    folds_despues_de_subida = 0   # bien clasificados
    manos_con_subida = 0
    manos_candidatas = 0
    ejemplos = []

    for h in hands:
        seq = list(learn._preflop_sequence(h))
        raises = limps = callers = 0
        voluntary = False
        idx_primer_raise = None

        for i, (pos, act, amt, blind) in enumerate(seq):
            es_ciega = learn._es_ciega_bb(i, pos, act, amt, blind, voluntary)
            if es_ciega:
                continue
            if act == 'r' and idx_primer_raise is None:
                idx_primer_raise = i
            if act == 'f':
                folds_totales += 1
                # ¿hubo una subida antes de este fold?
                if raises == 0:
                    # ¿pero la hay despues? -> candidato a error
                    hay_subida_despues = any(
                        a == 'r' for _p, a, _m, _b in seq[i + 1:])
                    if hay_subida_despues:
                        folds_antes_de_subida += 1
                        if len(ejemplos) < 5:
                            ejemplos.append(
                                (h.get('hand_id'),
                                 [(p, a, m) for p, a, m, _b in seq]))
                else:
                    folds_despues_de_subida += 1
            if act in ('b', 'r'):
                raises += 1
                voluntary = True
            elif act == 'c':
                if raises == 0:
                    limps += 1
                else:
                    callers += 1
                voluntary = True

        if any(a == 'r' for _p, a, _m, _b in seq):
            manos_con_subida += 1
            if any(a == 'r' for _p, a, _m, _b in seq):
                pass
        if any(a == 'r' for _p, a, _m, _b in seq) and \
                folds_antes_de_subida > 0:
            pass

    # Cuantas manos tienen al menos un fold antes de una subida
    n = 0
    for h in hands:
        seq = list(learn._preflop_sequence(h))
        raises = 0
        voluntary = False
        cand = False
        for i, (pos, act, amt, blind) in enumerate(seq):
            if learn._es_ciega_bb(i, pos, act, amt, blind, voluntary):
                continue
            if act == 'f' and raises == 0 and \
                    any(a == 'r' for _p, a, _m, _b in seq[i + 1:]):
                cand = True
            if act in ('b', 'r'):
                raises += 1
                voluntary = True
            elif act == 'c':
                voluntary = True
        if cand:
            n += 1

    print(f'ventana: {len(hands)} manos')
    print(f'manos con alguna subida preflop: {manos_con_subida}')
    print()
    print(f'folds totales:                          {folds_totales}')
    print(f'  con subida ANTES (bien clasificados): {folds_despues_de_subida}')
    print(f'  sin subida antes PERO con subida luego:{folds_antes_de_subida}'
          f'   <-- candidatos a error')
    print()
    print(f'manos con al menos un fold sospechoso:  {n}'
          f'  ({n / len(hands) * 100:.1f}%)')
    print()
    print('ejemplos:')
    for hid, seq in ejemplos:
        print(f'  {hid}: {seq}')
    print()
    print('LIMITE: este numero es una cota SUPERIOR. No se puede saber')
    print('cuantos de esos folds ocurrieron de verdad antes de la subida')
    print('(folding antes de una subida es totalmente legitimo). Lo que')
    print('si es certain es que el recorder NO puede distinguirlos, porque')
    print('emite los folds antes de saber si habia subida.')

    # ------------------------------------------------------------------
    # De donde viene cada mano: hay dos caminos de produccion distintos.
    # ------------------------------------------------------------------
    print()
    print('=' * 68)
    print('ORIGEN DE LA SECUENCIA: hay dos caminos de produccion')
    print('=' * 68)
    print("""
El recorder tiene dos caminos:
  A) `_detect_deltas` -> incremental por frames. Cada accion se anade cuando
     se detecta, asi que CONSERVA el orden real (UTG:f, MP:f, CO:b, BTN:f...)
  B) `_reconstruct_preflop` -> reconstruye desde UN snapshot: emite TODOS los
     folds primero, luego la ciega, luego los voluntarios en orden de posicion.

Si una mano empieza con un bloque de folds y despues aparecen los
voluntarios, viene de (B). Si las acciones estan intercaladas, viene de (A).
""")
    reconstruct = incremental = ambiguo = 0
    for h in hands:
        seq = [(a, m) for _p, a, m, _b in learn._preflop_sequence(h)]
        if not seq:
            continue
        first_vol = next((i for i, (a, m) in enumerate(seq)
                          if a in ('b', 'r') and m > 1.0), None)
        if first_vol is None:
            ambiguo += 1
            continue
        antes = [a for a, _m in seq[:first_vol]]
        if all(a in ('f', 'c') for a in antes) and any(a == 'f' for a in antes):
            reconstruct += 1
        else:
            incremental += 1
    total = reconstruct + incremental + ambiguo
    print(f'manos de la ventana:                       {total}')
    print(f'  (B) reconstruct_preflop  folds primero:   {reconstruct}'
          f'  ({reconstruct / total * 100:.1f}%)')
    print(f'  (A) _detect_deltas     orden real:       {incremental}'
          f'  ({incremental / total * 100:.1f}%)')
    print(f'  sin acciones voluntarias (ambiguo):       {ambiguo}')
    return 0


if __name__ == '__main__':
    sys.exit(main())