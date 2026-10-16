# -*- coding: utf-8 -*-
"""El AUC de la equity, con su intervalo. `CONTRATO_L_SEC.md` §8.

Y el summarise de lo que `revision_2` §1 encontró en la versión anterior:

  `c, v = cal.muestra()` seguido de `{i: y for i, y in c + v}` mete las manos
  de CALIBRACIÓN junto con las de VALIDACIÓN. El modelo sí se ajustaba solo en
  calibración, pero las predicciones evaluadas incluían también las manos con
  las que se ajustó. Eso mezcla dentro y fuera de muestra, y empuja el AUC
  HACIA ARRIBA. El resultado anterior queda como provisional y se rehace.

Lo corregido aquí:

  1. `etiqueta = dict(v)`. Solo validación, y una comprobación EXPLÍCITA de
     que todo lo evaluado es validación. No un `assert`, que desaparece con
     `python -O`: una función que lanza.
  2. La partición se llama a `calibrar.es_validacion`, que es la regla
     canónica. Aquí ya no hay una segunda copia de la regla que pueda
     divergir en silencio.
  3. El IC bootstrap es ESTRATIFICADO: se remuestrea por separado las
     victorias y las derrotas, que conserva los tamaños de las dos clases. La
     versión anterior remuestreaba la muestra conjunta y descartaba las
     réplicas que perdían una clase, que es un sesgo.
  4. El p de permutaciones es `(ge + 1) / (n + 1)`, la corrección de Monte
     Carlo. `ge / n` puede informar p = 0, que no existe.
  5. El IC y el p se INFORMAN POR SEPARADO. No son dos intervalos: uno
     expresa incertidumbre sobre el AUC, el otro evidencia contra H0. La
     versión anterior decía "los dos métodos coinciden" cuando el veredicto
     solo miraba el intervalo.

La hipótesis nula es DIRECCIONAL, declarada antes de mirar: H0 es AUC ≤ 0,5.
Por eso el test de permutaciones cuenta una sola cola.
"""
import collections
import importlib.util
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn, player_ranges

BOOTSTRAP = 10_000
PERMUTACIONES = 10_000
SEMILLA = 7
NIVEL = 0.05


