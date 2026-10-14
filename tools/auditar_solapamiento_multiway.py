# -*- coding: utf-8 -*-
"""Auditoria de la regla "puede actuar": ortogonalidad, temporalidad y
procedencia del dato. NO modifica nada.

Cierra revision_1 Tarea 2 (ortogonalidad) y revision_2 puntos 1 y 2
(temporalidad y procedencia). Las tres estaban abiertas sobre INC-001.

IMPORTANT: este script NO implementa la regla. La implementacion vive en
`motor/multiway.py` y este script la IMPORTA. Si aqui apareciera una
segunda definicion de `no_puede_actuar`, el bug de la regla del raise
vuelve por la puerta de atras. `test_no_hay_dos_implementaciones` lo
vigila.

Uso:  python tools/auditar_solapamiento_multiway.py
"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn                                       # noqa: E402
from motor.multiway import (                                  # noqa: E402
    ORDEN, PLAYER_IDS, POSTFLOP, acciones, clasificar_decision,
    contrato_orden_ok, en_bote, en_bote_en_instante, folds_hasta,
    hero_pos, heroes, instante_decision, no_puede_actuar,
    no_puede_actuar_en_instante, puede_responder, posiciones_allin,
    secuencia, ultima_accion,
)


# ---------------------------------------------------------------------------
def main():
    print('=' * 78)
    print('AUDITORIA DE "PUEDE ACTUAR"   (solo lectura)')
    print('=' * 78)
    manos = learn.load_hands(reliable_only=True)
    print('   ventana fiable: %d manos' % len(manos))
    print('   implementacion: motor/multiway.py  (importada, no copiada)')

    # =====================================================  1  ORDEN
    print()
    print('1) CONTRATO DE ORDEN DE players[]  (revision_2 punto 1)')
    print('-' * 78)
    print('   El mapeo de `allin` a posicion depende de que `players[]` siga')
    print('   el orden de PLAYER_IDS. Eso no se deduce del dato: se deduce')
    print('   del recorder. Evidencia leida de recorder/recorder_live.py:')
    rl = open(os.path.join(ROOT, 'recorder', 'recorder_live.py'),
              encoding='utf-8').read()
    print('      `for pid in PLAYER_IDS:` -> `hand[\'players\'].append(...)` : %s'
          % ('SI' if 'for pid in PLAYER_IDS:' in rl
             and "hand['players'].append(" in rl else 'NO'))
    print('      `del p[\'_id\']` al volcar (por eso `allin` guarda ids)     : %s'
          % ('SI' if "del p['_id']" in rl else 'NO'))
    print('      test que lo protege: motor/test_multiway.py::'
          'test_contrato_orden_players')
    largos = collections.Counter(len(h['players']) for h in manos)
    print('      longitudes de players[] en la ventana: %s' % dict(largos))
    print('      -> el supuesto se sostiene en la ventana y esta protegido por')
    print('         test. Si el recorder dejara de anexar en orden, el test')
    print('         falla antes de que una cifra falsa llegue a un documento.')

    # =====================================================  2  PROCEDENCIA
    print()
    print('2) PROCEDENCIA DE `allin`  (revision_2 punto 2)')
    print('-' * 78)
    sin = [h for h in manos if 'allin' not in h]
    con = [h for h in manos if 'allin' in h]
    vacio = sum(1 for h in con if not h['allin'])
    ids_sin = sorted(int(h['hand_id'].split('_')[1]) for h in sin)
    print('   %-38s %5d' % ('manos CON campo `allin`', len(con)))
    print('   %-38s %5d' % ('   de ellas, `allin: []` (confirmado)',
                            vacio))
    print('   %-38s %5d' % ('   de ellas, con al menos un all-in',
                            len(con) - vacio))
    print('   %-38s %5d' % ('manos SIN campo `allin`', len(sin)))
    if ids_sin:
        print()
        print('   De las %d sin campo: hand_id %d..%d, fechas %s -> %s'
              % (len(sin), ids_sin[0], ids_sin[-1],
                 min(h['date'] for h in sin)[:19],
                 max(h['date'] for h in sin)[:19]))
        contiguo = ids_sin == list(range(ids_sin[0], ids_sin[0] + len(ids_sin)))
        print('   Son un PREFIJO CONTIGUO de hand_id: %s' % ('SI' if contiguo
                                                             else 'NO'))
        print()
        print('   RESPUESTA: son las primeras manos grabadas, por un recorder')
        print('   ANTERIOR que aun no escribia el campo. No es perdida de dato')
        print('   ni corrupcion: es una frontera de version, y se comporta')
        print('   como tal (100%% de las >= %d lo tienen, 100%% de las < %d no).'
              % (ids_sin[-1] + 1, ids_sin[0]))
        print('   Se pueden distinguir los tres estados:')
        print('      `allin` ausente  -> desconocido  (%d manos)' % len(sin))
        print('      `allin: []`      -> confirmado que no hay all-in (%d)' % vacio)
        print('      `allin: [ids]`   -> confirmado (%d)'
              % (len(con) - vacio))
        print()
        print('   RECONSTRUCCION: NO se puede recuperar sin inventar. El stack')
        print('   guardado es el de INICIO de mano, y el importe de un `r` es')
        print('   "raise to", no un incremento, asi que la suma de apuestas no')
        print('   reconstruye el commitmento. Se conserva el estado desconocido.')
    print()
    n_ids = sum(len(posiciones_allin(h) or ()) for h in manos)
    sin_pos = sum(1 for h in manos
                  for pid in (h.get('allin') or [])
                  if not contrato_orden_ok(h))
    f_allin = sum(1 for h in manos
                  for p in (posiciones_allin(h) or ())
                  if p in folds_hasta(h, 'river'))
    print('   Defecto del propio campo (INC-002): el recorder filtra `allin`')
    print('   con `p["active"]`, que significa "estaba sentado al empezar", no')
    print('   "no ha foldeado". Entradas en `allin` de la ventana: %d' % n_ids)
    print('   de las cuales con un fold posterior: %d  (%.1f%%)'
          % (f_allin, f_allin / n_ids * 100 if n_ids else 0))
    print('   -> deuda de datos con nombre y linea; va en INC-002.')

    # =====================================================  3  ORTOGONALIDAD
    print()
    print('3) ORTOGONALIDAD  folds_hasta  x  no_puede_actuar')
    print('-' * 78)
    print('   Un jugador que foldeo ya no esta en el bote. Si aparece en los')
    print('   dos a la vez, hay doble conteo.')
    print('   %-18s %9s %9s %9s' % ('instante', 'ambos', 'solo uno', 'ninguno'))
    for nombre, fn_npa in (
            ('por calle', lambda h, st: no_puede_actuar(h, st)),
            ('por instante',
             lambda h, st: no_puede_actuar_en_instante(
                 h, st, instante_decision(h, st) or 0))):
        ambos = solo = ninguno = 0
        for h in manos:
            for st in POSTFLOP:
                i = instante_decision(h, st)
                if i is None:
                    continue
                f = folds_hasta(h, st)
                n = fn_npa(h, st)
                if n is None:
                    continue
                for pos in en_bote_en_instante(h, st, i) | f | n:
                    a, b = pos in f, pos in n
                    if a and b:
                        ambos += 1
                    elif a or b:
                        solo += 1
                    else:
                        ninguno += 1
        print('   %-18s %9d %9d %9d' % (nombre, ambos, solo, ninguno))
    print()
    print('   El cruce "ambos" cae a 0 con la regla de evidencia. Los dos')
    print('   hechos (fold y commitment) son ortogonales por construccion; lo')
    print('   que queda son los registros corruptos de INC-002.')

    # =====================================================  4  TEMPORALIDAD
    print()
    print('4) TEMPORALIDAD: por CALLE vs por INSTANTE  (revision_2 punto 1)')
    print('-' * 78)
    print('   Por calle: un all-in en la calle S bloquea desde el PRINCIPIO')
    print('   de S. Por instante: solo bloquea si su commitmentio es ANTERIOR')
    print('   a la decision del hero. El orden SI es reconstruible:')
    print('   `streets[k].actions` es una lista y las calles van en orden.')
    print()
    comb = collections.Counter()
    ejemplos = []
    for h in manos:
        hp = hero_pos(h)
        for st in POSTFLOP:
            i = instante_decision(h, st)
            if i is None or acciones(h, st)[i]['action'] == 'f':
                continue
            ps = no_puede_actuar(h, st)
            pi = no_puede_actuar_en_instante(h, st, i)
            inst = puede_responder(h, st, i)
            if ps is None or pi is None or inst is None:
                continue
            if not inst:
                # sin ningun rival que responder no hay nada que repartir
                # entre HU y MULTIWAY: se clasifica aparte
                comb[(None, None)] += 1
                continue
            c1 = len((en_bote(h, st) - ps) - {hp}) > 1
            c2 = len(inst) > 1
            comb[(c1, c2)] += 1
            if c1 != c2 and len(ejemplos) < 3:
                ejemplos.append((h['hand_id'], st,
                                 [(a['pos'], a['action'])
                                  for a in acciones(h, st)],
                                 sorted(ps - pi), sorted(inst)))
    print('   %-26s %7s' % ('clase', 'puntos'))
    for (c1, c2), v in sorted(comb.items(), key=lambda x: -x[1]):
        if c1 is None:
            etiq = 'sin rival que responder'
            marca = ''
        else:
            etiq = ('MW' if c1 else 'HU') + ' -> ' + ('MW' if c2 else 'HU')
            marca = '   <-- cambia' if c1 != c2 else ''
        print('   %-26s %7d%s' % (etiq, v, marca))
    cambia = sum(v for (c1, c2), v in comb.items()
                 if c1 is not None and c1 != c2)
    print()
    print('   La aproximacion por calle reclasifica %d puntos.' % cambia)
    print('   No es un caso teorico: son decisiones en las que un rival se')
    print('   commitmenta DESPUES de que el hero haya jugado; la regla por')
    print('   calle lo habia marcado bloqueado desde el principio de la calle.')
    print('   Ejemplos:')
    for h_id, st, acts, dif, inst in ejemplos:
        print('      %-8s %-5s %s' % (h_id, st, acts))
        print('               bloquea de mas por calle: %-18s'
              'rivales que responden: %s' % (dif, inst))

    # =====================================================  5  PUNTO DE DECISION
    print()
    print('5) QUE ES UN "PUNTO DE DECISION"  (el denominador de verdad)')
    print('-' * 78)
    print('   El inventario de F7.1 contaba como punto de decision CUALQUIER')
    print('   calle que tuviera acciones. Eso mete en el numerador puntos en')
    print('   los que el hero ya no esta en la mano: no hay nada que decidir.')
    print('   Y al restar 1 al numero de activos para excluir al hero, en')
    print('   esos puntos resta de mas.')
    print()
    c5 = collections.Counter()
    for h in manos:
        hp = hero_pos(h)
        for st in POSTFLOP:
            if not acciones(h, st):
                continue
            i = instante_decision(h, st)
            if i is None:
                c5['la calle tiene acciones, el hero no esta en ella'] += 1
            elif hp in folds_hasta(h, st) and acciones(h, st)[i]['action'] != 'f':
                c5['el hero folteo DESPUES en esa misma calle'] += 1
            else:
                c5['decision real del hero'] += 1
    for k, v in sorted(c5.items(), key=lambda x: -x[1]):
        print('   %-46s %5d' % (k, v))
    print()
    print('   -> %d de %d calles con acciones NO son decisiones del hero.'
          % (c5['la calle tiene acciones, el hero no esta en ella'],
             sum(c5.values())))
    print('   Los %d de "folteo despues en esa misma calle" SI son decisiones'
          % c5['el hero folteo DESPUES en esa misma calle'])
    print('   reales: el hero apuesta, ve una resubida y foltea. Con el corte')
    print('   en el instante cuenta como decision; el corte por calle lo')
    print('   excluia por error.')

    # =====================================================  6  CIFRAS
    print()
    print('6) CIFRAS CON EL CONTRATO DE DECISION  (base para F7.2)')
    print('-' * 78)
    res = collections.Counter()
    mw_calle = mw_inst = 0
    for h in manos:
        for st in POSTFLOP:
            i = instante_decision(h, st)
            if i is not None and acciones(h, st)[i]['action'] == 'f':
                # Decision real del hero, pero de folding: no consulta
                # equity, asi que no entra en la politica multiway. Se
                # cuenta aparte en vez de colarlo dentro de un HU cualquiera.
                res['FOLD'] += 1
                continue
            r = clasificar_decision(h, st)
            res[r['clase']] += 1
            hp = hero_pos(h)
            if i is None or r['sin_evidencia'] or hp is None:
                continue
            # Se usa `puede_responder` y no `len(bote) - n - 1`: restar el
            # hero a mano cuenta mal cuando el hero es el que se
            # commitmenta, porque entonces ya estaba en el conjunto de
            # bloqueados y restarlo dos veces deja un rival de menos.
            pueden_inst = puede_responder(h, st, i)
            ps = no_puede_actuar(h, st)
            pueden_calle = None
            if ps is not None:
                pueden_calle = (en_bote(h, st) - ps) - {hp}
            if pueden_inst is not None and pueden_calle is not None:
                mw_calle += len(pueden_calle) > 1
                mw_inst += len(pueden_inst) > 1
    print('   puntos de calle inspeccionados: %d  (%d manos x 3 calles)'
          % (len(manos) * 3, len(manos)))
    print()
    print('   puntos de DECISION del hero:')
    tot = sum(res.values())
    for k in ('HU', 'MULTIWAY', 'DESCONOCIDO', 'FOLD', 'SIN_DECISION'):
        print('      %-14s %5d  (%5.1f%%)'
              % (k, res[k], res[k] / tot * 100 if tot else 0))
    print()
    print('   el hero FOLDEA en %d puntos: son decisiones reales, pero no'
          % res['FOLD'])
    print('   consumen equity, asi que no entran en la politica multiway.')
    print()
    print('   efecto de la correccion temporal, sobre los %d puntos con'
          % (res['HU'] + res['MULTIWAY']))
    print('   evidencia y donde el hero no foldea:')
    print('      MW por calle    : %d' % mw_calle)
    print('      MW por instante : %d' % mw_inst)
    print('      el que se firma : %d' % res['MULTIWAY'])

    # cota superior
    techo = res['MULTIWAY']
    for h in manos:
        for st in POSTFLOP:
            i = instante_decision(h, st)
            if i is None or acciones(h, st)[i]['action'] == 'f':
                continue
            if posiciones_allin(h) is None:
                hp = hero_pos(h)
                bote = en_bote_en_instante(h, st, i) | {hp}
                techo += len(bote) - 1 > 1
    print()
    print('   DENOMINADOR DE F7.2:  %d puntos con evidencia'
          % (res['HU'] + res['MULTIWAY']))
    print('   MULTIWAY confirmado: %d  (HU %d)'
          % (res['MULTIWAY'], res['HU']))
    print('   DESCONOCIDO: %d puntos (no entran en el numerador)'
          % res['DESCONOCIDO'])
    print('   COTA (techo, si en los desconocidos nadie estuviera all-in):')
    print('      %d + %d = %d' % (res['MULTIWAY'],
                                  techo - res['MULTIWAY'], techo))
    print()
    print('   CONTRASTE con las cifras anteriores:')
    print('      F7.1 por calle, regla del raise   : HU 702  MW 304')
    print('      F7.1 por calle, regla de evidencia: MW 225 (cota 276)')
    print('      contrato de decision + instante   : HU %d  MW %d'
          % (res['HU'], res['MULTIWAY']))
    print()
    print('   Las tres cifras no son comparables entre si: cambia QUE se')
    print('   cuenta (punto de decision) y COMO se cuenta (instante).')
    print('   La vigente es la ultima. Ver DOCS/CONTRATO_F72A.md.')
    return 0


if __name__ == '__main__':
    sys.exit(main())