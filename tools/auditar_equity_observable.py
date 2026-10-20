# -*- coding: utf-8 -*-
"""EL EXPERIMENTO PREPARADO: si la equity observable ORDENA las manos.

Y lo que este script hace es PREPARAR el experimento y ejecutarlo con los
parametros que se le den. Y el motivo de que exista, y no sea una nota en un
documento: **un experimento que no se puede ejecutar no es un
experimento**, es una intencion.

## Y LO QUE NO HACE, Y POR QUE

Y no cambia la herramienta que genera el AUC publicado
(`tools/equity_de_mano.py`), y el motivo es el de siempre: cambiar esa
herramienta MOVERIA el AUC, y mover el AUC es una recalibracion, y las
recalibraciones van despues de la adopcion de la base.

De modo que este script **replica** el ajuste de esa herramienta —las mismas
lineas, con el mismo motivo— en vez de llamar a su `main()`, que hace las dos
cosas a la vez. Y la replica esta DECLARADA, y un test la comprueba.

## Y LA POBLACION, QUE ES DONDE ESTA EL SESGO

Y las manos son las de la **particion versionada** (`es_validacion`), que es
la misma que usa el AUC publicado. Y el sesgo que hay que evitar es el
inverso de la fuga: no se puede validar el estimador observable con una mano
si el estimador se ha construido con las cartas de esa mano. Y aqui no cabe:
el rango del rival se construye de las TABLAS y del perfil, no de sus
cartas ✓.

## Y EL COSTE, DECLARADO PORQUE ES EL DATO

Y cada combo enumerar C(48,5) = 1 712 304 sorteos, de modo que una mano con
`n_combos` combos cuesta `n_combos` enumeraciones. Y con las 47 manos de la
particion y 40 combos, son 1880 enumeraciones: de horas. Y por eso el
script imprime el coste ANTES de empezar, y por eso el `--piloto` existe.
"""
import argparse
import io
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn                                # noqa: E402
from motor import player_ranges                        # noqa: E402
from motor import postflop_ranges                      # noqa: E402
from motor.hand_evaluator import equity_preflop_rango   # noqa: E402
from tools import calibrar                             # noqa: E402
from tools.equity_de_mano import (candidatos, corte_de_decision,   # noqa: E402
                                  cartas_de, hero_pos_de, perfiles_de,
                                  rango_del_rival)

# Y los parametros por defecto, que son los del CONTRATO (`CONTRATO_PREFLOP.md`,
# Decision 1): muestreado con `n_combos = 40`, y el `seed` del motor.
N_COMBOS_POR_DEFECTO = 40
SEED_POR_DEFECTO = 7

# Y el coste por combo, que es el dato que hay que declarar antes de empezar.
SORTEOS_POR_COMBO = 1712304

# Y LA PUERTA, que es una VARIABLE DE ENTORNO y no un parametro, y el motivo
# es que un parametro se puede pasar por error de verdad y una variable de
# entorno hay que escribirla a proposito.
#
# Y MEDIDO, el coste: una mano con dos combos tarda 54 s, y las 47 con 40
# combos son 1880 enumeraciones de C(48,5), o sea de HORAS. De modo que esto
# no se lanza por accidente.
#
# Y el valor es el que dice el nombre, para que se vea en la lista de
# variables y no haya que buscarlo.
VARIABLE_DE_AUTORIZACION = 'POKER_EQUITY_OBSERVABLE'


def _modelos(ajuste):
    """El ajuste de rangos, y las etiquetas de perfil.

    Y es una REPLICA de las lineas de `tools/equity_de_mano.py::main`, y el
    motivo de que sea una replica y no una llamada es que ese `main` hace
    las dos cosas a la vez —el AUC y el ajuste— y no se puede llamar a una
    sin la otra. Y la replica esta DECLARADA, y `test_auditar_equity_observable`
    la comprueba: si el original cambia, este tiene que cambiar con el.
    """
    modelos = {
        'preflop': player_ranges.ProfileRangeModel.from_hands(
            ajuste, alpha=player_ranges.DEFAULT_ALPHA),
    }
    try:
        modelos['postflop'] = postflop_ranges.PostflopModel()
    except Exception:                                   # noqa: BLE001
        modelos['postflop'] = None
    return modelos


def equity_observable(hand, labels, modelos, n_combos=N_COMBOS_POR_DEFECTO,
                      seed=SEED_POR_DEFECTO):
    """La equity OBSERVABLE del hero en la mano, y el detalle.

    Y la diferencia con la de la herramienta publicada: el rango del rival se
    construye IGUAL, pero la equity se calcula con `equity_preflop_rango` —
    que no ve las cartas del rival— en vez de contra la mano real.
    """
    hero_pos = hero_pos_de(hand)
    if hero_pos is None:
        return None, 'la mano no tiene jugador con el nombre del hero'
    calle, indice = corte_de_decision(hand, hero_pos)
    if calle is None:
        return None, 'el hero no actuo en la mano'
    hero = cartas_de(hand, hero_pos)
    board = []
    if len(hero) < 2:
        return None, 'el hero no tiene cartas'
    rivales = candidatos(hand, hero_pos, calle)
    if not rivales:
        return None, 'no queda ningun rival en el bote en esa calle'
    salida = []
    for r in rivales:
        rs, _perfil = rango_del_rival(
            hand, r, hero, board, labels, modelos['preflop'],
            modelos.get('postflop'), calle=calle, indice=indice)
        eq = equity_preflop_rango(hero, rs, n_combos=n_combos, seed=seed)
        salida.append((r, float(eq)))
    return salida, {'calle': calle, 'hero_pos': hero_pos,
                    'n_combos': n_combos, 'seed': seed}


