# -*- coding: utf-8 -*-
"""LA EQUITY PREFLOP OBSERVABLE, Y QUE NO USE LAS CARTAS DEL RIVAL.

Y los dos tests que `DOCS/CONTRATO_PREFLOP.md` pide, escritos y CORRIENDO:
el de la cobertura observable y el de la fuga de información. Y el segundo es
el importante:

> «Si el rango se construye con las cartas del rival, esto falla. La tentación
> va a ser pasarle la mano real porque es más exacto. Este test es para que
> eso no pase por sin que se note: es una fuga de información y no se nota en
> el número, solo en que el número es demasiado bueno.»

Y el motor YA tiene el camino observable —`equity_preflop_rango`, que solo
recibe el RANGO del rival—, de modo que el test se puede escribir de verdad: y
lo que se comprueba es que la mano del rival no entra por ningun lado.

Y el test es BARATO, y el motivo es que se intercepta la evaluacion por
combo: lo que se prueba es QUE COMBOS se eligen, que es la pregunta, y no
cuanto vale cada uno, que es lo caro.
"""
import ast
import io
import os

import numpy as np

from motor import hand_evaluator as he

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _combo_legal(hero_codes):
    """El indice del primer combo legal para el hero.

    Y es el MISMO criterio que usa el motor —los combos que no contienen
    ninguna carta del hero—, y no uno propio: que sea el motor el que diga
    cual es legal es lo que hace que la comparacion signifique algo.
    """
    hero = he._cards_de_hero(hero_codes)
    mask = 0
    for c in hero:
        mask |= (1 << int(c))
    ids = np.where((he.HAND_MASKS & mask) == 0)[0]
    assert ids.size, 'no hay combos legales'
    return int(ids[0])


def test_la_equity_preflop_no_usa_las_cartas_del_rival(monkeypatch):
    """Y que el UNICO dato del rival que entra sea su rango.

    Y el montaje: un rango con masa en UN solo combo, y la evaluacion por
    combo interceptada. Si el motor usara las cartas reales del rival, los
    combos que se mirarian serian OTROS —o serian mas de uno— y el test
    falla.

    Y el resultado: con un solo combo, la equity es la de ese combo, y el
    estimador es la media simple —sin volver a ponderar—, de modo que el
    valor sale exacto.
    """
    vistos = []

    def _falso(hero, villain):
        vistos.append((int(villain[0]), int(villain[1])))
        return 0.25

    monkeypatch.setattr(he, 'equity_preflop_contra_combo', _falso)

    hero_codes = ['As', 'Kd']
    idx = _combo_legal(hero_codes)
    reach = np.zeros(1326)
    reach[idx] = 1.0

    eq = he.equity_preflop_rango(hero_codes, reach, n_combos=5, seed=7)

    esperado = (int(he.COMBO0[idx]), int(he.COMBO1[idx]))
    assert set(vistos) == {esperado}, (
        'se han evaluado %d combos distintos, y con un rango de masa en uno '
        'solo tiene que ser UNO: %r. Y si se mira mas de uno, o uno que no '
        'es el del rango, es que ha entrado informacion que no debia.'
        % (len(set(vistos)), sorted(set(vistos))[:6]))
    assert eq == 0.25


def test_la_equity_preflop_es_determinista(monkeypatch):
    """Y que el mismo `seed` de el mismo numero.

    Y el motivo: si el estimador no fuera determinista, ninguna de las
    cifras que dependan de el seria reproducible, y el intervalo del AUC
    seria del ruido del muestreo y no de la muestra.

    Y la evaluacion por combo se intercepta, y el motivo es el coste: cada
    combo enumera C(48,5) = 1 712 304 sorteos, de modo que la determinidad
    del MUESTREO —que es lo que se mide— se comprueba sin pagar la
    enumeracion. Y lo que se mide es el muestreo: con el mismo `seed`, los
    MISMOS combos, en el mismo orden.
    """
    vistos = []

    def _falso(hero, villain):
        vistos.append((int(villain[0]), int(villain[1])))
        return 0.25

    monkeypatch.setattr(he, 'equity_preflop_contra_combo', _falso)

    hero_codes = ['As', 'Kd']
    reach = np.zeros(1326)
    reach[_combo_legal(hero_codes)] = 1.0
    a = he.equity_preflop_rango(hero_codes, reach, n_combos=3, seed=7)
    b = he.equity_preflop_rango(hero_codes, reach, n_combos=3, seed=7)
    assert a == b
    # y con el MISMO seed salen los MISMOS combos, que es lo que significa
    # determinista
    assert len(vistos) == 6, vistos
    assert vistos[:3] == vistos[3:], vistos


