# -*- coding: utf-8 -*-
"""El test del REGISTRO: que todo lo abierto tenga dueño y condición.

Y la regla que el test comprueba:

> **Un trabajo abierto sin dueño es un trabajo que no se hace.** Y un trabajo
> abierto sin condición de activación es un trabajo que se empieza cuando
> somebody tenga ganas, que es la forma más cara de hacerlo.

Y el apartado 5 —«abierto, sin dueño asignado»— tiene que estar VACÍO, y eso
también se comprueba: un apartado de trabajos sin dueño que no está vacío es
una lista de deudas que alguien tiene que mirar.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'DOCS', 'ESTADO_DEL_TRABAJO.md')

# Los dueños que valen. Y una lista, porque un dueño es un NOMBRE, y un
# nombre se escribe. Y la lista es EXPRESA, no derivada: los dueños son
# personas, no una derivacion.
DUENOS = ('A1', 'A2', 'A2, con A1')

# Y la seccion del registro que se comprueba.
SECCION = '## 6. LAS CONDICIONES DE ACTIVACIÓN, en una tabla'


def _registro():
    with io.open(DOC, encoding='utf-8') as f:
        return f.read()


def _tabla_de_condiciones():
    """Las filas de la tabla de condiciones, como (trabajo, dueño, condición).

    Y se PARSEA, y no se busca con un `in`: un `in` encuentra el texto en
    cualquier parte del documento, y no dice si la fila esta completa.
    """
    reg = _registro()
    assert SECCION in reg, (
        'el registro no tiene la seccion de condiciones de activacion, que es '
        'la que se comprueba')
    cuerpo = reg.split(SECCION, 1)[1]
    filas = []
    dentro = False
    for l in cuerpo.split('\n'):
        if l.startswith('| trabajo |'):
            dentro = True
            continue
        if dentro:
            if not l.startswith('|'):
                break
            celdas = [c.strip() for c in l.strip('|').split('|')]
            if len(celdas) != 3:
                continue
            if set(''.join(celdas)) <= set('-: '):
                continue
            filas.append(tuple(celdas))
    return filas


def test_todo_trabajo_abierto_tiene_dueno_y_condicion():
    """La regla, comprobada fila por fila.

    Y el mensaje nombra la fila, porque un fallo que no dice cual no se
    puede arreglar.
    """
    filas = _tabla_de_condiciones()
    assert filas, 'la tabla de condiciones esta vacia, y el registro no dice que'
    for trabajo, dueno, condicion in filas:
        assert dueno, (
            'el trabajo %r no tiene dueño. Y un trabajo sin dueño es un '
            'trabajo que no se hace.' % trabajo)
        assert dueno in DUENOS, (
            'el trabajo %r tiene un dueño que no es ninguno de los conocidos: '
            '%r' % (trabajo, dueno))
        assert condicion, (
            'el trabajo %r no dice QUE lo desbloquea. Y sin condicion, un '
            'trabajo se empieza cuando a alguien le apetece.' % trabajo)
        assert condicion.lower() not in ('cuando se pueda', 'pendiente'), (
            'la condicion del trabajo %r no es una condicion: %r'
            % (trabajo, condicion))


def test_los_cuatro_bloqueos_de_a1_estan_en_la_tabla():
    """Y que los cuatro esten, porque son los que hay que retomar.

    Y el motivo de nombrarlos: una lista de bloqueos sin sus anclas es una
    lista de temas, no una lista de bloqueos.
    """
    filas = _tabla_de_condiciones()
    trabajos = ' '.join(f[0].lower() for f in filas)
    for ancla in ('matrix', 'divergentes', 'preflop', 'rival'):
        assert ancla in trabajos, (
            'el registro no nombra el bloqueo de %r en la tabla de '
            'condiciones' % ancla)


def test_no_hay_trabajo_abierto_sin_dueno():
    """Y que el apartado de los que no tienen dueño este VACIO.

    Y no es un requisito de forma: es una DECLARACION. Un apartado con
    trabajos sin dueño que no esta vacio es una lista de deudas, y las deudas
    que no tienen dueño no se pagan.
    """
    reg = _registro()
    assert '## 5. ABIERTO, sin dueño asignado' in reg, (
        'el registro no tiene el apartado de los trabajos sin dueño, y ese '
        'apartado es una DECLARACION: si esta vacio, no hay deudas sin '
        'dueño')
    cuerpo = reg.split('## 5. ABIERTO, sin dueño asignado', 1)[1]
    cuerpo = cuerpo.split('## ', 1)[0]
    filas = [l for l in cuerpo.split('\n')
             if l.startswith('|') and l.count('|') >= 3]
    con_trabajo = []
    for l in filas:
        celdas = [c.strip() for c in l.strip('|').split('|')]
        if len(celdas) >= 3 and celdas[0] and celdas[0] not in ('trabajo',):
            if set(''.join(celdas)) <= set('-: '):
                continue
            con_trabajo.append(celdas[0])
    assert con_trabajo == ['ninguno'], (
        'hay %d trabajo(s) abierto(s) SIN dueño: %r. Y un trabajo sin dueño '
        'es un trabajo que no se hace.' % (len(con_trabajo) - 1, con_trabajo))
