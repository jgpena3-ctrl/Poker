# -*- coding: utf-8 -*-
"""R2 parrafo 5: staged sin commitear MAS unstaged, y los numeros de linea.

MEDIDO antes de arreglar nada, con un repositorio de verdad:

  antes, con `git diff` + `git diff --cached`:  2 de 3 lineas con el numero
  equivocado. Los dos diffs van en coordenadas de SU version —el indice y
  el arbol—, y cuando hay cambios en las dos zonas unirlos no da el numero
  de ninguna.

  ahora, con `git diff HEAD`: 0 de 3. Un solo diff, una sola base, y su
  lado `+` es el fichero que se esta leyendo.

Lo que NO cambia es la CLASIFICACION: "este hallazgo es del cambio" ya era
cierta y lo sigue siendo. Por eso hay dos tests y no uno: un arreglo de
numeros no puede romper la clasificacion sin que se note, y al reves.

El repositorio es temporal y se borra. Y hay un test de mas: el caso en el
que las inserciones NO se solapan, que es donde los numeros coincidian por
casualidad y por eso el fallo no se veia antes.
"""
import importlib.util
import io
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIRILICO = chr(0x435)


def _vc():
    ruta = os.path.join(ROOT, 'tools', 'verificar_caracteres.py')
    spec = importlib.util.spec_from_file_location('vc_staged', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _git(repo, *args):
    return subprocess.run(['git'] + list(args), cwd=repo,
                          capture_output=True).stdout.decode('utf-8')


def _leer(repo):
    with io.open(os.path.join(repo, 'x.txt'), encoding='utf-8') as f:
        return f.read().split('\n')


def _escribir(repo, lineas):
    with io.open(os.path.join(repo, 'x.txt'), 'w', encoding='utf-8',
                 newline='') as f:
        f.write('\n'.join(lineas))


def _repo_base():
    d = tempfile.mkdtemp(prefix='opencode_staged_')
    _git(d, 'init', '-q')
    _git(d, 'config', 'user.email', 't@t')
    _git(d, 'config', 'user.name', 't')
    base = ['linea %d' % i for i in range(1, 21)] + ['']
    _escribir(d, base)
    _git(d, 'add', '-A')
    _git(d, 'commit', '-qm', 'base')
    return d


def _montar_diverge():
    """STAGE abajo y UNSTAGED arriba: las dos vistas se separan."""
    d = _repo_base()
    _escribir(d, _leer(d)[:-1] + ['STAGE 1', 'STAGE 2', ''])
    _git(d, 'add', 'x.txt')
    lineas = _leer(d)
    lineas.insert(0, 'UNSTAGED arriba')
    _escribir(d, lineas)
    return d


def _montar_no_divergen():
    """STAGE arriba y UNSTAGED abajo: los numeros coinciden por casualidad.

    Es el caso en el que el fallo NO se ve, y por eso hace falta tambien:
    un test que solo prueba el caso dificil no dice si el facil esta bien.
    """
    d = _repo_base()
    _escribir(d, ['STAGE 1', 'STAGE 2'] + _leer(d))
    _git(d, 'add', 'x.txt')
    lineas = _leer(d)
    lineas.insert(7, 'UNSTAGED en medio')
    _escribir(d, lineas)
    return d


# =========================================================== los numeros
def test_los_numeros_son_del_fichero_actual_aunque_haya_dos_zonas():
    vc = _vc()
    d = _montar_diverge()
    try:
        vc.ROOT = d
        nuevas = vc.lineas_nuevas(os.path.join(d, 'x.txt'))
        real = _leer(d)
        assert nuevas, 'tiene que ver las dos zonas'
        for n, t in nuevas:
            assert 1 <= n <= len(real), (
                'la linea %d no existe en un fichero de %d: el numero viene '
                'de una version que no es esta' % (n, len(real)))
            assert real[n - 1] == t, (
                'en la linea %d hay %r, no %r' % (n, real[n - 1], t))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_y_tambien_cuando_las_zonas_no_se_solapan():
    vc = _vc()
    d = _montar_no_divergen()
    try:
        vc.ROOT = d
        nuevas = vc.lineas_nuevas(os.path.join(d, 'x.txt'))
        real = _leer(d)
        for n, t in nuevas:
            assert real[n - 1] == t, (
                'linea %d: %r en vez de %r' % (n, real[n - 1], t))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_solo_usa_un_diff():
    """Contra una sola base. Si alguien vuelve a sumar `git diff` y
    `git diff --cached`, el numero equivocado vuelve y este test no lo
    detecta; por eso ademas esta el de arriba, que si lo detecta."""
    texto = open(os.path.join(ROOT, 'tools', 'verificar_caracteres.py'),
                 encoding='utf-8').read()
    i = texto.index('def lineas_nuevas(path):')
    cuerpo = texto[i:i + 2000]
    assert "'git', 'diff', 'HEAD', '-U0'" in cuerpo, (
        'tiene que ser un diff contra HEAD')
    assert "'--cached'" not in cuerpo, (
        'y NO el del indice: sus numeros van en coordenadas del indice, que '
        'con cambios en las dos zonas no son los del fichero actual')
    assert 'staged sale como sin cambios' not in cuerpo


# ======================================================= la clasificacion
def test_la_clasificacion_sigue_cierta_aunque_los_numeros_cambien():
    """R2 lo dice: la clasificacion no depende de los numeros. Se fija
    aparte para que arreglar los numeros no pueda romperla."""
    vc = _vc()
    d = _montar_diverge()
    try:
        vc.ROOT = d
        with io.open(os.path.join(d, 'x.txt'), 'a', encoding='utf-8',
                     newline='') as f:
            f.write('%s\n' % CIRILICO)
        estado, lineas = vc.en_cambio(os.path.join(d, 'x.txt'), CIRILICO)
        assert estado is True
        assert lineas
        real = _leer(d)
        for n in lineas:
            assert real[n - 1].endswith(CIRILICO)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_un_fichero_sin_cambios_no_tiene_lineas_nuevas():
    vc = _vc()
    d = _repo_base()
    try:
        vc.ROOT = d
        assert vc.lineas_nuevas(os.path.join(d, 'x.txt')) == []
        assert vc.en_cambio(os.path.join(d, 'x.txt'), CIRILICO) == (False, [])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_lo_ya_commiteado_es_preexistente():
    """El otro extremo: si el caracter se commiteo, ya no es del cambio.
    Con `git diff HEAD` sale de la comparacion por definicion; con
    `--cached` tambien. Se prueba para que no se rompa al cambiar de
    comando."""
    vc = _vc()
    d = _repo_base()
    try:
        _escribir(d, ['%s committed' % CIRILICO] + _leer(d))
        _git(d, 'add', '-A')
        _git(d, 'commit', '-qm', 'con el caracter')
        vc.ROOT = d
        estado, _l = vc.en_cambio(os.path.join(d, 'x.txt'), CIRILICO)
        assert estado is False, (
            'lo que esta commiteado y sin tocar es preexistente, que es lo '
            'unico que protege de retocar cosas de antes')
    finally:
        shutil.rmtree(d, ignore_errors=True)