# -*- coding: utf-8 -*-
"""EL EXPERIMENTO PREPARADO, Y QUE NO TOCA LA HERRAMIENTA PUBLICADA.

Y lo que se comprueba aqui, en cuatro cosas:

  · que el experimento usa la **particion versionada**, que es la misma que
    usa el AUC publicado, de modo que la comparacion sea legitima;
  · que sus parametros por defecto son los del **CONTRATO** —muestreado con
    40 combos y la semilla del motor—;
  · que el **COSTE** esta declarado antes de empezar, porque es el dato que
    hace que el experimento sea de horas y no de segundos;
  · y que la herramienta que genera el AUC publicado **NO se toca**: su
    estimador sigue siendo el RETROSPECTIVO.

Y la ultima es la importante, y por eso se comprueba por el ARBOL y no por
un diff: que `equity_contra` siga usando la enumeracion contra la mano real
del rival. Y el motivo de que se compruebe por el arbol y no por el hash del
fichero es que el comentario de esa herramienta SI se ha corregido en este
bloque —un comentario no cambia el numero—, de modo que el hash moveria por
un motivo que no es el que se vigila.

Y el piloto, que es lo que demuestra que el experimento FUNCIONA, no corre
en la suite: MEDIDO, una mano con dos combos cuesta 54 s, y el piloto paga
ademas el ajuste del modelo. De modo que aqui se comprueba la fontintería con
la evaluacion interceptada, y el piloto real se ha ejecutado a mano.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ruta(nombre):
    return os.path.join(ROOT, *nombre.split('/'))


def _arbol(nombre):
    with io.open(_ruta(nombre), encoding='utf-8') as f:
        return ast.parse(f.read())


def test_el_experimento_usa_la_particion_versionada():
    """Y no una particion propia, que es donde entraria el sesgo.

    Y el motivo: la particion se VERSIONA y no se cambia una vez escrita, y
    la del AUC publicado es la misma. De modo que un experimento con otra
    particion mediria otra cosa, y su numero no se podria comparar con
    ningun otro.
    """
    arbol = _arbol('tools/auditar_equity_observable.py')
    llamadas = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Attribute):
            llamadas.add(ast.unparse(n))
    assert 'calibrar.es_validacion' in llamadas, (
        'el experimento no usa `calibrar.es_validacion`, que es la particion '
        'versionada: %r' % sorted(llamadas))


def test_los_parametros_por_defecto_son_los_del_contrato():
    """Y 40 combos y la semilla 7, que es lo que dice el contrato.

    Y el motivo: el contrato decidio «muestreado, con `n_combos = 40`», y un
    experimento con otro numero mide otra cosa, y su numero no se puede
    comparar con el AUC publicado ni con nada.
    """
    arbol = _arbol('tools/auditar_equity_observable.py')
    constantes = {}
    for n in arbol.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    constantes[t.id] = n.value.value
    assert constantes.get('N_COMBOS_POR_DEFECTO') == 40, constantes
    assert constantes.get('SEED_POR_DEFECTO') == 7, constantes
    assert constantes.get('SORTEOS_POR_COMBO') == 1712304, constantes


def test_el_coste_se_declara_antes_de_empezar():
    """Y que el script imprima el coste ANTES de medir.

    Y el motivo: un experimento de horas que se lanza sin decir cuanto
    cuesta es un experimento que alguien descubre a la mitad, con la
    maquina ocupada y sin el numero.
    """
    fuente = io.open(_ruta('tools/auditar_equity_observable.py'),
                     encoding='utf-8').read()
    i_coste = fuente.index('COSTE')
    i_ciclo = fuente.index('for h in validacion:')
    assert i_coste < i_ciclo, (
        'el coste se imprime DESPUES del bucle, de modo que no avisa de nada')
    assert 'SORTEOS_POR_COMBO' in fuente


def test_el_experimento_no_toca_la_herramienta_del_auc_publicado():
    """Y que el estimador publicado sigue siendo el RETROSPECTIVO.

    Y el motivo de que se compruebe por el ARBOL: el comentario de esa
    herramienta SI se ha corregido —un comentario no cambia ningun numero—,
    de modo que un hash moveria por un motivo que no es el que se vigila. Lo
    que se vigila es la RAMA, que es la que decide el numero.
    """
    arbol = _arbol('tools/equity_de_mano.py')
    fn = next(n for n in ast.walk(arbol)
              if isinstance(n, ast.FunctionDef)
              and n.name == 'equity_contra')
    llamadas = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            llamadas.add(ast.unparse(n.func))
    assert any('equity_preflop' in c for c in llamadas), (
        'la rama preflop de `equity_contra` ya no usa la enumeracion '
        'retrospectiva, y eso MOVERIA el AUC publicado: %r'
        % sorted(llamadas))
    assert not any('equity_preflop_rango' in c for c in llamadas), (
        'la rama preflop de `equity_contra` esta usando el camino OBSERVABLE, '
        'y eso MOVERIA el AUC publicado: %r' % sorted(llamadas))


def test_el_experimento_usa_el_rango_y_no_las_cartas_del_rival():
    """Y que el rango se construya con las tablas y el perfil.

    Y el motivo: el sesgo que hay que evitar es el INVERSO de la fuga —que
    el estimador se haya construido con las cartas de la mano que valida—,
    y en este experimento no cabe: el rango viene de `rango_del_rival`, que
    es el mismo camino que usa la herramienta publicada.
    """
    arbol = _arbol('tools/auditar_equity_observable.py')
    llamadas = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Call):
            llamadas.add(ast.unparse(n.func))
    assert 'rango_del_rival' in llamadas, (
        'el experimento no construye el rango por el mismo camino que la '
        'herramienta publicada: %r' % sorted(llamadas))
    assert 'equity_preflop_rango' in llamadas, (
        'y la equity tiene que ser la OBSERVABLE: %r' % sorted(llamadas))


def test_el_piloto_devuelve_que_no_hay_las_dos_clases():
    """Y que con una sola mano el script diga que NO se puede calcular el AUC.

    Y el motivo: un AUC con una sola clase no es un AUC, es un numero. Y
    la herramienta tiene que decirlo en vez de devolver un 0.5 invented.
    """
    from tools import auditar_equity_observable as EXP
    import tools.auditar_auc as auc

    # Y la evaluacion por combo se intercepta: lo que se comprueba aqui es
    # la fontinteria —la particion, el rango, la etiqueta y el AUC—, y no
    # el numero, que es de horas.
    original = EXP.equity_preflop_rango

    def _falso(hero, reach, n_combos=40, seed=7):
        return 0.25

    EXP.equity_preflop_rango = _falso
    try:
        rc = EXP.main(['--manos', '1'])
    finally:
        EXP.equity_preflop_rango = original
    assert rc == 1, (
        'con una sola mano el script tiene que decir que no se puede '
        'calcular el AUC, y ha salido con %d' % rc)
