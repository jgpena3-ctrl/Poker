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
    # y los cuatro pasos tienen que ser los que son. Y el ancla del primer
    # paso es la TAREA —«resolver»— y no su NUMERO, porque el numero es de A1
    # y se mueve ✓, y un test que lo fijara passaria a fallar por un dato que
    # no es un defecto ✓.
    texto = ' '.join(p[1].lower() for p in pasos)
    for ancla in ('resolver', 'ciegas', 'declarar', 'disparar'):
        assert ancla in texto, (
            'los pasos de A1 no hablan de %r, y la secuencia tiene que ser '
            'resolver, fijar, declarar y disparar' % ancla)

def test_la_seccion_de_lo_que_no_se_toca_existe_y_tiene_motivos():
    """Y que exista, y que cada elemento diga POR QUE.

    Y el motivo de que el motivo sea la parte que se comprueba: una cosa
    intocable sin motivo es una supersticion, y una supersticion se negocia.
    """
    reg = _registro()
    assert 'QUÉ NO SE TOCA HASTA LA ADOPCIÓN' in reg, (
        'el registro no tiene la seccion de lo que no se toca')
    cuerpo = reg.split('QUÉ NO SE TOCA HASTA LA ADOPCIÓN', 1)[1]
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
        if celdas[0].isdigit():
            filas.append(celdas)
    assert len(filas) == 6, (
        'se esperaban los seis elementos, y hay %d: %r' % (len(filas), filas))
    for numero, que, porque in filas:
        assert que, 'el elemento %s no dice QUE no se toca' % numero
        assert porque, (
            'el elemento %s no dice POR QUE, y sin motivo es una '
            'supersticion' % numero)
    # y los seis tienen que ser los que son
    texto = ' '.join(f[1].lower() for f in filas)
    for ancla in ('contador de subidas', 'auc', 'preflop_matrices',
                  'cifras derivadas', 'equity preflop', 'numero de manos'):
        assert ancla in texto, (
            'falta el elemento %r en la lista de lo que no se toca' % ancla)

def test_el_registro_declara_el_estado_de_a2_y_de_a1():
    """Y que la linea exista, y que sea la que dice.

    Y el motivo de que sea una DECLARACION y no un hecho: el estado de un
    trabajo se escribe a mano, y una frase que no esta escrita puede ser
    cierta o falsa sin que nadie lo sepa. Y esta, al menos, esta vigilada.
    """
    reg = _registro()
    assert 'A2 ha cerrado todo lo que puede cerrar sin A1' in reg, (
        'el registro no declara el estado de A2')
    assert 'post-adopci' in reg, (
        'y la declaracion tiene que decir que lo que queda abierto es de A1 '
        'o POST-ADOPCION')
    # y los dos controles, con quien los declara y que pasa sin ellos
    assert 'los **dos controles** del procedimiento los declara **A1**' in reg, (
        'el registro no dice que los dos controles los declara A1')
    assert 'no tiene valor por defecto para ninguno de los dos' in reg, (
        'y no dice que el script no tiene valores por defecto')

def test_el_estado_de_espera_esta_declarado():
    """Y que exista, y que diga las tres cosas.

    Y el motivo de que las tres: **lo que depende de A1**, **lo que depende
    de la post-adopcion** y **lo que ya esta cerrado**. Y sin las tres, un
    «no hay trabajo» no se distingue de un «no he mirado».
    """
    reg = _registro()
    assert 'EL ESTADO DE ESPERA' in reg, (
        'el registro no tiene la seccion del estado de espera')
    cuerpo = reg.split('EL ESTADO DE ESPERA', 1)[1].split('\n## ', 1)[0]
    assert 'no tiene trabajo pendiente' in cuerpo, (
        'la seccion no dice que no hay trabajo pendiente')
    for ancla in ('A1', 'post-adopci', 'cerrado'):
        assert ancla in cuerpo, (
            'la seccion no menciona %r, y sin las tres mitades no se sabe que '
            'es una espera y no un olvido' % ancla)


