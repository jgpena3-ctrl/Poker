# -*- coding: utf-8 -*-
"""Que el detector de copias NO sea un adorno: tiene que FALLAR cuando hay
una copia.

Un test que pasa siempre no vigila nada. Este mete una copia de verdad en
un fichero temporal de test, ejecuta el detector sobre el, y comprueba que
la senala. Si el detector no la ve, el test falla —que es lo que tiene que
hacer para servir de algo.
"""
import io
import os
import shutil
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTE = os.path.join(ROOT, 'tools', 'test_sin_copias.py')

# Este fichero contiene una COPIA a proposito: es lo que demuestra que el
# detector funciona. Por eso declara la exencion, y el detector la nombra
# en el mensaje de fallo si alguna vez se salta de mas.
COPIA_ESPERADA = True

# Una copia exacta de la que se borro, con la logica vieja.
COPIA = '''
def _etiqueta_posible(cal, h, hero_pos):
    """COPIA. No delega: vuelve a hacer el calculo."""
    declarados = {cal.id_a_pos(h, i) for i in (h.get('winner') or [])}
    declarados.discard(None)
    if not declarados:
        return 'sin ganador declarado', None
    scores, mejor = cal.mejores_manos(h)
    llegan = {p for p in declarados
              if cal.llego_al_showdown(h, p) and scores and p in scores}
    if not llegan:
        ok, _mot = cal.gano_por_fold(h, declarados)
        return ('ok', 1.0) if ok else ('fold no verificable', None)
    return 'ok', (1.0 if hero_pos in llega else 0.0)


def test_que_no_hace_nada():
    pass
'''

# Una copia "delegada": misma firma, pero delega. NO se debe senalar.
DELEGADA = '''
def _etiqueta_possible(cal, h, hero_pos):
    """NO es copia: delega en la funcion de la herramienta."""
    import importlib.util
    ruta = os.path.join(os.path.dirname(__file__),
                        'auditar_representatividad.py')
    spec = importlib.util.spec_from_file_location('ar', ruta)
    ar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ar)
    r = ar.resto_de_muestra(cal, h, hero_pos)
    return r.motivo, r.y
'''


def _ejecutar_en(raiz, extra):
    """Copia el detector a un arbol que imita el repo, con la pieza anadida.

    El detector resuelve ROOT con dos niveles ARRIBA del fichero, asi que el
    temporal tiene que tener `tools/` y `motor/` debajo de una raiz, y el
    detector dentro de `tools/`.

    El orden importa: primero los directorios, luego el fichero. Copiar a
    una ruta cuyo directorio no existe es FileNotFoundError, y ese error lo
    daba el esqueleto anterior.
    """
    os.makedirs(os.path.join(raiz, 'tools'), exist_ok=True)
    os.makedirs(os.path.join(raiz, 'motor'), exist_ok=True)
    destino = os.path.join(raiz, 'tools', 'test_sin_copias.py')
    with io.open(FUENTE, encoding='utf-8') as f:
        base = f.read()
    with io.open(destino, 'w', encoding='utf-8', newline='') as f:
        f.write(base)
    # La pieza va a SU PROPIO fichero, no pegada al detector. Pegada, el
    # detector se eximia a si mismo —el token de exencion esta en su
    # fuente— y no miraba nada. Y una copia de test, en la vida real, esta
    # en otro fichero de test.
    if extra:
        iny = os.path.join(raiz, 'tools', 'test_zz_inyectado.py')
        with io.open(iny, 'w', encoding='utf-8', newline='') as f:
            f.write(extra)
    import importlib.util
    spec = importlib.util.spec_from_file_location('detector', destino)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_el_detector_senala_una_copia_de_verdad():
    tmp = tempfile.mkdtemp(prefix='opencode_copia_')
    try:
        m = _ejecutar_en(tmp, COPIA)
        try:
            m.test_ninguna_funcion_de_test_reimplementa_el_calculo_de_la_etiqueta()
        except AssertionError as exc:
            assert '_etiqueta_posible' in str(exc), (
                'senala la copia equivocada: %s' % exc)
        else:
            raise AssertionError(
                'el detector NO ha visto una copia que usa las tres '
                'funciones del mecanismo y devuelve 1.0. Un detector que no '
                've una copia de verdad no vigila')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_detector_no_senala_una_funcion_que_delega():
    """Y que no senale lo legitimo. Un detector que senala todo no sirve:
    en dos dias nadie lo mira."""
    tmp = tempfile.mkdtemp(prefix='opencode_copia_ok_')
    try:
        m = _ejecutar_en(tmp, DELEGADA)
        m.test_ninguna_funcion_de_test_reimplementa_el_calculo_de_la_etiqueta()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_detector_no_senala_una_llamada_simple_al_mecanismo():
    """`test_calibrar.py` llama a `gano_por_fold()` y a `mejores_manos()`
    porque ES el test de `calibrar.py`. Con una sola llamada no hay copia,
    porque una copia necesita el mecanismo COMPLETO."""
    tmp = tempfile.mkdtemp(prefix='opencode_copia_una_')
    try:
        pieza = ('\n\ndef test_algo():\n'
                 '    ok, _m = cal.gano_por_fold(h, declarados)\n'
                 '    return ok\n')
        m = _ejecutar_en(tmp, pieza)
        m.test_ninguna_funcion_de_test_reimplementa_el_calculo_de_la_etiqueta()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)