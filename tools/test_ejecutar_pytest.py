# -*- coding: utf-8 -*-
"""PRUEBAS DEL MODULO `ejecutar_pytest.py`. Que se pruebe a si mismo.

POR QUE ESTE FICHERO EXISTE

El modulo declara cuatro reglas. Un modulo que declara reglas y no las
prueba es un documento, no un mecanismo — y este repositorio lleva veintiocho
bloques distinguiendo las dos cosas.

Y hay una regla que lo necesita MAS que las otras: la que rechaza el
selector suelto. Si `auditar_comando()` no puede fallar, es codigo muerto, y
el codigo muerto que parece una comprobacion es lo peor que hay: da la
sensacion de que la regla esta puesta.

Asi que la primera prueba de este fichero no es «la regla funciona»: es
«la regla se ha ejecutado de verdad», y para eso hay que darle el comando
MAL, y ver que se cae.

LO QUE ESTA MEDIDO, Y ESTA ESCRITO EN EL MODULO

    FICHERO -q ::test   ->  codigo 4   (no se ha ejecutado nada)
    FICHERO::test       ->  codigo 1   (ha fallado el que se queria)

Y la asimetria que obliga a dos comprobaciones distintas:

    en VERDE, con `-q`, el nombre del test NO sale en la salida
    en ROJO, sale: `FAILED tools/x.py::test_nombre`

Asi que en verde hay que mirar el RECUENTO, y en rojo el NOMBRE. Una sola
comprobacion con un «o» haria verde el caso imposible y caeria en el otro.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import ejecutar_pytest as ep                             # noqa: E402
import retraccion_scan as rs                             # noqa: E402

FICH = os.path.join(ROOT, 'tools', 'test_causa_no_validez.py')
VERDE = 'test_la_prueba_causal_sigue_en_pie'
ROTO = 'test_la_tesis_de_no_validez_se_afirma_como_no_demostrada'
FRASE = ('Eso **no** está demostrado, y no lo puede',
         'Eso **sí** está demostrado, y lo puede')


def _docs_con_la_tesis_afirmada():
    tmp = tempfile.mkdtemp(prefix='opencode_afirmada_')
    destino = os.path.join(tmp, 'DOCS')
    shutil.copytree(os.path.join(ROOT, 'DOCS'), destino)
    ruta = os.path.join(destino, 'QUE_REPRESENTA_LA_PREDICCION.md')
    with open(ruta, encoding='utf-8') as f:
        t = f.read()
    viejo, nuevo = FRASE
    assert viejo in t, 'el texto de la tesis ha cambiado: hay que actualizar'
    with open(ruta, 'w', encoding='utf-8', newline='') as f:
        f.write(t.replace(viejo, nuevo))
    env = dict(os.environ)
    env[rs.DIR_DE_DOCUMENTOS] = destino
    env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
    return tmp, env


# ============================ 1. LA REGLA QUE NO PUEDE FALLAR, SÍ FALLA
def test_auditar_comando_rechaza_el_selector_suelto():
    """La prueba de que el guard esta vivo.

    Y el comando que se le da es el que de verdad daba 4, medido. No una
    invencion: el orden que de verdad daba 4, medido, y que se ha
    escrito en mas de un sitio.

    Y el fallo tiene que NOMBRAR el 4, porque el motivo de la regla es el
    4: sin el 4, el mensaje dice «esto no me gusta» y no dice «esto te daria
    un falso verde»."""
    mal = [sys.executable, '-m', 'pytest', FICH, '-q', '::' + VERDE,
           '--no-header', '-p', 'no:cacheprovider']
    with pytest.raises(AssertionError) as ei:
        ep.auditar_comando(mal)
    mensaje = str(ei.value)
    assert '::' in mensaje, (
        'el fallo tiene que señalar el selector suelto: %s' % mensaje)
    assert '4' in mensaje, (
        'el fallo tiene que decir el %d, que es lo que hace peligroso el '
        'error: sin el numero, «esto no me gusta» no es «esto te daria un '
        'falso verde». Mensaje: %s'
        % (ep.CODIGO_NINGUNO_EJECUTADO, mensaje))
    assert 'ADJACENTE' in mensaje, (
        'y tiene que decir como se arregla: %s' % mensaje)


def test_auditar_comando_acepta_el_selector_adyacente():
    """La otra mitad: si la regla rechazara todo, tambien seria codigo
    muerto, del otro tipo."""
    bien = [sys.executable, '-m', 'pytest', FICH + '::' + VERDE,
            '-q', '--no-header', '-p', 'no:cacheprovider']
    assert ep.auditar_comando(bien) is None


def test_el_guard_rechaza_tambien_un_comando_sin_fichero():
    """La segunda mitad de `auditar_comando`. Sin `.py` no hay prueba: hay
    pytest sobre el directorio entero, que es mas lento y mas fragil, y
    nadie lo ha pedido."""
    with pytest.raises(AssertionError) as ei:
        ep.auditar_comando([sys.executable, '-m', 'pytest', '-q'])
    assert '.py' in str(ei.value)


# ============================ 2. LO QUE EL CODIGO NO DICE
def test_un_nombre_que_no_existe_nunca_llega_a_ser_un_fallo():
    """La regla 2, probada con el caso que la provoca.

    Un nombre de test que no existe NO es un test que falla: es que no se ha
    ejecutado nada. Y eso no es 0, asi que un `!= 0` lo aprueba en verde.
    `correr()` tiene que cortarlo ANTES de devolver nada, que es lo unico
    que evita que el que llama lo interprete como una rotura que ha roto.

    Y EL CODIGO SE MIDE, no se supone. Escribi que este caso daba 5
    —NO_TESTS_COLLECTED— y da 4:

        pytest FICHERO::test_que_no_existe
        ERROR: not found: ... (no match in any of [<Module ...>])
        -> 4

    Que es el mismo error que R1 cometio con `y = 0`: un numero escrito sin
    medir. Y la consecuencia es la que hace util medirlo: el modulo vigila
    LOS DOS codigos, y esa lista no esta razonada, esta medida.

    Y el test, en vez de comprobar contra el numero que yo creia, comprueba
    contra los dos que el modulo dice cortar, y que el que salio sea uno de
    ellos. Si pytest cambiara, el test avisa en vez de seguir."""
    with pytest.raises(AssertionError) as ei:
        ep.correr(FICH, 'este_test_no_existe')
    m = str(ei.value)
    cortado = {ep.CODIGO_NINGUNO_EJECUTADO, ep.CODIGO_NINGUNO_ENCONTRADO}
    cual = [c for c in cortado if str(c) in m.split('pytest ha dado')[1][:8]]
    assert cual, (
        'el fallo tiene que decir el codigo que ha salido, y ha salido uno '
        'que el modulo no recorta. O sea que hay un codigo por el que se '
        'pasa un `!= 0` sin que este modulo lo pare. Mensaje:\n%s' % m)
    assert 'fallo de test' in m, (
        'y tiene que decir POR QUE no lo es, que es lo que evita el falso '
        'verde: %s' % m[:300])


def test_correr_solo_descarta_4_y_5():
    """Y no descarta mas: un 1 se devuelve, porque el que llama tiene que
    poder leer «ha fallado» y decidir si es el suyo."""
    codigo, salida = ep.correr(FICH, VERDE)
    assert codigo == 0, 'el test de control deberia pasar'
    assert 'no tests ran' not in salida


# ============================ 3. VERDE: EL RECUENTO, NO EL NOMBRE
def test_en_verde_el_nombre_del_test_no_sale():
    """La asimetria, medida. Y es la que obliga a que `afirmar_verde` mire
    el RECUENTO: buscar el nombre seria falso siempre, y un `or` con el
    nombre dejaria la comprobacion en verde por una rama que nunca ocurre."""
    codigo, salida = ep.correr(FICH, VERDE)
    assert codigo == 0
    assert '::%s' % VERDE not in salida, (
        'el nombre ha salido en VERDE. Entonces la regla de esta pagina esta '
        'equivocada y hay que revisar el modulo entero. Salida:\n%s'
        % salida[-600:])
    assert '1 passed' in salida, (
        'pero el RECUENTO si sale, y es el que se puede mirar:\n%s'
        % salida[-400:])


def test_afirmar_verde_pasa_con_el_test_que_se_pide():
    assert '1 passed' in ep.afirmar_verde(FICH, VERDE)


def test_afirmar_verde_pasa_con_el_control_y_falla_con_el_documento_roto():
    """Las dos mitades, porque «cae» no dice nada si no se dice cuando.

    Y la primera mitad es el CONTROL: con el DOCS real, ese test tiene que
    PASAR. Una version anterior de esta prueba decia lo contrario —«cae con
    el DOCS real»— y era falso: es el test de control, y por eso pasa. Lo que
    tiene que caer es cuando el documento se rompe.

    Y fallar por la razon equivocada tambien es fallar: el fallo tiene que
    decir que esperaba verde, no cualquier cosa."""
    assert '1 passed' in ep.afirmar_verde(FICH, ROTO)
    tmp, env = _docs_con_la_tesis_afirmada()
    try:
        with pytest.raises(AssertionError) as ei:
            ep.afirmar_verde(FICH, ROTO, env=env, cwd=ROOT)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    m = str(ei.value)
    assert ROTO in m, (
        'el fallo tiene que NOMBRAR el test: %s' % m[:300])
    assert 'PASASE' in m, (
        'y tiene que decir que se esperaba que pasara: %s' % m[:300])


# ============================ 4. ROJO: EL NOMBRE, Y QUE SEA EL MIO
def test_afirmar_caida_acepta_la_caida_por_la_razon_esperada():
    tmp, env = _docs_con_la_tesis_afirmada()
    try:
        salida = ep.afirmar_caida(FICH, ROTO, env=env, cwd=ROOT)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert '::%s' % ROTO in salida, (
        'la salida tiene que nombrar el test que ha caido: %s' % salida[-400:])


def test_afirmar_caida_exige_que_el_nombre_SEA_EL_MIO():
    """La mitad que hace el trabajo: el codigo 1 no dice cual.

    Y aqui se prueba de verdad: se pide el nombre de UN test mientras se
    ejecuta otro. El 1 sale igual, y `afirmar_caida` tiene que caer — que es
    justo el fallo que un `!= 0` no veria nunca."""
    tmp, env = _docs_con_la_tesis_afirmada()
    try:
        with pytest.raises(AssertionError) as ei:
            ep.afirmar_caida(FICH, VERDE, env=env, cwd=ROOT)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    m = str(ei.value)
    assert VERDE in m, (
        'el fallo tiene que decir el nombre que se pedia, que es lo unico '
        'que distingue este caso de una caida cualquiera: %s' % m[:300])
    assert 'FAILED' in m or 'CAESE' in m, (
        'y tiene que decir o que el codigo no fue 1, o que no hubo un FAILED '
        'con ese nombre. Lo que hace el trabajo es el segundo: %s' % m[:400])


def test_afirmar_caida_exige_el_recuento_cuando_se_ejecuta_el_fichero():
    """Con `test=None` no hay un nombre mio que exigir: hay un RECUENTO de
    fallos. Y es lo que sale, y lo que se comprueba."""
    tmp, env = _docs_con_la_tesis_afirmada()
    try:
        salida = ep.afirmar_caida(FICH, None, env=env, cwd=ROOT)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert ' failed' in salida, (
        'la salida del fichero entero tiene que traer el recuento: %s'
        % salida[-400:])
    # y si el fichero entero pasa, tiene que CAER la comprobacion
    with pytest.raises(AssertionError) as ei:
        ep.afirmar_caida(FICH, None, cwd=ROOT)
    m = str(ei.value)
    assert 'CAESE' in m, (
        'sin romper nada el fichero entero pasa, y `afirmar_caida` tiene que '
        'quejarse de eso, no de otra cosa: %s' % m[:300])
    assert FICH in m, (
        'y el fallo tiene que decir de que fichero habla: %s' % m[:300])


def test_afirmar_caida_con_el_control_no_miente():
    """La precondicion: el fichero de control esta VERDE, asi que pedir su
    caida tiene que fallar. Sin esto, los tests de arriba probarian que
    `afirmar_caida` se queja, no que se queja CUANDO DEBE."""
    with pytest.raises(AssertionError):
        ep.afirmar_caida(FICH, VERDE, cwd=ROOT)


# ============================ 5. Y QUE NADIE USE «DISTINTO DE CERO»
def test_ningun_test_de_este_repositorio_acepta_el_codigo_cuatro():
    """La regla aplicada a los ficheros que TIENEN subprocesos.

    Y se busca el `!= 0` en el fuente, no se mira el nombre de la variable:
    una version anterior busco `returncode != 0` y fallo porque aqui la
    variable se llama `codigo`. Un mal test por partida doble — falla por una
    razon que no es la que vigila, y obliga a escribir el codigo como el
    test."""
    import re
    for nombre in ('test_sensibilidad_end_to_end.py', 'test_tareas_r1.py'):
        ruta = os.path.join(ROOT, 'tools', nombre)
        fuente = open(ruta, encoding='utf-8').read()
        # Y la precondicion: tiene subprocesos DE ALGUNA DE LAS DOS FORMAS.
        #
        # Se puso `subprocess.run(` y sola, y se quedo desfasada en cuanto el
        # fichero que vigila paso a usar el modulo. Un test que se invalida con
        # el arreglo que pretendia vigilar es un test que se desactiva sin
        # avisar: lo unico que hizo fue fallar su precondicion.
        #
        # Y es la razon de que la precondicion sea «alguno de los dos» y no
        # «este»: una precondicion estrecha deja de ser certaina el mismo dia
        # que se arregla lo que vigila, y un test que se apaga solo no es un
        # test que avisa.
        assert ('subprocess.run(' in fuente
                or 'ejecutar_pytest' in fuente), (
            '%s no tiene subprocesos de pytest, ni directos ni por el '
            'modulo, asi que este test no aplica' % nombre)
        # se Busca un `!= 0` APLICADO A UN RESULTADO, no la palabra suelta
        usado = re.findall(r'(?:returncode|codigo|r\.returncode)\s*!=\s*0',
                           fuente)
        assert not usado, (
            '%s usa «!= 0» %d vez/veces sobre el resultado de un subproceso. '
            'Un %d —«no se ha ejecutado nada»— tambien es «distinto de '
            'cero», asi que eso pasa en verde. Lo que hay que usar es '
            'ejecutar_pytest.afirmar_caida, que ademas comprueba que el '
            'nombre que ha caido es el mio.'
            % (nombre, len(usado), ep.CODIGO_NINGUNO_EJECUTADO))
        # y que use el modulo
        assert 'ejecutar_pytest' in fuente, (
            '%s tiene subprocesos de pytest y no usa el modulo comun. Tres '
            'copias de la regla son tres sitios donde equivocarse' % nombre)


# ============================ 6. ESCRITO Y SIN PROBAR
def test_una_escritura_sin_ejecucion_queda_pendiente_y_se_nombra():
    """El invariante, probandose a si mismo.

    Y en las DOS mitades, porque un invariante que solo dice «detecta» no
    dice «no falsea nada»: si acusara de todo, tambien pasaria. Y una regla
    que acusa de todo es una regla que nadie va a mirar cuando praise.

    Y este invariante ya estuvo roto en verde: la primera version marcaba
    el DIRECTORIO entero, y como las tres roturas de un contrato comparten
    directorio, la ejecucion de la segunda borraba la marca de la primera.
    Con el hueco abierto decia `codigo = 0`.

    La version mala tambien estaba en verde, y tambien «funcionaba». Que
    es la unica forma de que se note que un invariante hay que probarlo
    ROMPIENDOLO, y no mirandolo pasar."""
    import shutil
    import tempfile
    directorio = tempfile.mkdtemp(prefix='opencode_sinprobar_')
    try:
        ruta = os.path.join(directorio, 'UN_TXT.md')
        ep.escribir_documento(ruta, 'lo que sea', que='LA MUTACION')
        pendientes = ep.sin_probar()
        assert pendientes, (
            'una escritura que no ha llegado a ningun test tiene que quedar '
            'pendiente, y no queda. O sea que el invariante no vigila')
        assert pendientes[0][0] == 'LA MUTACION', (
            'y el pendiente tiene que decir QUE se escribio, no el '
            'directorio: un fallo que dice «falta probar» sin decir que es '
            'inaccionable. Pendientes: %r' % (pendientes,))
    finally:
        shutil.rmtree(directorio, ignore_errors=True)


def test_una_escritura_con_ejecucion_no_queda_pendiente():
    """La otra mitad: ejecutada, se absuelve.

    Y con un test de verdad, no con un registro a mano. Si se registrara a
    dedo, la comprobacion probaria que la lista se vacia con un dato puesto
    a proposito, que es lo que hace cualquier lista."""
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix='opencode_absuelta_')
    try:
        destino = os.path.join(tmp, 'DOCS')
        shutil.copytree(os.path.join(ROOT, 'DOCS'), destino)
        ruta = os.path.join(destino, 'UN_TXT.md')
        ep.escribir_documento(ruta, 'lo que sea', que='LA MUTACION')
        env = dict(os.environ)
        env[rs.DIR_DE_DOCUMENTOS] = destino
        env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
        ep.correr(FICH, VERDE, env=env, cwd=ROOT)
        pendientes = ep.sin_probar()
        assert not pendientes, (
            'una escritura que ha llegado a un test NO tiene que quedar '
            'pendiente, y queda: %r' % (pendientes,))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_dos_escrituras_y_una_ejecucion_no_absuelven_a_las_dos():
    """Y lo que motivo el diseno: con dos mutaciones seguidas y UNA sola
    ejecucion, la primera queda pendiente.

    Es el caso exacto del fallo del bloque —escribir, escribir, y ejecutar
    una sola vez— y el que la version de MARCA por directorio no podia ver,
    porque la unica ejecucion borraba las dos marcas.

    Y que sea la PRIMERA y no la segunda es la regla, leida bien: una
    escritura queda pendiente si no hay una ejecucion ANTES de la siguiente
    escritura. Al reves seria verdad de forma accidental, y esta prueba se
    escribio poniendo «LA SEGUNDA» y fallando: el codigo estaba bien y la
    expectativa mal.

    Que es el favor de siempre: la prueba no solo comprueba el codigo, lo
    pone en aprietos."""
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix='opencode_dos_')
    try:
        destino = os.path.join(tmp, 'DOCS')
        shutil.copytree(os.path.join(ROOT, 'DOCS'), destino)
        env = dict(os.environ)
        env[rs.DIR_DE_DOCUMENTOS] = destino
        env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
        ep.escribir_documento(os.path.join(destino, 'A.md'), 'a',
                              que='LA PRIMERA')
        ep.escribir_documento(os.path.join(destino, 'B.md'), 'b',
                              que='LA SEGUNDA')
        ep.correr(FICH, VERDE, env=env, cwd=ROOT)
        pendientes = [q for q, _ in ep.sin_probar()]
        assert pendientes == ['LA PRIMERA'], (
            'con dos escrituras seguidas y una sola ejecucion, la que NO ha '
            'llegado a ningun test es la PRIMERA — la segunda ha sido la que '
            'ha ido seguida del unico test que se ha corrido—, y no la '
            'unica pendiente: %r' % (pendientes,))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_una_ejecucion_sobre_un_4_no_absuelve():
    """Y el caso que hizo falta el registro en vez de la marca.

    Un `correr` cuyo codigo es 4 —«no se ha ejecutado nada»— LANZA, y por
    tanto no registra. O sea que no absuelve: que es lo unico razonable,
    porque un 4 no ha probado nada.

    Y esto es lo que hacia la version de marca por directorio incorrecta en
    el otro sentido tambien: si hubiera registrado antes del corte, un `!= 0`
    cualquiera —incluido un 4— habria vaciado la lista y habria dicho
    «probado» sin haber probado."""
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix='opencode_cuatro_')
    try:
        destino = os.path.join(tmp, 'DOCS')
        shutil.copytree(os.path.join(ROOT, 'DOCS'), destino)
        ep.escribir_documento(os.path.join(destino, 'A.md'), 'a',
                              que='LA MUTACION')
        with pytest.raises(AssertionError):
            ep.correr(FICH, 'este_test_no_existe', cwd=ROOT)
        pendientes = [q for q, _ in ep.sin_probar()]
        assert pendientes == ['LA MUTACION'], (
            'un test que no llego a ejecutarse NO puede absolver una '
            'escritura. Y la absuelve: %r' % (pendientes,))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
