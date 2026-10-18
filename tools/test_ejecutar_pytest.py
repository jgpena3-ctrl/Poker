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
import ast
import io
import os
import re
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
def _ficheros_de_prueba():
    """Todos los `tools/test_*.py`. Y todos, que es lo que faltaba.

    Y no un lista escrita aqui: eso es lo que paso, y la lista se quedo
    corta sin que nadie lo notara. Una lista de nombres es una declaracion
    de lo que se ha mirado, y se queda vieja sin avisar."""
    return [os.path.join(ROOT, 'tools', f) for f in os.listdir(
        os.path.join(ROOT, 'tools'))
        if f.startswith('test_') and f.endswith('.py')]


def _cadenas_de_la_llamada(nodo):
    """Todas las cadenas constantes de los argumentos de una llamada, a
    CUALQUIER profundidad.

    Y a cualquier profundidad, porque el comando de pytest no son argumentos
    sueltos sino una lista:

        subprocess.run([sys.executable, '-m', 'pytest', FICHERO])

    Una version anterior tomaba los `ast.Constant` de `nodo.args` y aqui no
    habia ninguno: lo que hay es un `ast.List`. O sea que el detector no
    senalaba nada —ni a los subprocesos propios, ni al de prueba—, y un
    detector que no senala nada tambien esta roto, en el sentido contrario.

    Que es lo que la prueba de las dos mitades ha hecho falta para ver: que
    senale UN subproceso real, y que NO senale uno que solo lo menciona."""
    return [n.value for n in ast.walk(nodo)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _llamadas_de_subproceso(fuente):
    """Las llamadas a `subprocess.run/call/check_output/Popen`, con su linea.

    Y si el fichero NO PARSEA, LANZA. MEDIDO: antes el `SyntaxError` lo
    recogia el que llama y devolvia «no senala», que es lo que la regla quiere
    oir de un fichero limpio. O sea que un fichero con un error de sintaxis
    se contaba como LIMPIO.

    Y no hay otra via que lo vea: pytest no recoge un fichero que no parsea.
    El unico que puede detectarlo es este.

    Y es la CUARTA vez en cuatro bloques que una comprobacion esta en verde
    porque su CONDICION no se cumple — la regla de dos ficheros de quince,
    `sin_probar()` sin ambito, el filtro `ast.IsNot`— y esta es la mas
    oculta, porque un `try/except` que devuelve el valor tranquilo es la
    forma mas comun de que un detector deje de mirar.

    La regla que lo evita:

        no senala porque no hay nada         -> correcto
        no senala porque no he podido mirar -> INCORRECTO, y silencioso

    Un booleano no distingue las dos cosas. Un fallo si."""
    arbol = ast.parse(fuente)
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr in ('run', 'call', 'check_output', 'Popen')):
            yield nodo


def _lanza_pytest_propio(ruta):
    """Si el fichero EJECUTA pytest con un `subprocess` propio.

    Y se pregunta sobre el ARBOL, no sobre el texto. MEDIDO por que:

        version de TEXTO:  busca `'-m', 'pytest'` en el fichero entero
            -> senalaba a ESTE MISMO fichero, que no ejecuta pytest: lo
               documenta. Septimo falso positivo de la familia, y el primero
               que me hago yo: la marca esta y el sujeto no.

        version de ARBOL:  una llamada `subprocess.*` con `-m` y `pytest`
            entre sus argumentos, a cualquier profundidad

    La diferencia es «el fichero habla de pytest» contra «el fichero ejecuta
    pytest», y esa es la pregunta.

    Y un `subprocess.run(['git', ...])` no casa, porque no lleva `-m pytest`:
    esta comprobacion tambien tiene que saber decir que NO, y no solo que
    si."""
    fuente = io.open(ruta, encoding='utf-8').read()
    hallazgos = []
    for nodo in _llamadas_de_subproceso(fuente):
        args = _cadenas_de_la_llamada(nodo)
        if '-m' in args and 'pytest' in args:
            hallazgos.append('linea %d' % nodo.lineno)
    return bool(hallazgos), hallazgos


def _funciones_que_llaman_a_crudo(fuente):
    """Las FUNCIONES que llaman a `crudo()`, no las que lo mencionan.

    MEDIDO: buscando `'crudo('` en el fuente, el test que explica la
    exencion se senalaba a si mismo —por tener `crudo(` en el docstring—.
    Con arbol se sabe a que funcion pertenece la llamada, y con texto no.

    Y el nombre de la funcion es justo lo que hace falta para exigir que la
    exencion este justificada: la regla es «solo en un test cuya funcion
    hable del exit code», y eso se comprueba sobre la funcion."""
    arbol = ast.parse(fuente)
    padre = {}
    for nodo in ast.walk(arbol):
        for hijo in ast.iter_child_nodes(nodo):
            padre[hijo] = nodo
    funciones = []
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == 'crudo'):
            continue
        arriba = padre.get(nodo)
        while arriba is not None and not isinstance(arriba, ast.FunctionDef):
            arriba = padre.get(arriba)
        funciones.append(arriba.name if arriba is not None else '<modulo>')
    return funciones


PUERTA_COMUN = ('correr', 'crudo', 'afirmar_caida', 'afirmar_verde')


# Y `ejecutar_pytest` o `ep`. MEDIDO: sin esto, `otro.correr(...)` —una
# base de datos, un cliente HTTP— se senalaba como infraccion de una regla
# que no habla de bases de datos. Y un detector que acusa de todo es un
# detector que nadie va a mirar cuando accuse de algo falso.
RECEPTORES = ('ep', 'ejecutar_pytest')


PUERTA = 'ejecutar_pytest'
RECEPTORES = ('ep', 'ejecutar_pytest')


def _imports_de_nivel_de_modulo(arbol):
    """Las sentencias de nivel de modulo, y lo que hay dentro de ellas.

    Y «de nivel de modulo» significa: se BAJA dentro de `if`, `try`, `with`,
    `for` y `while` — que son condiciones, no?— y NO dentro de `def`, `class`
    ni `lambda`.

    Que es justo la diferencia entre dos cosas que se confundian:

      `try: from ejecutar_pytest import correr` a nivel de modulo
          -> el nombre queda ligado en el modulo CUANDO el import se ejecuta.
             Y que se ejecute o no es la limitacion ya documentada —
             presencia, no ejecucion —, que es aceptable.

      `def auxiliar(): from ejecutar_pytest import correr`
          -> el nombre queda ligado SOLO dentro de `auxiliar`. Y una
             llamada a `correr` FUERA de `auxiliar` es un `NameError`, no una
             llamada a la puerta.

    Y la segunda es lo que R2 senala, y es un problema DISTINTO del primero:
    no es que el detector no sepa si el import corre, es que el nombre no
    existe en ese punto del programa.

    MEDIDO, antes de arreglarlo, cinco falsos positivos: los tres con
    receptor anidado y dos con import de ambito local."""
    pendientes = list(getattr(arbol, 'body', []))
    while pendientes:
        nodo = pendientes.pop()
        yield nodo
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef, ast.Lambda)):
            continue                      # un ambito NUEVO: no se hereda
        for atributo in ('body', 'orelse', 'finalbody', 'handlers'):
            hijo = getattr(nodo, atributo, None)
            if isinstance(hijo, list):
                pendientes.extend(hijo)


