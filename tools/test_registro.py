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

def test_los_cinco_campos_de_cada_frente_estan():
    """Y que la tabla de los frentes tenga los CINCO campos.

    Y los cinco, y por que cinco: responsable, resultado medido, decision
    pendiente, condicion de activacion, y la prueba que demuestra el
    cierre. Y el quinto es el que hace que los otros cuatro no se
    desvanezcan: un frente sin prueba que lo fije, es un frente que se
    cierra cuando alguien se acuerda.
    """
    reg = _registro()
    cuerpo = reg.split('## 4. ABIERTO, de A2, INDEPENDIENTE', 1)[1]
    cuerpo = cuerpo.split('## ', 1)[0]
    filas = []
    for l in cuerpo.split('\n'):
        if not l.startswith('|') or l.count('|') < 7:
            continue
        celdas = [c.strip() for c in l.strip('|').split('|')]
        if len(celdas) != 6:
            continue
        if set(''.join(celdas)) <= set('-: '):
            continue
        if celdas[0] == 'frente':
            continue          # la cabecera de la tabla, no una fila
        filas.append(celdas)
    assert len(filas) == 4, (
        'se esperaban los cuatro frentes en la tabla, y hay %d: %r'
        % (len(filas), filas))
    for frente, resp, medido, decision, condicion, prueba in filas:
        for nombre, valor in (('responsable', resp),
                              ('resultado medido', medido),
                              ('decision pendiente', decision),
                              ('condicion de activacion', condicion),
                              ('prueba que demuestra el cierre', prueba)):
            assert valor, (
                'el frente %r no tiene %s' % (frente, nombre))


def test_los_cuatro_pasos_de_a1_estan_con_su_criterio_de_hecho():
    """Y que la seccion de los pasos exista, y que cada paso diga cuando
    esta HECHO.

    Y el motivo del «criterio de hecho»: una lista de pasos sin criterio de
    hecho es una lista de intenciones, y las intenciones no se comprueban.
    """
    reg = _registro()
    assert 'QUÉ DEBE HACER A1 ANTES DE DISPARAR' in reg, (
        'el registro no tiene la seccion de los pasos de A1')
    cuerpo = reg.split('QUÉ DEBE HACER A1 ANTES DE DISPARAR', 1)[1]
    cuerpo = cuerpo.split('\n## ', 1)[0]
    filas = []
    for l in cuerpo.split('\n'):
        if not l.startswith('|') or l.count('|') < 4:
            continue
        celdas = [c.strip() for c in l.strip('|').split('|')]
        if len(celdas) != 3:
            continue
        if set(''.join(celdas)) <= set('-: '):
            continue
        filas.append(celdas)
    pasos = [f for f in filas if f[0].isdigit()]
    assert len(pasos) == 4, (
        'se esperaban los cuatro pasos, y hay %d: %r' % (len(pasos), pasos))
    for numero, paso, hecho in pasos:
        assert paso, 'el paso %s no dice que hacer' % numero
        assert hecho, 'el paso %s no dice su criterio de «hecho»' % numero
    # y los cuatro pasos tienen que ser los que son
    texto = ' '.join(p[1].lower() for p in pasos)
    for ancla in ('203', 'ciegas', 'declarar', 'disparar'):
        assert ancla in texto, (
            'los pasos de A1 no hablan de %r, y la secuencia tiene que ser '
            'cerrar, fijar, declarar y disparar' % ancla)

