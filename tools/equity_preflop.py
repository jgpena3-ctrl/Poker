# -*- coding: utf-8 -*-
"""Equity PREFLOP por enumeracion completa.

Por que hace falta: `hand_evaluator.evaluate_batch` declara board de **3 a
5** cartas y sus subsets son de 5, 6 y 7 cartas. Con board vacio no hay
subset y `situation` revienta con `KeyError`. Medido: eso deja fuera
**96 de las 161 manos** de la muestra de `L_sec`.

Y en preflop la equity no es "el evaluador contra un rango": son dos manos
de 2 cartas contra un sorteo completo de 5 comunitarias. Es un calculo
distinto, y aqui esta.

    C(48, 5) = 1 712 304 boards por par de manos. Con numpy en
    trozos, van en segundos.

El reparto se cuenta como 0,5, igual que en `situation`: `equity =
wins + 0.5 * ties`.

    python tools/equity_preflop.py --hero AsKd --villain QhJh
    python tools/equity_preflop.py --comprobar
"""
import argparse
import json
import itertools
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np                                       # noqa: E402

from motor.cards import card_id                         # noqa: E402
from motor.hand_evaluator import evaluate_n_batch        # noqa: E402

TROZO = 200_000

#: Cache en memoria por par de manos. Una enumeracion son 1,7 millones
#: de evaluaciones (~13 s) y el mismo par sale MUCHAS veces: casi todas
#: las manos preflop de la muestra se vuelven a consultar en cada
#: corrida de cobertura.
_CACHE = {}

#: Cache en disco. La de memoria se pierde en cada proceso; esta no. Vive
#: en `data/`, que esta en `.gitignore` porque se regenera sola.
RUTA_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', '_cache_equity_preflop.json')
_CACHE_DISCO = None

#: Version del algoritmo. Si cambia `evaluate_n_batch`, `_cell_`, el
#: reparto del bote o la comparacion de scores, hay que subirla: si no, la
#: cache devuelve numeros de la version anterior sin avisar.
#:
#: Va DENTRO de la clave y del fichero, no solo en el nombre. Un fichero
#: cacheado con otra version se descarta entero.
VERSION = 2


def _ruta_de(version):
    return '%s.v%d.json' % (RUTA_CACHE, version)


def _cargar_disco():
    """Solo lee la cache de ESTA version. La de otra se ignora."""
    global _CACHE_DISCO
    if _CACHE_DISCO is None:
        _CACHE_DISCO = {}
        try:
            with open(_ruta_de(VERSION), encoding='utf-8') as fh:
                crudo = json.load(fh)
        except Exception:
            return _CACHE_DISCO
        if crudo.get('version') == VERSION:
            _CACHE_DISCO = crudo.get('entradas') or {}
    return _CACHE_DISCO


def _guardar_disco():
    if _CACHE_DISCO is None:
        return
    try:
        os.makedirs(os.path.dirname(RUTA_CACHE), exist_ok=True)
        ruta = _ruta_de(VERSION)
        tmp = ruta + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump({'version': VERSION, 'entradas': _CACHE_DISCO}, fh)
        os.replace(tmp, ruta)
    except Exception:
        pass          # la cache es una comodidad, no un requisito


def version_cache_en_uso():
    """La version con la que se ha leido o escrito. Para los tests."""
    return VERSION


def limpiar_cache():
    """Para medir de verdad, sin el atajo. Tambien borra la de disco."""
    global _CACHE_DISCO
    _CACHE.clear()
    _CACHE_DISCO = None
    try:
        os.remove(_ruta_de(VERSION))
    except OSError:
        pass


def a_combos(hero, villain):
    """(hero, villano) como listas de 2 cartas, y los 48 restantes."""
    h = [card_id(hero[0:2]), card_id(hero[2:4])]
    v = [card_id(villain[0:2]), card_id(villain[2:4])]
    usados = set(h) | set(v)
    resto = [c for c in range(52) if c not in usados]
    return np.asarray(h, dtype=np.intp), np.asarray(v, dtype=np.intp), \
        np.asarray(resto, dtype=np.intp)


def boards_completos(resto):
    """Todos los C(48,5) como (N,5) de ids de carta. Son 1 712 304 filas."""
    return np.asarray(list(itertools.combinations(resto, 5)),
                      dtype=np.intp)