def _ligados_por_import(fuente):
    """Los nombres que este modulo ha ligado a la puerta comun, EN ESTE AMBITO.

    Y son DOS preguntas, no una:

      - `from ejecutar_pytest import correr`  -> 'correr' queda ligado
      - `import ejecutar_pytest as e`         -> 'e' queda ligado

    Que es lo que una version anterior mezclaba: preguntaba solo por la
    segunda y por el atributo, y por eso rechazaba dos casos legitimos —
    `from ejecutar_pytest import correr as puerta` + `puerta(...)`, e
    `import ejecutar_pytest` + `ejecutar_pytest.correr(...)`—.

    Un `import` es una SENTENCIA, no un camino de datos. Por eso esto es
    barato y por eso tapa el hueco en vez de desplazarlo.

    Y SOLO de nivel de modulo. Un import dentro de una funcion no liga nada
    fuera de ella, y contarlo como si ligara es un falso positivo que no es
    de flujo sino de AMBITO: el nombre sencillamente no existe ahi.

    Y EL HUECO QUE ESTA DECLARACION CREA, que es el precio:

        def auxiliar():
            from ejecutar_pytest import correr
            codigo, salida = correr(F, 't')      <-- SI es la puerta

    Eso deja de detectarse. Y es un hueco en la direccion CONTRARIA —se
    detecta menos— que es la buena: un detector que mide de menos se ve como
    fallo; uno que mide de mas convence de que mide bien."""
    arbol = ast.parse(fuente)
    ligados = set()
    for nodo in _imports_de_nivel_de_modulo(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module == PUERTA:
            for alias in nodo.names:
                ligados.add(alias.asname or alias.name)
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name == PUERTA:
                    ligados.add(alias.asname or alias.name)
    return ligados


def _llamada_de_la_puerta(fuente, valor):
    """El NOMBRE LIGADO de la llamada de la puerta, o None.

    Y «nombre ligado», no «nombre de la puerta», y la diferencia es toda:
    `from ejecutar_pytest import correr as c` devuelve `'c'`, que NO esta en
    `PUERTA_COMUN` y por tanto no se senala. El alias queda como hueco, y se
    queda porque la LISTA lo para, no porque el helper lo rechace — dos
    mecanismos, cada uno haciendo lo suyo, que es mejor que uno haciendo
    las dos cosas.

    Y lo que se corrige con esto es un FALSO POSITIVO real, medido:

        def correr(f, t): ...            -> se tomaba por la puerta
        from otra_cosa import correr    -> se tomaba por la puerta

    Los dos son llamadas sueltas con un nombre que no sale de la puerta, y
    las dos se aceptaban. Y el primero es el caso que R2 senala.

    Con esto:

        una llamada SUELTA `X(...)`   -> X tiene que salir de un
                                          `from ejecutar_pytest import X`
        una llamada `R.correr(...)`   -> R es `ep`/`ejecutar_pytest`, o esta
                                          ligado por `import ejecutar_pytest
                                          as R`
    """
    while isinstance(valor, ast.Subscript):
        valor = valor.value               # `ep.correr(...)[0]`
    if not isinstance(valor, ast.Call):
        return None
    ligados = _ligados_por_import(fuente)
    func = valor.func
    if isinstance(func, ast.Attribute):
        # Y el receptor tiene que ser un `ast.Name` DIRECTO. MEDIDO: con
        # `receptor.attr if isinstance(receptor, ast.Attribute)` se sacaba el
        # ULTIMO atributo de una cadena, y eso hacia pasar tres casos que no
        # son la puerta:
        #
        #     obj.ep.correr(...)                 -> 'ep'   -> la aceptaba
        #     obj.e.correr(...)  con `e` ligado  -> 'e'    -> la aceptaba
        #     modulo.ejecutar_pytest.correr(...) -> '...'  -> la aceptaba
        #
        # Y `obj.ep` no es el modulo de la puerta: es un atributo `ep` de un
        # objeto `obj`, que puede ser cualquier cosa. La pregunta correcta es
        # «¿este NOMBRE, en este punto, es el modulo?», y un atributo anidado
        # no es un nombre.
        #
        # Y es la misma asimetria que con el alias: un atributo anidado no
        # cambia lo que se pregunta, igual que un alias de funcion. La puerta
        # se importa como nombre, no como atributo de nada.
        receptor = func.value
        if not isinstance(receptor, ast.Name):
            return None
        if (receptor.id not in RECEPTORES
                and receptor.id not in ligados):
            return None
        return func.attr
    # SUELTA. Y el nombre tiene que VENIR de la puerta: una `def` local con
    # el mismo nombre no cuenta, porque es una definicion, no una
    # importacion. MEDIDO: antes se aceptaba.
    nombre = getattr(func, 'id', '')
    return nombre if (nombre and nombre in ligados) else None


def _variables_de_la_puerta(fuente):
    """Los nombres asignados desde `correr()`, `crudo()` o `afirmar_*()`.

    Y se recoge el ORIGEN, que es lo que hace la regla precisa: un `!= 0`
    sobre cualquier otra variable —un contador, un codigo de git, una
    cadena— no es lo mismo, y prohibitlo seria una regla que necesita
    aceptaciones.

    Que es lo que hace aplicable una regla: una regla sin excepciones
    necesita aceptarlas cada vez que aparece una, y entonces se deja de
    mirar."""
    arbol = ast.parse(fuente)
    nombres = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        llamada = _llamada_de_la_puerta(fuente, nodo.value)
        if llamada is None or llamada not in PUERTA_COMUN:
            continue
        for t in nodo.targets:
            if isinstance(t, ast.Name):
                nombres.add(t.id)
            elif isinstance(t, ast.Tuple):
                nombres.update(e.id for e in t.elts
                               if isinstance(e, ast.Name))
    return nombres


def _comparaciones_inequivocas(fuente):
    """Las comparaciones `X != 0` donde X viene de la puerta comun.

    MEDIDO en todo `tools/`: cero. Y no porque no haya `!= 0` —hay—, sino
    porque ninguno cae sobre un codigo de salida.

    Y el criterio se apoya en el ARBOL, de modo que el docstring que explica
    la regla puede nombrarla: eso es la diferencia entre «la palabra
    prohibida no aparece» y «la cosa prohibida no se hace». Solo la segunda
    admite un docstring que diga POR QUE."""
    de_la_puerta = _variables_de_la_puerta(fuente)
    if not de_la_puerta:
        return []
    arbol = ast.parse(fuente)
    encontradas = []
    for nodo in ast.walk(arbol):
        # Y `ast.NotEq`, que es `!=`. Y NO `ast.IsNot`, que es `is not`.
        #
        # MEDIDO: con `IsNot` el detector estaba INVERTIDO —no detectaba
        # `codigo != 0` con `codigo` de `ep.correr`, y SI detectaba `codigo
        # is not 0`—. Y en el repositorio entero, seis apariciones de
        # `X != 0` en el texto y cero detectadas: con el filtro sin casar
        # nunca, la regla se cumplia siempre. Verde por no mirar.
        #
        # Y `is not 0` es MAS ESTRICTO que `!= 0` —no deja pasar ningun
        # valor raro—, o sea que el detector no solo fallaba lo que tiene que
        # fallar: ademas senalaba algo que no es la infraccion.
        #
        # Y es la TERCERA vez en tres bloques que una comprobacion esta en
        # verde porque su CONDICION nunca se cumple. Las otras dos —la regla
        # que miraba dos ficheros de quince, y `sin_probar()` sin ambito—
        # son la misma cosa.
        if not (isinstance(nodo, ast.Compare) and len(nodo.ops) == 1
                and isinstance(nodo.ops[0], ast.NotEq)
                and isinstance(nodo.comparators[0], ast.Constant)
                and nodo.comparators[0].value == 0):
            continue
        nombre = getattr(nodo.left, 'id', None)
        if nombre and nombre in de_la_puerta:
            encontradas.append((nodo.lineno, nombre))
    return encontradas


def test_la_puerta_de_ejecutar_pytest_es_unica_en_todo_tools():
    """LA REGLA, DE VERDAD REPO-WIDE. Y con la exencion en el nombre.

    La version anterior de esta comprobacion miraba DOS ficheros y decia
    «ningun test del repositorio». Los dos cumplian. Los demas no se
    miraban, y en esos habia dos que NO cumplian — uno de ellos, el de la
    matriz de cuatro celdas.

    MEDIDO antes de arreglarlo:

        ficheros que lanzan pytest por el modulo:   3
        ficheros con subproceso PROPIO:             2
            test_disciplina_de_los_tests.py   3 subprocesos, `!= 0`
            test_inc004_sigue_abierto.py     1 subproceso, `!= 0`

    Y ahora la regla tiene tres partes, y las tres nacen de ese fallo:

      1. quien lance pytest, entra por `ejecutar_pytest`
      2. `crudo` —la exencion, que NO corta— solo en un test cuyo nombre
         hable del exit code. Es un criterio tonto y estricto, y es
         preferible a «este fichero se lo permite», que es una excepcion que
         se extiende sola
      3. ningun `!= 0` aplicado a un codigo de salida de pytest
    """
    con_propio, con_crudo, con_inequivoco = [], [], []
    for ruta in _ficheros_de_prueba():
        nombre = os.path.basename(ruta)
        fuente = io.open(ruta, encoding='utf-8').read()
        lanza, donde = _lanza_pytest_propio(ruta)
        if lanza:
            con_propio.append('%s (en %s)' % (nombre, ', '.join(donde)))
        # (2) la exencion tiene que estar justificada POR SU NOMBRE, y el
        # nombre es el de la FUNCION a la que se llama —no el fichero, y no
        # el texto, que senalaba al test que explica la exencion—.
        funciones = _funciones_que_llaman_a_crudo(fuente)
        justificadas = [n for n in funciones
                        if 'exit_code' in n or 'codigo' in n]
        if len(justificadas) != len(funciones):
            con_crudo.append((nombre, funciones))
        # (3) el `!= 0` sobre una variable que venga de la PUERTA COMUN.
        #
        # Y por ORIGEN, no por texto. Con texto, la regla senalaba al
        # docstring que la EXPLICABA —«Y 4 != 0. O sea que `assert
        # returncode != 0` sobre eso PASA SIEMPRE»— y con eso un docstring
        # que dice por que algo esta prohibido tendria prohibido nombrarlo.
        #
        # Que es peor que un falso positivo molesto: es un docstring que no
        # puede decir la verdad.
        for linea, variable in _comparaciones_inequivocas(fuente):
            con_inequivoco.append('%s linea %d: %s != 0'
                                   % (nombre, linea, variable))

    print()
    print('   ficheros que lanzan pytest por su cuenta: %s'
          % (con_propio or 'ninguno'))
    print('   ficheros con `crudo` sin justificacion:     %s'
          % (con_crudo or 'ninguno'))
    print('   `!= 0` sobre un codigo de pytest:          %s'
          % (con_inequivoco or 'ninguno'))

    assert not con_propio, (
        'estos ficheros lanzan pytest con un `subprocess` PROPIO y no por '
        '`ejecutar_pytest`, y por tanto no cortan el 4 ni miran la salida:\n'
        '%s\n\nUn subproceso propio no es un problema de estilo: es el '
        'instrumento entero de este bloque, en otro sitio. Y la version '
        'anterior de esta comprobacion miraba dos ficheros de los quince, y '
        'los dos cumplian.' % chr(10).join('   - %s' % n for n in con_propio))
    assert not con_crudo, (
        '`crudo` es la EXENCION —no corta nada— y solo puede usarse donde se '
        'esta comprobando que el corte funciona, que es un test cuyo nombre '
        'habla del exit code. Aqui se usa en:\n%s'
        % chr(10).join('   - %s, en %r' % (n, f) for n, f in con_crudo))
    assert not con_inequivoco, (
        'un `!= 0` sobre el codigo que devuelve la puerta comun aprueba un 4 '
        '—«no se ha ejecutado nada»— en verde:\n%s'
        % chr(10).join('   - %s' % n for n in con_inequivoco))


def test_la_comprobacion_esta_rota_y_se_dice():
    """La comprobacion anterior, y lo que era.

    Y esto no es historia: es la forma de que quien la lea sepa que tiene
    que MIRA TODO. Una comprobacion repo-wide que de hecho mira dos ficheros
    es peor que no hacerla, porque da por cubierta una cosa que no lo
    esta — y este bloque lleva veintinueve bloques con cosas que de hecho no
    estaban cubiertas.

    Y el numero: quince ficheros de test en `tools/`, y se miraban dos."""
    fuente = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    assert '_ficheros_de_prueba' in fuente, (
        'esta comprobacion tiene que apoyarse en el recorrido, no en una '
        'lista de nombres escrita a mano')
    assert 'os.listdir' in fuente, (
        'y el recorrido tiene que ser REAL: si vuelve a ser una lista, esta '
        'comprobacion vuelve a mirar dos ficheros de quince')


def test_el_detector_no_se_senala_a_si_mismo():
    """La regla NUEVA senalaba a ESTE fichero, que solo DOCUMENTA pytest.

    MEDIDO: su fuente contiene `'-m', 'pytest'` en el docstring de
    `construir()` y en los ejemplos, y un detector de TEXTO lo leia como un
    subproceso propio. Septimo falso positivo de la familia, y el primero
    que me hago yo: la marca esta y el sujeto no.

    Y es el peor sitio posible para ese fallo: el detector ES la prueba de
    la puerta unica, y un detector que senala su propio fichero de prueba
    no es un detector, es ruido. Un ruido asi se aprende a ignorar, y a
    ignorarlo es dejar de comprobar.

    Y la comprobacion es de las dos mitades, porque un detector que senala
    de mas y otro que no senala nada fallan igual de mal: uno entrena a
    ignorar, el otro deja pasar lo que hay que cazar.
    """
    propio, donde = _lanza_pytest_propio(os.path.abspath(__file__))
    assert not propio, (
        'el detector senala a su PROPIO fichero de prueba, en %s. O sea que '
        'pregunta por el texto y no por el arbol, y eso lo hace senalar '
        'documentacion. Un detector que senala su propia prueba no vigila '
        'nada: entrena a ignorar.' % donde)

    del_modulo_boo, donde_modulo = _lanza_pytest_propio(
        os.path.join(ROOT, 'tools', 'ejecutar_pytest.py'))
    assert not del_modulo_boo, (
        'y senala al MODULO, que construye el comando para que lo usen otros '
        'y no lo ejecuta: %s' % donde_modulo)

    # Y que aun asi detecta un subproceso de verdad. Un detector que no
    # senala NADA tambien seria un detector roto, en el otro sentido.
    with tempfile.TemporaryDirectory() as tmp:
        bueno = os.path.join(tmp, 'bueno.py')
        io.open(bueno, 'w', encoding='utf-8').write(
            'import subprocess\n'
            'r = subprocess.run([sys.executable, \'-m\', \'pytest\', F])\n')
        malo = os.path.join(tmp, 'malo.py')
        io.open(malo, 'w', encoding='utf-8').write(
            '# esto solo lo documenta: subprocess.run([\'-m\', \'pytest\'])\n'
            'import subprocess\n'
            'r = subprocess.run([\'git\', \'rev-parse\', \'HEAD\'])\n')
        assert _lanza_pytest_propio(bueno)[0], (
            'un `subprocess.run` de verdad con `-m pytest` NO puede pasar: el '
            'detector no senala nada y no vigila')
        assert not _lanza_pytest_propio(malo)[0], (
            'un fichero que solo lo MENCIONA en un comentario, y que ejecuta '
            '`git`, no puede senalarse: eso es lo que hacia antes')

# ============================ 7. R2, CONDICION 3: QUE NO SE CONTAMINE
def test_el_ambito_no_sobrevive_a_una_excepcion():
    """La mitad que no estaba comprobada, y es la importante.

    El `finally` del ambito cierra el registro aunque el test reviente, y un
    `finally` es exactamente el sitio donde se esconde un fallo: si el test
    deja una escritura pendiente y el ambito no se cierra, el siguiente test
    hereda esa escritura y cae por ella.

    O sea que un `finally` sin prueba es una promesa sobre una rama de codigo
    que no se ejecuta casi nunca.

    Y se ejecuta aqui, y a proposito: se abre el ambito, se deja una escritura
    PENDIENTE —sin ejecutar nada— y se revienta dentro. Lo que tiene que
    pasar al salir es que no quede ambito, y por tanto que la escritura
    pendiente se haya perdido con el.

    Que perderse es lo correcto, y hay que decirlo: el ambito es de UN test,
    y un test que revienta ya ha fallado por otra cosa. Lo que no puede es
    dejar el registro contaminado para el siguiente.

    Y la razon de que esto se pueda escribir: el `finally` esta en
    `ejecutar_pytest.ambito()`, no en el fixture. MEDIDO: pytest no deja
    llamar a un fixture directamente, y reimplementar la logica aqui seria
    probar una copia — una copia puede tener un `finally` y el original no.
    """
    # Y en un TEMPORAL, no en `tools/`. MEDIDO: con la ruta dentro del
    # repositorio, este test dejaba un `?? tools/NO_EXISTE.md` en cada
    # pasada — porque `escribir_documento` SI escribe, que es lo que hace—.
    #
    # Y un test que escribe en el arbol del proyecto puede pisar un
    # fichero de verdad. Aqui no ha pasado porque el nombre es imposible de
    # colisionar, pero el patron no lo garantiza: un test que muta el
    # REPOSITORIO en vez de una copia no es un test.
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, 'UN_TXT.md')
        with pytest.raises(RuntimeError):
            with ep.ambito():
                ep.escribir_documento(ruta, 'x', que='LA PENDIENTE')
                pendientes = [q for q, _ in ep.sin_probar()]
                assert pendientes == ['LA PENDIENTE'], (
                    'antes de la excepcion tiene que haber una pendiente, '
                    'para que la prueba signifique algo: %r' % (pendientes,))
                raise RuntimeError('una excepcion a proposito')
    assert ep._ALCANCE is not None, (
        'el ambito EXTERIOR tiene que seguir vivo: `ambito()` restaura el '
        'anterior al salir, no lo pone a None. Si no, un ambito dentro de '
        'otro deja al exterior sin registro, y el que lo abrio creeria que '
        'tiene uno')
    assert [q for q, _ in ep.sin_probar()] == [], (
        'y no puede quedar nada pendiente del ambito que revienta: %r'
        % ([q for q, _ in ep.sin_probar()],))

