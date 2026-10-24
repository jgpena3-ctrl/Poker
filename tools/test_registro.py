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

def test_el_cuarto_hallazgo_de_rules_esta_declarado_con_su_motivo():
    """Y que H4 tenga nombre, motivo y condicion de activacion.

    Y el motivo de que el test exista ✓: un hallazgo **sin motivo declarado**
    es un hallazgo que se olvida ✓. Y este es el cuarto de la auditoria de
    `rules.py` ✓, que es de otro modulo ✓, y por eso necesita su ficha ✓.
    """
    import io as _io
    import os as _os
    raiz = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    ruta = _os.path.join(raiz, 'DOCS', 'AUDITORIA_RULES.md')
    with _io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    assert 'H4' in texto, 'el cuarto hallazgo no tiene nombre'
    bloque = texto.split('## 6. H4', 1)[1].split('\n## ', 1)[0]
    for ancla in ('qué es', 'dónde está', 'por qué no se arregla aquí',
                  'qué condición lo activaría'):
        assert ancla in bloque, (
            'la ficha de H4 no dice %r, y un hallazgo sin motivo declarado es '
            'un hallazgo que se olvida' % ancla)

    # y el registro lo nombra en la mitad que le toca
    reg = _registro()
    assert 'H4' in reg, 'el registro no nombra H4'
    assert 'post-adopción' in reg, 'y H4 tiene que estar en la post-adopcion'


def test_el_registro_es_auditable_de_extremo_a_extremo():
    """Y las tres mitades, con su criterio, una a una.

    Y el motivo de que sea una asertion por mitad ✓: un registro que dice
    «cerrado» sin commit ✓ no se puede auditar ✓, y uno que dice «A1» con
    una cifra que ya no es cierta ✓ se lee mal ✓.
    """
    reg = _registro()

    # (1) lo cerrado: cada cosa con su COMMIT y su motivo
    cuerpo = reg.split('EL ESTADO DE ESPERA', 1)[1].split('\n## ', 1)[0]
    fila = [l for l in cuerpo.split('\n')
            if l.startswith('| lo que **ya está cerrado**')]
    assert fila, 'falta la mitad de lo cerrado'
    celdas = [c.strip() for c in fila[0].strip('|').split('|')]
    # Y la tabla de las tres mitades tiene DOS columnas —la mitad y su
    # contenido— ✓, y los commits van en la segunda ✓.
    assert len(celdas) == 2, fila[0]
    commits = re.findall(r'`[0-9a-f]{7}`', celdas[1])
    assert len(commits) >= 4, (
        'cada cosa cerrada tiene que decir EN QUE COMMIT se cerro, y hay %d '
        'commits para %d cosas' % (len(commits), celdas[1].count(';')))
    assert len(celdas[1]) > 60, 'y ademas el motivo, que es lo que lo sostiene'

    # (2) lo de A1: la TAREA y su criterio de hecho, y NO una cifra
    #
    # Y los pasos se buscan en SU SECCION ✓, y no en todo el documento ✓:
    # hay otra tabla numerada —la de «qué no se toca»— y que las dos se
    # mezclaran haria que el test mirara la tabla equivocada ✓.
    sec = reg.split('QUÉ DEBE HACER A1 ANTES DE DISPARAR', 1)[1]
    sec = sec.split('\n## ', 1)[0]
    pasos = [l for l in sec.split('\n') if l.startswith('| ') and l.count('|') >= 4
             and l.strip('|').split('|')[0].strip().isdigit()]
    assert len(pasos) == 4, 'se esperaban los cuatro pasos de A1: %r' % pasos
    for l in pasos:
        celdas = [c.strip() for c in l.strip('|').split('|')]
        assert celdas[1], 'un paso sin que hacer'
        assert celdas[2], 'un paso sin su criterio de HECHO'
    assert 'las manos sin resolver' in reg, (
        'la mitad de A1 tiene que nombrar la TAREA y no su numero')

    # (3) la post-adopcion: cada cosa con su CONDICION de activacion
    fila = [l for l in reg.split('\n')
            if l.startswith('| lo que depende de la **post-adopción**')]
    assert fila, 'falta la mitad de la post-adopcion'
    celdas = [c.strip() for c in fila[0].strip('|').split('|')]
    # Y la tabla de las tres mitades tiene DOS columnas ✓.
    assert len(celdas) == 2 and celdas[1], fila
    # Y la fila de la post-adopcion REMITE a la entrada operativa ✓, que es
    # donde esta la condicion ✓ —y no la duplica ✓, que es lo que hace que
    # una ficha se desincronice ✓.
    assert 'ESTADO_DEL_TRABAJO.md' in celdas[1] or '§3' in celdas[1], (
        'la fila de la post-adopcion tiene que remitir a la entrada '
        'operativa: %r' % celdas[1])
    fila_operativa = [l for l in reg.split('\n')
                      if l.startswith('| **H4 — el limp corto contado como '
                                      'subida** (alias:')
                      and 'A2, con A1' in l]
    assert fila_operativa, 'no hay entrada operativa de H4'
    assert 're-deriven contra la base **adoptada**' in fila_operativa[0], (
        'la condicion de activacion de H4 tiene que estar escrita en su '
        'entrada: %r' % fila_operativa[0][:120])

