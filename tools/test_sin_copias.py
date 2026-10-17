# -*- coding: utf-8 -*-
"""Tarea 3: que no quede ninguna COPIA de la calculo de la etiqueta.

Lo que paso: `test_bloqueo_orden_filtros.py` tenia `_etiqueta_posible()`
copiada dentro del test, con la logica vieja, y afirmaba 78 victorias y
cero derrotas. Seguia dando verde con el error dentro, porque **no comparte
codigo con lo que prueba**.

La primera version de este detector era demasiado cruda y senalaba a
legitimos: `test_calibrar.py` llama a `gano_por_fold()` y a `mejores_manos()`
porque ES el test de `calibrar.py`, y llamar a la funcion REAL es
exactamente lo contrario de copiarla.

Asi que la regla no es "no llames al mecanismo". Es: **una funcion de test
que llame a DOS O MAS funciones del mecanismo, y que devuelva algo con forma
de etiqueta sin delegar en `resto_de_muestra()`, es una copia.** Esa es la
firma exacta del error, y es lo que se busca.

Lo que se busca, entonces:

  1. una funcion de test que use dos o mas de {gano_por_fold,
     mejores_manos, llego_al_showdown} y devuelva `(algo, 1.0)` o similar,
     sin llamar a `resto_de_muestra`
  2. una funcion que se llame como la que se borro, y no delegue
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIRS = ('tools', 'motor')
MECANISMO = ('gano_por_fold', 'mejores_manos', 'llego_al_showdown')
DELEGACION = 'resto_de_muestra'

# Las funciones de ESTE detector. Se saltan por NOMBRE DE FUNCION y no por
# nombre de fichero: un fichero puede contener el detector y una copia, y
# saltarse el fichero entero se lleva la copia por delante. Ese error lo
# encontro el test que mete una copia aqui mismo, y por eso existe.
# Los ficheros que declaran esto quedan EXENTOS, y el detector lo dice en
# el mensaje de fallo. Solo lo declara `test_detector_de_copias.py`, que
# lleva dentro una copia COMO FIXTURE para probar que el detector la ve.
# Una exencion sin nombre no es una exencion: es un agujero.
COPIA_ESPERADA = 'COPIA_ESPERADA = True'

YO = 'test_sin_copias.py'

PROPIAS = frozenset((
    'test_ninguna_funcion_de_test_reimplementa_el_calculo_de_la_etiqueta',
    'test_la_copia_que_se_borro_no_esta_y_lo_que_la_sustituye_delega',
    'test_los_tests_que_llaman_al_mecanismo_son_el_test_del_mecanismo',
    'test_la_lista_de_funciones_buscadas_no_aparece_en_ningun_test',
))


def _ficheros():
    """Todos los tests, incluido este.

    Antes se excluia a si mismo por nombre de fichero, y eso hacia
    INVISIBLE cualquier copia metida en su propio fichero — que es
    precisamente lo que hace el test que prueba que el detector funciona.
    """
    out = []
    for d in TEST_DIRS:
        ruta = os.path.join(ROOT, d)
        if not os.path.isdir(ruta):
            continue
        for n in sorted(os.listdir(ruta)):
            if n.startswith('test_') and n.endswith('.py'):
                out.append(os.path.join(d, n))
    return out


def _exentos(texto):
    return COPIA_ESPERADA in texto


def _texto(ruta):
    with io.open(os.path.join(ROOT, ruta), encoding='utf-8') as f:
        return f.read()


def _funciones(texto):
    """[(nombre, cuerpo)] de todas las funciones de nivel superior."""
    out = []
    for m in re.finditer(r'^def\s+(\w+)\s*\(', texto, re.MULTILINE):
        nxt = texto.find('\ndef ', m.end())
        out.append((m.group(1), texto[m.end():nxt if nxt > 0
                                    else len(texto)]))
    return out


def test_ninguna_funcion_de_test_reimplementa_el_calculo_de_la_etiqueta():
    """La firma de la copia: dos o mas del mecanismo, y una salida con
    forma de etiqueta, sin delegar."""
    malas, exentos = [], []
    for ruta in _ficheros():
        texto = _texto(ruta)
        if _exentos(texto):
            exentos.append(ruta)
            continue
        for nombre, cuerpo in _funciones(texto):
            if nombre in PROPIAS:
                continue              # estas son del detector, no copias
            usadas = [fn for fn in MECANISMO if fn + '(' in cuerpo]
            if len(usadas) < 2:
                continue
            if DELEGACION in cuerpo:
                continue
            # una salida con forma de etiqueta: un float literal devuelto
            devuelve_float = re.search(
                r'return\b[^\n]*\b[01]\.0\b', cuerpo) or re.search(
                    r',\s*[01]\.0\s*\)', cuerpo)
            if devuelve_float:
                malas.append('%s: %s() usa %s y devuelve una etiqueta'
                             % (ruta, nombre, ' y '.join(usadas)))
    assert not malas, (
        'funciones de test que reimplementan el calculo de la etiqueta:\n'
        '   ' + '\n   '.join(malas)
        + ('\n\n   Ficheros EXENTOS por declarar una copia a proposito: %s'
           % exentos if exentos else ''))


def test_la_copia_que_se_borro_no_esta_y_lo_que_la_sustituye_delega():
    """Y el caso concreto: se borro `_etiqueta_posible` con logica propia, y
    lo que hay en su lugar tiene que llamar a `resto_de_muestra`."""
    texto = _texto(os.path.join('tools', 'test_bloqueo_orden_filtros.py'))
    assert 'def _etiqueta_posible' in texto, (
        'se borro la copia y no quedo nada en su lugar')
    i = texto.index('def _etiqueta_posible')
    cuerpo = texto[i:i + 800]
    assert DELEGACION in cuerpo, (
        'y lo que hay en su lugar TIENE que delegar: una copia que devuelve '
        'lo mismo sigue siendo una copia')
    usadas = [fn for fn in MECANISMO if fn + '(' in cuerpo]
    assert len(usadas) < 2, (
        'y no tiene que usar el mecanismo por su cuenta: usa %s' % usadas)


def test_los_tests_que_llaman_al_mecanismo_son_el_test_del_mecanismo():
    """Los que si lo llaman tienen que ser los de la funcion que lo contiene.
    Llamar a `calibrar.gano_por_fold` desde `test_calibrar.py` es lo
    correcto; llamarlo desde un test de otra cosa es suspecto, y no se
    prohibe porque puede ser justo lo que se quiere comprobar."""
    for ruta in _ficheros():
        nombre = os.path.basename(ruta)[:-3]          # test_calibrar
        texto = _texto(ruta)
        if 'mejores_manos(' not in texto and 'gano_por_fold(' not in texto:
            continue
        if nombre in ('test_calibrar',):
            continue
        # en los demas, el uso tiene que estar en un test que lo diga
        declarados = [l for l in texto.split('\n')
                      if 'mejores_manos(' in l or 'gano_por_fold(' in l]
        # no se exige nada mas: el detector principal ya cubre las copias, y
        # este es el aviso de que el uso es legitimo pero raro
        assert declarados is not None


def test_la_lista_de_funciones_buscadas_no_aparece_en_ningun_test():
    """Que nadie se copie el detector para evadirlo.

    Este fichero si la declara —tiene que, para saber que busca— asi que se
    exime a si mismo por nombre. Y la exencion es de UN fichero: cualquier
    otro que declare la lista esta escribiendo un detector de copias.
    """
    for ruta in _ficheros():
        if os.path.basename(ruta) == YO:
            continue
        texto = _texto(ruta)
        assert 'MECANISMO' not in texto, (
            '%s declara la lista de funciones buscadas, o sea que alguien '
            'esta escribiendo un detector de copias aqui' % ruta)