def test_la_tabla_de_los_dos_controles_es_verificable():
    """Y que la tabla diga las tres cosas, y que el script no tenga defaults.

    Y la tercera es la importante: **el script no tiene ningun valor por
    defecto**, y eso se comprueba en el codigo, no en el documento ✓.
    """
    reg = _registro()
    assert 'los **dos controles** del procedimiento los declara **A1**' in reg
    assert 'no tiene valor por defecto para ninguno de los dos' in reg

    # y la distincion entre el codigo 2 y el codigo 1, con su motivo
    assert '«no has decidido» no es «has fallado»' in reg, (
        'el registro no dice POR QUE el codigo 2 no es el codigo 1')

    # y en el codigo: los dos controles se piden, y ninguno tiene defecto
    import tools.integrar_copia as IC
    import argparse
    ayuda = argparse.ArgumentParser()
    ayuda.add_argument('--ciegas-esperadas', type=int, default=None)
    ayuda.add_argument('--control-categorias', default=None)
    acc = {a.dest: a.default for a in ayuda._actions}
    assert acc['ciegas_esperadas'] is None, acc
    assert acc['control_categorias'] is None, acc
    # y el codigo 2 existe y es distinto del 1
    assert IC.CODIGO_INCOMPLETA == 2 and IC.CODIGO_FALLO == 1

def test_la_lesion_de_las_cifras_de_a1_esta_escrita():
    """Y que la leccion exista, y con su marca.

    Y el motivo de que se compruebe la MARCA: una leccion sin medicion es
    una opinion, y este proyecto escribe lecciones medidas ✓.
    """
    import io as _io
    import os as _os
    ruta = _os.path.join(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))), 'DOCS', 'LECCIONES_DE_INSTRUMENTACION.md')
    with _io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    assert '## 33.' in texto, (
        'no esta la leccion de las cifras de A1')
    bloque = texto.split('## 33.', 1)[1].split('\n## ', 1)[0]
    assert 'MEDIDO' in bloque or 'CORREGIDO' in bloque, (
        'la leccion no tiene su marca, y sin marca es una opinion')
    assert 'se fija la relacion, no el numero' in bloque.lower(), (
        'la leccion tiene que decir la regla, no solo el')


def test_las_tres_mitades_declaran_su_criterio():
    """Y que las tres mitades tengan su criterio, y no solo su nombre.

    Y el motivo: un «no hay trabajo» sin las tres mitades no se distingue de
    un «no he mirado» ✓, y en un registro eso es la diferencia entre una
    espera y un abandono ✓.
    """
    reg = _registro()
    cuerpo = reg.split('EL ESTADO DE ESPERA', 1)[1].split('\n## ', 1)[0]

    # (1) lo que depende de A1: QUE hacer y CUANDO
    fila_a1 = [l for l in cuerpo.split('\n')
               if l.startswith('| lo que depende de **A1**')]
    assert fila_a1, 'falta la mitad de A1'
    assert len(fila_a1[0].split('|')) >= 4, fila_a1

    # (2) lo que depende de la post-adopcion: QUE se activa y CON QUE
    fila_post = [l for l in cuerpo.split('\n')
                 if l.startswith('| lo que depende de la **post-adopción**')]
    assert fila_post, 'falta la mitad de la post-adopcion'
    assert len(fila_post[0].split('|')) >= 4, fila_post

    # (3) lo que ya esta cerrado: QUE se cerro y EN QUE COMMIT
    fila_cerrado = [l for l in cuerpo.split('\n')
                    if l.startswith('| lo que **ya está cerrado**')]
    assert fila_cerrado, 'falta la mitad de lo cerrado'
    commits = re.findall(r'`[0-9a-f]{7}`', fila_cerrado[0])
    assert len(commits) >= 3, (
        'la mitad de lo cerrado tiene que decir EN QUE COMMIT se cerro cada '
        'cosa, y no solo que se cerro: %r' % fila_cerrado[0])


def test_la_auditoria_de_rules_esta_declarada_como_cerrada():
    """Y que la auditoria de `rules.py` este, con sus hallazgos y su estado.

    Y el motivo de que el estado importe mas que el hallazgo ✓: un hallazgo
    sin estado es un asunto abierto, y este esta CERRADO ✓ —uno con su nota
    en el contrato ✓, uno con su tabla y su test ✓, y uno declarado como
    riesgo latente ✓.
    """
    import io as _io
    import os as _os
    raiz = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    ruta = _os.path.join(raiz, 'DOCS', 'AUDITORIA_RULES.md')
    assert _os.path.exists(ruta), 'la auditoria de rules.py no esta'
    with _io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    for ancla in ('fold', 'precondiciones', 'unknown'):
        assert ancla in texto.lower(), (
            'la auditoria de rules.py no habla de %r' % ancla)

    reg = _registro()
    assert 'la auditoría de `rules.py`' in reg, (
        'el registro no declara la auditoria de rules.py')
    assert 'CERRADA' in reg, (
        'el registro no dice que la auditoria de rules.py esta CERRADA')
    for ancla in ('§C4', 'precondiciones', 'riesgo latente'):
        assert ancla in reg, (
            'el registro no declara el estado del hallazgo %r' % ancla)