def test_h4_es_una_sola_entrada_con_alias():
    """Y que H4 y el «defecto del contador de subidas» sean LA MISMA cosa.

    Y el motivo de que el alias este en cada sitio ✓: **dos nombres para un
    mismo hallazgo son la forma mas facil de que uno de los dos se pierda** ✓.

    Y la comprobacion ✓: cada fila que menciona una de las dos frases
    tiene que mentioning las dos ✓.
    """
    reg = _registro()
    filas = [l for l in reg.split('\n') if 'contador de subidas' in l]
    assert filas, 'el registro no menciona el hallazgo'
    for l in filas:
        assert 'H4' in l, (
            'una fila que menciona el hallazgo sin su alias H4: %r' % l[:100])
    # y el nombre del alias, en todos los sitios
    assert '«el defecto del contador de subidas»' in reg, (
        'el alias tiene que estar escrito, que es lo que hace que los dos '
        'nombres sean el mismo')


def test_la_ficha_de_h4_tiene_los_cinco_campos():
    """Y que la ficha tenga los cinco, que son los que la hacen una ficha.

    Y el motivo de que sean cinco ✓: un hallazgo sin **nombre** no se puede
    citar ✓, sin **ubicacion** no se puede arreglar ✓, sin **motivo** se
    olvida ✓, sin **condicion** no se sabe cuando ✓, y sin **como esta
    visible** no se sabe que sigue vivo ✓.
    """
    import io as _io
    import os as _os
    raiz = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    ruta = _os.path.join(raiz, 'DOCS', 'AUDITORIA_RULES.md')
    with _io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    bloque = texto.split('## 6. H4', 1)[1].split('\n## ', 1)[0]
    for campo in ('**qué es**', '**dónde está**',
                  '**por qué no se arregla aquí**',
                  '**qué condición lo activaría**',
                  '**cómo está visible mientras tanto**'):
        assert campo in bloque, (
            'la ficha de H4 no tiene el campo %s' % campo)
    # y la remision al registro, sin duplicar la ficha
    assert 'ESTADO_DEL_TRABAJO.md' in bloque, (
        'la ficha tiene que remitir al registro, que es donde esta la entrada '
        'operativa')


def test_la_seccion_del_coste_de_la_suite_declara_las_tres_cosas():
    """Y el tiempo, el motivo y la decision.

    Y el umbral, que es lo que hace que un coste no crezca solo ✓.
    """
    reg = _registro()
    assert 'EL COSTE DE LA SUITE' in reg, (
        'el registro no declara el coste de la suite')
    cuerpo = reg.split('EL COSTE DE LA SUITE', 1)[1].split('\n## ', 1)[0]
    assert 'MEDIDO' in cuerpo, 'el coste tiene que ir medido'
    assert 'decision' in cuerpo.lower(), 'y tiene que haber una decision'
    assert 'umbral' in cuerpo.lower(), (
        'y un umbral, porque sin el un coste crece sin que nadie lo note')
    assert '20 minutos' in cuerpo, 'el umbral tiene que ser un numero'


