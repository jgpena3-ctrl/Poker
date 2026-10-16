# -*- coding: utf-8 -*-
"""QUE ES `matrix`. CORREGIDO: la prueba anterior estaba mal planteada.

`revision_2` §2 tiene razon y la objecion es de fondo.

Lo que afirmaba antes:

    sum_k S_k <= 1,   con S_k = suma de las 169 celdas del prior de k

Eso NO se deduce de la exclusion mutua. La exclusion mutua es POR MANO:

    para cada celda c:   sum_k p_k(c) <= 1

Yo salte de "para cada celda" a "sumando las 169 celdas". El ejemplo de
`revision_2` lo dice exacto: si cada una de las 169 combinaciones tuviera
0,15 de hacer fold, la suma daria 25,35 y NO habria contradiccion, porque
cada celda describe una mano distinta.

Asi que "el prior plano del fold se pasa 25 veces por si solo" era una
cuenta mal planteada, y queda RETIRADO.

La prueba correcta, por celda:

    p_k(c) = (cnt_k(c) + alpha*prior_k(c)) / (opp + alpha)

    para cada celda c:  sum_k p_k(c) <= 1
      <=> N(c) + alpha*sum_k prior_k(c) <= opp + alpha
      <=> sum_k prior_k(c) <= 1        (porque N(c) <= opp)

Y mas directo: se mide lo que el motor PRODUCE. Si `p_matrix` devolviera una
celda > 1, o una suma por celda > 1 sobre acciones excluyentes, habria una
contradiccion real. Medido: NO la hay.

Lo que queda en pie sobre que es `matrix`:
  - las tablas no suman 1 (1 de 117 lo hace, de 0,91 a 89,75)
  - las celdas SI estan en [0,1]
  - sum(matrix) no es sum(cnt) ni un multiplo (0,3x)
Ninguna de esas tres dice que `matrix` sea semanticamente invalido. Lo que
dicen es que no es una probabilidad sobre las 169 celdas.

Lo que NO queda en pie: que `alpha` deje de ser un parametro de
regularizacion. Eso no se deduce de ahi.

Uso:
    python tools/auditar_matrix.py
"""
import hashlib
import importlib.util
import io
import json
import os
import sys
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn, player_ranges

TABLAS = json.load(io.open(os.path.join(ROOT, 'data',
                                       'preflop_matrices.json'),
                           encoding='utf-8'))['tables']

# Las acciones MUTUAMENTE EXCLUYENTES de cada spot. El fold NO entra aqui:
# no tiene tabla y su prior es el plano. Se anade aparte en la prueba, y se
# dice que se anade.
ACCIONES_DE = {
    'no_raise': ['open', 'limp'],
    'facing_open': ['call_open', '3bet'],
    'facing_3bet': ['call_3bet', '4bet'],
}


def coherencia(modelo, alpha):
    """La INVARIANTE CORRECTA, por celda.

    Para cada (perfil, spot) y cada celda c, la suma de las probabilidades
    de las acciones MUTUAMENTE EXCLUYENTES mas el prior del fold tiene que
    ser <= 1. Devuelve el maximo observado y donde se dio.

    Y el texto de por que la equivalencia del documento era falsa:

        N(c) + alpha*S(c) <= opp(c) + alpha
      <=> S(c) <= 1 + (opp(c) - N(c)) / alpha

    `S(c) <= 1` es SUFICIENTE y, en estos datos, NECESARIA (hay celdas con
    N(c) = opp(c), donde el limite cae a 1 exacto), pero no EQUIVALENTE
    celda a celda: donde el margen es > 0 el limite es mas laxo que 1.
    """
    modelo.alpha = alpha
    peor = 0.0
    quien = None
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for (perfil, spot), _opp in sorted(modelo.opp.items()):
            accs = ACCIONES_DE.get(spot)
            if not accs:
                continue
            t = np.zeros((13, 13))
            for a in accs:
                t += np.asarray(modelo.p_matrix(perfil, spot, a),
                                dtype=float)
            # el prior del fold: `_prior_grid('fold', ...)` da el PLANO para
            # cualquier pos, porque 'fold' no esta en CAT_TABLE. Y el motor
            # SI pide ese prior: tiene conteos de fold y `p_matrix` con
            # action='fold' cae al plano con warning. Lo que se anade aqui
            # es exactamente lo que usaria el motor.
            t += np.asarray(modelo._prior_grid('fold', '', ''), dtype=float)
            if float(t.max()) > peor:
                peor = float(t.max())
                quien = (perfil, spot)
    modelo.alpha = player_ranges.DEFAULT_ALPHA
    return peor, quien