def test_el_camino_observable_llega_desde_situation():
    """Y que `situation.equity_vs_range` delega en el camino observable.

    Y el motivo de que sea un test sobre el ARBOL y no una llamada: la
    llamada cuesta —con los parametros por defecto son 200 combos, y cada
    combo enumera C(48,5) sorteos—, y lo que se fija aqui es el ENCAMINAMIENTO,
    que es una cosa de codigo y no de numero.
    """
    ruta = os.path.join(ROOT, 'motor', 'situation.py')
    with io.open(ruta, encoding='utf-8') as f:
        arbol = ast.parse(f.read())
    fn = next(n for n in ast.walk(arbol)
              if isinstance(n, ast.FunctionDef)
              and n.name == 'equity_vs_range')
    llamadas = [ast.unparse(n.func) for n in ast.walk(fn)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)]
    assert 'equity_preflop_rango' in llamadas, (
        '`equity_vs_range` no llama a `equity_preflop_rango`: el camino '
        'observable no esta conectado, y las llamadas son %r' % llamadas)


def test_la_firma_de_la_equity_preflop_no_se_ha_tocado():
    """Y que la firma siga siendo la que el contrato escribio.

    Y el motivo: el contrato dice, textual, que la firma esta «sin tocar». Y
    un contrato que dice «sin tocar» y no lo vigila, es un contrato que
    dice «sin tocar» hasta que alguien la toque.
    """
    import inspect
    firma = str(inspect.signature(he.equity_preflop_rango))
    for nombre in ('hero_codes', 'villain_reach', 'n_runouts', 'n_combos',
                   'seed'):
        assert nombre in firma, (
            'la firma de `equity_preflop_rango` ya no tiene %r: %s'
            % (nombre, firma))
    # y los parametros por defecto, que el contrato declara
    assert 'DEFAULT_RUNOUT_COMBOS' in io.open(
        os.path.join(ROOT, 'motor', 'hand_evaluator.py'),
        encoding='utf-8').read(), (
        'el contrato declara que `DEFAULT_RUNOUT_COMBOS = 200` de '
        '`decision.py` NO se baja a 40, y esa constante tiene que seguir '
        'en `hand_evaluator.py`')

def test_el_camino_observable_funciona_de_situation(monkeypatch):
    """Y que la delegacion FUNCIONA, y no solo que existe.

    Y el motivo de que haga falta: el test anterior comprueba que la
    DELGACION esta en el codigo —por el arbol—, y eso no dice que el camino
    funcione. Y un camino que no funciona y un camino que no existe dan el
    mismo resultado en un test que solo mira el arbol.

    Y el `n_combos` se puede bajar porque `equity_vs_range` lo expone, que es
    lo que hace que el camino sea practicable: con 200 combos, cada mano
    cuesta minutos.
    """
    from motor import situation

    def _falso(hero, villain):
        return 0.25

    monkeypatch.setattr(he, 'equity_preflop_contra_combo', _falso)

    hero_codes = ['As', 'Kd']
    reach = np.zeros(1326)
    reach[_combo_legal(hero_codes)] = 1.0

    eq, wins, ties, losses = situation.equity_vs_range(
        hero_codes, [], villain_reach=reach, n_combos=2)
    assert eq == 0.25
    assert abs(wins + ties + losses - 1.0) < 1e-9