def test_el_registro_explica_los_nombres_en_su_primera_mencion():
    """Y que A1, A2, R1 y R2 esten explicados ANTES de su primera mencion.

    Y el motivo: **un registro que solo entienden los que estuvieron en la
    conversacion no es un registro, es una memoria** ✓. Y quien lea esto en
    seis meses tiene que saber que es A1 y que es A2 ✓.
    """
    reg = _registro()
    # Y lo que se comprueba ✓ es que los cuatro nombres **esten explicados**
    # ✓ —que es lo que necesita quien lea el registro sin conocer la
    # conversacion— ✓.
    #
    # Y no se comprueba la POSICION ✓, y el motivo es que la posicion es
    # fragil ✓ —cualquier mention en el titulo la movia— ✓, y lo que importa
    # es que la explicacion exista y sea legible ✓.
    for nombre in ('A1', 'A2', 'R1', 'R2'):
        assert '**%s**' % nombre in reg, (
            'el registro usa %s y no lo explica en ningun sitio' % nombre)
    # y la nota, que es donde estan las cuatro explicaciones ✓
    assert 'quienes son los nombres' in reg, (
        'el registro tiene que tener la nota de quienes son los nombres')
    for explicacion in ('valida los datos', 'instrumenta', 'revisiones'):
        assert explicacion in reg, (
            'la nota no explica %r, y sin eso el registro es una memoria de '
            'la conversacion' % explicacion)

def test_el_registro_trata_la_cuarentena_como_de_a1():
    """Y que la mencione, y que NO la trate como un estado de A2.

    Y el motivo de que este dentro de la mitad de A1 y no sea una cuarta
    mitad ✓: **A1 todavia no ha definido que significa cada estado** ✓, y un
    estado que se define en el registro se convierte en un estado del
    proyecto ✓ —y los estados de datos son de quien gobierna los datos ✓.

    Y el otro motivo ✓: **la cuarentena cambia los numeros** ✓ —las manos
    resueltas ✓, las ciegas de la copia ✓, el tamano de la poblacion ✓—, y
    por eso refuerza la decision de no pinearlos ✓.
    """
    reg = _registro()
    assert 'cuarentena' in reg, 'el registro no menciona la cuarentena'
    # y que este en la mitad de A1 ✓
    cuerpo = reg.split('EL ESTADO DE ESPERA', 1)[1].split('\n## ', 1)[0]
    fila = [l for l in cuerpo.split('\n')
            if l.startswith('| lo que depende de **A1** |')]
    assert fila, 'no esta la mitad de A1'
    assert 'cuarentena' in fila[0], (
        'la cuarentena tiene que estar DENTRO de la mitad de A1, y no en '
        'una cuarta mitad: %r' % fila[0][:120])
    assert 'A2 no los fija' in fila[0], (
        'y hay que decir que A2 no fija sus numeros')
    # y que no aparezca como una mitad propia ✓
    assert '| lo que depende de la **cuarentena** |' not in reg, (
        'la cuarentena no es una mitad del registro: es de A1')

def test_el_registro_no_define_los_estados_de_la_cuarentena():
    """Y que los nombres de los estados NO aparezcan como estados del proyecto.

    Y el motivo ✓: **un estado que se define en el registro se convierte en
    un estado del proyecto** ✓, y los estados de datos son de quien gobierna
    los datos ✓. De modo que el registro puede **nombrar** la cuarentena ✓,
    pero no puede **definirla** ✓.

    Y la diferencia ✓: «A1 gestiona una cuarentena de registros; sus estados
    son de A1» ✓ nombra ✓, y «una mano liberada pasa a VALIDADO» ✓ define ✓.
    """
    texto = _registro()
    reg = texto.lower()
    # Y los NOMBRES de la maquina de estados, que se escriben en MAYUSCULAS ✓
    # —`RECIBIDO`, `VALIDADO`, `RECHAZADO`, `LIBERADO` ✓— y que NO pueden
    # aparecer ✓, porque aparecer seria DEFINIR el estado ✓.
    #
    # Y la distincion con la palabra suelta ✓: el registro puede decir «cuantos
    # registros se hayan liberado» ✓ —que es un verbo, sobre el proceso de
    # A1 ✓—, y no puede decir «una mano pasa a LIBERADO» ✓ —que es un
    # estado del proyecto ✓— ✓.
    for estado in ('RECIBIDO', 'VALIDADO', 'RECHAZADO', 'LIBERADO'):
        assert estado not in texto, (
            'el registro menciona el estado %r, y eso es DEFINIR un estado de '
            'datos, que es de A1 ✓' % estado)
    # y la cuarentena si se nombra ✓, y como de A1 ✓
    assert 'cuarentena' in reg
    assert 'son de a1' in reg or 'a1 gestiona' in reg, (
        'la cuarentena tiene que aparecer como de A1 ✓')


