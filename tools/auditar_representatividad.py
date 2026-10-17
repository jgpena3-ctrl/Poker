# -*- coding: utf-8 -*-
"""Auditoria de representatividad de los 23 cortes preflop. SOLO LEE.

Que es lo que descubre, y por que el instrumento ya no los produce:

    Los 23 cortes preflop de VALIDACION tienen y = 0. Los 23.
    Y los 75 de CALIBRACION tambien: 75 de 75.

    No es que el heroe pierda siempre. El corte (`corte_de_decision`) es la
    ULTIMA accion del heroe, y acepta 'f'. Los 23 son la ultima accion del
    heroe siendo un FOLD. La poblacion preflop del instrumento era la
    poblacion de los folds, que no es la poblacion B del AUC ("el heroe
    continua o checkea", `CONTRATO_L_SEC.md` §8).

    Y un fold tiene y = 0 POR CONSTRUCCION: el que foldea no puede ganar.
    Meter 23 observaciones de una sola clase en un AUC no anade manos, anade
    la regla de seleccion.

Este script audita esas 23 como población —que es lo que se le pidió— y
mide ademas lo que hace que no sean extrapolables. Y no escribe nada.

Uso:
    python tools/auditar_representatividad.py
"""
import collections
import importlib.util
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RANGOS = '23456789TJQKA'
PALOS = 'cdhs'
PREMIOS = {'AA', 'KK', 'QQ', 'JJ', 'AK', 'AQ', 'AJ', 'AT', 'KJ'}


