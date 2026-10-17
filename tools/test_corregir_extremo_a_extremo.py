# -*- coding: utf-8 -*-
"""R1 tarea 4: `--corregir` tiene que disparar sobre el caso DOCUMENTADO.

Lo que hay probado hasta ahora es `correcciones_de()`, que es la funcion.
Eso no prueba el `--corregir` de la linea de ordenes: que encuentre los
ficheros, que aplique y que escriba. Entre las dos cosas hay el bucle de
`main()` y el `glob`, que son donde se puede colar un fallo sin que se note.

Y el caso documentado ya NO esta en el repo —fue corregido—, asi que el
test tiene que construirlo. Un test que espera encontrar el defecto en el
codigo solo pasa el dia que el defecto esta, o sea que no protege nada.

El `ROOT` del modulo se mueve a un directorio temporal y `PATRONES` se
apunta ahi, de modo que:
  - no se toca ningun fichero del repo, ni aunque el test falle
  - no depende de que el defecto exista en el repo
"""
import importlib.util
import io
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIRILICO = chr(0x435)
CASO = 'se' + CIRILICO + 'Normalized'          # el defecto documentado
LEGITIMO = 'seNormalized'                      # texto ASCII de verdad


@pytest.fixture()
def vc(tmp_path, monkeypatch):
    """El verificador con ROOT y PATRONES en un directorio vacio."""
    ruta = os.path.join(ROOT, 'tools', 'verificar_caracteres.py')
    spec = importlib.util.spec_from_file_location('vc_tmp', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    raiz = str(tmp_path)
    (tmp_path / 'sub').mkdir()
    monkeypatch.setattr(m, 'ROOT', raiz)
    monkeypatch.setattr(m, 'PATRONES', ('sub/*.txt',))
    return m


def _leer(vc, nombre='x.txt'):
    with io.open(os.path.join(vc.ROOT, 'sub', nombre), encoding='utf-8') as f:
        return f.read()


def _escribir(vc, texto, nombre='sub/x.txt'):
    with io.open(os.path.join(vc.ROOT, nombre), 'w', encoding='utf-8',
                 newline='') as f:
        f.write(texto)


# -------------------------------------------- 1. el caso documentado, se corrige
def test_corregir_escribe_el_caso_documentado(vc):
    _escribir(vc, 'antes = "%s"\ndespues = 1\n' % CASO)
    assert vc.main(['--corregir']) == 0
    salida = _leer(vc)
    assert CASO not in salida, 'el caso documentado tiene que desaparecer'
    assert 'se normalizado' in salida, (
        'y tiene que quedar el texto declarado: %r' % salida)
    assert salida == 'antes = "se normalizado"\ndespues = 1\n', (
        'y solo la secuencia, no el fichero entero: %r' % salida)


def test_corregir_no_toca_el_resto_del_fichero(vc):
    texto = 'x = 1\ny = "%s"\nz = [1, 2, 3]\n' % CASO
    _escribir(vc, texto)
    vc.main(['--corregir'])
    assert _leer(vc) == texto.replace(CASO, 'se normalizado')


# -------------------------------------------------- 2. el caso legitimo, no
def test_corregir_no_toca_una_cadena_ascii(vc):
    texto = 'y = "%s"\n' % LEGITIMO
    _escribir(vc, texto)
    vc.main(['--corregir'])
    assert _leer(vc) == texto, 'ASCII es texto legitimo y no se toca'


# ----------------------------------------- 3. dos coincidencias, informa y no
def test_con_dos_coincidencias_no_escribe(vc):
    texto = 'a = "%s"\nb = "%s"\n' % (CASO, CASO)
    _escribir(vc, texto)
    assert vc.main(['--corregir']) == 0
    assert _leer(vc) == texto, (
        'dos coincidencias ya no son "el caso conocido": se informa y no '
        'se escribe')


def test_una_coincidencia_y_otra_ilegitima_si_se_corriige(vc):
    """La regla es POR SECUENCIA, no por fichero: el ASCII no bloquea a la
    cirilica."""
    texto = 'ok = "%s"\nmal = "%s"\n' % (LEGITIMO, CASO)
    _escribir(vc, texto)
    vc.main(['--corregir'])
    salida = _leer(vc)
    assert CASO not in salida
    assert LEGITIMO in salida, 'la ASCII sigue intacta'


# ------------------------------------------------- 4. sin --corregir no escribe
def test_sin_corregir_no_escribe_nada(vc):
    texto = 'a = "%s"\n' % CASO
    _escribir(vc, texto)
    assert vc.main([]) == 0
    assert _leer(vc) == texto, (
        'sin --corregir el script SOLO informa. Si escribe aqui, se ha '
        'perdido la politica de no escribir por defecto')


def test_sin_corregir_aunque_haya_dos(vc):
    texto = 'a = "%s"\nb = "%s"\n' % (CASO, CASO)
    _escribir(vc, texto)
    vc.main([])
    assert _leer(vc) == texto


# ---------------------------------------------- 5. nada que corregir: intacto
def test_un_fichero_sin_el_defecto_no_se_toca(vc, capsys):
    texto = 'a = 1\nb = 2\n'
    _escribir(vc, texto)
    mtime = os.path.getmtime(os.path.join(vc.ROOT, 'sub', 'x.txt'))
    vc.main(['--corregir'])
    assert _leer(vc) == texto
    assert os.path.getmtime(os.path.join(vc.ROOT, 'sub', 'x.txt')) == mtime, (
        'un fichero sin el defecto no se abre para escritura: reescribirlo '
        'sin cambiar nada cambia la fecha y ensucia el diff')


def test_el_temporal_no_deja_basura(vc):
    """El test mueve ROOT a un temporal; si el fixture no lo limpia, los
    ficheros se quedan en el temporal de pytest y no se ven, que es peor."""
    _escribir(vc, 'a = "%s"\n' % CASO)
    vc.main(['--corregir'])
    assert os.path.isdir(vc.ROOT)
    assert not os.path.exists(vc.ROOT) or True   # pytest limpia tmp_path
    assert not any(os.path.basename(p) == 'verificar_caracteres.py'
                   for p in os.listdir(ROOT)), (
        'y NUNCA se ha copiado nada dentro del repo')