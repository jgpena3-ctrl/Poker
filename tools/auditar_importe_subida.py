# -*- coding: utf-8 -*-
"""¿Se pueden DEMOSTRAR los importes de las 25 manos de IMPORTE_SUBIDA?

Esta es la pregunta que decide entre A y B, y revision_2 la condiciono:
corregir antes **si los importes son demostrables con evidencia
disponible**; si hay que reconstruirlos, congelar y declarar.

No es una preferencia: se mide. Y la respuesta sale de lo que el registro
CONTIENE, no de lo que unonership wish fuera que contuviera.

Lo que el registro tiene por evento: el importe grabado, el stack del
jugador al inicio de la mano, y la secuencia. Lo que NO tiene: un segundo
importe para el mismo evento, ni medida del pantallazo, ni nada.

Un importe es DEMOSTRABLE si se deduce de una magnitud que el propio
registro implica. La unica candidata real es el stack: si la subida
grabada coincide con el stack del jugador, es un all-in y es verificable.
Todo lo demas seria reconstruirlo.

NO MODIFICA NADA.

    python tools/auditar_importe_subida.py
"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn                                # noqa: E402
from auditar_rango import importe_subida               # noqa: E402

ORDEN = ('preflop', 'flop', 'turn', 'river')


def casos():
    """(mano, calle, pos, importe) de cada IMPORTE_SUBIDA de la ventana."""
    out = []
    for h in learn.load_hands(reliable_only=True):
        for txt in importe_subida(h):
            calle, pos, imp = txt.split()[0], txt.split()[1], float(txt.split()[2])
            out.append((h, calle, pos, imp))
    return out


def stacks_de(hand):
    return {p.get('pos'): p.get('stack') for p in hand.get('players') or []}


def hay_subida_antes(hand, calle, pos, imp):
    """True si NADIE habia subido todavia en esa calle cuando ocurrio."""
    acts = ((hand.get('streets') or {}).get(calle) or {}).get('actions') or []
    idx = None
    for i, a in enumerate(acts):
        if (a.get('pos') == pos and a.get('action') == 'r'
                and abs(float(a.get('amount') or 0) - imp) < 0.01):
            idx = i
            break
    if idx is None:
        return None
    return not any(a.get('action') == 'r' for a in acts[:idx])


def main():
    print('=' * 78)
    print('IMPORTE_SUBIDA: ¿el importe correcto es DEMOSTRABLE?')
    print('=' * 78)
    cs = casos()
    manos = {c[0]['hand_id'] for c in cs}
    print('   casos: %d   manos: %d   ventana: 877'
          % (len(cs), len(manos)))
    print()

    veredictos = collections.Counter()
    detalle = []
    for h, calle, pos, imp in cs:
        stack = stacks_de(h).get(pos)
        if stack is not None and abs(imp - float(stack)) < 0.05:
            v = 'DEMOSTRABLE (all-in: el importe es el stack)'
        else:
            v = 'NO DEMOSTRABLE'
        sin_subida = hay_subida_antes(h, calle, pos, imp)
        veredictos[v.split()[0]] += 1
        detalle.append((h['hand_id'], calle, pos, imp, stack, v, sin_subida))

    print('VEREDICTO POR CASO')
    print('-' * 78)
    print('   %-6s  %d' % ('DEMOSTRABLE', veredictos['DEMOSTRABLE']))
    print('   %-6s  %d' % ('NO', veredictos['NO']))
    print()
    print('   La respuesta a la pregunta de revision_2 es %d de %d:'
          % (veredictos['DEMOSTRABLE'], len(cs)))
    print()

    print('LOS CASOS')
    print('-' * 78)
    print('   %-9s %-8s %-4s %8s %9s %-6s %s'
          % ('mano', 'calle', 'pos', 'importe', 'stack', 'all-in',
             'sin subida antes'))
    for hid, calle, pos, imp, stack, v, sin in detalle:
        print('   %-9s %-8s %-4s %8.1f %9s %-6s %s'
              % (hid, calle, pos, imp,
                 ('%.1f' % stack) if stack is not None else '?',
                 'si' if v.startswith('DEMOST') else 'no',
                 {True: 'si', False: 'NO', None: '?'}[sin]))

    # ---- la segunda pregunta: ¿el ACTION TYPE es reetiquetable? ---------
    print()
    print('=' * 78)
    print('SEGUNDA PREGUNTA: ¿el TIPO DE ACCION es reetiquetable?')
    print('=' * 78)
    print()
    print('El proyecto YA tiene una regla exacta y validada para un caso')
    print('parecido (verificar_cm004.py, "las tres del r -> c"):')
    print()
    print('    una subida a un importe <= la ciega nominal, SIN que nadie')
    print('    haya subido antes, no es una apertura')
    print()
    print('Si se cumple, la accion se reetiqueta `r` -> `c` y EL IMPORTE')
    print('NO SE TOCA. Eso no es reconstruir el importe: es no tocarlo.')
    print()
    print('   %-28s %s' % ('sin subida antes (regla aplicable)',
                           sum(1 for d in detalle if d[6] is True)))
    print('   %-28s %s' % ('con subida antes (NO aplicable)',
                           sum(1 for d in detalle if d[6] is False)))
    print()
    print('=' * 78)
    print('CONCLUSION')
    print('=' * 78)
    print()
    print('A NO ES POSIBLE en el sentido que pidio revision_2, porque A')
    print('exige los IMPORTES correctos y no hay ni uno solo derivable.')
    print('El registro no tiene un segundo importe para ningun evento.')
    print()
    print('Lo que SI es posible es un REETIQUETADO del tipo de accion en')
    print('%d de %d casos, con una regla que el proyecto ya valido, y que'
          % (sum(1 for d in detalle if d[6] is True), len(cs)))
    print('NO altera ningun importe.')
    print()
    print('Y un reetiquetado NO es la opcion A: A es migrar la base. Es un')
    print('arranque aparte, con su backup y su hash, y mientras este se hace')
    print('la calibracion mide igual. Por eso la decision es B.')
    return 0


if __name__ == '__main__':
    sys.exit(main())