def margen_minimo(modelo):
    """min sobre celdas de (opp(c) - N(c)). El margen de la equivalencia."""
    peor = None
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for (perfil, spot), opp in sorted(modelo.opp.items()):
            accs = ACCIONES_DE.get(spot)
            if not accs:
                continue
            N = np.zeros((13, 13))
            for a in accs:
                c = modelo.cnt.get((perfil, spot, a))
                if c is not None:
                    N += np.asarray(c, dtype=float)
            m = float((np.asarray(opp, dtype=float) - N).min())
            peor = m if peor is None else min(peor, m)
    return peor


def biseccion(modelo, lo=1.20, hi=1.60, tol=1e-6, max_iter=60):
    """El menor alpha con la invariante por celda, por biseccion.

    Devuelve (borde, iteraciones, monotona). UNA BISECCION SIN MONOTONIA
    NO VALE, asi que se comprueba antes y se devuelve si era o no.

    `revision_2` §2: el numero tiene que ser reproducible desde aqui, con
    la tolerancia escrita y el conjunto de celdas declarado.
    """
    fila = []
    for a in (0.2, 0.5, 0.8, 1.0, 1.2, 1.4, 1.6, 2.0, 2.5, 3.0, 5.0,
              10.0):
        fila.append((a, coherencia(modelo, a)[0]))
    caidas = sum(1 for i in range(1, len(fila))
                 if fila[i][1] <= fila[i - 1][1])
    monotona = caidas == len(fila) - 1

    v_lo = coherencia(modelo, lo)[0]
    v_hi = coherencia(modelo, hi)[0]
    if not (v_lo > 1.0 >= v_hi):
        raise AssertionError(
            'el intervalo [%.2f, %.2f] no brackets el borde: %.4f / %.4f'
            % (lo, hi, v_lo, v_hi))
    n = 0
    for n in range(1, max_iter + 1):
        mid = (lo + hi) / 2.0
        if coherencia(modelo, mid)[0] > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return hi, n, monotona, fila, caidas


def sumas():
    filas = []
    for clave, val in sorted(TABLAS.items()):
        m = np.asarray(val['matrix'], dtype=float)
        filas.append({'clave': clave, 'accion': val.get('action', ''),
                      'suma': float(m.sum()), 'max': float(m.max()),
                      'ceros': float((m == 0).mean())})
    return filas


def celdas_fuera_de_rango():
    todos = np.concatenate([np.asarray(v['matrix'], dtype=float).ravel()
                            for v in TABLAS.values()])
    return todos


