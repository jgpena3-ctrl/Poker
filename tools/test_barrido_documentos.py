# -*- coding: utf-8 -*-
"""El barrido de los 57 `.md` tiene que ver una violaciones cuando hay una.

Un barrido que sale limpio no dice que este bien: dice que no ha visto nada,
que es lo mismo que no mirar. Y un detector que nunca falla no se sabe si
vigila o si esta roto.

Por eso el primer test mete un documento con una violacion en un arbol
temporal y comprueba que la ve. Si el barrido no la ve, EL TEST falla —que
es lo que tiene que hacer para servir de algo.

Y los tres falsos positivos que EL BARRIDO DIO quedan como tests de que no
vuelven, en `test_falsos_positivos.py`. Los tres son numeros que coinciden y
no son el mismo numero:

    FASE_D_PLAN.md     | **TOTAL** | **78** |  -> total de DEFECTOS
    TECNICO.md         perfil con mas muestra, 236 manos  -> tamaño de un
                                                             PERFIL
    CONTRATO_PREFLOP   son 2 270 millones  -> el 270 es la cola de un numero

Los tres se resolvieron mirando DONDE ESTA EL SUJETO: el encabezado de la
tabla, la palabra que lo dice, y el numero entero que es. Un numero dentro
de una fila no dice de que es, y una palabra suelta como "muestra" aparece
en prosa corriente.

Y pytest NO avisa de nada de esto: dos tests con el mismo nombre en
ficheros distintos se ejecutan los dos, los dos pasan, y el color es
verde. Por eso hace falta `test_sin_duplicados.py`.
"""
import io
import os
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import auditar_todos_los_md as barrido                # noqa: E402


# ============================================== hoy: limpio
def test_ningun_documento_afirma_una_frase_retirada():
    """Los 57. Y el numero sale del propio barrido, para que no se pueda
    anadir un documento y que el test no lo mire."""
    salida = barrido.auditar_todos()
    detalle = '\n'.join(
        '   %s:%d [%s] %s' % (f, i, fr, l)
        for f, malas in salida for i, fr, l in malas)
    assert not salida, (
        'documentos que afirman una frase retirada:\n%s' % detalle)
    assert len(barrido._md_del_repo()) >= 50, (
        'el barrido solo ve %d documentos. Si el numero baja, el recorrido no '
        'esta leyendo el repositorio entero'
        % len(barrido._md_del_repo()))


# ============================================== y que vea una
def test_el_barrido_ve_una_violacion_si_la_hay():
    """La comprobacion de que el barrido sirve."""
    tmp = tempfile.mkdtemp(prefix='opencode_barrido_')
    try:
        ruta = os.path.join(tmp, 'UN_DOCUMENTO.md')
        with io.open(ruta, 'w', encoding='utf-8', newline='') as f:
            f.write('# Un documento cualquiera\n'
                    '\n'
                    'La poblacion B con etiqueta son 131 observaciones.\n')
        salida = barrido.auditar_todos(raiz=tmp)
        assert salida, 'el barrido NO ha visto un 131 afirmado'
        malas = salida[0][1]
        assert any(fr == '131' for _i, fr, _l in malas), (
            'pero no senala el 131: %r' % malas)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_barrido_no_se_equivoca_con_una_cita():
    """Y que no senale lo citado. Si senalara las citas, el barrido no lo
    usaria nadie, y las citas son obligatorias."""
    tmp = tempfile.mkdtemp(prefix='opencode_barrido_cita_')
    try:
        with io.open(os.path.join(tmp, 'CITA.md'), 'w', encoding='utf-8',
                     newline='') as f:
            f.write('# Documento\n'
                    '\n'
                    '> antes decia 131 observaciones; ahora son 48\n'
                    '\n'
                    'Hoy son 48 con etiqueta.\n')
        salida = barrido.auditar_todos(raiz=tmp)
        assert not salida, (
            'senala una cita: %r' % salida)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
