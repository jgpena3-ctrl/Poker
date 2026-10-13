# -*- coding: utf-8 -*-
"""Mide el `bb_check` perdido y propose la migracion (revision_1 punto 2).

`_reconstruct_preflop()` no puede emitir `bb_check`: desde UN snapshot, un BB
con `bet == ciega` es indistinguible de "el BB todavia no ha actuado" frente a
"el BB ya hizo check". Ambos estados dan `bb_bet = 1.0`.

Pero el camino incremental (`_detect_deltas`) si ve el check cuando el stack
cambia de estado. En la DB actual hay 187 `bb_check` del BB.

Falta un caso: manos cuyo preflop YA TERMINO (hay flop) y en las que el BB solo
tiene la ciega. Ahi el BB no puede "todavia no haber actuado": la calle se
cerro, y si no hizo fold (los folds si se detectan) hizo check.

Salida: conteo exacto y el listado, para la migracion.
"""
import collections
import importlib.util
import json
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

    registrados = perdidos = ambiguos = 0
    ids_perdidos = []
    por_jugador = collections.Counter()

    for h in hands:
        hid = h.get('hand_id', '?')
        st = h.get('streets', {}) or {}
        pf = (st.get('preflop') or {}).get('actions') or []
        flop = (st.get('flop') or {}).get('actions') or []
        board = (st.get('flop') or {}).get('board') or []
        if not pf:
            continue

        seq = learn._preflop_sequence(h)
        bbs = [(p, a, v, b) for p, a, v, b in seq if p == 'BB']
        # acciones propias del BB, excluyendo la ciega
        propias = [x for x in bbs if x[1] != 'b' or x[3]]

        if propias:
            registrados += 1
            continue

        preflop_cerrado = bool(flop) or bool(board)
        if preflop_cerrado:
            perdidos += 1
            ids_perdidos.append(hid)
            pos_bb = learn.player_of_pos(h, 'BB')
            if pos_bb:
                por_jugador[pos_bb] += 1
        else:
            ambiguos += 1

    total = registrados + perdidos + ambiguos
    print('ventana: %d manos con preflop' % total)
    print()
    print('  BB con accion propia registrada:      %4d  (%5.1f%%)'
          % (registrados, registrados / total * 100))
    print('  BB con check PERDIDO (flop ya existe): %4d  (%5.1f%%)'
          % (perdidos, perdidos / total * 100))
    print('  BB aun en preflop (ambiguo):          %4d  (%5.1f%%)'
          % (ambiguos, ambiguos / total * 100))
    print()
    if registrados + perdidos:
        subrep = perdidos / (registrados + perdidos) * 100
        print('  -> bb_check esta SUBREPRESENTADO un %.1f%%' % subrep)
        print('     (sobre %d eventos que&Iacute;stituyen el total real)'
              % (registrados + perdidos))
    print()
    print('jugadores afectados (top 8):')
    for nom, n in por_jugador.most_common(8):
        print('  %-20s %3d' % (nom, n))
    print()
    print('hand_ids afectados (%d):' % len(ids_perdidos))
    print('  ' + ', '.join(ids_perdidos[:30]))
    if len(ids_perdidos) > 30:
        print('  ... y %d mas' % (len(ids_perdidos) - 30))

    if '--json' in sys.argv:
        out = os.path.join(ROOT, 'data', 'bb_check_perdidos.json')
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'hand_ids': ids_perdidos,
                       'por_jugador': dict(por_jugador)}, f, indent=2)
        print('\n-> %s' % out)

    print()
    print('CONCLUSION')
    print('  El check del BB NO es recuperable desde el snapshot inicial de')
    print('  una mano, pero SI es recuperable a posteriori: si el preflop ya')
    print('  cerro y el BB no tiene accion propia, hizo check. La migracion')
    print('  anade ese evento con marca implicita, sin tocar el resto.')
    return 0


if __name__ == '__main__':
    sys.exit(main())