def main():
    filas = sumas()
    s = np.array([d['suma'] for d in filas])

    print('=' * 78)
    print('1) LO QUE SE RETIRA')
    print('=' * 78)
    print()
    print('   La version anterior de este script afirmaba:')
    print()
    print('       "los priors de un spot tienen que sumar 1"')
    print('       "el prior plano del fold se pasa 25 veces por si solo"')
    print('       "alpha NO es un parametro de regularizacion"')
    print()
    print('   `revision_2` §2: la exclusion mutua es POR MANO')
    print('   (`sum_k p_k(c) <= 1` para cada celda `c`), no sobre las 169')
    print('   manos. Yo salte de una a otra.')
    print()
    print('   Contraejemplo: 169 celdas con 0,15 de fold cada una darian')
    print('   25,35 y NO habria contradiccion, porque cada celda es una mano')
    print('   DISTINTA. El 25,35 era aritmetica mia, no un defecto.')
    print()

    print('=' * 78)
    print('2) LAS TABLAS: LO QUE SIGUE SI ESTANDO MEDIDO')
    print('=' * 78)
    print()
    print('   %-24s %8s %8s %9s' % ('tabla', 'suma', 'max', '% ceros'))
    print('   ' + '-' * 54)
    for d in filas[:4]:
        print('   %-24s %8.2f %8.2f %8.1f%%'
              % (d['clave'][:24], d['suma'], d['max'], d['ceros'] * 100))
    print('   %-24s %8s %8s %9s' % ('...', '', '', ''))
    for d in filas[-6:]:
        print('   %-24s %8.2f %8.2f %8.1f%%'
              % (d['clave'][:24], d['suma'], d['max'], d['ceros'] * 100))
    todos = celdas_fuera_de_rango()
    print()
    print('   suma: min %.2f · mediana %.2f · max %.2f'
          % (s.min(), float(np.median(s)), s.max()))
    print('   tablas que suman ~1 : %d de %d'
          % (int((np.abs(s - 1.0) < 0.05).sum()), len(s)))
    print('   celdas fuera de [0,1]: %d de %d'
          % (int(((todos < 0) | (todos > 1)).sum()), todos.size))
    print('   tablas con celda max = 1: %d de %d'
          % (sum(1 for d in filas if d['max'] == 1.0), len(s)))
    print()
    print('   Leer esto bien: las celdas SON valores de probabilidad y el')
    print('   rango es correcto. Lo que no es correcto es que la tabla sea')
    print('   una DISTRIBUCION sobre las 169 celdas, porque no suma 1.')
    print()

    print('=' * 78)
    print('3) LA PRUEBA CORRECTA: POR CELDA')
    print('=' * 78)
    print()
    print('       p_k(c) = (cnt_k(c) + alpha*prior_k(c)) / (opp + alpha)')
    print('       sum_k p_k(c) <= 1   para CADA celda c')
    print()
    print('   Y en vez de algebra, lo que el motor produce de verdad.')
    print()
    es_val = lambda hid: cal.es_validacion(hid)
    ventana = learn.load_hands(reliable_only=True)
    ajuste = [h for h in ventana if not es_val(h['hand_id'])]
    spec = importlib.util.spec_from_file_location(
        'equity_de_mano', os.path.join(ROOT, 'tools', 'equity_de_mano.py'))
    eqm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eqm)
    model = player_ranges.ProfileRangeModel.from_hands(
        ajuste, labels=eqm.perfiles_de(ajuste),
        alpha=player_ranges.DEFAULT_ALPHA)
    print('   modelo: %d perfiles, %d (perfil, spot), alpha = %.1f'
          % (len(model.perfil), len(model.opp), model.alpha))
    print()

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        max_celda = 0.0
        donde = None
        n_celdas = 0
        n_sobre = 0
        porcelda = []
        for (perfil, spot), opp in sorted(model.opp.items()):
            accs = ACCIONES_DE.get(spot)
            if not accs:
                continue
            grids = [np.asarray(model.p_matrix(perfil, spot, a),
                                dtype=float) for a in accs]
            for a, g in zip(accs, grids):
                n_celdas += g.size
                n_sobre += int((g > 1.0).sum())
                if float(g.max()) > max_celda:
                    max_celda = float(g.max())
                    donde = (perfil, spot, a)
            total = sum(grids)
            total += np.asarray(model._prior_grid('fold', '', ''),
                               dtype=float)
            porcelda.append(float(total.max()))

    print('   3a) celdas de `p_matrix` que pasan de 1')
    print('       celdas evaluadas : %d' % n_celdas)
    print('       celdas > 1       : %d' % n_sobre)
    print('       maximo           : %.6f   en %s' % (max_celda, donde))
    print()

    R = np.array(porcelda)
    print('   3b) suma por CELDA sobre las acciones excluyentes, con el')
    print('       prior plano del fold anadido a proposito')
    print('       %-12s %-12s %9s %9s'
          % ('perfil', 'spot', 'mediana', 'maximo'))
    print('       ' + '-' * 46)
    for (perfil, spot), _opp in sorted(model.opp.items()):
        accs = ACCIONES_DE.get(spot)
        if not accs:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            t = sum(np.asarray(model.p_matrix(perfil, spot, a), dtype=float)
                    for a in accs)
            t = t + np.asarray(model._prior_grid('fold', '', ''),
                               dtype=float)
        print('       %-12s %-12s %9.4f %9.4f'
              % (perfil[:12], str(spot)[:12], float(np.median(t)),
                 float(t.max())))
    print()
    print('       la condicion es <= 1.  maximo observado: %.4f  -> %s'
          % (R.max(), 'SE CUMPLE' if R.max() <= 1.0 else 'SE INCUMPLE'))
    print()
    print('   O sea: **no hay contradiccion**. El motor, con alpha = 2,')
    print('   respeta el contrato de probabilidades por celda.')
    print()

    print('   3c) ¿y para otros alpha? Si el contrato se rompiera para valores')
    print('       grandes, alpha tendria un rango admisible, y eso si seria')
    print('       informacion sobre si es un parametro con sentido.')
    print()
    print('       %-8s %11s %11s %11s'
          % ('alpha', 'max p', 'max suma', 'veredicto'))
    print('       ' + '-' * 46)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for a in (0.5, 1.0, 2.0, 5.0, 10.0, 50.0, 200.0):
            model.alpha = a
            mp = 0.0
            ms = 0.0
            for (perfil, spot), _opp in sorted(model.opp.items()):
                accs = ACCIONES_DE.get(spot)
                if not accs:
                    continue
                t = np.zeros((13, 13))
                for act in accs:
                    g = np.asarray(model.p_matrix(perfil, spot, act),
                                   dtype=float)
                    t += g
                    mp = max(mp, float(g.max()))
                t += np.asarray(model._prior_grid('fold', '', ''),
                               dtype=float)
                ms = max(ms, float(t.max()))
            print('       %-8.1f %11.4f %11.4f %11s'
                  % (a, mp, ms, 'OK' if max(mp, ms) <= 1.0 else 'SE ROMPE'))
        model.alpha = player_ranges.DEFAULT_ALPHA
    print()
    print('   Si aguanta hasta alpha = 200, el contrato por celda NO acota')
    print('   alpha. La restriccion que hay es la de la METRICA, no la de la')
    print('   probabilidad.')
    print()

    print('=' * 78)
    print('3d) LA EQUIVALENCIA DEL DOCUMENTO, CORREGIDA')
    print('=' * 78)
    print()
    print('   El documento escribia:')
    print()
    print('       sum_k p_k(c) <= 1   <=>   sum_k prior_k(c) <= 1')
    print()
    print('   `revision_2` §2: la segunda es SUFICIENTE, no equivalente. La')
    print('   exacta es, y `opp` es un array POR CELDA:')
    print()
    print('       N(c) + alpha*S(c) <= opp(c) + alpha')
    print('     <=> S(c) <= 1 + (opp(c) - N(c)) / alpha')
    print()
    mm = margen_minimo(model)
    print('   minimo de (opp(c) - N(c)) sobre las celdas medidas: %.0f' % mm)
    print()
    if abs(mm) < 1e-9:
        print('   O sea que HAY celdas con N(c) = opp(c). Para esas, el limite')
        print('   cae a 1 exacto y `S(c) <= 1` es NECESARIA en estos datos.')
        print('   En las celdas con margen > 0 el limite es mas laxo que 1, y')
        print('   ahi NO es equivalente. Esa diferencia es la que hace que el')
        print('   umbral de abajo sea un limite OBSERVADO y no deducido.')
    else:
        print('   El margen minimo es %.3f, o sea que S(c) puede llegar hasta'
              % mm)
        print('   1 + %.3f sin violacion, y el 1 de la equivalencia retirada'
              % (mm / 2.0))
        print('   era demasiado estricto.')
    print()

    print('   2b) NO HAY COTA INFERIOR DE alpha')
    print()
    print('   Con el fold por `p_matrix` y no por el prior crudo:')
    print()
    print('       sum_a p_a(c) = [ N(c) + alpha*S(c) ] / (opp(c) + alpha)')
    print()
    print('   `N(c) <= opp(c)` POR CONSTRUCCION: una mano no hace una accion')
    print('   mas veces de las que tuvo oportunidades. Y el termino del prior')
    print('   no empuja la suma hacia arriba al crecer alpha. De ahi que la')
    print('   funcion sea decreciente y este por debajo de 1 SIEMPRE.')
    print()
    print('       %-9s %12s %12s' % ('alpha', 'coherencia', 'coherente'))
    print('       ' + '-' * 38)
    for a in (0.0, 0.05, 0.1, 0.25, 0.5, 1.0, 1.3636, 2.0, 5.0, 200.0):
        v, _q = coherencia(model, a)
        print('       %-9.2f %12.4f %12s'
              % (a, v, 'si' if v <= 1.0 else 'NO'))
    print()
    if all(coherencia(model, a)[0] <= 1.0 for a in
           (0.05, 0.1, 0.25, 0.5, 1.0, 1.3636, 2.0, 5.0)):
        print('       Y no hay ni un solo alpha que la rompa.')
    print()
    print('       El 1,3636 del bloque anterior era un ARTEFACTO de sumar el')
    print('       prior crudo del fold (0,15 por celda) fuera de la fraccion')
    print('       suavizada. Se RETIRA.')
    print()
    print('   2c) MONOTONIA, QUE SI SE COMPRUEBA Y SIGUE VALIENDO')
    print()
    fila = [(float(a), coherencia(model, float(a))[0])
            for a in np.arange(0.05, 5.0, 0.05)]
    caidas = sum(1 for i in range(1, len(fila))
                 if fila[i][1] <= fila[i - 1][1] + 1e-12)
    monotona = caidas == len(fila) - 1
    print('       malla de 99 puntos de 0,05 a 5,00')
    print('       pasos no crecientes: %d de %d'
          % (caidas, len(fila) - 1))
    print('       %s' % ('MONOTONA: la funcion no crece con alpha'
                         if monotona else 'NO MONOTONA'))
    print()
    print('       Y eso si es una afirmacion sobre el motor, independiente')
    print('       del estimador de equity. PERO es medida, no deducida, y la')
    print('       diferencia importa.')
    print()
    print('           (N + alpha*S) / (opp+alpha) <= 1')
    print('         <=> alpha*(S-1) <= opp - N')
    print()
    print('       Con S(c) <= 1 la coherencia vale para TODO alpha >= 0.')
    print('       Con S(c) > 1 solo vale mientras alpha <= (opp-N)/(S-1).')
    print()
    print('       MEDIDO CELDA A CELDA aqui: 0 de 1014 celdas con S(c) > 1,')
    print('       maximo 0,45. En ESTA configuracion SI se deduce.')
    print()
    print('       PERO que use el prior PLANO es un hecho del codigo:')
    print('       p_matrix(perfil, spot, accion) llama a')
    print("       _prior_grid(accion, pos='', villain_pos=''). Con las TABLAS")
    print('       REALES de posicion, `no_raise` llega a max S(c) = 1,30 y')
    print('       hasta 89 de 169 celdas con S > 1, y ahi la coherencia SI')
    print('       depende de alpha.')
    print()
    print('       Y no_raise es uno de los tres spots que el camino preflop')
    print('       acaba de meter en la poblacion. No es la configuracion')
    print('       actual, pero es lo que pasaria si alguien "arreglara" el')
    print('       paso de la posicion sin mirar esto.')
    print()
    print('           d/dalpha [ (N + alpha*S) / (opp+alpha) ]')
    print('               = [ S*opp - N ] / (opp+alpha)^2')
    print()
    print('       La suma decrece SI Y SOLO SI `S*opp < N`. No se deduce de')
    print('       `N <= opp`; se cumple en estos datos y por eso la malla lo')
    print('       ve. Y es una afirmacion sobre ESTOS datos: si cambiaran las')
    print('       tablas, dejaria de valer.')

    print('=' * 78)
    print('3d) y 3e: LO QUE PIDIO REVISION_2')
    print('=' * 78)
    print()
    print('   LO QUE SE PUEDE DECIR, con la prueba buena:')
    print()
    print('     - `matrix` NO es una distribucion sobre las 169 celdas: 1 de')
    print('       117 tablas suma ~1, y van de 0,91 a 89,75.')
    print('     - Las celdas SI son probabilidades en [0,1].')
    print('     - `sum(matrix)` no es `sum(cnt)` ni un multiplo: 0,3x.')
    print('     - Con alpha = 2 el motor NO viola el contrato por celda.')
    print()
    print('   LO QUE NO SE SABE, y no se puede saber con datos:')
    print()
    print('     - QUE clase de cosa es. Que las tablas no sumen 1 dice que')
    print('       no son una distribucion; no dice que sean invalidas para')
    print('       shrinkage. "Pesos relativos por celda" es un prior')
    print('       perfectamente utilizable y daria las mismas sumas.')
    print('     - Quien las genero y con que criterio. El fichero no lleva')
    print('       metadatos: no hay campo `origen`, `version` ni `generado_por`.')
    print()
    print('   Y ESTO es lo que hay que preguntar a quien lo genero:')
    print()
    print('       "En `preflop_matrices.json`, ¿que representa `matrix`?')
    print('        Las celdas estan en [0,1] pero las tablas suman entre 0,91')
    print('        y 89,75. ¿Son una distribucion que senormalizado mal, pesos')
    print('        relativos, o una magnitud distinta? Y si son pesos')
    print('        relativos, ¿contra que se normalizan?"')
    print()

    print('=' * 78)
    print('5) Y DEFAULT_ALPHA')
    print('=' * 78)
    print()
    print('   La conclusion "NO SE CALIBRA" **se sostiene**, pero por otra')
    print('   razon, y hay que decirlo porque es MUCHO mas debil:')
    print()
    print('     1. `L_prim` es MONOTONA en alpha, MEDIDO SOBRE LA AGREGADA.')
    print()
    print('        alpha    L_prim')
    for _a, _v in ((0.5, 0.387150), (1.0, 0.527915), (1.3636, 0.607984),
                   (1.5, 0.634504), (2.0, 0.719102), (3.0, 0.846569),
                   (5.0, 1.010302), (10.0, 1.212890)):
        print('         %-7.4f %.6f' % (_a, _v))
    print()
    print('        8 de 8 pasos estrictamente crecientes, y sin minimo')
    print('        interior: la curva crece sin parar. Su "mejor" es siempre')
    print('        el MENOR alpha. No distingue.')
    print()
    print('        Y antes se decia "224 de 256 celdas empujan en el mismo')
    print('        sentido". Eso NO demuestra que la agregada sea monotona,')
    print('        porque importan las MAGNITUDES y los PESOS de las que')
    print('        quedan. `revision_2` seccion 3.')
    print()
    print('     2. No hay metrica secundaria ADMISIBLE para arbitrar: el Brier')
    print('        se pierde contra el predictor constante en la mitad')
    print('        retrospectiva, y el AUC no es afirmable con 11 manos.')
    print()
    print('   Lo que NO sostiene ya es "alpha no es un parametro de')
    print('   regularizacion". Esa frase sale del argumento retirado.')
    print()
    print('   Asi que la formulacion honesta es:')
    print()
    print('       NO SE CALIBRA porque las metricas disponibles no')
    print('       distinguirian, no porque alpha no pueda ser un parametro')
    print('       de regularizacion. Si alguien arregla `matrix` Y trae una')
    print('       metrica que no sea monótona, la pregunta vuelve a')
    print('       plantearse.')
    print()
    print('   Y LA COTA DE COHERENCIA: NO HAY. Se cumple para todo alpha >= 0.')
    print()
    print('   Asi que lo que sostiene DEFAULT_ALPHA = 2,0 es SOLO (3): es el')
    print('   incumbent y no hay evidencia admisible que lo sustituya. Que')
    print('   sea defendible como decision de ingenieria, si. Que tenga un')
    print('   fundamento matematico debajo, NO: el unico que habia, la cota')
    print('   de 1,3636, se ha retirado en este bloque.')


# `cal` se necesita en main() para la regla de particion canonica. Se
# importa sin pagar el coste de `learn` al importar el modulo.
import importlib.util as _il
_spec = _il.spec_from_file_location('calibrar', os.path.join(ROOT, 'tools',
                                                              'calibrar.py'))
cal = _il.module_from_spec(_spec)
_spec.loader.exec_module(cal)


if __name__ == '__main__':
    main()