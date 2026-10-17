# -*- coding: utf-8 -*-
"""El barrido de los 57 `.md` tiene que ver una violaciones cuando hay una.

Un barrido que sale limpio no dice que este bien: dice que no ha visto nada,
que es lo mismo que no mirar. Y un detector que nunca falla no se sabe si
vigila o si esta roto.

Por eso el primer test mete un documento con una violacion en un arbol
temporal y comprueba que la ve. Si el barrido no la ve, EL TEST falla —que
es lo que tiene que hacer para servir de algo.

Y los dos falsos positivos que EL BARRIDO DIO, quedan como tests de que no
vuelven. Los dos eran numeros que coinciden y no son el mismo numero:

    FASE_D_PLAN.md   | **TOTAL** | **78** |   -> total de DEFECTOS
    TECNICO.md       perfil con mas muestra, 236 manos  -> tamaño de un
                                                        PERFIL

Y los dos seromataron mirando donde esta el sujeto: el encabezado de la
tabla, y el sujeto de la frase. Un numero dentro de una fila no dice de que
es, y una palabra suelta como "muestra" aparece en prosa corriente.
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


# ============================== los dos falsos positivos, que no vuelven
def test_un_total_de_defectos_no_es_el_total_de_observaciones():
    """`FASE_D_PLAN.md` tiene `| TOTAL | 78 |`, y ese 78 es la suma de cuatro
    DEFECTOS de datos. La fila no lo dice; lo dice el encabezado."""
    texto = ('| defecto | publicado | ahora |\n'
             '|---|---:|---:|\n'
             '| `IMPORTE_SUBIDA` | 36 | 31 |\n'
             '| **TOTAL** | **78** | **51** |\n')
    assert barrido.frases_retiradas_en(texto)[0] == [], (
        'un total de defectos no es un total de observaciones. El sujeto esta '
        'en el ENCABEZADO, y por eso hay que mirar ahi y no en la fila')


def test_el_tamanio_de_un_perfil_no_es_un_corte_postflop():
    """`TECNICO.md` dice "perfil con mas muestra: ... 236 manos", y ese 236
    es el numero de manos de un perfil del grid.

    Y el motivo de que saliera: "muestra" estaba en la lista de palabras de
    poblacion, y "perfil con mas muestra" no es la muestra etiquetada. Una
    palabra que aparece en prosa corriente no puede decidir si un numero es el
    retirado."""
    texto = ('- Resultados reales (perfil con mas muestra): '
             'Regular/no_raise 236 manos (open 51, fold 123).\n')
    assert barrido.frases_retiradas_en(texto)[0] == [], (
        'el tamano de un perfil no es un numero de cortes postflop')


def test_una_mano_con_etiqueta_sigue_siendo_una_observacion():
    """Y el caso contrario: que la regla NO se haya quedado tan estrecha que
    deje pasar lo que tiene que senalar. Este es el que la regla existe para
    cazar."""
    texto = ('| | |\n'
             '|---|---:|\n'
             '| cortes preflop de poblacion B | 83 |\n'
             '| con etiqueta | **78** |\n')
    malas, _cit = barrido.frases_retiradas_en(texto)
    assert malas, (
        'la regla ya no ve un 78 afirmado sobre la poblacion. Se ha '
        'estrechado de mas: cabe mas un numero retirado sin que lo vea nadie')
    assert malas[0][1] == '78'