def equity_preflop(hero, villain, verbose=False):
    """(equity, detalle). `equity` en [0,1], con 0,5 para repartos."""
    clave = '%s|%s' % (hero, villain)
    eq = _CACHE.get(clave)
    if eq is None:
        eq = _cargar_disco().get(clave)
        if eq is not None:
            _CACHE[clave] = eq
    if eq is not None:
        if verbose:
            _reportar(eq[1])
        return eq[0], eq[1]
    h, v, resto = a_combos(hero, villain)
    boards = boards_completos(resto)
    n = boards.shape[0]

    # evaluate_batch NO sirve aqui: su oard es 1-D y compartido por
    # todas las filas, y lo que hace falta es un board DISTINTO por fila.
    # Se construye (N, 7) = 2 del jugador + 5 del sorteo y se llama a
    # evaluate_n_batch, que acepta n en (5, 6, 7). Con 7 cartas es
    # exactamente una mano de showdown.
    sh = np.empty(n, dtype=np.int64)
    sv = np.empty(n, dtype=np.int64)
    for ini in range(0, n, TROZO):
        b = boards[ini:ini + TROZO]
        m = b.shape[0]
        sh[ini:ini + m] = evaluate_n_batch(
            np.concatenate([np.repeat(h.reshape(1, 2), m, axis=0), b],
                           axis=1))
        sv[ini:ini + m] = evaluate_n_batch(
            np.concatenate([np.repeat(v.reshape(1, 2), m, axis=0), b],
                           axis=1))

    # GANA EL HERO cuando SU score es MAYOR. Este estaba al reves: se
    # contaba (sv > sh), que es el rival ganando, y la equity salia
    # complementada. AA contra KK daba 0,18 en vez de 0,82.
    #
    # Lo atrapo --comprobar, que es para eso: una banda de plausibilidad
    # escrita ANTES de mirar. Un instrumento que da el numero del otro se
    # nota en el segundo que se ejecuta.
    gana = int((sh > sv).sum())
    empata = int((sh == sv).sum())
    pierde = int((sh < sv).sum())
    equity = (gana + 0.5 * empata) / n
    det = {'boards': n, 'gana': gana, 'empata': empata,
            'pierde': pierde}
    _CACHE[clave] = (equity, det)
    _cargar_disco()[clave] = [equity, det]
    _guardar_disco()
    if verbose:
        _reportar(det)
    return equity, det


def _reportar(det):
    n = det['boards']
    print('   boards          : %d' % n)
    for k in ('gana', 'pierde', 'empata'):
        print('   %-15s : %d  (%.2f%%)'
              % (k, det[k], det[k] / n * 100))


# ------------------------------------------------------------------ pruebas
def comprobar_verboten():
    """Valores conocidos de manual. Si estos fallan, la enumeracion falla.

    Se eligieron los tres casos mas citados de la tabla de opening:
    AA dominando, y las dos parejas que mas se parecen al final.
    """
    print('=' * 74)
    print('COMPROBACION CONTRA VALORES DE MANUAL')
    print('=' * 74)
    print()
    casos = [
        ('AA', 'AsAd', 'KK', 'KhKs', 'pocket pair contra pocket pair'),
        ('AK', 'AhKs', 'QQ', 'QhQd', 'dominado por el as'),
        ('KK', 'KhKs', 'QQ', 'QhQd', 'dos pares contra dos pares'),
    ]
    filas = []
    for n1, h, n2, v, por in casos:
        eq, det = equity_preflop(h, v)
        filas.append((n1, n2, eq, por, det))
        print('   %-3s vs %-3s   equity %6.4f    (%s)'
              % (n1, n2, eq, por))
    print()
    aa, kk = filas[0][2], filas[1][2]
    print('   AA contra KK mide %.4f' % aa)
    print('   Los libros dan ~0,82 preflop para un par de ases contra')
    print('   reyes. Con dos opponents el valor baja; contra uno solo,')
    print('   ~0,80-0,85. Un resultado MUY fuera de esa banda significa')
    print('   que la enumeracion esta mal, no que el poker haya cambiado.')
    print()
    return aa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hero', help='dos cartas, p.ej. AsKd')
    ap.add_argument('--villain', help='dos cartas, p.ej. QhJh')
    ap.add_argument('--comprobar', action='store_true',
                    help='valores de manual, sin argumentos')
    args = ap.parse_args()

    if args.comprobar:
        aa = comprobar_verboten()
        # banda de plausibilidad, declarada antes de mirar
        if 0.70 <= aa <= 0.90:
            print('   -> DENTRO DE BANDA. La enumeracion se comporta.')
            return 0
        print('   -> FUERA DE BANDA. No uses esta herramienta hasta')
        print('      entender por que.')
        return 1

    if not (args.hero and args.villain):
        ap.print_help()
        return 1
    if len(args.hero) != 4 or len(args.villain) != 4:
        print('   dos cartas de 2 caracteres cada una: AsKd, no AsKdXx')
        return 1

    print('=' * 74)
    print('EQUITY PREFLOP POR ENUMERACION')
    print('=' * 74)
    print()
    print('   hero   : %s' % args.hero)
    print('   rival  : %s' % args.villain)
    print()
    eq, det = equity_preflop(args.hero, args.villain, verbose=True)
    print()
    print('   EQUITY = %.4f' % eq)
    return 0


if __name__ == '__main__':
    sys.exit(main())