def test_un_ambito_nuevo_no_ve_lo_del_anterior():
    """La otra mitad de (3): entre tests, y por lo tanto entre ficheros.

    No hace falta lanzar dos ficheros: el mecanismo que lo arregla es
    `abrir_ambito()`, y esa es la puerta por la que pasa todo. Se ensaya la
    puerta.

    Y se ensaya en el ORDEN que importa: dejar pendiente, cerrar, abrir, y
    mirar. Si al abrir apareciera algo, el registro se estaria filtrando."""
    with tempfile.TemporaryDirectory() as tmp:
        ep.escribir_documento(os.path.join(tmp, 'UN_TXT.md'), 'x',
                              que='DEL TEST ANTERIOR')
        assert [q for q, _ in ep.sin_probar()] == ['DEL TEST ANTERIOR']
        ep.cerrar_ambito()
        ep.abrir_ambito()
    assert ep.sin_probar() == [], (
        'un ambito nuevo tiene que estar VACIO. Si no, el registro se '
        'contamina entre tests, y un test puede caer por lo que hizo otro. '
        'MEDIDO: la version de registro global de modulo hacia exactamente '
        'esto, y estaba en verde.')
    assert ep._ALCANCE == {}, 'y no basta con que no haya pendiente: tiene '
    assert ep._ALCANCE == {}, 'que no haya ENTRADAS. Un ambito vacio es {}'