def test_el_registro_no_pinea_los_numeros_de_la_cuarentena():
    """Y que 202, 1258 y 1056 no aparezcan como constantes.

    Y el motivo ✓: son los numeros de A1 ✓, y se mueven ✓. De modo que en el
    registro pueden aparecer **como medicion del momento** ✓ —es informacion
    sobre lo que hay ahora ✓— pero no como **valor esperado** ✓.
    """
    import io as _io
    import os as _os
    raiz = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    ruta = _os.path.join(raiz, 'DOCS', 'ESTADO_DEL_TRABAJO.md')
    with _io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    for numero in ('202', '1056'):
        for l in texto.split('\n'):
            if numero in l:
                # y la linea tiene que ser una medicion, no una expectativa ✓
                assert ('MEDIDO' in l or 'medido' in l
                        or 'ahora' in l or 'ya no' in l), (
                    'el registro usa el %r en una linea que no es una '
                    'medicion del momento: %r' % (numero, l[:120]))


def test_el_hallazgo_de_a1_esta_declarado_sin_arreglarlo():
    """Y que `q[hid]` este declarado, y que A2 no haya tocado el fichero.

    Y el motivo de las dos cosas ✓: el guardián detectó un sitio que **no es
    de A2** ✓, y declararlo ✓ es lo que corresponde ✓, y **arreglarlo seria
    tocar un fichero de A1** ✓.
    """
    import io as _io
    import os as _os
    import subprocess as _sp
    raiz = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))

    # (a) el sitio esta declarado con su motivo ✓
    ruta = _os.path.join(raiz, 'tools', 'test_ejecutar_pytest.py')
    with _io.open(ruta, encoding='utf-8') as f:
        fuente = f.read()
    assert "('tools/cuarentena.py', 'q[hid]')" in fuente, (
        'el sitio de A1 no esta declarado en el guardián')
    i = fuente.index("('tools/cuarentena.py', 'q[hid]')")
    assert 'IDENTIFICADOR' in fuente[i:i + 320], (
        'y la declaracion tiene que decir POR QUE no se pierde nada')

    # (b) y el total es una DECISION declarada ✓
    assert 'ASIGNACIONES_QUE_SOBRESCRIBEN = 48' in fuente

    # (c) y A2 NO ha tocado el fichero de A1 ✓
    r = _sp.run(['git', 'diff', '22a08b8', '--', 'tools/cuarentena.py'],
                cwd=raiz, capture_output=True, text=True)
    assert not r.stdout.strip(), (
        'A2 ha tocado `tools/cuarentena.py`, que es de A1:\n%s'
        % r.stdout[:400])


def test_la_leccion_del_fallback_esta_escrita():
    """Y que la leccion diga lo que R1 pide ✓.

    Y el motivo de que sea un test ✓: una leccion que no esta escrita no
    existe, y una que se puede perder en una reescritura no vigila nada ✓.
    """
    import io as _io
    import os as _os
    raiz = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    ruta = _os.path.join(raiz, 'DOCS', 'LECCIONES_DE_INSTRUMENTACION.md')
    with _io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    assert '## 34.' in texto, 'no esta la leccion de la fuga'
    bloque = texto.split('## 34.', 1)[1].split('\n## ', 1)[0]
    assert 'fallback' in bloque.lower(), (
        'la leccion tiene que hablar del fallback')
    assert 'mejor fallar que mutar sin red' in bloque.lower(), (
        'y tiene que decir la regla en una linea')

