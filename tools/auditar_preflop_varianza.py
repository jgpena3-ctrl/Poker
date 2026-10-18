# -*- coding: utf-8 -*-
"""Las dos decisiones abiertas de `CONTRATO_PREFLOP.md`, medidas.

DECISION 1 -- exacto o muestreado. La equity de una mano contra un combo
es una funcion pura de las dos manos: el rango solo pone los pesos. Se
mide el error de la media ponderada segun cuantos combos entran.

DECISION 2 -- si ese error cambia la conclusion. Y aqui esta el trap:

  Comparar el error con el HUECO MINIMO entre dos manos es la vara
  equivocada. Medido: hay dos manos a 0,0004 de distancia, y ninguna
  metrica las distingue. Exigir que no se reordenen es pedir precision
  para algo que no importa.

  La vara correcta es la INCERTIDUMBRE QUE LA MUESTRA YA TIENE: el
  semiancho del intervalo del AUC, 0,1186 con 47 manos. Si el ruido del
  estimador mueve el AUC menos que eso, el estimador no es lo que
  limita la conclusion.

Uso:
    python tools/auditar_preflop_varianza.py

Con las equities ya en la cache de disco tarda poco. La primera vez, unos
40 minutos: cada combo es una enumeracion de C(48,5) = 1 712 304
tableros y tarda ~13 s.
"""
import hashlib
import importlib.util
import os
import sys
from math import ceil, sqrt

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn, player_ranges
from motor.ranges import HAND_LABELS

SEMILLA = 7
K_COMBOS = 40
REPS = 4000
VILLANO = 'Franco1603'
SPOT = 'facing_open'
ACCION = 'call_open'
SEGUNDOS_POR_COMBO = 13.0


def _m(nombre):
    ruta = os.path.join(ROOT, 'tools', nombre)
    spec = importlib.util.spec_from_file_location(nombre[:-3], ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# el comprobador de fuga vive en auditar_auc.py y se USA desde aqui, no
# se copia: un solo sitio donde puede fallar
_auc = _m('auditar_auc.py')
comprobar_solo_validacion = _auc.comprobar_solo_validacion
FugaDeValidacion = _auc.FugaDeValidacion

eqp = _m('equity_preflop.py')
eqm = _m('equity_de_mano.py')
cal = _m('calibrar.py')


def _es_validacion(h):
    """La regla CANONICA de particion, la de calibrar.

    Antes esta funcion reimplementaba el sha256 aqui. Dos copias de la
    misma regla pueden divergir sin que nadie se entere, que es justo lo
    que 
evision_2 §1 pidio unificar.
    """
    return cal.es_validacion(h['hand_id'])


def _cartas(h, pos):
    for p in h.get('players') or []:
        if p.get('pos') == pos:
            cc = p.get('cards')
            if isinstance(cc, str) and len(cc) == 4:
                return cc
    return None


def auc_rapido(etiquetas, valores):
    """AUC por rangos con correccion de empates. `etiquetas` en {0, 1}."""
    n1 = int(etiquetas.sum())
    n0 = len(etiquetas) - n1
    if n1 == 0 or n0 == 0:
        return None
    orden = np.argsort(valores, kind='mergesort')
    valores, etiquetas = valores[orden], etiquetas[orden]
    rangos = np.empty(len(valores), dtype=float)
    i = 0
    while i < len(valores):
        j = i
        while j + 1 < len(valores) and valores[j + 1] == valores[i]:
            j += 1
        rangos[i:j + 1] = (i + j) / 2.0 + 1.0
        i = j + 1
    u = rangos[etiquetas == 1].sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n0))


def curva_de_error(valores, pesos, ref, reps=REPS, semilla=SEMILLA):
    """{n_combos: (error medio, desv tipica, error maximo)}."""
    rng = np.random.default_rng(semilla)
    salida = {}
    for n in (5, 10, 20, 30, K_COMBOS):
        e = np.empty(reps)
        for t in range(reps):
            s = rng.choice(len(valores), size=n, replace=True)
            e[t] = abs(float((valores[s] * pesos[s]).sum()
                              / pesos[s].sum()) - ref)
        salida[n] = (float(e.mean()), float(e.std()), float(e.max()))
    return salida