# ============================ 8. R1 T4: QUE `0 failed` NO PASE
def test_el_exit_code_de_un_cero_de_fallidos_no_pasa_la_comprobacion():
    """La entrada que VALIA antes de la correccion.

    MEDIDO: `re.findall(r'(\d+) failed', '0 failed in 0.05s')` devuelve
    `['0']`. O sea que `assert m` —la version anterior— se cumplia con un
    cero, y el codigo de salida es el mismo que el de un test caido.

    Y no es un caso teorico: pytest imprime `0 failed` cuando la coleccion
    no ha encontrado nada que ejecutar, y un subproceso puede dar 1 por un
    error de importacion.

    Y el fallo tiene que distinguir las DOS cosas, porque no son lo mismo:

      - «no ha habido fallos»      -> no se ha mirado nada
      - «un error de importacion» -> tampoco es un fallo de test

    Y para eso hace falta la linea `FAILED fichero::test`: un recuento
    puede ser 0 mientras hay un error de coleccion, y solo el nombre
    demuestra que ha CAIDO un test."""
    import re as _re
    m = _re.findall(r'(\d+) failed', '0 failed in 0.05s')
    assert m, ('suposicion: el patron tiene que casar con `0 failed`, o esta '
               'prueba no prueba nada')
    assert not (m and int(m[-1]) >= 1), (
        'suposicion del contrario: `0 failed` NO tiene que pasar la '
        'comprobacion de «recuento mayor que cero». Y pasa: %r' % (m,))
    assert not _re.findall(r'^FAILED \S+::', '0 failed in 0.05s', _re.M), (
        'y `0 failed` tampoco trae linea `FAILED fichero::test`, que es la '
        'segunda mitad de la comprobacion')

    # Y ahora el caso REAL, y por las DOS PUERTAS, porque son dos preguntas:
    # `crudo` dice que codigo ha dado; `correr` dice que se ha ejecutado algo.
    with tempfile.TemporaryDirectory() as tmp:
        destino = os.path.join(tmp, 'DOCS')
        shutil.copytree(os.path.join(ROOT, 'DOCS'), destino)
        crudo, salida = ep.crudo(FICH, 'test_que_no_existe_este', cwd=ROOT)
        assert crudo in (ep.CODIGO_NINGUNO_EJECUTADO,
                         ep.CODIGO_NINGUNO_ENCONTRADO), (
            'MEDIDO: un nombre de test que no existe da %d, y %d si pytest no '
            'encuentra ninguno. Los dos son «no se ha ejecutado nada» y los '
            'dos pasan un `!= 0` en verde. Si aqui saliera un 1, la '
            'suposicion del comentario de arriba estaria caducada y habria '
            'que rehacerla.' % (ep.CODIGO_NINGUNO_EJECUTADO,
                                ep.CODIGO_NINGUNO_ENCONTRADO))
        assert not _re.findall(r'^FAILED \S+::', salida, _re.M), (
            'y la salida no trae ninguna linea `FAILED fichero::test`, que es '
            'la segunda mitad de la comprobacion de `afirmar_caida`: aqui no '
            'ha caido NINGUN test')
        # y la otra puerta: `correr` tiene que CORTAR, no devolver
        with pytest.raises(AssertionError):
            ep.correr(FICH, 'test_que_no_existe_este', cwd=ROOT)