def _m(nombre):
    ruta = os.path.join(ROOT, 'tools', nombre)
    spec = importlib.util.spec_from_file_location(nombre[:-3], ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


eqm = _m('equity_de_mano.py')
cal = _m('calibrar.py')


class FugaDeValidacion(RuntimeError):
    """Se evaluo una mano que no es de la particion de validacion."""


def comprobar_solo_validacion(ids):
    """Falla si algum ID evaluado no es de validacion.

    `revision_2` §1. Es una funcion que lanza y no un `assert` a proposito:
    `python -O` se come los asserts, y esta es exactamente la comprobacion
    que no puede desaparecer.
    """
    malos = [i for i in ids if not cal.es_validacion(i)]
    if malos:
        raise FugaDeValidacion(
            '%d de las %d manos evaluadas NO son de validacion: %s'
            % (len(malos), len(ids), sorted(malos)[:8]))
    return True


def auc_de(pos, neg):
    """AUC por comparaciones a pares. None si falta una clase."""
    if not pos or not neg:
        return None
    t = 0.0
    for p in pos:
        for n in neg:
            t += 1.0 if p > n else (0.5 if p == n else 0.0)
    return t / (len(pos) * len(neg))


def auc_rapido(et, v):
    """AUC por rangos con correccion de empates. Mucho mas rapido que O(n*m)."""
    n1 = int(et.sum())
    n0 = len(et) - n1
    if n1 == 0 or n0 == 0:
        return None
    orden = np.argsort(v, kind='mergesort')
    v, et = v[orden], et[orden]
    rangos = np.empty(len(v), dtype=float)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[j + 1] == v[i]:
            j += 1
        rangos[i:j + 1] = (i + j) / 2.0 + 1.0
        i = j + 1
    u = rangos[et == 1].sum() - n1 * (n1 + 1) / 2.0
    return u / (n1 * n0)


def ic_bootstrap(pos, neg, n=BOOTSTRAP, semilla=SEMILLA, estratificado=True):
    """(lo, hi) al 95 % por bootstrap percentil.

    ESTRATIFICADO por defecto: se remuestrea por separado las victorias y las
    derrotas, y se conservan los dos tamaños. La versión anterior remuestreaba
    la muestra conjunta y tiraba las réplicas que perdían una clase, lo que
    sesga el intervalo hacia el lado que tiene más manos.
    """
    rng = np.random.default_rng(semilla)
    ps = np.asarray([x for x in pos if np.isfinite(x)], dtype=float)
    ns = np.asarray([x for x in neg if np.isfinite(x)], dtype=float)
    if len(ps) < 2 or len(ns) < 2:
        return None
    if estratificado:
        et = np.concatenate([np.ones(len(ps)), np.zeros(len(ns))]).astype(int)
        todos = np.concatenate([ps, ns])
        vals = []
        for _ in range(n):
            i1 = rng.integers(0, len(ps), len(ps))
            i0 = rng.integers(0, len(ns), len(ns))
            s = np.concatenate([ps[i1], ns[i0]])
            e = np.concatenate([np.ones(len(i1)), np.zeros(len(i0))]).astype(int)
            a = auc_rapido(e, s)
            if a is not None:
                vals.append(a)
    else:
        m = len(ps) + len(ns)
        todos = np.concatenate([ps, ns])
        et = np.concatenate([np.ones(len(ps)), np.zeros(len(ns))]).astype(int)
        vals = []
        for _ in range(n):
            idx = rng.integers(0, m, m)
            a = auc_rapido(et[idx], todos[idx])
            if a is not None:
                vals.append(a)
    if not vals:
        return None
    return (float(np.percentile(vals, 2.5)),
            float(np.percentile(vals, 97.5)))


def p_permutaciones(pos, neg, n=PERMUTACIONES, semilla=SEMILLA):
    """p-valor de una cola de H0: AUC <= 0,5. Correccion (ge+1)/(n+1).

    UNA COLA, y declarada: la hipótesis direccional es que la equity ordena
    mejor que el azar, que es lo que `CONTRATO_L_SEC.md` §8 fija antes de
    mirar los numeros. Con una sola cola el p es la cola correcta; si la
    hipótesis fuera de dos colas habria que duplicarlo, y eso se declararia
    tambien.

    La corrección `(ge + 1) / (n + 1)` es la de Monte Carlo: con `ge / n` una
    permutacion puede dar p = 0 exactamente, que es un valor imposible.
    """
    rng = np.random.default_rng(semilla)
    obs = auc_de(pos, neg)
    if obs is None:
        return None, 0, 0
    base = np.concatenate([np.asarray(pos, float),
                           np.asarray(neg, float)])
    n1 = len(pos)
    ge = 0
    for _ in range(n):
        # COPIA: barajar in-place el mismo array lo degrada entre iteraciones
        todos = base.copy()
        rng.shuffle(todos)
        a = auc_de(todos[:n1].tolist(), todos[n1:].tolist())
        if a is not None and a >= obs - 1e-12:
            ge += 1
    return min(1.0, (ge + 1) / (n + 1)), ge, n


def _poblaciones(filas):
    return {
        'A) el hero CONTINUA (b/c/r)':
            [f for f in filas if f[2] in ('b', 'c', 'r')],
        'B) el hero CONTINUA o CHECKea':
            [f for f in filas if f[2] in ('b', 'c', 'r', 'x')],
    }


def main():
    ventana = learn.load_hands(reliable_only=True)
    # AJUSTE: solo calibracion. La regla es la de `calibrar`, la canonica.
    ajuste = [h for h in ventana if not cal.es_validacion(h['hand_id'])]
    labels = eqm.perfiles_de(ajuste)
    mod = {'preflop': player_ranges.ProfileRangeModel.from_hands(
        ajuste, alpha=player_ranges.DEFAULT_ALPHA), 'postflop': None}

    cal_, val_ = cal.muestra()

    # EVALUACION: solo VALIDACION. Este es el arreglo de `revision_2` §1.
    etiqueta = dict(val_)
    comprobar_solo_validacion(etiqueta)

    por_id = {h['hand_id']: h for h in ventana}

    print('=' * 78)
    print('1) LA SEPARACION ENTRE AJUSTE Y EVALUACION')
    print('=' * 78)
    print()
    print('   manos de la muestra        : %d' % (len(cal_) + len(val_)))
    print('   de las cuales CALIBRACION  : %d   (sirven para AJUSTAR)'
          % len(cal_))
    print('   de las cuales VALIDACION   : %d   (sirven para EVALUAR)'
          % len(val_))
    print('   reglas de particion        : %d / %d = 0,30'
          % (len(val_), len(cal_) + len(val_)))
    print()
    print('   AJUSTE  : %d manos, la regla de `calibrar.es_validacion`'
          % len(ajuste))
    print('   EVALUAR : %d manos, comprobado una a una' % len(etiqueta))
    print()
    print('   La version anterior evaluaba las %d: mezclaba las manos con'
          % (len(cal_) + len(val_)))
    print('   las que se ajusto el modelo. Se rehace el numero entero.')
    print()

    filas = []
    exc = collections.Counter()
    for hid, y in sorted(etiqueta.items()):
        h = por_id[hid]
        hero = eqm.hero_pos_de(h)
        if not hero:
            exc['sin hero'] += 1
            continue
        calle, idx = eqm.corte_de_decision(h, hero)
        if calle is None:
            exc['el hero no actuo'] += 1
            continue
        if y == 0.5:
            exc['reparto (AUC binario)'] += 1
            continue
        if calle == 'preflop':
            exc['preflop retrospectiva'] += 1
            continue
        r = eqm.equity_de_mano(h, labels, mod)
        if r is None or len(r) != 3:
            exc['sin equity'] += 1
            continue
        if r[2].get('observable') is False:
            exc['retrospectiva'] += 1
            continue
        acts = ((h.get('streets') or {}).get(calle) or {}).get('actions') or []
        if idx is None or idx >= len(acts):
            exc['no se lee la accion'] += 1
            continue
        filas.append((r[1]['mediana'], y, acts[idx].get('action')))

    print('=' * 78)
    print('2) QUE ENTRA AL AUC')
    print('=' * 78)
    print()
    print('   manos que entran : %d de %d de validacion'
          % (len(filas), len(etiqueta)))
    for k, n in exc.most_common():
        print('      excluida: %-40s %3d' % (k, n))
    print()
    for calle, n in collections.Counter(
            eqm.corte_de_decision(por_id[i], eqm.hero_pos_de(por_id[i]))[0]
            for i in etiqueta).items():
        print('      corte en %-10s %4d' % (calle, n))
    print()

    print('=' * 78)
    print('3) EL AUC. IC E INFERENCIA, POR SEPARADO')
    print('=' * 78)
    print()
    print('   El IC bootstrap responde: "de que valor puede ser el AUC".')
    print('   El p de permutaciones responde: "hay evidencia de que el AUC')
    print('   supera 0,5". NO SON DOS INTERVALOS y no se comparan entre si.')
    print()
    print('   %-34s %5s %6s %7s' % ('poblacion', 'n', 'gana', 'pierde'))
    print('   ' + '-' * 60)

    for nombre, sel in _poblaciones(filas).items():
        pos = [f[0] for f in sel if f[1] == 1.0]
        neg = [f[0] for f in sel if f[1] == 0.0]
        print('   %s' % nombre)
        print('      n=%d   gana=%d   pierde=%d'
              % (len(sel), len(pos), len(neg)))
        if not pos or not neg:
            print('      AUC NO DEFINIDO: falta una de las dos clases.')
            print('      Con una sola clase no hay nada que ordenar.')
            print()
            continue
        a = auc_de(pos, neg)
        ic = ic_bootstrap(pos, neg)
        p, ge, tot = p_permutaciones(pos, neg)
        lo, hi = ic
        print('      AUC                          : %.4f' % a)
        print('      95%% IC bootstrap ESTRATIFICADO: [%.4f, %.4f]' % (lo, hi))
        print('      una clase por debajo / una por encima, sin descartar')
        print('      ninguna réplica.')
        print('      p de permutaciones (1 cola)  : %.4f   (%d de %d, %s)'
              % (p, ge, tot, 'p corrector Monte Carlo'))
        print()
        excluye = not (lo <= 0.5 <= hi)
        rechaza = p < NIVEL
        print('      el IC excluye 0,5            : %s'
              % ('SI' if excluye else 'NO'))
        print('      el p rechaza H0 al %.0f%%      : %s'
              % (NIVEL * 100, 'SI' if rechaza else 'NO'))
        print()
        if excluye and rechaza:
            print('      LECTURA: las dos evidencias apuntan al mismo lado.')
            print('      El IC da el valor, el p da la fuerza. Es el caso')
            print('      fuerte, y aun asi no dice mas de lo que dice.')
        elif excluye or rechaza:
            print('      LECTURA: SOLO UNA de las dos evidencias. No se')
            print('      afirma: se publica la que sale y se dice cual.')
        else:
            print('      LECTURA: NO AFIRMABLE. El intervalo incluye 0,5.')
            print('      Con esta muestra no se puede distinguir orden')
            print('      util de azar, y esa es la conclusion.')
        print()

    print('=' * 78)
    print('4) LO QUE ESTO SIGUE SIN DECIR')
    print('=' * 78)
    print()
    print('   - Que la equity este CALIBRADA. Un AUC mide orden, no escala.')
    print('   - Que el motor decida bien. Eso es el objetivo C, que sigue')
    print('     fuera por falta de etiqueta de optimalidad.')
    print('   - Que ordene en PREFLOP. Las manos preflop siguen fuera porque')
    print('     su equity es retrospectiva. El camino preflop observable es')
    print('     lo que las mete, y todavia no existe.')
    print()
    print('   Y `DEFAULT_ALPHA` sigue en 2,0: nada de esto dice que un alpha')
    print('   sea mejor que otro.')


if __name__ == '__main__':
    main()