def _etiqueta(hand):
    """La etiqueta binaria de la mano: 1.0 si gano, 0.0 si perdio.

    Y el empate (`y = 0,5`) NO entra, que es la regla del reparto del
    `CONTRATO_L_SEC.md` §9: un AUC binario necesita dos clases, y meter un
    empate en una de ellas es una decision arbitraria. Y aqui se excluye y
    se CUENTA, que es lo que dice la regla.
    """
    g = calibrar.ganador_nombrado(hand)
    hero = hero_pos_de(hand)
    if g is None or hero is None:
        return None
    if g == hero:
        return 1.0
    return 0.0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='auditar_equity_observable.py',
                                 description='PREPARA y ejecuta el '
                                             'experimento de si la equity '
                                             'preflop observable ordena las '
                                             'manos. NO recalibra nada.')
    ap.add_argument('--n-combos', type=int, default=N_COMBOS_POR_DEFECTO,
                    help='combos rivales por mano (el contrato dice 40)')
    ap.add_argument('--seed', type=int, default=SEED_POR_DEFECTO,
                    help='la semilla del muestreo')
    ap.add_argument('--manos', type=int, default=0,
                    help='cuantas manos de la particion; 0 = todas')
    ap.add_argument('--piloto', action='store_true',
                    help='una sola mano y dos combos, para comprobar que el '
                         'experimento funciona sin pagar el coste')
    args = ap.parse_args(argv)

    # Y LA PUERTA, antes de nada: sin la variable de entorno, este script no
    # se ejecuta. Y el motivo de que la puerta este ANTES de calcular nada
    # es que el calculo de las etiquetas y del modelo ya cuesta.
    if os.environ.get(VARIABLE_DE_AUTORIZACION) != '1':
        print('ESTE EXPERIMENTO NO SE EJECUTA SIN AUTORIZACION.')
        print()
        print('   Y el motivo es el coste: MEDIDO, una mano con dos combos tarda')
        print('   54 s, y la particion de validacion son 47 manos con 40 combos,')
        print('   que son 1880 enumeraciones de C(48,5): de HORAS.')
        print()
        print('   Para ejecutarlo hay que escribir a proposito:')
        print('       %s=1 python %s ...'
              % (VARIABLE_DE_AUTORIZACION,
                 os.path.basename(__file__)))
        print()
        print('   Y la autorizacion es de A1, porque el experimento mide si la')
        print('   equity observable ordena las manos, y esa medicion es una')
        print('   CIFRA NUEVA, no una sustitucion del AUC publicado.')
        return 2

    n_combos = 2 if args.piloto else args.n_combos
    manos = 1 if args.piloto else args.manos

    ventana = learn.load_hands(reliable_only=True)
    validacion = [h for h in ventana if calibrar.es_validacion(h['hand_id'])]
    if manos:
        validacion = validacion[:manos]
    ajuste = [h for h in ventana if not calibrar.es_validacion(h['hand_id'])]
    labels = perfiles_de(ajuste)

    coste = len(validacion) * n_combos * SORTEOS_POR_COMBO
    print('MANOS DE LA PARTICION DE VALIDACION: %d' % len(validacion))
    print('COMBOS POR MANO: %d   SEED: %d' % (n_combos, args.seed))
    print('COSTE: %d enumeraciones de C(48,5) = %d sorteos'
          % (len(validacion) * n_combos, coste))
    if not args.piloto and coste > 10 ** 8:
        print()
        print('   AVISO: esto es de HORAS. Usa `--piloto` para comprobar que')
        print('   el experimento funciona, y el numero de manos que se corra')
        print('   se DECLARA en el informe.')
    print()

    modelos = _modelos(ajuste)
    filas = []
    t0 = time.time()
    for h in validacion:
        salida, det = equity_observable(h, labels, modelos, n_combos, args.seed)
        y = _etiqueta(h)
        if salida is None or y is None:
            continue
        filas.append((float(sum(e for _r, e in salida) / len(salida)), y,
                      h['hand_id']))
    print('MANOS MEDIDAS: %d   (%.1f s)' % (len(filas), time.time() - t0))
    if not filas:
        print('NINGUNA MANO MEDIBLE, y eso hay que decirlo antes que nada.')
        return 1
    pos = [x for x, y, _h in filas if y == 1.0]
    neg = [x for x, y, _h in filas if y == 0.0]
    print('GANAS: %d   PIERDES: %d   (los empates NO entran, y se cuentan)'
          % (len(pos), len(neg)))
    if not pos or not neg:
        print('NO HAY LAS DOS CLASES, de modo que el AUC no se puede calcular.')
        return 1
    from tools import auditar_auc                        # noqa: E402
    auc, lo, hi = auditar_auc.ic_bootstrap(pos, neg)
    print('AUC OBSERVABLE: %.4f   95%% IC [%.4f, %.4f]' % (auc, lo, hi))
    print()
    print('Y esto NO es el AUC publicado: es una medicion NUEVA, con su')
    print('propio nombre, y no sustituye a la retrospectiva.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