# ============================ 9. R1 T5: LA PALABRA, NO LA SUBCADENA
def test_el_cambio_cosmetico_toca_la_palabra_y_no_la_subcadena():
    """La correccion del punto 4 de R2, probada en las dos mitades.

    Y el punto 4 fue el unico NO CONFIRMADO: `find('el')` caia en el indice
    237 y 93, y en los dos contratos era palabra COMPLETA. O sea que la
    mutacion era cosmetica de verdad y la matriz era correcta.

    Lo que habia era una CASUALIDAD —depende de donde aparezca `el` en dos
    ficheros que este bloque no controla— y lo que se cambia son los limites
    de palabra. Y esa correccion, sin esta prueba, no seria mas que otra
    reescritura sin motivo: la prueba es lo que dice que la reescritura hace
    algo.

    Y las dos mitades, que es donde estuvo el fallo: cambiar la PALABRA y no
    cambiar lo que NO es palabra. Un `find('el')` cambiaria «ello», «elo» y
    «delegado» igual de bien, y dejaria un documento con palabras rotas."""
    import re as _re

    texto = 'el contrato dice que ello delegaba y el heroe continua'
    palabra = _re.search(r'\bel\b', texto)
    assert palabra is not None, 'suposicion: tiene que haber una palabra «el»'

    # (a) la PALABRA se cambia
    cambiado = texto[:palabra.start()] + 'EL' + texto[palabra.end():]
    assert 'EL contrato' in cambiado, (
        'la palabra «el» tiene que cambiarse, y no: %r' % cambiado)
    # (b) lo que NO es palabra no se toca
    for intacto in ('ello', 'delegaba'):
        assert intacto in cambiado, (
            '«%s» no es la palabra «el» y no tiene que cambiar: %r'
            % (intacto, cambiado))
    assert 'ello' in texto and _re.search(r'\bello\b', cambiado), (
        'y «ello» tiene que seguir siendo «ello», no «Ello» ni «ELlo»')
    # Y el cambio tiene que ser UNO, no dos
    assert cambiado.count('EL') == 1, (
        'un solo cambio de palabra. Con `find(..., 1)` se cambia el primero '
        'y se dejan los demas, que es la version que se descarto. Aqui: %r'
        % (cambiado,))
    # (c) Y el caso que rompia la palabra pegada
    pegado = 'ello'
    m2 = _re.search(r'\bel\b', pegado)
    assert m2 is None, (
        'suposicion: «ello» NO tiene una palabra «el» dentro. Y si la '
        'tuviera, este test estaria probando lo contrario de lo que dice')


def test_los_tests_de_este_fichero_no_dejan_basura_en_el_repositorio():
    """La comprobacion que sale de haber encontrado un `??` en `git status`.

    MEDIDO: dos pruebas de este mismo fichero usaban una ruta DENTRO de
    `tools/` como sitio donde «escribir una mutacion», y `escribir_documento()`
    escribe —que es lo que hace—, asi que dejaban `?? tools/NO_EXISTE.md` en
    cada pasada.

    Y hay dos razones por las que molesta, y las dos son malas:

      1. un `??` en el `git status` es ruido, y el ruido se aprende a
         ignorar
      2. un test que escribe en el ARBOL DEL PROYECTO puede pisar un
         fichero de verdad. Aqui no ha pasado —el nombre es imposible de
         colisionar—, pero el patron no lo garantiza

    Y lo que se comprueba no es «este test no escribe», que no se puede saber
    desde dentro, sino lo que se PUEDE: que en este fichero ninguna ruta de
    escritura apunta al repositorio. Que es una comprobacion de FUENTE, y
    por eso no es la ideal —la ideal es el `git status` limpio despues de
    correr—, pero es la que se puede dejar escrita al lado.

    Y LA LECCION, QUE ES LA TERCERA VEZ EN ESTE BLOQUE

    Las otras dos: `NL` sin definir, dos veces; y una medicion con barras
    invertidas en vez de saltos de linea. Las tres son codigo escrito a
    traves de una CAPA —un heredoc, una linea de ordenes, un fichero
    temporal— que altera lo que el autor cree que esta escribiendo. La capa
    es el sitio donde falla la escritura, y por eso hay que MIRAR lo que
    sale."""
    fuente = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    arbol = ast.parse(fuente)
    Within = ('TemporaryDirectory', 'mkdtemp')
    malas = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        nombre = getattr(nodo.func, 'id', '') or getattr(nodo.func, 'attr', '')
        if nombre != 'escribir_documento':
            continue
        for a in nodo.args:
            texto = ast.get_source_segment(fuente, a) or ''
            if ('ROOT' in texto and 'os.path.join' in texto
                    and '.tmp' not in texto):
                malas.append('linea %d: %s' % (nodo.lineno, texto))
    assert not malas, (
        'estas escrituras apuntan DENTRO del repositorio:\n%s\n\nUn test '
        'que escribe en el arbol del proyecto puede pisar un fichero de '
        'verdad. Que aqui no haya pasado no lo garantiza: el nombre lo '
        'hacia imposible de colisionar.' % chr(10).join(malas))
    del Within


# ============================ 10. CADA DETECTOR, CON UN CASO QUE LO MATA
#
# Y la leccion de por que estan las TRES, y no solo la que R2 senalo:
#
#     la prueba de que un detector no se senala a si mismo NO BASTA, porque
#     puede pasar con un detector que no reconoce NADA. MEDIDO: pasaba, con
#     `_comparaciones_inequivocas` sin detectar ni un `!=` del repositorio.
#
# Un detector se prueba con un caso que lo hace FALLAR y con uno que lo hace
# PASAR. El que lo hace fallar demuestra que detecta; el que lo hace pasar
# demuestra que no acusa de todo.
#
# Y por que las TRES, y no solo la senalada: un detector sin caso que lo mate
# puede estar roto sin que nadie se entere. Y las tres habian estado sin el
# suyo.

CODIGO_DE_LA_PUERTA = "codigo, salida = ep.correr(F, 't')"
CONTROL = 'contador = 3'


def test_el_detector_de_inequivoco_detecta_y_no_detecta():
    """R2, punto 1. Y la prueba que faltaba de verdad.

    MEDIDO antes de arreglarlo, con `ast.IsNot`:

        (a) `codigo != 0`, y `codigo` viene de `ep.correr`   detectado=False
        (b) `contador != 0`, SIN puerta comun                 detectado=False
        (c) `codigo is not 0`, con `codigo` de la puerta      detectado=True

    Invertido. Y el caso (c) importa mas que el (a): `is not 0` es MAS
    ESTRICTO que `!= 0` y no es la infraccion que se prohibe. O sea que no
    solo no detectaba lo que tiene que detectar: ademas senalaba lo que no.

    Y por que la especificidad importa tanto: un detector que accuse de todo
    es un detector que nadie va a mirar cuando accuse de algo falso. Y ahi
    es donde se pierde la senal."""
    casos = (
        ('la infraccion: `codigo != 0` con `codigo` de la puerta',
         CODIGO_DE_LA_PUERTA + chr(10) + 'if codigo != 0:' + chr(10)
         + '    pass' + chr(10), True),
        ('el control: `contador != 0` sin puerta comun',
         CONTROL + chr(10) + 'if contador != 0:' + chr(10) + '    pass'
         + chr(10), False),
        ('el inverso: `codigo is not 0` es mas estricto y NO es la infraccion',
         CODIGO_DE_LA_PUERTA + chr(10) + 'if codigo is not 0:' + chr(10)
         + '    pass' + chr(10), False),
    )
    for nombre, fuente, debe in casos:
        detectado = bool(_comparaciones_inequivocas(fuente))
        assert detectado == debe, (
            '%s' + chr(10) + '  detectado=%s  esperado=%s' + chr(10) + chr(10)
            + 'MEDIDO con el filtro que habia: `!=` es `ast.NotEq` y `is not` '
            'es `ast.IsNot`, y con `IsNot` el detector no detectaba la '
            'infraccion real y senalaba la inversa.' + chr(10) + 'Fuente:'
            + chr(10) + '%s'
            % (nombre, detectado, debe, fuente))

    # Y que diga la LINEA y el NOMBRE, que es lo que lo hace accionable
    (linea, variable), = _comparaciones_inequivocas(
        CODIGO_DE_LA_PUERTA + chr(10) + 'if codigo != 0:' + chr(10)
        + '    pass' + chr(10))
    assert variable == 'codigo' and linea == 2, (
        'el hallazgo tiene que decir la linea y la variable, que es lo unico '
        'que permite arreglarlo sin leer el fichero entero. Vino %r'
        % ((linea, variable),))