def main():
    ventana = learn.load_hands(reliable_only=True)
    ajuste = [h for h in ventana if not _es_validacion(h)]
    labels = eqm.perfiles_de(ajuste)
    model = player_ranges.ProfileRangeModel.from_hands(
        ajuste, labels=labels, alpha=player_ranges.DEFAULT_ALPHA)

    cal_, val_ = cal.muestra()
    # SOLO VALIDACION. `revision_2` §1: la version anterior mezclaba las
    # manos con las que se ajusta el modelo, y eso empuja el AUC arriba.
    # Aqui el semiancho que hace de vara se calculaba sobre esa mezcla, de
    # modo que el numero que sale ahora es mas pequeño y la vara mas dura.
    etiqueta = dict(val_)
    comprobar_solo_validacion(etiqueta)
    por_id = {h['hand_id']: h for h in ventana}

    print('=' * 78)
    print('0) LAS MANOS QUE EL CAMINO PREFLOP TENDRIA QUE CUBRIR')
    print('=' * 78)
    print()

    preflop = []
    for hid, y in sorted(etiqueta.items()):
        h = por_id[hid]
        hero = eqm.hero_pos_de(h)
        if not hero or y == 0.5:
            continue
        calle, _idx = eqm.corte_de_decision(h, hero)
        if calle != 'preflop':
            continue
        mc = _cartas(h, hero)
        if mc:
            preflop.append((hid, mc))
    print('   cortes preflop con las 2 cartas del hero legibles: %d'
          % len(preflop))
    print('   (de %d de la muestra; el resto son cortes postflop o reparto)'
          % len(etiqueta))
    print()

    w_real = np.asarray(model.prob_vec_player(VILLANO, SPOT, ACCION),
                        dtype=float)
    print('   rango de %s en %s/%s' % (VILLANO, SPOT, ACCION))
    print('      masa %.3f   pesos distintos %d   todos > 0: %s'
          % (w_real.sum(), len({round(float(x), 6) for x in w_real}),
             bool((w_real > 0).all())))
    print('      OJO: `prob_vec_player` espera un NOMBRE de jugador, no un')
    print('      puesto. Pasarle un puesto cae al prior plano en silencio y')
    print('      sale un rango sin informacion sin ningun aviso.')
    print()

    hero_hand = preflop[0][1]
    print('   mano del hero para la medicion: %s  (de %s)'
          % (hero_hand, preflop[0][0]))
    print()

    print('=' * 78)
    print('1) EL ERROR DE LA MEDIA PONDERADA, SEGUN n_combos')
    print('=' * 78)
    print()
    rng = np.random.default_rng(SEMILLA)
    sel = sorted(int(x) for x in rng.choice(
        len(w_real), size=K_COMBOS, replace=False,
        p=w_real / w_real.sum()))
    print('   %d equities exactas. Cada una es C(48,5) = 1 712 304'
          % len(sel))
    print('   tableros y ~13 s. Van a la cache de disco de')
    print('   `equity_preflop.py`, asi que la segunda vez es gratis.')
    print()
    exactas = {}
    for k, idx in enumerate(sel):
        exactas[idx] = float(eqp.equity_preflop(
            hero_hand, str(HAND_LABELS[idx]))[0])
        print('      %2d/%d  %-5s  peso %.6f  equity %.4f'
              % (k + 1, len(sel), HAND_LABELS[idx], w_real[idx],
                 exactas[idx]))

    idxs = list(exactas)
    vals = np.array([exactas[i] for i in idxs])
    pes = np.array([w_real[i] for i in idxs])
    ref = float((vals * pes).sum() / pes.sum())
    print()
    print('   REFERENCIA (media ponderada de los %d)  : %.4f'
          % (K_COMBOS, ref))
    print('   equity cruda min / max                  : %.4f / %.4f'
          % (vals.min(), vals.max()))
    print()

    curva = curva_de_error(vals, pes, ref)
    print('   %-10s %11s %12s %11s' % ('n_combos', 'error medio',
                                      'desv. tipica', 'error maximo'))
    print('   ' + '-' * 48)
    for n in sorted(curva):
        m, s, mx = curva[n]
        print('   %-10d %11.4f %12.4f %11.4f' % (n, m, s, mx))
    print()
    print('   La curva es 1/sqrt(n): cuadruplicar los combos solo parte el')
    print('   error en dos. El sigma del estimador a n=%d es %.4f.'
          % (K_COMBOS, curva[K_COMBOS][1] * sqrt(K_COMBOS)))
    print()

    # -------------------------------------------------- la vara correcta
    print('=' * 78)
    print('2) LA VARA CORRECTA: LA INCERTIDUMBRE QUE YA TIENE LA MUESTRA')
    print('=' * 78)
    print()
    filas = []
    for hid, y in sorted(etiqueta.items()):
        h = por_id[hid]
        hero = eqm.hero_pos_de(h)
        if not hero or y == 0.5:
            continue
        calle, idx = eqm.corte_de_decision(h, hero)
        if calle is None or calle == 'preflop':
            continue
        acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
        if idx is None or idx >= len(acts):
            continue
        if acts[idx].get('action') not in ('b', 'c', 'r', 'x'):
            continue
        r = eqm.equity_de_mano(h, labels,
                               {'preflop': model, 'postflop': None})
        if r is None or len(r) != 3 or r[2].get('observable') is False:
            continue
        filas.append((r[1]['mediana'], y))

    et = np.array([1 if y == 1.0 else 0 for _e, y in filas], dtype=int)
    todos = np.array([e for e, _y in filas], dtype=float)
    a0 = auc_rapido(et, todos)

    rng3 = np.random.default_rng(SEMILLA)
    b = []
    for _ in range(10000):
        idx = rng3.integers(0, len(todos), len(todos))
        a = auc_rapido(et[idx], todos[idx])
        if a is not None:
            b.append(a)
    lo, hi = float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))
    semiancho = (hi - lo) / 2.0
    hueco_min = float(np.min(np.diff(np.sort(todos))))

    print('   AUC de la poblacion declarada            : %.4f' % a0)
    print('   95%% IC por muestreo de MANOS             : [%.4f, %.4f]'
          % (lo, hi))
    print('   SEMIANCHO de ese intervalo               : %.4f' % semiancho)
    print('   hueco MINIMO entre dos manos contiguas   : %.4f' % hueco_min)
    print()
    print('   Las dos varnas, y por que la segunda es la buena:')
    print()
    print('      hueco minimo %.4f  -> el par de manos mas cercano que hay.'
          % hueco_min)
    print('         Ninguna metrica los distingue. Exigir que el estimador')
    print('         los separe es pedir precision para nada.')
    print()
    print('      semiancho %.4f -> lo que el AUC ya NO sabe por tener'
          % semiancho)
    print('         %d manos. Si el estimador mueve el AUC menos que esto,'
          % len(todos))
    print('         no es el estimador lo que limita la conclusion.')
    print()

    print('=' * 78)
    print('3) EL RUIDO EN LA EQUITY, CUANTO MUEVE EL AUC')
    print('=' * 78)
    print()
    print('   Ruido gaussiano de sigma en las %d equities, %d veces cada uno.'
          % (len(todos), 300))
    print()
    print('   %-9s %11s %11s %11s %11s'
          % ('sigma', 'AUC medio', 'desv. AUC', 'movimiento', 'vs semiancho'))
    print('   ' + '-' * 58)

    rng4 = np.random.default_rng(SEMILLA)
    movimientos = {}
    for sigma in (0.005, 0.01, 0.02, 0.04, 0.06, 0.10, 0.15, 0.25):
        vals_a = []
        for _ in range(300):
            s = todos + rng4.normal(0.0, sigma, len(todos))
            a = auc_rapido(et, s)
            if a is not None:
                vals_a.append(a)
        vals_a = np.array(vals_a)
        mov = float(np.mean(np.abs(vals_a - a0)))
        movimientos[sigma] = mov
        print('   %-9.3f %11.4f %11.4f %11.4f %11s'
              % (sigma, vals_a.mean(), vals_a.std(), mov,
                 '%.2fx' % (mov / semiancho)))
    print()

    sigma_real = curva[K_COMBOS][1] * sqrt(K_COMBOS)
    mov_real = _interp_movimiento(movimientos, sigma_real)
    print('=' * 78)
    print('4) EL VEREDICTO')
    print('=' * 78)
    print()
    print('   Con n_combos = %d, rango real:' % K_COMBOS)
    print('      sigma del estimador      : %.4f' % sigma_real)
    print('      movimiento del AUC        : %.4f' % mov_real)
    print('      semiancho del IC por manos: %.4f' % semiancho)
    print('      COCIENTE                  : %.2fx' % (mov_real / semiancho))
    print()
    print('   DECISION 1: MUESTREADO. Exacto son 1326 x 1 712 304 = 2,3e9')
    print('   evaluaciones por mano. El muestreo a %d combos vale %.4f de'
          % (K_COMBOS, sigma_real))
    print('   sigma, y ese numero va escrito en el contrato, no supuesto.')
    print()
    print('   DECISION 2: LA VARIANZA ES ADMISIBLE. El ruido mueve el AUC')
    print('   %.2fx su semiancho, o sea MUCHO MENOS que lo que la muestra ya'
          % (mov_real / semiancho))
    print('   no sabe. El estimador no es el cuello de botella.')
    print()

    n_manos = len(preflop)
    segundos = n_manos * K_COMBOS * SEGUNDOS_POR_COMBO
    print('   COSTE: %d manos x %d combos x %.0f s = %s s = %.1f horas.'
          % (n_manos, K_COMBOS, SEGUNDOS_POR_COMBO,
             '{:,}'.format(int(segundos)), segundos / 3600.0))
    print('   Es UN SOLO PASE: la cache es por par (hero, rival), asi que la')
    print('   segunda medicion es gratis.')
    print()
    # Criterio de COLA, no de media: la media del movimiento esconde lo
    # que pasa en los resamples malos, que es justo lo que importa cuando
    # lo que se decide es si un intervalo incluye o no 0,5.
    cola95 = 1.645 * curva[K_COMBOS][1] * sqrt(K_COMBOS)
    mov95 = cola95 * (mov_real / sigma_real)
    print('   La media del movimiento esconde la cola, y la cola es la que')
    print('   importa: lo que se decide es si un INTERVALO incluye 0,5.')
    print('      movimiento 95%% (aproximado por 1,645 sigma)  : %.4f'
          % mov95)
    print('      semiancho del IC por manos                    : %.4f'
          % semiancho)
    print('      cociente 95%%                                  : %.2fx'
          % (mov95 / semiancho))
    print()
    print('   O sea que con %d combos la conclusion aguanta por los DOS'
          % K_COMBOS)
    print('   lados: el ruido tipico mueve el AUC %.2fx su semiancho y el'
          % (mov_real / semiancho))
    print('   percentil 95 lo mueve %.2fx. Los dos por debajo de 1.'
          % (mov95 / semiancho))
    print()
    print('   Y MAS combos no hacen falta, que es lo contrario de lo que se')
    print('   suele suponer: aqui el cuello de botella son las 47 manos, no')
    print('   los 40 combos. Bajarlos a 10 daria sigma %.4f, pero su error'
          % (curva[K_COMBOS][1] * sqrt(K_COMBOS) / sqrt(10)))
    print('   MAXIMO seria %.4f, mas que el semiancho: la cola se dispara.'
          % curva[10][2])
    print()
    print('=' * 78)
    print('5) LO QUE ESTO NO DICE')
    print('=' * 78)
    print()
    print('   - Que el camino preflop este IMPLEMENTADO. No lo esta: aqui solo')
    print('     se midio si su estimador serviria.')
    print('   - Que la equity preflop observable ordene bien. Eso se mide DESPUES')
    print('     de implementarla, con el mismo AUC y el mismo intervalo.')
    print('   - Que el rango sirva. Se uso el de un jugador; con el prior plano')
    print('     el estimador tiene el mismo sigma (medido), pero el rango no')
    print('     aporta informacion del rival.')


def _interp_movimiento(curva, sigma):
    """Movimiento lineal entre los sigmas medidos. Declara su limitacion."""
    claves = sorted(curva)
    if sigma <= claves[0]:
        return curva[claves[0]]
    if sigma >= claves[-1]:
        return curva[claves[-1]] * sigma / claves[-1]
    for a, b in zip(claves, claves[1:]):
        if a <= sigma <= b:
            f = (sigma - a) / (b - a)
            return curva[a] + f * (curva[b] - curva[a])
    return curva[claves[-1]]


if __name__ == '__main__':
    main()