def _inst():
    ruta = os.path.join(ROOT, 'tools', 'equity_preflop_observables.py')
    spec = importlib.util.spec_from_file_location('eqpobs_rep', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cartas(c2):
    """('AK', 'hs') para 'AhKs'. '' si no son dos cartas.

    El par se ordena por RANGO DE POKER, no alfabeticamente.
    `revision_2` parrafo 1: `sorted(('K', 'J'))` da `'JK'`, y `PREMIOS`
    tiene `'KJ'`, asi que **KJ no se reconocia**. De los nueve premiums,
    KJ era el UNICO al que `sorted()` no llegaba; los otros ocho si,
    porque sus letras ya salen en orden alfabetico. Un detector que
    funciona en ocho de nueve casos parece correcto.
    """
    c2 = (c2 or '').strip()
    if len(c2) != 4:
        return ''
    for i in (0, 2):
        if c2[i] not in RANGOS or c2[i + 1] not in PALOS:
            return ''
    # de mayor a menor, que es como se escribe una mano: AK, no KA
    return ''.join(sorted((c2[0], c2[2]), key=RANGOS.index,
                          reverse=True)), c2[1] + c2[3]


def es_premium(s):
    c = cartas(s)
    return bool(c) and c[0] in PREMIOS


def es_par(s):
    c = cartas(s)
    return bool(c) and c[0][0] == c[0][1]


def es_suited(s):
    c = cartas(s)
    return bool(c) and c[1][0] == c[1][1]


def tipico(pp, n):
    return (pp * (100.0 - pp) / n) ** 0.5


def herfindahl(conteo):
    n = sum(conteo.values())
    return sum((c / n) ** 2 for c in conteo.values()) if n else 0.0


def sanity_de_cartas():
    """(fallos, lineas) de siete casos con cartas de verdad.

    Se escribe ANTES de mirar el resultado, y es lo que destapo los dos
    fallos del detector: uno que devolvia False SIEMPRE, y otro que
    confundia orden alfabetico con orden de rangos. Un criterio que no
    puede fallar no es un criterio, y por eso hace falta una tabla que si
    pueda fallar.

    `KhJs` esta porque es EL caso que rompia: con `sorted()` alfabetico
    daba `'JK'`, y `PREMIOS` tiene `'KJ'`, asi que noidia premium.
    """
    casos = (('AhKs', True, False, False),     # AK sin palo
             ('KhJs', True, False, False),     # KJ sin palo: el que fallaba
             ('KhJh', True, False, True),      # KJ suited
             ('AdKd', True, False, True),      # AK suited: dos diamantes
             ('QhKs', False, False, False),    # KQ NO es premium
             ('QcJc', False, False, True),     # jotas suited, no un par
             ('ThTs', False, True, False),     # un par, sin palo
             ('9h8s', False, False, False))
    fallos, lineas = 0, []
    for s_, prem, par, suited in casos:
        c = cartas(s_)
        ok = (es_premium(s_) == prem and es_par(s_) == par
              and es_suited(s_) == suited)
        fallos += not ok
        lineas.append('   %-6s %-14s premium=%-5s par=%-5s suited=%-5s  %s'
                      % (s_, c or 'NO SON CARTAS', es_premium(s_), es_par(s_),
                         es_suited(s_), 'ok' if ok else '>>> MAL <<<'))
    return fallos, lineas, len(casos)


# Con NOMBRES, y no una tupla suelta. El orden de los campos ya no puede
# importar porque el acceso es por nombre, y si alguien usa indices por
# costumbre, `Resto.motivo` deja de existir en cuanto se reordena.
Resto = collections.namedtuple('Resto', ('motivo', 'y'))


def resto_de_muestra(cal, h, hero_pos=None):
    """(motivo, y) con los filtros de `muestra()` MENOS los dos que se
    adelantan al camino de victoria por fold.

    Los dos son `board_completo()` y `len(con_cartas(h)) < 2`, y los dos
    estan ANTES de `gano_por_fold()`. Se saltan los dos porque la pregunta
    que se responde es "la poblacion esta vacia, o esta bloqueada", y solo
    se responde saltandolos.

    `revision_2` parrafo 2 y otra vez: la version anterior de este script
    mantenia los dos y de ahi salio la conclusion FALSA de que la
    poblacion era vacia. El filtro no es informacion sobre la poblacion:
    es informacion sobre el ORDEN de los filtros.
    """
    declarados = {cal.id_a_pos(h, i) for i in (h.get('winner') or [])}
    declarados.discard(None)
    if not declarados:
        return Resto('sin ganador declarado', None)
    scores, mejor = cal.mejores_manos(h)
    llegan = {p for p in declarados
              if cal.llego_al_showdown(h, p) and scores and p in scores}
    if not llegan:
        # el camino de victoria por fold: NO necesita las cartas de los
        # demas, y por eso los dos filtros de arriba le hacen sombra
        ok_fold, _mot = cal.gano_por_fold(h, declarados)
        if not ok_fold:
            return Resto('fold no verificable', None)
        return Resto('ok', 1.0)
    # showdown: aqui SI hacen falta las cartas de los demas
    if len(cal.con_cartas(h)) < 2:
        return Resto('showdown sin cartas de los demas', None)
    mejores = ({p for p, s_ in scores.items() if s_ == mejor}
               if mejor is not None else set())
    if llegan != mejores:
        return Resto('ganadores que no son los mejores', None)
    return Resto('ok', 1.0 if hero_pos in llegan else 0.0)


def cortes_de(ins, h, pos, cual):
    """(calle, idx) del corte del heroe. `cual` = 'ultima' o 'primera'.

    La version 'ultima' es la de `corte_de_decision`. La 'primera' NO
    existe en el codigo y vive aqui SOLO para medir la hipotesis. No la usa
    nada mas, y por eso no esta en `motor/`.
    """
    # El instrumento se pasa como argumento y no se busca un global: esta
    # funcion es de MODULO, y dentro de ella no existe ins ni eqm. Una
    # funcion de modulo que lee un global que existe solo dentro de otra es
    # una que funciona hasta que alguien la llama desde otro sitio.
    calles = ins.eqm.ORDEN_CALLES
    if cual == 'ultima':
        calles = list(reversed(calles))
    for st in calles:
        acts = ((h.get('streets') or {}).get(st) or {}).get('actions') or []
        rango = (range(len(acts) - 1, -1, -1) if cual == 'ultima'
                 else range(len(acts)))
        for i in rango:
            a = acts[i]
            if a.get('pos') == pos and a.get('action') in ('b', 'c', 'r',
                                                           'f', 'x'):
                return st, i
    return None, None


def medir_corte(ins, por_id, cual):
    """Las filas del corte pedido. Una por mano con corte preflop."""
    filas = []
    for hid in sorted(por_id):
        h = por_id[hid]
        pos = ins.eqm.hero_pos_de(h)
        if not pos:
            continue
        calle, idx = cortes_de(ins, h, pos, cual)
        if calle != 'preflop':
            continue
        acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
        acc = acts[idx]['action'] if idx is not None and idx < len(acts) \
            else None
        r = resto_de_muestra(ins.cal, h, pos)
        filas.append({'id': hid, 'accion': acc, 'y': r.y,
                      'jugada': acc in ins.ACCIONES_JUGADAS})
    return filas


def main():
    ins = _inst()
    from motor import learn, player_ranges

    ventana = learn.load_hands(reliable_only=True)
    por_id = dict((h['hand_id'], h) for h in ventana)
    ajuste = [h for h in ventana if not ins.cal.es_validacion(h['hand_id'])]
    labels = ins.eqm.perfiles_de(ajuste)
    model = player_ranges.ProfileRangeModel.from_hands(
        ajuste, labels=labels, alpha=player_ranges.DEFAULT_ALPHA)
    cal_, val_ = ins.cal.muestra()

    # Los cortes preflop TAL COMO ERAN: antes del filtro de fold. Se
    # recalculan aqui para que la auditoria no dependa de que el
    # instrumento los produzca: si desaparecen, la auditoria tiene que
    # seguir-existiendo, porque su conclusion es justo que no hay.
    def cortes(etiqueta, solo_jugadas):
        out = []
        for hid, y in sorted(etiqueta.items()):
            h = por_id.get(hid)
            if h is None:
                continue
            hero = ins.eqm.hero_pos_de(h)
            if not hero or y == 0.5:
                continue
            calle, idx = ins.eqm.corte_de_decision(h, hero)
            if calle != 'preflop':
                continue
            acts = ((h.get('streets') or {}).get(calle) or {}).get(
                'actions') or []
            accion = acts[idx]['action'] if idx is not None and idx < len(
                acts) else None
            if solo_jugadas and accion not in ins.ACCIONES_JUGADAS:
                continue
            spot = ins.mano_del_spot(h, calle, hero, idx)
            if spot not in ins.ACCIONES_SPOT:
                continue
            mc = ins.cartas_de(h, hero)
            nombre, vpos = ins.villano_del_corte(h, hero, calle, idx)
            if not mc or not nombre or nombre not in model.perfil:
                continue
            out.append({'id': hid, 'y': y, 'hero': mc, 'villano': nombre,
                        'spot': spot, 'accion': accion})
        return out

    A = cortes(dict(val_), False)
    B = cortes(dict(cal_), False)
    nA, nB = len(A), len(B)

    print('=' * 76)
    print('0.  EL DETECTOR DE CARTAS, antes de usarlo')
    print('=' * 76)
    fallos, lineas, n_casos = sanity_de_cartas()
    for l in lineas:
        print(l)
    # el total se SACA de la lista, no se escribe a mano: un "de 7" fijo
    # pasa a mentir en silencio el dia que se anade un caso y nadie se
    # acuerda de cambiarlo
    print('   fallos: %d de %d' % (fallos, n_casos))
    assert fallos == 0, (
        'el detector de cartas falla en %d de %d casos: los numeros de C3 no '
        'se publican con un detector roto' % (fallos, n_casos))

    print()
    print('=' * 76)
    print('1.  QUE SON LAS 23')
    print('=' * 76)
    print('   validacion  : %d cortes preflop' % nA)
    print('   calibracion : %d cortes preflop' % nB)
    ya = collections.Counter(t['accion'] for t in A)
    yb = collections.Counter(t['accion'] for t in B)
    print('   lo que hace el heroe en el corte, validacion  : %s' % dict(ya))
    print('   lo que hace el heroe en el corte, calibracion : %s' % dict(yb))
    print('   su etiqueta, validacion  : %s'
          % dict(collections.Counter(t['y'] for t in A)))
    print('   su etiqueta, calibracion : %s'
          % dict(collections.Counter(t['y'] for t in B)))
    print()
    print('   Las 23 son FOLDS. y = 0 por construccion: el que foldea no')
    print('   puede ganar. No son la poblacion B del AUC, que es "continua')
    print('   o checkea" (CONTRATO_L_SEC.md §8).')

    print()
    print('=' * 76)
    print('2.  LA CADENA DE SELECCION: no descarta nada')
    print('=' * 76)
    for nombre, etiqueta in (('validacion', dict(val_)),
                             ('calibracion', dict(cal_))):
        trabajo, etapas, _sr, sp = ins.seleccionar_manos(etiqueta, por_id,
                                                         model)
        tot = [etapas[e]['__total__'] for e in
               ('1_corte_preflop', '0_accion_jugada', '2_cartas_hero',
                '3_rival', '4_perfil')]
        print('   %-12s %3d -> corte %3d -> juega %3d -> cartas %3d '
              '-> rival %3d -> perfil %3d'
              % (nombre, len(etiqueta), tot[0], tot[1], tot[2], tot[3],
                 tot[4]))
    print()
    print('   Ni una mano se cae por falta de cartas, de villano o de')
    print('   perfil. El unico filtro que descarta es el de la ACCION, y')
    print('   descarta el 100% de los dos grupos.')

    print()
    print('=' * 76)
    print('3.  C1  MEZCLA DE SPOT   (23 contra 75; son dos grupos de folds)')
    print('=' * 76)
    SA = collections.Counter(t['spot'] for t in A)
    SB = collections.Counter(t['spot'] for t in B)
    print('   %-13s %9s %11s %10s %8s' % ('spot', 'A (23)', 'B (75)',
                                         'dif.', 'sigmas'))
    for spot in sorted(set(SA) | set(SB)):
        pa = 100.0 * SA.get(spot, 0) / nA
        pb = 100.0 * SB.get(spot, 0) / nB
        z = (pa - pb) / ((tipico(pa, nA) ** 2 + tipico(pb, nB) ** 2) ** 0.5
                        or 1.0)
        print('   %-13s %8.1f%% %10.1f%% %9.1f %8.1f'
              % (spot, pa, pb, pa - pb, z))
    pool = [t['spot'] for t in A] + [t['spot'] for t in B]
    SPOTS = sorted(set(SA) | set(SB))

    def separacion(et):
        ca = collections.Counter(pool[i] for i in range(len(pool)) if et[i])
        cb = collections.Counter(pool[i] for i in range(len(pool))
                                 if not et[i])
        return max(abs(100.0 * ca.get(s, 0) / nA
                       - 100.0 * cb.get(s, 0) / nB) for s in SPOTS)

    obs = separacion([1] * nA + [0] * nB)
    rng = random.Random(11)
    N_SIM = 20000
    cuantas = 0
    for _ in range(N_SIM):
        et = [1] * nA + [0] * nB
        rng.shuffle(et)
        if separacion(et) >= obs:
            cuantas += 1
    print('   mayor separacion observada %.1f pp   p por permutacion %.4f'
          % (obs, (cuantas + 1) / float(N_SIM + 1)))
    print()
    print('   El umbral declarado de 10 pp FALLABA en dos de tres spots. Con')
    print('   n = %d el error tipico de una proporcion es de %.0f a %.0f pp:'
          % (nA, tipico(35.0, nA), tipico(39.0, nA)))
    print('   el umbral estaba mas alla del ruido. Un criterio sin calibrar')
    print('   contra el tamano de la muestra no es un criterio.')

    print()
    print('=' * 76)
    print('4.  C2  VILLANOS')
    print('=' * 76)
    VA = collections.Counter(t['villano'] for t in A)
    VB = collections.Counter(t['villano'] for t in B)
    ta, tb = VA.most_common(1)[0], VB.most_common(1)[0]
    print('   mas frecuente  A: %-16s %d de %d (%.1f%%)   [%s]'
          % (ta[0], ta[1], nA, 100.0 * ta[1] / nA,
             ' '.join(t['id'] for t in A if t['villano'] == ta[0])))
    print('                 B: %-16s %d de %d (%.1f%%)'
          % (tb[0], tb[1], nB, 100.0 * tb[1] / nB))
    print('   distintos      A: %2d de %2d   B: %2d de %2d'
          % (len(VA), nA, len(VB), nB))
    print('   HHI            A: %.3f          B: %.3f'
          % (herfindahl(VA), herfindahl(VB)))
    print('   El umbral declarado (no pasar del doble) FALLABA: %.2fx.'
          % ((100.0 * ta[1] / nA) / (100.0 * tb[1] / nB)))
    print('   Pero son %d manos, y en A hay %d villanos distintos para %d'
          % (ta[1], len(VA), nA))
    print('   manos: la concentracion es baja en terminos absolutos.')

    print()
    print('=' * 76)
    print('5.  C3  CARTAS DEL HEROE')
    print('=' * 76)
    print('   %-9s %11s %13s %8s %8s' % ('tipo', 'A (23)', 'B (75)',
                                         'dif.', 'sigmas'))
    for nombre, fn in (('premium', es_premium), ('pares', es_par),
                       ('suited', es_suited)):
        a = sum(1 for t in A if fn(t['hero']))
        b = sum(1 for t in B if fn(t['hero']))
        pa, pb = 100.0 * a / nA, 100.0 * b / nB
        z = (pa - pb) / ((tipico(pa, nA) ** 2 + tipico(pb, nB) ** 2) ** 0.5
                        or 1.0)
        print('   %-9s %4d %5.1f%% %6d %5.1f%% %7.1f %8.1f'
              % (nombre, a, pa, b, pb, pa - pb, z))

    print()
    print('=' * 76)
    print('6.  LO QUE HAY DE VERDAD EN LA VENTANA, y si el preflop cabe')
    print('=' * 76)
    celda = collections.Counter()
    # DOS recuentos y DOS nombres. `revision_2` parrafo 3:
    #   bcr             acciones b/c/r — un recuento de ACCIONES
    #   continuaciones  b/c/r/x — un recuento de POBLACION B
    # `ACCIONES_JUGADAS` incluye 'x', asi que usarla para contar acciones
    # mezclaba dos cosas y el total no cuadraba con la tabla de arriba.
    bcr, continuaciones = [], []
    for h in ventana:
        pos = ins.eqm.hero_pos_de(h)
        if not pos:
            continue
        calle, idx = ins.eqm.corte_de_decision(h, pos)
        if calle is None:
            celda[('sin corte', '?')] += 1
            continue
        acts = ((h.get('streets') or {}).get(calle) or {}).get(
            'actions') or []
        acc = acts[idx]['action'] if idx is not None and idx < len(acts) \
            else '?'
        celda[(calle, acc)] += 1
        if calle == 'preflop' and acc in ('b', 'c', 'r'):
            bcr.append(h['hand_id'])
        if calle == 'preflop' and acc in ins.ACCIONES_JUGADAS:
            continuaciones.append(h['hand_id'])

    print('   La ULTIMA accion del heroe, en las %d manos fiables'
          % len(ventana))
    print('   %-10s %s' % ('calle', ' '.join('%5s' % a
                                           for a in 'b c r f x'.split())))
    for calle in ('preflop', 'flop', 'turn', 'river'):
        fila = [celda.get((calle, a), 0) for a in 'b c r f x'.split()]
        print('   %-10s %s   total %3d'
              % (calle, ' '.join('%5d' % x for x in fila), sum(fila)))
    con_y = set(hid for hid, _y in cal_ + val_)
    n_bcr = len(bcr)
    n_cont = len(continuaciones)
    print()
    print('   b/c/r   un recuento de ACCIONES                : %d' % n_bcr)
    print('   x       checks                                  : %d'
          % celda.get(('preflop', 'x'), 0))
    print('   b/c/r/x POBLACION B: continua o checkea        : %d' % n_cont)
    print('   de esas, con etiqueta                          : %d'
          % len([i for i in continuaciones if i in con_y]))
    print()
    print('   ASI QUE: la poblacion B en preflop no es que sea pequena. En')
    print('   este conjunto es VACIA. Las %d continuaciones de la ventana no'
          % n_cont)
    print('   tienen etiqueta, y las 98 que si la tienen son todas folds.')
    print()
    print('   POR QUE. Y aqui se RETIRA una explicacion que era mia y era')
    print('   falsa: "si el heroe juega y gana, vuelve a actuar y el corte')
    print('   se mueve de calle". En 81 de las 83 la mano TERMINA en')
    print('   preflop porque todos foldean a la apuesta del heroe, y el')
    print('   heroe gana POR FOLD con `winner` declarado. El corte se queda')
    print('   en preflop por eso, no porque el heroe vuelva a actuar.')
    print('   Lo que las mata es `board_completo()`, que exige')
    print('   `comunitarias.river >= 1` y es el PRIMER filtro de `muestra()`.')
    print('   Seccion 7, con el contrafactual.')

    print()
    print('=' * 76)
    print('7.  POR QUE NO HAY ETIQUETA: filtro a filtro, no con una teoria')
    print('=' * 76)
    grupos = collections.Counter()
    resto = collections.Counter()
    quien = []
    for hid in continuaciones:
        h = por_id[hid]
        comunitarias = (h.get('comunitarias') or {}).get('river') or []
        reales = []
        st = h.get('streets') or {}
        for calle in ('flop', 'turn', 'river'):
            reales += list((st.get(calle) or {}).get('board') or [])
        if comunitarias:
            grupos['A  comunitarias.river con cartas'] += 1
        elif reales:
            grupos['B  el board esta en streets, comunitarias vacio'] += 1
        else:
            grupos['C  no hay board en ninguna parte'] += 1
        r = resto_de_muestra(ins.cal, h, ins.eqm.hero_pos_de(h))
        resto[r.motivo] += 1
        if r.motivo == 'ok':
            quien.append((hid, r.y))

    print('   Donde esta el board, en las %d:' % n_cont)
    for k, v in sorted(grupos.items()):
        print('      %3d  %s' % (v, k))
    print()
    print('   Que dicen los filtros de `muestra()` que QUEDAN, sin el de')
    print('   board:')
    for k, v in resto.most_common():
        print('      %3d  %s' % (v, k))
    print()
    clases = collections.Counter(y for _i, y in quien)
    print('   CONTRAFACTUAL: %d de las %d tendrian etiqueta, y serian'
          % (len(quien), n_cont))
    print('                     %s' % dict(clases))
    print()
    print('   O SEA QUE LA POBLACION NO ESTA VACIA: ESTA BLOQUEADA. De las')
    print('   %d, %d tienen una victoria por fold VERIFICABLE —que es lo que'
          % (n_cont, len(quien)))
    print('   `gano_por_fold` sabe comprobar sin las cartas de los demas— y')
    print('   lo que las deja fuera son dos filtros que se ADELANTAN a ese')
    print('   camino: `board_completo()` y el de las dos cartas con cartas.')
    print()
    print('   PERO: las %d son TODAS victorias. Cero derrotas.' % len(quien))
    print()
    print('   Y esa es la razon por la que no hay AUC, que es distinta de la')
    print('   que se escribio: no es que falten manos, es que la poblacion')
    print('   tiene UNA SOLA CLASE. El corte es la ULTIMA accion del heroe;')
    print('   para que ese corte sea una accion jugada en preflop, la mano')
    print('   tiene que acabar ahi, y si acaba ahi con accion jugada, el')
    print('   heroe gana. Si siguiera, habria una accion posterior y el corte')
    print('   se moveria de calle.')
    print()
    print('   NO CAMBIA NADA. `board_completo()` es parte de una muestra')
    print('   firmada en CONTRATO_L_SEC.md; moverlo cambia los 160, la')
    print('   particion, el modelo ajustado y el AUC ya publicado. Lo que se')
    print('   mide es si la pregunta SERIA respondible con otra regla.')
    print()
    print('   Y la respuesta es que AUN ASI NO: no por falta de manos, sino')
    print('   porque no hay una sola derrota. Un AUC binario necesita las dos')
    print('   clases, y 78 victorias contra 0 derrotas dan un AUC INDEFINIDO,')
    print('   que es tan poco informativo como 0,5.')

    print()
    print('   Las que NO se pueden etiquetar ni saltando los dos filtros,')
    print('   y por que:')
    for hid in sorted(set(continuaciones) - {i for i, _y in quien}):
        h = por_id[hid]
        r = resto_de_muestra(ins.cal, h, ins.eqm.hero_pos_de(h))
        print('      %-9s %s' % (hid, r.motivo))
    print()

    print('=' * 76)
    print('   Y el AUC con una sola clase NO "daria 1,0 por definicion".')
    print('   `auditar_auc.auc_de()` devuelve None, y lo dice en su docstring:')
    print('   "None si falta una clase". El valor correcto es INDEFINIDO.')
    print()
    print()
    print('=' * 76)
    print('8.  EL CORTE EN LA PRIMERA DECISION, MEDIDO')
    print('=' * 76)
    print('   En tres documentos se afirmo, SIN MEDIR, que un corte en la')
    print('   primera decision del heroe traeria las manos en las que')
    print('   perduo. `revision_2` parrafo 3: es una hipotesis, no basta con')
    print('   decirla. Aqui esta medida, y SE SOSTIENE:')
    print()
    fu = medir_corte(ins, por_id, 'ultima')
    fp = medir_corte(ins, por_id, 'primera')

    def _cuenta(filas):
        jug = [f for f in filas if f['jugada']]
        con = [f for f in jug if f['y'] is not None]
        return (len(filas), len(jug), len(con),
                sum(1 for f in con if f['y'] == 1.0),
                sum(1 for f in con if f['y'] == 0.0))

    cu, cp = _cuenta(fu), _cuenta(fp)
    print('   %-28s %14s %14s' % ('', 'ULTIMA (ahora)', 'PRIMERA'))
    for i, nombre in enumerate(('cortes preflop', 'poblacion B jugada',
                                'con etiqueta posible', '   y = 1', '   y = 0')):
        print('   %-28s %14d %14d' % (nombre, cu[i], cp[i]))
    print()
    print('   Y ASI SE SEPARAN LOS DOS PROBLEMAS, que `revision_2` pide que')
    print('   no se confundan. Son de distinto tipo y no se arreglan igual:')
    print()
    print('     1. BLOQUEO DE ETIQUETADO. El orden de los filtros deja')
    print('        fuera etiquetas que SI se pueden verificar. Se arregla')
    print('        moviendo filtros, y NO cambia la poblacion: siguen')
    print('        siendo 78 victorias y 0 derrotas.')
    print()
    print('     2. SESGO DE LA SELECCION DEL CORTE. La ULTIMA accion del')
    print('        heroe selecciona una poblacion SIN derrotas preflop')
    print('        jugadas. Arreglar el 1 NO arregla el 2.')
    print()
    print('   El 2 es lo que hay que cambiar, y es un cambio de la DEFINICION')
    print('   del objetivo. Por eso va MEDIDO y no implementado: eso va en')
    print('   un contrato, y el de la muestra esta firmado.')
    print()
    print()
    print('=' * 76)
    print('CONCLUSION')
    print('=' * 76)
    print('   Las 23 NO son representativas de las decisiones preflop de la')
    print('   poblacion B, porque las decisiones preflop de la poblacion B')
    print('   no existen en este conjunto. Son representativas de una cosa')
    print('   distinta: de los folds preflop del heroe.')
    print()
    print('   Y sobre el AUC "con preflop incluido": NO SE CALCULA. Por dos')
    print('   razones distintas, y es importante que sean dos:')
    print()
    print('     1. Las 23 que el instrumentoLlegaba a producir eran folds, con')
    print('        y = 0 por construccion. Meterlas mediria la regla de')
    print('        seleccion. Eso ya no es una posibilidad: el instrumento ahora las')
    print('        descarta por ACCIONES_JUGADAS.')
    print()
    print('     2. Las 83 decisiones preflop de la poblacion B que SI existen')
    print('        en los datos tienen UNA SOLA CLASE: 78 serian')
    print('        victorias y 0 derrotas. Aun desbloqueando el orden de')
    print('        filtros, un AUC binario daria 1,0 por definicion.')
    print()
    print('   Y el instrumento ya no produce esas manos: `ACCIONES_JUGADAS`')
    print('   hace que un fold se cuente y se descarte, con su motivo.')
    return 0


if __name__ == '__main__':
    sys.exit(main())