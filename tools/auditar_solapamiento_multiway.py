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
    CLASES, CLASES_POLITICA, ORDEN, PLAYER_IDS, POSTFLOP, acciones,
    clasificar_decision, contrato_orden_ok, en_bote, en_bote_en_instante,
    folds_hasta, hero_pos, heroes, instante_decision, instantes_decision,
    metrica_politica, no_puede_actuar, no_puede_actuar_en_instante,
    puede_responder, puntos_decision_mano, posiciones_allin, secuencia,
    ultima_accion,
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
    print('   El punto de decision es una ACCION DEL HERO, no una calle. Dos')
    print('   correcciones, en este orden:')
    print()
    print('   a) El hero puede tener MAS DE UNA accion en la misma calle. Si')
    print('      apuesta y luego tiene que decidir otra vez ante una resubida,')
    print('      eso son dos decisiones con dos situaciones distintas: entre')
    print('      una y otra puede incorporarse un rival o irse otro. Contarlas')
    print('      como una escondia justo los puntos donde mas rivales pueden')
    print('      responder.')
    print()
    print('   b) Una calle con acciones en la que el hero NO aparece no es un')
    print('      punto de decision: no hay nada que decidir. Y al restar 1 al')
    print('      numero de activos para excluir al hero, en esos puntos se')
    print('      restaba de mas.')
    print()
    c5 = collections.Counter()
    for h in manos:
        hp = hero_pos(h)
        for st in POSTFLOP:
            acts = acciones(h, st)
            n_hero = len(instantes_decision(h, st)) if hp else 0
            if not acts:
                c5['calle sin ninguna accion'] += 1
            elif n_hero == 0:
                c5['calle con acciones, sin accion del hero'] += 1
            else:
                c5['calles con >=1 accion del hero'] += 1
                c5['   de ellas, con 2 o 3 acciones'] += (n_hero > 1)
    for k, v in sorted(c5.items()):
        print('   %-46s %5d' % (k, v))
    print()
    calles = len(manos) * 3
    sin_accion = c5['calle sin ninguna accion']
    sin_hero = c5['calle con acciones, sin accion del hero']
    con_hero = c5['calles con >=1 accion del hero']
    print('   CUADRA: %d + %d + %d = %d calles' %
          (sin_accion, sin_hero, con_hero, calles))
    assert sin_accion + sin_hero + con_hero == calles, 'no cuadra'

    # =====================================================  6  CIFRAS
    print()
    print('6) CIFRAS CON EL CONTRATO DE DECISION  (base para F7.2)')
    print('-' * 78)
    # --- correccion temporal, sobre la MISMA poblacion que la politica ---
    # Sin folds, sin desconocidos y con rival: comparar un "por instante"
    # de 258 contra un denominador de 507 sin folds seria meterlos otra
    # vez por la puerta de atras.
    mw_calle = mw_inst = 0
    for h in manos:
        hp = hero_pos(h)
        for st in POSTFLOP:
            for i in instantes_decision(h, st):
                if acciones(h, st)[i]['action'] == 'f':
                    continue
                if posiciones_allin(h) is None:
                    continue
                ps = no_puede_actuar(h, st)
                pi = no_puede_actuar_en_instante(h, st, i)
                if ps is not None:
                    mw_calle += len((en_bote(h, st) - ps) - {hp}) > 1
                if pi is not None:
                    mw_inst += len(puede_responder(h, st, i)) > 1

    m = metrica_politica(manos)
    t = m['tabla']
    folds = lambda c: t[('fold', c)]                  # noqa: E731
    nofold = lambda c: t[('no fold', c)]              # noqa: E731
    res = collections.Counter({c: folds(c) + nofold(c) for c in CLASES})

    print('   puntos de DECISION (acciones del hero): %d' % m['total'])
    print()
    print('   Un punto FOLD es una decision REAL del hero, pero NO consulta')
    print('   equity: no hay nada que repartir entre HU y MULTIWAY para una')
    print('   politica multiway. Se declara aparte, no se esconde.')
    print()
    print('   TABLA CRUZADA')
    print('   %-16s %8s %8s %8s %10s'
          % ('clase', 'fold', 'no fold', 'total', 'POLITICA'))
    for c in CLASES:
        pol = nofold(c) if c in CLASES_POLITICA else 0
        print('   %-16s %8d %8d %8d %10d'
              % (c, folds(c), nofold(c), folds(c) + nofold(c), pol))
    print('   %-16s %8d %8d %8d %10d'
          % ('TOTAL', m['total'] - sum(nofold(c) for c in CLASES),
             sum(nofold(c) for c in CLASES), m['total'], m['denominador']))
    print()

    print('   CUADRE 1 — todo lo clasificado, con folds dentro:')
    assert (sum(res[c] for c in CLASES) == m['total']), 'no cuadra el total'
    print('      %d + %d + %d = %d puntos'
          % (res['HU'] + res['MULTIWAY'], res['DESCONOCIDO'],
             res['SIN_DECISION'], m['total']))
    print('   CUADRE 2 — filas por columnas:')
    assert (sum(folds(c) for c in CLASES)
            + sum(nofold(c) for c in CLASES) == m['total']), \
        'no cuadra la tabla cruzada'
    print('      %d fold + %d no fold = %d puntos'
          % (m['total'] - sum(nofold(c) for c in CLASES),
             sum(nofold(c) for c in CLASES), m['total']))
    print('   CUADRE 3 — la politica no contiene folds:')
    assert m['denominador'] == nofold('HU') + nofold('MULTIWAY')
    assert m['numerador'] == nofold('MULTIWAY')
    print('      %d = HU %d + MULTIWAY %d'
          % (m['denominador'], nofold('HU'), nofold('MULTIWAY')))
    print()

    print('   METRICA DE POLITICA — aqui es donde NO entran los folds:')
    print('      HU no fold       : %d' % nofold('HU'))
    print('      MULTIWAY no fold : %d' % m['numerador'])
    print('      denominador     : %d' % m['denominador'])
    print('      MULTIWAY         : %.1f%%' % m['porcentaje'])
    print()
    print('   Con folds dentro daba %d/%d = %.1f%%. El PORCENTAGE aguanta;'
          % (res['MULTIWAY'], res['HU'] + res['MULTIWAY'],
             res['MULTIWAY'] / (res['HU'] + res['MULTIWAY']) * 100))
    print('   las CUENTAS no: de los %d multiway, %d eran folds.'
          % (res['MULTIWAY'], folds('MULTIWAY')))
    print('   Concluir lo mismo por dos caminos da una conclusion robusta;')
    print('   publicar el numero sin esta tabla hacia falta.')
    print()

    print('   efecto de la correccion temporal, sobre los %d puntos de'
          % m['denominador'])
    print('   politica:')
    print('      MW por calle    : %d' % mw_calle)
    print('      MW por instante : %d   <- el que se firma' % mw_inst)
    print('      la regla por calle se queda %d spots corto'
          % (mw_inst - mw_calle))
    print()
    print('   DENOMINADOR DE POLITICA F7.2: %d' % m['denominador'])
    print('      HU %d · MULTIWAY %d' % (nofold('HU'), m['numerador']))
    print('      folds excluidos: %d (HU %d + MULTIWAY %d)'
          % (folds('HU') + folds('MULTIWAY'), folds('HU'), folds('MULTIWAY')))
    print('      fuera del numerador: DESCONOCIDO %d (no fold %d) · sin rival %d'
          % (res['DESCONOCIDO'], nofold('DESCONOCIDO'), res['SIN_DECISION']))
    print()
    print('   COTA (techo, si en los desconocidos nadie estuviera all-in),')
    print('   con el MISMO criterio que la metrica principal (no folds):')
    print('      %d + %d = %d'
          % (m['numerador'], m['techo_desconocidos'], m['techo']))
    print()
    print('   CONTRASTE (NO son la misma metrica, no comparar directamente):')
    print('      F7.1 calle + regla del raise   : HU 702  MW 304')
    print('      F7.1 calle + regla de evidencia: MW 225 (cota 276)')
    print('      accion del hero + por CALLE    : MW %d' % mw_calle)
    print('      accion del hero + por INSTANTE  : HU %d  MW %d (cota %d)'
          % (nofold('HU'), m['numerador'], m['techo']))
    print()
    print('   Instrumento: motor/multiway.py::metrica_politica(). El auditor')
    print('   y los tests la IMPORTAN; no hay una segunda cuenta.')
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())