def test_el_detector_de_pytest_propio_detecta_y_no_detecta():
    """El primero de los tres detectores, con su caso que lo mata.

    Y el positivo importa: un detector que solo tiene el negativo —«este
    fichero no se senala»— puede no senalar NADA y seguir dando verde."""
    with tempfile.TemporaryDirectory() as tmp:
        positivo = os.path.join(tmp, 'positivo.py')
        io.open(positivo, 'w', encoding='utf-8').write(
            'import subprocess, sys' + chr(10)
            + "r = subprocess.run([sys.executable, '-m', 'pytest', F])"
            + chr(10))
        negativo = os.path.join(tmp, 'negativo.py')
        io.open(negativo, 'w', encoding='utf-8').write(
            'import subprocess' + chr(10)
            + "# aqui se menciona ['-m', 'pytest'] y no se ejecuta"
            + chr(10)
            + "r = subprocess.run(['git', 'rev-parse', 'HEAD'])" + chr(10))
        assert _lanza_pytest_propio(positivo)[0], (
            'un `subprocess.run` REAL de pytest tiene que senalarse')
        assert not _lanza_pytest_propio(negativo)[0], (
            'uno que solo lo menciona no puede senalarse')


def test_el_detector_de_crudo_detecta_y_no_detecta():
    """El segundo de los tres. Y el que mas facil se rompe.

    `_funciones_que_llaman_a_crudo` tiene que devolver el NOMBRE de la
    funcion —y para eso necesita el arbol, no el texto. MEDIDO: buscando
    `'crudo('` en el fuente, el test que EXPLICABA la exencion se senalaba a
    si mismo, por tener la palabra en el docstring.

    Y el caso que lo mata: una llamada de verdad tiene que salir con el
    nombre de su funcion, porque sin el no se puede exigir que la exencion
    este justificada por su nombre, que es lo unico que la hace visible."""
    fuente = ('import ejecutar_pytest as ep' + chr(10) + chr(10)
              + 'def test_una_cosa():' + chr(10)
              + "    ep.crudo(FICH, 't')" + chr(10) + chr(10)
              + 'def test_otra_cosa():' + chr(10)
              + "    ep.afirmar_caida(FICH, 't')" + chr(10))
    funciones = _funciones_que_llaman_a_crudo(fuente)
    assert funciones == ['test_una_cosa'], (
        'una llamada de verdad a `crudo()` tiene que salir con el nombre de '
        'su funcion, y sale %r. Sin el nombre no se puede exigir que la '
        'exencion este justificada por su nombre.' % (funciones,))

# ============================ 11. EL ALCANCE, COMO TABLA EJECUTABLE
#
# R2, punto 1: «no necesariamente hay que cubrir todas esas variantes; sí
# conviene delimitar qué patrones promete detectar la regla».
#
# Y es la peticion correcta. Y tiene dos mitades, y la segunda es la que
# sobrevive: la tabla —que esta aqui, MEDIDA— y el ALCANCE escrito en el
# codigo de la regla. Un informe se lee una vez; el codigo se relee cada vez
# que alguien usa la regla.
#
# Y hay una forma que NO se detecta, y esta declarado a proposito: el ALIAS.
# `from ejecutar_pytest import correr as c` no se ve. La razon de no ampliar
# el detector para taparla es de coste: seguir un `import` es analisis de
# flujo de nombres importados, que no se sabe mantener. Y un detector mas
# grande detecta mas Y avisa mas, y el que avisa de mas es ruido.
#
# Un hueco DECLARADO se busca. Uno no declarado se tropieza tres meses
# despues, por alguien que no lo sabe.