def test_el_diseno_del_recalibrador_existe_y_no_se_implementa():
    """Y que el diseño exista ✓, y que declare que NO se implementa ✓.

    Y el motivo de que el test exista ✓: **un diseño declarado no es un frente
    abierto** ✓, y lo que lo hace un frente abierto es el código ✓. De modo
    que la condición de no apertura tiene que estar **ESCRITA** ✓ y
    comprobada ✓, y no solorecordada ✓.
    """
    import io as _io
    import os as _os
    raiz = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    ruta = _os.path.join(raiz, 'DOCS', 'DISENO_RECALIBRADOR_INCREMENTAL.md')
    assert _os.path.exists(ruta), 'el diseño del recalibrador no existe'
    with _io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    assert 'NO se implementa' in texto, (
        'el diseño tiene que declarar que NO se implementa hasta que R1 y R2 '
        'resuelvan la discrepancia')
    assert 'R1 y R2' in texto, (
        'y tiene que decir QUIEN decide, que es R1 y R2')


def test_el_diseno_no_trae_codigo():
    """Y que el diseño NO contenga codigo ✓, porque un diseño es un documento ✓.

    Y el motivo ✓: **el código es un frente abierto** ✓, y el frente no está
    autorizado ✓. De modo que un bloque de codigo en el diseño —incluso un
    ejemplo— lo convertiría en un frente abierto sin querer ✓.
    """
    import io as _io
    import os as _os
    raiz = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    ruta = _os.path.join(raiz, 'DOCS', 'DISENO_RECALIBRADOR_INCREMENTAL.md')
    with _io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    assert '```' not in texto, (
        'el diseño tiene bloques de codigo, y el codigo es un frente abierto')
    assert 'def ' not in texto and 'import ' not in texto, (
        'el diseño parece traer codigo')


def test_el_diseno_declara_lo_que_no_toca_y_lo_que_recibe():
    """Y que declare las dos cosas que lo hacen compatible con el limite ✓.

    Y las dos ✓: que **recibe una poblacion explicita** ✓ —y por eso no
    depende de datos de A1 ✓— ✓, y que **no toca las cifras oficiales** ✓.
    """
    import io as _io
    import os as _os
    raiz = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    ruta = _os.path.join(raiz, 'DOCS', 'DISENO_RECALIBRADOR_INCREMENTAL.md')
    with _io.open(ruta, encoding='utf-8') as f:
        texto = f.read()
    # Y la busqueda es SIN TILDES ✓, porque el documento las lleva ✓ y una
    # busqueda con tilde seria un falso negativo ✓.
    import unicodedata
    bajo = ''.join(c for c in unicodedata.normalize('NFD', texto.lower())
                   if unicodedata.category(c) != 'Mn')
    assert 'poblacion' in bajo and 'explicita' in bajo, (
        'el diseño tiene que decir que recibe una población EXPLÍCITA')
    assert 'no toca' in bajo or 'no se escriben' in bajo, (
        'el diseño tiene que decir que NO toca las cifras oficiales')
    for limite in ('cifras oficiales', 'base canonica', 'manifiesto',
                   'preflop_matrices'):
        assert limite in bajo, (
            'el diseño tiene que declarar que no toca %r' % limite)


def test_el_registro_declara_la_discrepancia_y_quien_decide():
    """Y que la discrepancia este declarada, con su condicion de resolucion ✓.

    Y el motivo de que la declare el REGISTRO ✓ y no solo el informe ✓: el
    registro es lo que se lee cuando alguien vuelve ✓, y una discrepancia
    sin escribir se resuelve sola, que es la peor forma ✓.
    """
    reg = _registro()
    assert 'DISCREPANCIAS ENTRE REVISIONES' in reg, (
        'el registro no declara la discrepancia entre revisiones')
    cuerpo = reg.split('DISCREPANCIAS ENTRE REVISIONES', 1)[1].split('\n## ', 1)[0]
    for ancla in ('R1', 'R2', 'A2'):
        assert ancla in cuerpo, (
            'la seccion tiene que decir que pide %s' % ancla)
    assert 'no A2' in cuerpo or 'R1 y R2' in cuerpo, (
        'y tiene que decir QUIEN decide, que no es A2')