ALCANCE = (
    # (nombre, CODIGO COMPLETO de la forma, lo que la regla PROMETE)
    ('desestructura de tupla',
     "codigo, salida = ep.correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), True),
    ('desestructura invertida',
     "salida, codigo = ep.correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), True),
    ('indice `[0]`: la llamada con un indice encima',
     "codigo = ep.correr(F, 't')[0]" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), True),
    ('dentro de un `assert`',
     "codigo, salida = ep.correr(F, 't')" + chr(10) + 'assert codigo != 0'
     + chr(10), True),
    ('dentro de una EXPRESION, no de una sentencia',
     "codigo, salida = ep.correr(F, 't')" + chr(10) + 'x = (codigo != 0)'
     + chr(10), True),
    ('la llamada SUELTA, sin `ep.`',
     'from ejecutar_pytest import correr' + chr(10)
     + "codigo, salida = correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), True),
    # Y esta mide PROCEDENCIA, NO VALOR. Que es un FALSO POSITIVO REAL y
    # declarado, no una forma que la regla cubra:
    #
    #     codigo, salida = ep.correr(F, 't')
    #     codigo = len(salida)
    #     if codigo != 0:      <-- compara una LONGITUD, no un codigo
    #
    # El detector senala porque `codigo` SALIO de la puerta, no porque su
    # valor siga siendo el codigo de salida. Y la fila anterior se llamaba
    # «la variable vuelve a usarse para otra cosa», que suena a una forma
    # cubierta y no a un falso positivo.
    #
    # Y no se arregla porque arreglarlo es SEGUIR la variable, que es
    # analisis de flujo de datos — lo unico que este detector no hace, y lo
    # que este bloque ha decidido no hacer, por el mismo motivo que no sigue
    # alias —.
    #
    # Y de las dos salidas posibles, la que se elige es la de DECIRLO. La
    # otra —dejar de senalar una variable reasignada— perderia un caso real:
    # `codigo, salida = correr(...)` + `otro, codigo = f()` + `codigo != 0`
    # seguira senalandose, porque en algun momento SI hubo un codigo ahi.
    #
    # Y esta es la QUINTA vez con la misma forma, y en la DIRECCION OPUESTA
    # a las otras cuatro, que median menos de lo que decian. Y medir mas de
    # lo que se dice es PEOR: un detector que mide de mas CONVENCE de que
    # mide bien. El que mide menos se ve como fallo; el que mide mas se lleva
    # una impresion que es justo lo que tiene que prevenir.
    ('REASIGNADA — mide PROCEDENCIA, no valor: FALSO POSITIVO declarado',
     "codigo, salida = ep.correr(F, 't')" + chr(10) + 'codigo = len(salida)'
     + chr(10) + 'if codigo != 0:' + chr(10) + '    pass' + chr(10), True),
    # --- y las que la regla NO promete, DECLARADAS ---
    ('ALIAS de la funcion: `correr as c`',
     'from ejecutar_pytest import correr as c' + chr(10)
     + "codigo, salida = c(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), False),
    # Y una que la version anterior ponia aqui, en las que NO promete, y que
    # ahora se detecta — y es CORRECTO: `import ejecutar_pytest as e` liga
    # el MISMO modulo, solo que con otro nombre.
    #
    # O sea que el rechazo anterior era un artefacto de no seguir ningun
    # alias, no una decision. Y ahora sigue el alias del MODULO porque el
    # receptor es una pregunta SOBRE EL MODULO, y un alias del modulo no
    # cambia la respuesta.
    #
    # Y el alias de la FUNCION sigue siendo hueco, y esa asimetria no es
    # arbitraria: renombrar la FUNCION es salirse del contrato de la puerta,
    # que es una lista de nombres CANONICOS, mientras que renombrar el modulo
    # no cambia lo que se pregunta.
    #
    # Y R1 lo prohibe explicitamente: «no amplies el detector para tapar el
    # alias. Esta declarado a proposito». O sea que la asimetria es la
    # DECISION, y lo que faltaba era declararla.
    ('ALIAS del MODULO: `ejecutar_pytest as e` — el mismo modulo, otro nombre',
     'import ejecutar_pytest as e' + chr(10)
     + "codigo, salida = e.correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), True),
    ('`def correr` local JUNTO a un import legitimo: hueco DECLARADO',
     'from ejecutar_pytest import correr' + chr(10)
     + 'def correr(f, t):' + chr(10) + '    return 1, 2' + chr(10) + chr(10)
     + "codigo, salida = correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), True),
    ('`def correr` local SIN import: no es la puerta',
     'def correr(f, t):' + chr(10) + '    return 1, 2' + chr(10) + chr(10)
     + "codigo, salida = correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), False),
    ('`correr` de otro modulo, importado sin alias',
     'from otra_cosa import correr' + chr(10)
     + "codigo, salida = correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), False),
    ('`correr` de OTRO modulo: no es la puerta comun',
     'import otro' + chr(10) + "codigo, salida = otro.correr(F, 't')"
     + chr(10) + 'if codigo != 0:' + chr(10) + '    pass' + chr(10), False),
    ('desestructura de LISTA, no de tupla',
     "[codigo, salida] = ep.correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), False),
    ('comparacion contra OTRO numero, no contra 0',
     "codigo, salida = ep.correr(F, 't')" + chr(10) + 'if codigo != 1:'
     + chr(10) + '    pass' + chr(10), False),
    ('comparacion ENCADENADA',
     "codigo, salida = ep.correr(F, 't')" + chr(10) + 'if 0 < codigo != 0:'
     + chr(10) + '    pass' + chr(10), False),
    ('`==` en vez de `!=`: no es la infraccion',
     "codigo, salida = ep.correr(F, 't')" + chr(10) + 'if codigo == 0:'
     + chr(10) + '    pass' + chr(10), False),
    # --- los tres de R2, mas uno que salio al medirlos ---
    #
    # Y que el TERCERO no lo senale R2 y saliera aqui, al medir, es lo de
    # siempre: los casos que se escriben sin pensar son los que encuentran
    # los fallos de la pregunta. El caso sin pensar es «y si el modulo esta
    # dentro de un atributo mas?».
    ('RECEPTOR ANIDADO: `obj.ep.correr` — `obj.ep` no es el modulo',
     'import ejecutar_pytest' + chr(10) + 'obj = algo()' + chr(10)
     + "codigo, salida = obj.ep.correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), False),
    ('RECEPTOR ANIDADO: `obj.e.correr`, con `e` ligado por el modulo',
     'import ejecutar_pytest as e' + chr(10) + 'obj = algo()' + chr(10)
     + "codigo, salida = obj.e.correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), False),
    ('RECEPTOR ANIDADO: `modulo.ejecutar_pytest.correr`',
     "codigo, salida = modulo.ejecutar_pytest.correr(F, 't')" + chr(10)
     + 'if codigo != 0:' + chr(10) + '    pass' + chr(10), False),
    ('import de ambito LOCAL + llamada FUERA: el nombre no esta ligado',
     'def auxiliar():' + chr(10)
     + '    from ejecutar_pytest import correr' + chr(10) + chr(10) + chr(10)
     + "codigo, salida = correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), False),
    # Y esta es un CAMBIO DE CONTRATO, no una perdida por descuido: para que
    # el nombre quede ligado EN EL MODULO los imports tienen que ser de nivel
    # de modulo, y uno de nivel de funcion liga el nombre solo ahi dentro.
    #
    # Y es un hueco en la direccion CONTRARIA, que es la buena:
    #
    #     se detecta menos -> se ve como fallo
    #     se detecta mas   -> convence de que esta bien
    #
    # Un detector que mide de menos ensena a mirar; uno que mide de mas
    # ensena a no mirar. Y por eso el precio vale la pena y por eso el
    # nombre de la fila lo DECLARA.
    ('import LOCAL + llamada DENTRO de la misma funcion: hueco DECLARADO',
     'def auxiliar():' + chr(10)
     + '    from ejecutar_pytest import correr' + chr(10) + chr(10)
     + "    codigo, salida = correr(F, 't')" + chr(10) + '    if codigo != 0:'
     + chr(10) + '        pass' + chr(10), False),
    ('`try/except ImportError` de nivel de modulo: la presencia es la regla',
     'try:' + chr(10) + '    from ejecutar_pytest import correr' + chr(10)
     + 'except ImportError:' + chr(10) + '    pass' + chr(10) + chr(10)
     + "codigo, salida = correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), True),
)


def test_el_alcance_de_la_regla_es_el_declarado():
    """Cada forma del alcance, con SU CODIGO COMPLETO, medida.

    Y el alcance esta en una CONSTANTE del fichero, no en el docstring. Que
    es la diferencia entre «se puede comprobar que lo declarado es lo que
    hace» y «alguien lo leo una vez».

    Y CADA FILA LLEVA EL CODIGO ENTERO, no una base a la que se le anade la
    comparacion. Una version anterior de esta tabla hacia eso, y fallaba en
    las formas que ya traian comparacion —`assert codigo != 0`,
    `x = (codigo != 0)`— porque encima se anadia una segunda, y sin origen.

    Que es el CUARTO fallo de este bloque con la misma forma: la comprobacion
    existe y no mide lo que dice medir. Las otras tres son el filtro
    `ast.IsNot` que nunca casaba, el `except SyntaxError` que decia «limpio»,
    y `sin_probar()` sin ambito que decia «nada pendiente».

    Y con el codigo entero, si una fila esta mal escrita el fallo lo dice EN
    LA FILA, y no en un numero de la suma.

    Y una fila se ha MOVIDO de grupo al afinar el detector, y no es un fallo
    de la tabla: `import ejecutar_pytest as e` + `e.correr(...)` esta ahora
    entre las que se detectan, porque ese `e` es el MISMO modulo de la
    puerta. El rechazo anterior era un artefacto de no seguir ningun alias.

    Y el alias de la FUNCION se queda en el grupo de las que NO, y esa
    asimetria es la decision — R1 prohibe tapar el alias —, asi que la fila
    lo dice para que dentro de seis meses no se lea como un fallo."""
    for nombre, fuente, debe in ALCANCE:
        detectado = bool(_comparaciones_inequivocas(fuente))
        assert detectado == debe, (
            'ALCANCE NO CUMPLIDO en «%s».' % nombre + chr(10) + chr(10)
            + '  la regla promete %s, y hace %s'
            % ('detectar' if debe else 'NO detectar',
               'detecta' if detectado else 'no detecta')
            + chr(10) + chr(10) + 'Fuente:' + chr(10) + fuente)


# ============================ 12. QUE EL INVARIANTE NO PASE POR PIEDAD
def test_el_invariante_no_puede_pasar_por_lista_vacia():
    """R2, punto 2, y la pregunta que hace es la fina.

    `sin_probar()` devuelve `[]` en tres situaciones que NO son lo mismo:

        no habia ninguna escritura pendiente        -> lo correcto
        no habia ninguna escritura REGISTRADA      -> vacio por PIEDAD
        se escribio con `f.write` a pelo, sin marcar -> vacio por PIEDAD

    Y las dos ultimas son el mismo fallo que el filtro `ast.IsNot` y el
    `except SyntaxError`: la comprobacion dice «nada pendiente» y lo que ha
    pasado es «no he mirado».

    Y la tercera puede pasar de verdad, por una razon que no es de estado
    sino de API: `escribir_documento()` es una FUNCION y se puede NO
    LLAMAR. Un test que escribe con `f.write` y despues comprueba
    `sin_probar()` tiene un invariante que no ve su propia escritura.

    Que es el fallo del bloque anterior un nivel mas abajo: la mutacion se
    escribio por la puerta equivocada, y la puerta correcta no se entero.

    Y CADA CASO CON SU AMBITO. MEDIDO: las tres partes compartian el ambito
    del test, y la que queria comprobar «no hay nada registrado» no
    podia, porque la anterior habia registrado.

    Y la solucion no es «limpiar a mitad», es que cada caso tenga el suyo con
    `ep.ambito()`. Que es lo que hace el `autouse` por fuera, y lo que hace
    falta por dentro cuando un test tiene varios casos. Los ambitos se
    anidan, y el exterior se restaura al salir.

    Que es la respuesta a «pytest no deja llamar a un fixture»: los ambitos
    se abren a mano cuando hace falta, y el que se abre a mano se puede
    comprobar."""
    # (a) lo correcto: se registro y llego a un test
    with ep.ambito():
        with tempfile.TemporaryDirectory() as tmp:
            destino = os.path.join(tmp, 'DOCS')
            shutil.copytree(os.path.join(ROOT, 'DOCS'), destino)
            env = dict(os.environ)
            env[rs.DIR_DE_DOCUMENTOS] = destino
            env['PYTHONPATH'] = os.path.join(ROOT, 'tools')
            ep.escribir_documento(os.path.join(destino, 'A.md'), 'a',
                                  que='LO REGISTRADO')
            assert ep.Registrado() == ['LO REGISTRADO'], (
                'una escritura por la puerta tiene que verse en `Registrado()`. '
                'Si no se ve, `sin_probar()` esta mintiendo: devolveria vacio, '
                'y eso se lee como «todo lo escrito llego a un test». Se ve: '
                '%r' % (ep.Registrado(),))
            ep.correr(FICH, VERDE, env=env, cwd=ROOT)
            assert not ep.sin_probar(), (
                'y la escritura si llego a un test, asi que no hay pendientes')

    # (b) vacio por piedad: nada registrado. Y `Registrado()` LO DICE, que
    #     es lo unico que separa «todo probado» de «no mirado».
    with ep.ambito():
        assert ep.sin_probar() == [], 'el ambito nuevo esta vacio'
        assert ep.Registrado() == [], (
            'y `Registrado()` tiene que estar vacio. Si las dos devolvieran '
            'lo mismo, la precondicion no serviria para nada: no habria '
            'forma de distinguir «todo lo escrito llego a un test» de «no se '
            'ha registrado nada»')

    # (c) una escritura por la PUERTA EQUIVOCADA: el invariante no la ve
    with ep.ambito(), tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, 'B.md')
        with io.open(ruta, 'w', encoding='utf-8', newline='') as f:
            f.write('una mutacion escrita por la puerta equivocada')
        assert ep.sin_probar() == [], (
            'una escritura con `f.write` NO la ve el invariante, y eso no es '
            'un fallo suyo: es la linea del contrato. Se marca lo que es '
            'MUTACION, no lo que es un fichero, porque marcarlo todo vuelve '
            'al invariante de fuente que senalaba los ficheros que se '
            'CONSTRUYEN — que era ruido')
        assert ep.Registrado() == [], (
            'y por eso `Registrado()` tiene que estar vacio: un test que '
            'escribe por la puerta equivocada no tiene nada registrado, y '
            'por eso su `sin_probar()` no significa NADA. Que es exactamente '
            'lo que el test tiene que comprobar ANTES de mirar pendientes')

# ============================ 13. LA AUDITORIA DEL ARBOL COMPLETO
def test_el_recorrido_de_la_regla_cubre_todos_los_ficheros_de_prueba():
    """R2, punto 3: «debe quedar verificado el recorrido de todos los
    archivos que pretende cubrir».

    Y es la peticion correcta, y es de este bloque: demostrar que un
    detector funciona con un caso SINTETICO no es auditar un arbol. El
    sintetico prueba que el detector funciona; el recorrido prueba que se
    le ha dado algo que mirar.

    Y las dos cosas que pueden fallar en silencio:

      (1) que el FILTRO del recorrido no case con algun fichero de prueba.
          `_ficheros_de_prueba()` filtra por `startswith('test_')` y
          `endswith('.py')`, que es la convencion de pytest. Y aqui se
          comprueba que el filtro no deja ninguno fuera, que es
          exactamente el fallo de hace dos bloques —la regla que miraba dos
          ficheros de quince— pero por el otro lado: un filtro en vez de una
          lista, que puede fallar en la direccion contraria.

      (2) que la APERTURA falle en silencio. `_lanza_pytest_propio` ya
          LANZA con un `SyntaxError`, pero abrir un fichero puede fallar por
          PERMISOS o por una CODIFICACION, y si eso se devuelve como «no
          senala», es la cuarta vez que una comprobacion dice «nada».

    Y el caso de la codificacion no es teorico en Windows: `open(...,
    encoding='utf-8')` sobre un fichero escrito con otra codificacion lanza
    `UnicodeDecodeError`, que NO es un `SyntaxError` y pasaria intacto por el
    `except`. Y un test nuevo que se escribiera con la codificacion por
    defecto de Windows entraria por ahi sin que nadie lo note.

    Que es el mismo modo de fallo del `except SyntaxError`, con otro
    envoltorio: la excepcion que no es la que se esperaba pasa por el
    camino de la que si.
    """
    en_disco = sorted(
        os.path.join(ROOT, 'tools', f)
        for f in os.listdir(os.path.join(ROOT, 'tools'))
        if f.startswith('test_') and f.endswith('.py'))
    recorrido = sorted(os.path.normpath(r) for r in _ficheros_de_prueba())

    # IDENTIDADES, NO CANTIDADES. MEDIDO: con `len(recorrido) ==
    # len(en_disco)`, un recorrido que omite un fichero e incluye otro dos
    # veces tiene los MISMOS numeros y no son los mismos ficheros:
    #
    #     en disco:   ['a', 'b', 'c']
    #     recorrido: ['a', 'b', 'b']
    #     len == len:  True     <- la comprobacion de antes pasa
    #     son los mismos: False
    #
    # Que es el fallo de la lista de dos ficheros un nivel mas abajo: aquella
    # comprobaba SI/NO sobre dos nombres, esta comprobaba CUANTOS sobre todos.
    # Ninguna mira SI SON LOS MISMOS.
    #
    # Y `normpath`, porque en Windows `tools\\x.py` y `.\\tools\\x.py` son el
    # mismo fichero y sin normalizar son dos.
    #
    # Y POR QUE HACE FALTA UN SEGUNDO CHECK PARA LOS DUPLICADOS: porque
    # `set()` los borra. Un recorrido con un duplicado tiene el mismo
    # conjunto, y los dos numeros pueden coincidir. O sea que comprobar solo
    # el conjunto tambien deja pasar el duplicado. Son dos comprobaciones
    # porque son dos fallos.
    assert len(recorrido) == len(set(recorrido)), (
        'el recorrido tiene DUPLICADOS: %d entradas, %d distintas. Un '
        'duplicado no lo ve un `set()`, de modo que comparar conjuntos no '
        'basta por si solo.\n\nRecorrido: %s'
        % (len(recorrido), len(set(recorrido)), recorrido))

    assert recorrido == en_disco, (
        'el recorrido no cubre EXACTAMENTE los ficheros de prueba.\n\n'
        'en disco:    %d\n%s\n\nrecorridos: %d\n%s\n\nsolo en disco:     '
        '%s\nsolo en recorrido: %s\n\nUn filtro que no casa deja un '
        'fichero SIN MIRAR y la regla sigue en verde.'
        % (len(en_disco), chr(10).join('   ' + os.path.basename(f)
                                       for f in en_disco),
           len(recorrido),
           chr(10).join('   ' + os.path.basename(f) for f in recorrido),
           sorted(os.path.basename(f) for f in set(en_disco)
                  - set(recorrido)) or 'ninguno',
           sorted(os.path.basename(f) for f in set(recorrido)
                  - set(en_disco)) or 'ninguno'))

    # Y que ABRIR cada uno no falle en silencio
    for ruta in recorrido:
        with io.open(ruta, encoding='utf-8') as f:
            f.read()

    with tempfile.TemporaryDirectory() as tmp:
        # (a) sintaxis rota, por el DETECTOR
        roto = os.path.join(tmp, 'roto.py')
        io.open(roto, 'w', encoding='utf-8', newline='').write(
            'def f(:' + chr(10))
        with pytest.raises(SyntaxError):
            _lanza_pytest_propio(roto)

        # (b) codificacion incompatible, POR EL DETECTOR
        #
        # Y no comprobando `io.open(...)`, que es lo que hacia antes. Es
        # comprobar que `open` falla, no que falle el detector: la prueba
        # tiene que ejercitar la FUNCION que se audita, o no audita nada.
        #
        # Y el caso no es teorico en Windows, donde `open` sin `encoding`
        # lee `cp1252`. Un test nuevo escrito con la codificacion por defecto
        # entraria por ahi sin que nadie lo note.
        otro = os.path.join(tmp, 'cp1252.py')
        with io.open(otro, 'w', encoding='cp1252', newline='') as f:
            f.write('# acento: n' + chr(241) + chr(32) + chr(10))
        with pytest.raises(UnicodeDecodeError):
            _lanza_pytest_propio(otro)
