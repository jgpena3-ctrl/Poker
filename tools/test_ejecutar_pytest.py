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
        # Y `cases`, que se habia olvidado. MEDIDO: un import dentro de un
        # `case` de `match` no se recogia, y `match` NO abre ambito — es una
        # condicion mas— asi que el nombre queda ligado en el modulo.
        #
        # Y es un atributo olvidado, no una excepcion mal escrita: una lista
        # incompleta. Y una lista incompleta se tapa escribiendo el elemento.
        #
        # Y anadir `cases` mete al recorrido dentro del cuerpo de los
        # `match_case`, que es lo correcto: son del ambito que los contiene.
        # El `class` sigue siendo ambito nuevo y no se toca.
        # Y `CAMPOS_RECORRIDOS`, y no una tupla aqui.
        #
        # MEDIDO, antes: la implementacion tenia su PROPIA tupla, identica
        # a la constante, y `CAMPOS_RECORRIDOS` no aparecia en ella. Dos
        # literales iguales, que pueden separarse sin que nada lo note: se
        # anade un campo a la constante, la derivacion dice que el corpus lo
        # exige, la comprobacion pasa — y el codigo sigue sin recorrerlo.
        #
        # Que es la sexta vez con la misma forma, y la primera en que las dos
        # listas son IGUALES: en las otras cinco se diferenciaban en el
        # contenido, y aqui se diferencian en que son dos, lo cual es peor
        # porque a simple vista es indistinguible.
        #
        # Y el arreglo no es sincronizarlas: es que solo haya UNA.
        for atributo in CAMPOS_RECORRIDOS:
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
    ('import dentro de un `class` + llamada fuera: `class` SI abre ambito',
     'class Auxiliar:' + chr(10)
     + '    from ejecutar_pytest import correr' + chr(10) + chr(10)
     + "codigo, salida = correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), False),
    ('import dentro de un `case` de `match` + llamada fuera',
     'match opcion:' + chr(10) + '    case 1:' + chr(10)
     + '        from ejecutar_pytest import correr' + chr(10) + chr(10)
     + "codigo, salida = correr(F, 't')" + chr(10) + 'if codigo != 0:'
     + chr(10) + '    pass' + chr(10), True),
    ('import dentro de un `case` de `match` + llamada DENTRO del `case`',
     'match opcion:' + chr(10) + '    case 1:' + chr(10)
     + '        from ejecutar_pytest import correr' + chr(10)
     + "        codigo, salida = correr(F, 't')" + chr(10)
     + '        if codigo != 0:' + chr(10) + '            pass' + chr(10), True),
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


# ============================ 14. LA INVARIANTE QUE ROMPIO EL ARNES
DISTRACTOR = (
    'codigo = 0' + chr(10)
    + 'salida = "nada"' + chr(10)
    + 'obj = algo()' + chr(10)
)


def test_una_asignacion_distractora_no_cambia_el_resultado():
    """R1, tarea 5, y la propiedad que de verdad se puede guardar.

    El arnés que falló estaba en un script temporal, así que no hay nada que
    guardar de él. Lo que se guarda es la PROPIEDAD que el arnés respetaba:

        anteponer una asignación que no tiene que ver con la comparación no
        cambia el resultado

    Y esa es una invariante real de `_llamada_de_la_puerta`, y es lo que vino
    a enseñar el fallo: que el detector tiene que mirar la asignación
    CORRECTA.

    Y por qué merece una prueba, cuando `_variables_de_la_puerta` ya recorre
    el árbol entero con `ast.walk` y le da igual el orden:

    Porque eso es una CONSECUENCIA de que recorra todo, y no una PROPIEDAD
    declarada. Y una consecuencia no escrita se rompe en cuanto alguien
    cambie el recorrido para que sea más rápido —que es la optimización
    natural de un `ast.walk`—, y ahí esta prueba dice «ok» mientras el
    detector ha empezado a mirar la primera.

    Y esa es la forma que toman los fallos de este bloque: una consecuencia
    que funciona, escrita como si fuera una garantía.

    Y el distractor lleva `codigo = 0`, que es lo más peligroso: un detector
    que mirase la primera asignación vería `codigo` y no tendría nada que
    mirar. Un `obj = algo()` no estorbaría."""
    for nombre, fuente, debe in ALCANCE:
        limpio = bool(_comparaciones_inequivocas(fuente))
        con_distractor = bool(_comparaciones_inequivocas(
            DISTRACTOR + fuente))
        assert limpio == debe, (
            'ALCANCE NO CUMPLIDO en «%s» sin distractor: %s, esperaba %s'
            % (nombre, limpio, debe))
        assert con_distractor == limpio, (
            'ALCANCE ROTO en «%s»: con una asignación distractora delante, el '
            'resultado pasa de %s a %s.' % (nombre, limpio, con_distractor)
            + chr(10) + chr(10)
            + 'O sea que el detector no esta leyendo la fila sino el ARBOL, '
            'y el orden le importa. Y eso puede venir de que '
            '`_variables_de_la_puerta` recorra con `ast.walk`, que hoy '
            'recorre todo y le da igual el orden — y por eso la invariancia '
            'es una CONSECUENCIA y no una PROPIEDAD—.')


# ============================ 15. LA LISTA DE CAMPOS, DERIVADA Y COMPROBADA
#
# Y esta es la respuesta a R2, que pedia dos cosas:
#
#   - descender por if, try, for, while, with y match/case
#   - no descender por def, async def, class ni lambda
#   - y que haya un test que verifique que la lista esta COMPLETA
#
# La tercera es la importante, y es la misma leccion que la lista de dos
# ficheros de hace tres bloques: una lista escrita a mano que declara cubrir
# un conjunto y no lo cubre. `cases` se le olvido, y nadie lo noto porque la
# lista es correcta para todo lo que el diagnostico senalo.
#
# Y «completa» no se puede decir escribiendo la lista. Se puede decir
# DERIVANDOLA de una pregunta sobre el propio arbol:
#
#     ¿descender por este campo PUEDE LLEGAR a una sentencia?
#
# Y esa pregunta es distinta de «este campo guarda sentencias», y la
# diferencia importa:
#
#   - `handlers` no guarda sentencias: guarda `ast.ExceptHandler`, que no es
#     un `ast.stmt` — es de la rama `excepthandler`—. Y sin embargo por ahi
#     se llega a un `try`.
#   - `cases` tampoco: guarda `match_case`, que tampoco es un `stmt`. Y sin
#     bajar por `cases` no se llega al `body` que ese `match_case` si tiene.
#
# O sea que los dos atributos que mas importaban eran los dos que el filtro
# «los elementos son stmt» descartaba. Y hay que distinguir «lo que guarda
# una sentencia» de «lo que POR DONDE se llega a una».
#
# Y DOS LISTAS, POR DOS RAZONES DISTINTAS
#
#   los CAMPOS que hay que recorrer   -> si faltan, se pierde cobertura
#   las PARADAS donde no hay que bajar -> si sobran, se accepts de mas
#
# Y son dos porque una lista con los dos no dice nada: `body` esta en las dos,
# y no se podria decir por que lado cae. Que es la misma razon por la que la
# tabla de ALCANCE separa «promete» de «no promete».

# ============================================ el corpus, aqui y legible
CORPUS_CONSTRUCCIONES = (
    ('module', ''),
    ('if/else', 'if x:\n    pass\nelse:\n    pass\n'),
    ('for/else', 'for x in y:\n    pass\nelse:\n    pass\n'),
    ('async for/else', 'async def f():\n    async for x in y:\n        pass\n'
                       '    else:\n        pass\n'),
    ('while/else', 'while x:\n    pass\nelse:\n    pass\n'),
    ('with', 'with a as b:\n    pass\n'),
    ('async with', 'async def f():\n    async with a as b:\n        pass\n'),
    ('try/except/else/finally',
     'try:\n    pass\nexcept E as e:\n    pass\nelse:\n    pass\n'
     'finally:\n    pass\n'),
    ('try* (except*)', 'try:\n    pass\nexcept* E:\n    pass\n'),
    ('match/case', 'match x:\n    case 1:\n        pass\n'
                   '    case _:\n        pass\n'),
    ('def', 'def f():\n    pass\n'),
    ('async def', 'async def f():\n    pass\n'),
    ('class', 'class C:\n    pass\n'),
    ('lambda', 'lambda: 1'),
)

# Los campos por los que el recorrido TIENE que bajar.
CAMPOS_RECORRIDOS = ('body', 'orelse', 'finalbody', 'handlers', 'cases')

# Los tipos donde NO se baja, y son ambitos nuevos.
PARADAS = ('FunctionDef', 'AsyncFunctionDef', 'ClassDef', 'Lambda')


def _hijos(valor):
    """Los hijos de un campo de `ast`, como lista.

    Y en UN solo sitio, porque `ast` da tres formas y hay que mirar las tres:

      - una lista      -> la lista
      - un nodo suelto -> [nodo]
      - `None`         -> []   <- y este es el que revienta

    MEDIDO: sin el caso de `None`, `orelse=None` entra en la cola como
    `[None]` y `iter_fields(None)` revienta en `node._fields`. Que es un
    `AttributeError` sobre `'NoneType'`, o sea un fallo MUY visible —y por
    eso no es peligroso—. Los peligrosos son los que devuelven un valor.

    Y el filtro de `ast.AST` es lo que hace que no se bajen a las
    EXPRESIONES —`test`, `subject`, `pattern`—, que son campos pero no
    llevan a ninguna sentencia.

    Y UN solo sitio, y no tres expresiones repetidas: repetir «es una lista,
    o un nodo, o nada» tres veces es la via corta a tener tres versiones que
    divergen. Y ya ha pasado en este bloque con cuatro ficheros de prueba
    casi iguales."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return [v for v in valor if isinstance(v, ast.AST)]
    return [valor] if isinstance(valor, ast.AST) else []


def _llega_a_sentencia(nodo, paradas=PARADAS):
    """¿Algun camino desde `nodo` llega a una sentencia SIN pasar por un
    ambito nuevo?

    Y el limite de profundidad, porque `ast` es un grafo dirigido sin ciclos
    hacia statements pero con caminos larguisimos —una comprehension dentro
    de un `if` dentro de un `try`— y aqui no interesa la longitud sino si hay
    camino."""
    # Y EL ORDEN IMPORTA, y en el sentido contrario al que parece.
    #
    # MEDIDO: `ast.FunctionDef` ES un `ast.stmt` — hereda de `stmt`—, de modo
    # que con el isinstance primero la funcion se contaba como sentencia
    # ALCANZABLE y la parada no paraba. El fallo era del sanity check entero.
    #
    # Que es la misma leccion del bloque, en su forma mas fina: dos
    # comprobaciones que ambas son ciertas, y el ORDEN decide. Con el orden
    # equivocado el resultado es un verde que no significa nada, y no hay
    # ningun error que lo delate.
    if type(nodo).__name__ in paradas:
        return False                      # un ambito nuevo: aqui no se llega
    if isinstance(nodo, ast.stmt):
        return True
    if not isinstance(nodo, ast.AST):
        return False
    # Y SIN limite de profundidad, con PILA y VISTOS.
    #
    # Y una version anterior de este comentario decia que el limite «podia
    # contestar no a un si, con un camino de nueve niveles». MEDIDO: NO.
    #
    #     1..13 niveles de anidamiento: sin limite=True, con limite=True
    #     El limite NUNCA cambio un resultado.
    #
    # Y la razon de no llegar: la pregunta es «¿puedo llegar a una
    # sentencia?», y los campos de `ast` que guardan sentencias guardan
    # `ast.stmt` DIRECTAMENTE —`With.body` es una lista de `stmt`—, asi que
    # un nivel basta. Para necesitar nueve habria una cadena de nodos que no
    # fueran sentencia y guardaran sentencia, y `ast` no produce eso.
    #
    # O sea: la afirmacion era CIERTA EN PRINCIPIO y FALSA EN LA PRACTICA, y
    # documentarla como medida era escribir algo que no se ha medido. Que es
    # la septima vez que una medicion contradice lo escrito, y la segunda en
    # que la contradiccion es «es cierto pero no asi de fuerte»:
    #
    #     «puede pasar» != «pasa»
    #
    # Y se quita igual, y por el ARGUMENTO que no es el del comentario
    # viejo: `ast` es aciclico, un conjunto de vistos termina solo, y un
    # limite a 8 es un adorno que nunca cambia un resultado. Un adorno que
    # no protege de nada se queda puesto porque nadie lo nota.
    #
    # Y la objecion de R2 SIGUE siendo valida —un corte puede responder mal
    # en principio—, y lo que no se puede construir es el ejemplo para ESTA
    # pregunta sobre ESTE arbol. Que es la razon de que la respuesta sea
    # quitarlo y DECIR POR QUE, en vez de dejarlo con un comentario que
    # afirma un dano que no se ha visto ocurrir.
    #
    # Y EL PARAMETRO SE QUITA, porque dejarlo invites a volver a poner un
    # corte. El parametro era el sitio donde el limite estaba.
    pendientes, vistos = [nodo], set()
    while pendientes:
        actual = pendientes.pop()
        clave = id(actual)
        if clave in vistos:
            continue
        vistos.add(clave)
        if type(actual).__name__ in paradas:
            continue                      # un ambito nuevo
        if isinstance(actual, ast.stmt):
            return True
        if not isinstance(actual, ast.AST):
            continue
        for _, valor in ast.iter_fields(actual):
            pendientes.extend(_hijos(valor))
    return False


def _sin_ambitos(arbol, paradas=PARADAS):
    """Los nodos alcanzables SIN cruzar un ambito nuevo.

    Y esto es lo que le faltaba a la primera version: usaba `ast.walk`, que
    visita el arbol entero, y preguntaba sobre el `FunctionDef` — que la
    implementacion nunca llega a mirar—. O sea que la derivacion se
    preguntaba sobre mas cosas que la implementacion, y por eso decia que
    las paradas no paraban.

    MEDIDO, antes del arreglo:

        por debajo de `FunctionDef` hay sentencias y el recorrido las ve:
        body

    Que era verdad de `ast.walk` y falso de la regla. Y la tension que
    introduce es REAL y hay que decirla: a partir de aqui, la derivacion y la
    implementacion comparten la REGLA DE VISITA.

    Lo que sigue siendo independiente —y es lo que sostiene la
    comprobacion— son las dos cosas que se COMPARAN:

        lo que el CODIGO recorre    -> `CAMPOS_RECORRIDOS`, escrito a mano
        lo que hace FALTA recorrer  -> derivado del corpus

    Si el codigo recorre de mas sale «sobran»; si de menos, «falta». Y en los
    dos casos se compara contra algo que nadie escribio a mano.

    Lo que se pierde es detectar que la REGLA DE VISITA este mal — y eso se
    acepta a conciencia, porque «no bajes dentro de un ambito nuevo» es una
    DECISION, y las decisiones no se derivan: se argumentan. Y ya esta
    argumentada, con la razon de que un import dentro de `def` liga el
    nombre solo ahi dentro."""
    vistos, pendientes = [], [arbol]
    while pendientes:
        nodo = pendientes.pop()
        if type(nodo).__name__ in paradas:
            continue                      # un ambito nuevo: no se entra
        vistos.append(nodo)
        for _, valor in ast.iter_fields(nodo):
            pendientes.extend(_hijos(valor))
    return vistos


def _campos_necesarios(fuente, paradas=PARADAS):
    """Los campos por los que hay que bajar para alcanzar una sentencia.

    Y sobre los nodos que se ven SIN CRUZAR un ambito nuevo, que es lo que
    hace la implementacion. Antes usaba `ast.walk` —todo el arbol— y por eso
    decia que las paradas no paraban."""
    necesarios = set()
    for padre in _sin_ambitos(ast.parse(fuente), paradas):
        for campo, valor in ast.iter_fields(padre):
            if campo.startswith('_'):
                continue
            for hijo in _hijos(valor):
                if _llega_a_sentencia(hijo, paradas):
                    necesarios.add(campo)
                    break
    return necesarios


def test_los_campos_recorridos_son_los_que_hacen_falta():
    """R1, tarea 5, y R2: «hay que asegurarse de que la lista de atributos
    recorridos incluya todos los nodos de control que pueden contener
    sentencias de nivel de modulo».

    Y eso NO se dice escribiendo la lista: se dice DERIVANDOLA de una
    pregunta sobre el arbol.

    Y hay dos intentos previos que no valian, y los dos produceron una
    respuesta que parecia buena:

      - mirar `vars(clase)` buscando listas: en CPython los campos de `ast`
        no son listas, son slots. NINGUN atributo pasaba el filtro y la
        diferencia salia «ninguno» — la lista esta completa —. Una
        comprobacion que dice «no falta nada» porque no ha encontrado nada
        que comparar.

      - exigir que los elementos fUESEN `ast.stmt`: eso descarta `handlers`
        — `ExceptHandler` no es un `stmt` — y descarta `cases` — `match_case`
        tampoco —. O sea que los dos atributos que mas importaban eran los dos
        que el filtro rechazaba.

    Y la pregunta que si funciona es «¿descender por este campo puede LLEGAR
    a una sentencia?», que no es lo mismo que «este campo guarda
    sentencias»: `handlers` y `cases` no guardan sentencias, pero son por
    donde se llega a ellas.

    Y el CORPUS esta escrito aqui, pieza por pieza, y se puede LEER. Que es
    la diferencia con una lista de atributos opaca: mirando el corpus, la
    pregunta «¿falta `async for`?» tiene respuesta. Una lista no la tiene.
    """
    necesarios = _campos_necesarios(chr(10).join(
        fuente for _, fuente in CORPUS_CONSTRUCCIONES))
    faltan = sorted(necesarios - set(CAMPOS_RECORRIDOS))
    assert not faltan, (
        'descender por estos campos PUEDE llevar a una sentencia, y el '
        'recorrido no lo hace:\\n%s\\n\\nnecesarios: %s\\nrecorridos:  %s\\n\\n'
        'O sea: hay un sitio donde un import de nivel de modulo se esconde y '
        'la regla no lo ve. Y eso es un hueco que no se nota, porque lo que '
        'falta no produce ningun fallo: produce una regla mas debil.'
        % (chr(10).join('   - %s' % c for c in faltan),
           ', '.join(sorted(necesarios)), ', '.join(sorted(CAMPOS_RECORRIDOS))))


def test_no_se_recorre_de_mas_y_las_paradas_son_las_declaradas():
    """La otra mitad, que es la que R2 no pedia y que si importa.

    Si `CAMPOS_RECORRIDOS` tuviera un campo de mas, searianarian
    INFRACCIONES que no son infracciones — un detector que acusa de todo es
    un detector que nadie mira cuando accuse de algo falso—, y no habria
    ninguna prueba que lo dijera.

    Y la segunda mitad: las PARADAS tienen que ser las de AMBITOS NUEVOS, y
    solo esas. Un `def` para ahi porque el nombre no queda ligado fuera; un
    `if` no, porque es una condicion.

    Y se comprueba contra `ast`: si manana aparece un `async def` nuevo, o si
    alguna de estas clases cambia de nombre, el fallo lo dice."""
    sobran = sorted(set(CAMPOS_RECORRIDOS) - _campos_necesarios(
        chr(10).join(fuente for _, fuente in CORPUS_CONSTRUCCIONES)))
    assert not sobran, (
        'estos campos se recorren y no hacen falta para ninguna construccion '
        'del corpus:\\n%s\\n\\nO sea: se acepta de mas. Y eso no produce '
        'ningun fallo visible, solo un detector que convence de que vigila.'
        % chr(10).join('   - %s' % c for c in sobran))

    for nombre in PARADAS:
        assert hasattr(ast, nombre), (
            'la parada %r no existe en `ast`: o se ha renombrado, o estaba '
            'mal escrita. Y una parada que no existe NO PARA NADA, que es '
            'peor que no tenerla' % nombre)

    # Y que cada parada PARE DE VERDAD, que es distinto de existir.
    #
    # Y el `lambda` se trata aparte, y por un motivo que es el resultado de
    # escribir mal el caso: el cuerpo de un `lambda` NO PUEDE contener
    # sentencias, de modo que no hay fragmento que comprobar para el. Y eso
    # mismo es la comprobacion — un `lambda` no puede contener un import, y
    # por eso la parada sobra para el —.
    #
    # Y para las otras tres el fragmento es «sentencias SOLO debajo de la
    # parada», y el resultado tiene que ser que NO HAY CAMPOS NECESARIOS. Que
    # es lo que dice «la parada para de verdad», y no «la parada existe»:
    # comprobar un nombre y comprobar un comportamiento son dos cosas.
    FRAGMENTOS = {
        'FunctionDef': 'def f():\n    import ejecutar_pytest as e\n'
                       "    codigo, salida = e.correr(F, 't')\n",
        'AsyncFunctionDef': 'async def f():\n'
                            '    import ejecutar_pytest as e\n'
                            "    codigo, salida = e.correr(F, 't')\n",
        'ClassDef': 'class C:\n    import ejecutar_pytest as e\n'
                    "    codigo, salida = e.correr(F, 't')\n",
    }
    for nombre, fragmento in FRAGMENTOS.items():
        assert nombre in PARADAS, (
            'el fragmento de %s existe pero no esta en las PARADAS, o al '
            'reves. Si una parada no tiene fragmento que la compruebe, puede '
            'no estar parando' % nombre)
        necesarios = _campos_necesarios(fragmento)
        assert not necesarios, (
            'por debajo de `%s` hay sentencias y el recorrido las ve: %s. O '
            'sea que la PARADA no para, y un import ahi liga el nombre solo '
            'dentro — una llamada fuera seria un `NameError`.'
            % (nombre, ', '.join(sorted(necesarios))))


# Los fragmentos del corpus que NO puede alcanzar, y por que.
#
# Y son TRES, no dos. MEDIDO: `async def` tambien empieza por si misma, y
# tambien es una PARADA, y tambien es inalcanzable. Yo decia dos, y el test
# que comprueba esta lista lo dijo en la primera pasada — que es justo para
# lo que esta ahi.
#
# Y POR QUE ESTA LISTA, Y POR QUE MARCA LOS QUE NO ALCANZA
#
# MEDIDO, por lo que hace la derivacion: un fragmento inalcanzable aporta
# exactamente lo mismo al conjunto derivado que si no existiera — `body` y
# `orelse` ya estan por otros—, y ademas deja escrito que se comprueba. O sea
# que el corpus DECLARA una cobertura que no tiene.
#
# Y por eso es PEOR QUE NO ESTAR: un fragmento ausente del corpus no promete
# nada, y se nota al leer la lista; uno inalcanzable promete, esta ahi, se lee
# y parece comprobar. Lo que se puede cubrir sin cubrir esta como
# infracubierto; lo que parece cubierto y no lo esta es peor.
#
# Y por eso la lista marca los tres, y no los quita del corpus — que es lo que
# haria la opcion que R2 dejo abierta de «documentar que las asincronas
# comparten los campos»: quitar un fragmento del corpus borra el recordatorio,
# y marcarlo lo conserva. Y las dos cosas se necesitan: el recordatorio para
# el que lee, y la comprobacion de CAMPOS —`PARES_ASINCRONOS`— para el que la
# derivacion no puede alcanzar.
#
# Y que una lista de estas sea una DECLARACION COMPROBADA, y no una lista
# escrita: porque una lista escrita a mano que se compara contra otra lista
# escrita a mano no se comprueba, se leen las dos y se ve que dicen lo mismo.
INALCANZABLES_DEL_CORPUS = (
    # `async for` y `async with` solo existen dentro de una funcion `async`, y
    # una funcion `async` es una PARADA. No hay fragmento que los alcance.
    'async for/else',
    'async with',
    'async def',
)


# ============================ 16. LAS ASINCRONAS, QUE EL CORPUS NO CUBRE
#
# Y este es el caso PEOR de la familia, porque no es que falte una
# construccion: es que el corpus la DECLARA y no la comprueba.
#
# R2, punto 2:
#
#     async for y async with figuran en el corpus, pero quedan detrás de una
#     parada. _sin_ambitos() se detiene en AsyncFunctionDef.
#
# Cierto, y medido por la razon obvia al mirar el corpus:
#
#     ('async for/else', 'async def f():\n    async for x in y:\n...')
#     ('async with',    'async def f():\n    async with a as b:\n...')
#
# Los dos empiezan por `async def`, que es una PARADA. O sea que
# `_sin_ambitos` se para en el nodo RAIZ de esos dos fragmentos y no ve nada
# de dentro.
#
# Y no se puede arreglar poniendolos a nivel de modulo, porque `async for` y
# `async with` SOLO existen dentro de una funcion `async`. O sea que la
# construccion es INACCESIBLE para una derivacion que respeta las paradas.
#
# Y POR QUE ES PEOR QUE NO ESTAR
#
# Un fragmento inalcanzable que contributes `body` y `orelse` al conjunto
# derivado hace EXACTAMENTE lo mismo que si no existiera — y ademas deja
# escrito que se comprueba. O sea que es la octava vez con la forma «pasa
# por el motivo equivocado», y la mas discreta, porque el fragmento esta ahi,
# se lee, y parece comprobar algo.
#
# LA COMPROBACION QUE SI FUNCIONA, Y POR QUE HACE FALTA
#
# MEDIDO:
#
#     For._fields             == AsyncFor._fields
#     With._fields            == AsyncWith._fields
#     FunctionDef._fields     == AsyncFunctionDef._fields
#
# O sea que las clases asincronas tienen los mismos campos. Y por eso hace
# falta una comprobacion PROPIA: el corpus cubre `For`, y de ahi no se sigue
# NADA sobre `AsyncFor` — que solo puede aparecer dentro de una funcion
# `async`, que es una parada—.
#
# Y la razon de fondo: comparar CAMPOS sin mirar las CLASES es comparar
# NOMBRES. Dos clases distintas con los mismos campos necesitan su propia
# comprobacion o no estan cubiertas. Y eso no es un detalle de este
# detector: es la forma de hacer las pruebas en general.
#
# Y QUE SE COMPRUEBA, CONCRETAMENTE
#
# Para cada par sincrono/asincrono, que los campos sean iguales, y que
# ademas el `ast` TENGA las dos clases — porque si Python dejara de tener
# `AsyncFor`, el par pasaria a comparar `None` contra `None` y dira «iguales».


# Los pares cuya CLASE cambia con `async`, y que tienen los mismos campos.
PARES_ASINCRONOS = (('For', 'AsyncFor'), ('With', 'AsyncWith'),
                    ('FunctionDef', 'AsyncFunctionDef'))


def test_las_asincronas_tienen_los_mismos_campos_que_las_sincronas():
    """La comprobacion especifica que el corpus NO puede dar.

    Y el motivo por el que el corpus no puede darla es el que hay que decir
    primero: `async for` y `async with` solo existen dentro de una funcion
    `async`, y una funcion `async` es una PARADA. O sea que un recorrido que
    respeta las paradas no puede llegar a ellas NUNCA — no con un fragmento
    mejor escrito, sino con ninguno.

    Y el corpus las decia mirar. Que es la forma peor de esta familia: no es
    que falte una construccion, es que hay una escrita que no comprueba nada.

    Y la comprobacion que si funciona sale del propio `ast`, que DECLARA los
    campos de cada clase:

        For._fields         == AsyncFor._fields
        With._fields        == AsyncWith._fields
        FunctionDef._fields == AsyncFunctionDef._fields

    Y se comprueban las dos cosas: que los campos sean iguales, y que las dos
    CLASES existan — porque si Python dejara de tener `AsyncFor`, el par
    compararia `None` contra `None` y diria «iguales», que es verde por no
    mirar."""
    for sincrona, asincrona in PARES_ASINCRONOS:
        a, b = getattr(ast, sincrona, None), getattr(ast, asincrona, None)
        assert a is not None, (
            '`%s` no existe en `ast`. El corpus declara esta construccion y '
            'la comparacion compararia `None` contra `None` y dira «iguales», '
            'que es verde por no mirar' % sincrona)
        assert b is not None, (
            '`%s` no existe en `ast`. La version asincrona de `%s` es la que '
            'NO se puede cubrir con el corpus, de modo que si desaparece no '
            'queda nada que la compruebe' % (asincrona, sincrona))
        assert a._fields == b._fields, (
            '`%s` y `%s` tienen campos distintos:\n'
            '    %-16s %s\n    %-16s %s\n'
            'Y el corpus cubre la sincrona, de modo que de la asincrona no se '
            'sigue nada. Es decir: la cobertura de la sincrona NO es la '
            'cobertura de la asincrona, y por eso hacen falta dos.'
            % (sincrona, asincrona, sincrona, a._fields, asincrona,
               b._fields))


def test_el_corpus_declara_que_no_alcanza():
    """Y que el corpus NO prometa lo que no cumple.

    Los dos fragmentos `async` están escritos, y se van a quedar escritos —
    porque se pueden LEER y son la respuesta a «¿y las asincronas?», que es la
    pregunta que se hace mirando un corpus—.

    Pero un fragmento que la derivacion no alcanza tiene que estar MARCADO,
    o vuelve a pasar lo de siempre: un caso escrito que parece comprobar.

    Y la marca va en el propio corpus, no en un comentario al lado: una lista
    de fragmentos inalcanzables se lee junto a ellos o no se lee."""
    inalcanzables = [etiqueta for etiqueta, fuente in CORPUS_CONSTRUCCIONES
                     if fuente.lstrip().startswith('async def')]
    assert tuple(inalcanzables) == INALCANZABLES_DEL_CORPUS, (
        'los fragmentos que empiezan por `async def` son %r, y la lista '
        'INALCANZABLES dice %r.'
        % (inalcanzables, list(INALCANZABLES_DEL_CORPUS))
        + chr(10) + chr(10)
        + 'MEDIDO: son TRES, no dos. Yo decia dos, y este test lo ha dicho '
        'en la primera pasada. Un fragmento escrito que no comprueba nada es '
        'PEOR que uno ausente, porque deja escrito que se comprueba — y esa '
        'declaracion es la que hay que vigilar, porque es la que engaña.')
    for etiqueta in inalcanzables:
        assert etiqueta in INALCANZABLES_DEL_CORPUS, (
            'el fragmento «%s» empieza por `async def`, que es una PARADA, y '
            'la derivacion no lo alcanza. O sea que no comprueba nada. Y un '
            'fragmento escrito que no comprueba es PEOR que uno ausente: '
            'deja escrito que se comprueba.' % etiqueta)


# ============================ 17. LAS RUTAS QUE SOLO SE EJECUTAN AL FALLAR
#
# R2, punto 1:
#
#     Python no admite %n como especificador de formato de cadenas. Si alguna
#     pareja tiene campos distintos, la construcción del mensaje puede lanzar
#     ValueError en vez de mostrar la discrepancia que hizo fallar la prueba.
#
# Cierto, y medido — con el TIPO DE EXCEPCION que de verdad sale, que no es el
# que dice R2:
#
#     '`%s` y `%s` tienen campos distintos:%n' % ('For', 'AsyncFor')
#     -> TypeError: not enough arguments for format string
#
# R2 decia ValueError y sale TypeError, porque los dos `%s` se han comido los
# argumentos y el `%n` se queda sin ellos. Y eso da PEOR que un ValueError: el
# mensaje dice «not enough arguments», que no menciona ni el `%n` ni las
# clases. O sea que el fallo borra la causa Y ademas confunde sobre la causa.
#
# Y POR QUE NO SE VE NUNCA
#
# Porque el mensaje se construye SOLO cuando la asercion falla. O sea que este
# bloque entero de codigo vive en un camino que la suite NUNCA recorre
# mientras todo va bien.
#
# Y la prueba en la que estaba, `test_las_asincronas_tienen_los_mismos_campos_
# que_las_sincronas`, existe PRECISAMENTE para detectar un cambio futuro del
# AST. O sea que su unico trabajo es hablar cuando algo va mal, y no puede
# hablar. Que es la peor combinacion posible.
#
# Y EL TIPO DE HUECO, QUE NO SE HABIA CERRADO EN ESTE BLOQUE
#
# Las siete «la comprobacion no mide lo que dice medir» han sido sobre rutas
# QUE SE EJECUTAN: un invariante que devuelve la lista vacia, un filtro que
# nunca casa, una lista de dos ficheros, un limite que nunca corta, una lista
# de campos con dos copias iguales.
#
# Y esta es la primera sobre una ruta QUE NO SE EJECUTA: el mensaje de error.
#
# O sea: hay codigo cuyo unico trabajo es hablar cuando algo va mal, y no hay
# nada que lo compruebe. Y un fallo ahi es doble — no sale el diagnostico, y
# sale otro fallo que no menciona el problema—, de modo que es PEOR que no
# tener fallo ahi.
#
# Y POR QUE NO SE CIERRA MIRANDO LOS MENSAJES
#
# Porque un mensaje de asercion hay que METERLO en un fallo para verlo. Y eso
# se puede hacer sin que nada falle de verdad: se construye el mensaje con
# argumentos DE MENTIRA y se ve si revienta. Que es un test que falla a
# proposito para poder leerse.
#
# Y LA FORMA DE QUE NO CUENTE MAL: NO CUENTA NADA
#
# La idea obvia es contar los especificadores de la plantilla con una
# expresion regular y dar tantos argumentos falsos como haya. MEDIDO: eso es
# exactamente el error que se busca detectar —contar mal un formato—, y
# ponerlo en el comprobador que existe para detectar eso es meter el defecto
# dentro del detector.
#
# La forma que no cuenta nada es PREGUNTAR:
#
#     '%s' % ()       -> TypeError: not enough arguments for format string
#     '%s' % (x, y)   -> TypeError: not all arguments converted
#
# O sea que con `%` solo hay un numero de argumentos que funciona, y se
# encuentra probando. Y asi el comprobador no sabe nada de formatos: no puede
# equivocarse al contarlos porque no los cuenta.
#
# Y MENTRAS LO MEDIA, EL DEFECTO ENCONTRO A QUIEN LO BUSCABA
#
# MEDIDO, tres veces, en el propio script que media: `'... (`cadena % algo`):
# %d' % n` revienta, y `'... % algo ...' % n` revienta, y
# `'... `algo + % + algo`: %d' % n` revienta. Las tres por escribir un `%`
# literal en una cadena que se despues se formatea, donde hace falta `%%`.
#
# O sea que el fallo no es raro: es facil, y se cuela en el fichero que existe
# para buscarlo. Que es la mejor noticia posible sobre el valor de buscarlo.

# Donde mira el comprobador, y MEDIDO antes de decidirlo:
#
#     tools     109 ficheros   290 plantillas   1 rota
#     motor      68 ficheros    85 plantillas   0 rotas
#     recorder    4 ficheros     1 plantilla    0 rotas
#     .           1 fichero      0 plantillas   0 rotas
#
# O sea que la unica rota esta en `tools/`, que es mio. Y el alcance es
# `tools/` porque `motor/`, `data/` y `asistente_live.py` no son mios — no
# porque se banquen, sino porque no se tocan. Y se declara porque un
# comprobador que mira de mas no es riguroso: es un boiled que espera a que
# alguien toque lo que no debe.
CARPETA_DE_MENSAJES = 'tools'

# El suelo del numero de plantillas que el barrido tiene que encontrar.
#
# Y POR QUE HACE FALTA: porque un barrido que devuelve la lista vacia pasa
# igual que uno que encuentra 290. Y esa es la version de este bloque del
# «una comprobacion que no mide nada da verde»: si el patron deja de casar
# —porque se toco el arbol, porque se cambio una comilla, porque alguien
# reescribio el mensaje con f-string— el comprobador se quedaria callado y en
# verde.
#
# MEDIDO: 290 en `tools/`. El suelo esta por debajo a proposito, para que un
# cambio que borre la mitad de los mensajes no lo tumbe.
PLANTILLAS_MINIMAS = 200


class _Mentira(object):
    """Un valor que se deja formatear de cualquier manera.

    Y MEDIDO, que es lo que obliga a esto: el repo usa `%s` x180, `%d` x99,
    `%r` x98, `%f` x21 y `%n` x3.

    Un dummy de cadena revienta en `%f`, porque `%f` llama a `float()`, y
    `%c` exige un entero de 0 a 255. O sea que un dummy de cadena daria
    fallos que NO son del mensaje, y un test que falla por culpa de su propio
    instrumento es un test que no sirve.

    MEDIDO, y por eso existen los dos metodos:

        %s -> 'x'      %d -> '0'      %r -> 'x'      %f -> '0.000000'
        %c -> '\x00'   %x -> '0'      %e -> '0.000000e+00'

    Y `%n` NO aparece en la lista, porque no se puede construir: es el
    defecto."""

    def __float__(self):
        return 0.0

    def __index__(self):
        return 0


def _sin_percent_escapado(plantilla):
    """La plantilla con los `%%` YA INTERPRETADOS.

    Y por que hace falta, MEDIDO: `'%(' in '%%(nombre)s'` es True, porque la
    subcadena aparece en la segunda posicion. O sea que una comprobacion que
    busca `%(` sin quitar antes los `%%` ve una especificacion con nombre donde
    lo unico que hay es un percent escrito dos veces.

    Y no es un detalle de esta comprobacion: es del LENGUAJE. `%%` no consume
    argumento y no abre especificacion, asi que buscar especificadores sobre
    una plantilla donde hay `%%` escaped es buscar sobre el texto equivocado.

    Y la tercera vez en este bloque que hay que hacer esto —la primera en el
    texto, la segunda en el barrido de las 290 plantillas, esta en el
    comprobador—, y las tres se olvidaron la primera. O sea que no es un
    descuido: es que `%%` es una cosa del lenguaje que se olvida.

    Y por eso es una FUNCION y no un `.replace` en cada sitio: para que el
    cuarto sitio la use sin volver a decidir si hay que hacerlo."""
    return plantilla.replace('%%', '')


# ============================ 20. EL TOPE, EL ALCANCE, Y LOS SITIOS VIVOS
#
# R2, punto 1, y es real:
#
#     for cuantos in range(tope):
#
#     Con tope=16 el bucle prueba de 0 a 15 argumentos. Una plantilla válida
#     que necesite exactamente 16 argumentos nunca se probará con el número
#     correcto y se declarará rota.
#
#     plantilla = ' '.join(['%s'] * 16)
#
# MEDIDO, con la version que estaba en el repo:
#
#      1 especificadores: -> 1
#     15 especificadores: -> 15
#     16 especificadores: -> None    <<< PLANTILLA VALIDA DECLARADA ROTA
#     17 especificadores: -> None
#
# Y ES PEOR QUE EL LIMITE DE PROFUNDIDAD DEL BLOQUE ANTERIOR, por una razon que
# conviene decir porque son los dos limites y solo uno puede constructirse:
#
#     el limite de profundidad contestaba «no hay camino» —una respuesta FALSA
#     sobre una pregunta que con otro limite era CIERTA—.
#
#     el `tope` contesta «esta rota» —una respuesta FALSA sobre una plantilla
#     que esta BIEN—.
#
# O sea que produce exactamente lo que busca el detector: un diagnostico que
# no describe el problema. Salvo que aqui el diagnostico sale del DETECTOR, y
# por tanto se leeria como si el fallo fuera real.


def _argumentos_para(plantilla):
    """Cuantos argumentos hay que darle a `plantilla` para construirla.

    Y None si no se puede construir con NINGUN numero — que es lo que significa
    «esta plantilla esta rota», y es una afirmacion MAS FUERTE que la que hacia
    antes: antes queria decir «no se pudo con hasta 16».

    LA COTA SE DERIVA, Y POR QUE NO PUEDE QUEDAR CORTA

    Un especificador ocupa POR LO MENOS dos caracteres —`%s`— y `%%` ocupa dos
    sin consumir argumento. O sea que una plantilla de longitud L no puede
    tener mas de L // 2 especificadores, y por tanto

        range(L // 2 + 1)

    es una cota que no puede quedar corta. Y se deriva de la propia plantilla,
    que es lo unico que se puede derivar sin escribir un numero a mano.

    MEDIDO, y no solo en el borde de 16 —que es donde se ve el fallo— sino en
    ocho, para que no sea un caso elegido:

          1 espec. (L=  2)   tope=16 -> 1        derivada -> 1
          2 espec. (L=  5)   tope=16 -> 2        derivada -> 2
          5 espec. (L= 14)   tope=16 -> 5        derivada -> 5
         16 espec. (L= 47)   tope=16 -> None     derivada -> 16
         17 espec. (L= 50)   tope=16 -> None     derivada -> 17
         40 espec. (L=119)   tope=16 -> None     derivada -> 40
        100 espec. (L=299)   tope=16 -> None     derivada -> 100
        250 espec. (L=749)   tope=16 -> None     derivada -> 250

    MEDIDO, el coste: 302 plantillas. 4832 intentos con el tope y 14543 con
    la cota derivada. Los dos barren el fichero entero en 1.0 ms.

    O sea que la cota no cuesta nada, que es lo que hace falta para que no
    haya excusa de dejar el numero puesto a mano.

    Y EL ARREGLO MINIMO DE R2, Y POR QUE NO BASTA

        for cuantos in range(tope + 1)

    MEDIDO:

        16 especificadores con tope=16:  antes -> None    con `+1` -> 16
        17 especificadores con tope=16:  antes -> None    con `+1` -> None

    O sea que quita UN numero y deja el problema donde estaba: un numero
    puesto a mano que puede volver a quedar corto. Y el comentario pasaria a
    decir «hasta 16» cuando lo que el codigo garantiza es «lo que quepa en 16
    intentos», que es una promesa mas debil.

    Y el `tope` no protege de nada: solo DEJA DE MIRAR. Que es la frase del
    limite de profundidad, y aqui si se puede demostrar el caso, que alli no.

    Y LA PROMESA DE ESTE `None`, Y LO QUE DEPENDE

    Que devuelva `None` significa «no se puede construir con NINGUN numero de
    argumentos». Y eso son DOS afirmaciones, y solo la primera esta medida:

        «el bucle no se queda corto»      -> medida, y es lo que arregla esto
        «todo None es una plantilla rota» -> depende de lo que se capture

    MEDIDO, con 23 plantillas que usan todos los especificadores y banderas que
    acepta el operador de formato:

        23 plantillas probadas
        fugas FUERA de (TypeError, ValueError): 0

    O sea que capturar solo esas dos no deja pasar nada por fuera, y por tanto
    la afirmacion se sostiene para el alcance declarado —los mensajes de este
    repo—, que es el unico que necesita un detector con alcance sobre
    `tools/`.

    Y LO QUE NO SE HA MEDIDO: que no exista un formato mal formado que de otra
    excepcion. Eso es una afirmacion sobre el LENGUAJE, y aqui se ha medido el
    REPO. Que es un limite del alcance, y los limites se declaran.

    Y POR QUE LA SALIDA, SI EXISTIERA, SERIA RUIDOSA Y ESO ES LO BUENO

    Una excepcion distinta se PROPAGARIA, porque el `except` es
    `(TypeError, ValueError)` y no `Exception`, y el fallo seria `KeyError` o
    lo que sea, en el test. O sea que no es un `None` que significara otra
    cosa: es un fallo que se ve.

    Y conviene decir POR QUE antes de que alguien lo cambie por un
    `except Exception` para «ser mas robusto»:

        un `except Exception` aqui convertiria un fallo ruidoso en un `None`,
        y un `None` significa «plantilla rota». O sea que el arreglo de
        robustez convertiria una verdad en una mentira, y nadie lo veria.

    Que es el patron del bloque por dentro: una comprobacion que se ensancha
    para que no falle nunca, y que deja de poder fallar."""
    for cuantos in range(len(plantilla) // 2 + 1):
        try:
            plantilla % tuple(_Mentira() for _ in range(cuantos))
        except (TypeError, ValueError):
            continue
        return cuantos
    return None


def _plantilla_de(mensaje):
    """La CADENA de un mensaje con formato, o None si no es un mensaje.

    Y hay una funcion y no dos, porque `assert x, 'a %s' % y` y
    `raise E('a %s' % y)` son la MISMA cosa —una plantilla— en dos sintaxis
    distintas, y tratarlas por separado es como tratar por separado las dos
    ramas de una misma condicion.

    Y el alcance de esta funcion, medido:

        `assert`      -> `msg` es un `BinOp %`
        `raise E(...)` -> `exc.args[0]` es un `BinOp %`

    Y lo demas se queda fuera a proposito: un `raise 'texto' % x` no es Python
    valido, de modo que la plantilla de un `raise` solo puede estar en el
    primer argumento de la llamada. No es una limitacion que se imponga: es la
    unica forma que hay."""
    if not (isinstance(mensaje, ast.BinOp)
            and isinstance(mensaje.op, ast.Mod)):
        return None
    izquierda = mensaje.left
    if not (isinstance(izquierda, ast.Constant)
            and isinstance(izquierda.value, str)):
        return None
    if '%' not in izquierda.value:
        return None
    return izquierda.value


def _plantillas_de(fuente):
    """Los mensajes con formato de UNA fuente, CON SU CLASE.

    Y la clase sale del ARBOL, y esa es toda la diferencia con la version que
    la adivinaba por el texto.

    MEDIDO, y no es un defecto latente:

        hallazgos por el ARBOL:  336
        hallazgos por el TEXTO:  336
        DESACUERDOS:            1
            test_ejecutar_pytest.py:3265   de verdad assert  por texto raise

    La linea 3265 era un `assert` cuyo MENSAJE empieza por «el barrido deberia
    encontrar al menos 20 `raise`» — de modo que la palabra «raise» estaba en la
    linea y el `assert` se contaba como un `raise`.

    O sea que el fallo mas incomodo posible: la comprobacion que vigila al
    clasificador estaba ella misma mal clasificada, y por eso el suelo de 20 se
    estaba comprobando con un dato contaminado. Los dos numeros reales eran 25
    `raise` y 311 `assert`, no 26 y 310.

    MEDIDO, Y LA DIRECCION QUE NO EXISTE

    La direccion contraria —un `raise` clasificado como `assert`— NO se puede
    producir: `Raise.lineno` es la linea de la palabra `raise`, y ahi la palabra
    esta. MEDIDO con un `raise` partido en tres lineas: sigue aciertando.

    O sea que el fallo era de una sola direccion, y eso solo se sabe midiendo. Lo
    razonable sin medir seria decir «va en las dos direcciones», que habria sido
    la mitad de verdad.

    Y POR QUE UNA FUNCION Y NO UN `for` DENTRO DEL BARRIDO

    Porque hay que poder darle una fuente INVENTADA. `_mensajes_plantilla()` lee
    ficheros del disco y no se puede comprobar con un caso escrito a mano; esta
    recibe texto y si. Que es el mismo motivo por el que el guardia de control
    salio del test: una comprobacion que solo se puede ejecutar contra el
    repositorio tiene dientes para el repositorio y ninguno para si misma.

    Y LA PREGUNTA DE R2: ¿PASARLE `filename` A `ast.parse`?

    MEDIDO: con `filename` el `SyntaxError` de Python SI nombra el fichero.

        sin filename   -> invalid syntax (<unknown>, line 1)
        con filename   -> invalid syntax (ruta/roto.py, line 1)

    O sea que la via que describe R2 es real, y funciona.

    Y NO se anade, por un motivo MEDIDO y no supuesto: los dos unicos
    llamadores de esta funcion son el barrido —que captura el `SyntaxError` y
    escribe su mensaje, que empieza por el nombre del fichero— y el test de los
    disfraces, que pasa texto en memoria y no tiene nombre que dar.

    O sea que no hay llamador de produccion a quien `filename` le aportase
    algo: el mensaje propio ya dice cual es el fichero, que es el dato que con
    109 ficheros en el alcance importa.

    Y lo que SI seria motivo para volver a mirarlo: que aparezca un llamador que
    pase texto de un fichero y NO capturare el `SyntaxError`. O sea, un
    criterio y no una intencion — que es la diferencia entre «no se anade» y
    «no se anade aun».

    Y que la decision estuviera tomada en un script de medicion es la misma
    forma que las cifras duplicadas del inventario: algo que el codigo hace,
    dicho en un sitio al que nadie vuelve.

    Y MEDIDO, y por que el texto no valia: el texto de una linea contiene el
    mensaje del assert, sus comentarios, y la palabra que se le parezca. O sea que
    «¿esta linea es un raise?» tiene tres respuestas posibles y la pregunta solo
    tiene dos."""
    salida = []
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.Assert) and nodo.msg is not None:
            plantilla = _plantilla_de(nodo.msg)
            if plantilla is not None:
                salida.append(('assert', nodo.lineno, plantilla))
        elif isinstance(nodo, ast.Raise) and nodo.exc is not None:
            exc = nodo.exc
            if isinstance(exc, ast.Call) and exc.args:
                plantilla = _plantilla_de(exc.args[0])
                if plantilla is not None:
                    salida.append(('raise', nodo.lineno, plantilla))
    return salida


def _mensajes_plantilla(carpeta=None):
    """Los mensajes que se construyen SOLO cuando algo va mal. Y no solo los
    de `assert`.

    Y POR QUE RECIBE UNA CARPETA, y no es comodidad

    MEDIDO: sin el no hay forma de dirigir el barrido a un
    directorio inventado, y sin eso esta comprobacion no
    se puede ejecutar fuera del repositorio. Que es el mismo
    hueco que el del guardia de control, y con el mismo
    arreglo: una pieza a la que se pueda llamar con un
    caso inventado.

    Y el cambio es el del punto 2 de R2, que decia: el alcance son solo los
    `assert`, y el nombre del test puede leerse mas amplio que su
    implementacion. MEDIDO antes de decidirlo:

        tools     raise: 39    con formato: 25   rotas: 0
        motor     raise: 72    con formato: 14   rotas: 0
        recorder  raise:  2    con formato:  0   rotas: 0

    Y aqui esta la razon de cerrarlo. Un `raise` con formato es la MISMA clase
    de ruta que un `assert` con formato: codigo que solo se ejecuta cuando algo
    va mal. O sea que la exclusion no era una distincion de CLASE, era una
    distincion de SINTAXIS.

    Y una distincion de sintaxis se sostiene en una sola cosa: que no haya
    ningun caso. MEDIDO: hay 25 en `tools/`, que es mio.

    O sea que el hueco estaba declarado y VACIO, y «vacio» no es «no puede
    pasar»: es «hoy no pasa». Y con 25 sitios, «hoy» es un tecnicismo.

    Y el alcance se queda en `tools/`, por la razon de siempre: `motor/`,
    `data/` y `asistente_live.py` no son mios. Sus 14 raises con formato se
    declaran, no se comprueban — y declarar un hueco que existe es distinto de
    dejar de mirar un hueco que existe: el primero esta escrito, el segundo
    se Vera cuando alguien lo rompa.

    Y el nombre. `test_los_mensajes_de_fallo_se_pueden_construir` sigue igual,
    y ahora dice lo que dice: mensajes de fallo, de `assert` y de `raise`, de
    `tools/`. Lo que NO garantiza —y hay que decirlo porque R2 tiene razon en
    que el nombre se prestaba a leer mas— es:

        - que la plantilla se construya con MENTIRAS, no con los valores
          reales. Una plantilla bien formada que al ejecutarse lance por otra
          cosa —un `%s` sobre un objeto sin `__str__`— no se ve aqui.
        - nada de `pytest.raises`, ni de `warnings.warn`, ni de `print`. Que
          son las tres rutas que quedan por mirar, y son OTRA TAREA con su
          propio corpus, no un parche de este detector."""
    if carpeta is None:
        carpeta = os.path.join(ROOT, CARPETA_DE_MENSAJES)
    assert os.path.isdir(carpeta), (
        'la carpeta de mensajes tiene que existir, y no existe: %s. Un barrido '
        'sobre una carpeta que no esta encuentra cero plantillas, CERO, y con '
        'cero todo pasa. O sea que el fallo de esta comprobacion es el verde.'
        % carpeta)
    encontrados = []
    for nombre in sorted(os.listdir(carpeta)):
        if not nombre.endswith('.py'):
            continue
        ruta = os.path.join(carpeta, nombre)
        # Y DOS EXCEPCIONES EN DOS OPERACIONES, que es lo que R2 senala y
        # lo que este bloque habia desincronizado.
        #
        # MEDIDO, antes, con un directorio inventado:
        #
        #     uno bien             -> NO FALLO
        #     sintaxis invalida    -> SyntaxError de Python   nombra el
        #                              fichero: False
        #     no es utf-8          -> mi AssertionError       nombra el
        #                              fichero: True
        #
        # O sea que de las DOS palabras del except una seguia viva y la
        # otra era adorno: el parse se habia ido dentro de
        # `_plantillas_de`, que se llama DESPUES del try. Y una palabra
        # del except no sobra por vieja: sobra porque la operacion que
        # puede darla ya no esta dentro.
        #
        # Y por que importa mas de lo que parece: mi mensaje dice «no se
        # ha podido NI LEER» y escribe el nombre del fichero; el
        # SyntaxError de Python dice «invalid syntax» y la posicion, y NO
        # el nombre. Con 109 ficheros en el alcance, un fallo sin nombre
        # es un fallo que obliga a buscar.
        try:
            fuente = io.open(ruta, encoding='utf-8').read()
        except UnicodeDecodeError as e:
            raise AssertionError(
                '%s no se ha podido LEER (%s). Un fichero que no se lee no se '
                'mira, y un fichero que no se mira no aparece en el barrido, y '
                'eso es verde por no mirar. Por eso aqui no se salta: se '
                'para.' % (nombre, e))
        try:
            plantillas = _plantillas_de(fuente)
        except SyntaxError as e:
            raise AssertionError(
                '%s tiene SINTAXIS INVALIDA (%s). MEDIDO, antes: el except de '
                'este bloque llevaba SyntaxError junto a UnicodeDecodeError, '
                'pero el parse estaba DENTRO de la llamada que esta despues '
                'del try. O sea que la palabra no sobraba por vieja: sobraba '
                'porque la operacion que puede dar esa excepcion ya no estaba '
                'dentro. Y una lista de excepciones que no corresponde con su '
                'bloque tiene una rama que es adorno, que es peor que un '
                'except que falta, porque parece que hay una comprobacion.'
                % (nombre, e))
        for clase, numero, plantilla in plantillas:
            encontrados.append((clase, nombre, numero, plantilla))
    return encontrados


def test_los_mensajes_de_fallo_se_pueden_construir():
    """El camino que no se ejecuta, ejecutado de mentira.

    Y ahora `raise` tambien, y la razon por la que antes no estaba es que no
    habia motivo — no que fuera otra clase de ruta. MEDIDO: `tools/` tiene 25
    `raise` con formato, y un `raise` con formato es exactamente lo mismo que
    un `assert` con formato: codigo que solo se ejecuta cuando algo va mal.

    Y el alcance se queda en `tools/`: `motor/` tiene 14 mas, y no son mios.

    Y lo que este test NO garantiza, que es lo que R2 tiene razon en que el
    nombre prestaba a leer mas:

        - que la plantilla se construya con MENTIRAS, no con los valores
          reales. Una plantilla bien formada que al ejecutarse lance por otra
          cosa no se ve aqui.
        - nada de `pytest.raises`, `warnings.warn` ni `print`. Que son tres
          rutas mas, y son otra tarea con su propio corpus."""
    sin_diccionario = []
    rotas = []
    for _clase, nombre, linea, plantilla in _mensajes_plantilla():
        if '%(' in _sin_percent_escapado(plantilla):
            # MEDIDO: CERO en el repo. Y no se puede construir con una tupla
            # de mentiras, porque `%(nombre)s` pide un DICCIONARIO. O sea
            # que si aparece uno, el comprobador lo declararia roto sin
            # serlo — y por eso se cuenta aqui, para que la lista de lo que
            # no se mira no crezca en silencio.
            sin_diccionario.append((nombre, linea))
            continue
        if _argumentos_para(plantilla) is None:
            rotas.append((nombre, linea, plantilla))
    assert not sin_diccionario, (
        'aparecen %d mensajes con `%%(nombre)s`, que necesitan un DICCIONARIO '
        'y no una tupla. MEDIDO: no habia ninguno hasta que aparecio este. O '
        'sea que el comprobador tiene que aprender a construirlos antes de '
        'que se cuele uno: un comprobador que declara roto lo que no lo esta '
        'es peor que uno que no mira.'
        % len(sin_diccionario))
    assert not rotas, (
        'hay %d mensajes de asercion que NO se pueden construir, y son la '
        'razon de existir de este bloque:%s\n\n'
        'Que es lo que hace un fallo en un mensaje: en vez del diagnostico, '
        'otro fallo que no menciona el problema. Y en el caso de una prueba '
        'que existe para detectar un cambio futuro del AST, es la razon por '
        'la que no podria hacer su trabajo.\n\n'
        'MEDIDO, el tipo de excepcion importa: un `%%n` con dos `%%s` delante '
        'da TypeError y no ValueError, porque los dos `%%s` se han comido los '
        'argumentos. Y el mensaje de ese error dice «not enough arguments», '
        'que no menciona ni el especificador ni las clases.'
        % (len(rotas),
           chr(10).join('    %s:%d  %s' % (n, l, t.replace(chr(10), ' ')[:70])
                        for n, l, t in rotas)))


def test_el_comprobador_de_mensajes_tiene_dientes():
    """Que `_argumentos_para` distinga de verdad, y no solo con lo que hay.

    Y POR QUE HACE FALTA, que es lo importante: MEDIDO, el barrido de
    `tools/` encuentra UNA plantilla rota, y es la que R2.signaló. O sea que
    un comprobador que encuentra exactamente el defecto para el que se
    escribio no tiene NINGUNA evidencia de que encontraria otro mañana.

    Y esa es la septima vez con la forma, en su version mas debil: no es que
    la comprobacion mida mal, es que no se ha visto medir NADA MAS que lo
    previsto.

    Y por eso este test: le da plantillas rotas A PROPOSITO y comprueba que las
    ve. Que es lo que hay que hacer con un detector: darle un caso que lo
    mate, y comprobar que lo ve."""
    rotas = ('%n', '%s %n', '%.3q', '%d %r %s %n')
    for plantilla in rotas:
        assert _argumentos_para(plantilla) is None, (
            '`_argumentos_para(%r)` ha dicho que se puede construir con %d '
            'argumentos. O sea que el comprobador que existe para encontrar '
            'formatos rotos no los ve. Y eso no es un fallo de la plantilla '
            'de ejemplo: es un fallo del comprobador, que es lo unico que '
            'esta en juego.'
            % (plantilla, _argumentos_para(plantilla)))
    buenas = ('%s', '%d y %r', '%%', '%s%%', '%f', '%.3f', '%s y %s',
              'no hay nada que formatear')
    for plantilla in buenas:
        assert _argumentos_para(plantilla) is not None, (
            '`_argumentos_para(%r)` ha dicho que NO se puede construir. Y '
            'esa plantilla se construye, de sobra. O sea que el comprobador '
            'daria un fallo sobre un mensaje que esta bien, y eso lo hace '
            'inutil: un comprobador que tambien falla cuando todo va bien '
            'enseña a no fiarse de el.' % plantilla)


def test_el_comprobador_de_mensajes_no_puede_devolver_nada():
    """Y que el barrido no pueda quedarse vacio en verde.

    Y esta es la version MAS DEBIL de la septima vez, y por eso va aparte: las
    otras seis comprobaciones fallaban cuando la condicion se cumplia mal.
    Esta podria pasar sin comprobar NADA, y pasaria si el patron dejara de
    casar — porque se haya cambiado una comilla, porque el mensaje se haya
    pasado a f-string, porque el arbol haya cambiado.

    MEDIDO: 290. El suelo es 200, por debajo a proposito, para que un cambio
    que borre la mitad de los mensajes lo tumbe y no lo deje pasar."""
    encontrados = _mensajes_plantilla()
    assert len(encontrados) >= PLANTILLAS_MINIMAS, (
        'el barrido ha encontrado %d plantillas y el suelo es %d. MEDIDO: '
        'eran 290. O sea que el barrido ha dejado de encontrar mensajes, y '
        'un barrido que no encuentra nada no falla: es exactamente el caso '
        'para el que hace falta el suelo, porque en verde no se distingue '
        '«no hay ninguno» de «no se miró ninguno».'
        % (len(encontrados), PLANTILLAS_MINIMAS))


# ============================ 18. LA CONSTANTE, EN LAS DOS DIRECCIONES
#
# R2, punto 2: la lista de la produccion y la lista que valida la prueba
# tienen que dejar de ser dos fuentes independientes. Y R1 lo dicta como
# cuatro comprobaciones:
#
#     La implementación usa CAMPOS_RECORRIDOS, no un literal propio.
#     No hay dos listas idénticas en test_ejecutar_pytest.py.
#     Si se añade un campo a CAMPOS_RECORRIDOS, la implementación lo recorre.
#     Si se quita un campo, la implementación deja de recorrerlo.
#
# Y LAS DOS ULTIMAS, MEDIDAS, Y NO SON LO QUE PARECEN
#
# Lo facil — y lo que haria el_array de siempre— es comprobar que la
# implementacion MENCIONA la constante. MEDIDO: eso ya se cumple, y en efecto
# no la menciona porque usa la constante. Y un test que comprueba que se
# menciona una constante es un test que pasaria igual que si la usara con la
# palabra puesta delante: porque mencionarla es lo mas facil que hay.
#
# O sea que el test tiene que distinguir USARLA de MENCIONARLA, y la unica
# forma es cambiar la constante y ver si el COMPORTAMIENTO cambia.
#
# Y LA DIRECCION DE QUITAR UN CAMPO TIENE CASO REAL; LA DE ANADIR, NO
#
# MEDIDO: en `ast` no hay ningun campo fuera de los cinco que guarde
# sentencias. Los que podrian —Match, match_case, ExceptHandler, Module,
# Expression— guardan sentencias en `cases`, `body`, `finalbody` o `handlers`,
# que ya estan. Y los de ambito son PARADAS.
#
# O sea que con `ast` de verdad NO HAY CASO donde anadir un campo cambie una
# respuesta. Y eso es, de rebote, la confirmacion de que la derivacion
# acertaba: los cinco campos son los cinco.
#
# Y por eso la direccion de anadir necesita un nodo SINTETICO, y hay que
# decirlo con nombre. Un nodo `ast` con un campo que `ast` no define en
# ninguna clase:
#
#     sin el campo    -> 0 import(s)    no lo encuentra
#     CON el campo    -> 1 import(s)    LO ENCUENTRA
#
#     con `cases`     -> 1 import(s)    LO ENCUENTRA
#     sin `cases`     -> 0 import(s)    no lo encuentra
#
# Y las dos direcciones se distinguen POR COMPORTAMIENTO. Que es lo unico que
# no puede pasar por «se menciona la constante».


class _NodoConCampoPropio(ast.AST):
    """Un nodo de `ast` con un campo que `ast` no define en ninguna clase.

    Y esto NO es un truco para hacer pasar un test: es la unica forma de
    comprobar la direccion de «anadir un campo», porque MEDIDO no existe en
    `ast` ningun campo de sentencias fuera de los cinco.

    Y el nombre lo dice, para que nadie lo lea dentro de un dia como si fuera
    un caso real del detector: `_NodoConCampoPropio`, y aqui."""
    _fields = ('body', 'instruccion')


def _arbol_con_campo_propio():
    """Un modulo con un nodo que tiene un campo `instruccion` con un import."""
    importacion = ast.Import(names=[ast.alias(name='ejecutar_pytest',
                                              asname=None)])
    nodo = _NodoConCampoPropio()
    nodo.body = []
    nodo.instruccion = [importacion]
    return ast.fix_missing_locations(ast.Module(body=[nodo], type_ignores=[]))


def _imports_de_modulo(arbol):
    """Los `ast.Import` que el recorrido encuentra en `arbol`."""
    return [nodo for nodo in _imports_de_nivel_de_modulo(arbol)
            if isinstance(nodo, ast.Import)]


def test_anadir_un_campo_a_la_constante_hace_que_la_implementacion_lo_recorra(
        monkeypatch):
    """La primera de las dos direcciones, y la que necesita el nodo sintetico."""
    original = CAMPOS_RECORRIDOS
    monkeypatch.setitem(globals(), 'CAMPOS_RECORRIDOS', original)
    sin_campo = len(_imports_de_modulo(_arbol_con_campo_propio()))
    monkeypatch.setitem(globals(), 'CAMPOS_RECORRIDOS',
                        original + ('instruccion',))
    con_campo = len(_imports_de_modulo(_arbol_con_campo_propio()))

    assert sin_campo == 0, (
        'sin `instruccion` en la constante, el recorrido deberia ignorar ese '
        'campo, y encuentra %d. O sea que la implementacion esta recorriendo '
        'un campo que la constante no declara — que es el otro sentido del '
        'mismo fallo: no es que las dos listas se separen, es que la '
        'implementacion tiene su propia lista dentro.' % sin_campo)
    assert con_campo == 1, (
        'con `instruccion` en la constante, el recorrido deberia encontrar el '
        'import que hay en ese campo, y encuentra %d. O sea que la '
        'implementacion NO esta leyendo la constante: la menciona y sigue '
        'con su propia lista. Y es exactamente el defecto que este bloque '
        'arranco arreglando, en la direccion contraria.' % con_campo)


def test_quitar_un_campo_de_la_constante_hace_que_la_implementacion_lo_olvide(
        monkeypatch):
    """La segunda direccion, y aqui si hay un caso REAL de `ast`.

    MEDIDO: con `cases` en la constante, el import dentro de un `case` de
    `match` se encuentra; sin `cases`, no. Y `match` no abre ambito — es una
    condicion mas—, de modo que ese import SI liga el nombre en el modulo y
    perderlo es perder un enlace de verdad."""
    match = ast.parse('match x:' + chr(10)
                      + '    case 1:' + chr(10)
                      + '        import ejecutar_pytest' + chr(10))
    monkeypatch.setitem(globals(), 'CAMPOS_RECORRIDOS', CAMPOS_RECORRIDOS)
    con_cases = len(_imports_de_modulo(match))
    monkeypatch.setitem(globals(), 'CAMPOS_RECORRIDOS',
                        tuple(c for c in CAMPOS_RECORRIDOS if c != 'cases'))
    sin_cases = len(_imports_de_modulo(match))

    assert con_cases == 1, (
        'con `cases` en la constante, el import dentro del `case` tiene que '
        'aparecer, y aparecen %d. O sea que el caso de `match/case` ha '
        'dejado de cubrirse, y no porque `match` haya cambiado: porque la '
        'constante ya no dice que se recorra.' % con_cases)
    assert sin_cases == 0, (
        'sin `cases` en la constante, el recorrido deberia ignorar `cases`, y '
        'encuentra %d. O sea que quitar un campo de la constante no quita el '
        'campo del recorrido, que es la forma de que las dos listas vuelvan a '
        'ser dos — y ahi la separacion seria SILENCIOSA, porque el '
        'comprobador seguiria mirando la constante y el codigo seguiria '
        'mirando la suya.' % sin_cases)


def test_no_hay_dos_listas_identicas():
    """Y que no quede una segunda lista de campos escrita a mano.

    MEDIDO, ANTES del arreglo de este bloque:

        implementacion: for atributo in ('body', 'orelse', 'finalbody',
                                          'handlers', 'cases'):
        constante:      CAMPOS_RECORRIDOS = ('body', 'orelse', 'finalbody',
                                              'handlers', 'cases')

    DOS LITERALES IGUALES. Y esa era la sexta vez con la forma, y la primera
    en que las dos listas eran iguales: en las otras cinco se diferenciaban en
    el contenido y aqui se diferencian en que son dos, lo cual es peor porque
    a simple vista es indistinguible.

    Y por eso este test mira el TEXTO, aunque los otros dos de esta seccion
    miran el COMPORTAMIENTO: porque lo que se quiere comprobar aqui es
    literalmente que no exista una segunda COPIA, y una copia es una cosa de
    texto. El comportamiento no la ve — una copia produce el mismo
    comportamiento—, y es por eso que este caso necesita el otro metodo y no
    el de al lado.

    Y el limite: se mira ESTE fichero. Una copia en otro fichero no se ve,
    y es un hueco declarado."""
    cuerpo = io.open(__file__, encoding='utf-8').read()
    # Y POR EL ARBOL Y NO POR EL TEXTO, que es lo que hacia antes y fallaba.
    #
    # MEDIDO, el fallo: el patron de texto encontraba 3 y hay 1. Los otros
    # dos eran el bloque 18 CITANDO el defecto, y una cita de un defecto es
    # texto igual que el defecto. Que es la novena vez con la misma forma, y
    # con un matiz que no tenian las otras ocho: las otras contaban la cosa
    # mala por error; esta contaba la cosa BUENA por error.
    #
    # Y lo que las distingue es la ESTRUCTURA: una frase citada en un
    # docstring es un `ast.Constant`; una copia de la lista es una
    # `ast.Tuple` de cinco valores, en ese orden.
    #
    # Y de rebote el arreglo cubre el caso multilinea, que el patron de
    # texto no cogia — MEDIDO, uno de los tres literales estaba partido en dos
    # lineas—, porque el arbol tiene la concatenacion implicita ya hecha.
    copia = [nodo.lineno for nodo in ast.walk(ast.parse(cuerpo))
             if isinstance(nodo, ast.Tuple)
             and len(nodo.elts) == len(CAMPOS_RECORRIDOS)
             and all(isinstance(e, ast.Constant) for e in nodo.elts)
             and tuple(e.value for e in nodo.elts) == CAMPOS_RECORRIDOS]
    assert len(copia) == 1, (
        'hay %d literales con la lista de campos completa. MEDIDO, antes: '
        'habia dos, y eran IGUALES, que es la forma peor porque a simple '
        'vista no se distinguen. O sea que la comprobacion de que la '
        'derivacion es correcta y la implementacion pueden separarse sin que '
        'nada lo note. El arreglo no es sincronizarlas: es que solo haya una.\n\n'
        'MEDIDO, y la cuenta que sale es sobre el ARBOL y no sobre el texto: '
        'una frase que cita el defecto es un `Constant`, y una copia de la '
        'lista es una `Tuple` de cinco. Por eso el numero de ahora no es el '
        'de antes.'
        % len(copia))
    assert 'CAMPOS_RECORRIDOS' in cuerpo, (
        'esto solo puede pasar si la constante ha desaparecido del fichero')


# ============================ 19. LOS CARACTERES DE CONTROL
#
# Y el defecto que cierra es del bloque anterior, y MEDIDO por que existe.
#
# En una cadena de PowerShell con comillas DOBLES el backtick es el caracter
# de escape, y ``` `X ``` produce el caracter de control ASCII de esa letra.
#
#     cadena normal      "x`ay"   ->  78 07 79    x, BEL, y
#     aqui-string        "x`ay"   ->  78 07 79    x, BEL, y
#     comillas simples   'x`ay'   ->  78 60 61 79 x, `, a, y
#
# Y MEDIDO, los cuatro casos del repo, y los cuatro empiezan por una letra que
# es un escape de PowerShell:
#
#     tools/test_ejecutar_pytest.py:1707     `ast -> 0x07   ast.FunctionDef
#     tools/auditar_preflop_varianza.py:60  `a   -> 0x07   auditar_auc.py
#     tools/equity_preflop.py:159           `b   -> 0x08   board
#     tools/test_revision2_cierre.py:41     `v   -> 0x0b   villano_del_corte
#
# Que no es casualidad: los cuatro son la MISMA causa. Y el bloque anterior
# solo arreglo uno, porque solo miro UN FICHERO — y luego escribio que no
# habia mas.
#
# Y ESO es lo que estaba mal, y no el guardia: el guardia era correcto y su
# ALCANCE decia «el repo» cuando decia «un fichero». Que es la misma forma por
# septima vez, y con un matiz que no tienen las otras seis: las otras contaban
# mal lo que miraban; esta miraba poco y decia que era mucho.
#
# Y POR QUE LEE BYTES Y NO TEXTO
#
# Un guardia que abre el fichero como texto y busca caracteres de control
# tiene un fallo: si el fichero no esta en UTF-8 la lectura revienta, y hay que
# saltarselo — y saltar un fichero es no mirarlo, que es verde por no mirar.
#
# Leyendo BYTES no hay ese fallo: no hay decodificacion que pueda fallar, y
# un byte menor de 0x20 que no sea tabulador, salto de linea ni retorno es un
# caracter de control, se mire como se mire.
#
# Y EL ALCANCE, Y POR QUE ES SOLO `.py` — y aqui esta MEDIDO, no supuesto
#
# Porque se podria pensar que el alcance es por comodidad, y no lo es.
#
# MEDIDO: cuatro ficheros de `DOCS/` tienen bytes de control, y NINGUNO es un
# defecto:
#
#     DOCS/AUDIT_NOPUEDE_ACTUAR.txt   0x00 en 3    empieza por ff fe
#     DOCS/CORRELACION_CAPTURAS.txt   0x00 en 3    empieza por ff fe
#     DOCS/baseline_folds_900.txt      0x00 en 3    empieza por ff fe
#     DOCS/INVENTARIO_MULTIWAY_HEAD.txt  0x00 en 3  empieza por ff fe
#
# Son ficheros UTF-16LE leidos como bytes: cada caracter ASCII va seguido de
# `0x00`, y el `0x14` que sale en tres de ellos es la mitad BAJA de U+2014 —la
# raya—, no un caracter de control. MEDIDO en el contexto: `1<0x14>  todo lo
# clasifico`, que es donde una raya aparece en un informe.
#
# O sea que en un `.txt` «byte menor de 0x20» y «caracter de control» NO son
# lo mismo, y un guardia que los confunda daria siete falsos positivos sobre
# ficheros que estan bien.
#
# En un `.py` SI son lo mismo: el codigo fuente de Python no puede estar en
# UTF-16 —el interprete no lo leeria—, de modo que ahi un byte de control es
# siempre un caracter de control.
#
# Y ese es el criterio del alcance: no «lo que me da la gana mirar», sino
# exactamente donde las dos cosas coinciden. Y el resto del repo se mide
# igualmente: los tres que quedaban estaban en `tools/`, y no hay ni uno en
# `motor/`, `recorder/` ni en la raiz.

CARPETAS_QUE_NO_SE_MIRAN = ('.git', '__pycache__', 'node_modules', '.pytest_cache')
BYTES_DE_CONTROL = tuple(b for b in range(0x20)
                         if chr(b) not in (chr(9), chr(10), chr(13)))


def test_no_hay_caracteres_de_control_en_ningun_fichero():
    """Lo que un guardia de UN FICHERO deja pasar, y por que esta no.

    Y que el numero de ficheros salga del MISMO recorrido que busca, no de otro
    en paralelo: un testigo que comparte el recorrido comparte el fallo.

    Y que el guardia se llame a una PIEZA y no este escrito entero aqui, que
    es lo que faltaba para que tuviera dientes: escrito entero, la unica
    forma de darle un caso es tocar el repositorio."""
    encontrados, mirados = _caracteres_de_control_en(ROOT)
    assert mirados >= 100, (
        'el recorrido ha mirado %d ficheros .py. MEDIDO: 109 en `tools/` y mas '
        'en el resto del repo. O sea que el recorrido no esta viendo todo, y '
        '«no ha encontrado nada» ha vuelto a significar «no ha mirado».'
        % mirados)
    assert not encontrados, (
        'caracteres de control en %d sitio(s):%s\n\n'
        'Y todos vienen del mismo sitio, MEDIDO: el backtick de una cadena de '
        'PowerShell con comillas dobles es un caracter de escape, y `` `X `` '
        'produce el control de esa letra. O sea que un `ast` se convierte en '
        'BEL, un `board` en BS y un `villano` en VT, sin avisar.\n\n'
        'MEDIDO: cadena normal, aqui-string y comillas dobles se comportan '
        'igual; las comillas SIMPLES dejan el backtick como backtick. O sea '
        'que hay una forma de escribirlo que no rompe nada.\n\n'
        'Y ESTA ES UNA POLITICA, no una propiedad del lenguaje: cero bytes de '
        'control en codigo fuente. Y es razonable en `.py` y no en general, '
        'MEDIDO: cuatro ficheros de `DOCS/` tienen bytes de control y ninguno '
        'es un defecto, son UTF-16LE leidos como bytes.\n\n'
        'Y el guardia del bloque anterior era correcto: lo que no era correcto '
        'era su alcance, que decia «el repo» y miraba un fichero.'
        % (len(encontrados),
           chr(10).join('    %s:%d  %s' % t for t in encontrados[:12])))


def test_el_guardia_de_control_encuentra_un_fichero_inventado():
    """La tarea 4 de R1: «si se añade un .py con control, el test falla».

    Y se comprueba con un DIRECTORIO INVENTADO, que es lo que hace posible
    dar el caso sin tocar el repositorio — y que es justo lo que antes no
    habia: el guardia estaba escrito dentro del test, de modo que la unica
    forma dedarle el caso era meter un fichero malo de verdad en el repo y
    borrarlo despues, que es una forma de romper el repo para probar que se
    rompe.

    Y el caso lleva TRES cosas a proposito, y cada una mira una parte distinta:

      - un `.py` con BEL, que es el defecto real;
      - un `.py` LIMPIO al lado, que comprueba que el recorrido no dice que
        todo esta mal porque un fichero este mal;
      - y un `.txt` con BEL, que comprueba el ALCANCE: el guardia no mira los
        `.txt`, y si los mirara daria un falso positivo sobre los UTF-16 que
        hay en `DOCS/`."""
    with tempfile.TemporaryDirectory() as alta:
        os.makedirs(os.path.join(alta, 'sub'))
        bueno = os.path.join(alta, 'limpio.py')
        malo = os.path.join(alta, 'sub', 'malo.py')
        fuera = os.path.join(alta, 'no_mirado.txt')
        io.open(bueno, 'w', encoding='utf-8').write('x = 1' + chr(10) + 'y = 2' + chr(10))
        io.open(malo, 'w', encoding='utf-8').write('z = 3' + chr(10) + chr(7) + 'w = 4')
        io.open(fuera, 'w', encoding='utf-8').write('a = 1' + chr(10) + chr(7))

        encontrados, mirados = _caracteres_de_control_en(alta)
        assert mirados == 2, (
            'el recorrido ha mirado %d ficheros y esperaba 2. MEDIDO, el caso '
            'es un `.py` limpio y un `.py` con BEL, y un `.txt` con BEL que '
            'esta FUERA del alcance. O sea que si el numero no es 2, o se '
            'estan mirando cosas que no, o no se estan mirando cosas que si.'
            % mirados)
        assert len(encontrados) == 1, (
            'MEDIDO: hay exactamente un control que el guardia debe ver, y se '
            'han encontrado %d: %r. Y el `.txt` con BEL no cuenta, porque el '
            'alcance son los `.py` — que es lo que impide el falso positivo '
            'sobre los cuatro ficheros UTF-16 de `DOCS/`.' % (
                len(encontrados), encontrados))
        assert encontrados[0][0].endswith('malo.py'), (
            'el hallazgo dice %r y el fichero con el control se llama '
            '`malo.py`. O sea que el recorrido ha atribuido el control al '
            'fichero equivocado, que es la version silenciosa de un guardia '
            'que mira de mas.' % encontrados[0][0])
        assert encontrados[0][1] == 2, (
            'el control esta en la linea 2 y el guardia dice la %d. MEDIDO: '
            'cuenta `\n` antes del byte, y eso da la linea donde ESTA el '
            'control, que no es la linea donde empieza el fichero.'
            % encontrados[0][1])


# ============================ 21. EL GUARDIA, CON DIENTES, Y LOS SITIOS VIVOS
#
# Y R1 lo dicta asi, en la tarea 4:
#
#     El guardia nuevo recorre solo .py.
#     Hay un test que verifica que recorre todos los .py (no solo uno).
#     Si se añade un .py con \x07, el test falla.
#
# Y las tres son MEDIBLES, y las tres necesitan lo mismo: separar el guardia
# en piezas, para que la PIEZA se pueda probar con un fichero inventado.
#
# Y ESO ES LO QUE FALTA, y es un hueco de la forma que ya se ha visto siete
# veces: el guardia esta escrito entero dentro del test, de modo que no hay
# forma de darle un caso sin tocar el repositorio. O sea que el test tiene
# dientes para el repositorio y ninguno para si mismo.
#
# Y LA SEGUNDA PIEZA ES OTRA COSA, Y ES LA TAREA 5 DE R1
#
#     Hay un test que verifica que las seis están bien.
#     Si se vuelve a mirar el objeto equivocado, el test falla.
#
# Y las seis fallidas eran de MI VERIFICACION, que vive en `%TEMP%` y se
# descarta. O sea que un test del repo que verifique «las seis de aquella
# verificacion» seria un test de algo que no existe.
#
# La pregunta permanente no es «estan las seis bien» sino:
#
#     ¿quedan SITOS VIVOS en el repo donde una de esas clases pueda volver a
#     pasar?
#
# Y MEDIDO, las cuatro clases de las seis, y en este fichero:
#
#     (a) texto que contiene la palabra y no es la cosa
#         MEDIDO: CERO usos como condicion. `profundidad` aparece 5 veces en
#         el fichero —en comentarios que explican el arreglo— y se usa como
#         condicion 0 veces.
#
#     (b) la ventana equivocada
#         MEDIDO: no queda sitio. El unico `rfind` vivo es el del comentario
#         de la constante, y ya sube por el bloque linea a linea.
#
#     (c) decoracion en una subcadena estable
#         MEDIDO: 0 llamadas a `find`, `rfind`, `index`, `finditer` o
#         `splitlines` con una cadena constante en el argumento. La que sufrio
#         buscaba una cabecera con su fila de `=`, y estaba en el script
#         desechable.
#
#     (d) la codificacion que hace que un fichero se salte en silencio
#         MEDIDO: CERRADA POR CONSTRUCCION. El guardia abre en BINARIO, y las
#         dos aperturas de texto son de `.py` del repo, que no pueden estar en
#         UTF-16.
#
# O sea que NO quedan sitios vivos. Y aqui esta el punto de este bloque:
#
#     una tabla con CERO filas no puede fallar, asi que no sirve como prueba.
#
# Y la solucion no es mas reglas: es que el instrumento se pruebe con un caso
# INVENTADO. Que es lo que hacen las pruebas siguientes, y sin ellas el
# inventario seria decoracion — que es, precisamente, lo que la clase (c)
# detecta: texto que parece una comprobacion y no comprueba nada.


def _bytes_de_control(crudo):
    """Los bytes de control de un fichero, con la linea de cada uno.

    Y lee BYTES, y por que: un guardia que abre el fichero como texto y busca
    caracteres de control tiene un fallo — si el fichero no esta en UTF-8 la
    lectura revienta, hay que saltarselo, y saltar un fichero es no mirarlo, que
    es verde por no mirar.

    Leyendo BYTES no hay ese fallo: no hay decodificacion que pueda fallar, y
    un byte menor de 0x20 que no sea tabulador, salto de linea ni retorno es
    un caracter de control, se mire como se mire.

    Y una cosa que esto NO es, que R2 tiene razon en que conviene decir:

        NO es una prueba de que cualquier fichero con un byte de control sea
        invalido. Es una POLITICA —cero bytes de control en codigo fuente de
        Python—.

    Y la politica es mas debil que la propiedad, y declararla es la unica forma
    de que nadie la lea como una propiedad. Que es la misma diferencia que hay
    entre «esto no se puede» y «esto no lo hacemos»: lo primero se demuestra,
    lo segundo se decide.

    Y MEDIDO, por que la politica es razonable en `.py` y no en general:

        DOCS/AUDIT_NOPUEDE_ACTUAR.txt     0x00    empieza por ff fe
        DOCS/CORRELACION_CAPTURAS.txt     0x00    empieza por ff fe
        DOCS/baseline_folds_900.txt        0x00    empieza por ff fe
        DOCS/INVENTARIO_MULTIWAY_HEAD.txt 0x00    empieza por ff fe

    Son UTF-16LE leidos como bytes, y el `0x14` de tres de ellos es la mitad
    BAJA de U+2014 —la raya—, no un control. O sea que en un `.txt` «byte
    menor de 0x20» y «caracter de control» no son lo mismo, y la politica
    tendria que ser distinta ahi. En un `.py` si son lo mismo, porque el
    codigo fuente de Python no puede estar en UTF-16."""
    salida = []
    for byte in BYTES_DE_CONTROL:
        posicion = crudo.find(bytes([byte]))
        if posicion < 0:
            continue
        salida.append((byte, crudo[:posicion].count(b'\n') + 1))
    return salida


def _caracteres_de_control_en(directorio):
    """Los bytes de control de TODOS los `.py` de `directorio` y subcarpetas.

    Y devuelve dos cosas: los hallazgos y CUANTOS ficheros ha mirado. Y las
    dos hacen falta, y por que:

      - los hallazgos, que es lo que se comprueba;
      - el numero de ficheros, que es lo que demuestra que no se miraron solo
        algunos.

    Y el numero lo da el MISMO recorrido que busca, no otro. MEDIDO, el
    argumento para que no sea el mismo: un testigo que comparte el recorrido
    comparte el fallo. Y aqui no es hipotetico — el guardia anterior miraba UN
    fichero y decia «el repo»—, pero hay un caso en que compartir es lo
    correcto y conviene nombrarlo: cuando lo que se quiere comprobar es «este
    recorrido va a este sitio», el recorrido tiene que ser el que se prueba.
    Por eso el numero va DENTRO del return y no en un segundo recorrido.

    Y que devuelva DONDE y no un booleano: un guardia que devuelve «hay un
    control» obliga a abrir el fichero a mano para saber cual; uno que devuelve
    la ruta y la linea se puede comprobar entero."""
    hallazgos = []
    mirados = 0
    for carpeta, directorios, ficheros in os.walk(directorio):
        directorios[:] = [d for d in directorios
                          if d not in CARPETAS_QUE_NO_SE_MIRAN]
        for nombre in sorted(ficheros):
            if not nombre.endswith('.py'):
                continue
            mirados += 1
            ruta = os.path.join(carpeta, nombre)
            crudo = io.open(ruta, 'rb').read()
            for byte, numero in _bytes_de_control(crudo):
                hallazgos.append((os.path.relpath(ruta, directorio), numero,
                                  '0x%02X' % byte))
    return hallazgos, mirados


def _busquedas_sobre_fuente(fuente):
    """Los sitios donde el codigo busca TEXTO en el codigo fuente de si mismo.

    Y es el inventario de la tarea 5 de R1: las clases de «mirar el objeto
    equivocado» que fallaron en la verificacion del bloque anterior.

    Y sale del ARBOL y no de un `grep`, por una razon que es la del bloque
    entero: hay que distinguir USAR una busqueda de ESCRIBIR una cadena que
    contiene un metodo. Un `grep` las ve iguales; el arbol no.

    Y el alcance, medido: llamadas a `find`, `rfind`, `index`, `finditer` y
    `splitlines` cuyo PRIMER ARGUMENTO es una cadena constante. Que es donde
    puede aparecer una decoracion —«buscar una cabecera con su fila de =»—,
    que es la clase (c).

    Y MEDIDO, lo que hay hoy en este fichero: CERO. O sea que la tabla
    declarada tiene cero filas, y una tabla con cero filas no puede fallar.

    Y por eso esta funcion existe igual: no para vigilar, sino para PODER
    PROBAR EL INSTRUMENTO con un caso inventado. Que es lo que hace
    `test_el_inventario_de_busquedas_detecta_una_decoracion`.

    Y por que el alcance no incluye `x in texto`, que es la clase (a):
    MEDIDO, hay comparaciones de esa forma y no hay ninguna viva. Declararla
    sin sitio es declarar un hueco que no existe, que es lo contrario de
    declarar."""
    encontrados = []
    METODOS = ('find', 'rfind', 'index', 'finditer', 'splitlines')
    for nodo in ast.walk(ast.parse(fuente)):
        if not (isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)):
            continue
        if nodo.func.attr not in METODOS or not nodo.args:
            continue
        arg = nodo.args[0]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            continue
        encontrados.append((nodo.lineno, nodo.func.attr, arg.value[:50]))
    return encontrados


# Las busquedas sobre fuente que este fichero ACEPTA, y por que.
#
# MEDIDO: la lista esta vacia. Y una lista vacia no es una regla: es una
# medida de hoy. O sea que el valor de tenerla escrita no es vigilar, es poder
# decir «aqui no hay ninguna, y cuando haya una, sale en el fallo».
BUSQUEDAS_ACEPTADAS = ()

def test_no_hay_busquedas_sobre_fuente_sin_declarar():
    """Que este fichero no tenga ninguna, o que la diga.

    Y MEDIDO: cero. Y por eso `BUSQUEDAS_ACEPTADAS` esta vacia, que es una
    medida de hoy y no una regla.

    Y el fallo sale aqui y no en el de la funcion, para que el nombre del test
    sea lo que hay que leer cuando algo se rompa."""
    encontradas = _busquedas_sobre_fuente(io.open(__file__,
                                                 encoding='utf-8').read())
    declaradas = tuple(sorted(BUSQUEDAS_ACEPTADAS))
    assert tuple(sorted(encontradas)) == declaradas, (
        'este fichero busca texto en su propia fuente en %d sitio(s), y hay %d '
        'declarado(s) en BUSQUEDAS_ACEPTADAS.%s\n\n'
        'O una busqueda nueva se declara y se explica —que es lo que hay que '
        'hacer si es correcta—, o se quita: una busqueda sobre el fuente es '
        'siempre una oportunidad de mirar el objeto equivocado, porque el '
        'texto contiene la palabra Y el comentario que explica el arreglo.%s\n'
        'MEDIDO, las cuatro clases que fallaron: texto con la palabra que no '
        'es la cosa, ventana que empieza donde acaba el bloque, decoracion en '
        'la subcadena, y codificacion que hace saltar el fichero. La ultima '
        'esta cerrada por construccion —el guardia abre en binario—.'
        % (len(encontradas), len(declaradas),
           chr(10).join('      linea %-5d %s(%r)' % t for t in encontradas),
           chr(10)))


def test_el_inventario_de_busquedas_detecta_una_decoracion():
    """Y que el instrumento del inventario FUNCIONE, aunque la lista este vacia.

    Y esto es lo que faltaba, y es la respuesta a la tarea 5 de R1. Una tabla
    con cero filas no puede fallar, asi que no prueba nada; lo que prueba es
    que el instrumento que contaria las filas las cuenta.

    Y el caso es la clase (c) exacta que fallo: buscar una cabecera de seccion
    con su decoracion, que es una fila de `=` que cambia con cada edicion.

    Y el contraejemplo va en la MISMA prueba, porque el remedio para una cosa
    parece arreglar la otra: buscar la palabra estable —la que NO es
    decoracion— sigue encontrandola aunque cambien los `=`. O sea que el
    arreglo no es «no uses decoraciones», que es una regla sin motivo, sino
    «busca la parte que no es decoracion», que se puede probar."""
    con_decoracion = chr(10).join([
        '# ==================== 20. EL TOPE',
        'def _algo():',
        '    s = "texto"',
        "    return s.find('# ==================== 20. EL TOPE')",
    ])
    assert _busquedas_sobre_fuente(con_decoracion), (
        'una fuente con `s.find(«# ==== 20. EL TOPE»)` —una decoracion dentro '
        'de la subcadena— no aparece en el inventario. O sea que el '
        'instrumento no cuenta lo que dice contar, y la tabla de aceptadas, '
        'aunque este vacia, no estaria vigilando nada.')

    solo_palabra = chr(10).join([
        '# ==================== 20. EL TOPE',
        'def _algo():',
        '    s = "texto"',
        "    return s.find('20. EL TOPE')",
    ])
    assert len(_busquedas_sobre_fuente(solo_palabra)) == 1, (
        'una fuente con una sola busqueda por palabra estable tiene que dar '
        'un hallazgo, y no lo da. O sea que el inventario cuenta de mas o de '
        'menos, y un inventario que cuenta mal no vigila nada.')

    limpio = chr(10).join(['def _otro(x):', '    return x'])
    assert _busquedas_sobre_fuente(limpio) == [], (
        'una fuente sin busqueda de texto tiene que dar lista vacia, y no la '
        'da. O sea que el inventario tiene un falso positivo, y una lista con '
        'falsos positivos obliga a mirar cada vez que sale uno —que es como '
        'deja de vigilarse.')

    dos = chr(10).join([
        'def _otro():',
        "    return 'texto'.index('texto')",
    ])
    assert len(_busquedas_sobre_fuente(dos)) == 1, (
        '`index` tambien es una busqueda, y una que devuelve indice en vez de '
        'posicion. MEDIDO: el inventario lo declara, y si no lo declarara el '
        'test que acabas de leer no habria detectado la diferencia entre '
        '«buscar» y «buscar de otra manera».')


def test_el_barrido_de_mensajes_alcanza_los_raise_y_solo_los_de_tools():
    """El alcance, en las DOS direcciones: entra en lo que tiene que entrar y
    no entra en lo que no.

    Y las dos mitades importan por motivos distintos:

      - que encuentre los `raise` es lo que se anadio hace dos bloques, y sin
        esta comprobacion el cambio seria invisible: el barrido volveria a dar
        verde si dejara de mirar los `raise`, porque 302 de `assert` siguen
        estando por debajo del suelo de 200.

        O sea que ESTA es la comprobacion que hace que la ampliacion tenga
        efecto observable. Sin ella, anadir `raise` habria sido un cambio que
        no se puede ver.

      - que NO entre en `motor/` es lo que hace que el alcance siga siendo
        auditable. Un detector que se sale de su sitio no es mas preciso: es
        menos auditable, porque ya no se puede decir que no toca lo que no es
        suyo.

    Y LA CLASE SALE DEL ARBOL, Y ANTES SALIA DEL TEXTO

    MEDIDO, con la clasificacion por texto:

        hallazgos por el ARBOL:  336
        hallazgos por el TEXTO:  336
        DESACUERDOS:            1

    Y el unico desacuerdo era ESTE test: su mensaje empieza por «el barrido
    deberia encontrar al menos 20 `raise`», de modo que la palabra «raise»
    estaba en la linea y este `assert` se contaba como un `raise`.

    O sea que el fallo mas incomodo posible: la comprobacion que vigila al
    clasificador estaba ella misma mal clasificada. Los dos numeros reales
    eran 25 `raise` y 311 `assert`.

    Y el arreglo no es afinar la busqueda de la palabra —que dejaria el mismo
    problema para la siguiente palabra— sino que la clase salga del nodo que la
    encontro. Que es la regla del bloque aplicada a mi propio bloque."""
    encontrados = _mensajes_plantilla()
    raises = [(nombre, linea) for clase, nombre, linea, _t in encontrados
              if clase == 'raise']
    asserts = [(nombre, linea) for clase, nombre, linea, _t in encontrados
               if clase == 'assert']
    assert len(raises) >= 20, (
        'el barrido deberia encontrar al menos 20 `raise` con formato en %s y '
        'ha encontrado %d. MEDIDO: 25. O sea que el alcance declarado ya no '
        'es el alcance real, y esa es la unica forma de que un alcance se '
        'vuelva falso: que el codigo cambie sin que cambie el comentario.'
        % (CARPETA_DE_MENSAJES, len(raises)))
    assert len(asserts) >= 200, (
        'el barrido deberia encontrar al menos 200 `assert` con formato y ha '
        'encontrado %d. MEDIDO: 311. O sea que anadir los `raise` ha tapado '
        'algo en los `assert`, y dos cambios en el mismo sitio se pueden '
        'cancelar sin que ninguno se note.' % len(asserts))
    fuera = [nombre for _clase, nombre, _, _t in encontrados
             if os.path.sep + 'motor' + os.path.sep in os.path.join(ROOT,
                                                                     nombre)]
    assert not fuera, (
        'el barrido ha entrado en `motor/`, que no es mio: %r. MEDIDO: '
        '`motor/` tiene 14 `raise` con formato y ninguno se mira, y eso esta '
        'DECLARADO en el docstring de `_mensajes_plantilla`, que es donde se '
        'declara lo que no se comprueba.' % fuera[:3])


def test_la_clase_de_un_mensaje_viene_del_arbol_no_del_texto():
    """La direccion en la que el fallo se PRODUCIA, comprobada.

    Y el caso es el que MEDIDO salio en el repo: un `assert` cuyo MENSAJE
    contiene la palabra «raise». Con la clasificacion por texto, ese `assert`
    se contaba como un `raise`.

    Y hay un cuarto caso que el repo no tiene pero que puede aparecer: la
    palabra en un COMENTARIO de la linea. Que es la misma Confusion con otro
    disfraz, y por eso va en la MISMA prueba: si la arreglo solo entiende el
    mensaje, el comentario la rompe otra vez.

    Y el quinto caso es el que NO falla, y va tambien: un `raise` partido en
    varias lineas, donde la plantilla vive en una linea que no tiene la palabra
    `raise`. MEDIDO: la clasificacion por texto ACIERTA en ese caso, porque
    `Raise.lineno` es la linea de la palabra `raise`. O sea que hay que
    comprobar que sigue aciertando, no solo que deja de fallar."""
    fuente = chr(10).join([
        'def _f(x, y):',
        '    assert x, "no debe hacer raise %s" % y',
        '    assert x, "nada %s" % y  # raise por aqui',
        '    raise E("fallo %s" % y)',
        '    raise E(',
        '        "otro fallo %s" % y)',
    ])
    clases = [clase for clase, _linea, _t in _plantillas_de(fuente)]
    assert clases == ['assert', 'assert', 'raise', 'raise'], (
        'MEDIDO, el caso del repo es el primero —un `assert` cuyo mensaje '
        'contiene «raise»— y con la clasificacion por texto se contaba como '
        'un `raise`. Y el segundo es el mismo fallo con otro disfraz: la '
        'palabra en un comentario. Salen %r y se esperaba %r. O sea que la '
        'clase no sale del nodo que la encontro.' % (clases, ['assert',
                                                             'assert',
                                                             'raise', 'raise']))
    lineas = [linea for _c, linea, _t in _plantillas_de(fuente)]
    assert lineas == [2, 3, 4, 5], (
        'las lineas %r no son las de los nodos. MEDIDO: `Raise.lineno` es la '
        'linea de la palabra `raise`, de modo que el cuarto caso —un raise '
        'partido— se cuenta en la linea 5 y no en la 7. Y eso es lo que hay '
        'que comprobar: que la linea tambien venga del arbol.' % lineas)

def test_cada_excepcion_del_barrido_nombra_su_fichero():
    """El except que ya no podia coger lo que decia coger.

    Y el caso es el que MEDIDO salio: un `.py` con sintaxis invalida salia
    como `SyntaxError` de Python, que NO nombra el fichero. Y el otro, un `.py`
    que no es UTF-8, si llevaba mi mensaje, que si lo nombra.

    O sea que de las dos ramas del except una estaba viva y la otra era
    adorno. Y un adorno en un except es peor que un except que falta, porque
    parece que hay una comprobacion.

    Y van los DOS casos, porque el que funciona tambien puede romperse: si
    alguien ensancha el except a `Exception` para «ser mas robusto», los dos
    mensajes desaparecen a la vez —y este test lo veria, porque mira que el
    NOMBRE este en el texto.

    Y por que se mira el nombre y no el tipo de excepcion: porque el nombre es
    lo que hace falta. Con 109 ficheros en el alcance, un fallo que no dice
    cual es obliga a buscar; uno que lo dice no. Y el tipo puede cambiar sin
    que el diagnostico empeore, que es justo lo que permite arreglar esto sin
    reescribir la prueba."""
    def _barrido_con(nombre, escribir):
        # Y UN DIRECTORIO POR CASO, que es lo que hace falta.
        #
        # MEDIDO, el fallo de la version anterior: un solo directorio con
        # `bien.py`, `latin.py` y `roto.py`. El barrido se para en el PRIMERO
        # que falla, y como `sorted` los da en orden alfabetico, ese era
        # siempre `latin.py`. O sea que el caso de `roto.py` no llegaba a
        # existir: el test no fallaba, es que el INSTRUMENTO no sabia medir
        # el caso que se le pedia.
        #
        # Y con `roto.py` y `latin.py` cambiados de nombre, el test habria
        # pasado sin comprobar nada. Que es una forma nueva de la familia, y
        # la mas discreta hasta ahora: un test que depende del ORDEN de los
        # ficheros y mide uno de ellos.
        with tempfile.TemporaryDirectory() as alta:
            escribir(os.path.join(alta, nombre))
            try:
                _mensajes_plantilla(alta)
                return 'NO FALLO'
            except AssertionError as e:
                return str(e)
            except Exception as e:          # noqa: BLE001
                # Y aqui, la distincion que R2 senala, y es de dos
                # clases y no de una.
                #
                # MEDIDO: _mensajes_plantilla lanza AssertionError
                # para los DOS fallos que sabe explicar —no leer, no
                # parsear—, y propaga cualquier otra cosa. O sea que si
                # aqui aparece otra excepcion, NO es un caso del que el
                # test sepa: es el instrumento fallando de una forma no
                # prevista.
                #
                # Y el texto lo dice, porque R2 tiene razon en que un
                # except Exception que convierte todo en el mismo texto
                # puede esconder la distincion. El arreglo no es propagar
                # —que haria el test menos util—: es que el mensaje diga de
                # donde viene.
                return ('NO ES EL MENSAJE PROPIO DE LA '
                        'COMPROBACION: ha salido una %s, que el '
                        'instrumento no previó (%s). O sea que este fallo '
                        'no es un caso del detector: es el detector roto.'
                        % (type(e).__name__, e))

    def _roto(ruta):
        io.open(ruta, 'w', encoding='utf-8').write('def f(:' + chr(10))

    def _latin(ruta):
        io.open(ruta, 'wb').write(b'x = 1' + bytes([10]) + b'y = "' + bytes([0xa1])
            + bytes([0xa8]) + b'"')

    for nombre, marca, escribir in (
            ('roto.py', 'SINTAXIS INVALIDA', _roto),
            ('latin.py', 'no se ha podido LEER', _latin)):
        fallo = _barrido_con(nombre, escribir)
        assert marca in fallo, (
            'el fichero `%s` produce «%s», y se esperaba un mensaje que '
            'dijera «%s». MEDIDO, antes: `roto.py` salia como `SyntaxError` de '
            'Python, que NO nombra el fichero, porque el parse se habia ido de '
            'dentro del try.' % (nombre, fallo[:90], marca))
        assert nombre in fallo, (
            'el mensaje sale de Python y no nombra el fichero: «%s». Y eso es '
            'lo que importa: con 109 ficheros en el alcance, un fallo que no '
            'dice cual es obliga a buscar.' % fallo[:120])

    # Y que un directorio SANO no da ningun hallazgo, que es la tercera mitad.
    with tempfile.TemporaryDirectory() as alta:
        io.open(os.path.join(alta, 'bien.py'), 'w',
                encoding='utf-8').write('assert x, "nada %s" % y' + chr(10))
        assert len(_mensajes_plantilla(alta)) == 1, (
            'un directorio con un `.py` sano y un `assert` con formato tiene '
            'que dar UN hallazgo. MEDIDO, que es lo que confirma que el test '
            'mide el fallo y no elalto del ruido.')


# ============================ 22. EL GUARDIA DE LOS TESTS QUE DESAPARECEN
#
# Y este es el que R1 pide y que estaba en el sitio donde no se guarda: el
# parche. MEDIDO, lo que llevo un bloque:
#
#     @@ -3114,170 +3164 @@ BUSQUEDAS_ACEPTADAS = ()
#     -def test_no_hay_busquedas_sobre_fuente_sin_declarar():
#     -def test_el_inventario_de_busquedas_detecta_una_decoracion():
#     -def test_el_barrido_de_mensajes_alcanza_los_raise_y_solo_los_de_tools():
#
# TRES TESTS, y la suite no dio ni un fallo. Porque un test que desaparece no
# rompe nada —no hay nada que ejecutar— y el parse pasa.
#
# Y por eso este guardia esta en un TEST y no en un parche: un parche se
# ejecuta una vez, y esto tiene que comprobarse en cada suite.
#
# Y CUENTA EL REPO ENTERO, porque una regla que dice «el repo» tiene que
# mirar el repo. Ya paso una vez que una decia «el repo» y miraba dos ficheros
# de quince.
#
# Y por el ARBOL y no por `grep`: `def test_` puede aparecer en la prosa de un
# docstring, y contarlo seria contar prosa. MEDIDO, hoy en este fichero los dos
# dan 43 — y eso es «hoy no pasa», no «no puede pasar».
#
# Y lo que NO esta en el alcance, declarado: la raiz del repositorio. MEDIDO:
# en la raiz solo hay `hand_editor.py`. Y `asistente_live.py` no esta ahi:
# vive en `motor/`, es `motor/test_asistente_live.py`, y esta dentro del
# alcance, con 88 tests.
CARPETAS_DEL_INVENTARIO = ('tools', 'motor', 'recorder')

# Y LAS CIFRAS, EN UN SOLO SITIO
#
# Y este comentario NO lleva cifras, y antes las llevaba, y era un defecto.
# MEDIDO, lo que habia:
#
#     el comentario:      tools 459, motor 834, recorder 4      suma 1297
#     la constante:       {'tools': 461, 'motor': 834, ...}    suma 1299
#
# O sea que habia DOS copias de la misma medicion y no coincidian. Y R2 lo
# senalo, y con razon: las cifras son el OBJETO del guardia, de modo que si
# estan dos veces, hubo un momento en que una era la buena y la otra no, y no
# hay forma de saber cual.
#
# Y eso no es cosmetico aunque lo parezca: un comentario con una cifra
# desactualizada en otro sitio es inocuo. Aqui no, porque una cifra
# desactualizada al lado de la cifra buena es una medicion que no se puede
# repetir —no dice de cuando es—.
#
# 459 era la medicion de ANTES de anadir dos tests. O sea que el que estaba
# desactualizado era el comentario, y la constante era la buena.
#
# Y EL ARREGLO NO ES PONERLAS AL DIA: es que solo haya una
#
#     la CONSTANTE tiene las cifras, porque es lo que el test compara
#     este COMENTARIO no tiene cifras, porque no se compara con nada
#
# Que es la leccion de «dos listas identicas» con otras palabras: dos copias de
# la misma cosa se ven iguales y pueden divergir, y el arreglo es que solo haya
# una.
#
# Y EN LUGAR DE LAS CIFRAS, LA ORDEN QUE LAS REPRODUCE
#
#     python -m pytest tools/test_ejecutar_pytest.py -k no_ha_desaparecido
#
# y el fallo del test imprime, por carpeta, la cifra declarada y la medida, una
# al lado de otra. O sea que la medicion esta donde se ve y no en una copia.
#
# Y son TRES cifras y no ochenta y nueve filas, porque un inventario por
# fichero de esa taille es una tabla que nadie mantiene, y una tabla que nadie
# mantiene es decoracion.

TESTS_POR_CARPETA = {'motor': 884, 'recorder': 4, 'tools': 605}


# Y los FICHEROS, que son OTRA medida. MEDIDO, y sin ellos el guardia
# fijaba una cifra de funciones y no podia decir si habia mirado todos
# los ficheros o solo algunos — que es lo que R2 senala, y lo mismo que
# hacia el guardia de caracteres de control con su `mirados`.
#
# Y el alcance, DICHO y VIGILADO: el PRIMER NIVEL de estas tres carpetas.
# MEDIDO: hay CERO tests en subcarpetas, de modo que hoy «el repo entero»
# es cierto. Y «hoy» no es una propiedad. O sea que el guardia no baja,
# pero FALLA si algun dia hay tests abajo: es el unico caso en el que
# bajaria, y bajarlo sin querer seria decir «el repo entero» sin serlo.
FICHEROS_POR_CARPETA = {'motor': 72, 'recorder': 4, 'tools': 128}
# Y LA MAGNITUD QUE MIDE ESTE GUARDIA, que es lo que R2 pregunta, y que hay
# que responder por la magnitud y no solo por el numero.
#
# MEDIDO, y las TRES magnitudes no son la misma:
#
#     definiciones test_* a cualquier profundidad : 1300
#     definiciones test_* ANIDADAS                : 0
#     tests que pytest RECOGE                       : 1350
#
#     funciones con parametrize                   : 17
#     clases que heredan de unittest.TestCase      : 0
#
# O sea que pytest ejecuta 50 mas de los que hay definidos, y la diferencia
# sale de las 17 funciones parametrizadas.
#
# Y ESTE GUARDIA MIDE DEFINICIONES, y por que no lo que pytest recoge:
# MEDIDO, `collect-only` tarda cuarenta segundos e importa los modulos. Un
# guardia de cuarenta segundos no es un guardia: es un coste que acaba
# descartado por quien lo escribio.
#
# Y EL PUNTO CIEGO, DICHO:
#
#     si a una de esas 17 funciones se le quita UN CASO de su parametrize,
#     pytest recoge uno menos y este guardia NO se entera, porque la funcion
#     sigue estando.
#
# Y lo que se puede tapar se tapa con `PARAMETRIZADOS_ABAJO`, que cuenta las
# funciones con parametrize: si cambia el numero de funciones parametrizadas,
# cambia ese numero. Lo que NO se puede tapar sin ejecutar pytest es el numero
# de CASOS de cada una, y eso queda declarado como punto ciego y no como
# garantia.
PARAMETRIZADOS_ABAJO = 18

def _tests_de(directorio):
    """Cuantos `def test_` hay en los `.py` de `directorio`, y cuantos ficheros.

    Y devuelve DOS cosas, que son DOS medidas distintas. MEDIDO, y el motivo es
    que R2 senalo que el guardia fijaba funciones y no decia si habia mirado
    todos los ficheros: un `.py` con un solo test sigue siendo un fichero, y sin
    contarlos no hay forma de distinguir «he mirado el arbol entero» de «he
    mirado parte».

    Que es la misma forma del hueco que cerraba el guardia de caracteres de
    control, que devuelve `(hallazgos, mirados)` justamente para poder decir
    que ha mirado todos.

    Y NO BAJA A SUBCARPETAS, y eso es DECLARADO y VIGILADO

    MEDIDO: hay CERO tests en subcarpetas de las tres carpetas, de modo que hoy
    «el repo entero» es cierto.

    Y «hoy» no es una propiedad. O sea que esta funcion no baja, y el test
    FALLA si algun dia hay tests abajo — que es el unico caso en el que
    bajaria. Bajarlo sin querer seria decir «el repo entero» sin serlo, que es
    el fallo que ya se cometio una vez en este bloque: una regla que decia «el
    repo» y miraba dos ficheros de quince.

    Y `_tests_en_subcarpetas` es la que mira, y el test la llama. Que es
    preferible a bajar por una razon concreta: un `.py` en una subcarpeta puede
    no ser un modulo de este repo, y bajar obligaria a decidir eso. Midiendo
    primero, la decision solo hace falta el dia que haya algo que decidir.

    Y por el arbol, y no por `grep`: `def test_` puede aparecer dentro de un
    docstring —este mismo fichero lo menciona al explicar por que se cuenta—
    y contarlo seria contar prosa. Que es el mismo motivo por el que el
    inventario de campos se cuenta con `ast.Tuple` y no con un patron.

    Y aqui, al reves que en el barrido de mensajes, la excepcion de Python SI
    nombra el fichero —`SyntaxError` lleva el nombre en su mensaje—, y por eso
    no hace falta una mia. MEDIDO, y conviene decirlo porque son dos sitios que
    hacen lo mismo con dos politicas distintas, y sin decir nada parece
    incoherencia."""
    total = ficheros = 0
    for nombre in sorted(os.listdir(directorio)):
        if not nombre.endswith('.py'):
            continue
        ficheros += 1
        try:
            arbol = ast.parse(io.open(os.path.join(directorio, nombre),
                                      encoding='utf-8').read())
        except (SyntaxError, UnicodeDecodeError) as e:
            raise AssertionError(
                '%s no se ha podido leer ni parsear (%s). Y MEDIDO: aqui la '
                'excepcion de Python SI nombra el fichero, que es lo que la '
                'hace aceptable, mientras que en el barrido de mensajes habia '
                'que escribir una propia.' % (nombre, e))
        total += sum(1 for nodo in ast.walk(arbol)
                     if isinstance(nodo, (ast.FunctionDef,
                                          ast.AsyncFunctionDef))
                     and nodo.name.startswith('test_'))
    return total, ficheros


def _tests_por_debajo_del_primer_nivel(directorio):
    """Los tests que hay POR DEBAJO del primer nivel de `directorio`.

    Y RECURSIVO, a cualquier profundidad, y eso es un cambio de este bloque.

    MEDIDO, por que: la version anterior recorria las subcarpetas de primer
    nivel y los `.py` de dentro, pero NO entraba en una segunda generacion. O
    sea que un test en `tools/nueva/test_x.py` se avisaba y uno en
    `tools/nueva/otra/test_x.py` no.

    Y con nombre y mensaje precisos habria bastado —R2 ofrece las dos
    opciones—, pero la opcion de «un nivel» deja al guardia sin cubrir
    justo el caso para el que existe: el aviso pretende decir «alguien ha
    puesto un test en una subcarpeta», y con un nivel, un test en un tercer
    nivel no se avisaria.

    Y el coste, MEDIDO: hoy hay CERO `.py` por debajo del primer nivel en las
    tres carpetas —de hecho, cero subcarpetas—, de modo que recorrer mas no
    cuesta nada y no puede dar falsos positivos.

    Y aqui, y por que no se baja al REPOSITORIO entero: el alcance declarado
    son las tres carpetas. Un `.py` en otro sitio no es de este detector.

    Y `__pycache__` y los buzones de pytest quedan excluidos por nombre: no
    tienen `.py`, pero excluirlos es mas barato que comprobarlo.
    """
    encontrados = []
    for carpeta, directorios, ficheros in os.walk(directorio):
        directorios[:] = [d for d in directorios
                          if d not in ('__pycache__', '.pytest_cache')]
        if os.path.abspath(carpeta) == os.path.abspath(directorio):
            continue                     # el primer nivel lo cuenta `_tests_de`
        for fichero in sorted(ficheros):
            if not fichero.endswith('.py'):
                continue
            try:
                arbol = ast.parse(io.open(os.path.join(carpeta, fichero),
                                          encoding='utf-8').read())
            except (SyntaxError, UnicodeDecodeError) as e:
                raise AssertionError(
                    '%s no se ha podido leer (%s). Un fichero que no se lee no se mira, y eso es verde por no mirar. Por eso aqui se para.' % (os.path.join(carpeta, fichero), e))
            cuenta = sum(1 for nodo in ast.walk(arbol)
                         if isinstance(nodo, (ast.FunctionDef,
                                              ast.AsyncFunctionDef))
                         and nodo.name.startswith('test_'))
            if cuenta:
                encontrados.append(
                    (os.path.relpath(os.path.join(carpeta, fichero),
                                     directorio).replace('\\', '/'), cuenta))
    return encontrados



def _parametrizados(directorio):
    """Las funciones de test de NIVEL DE MODULO con `@pytest.mark.parametrize`.

    Y no es un adorno: es la segunda medida, y sale de lo medido.

    MEDIDO, y las TRES magnitudes que no son la misma:

        definiciones `test_*` a cualquier profundidad : 1300
        definiciones `test_*` ANIDADAS                : 0
        tests que pytest RECOGE                       : 1350

    O sea que pytest ejecuta 50 mas de los que hay definidos, y R2 tiene razon
    en que son magnitudes distintas. La diferencia sale de aqui:

        funciones con `@parametrize`                  : 17
        clases que heredan de `unittest.TestCase`      : 0

    De modo que el guardia mide DEFINICIONES, y eso tiene un punto ciego
    concreto que conviene decir en voz alta:

        si a una de esas 17 funciones se le quita UN CASO de su `@parametrize`,
        pytest recoge uno menos y el guardia NO se entera, porque la funcion
        sigue estando.

    Y lo que hace ESTE contador es tapar la parte que se puede tapar: si cambia
    el numero de funciones parametrizadas, cambia este numero. Lo que NO se
    puede tapar sin ejecutar pytest es el numero de CASOS de cada una, y eso
    esta declarado como punto ciego y no como garantia.

    Y por que no se cuenta pytest directamente con `--collect-only`: MEDIDO,
    tarda cuarenta segundos y ademas importa los modulos. O sea que un guardia
    que dura cuarenta segundos no es un guardia: es un coste que se acaba
    dejando.

    Y LAS DOS REGLAS, QUE ESTABAN EN TEXTO Y AHORA NO

    MEDIDO, con los casos de un fichero inventado:

        decorador con la palabra pero que NO es pytest   texto=1 estructural=0
        decorador de pytest de verdad                    texto=1 estructural=1
        funcion test_ anidada con parametrize            texto=1 estructural=1
        nombre que CONTIENE parametrize                  texto=1 estructural=1

    O sea que la regla anterior —`if 'parametrize' in ast.unparse(...)`—
    contaba un decorador ajeno que tuviera la palabra. Y R2 lo senala, y con
    razon: eso detecta TEXTO donde lo que hay que reconocer es IDENTIDAD.

    Y ahora reconoce la forma, que son dos condiciones:

        1. es una LLAMADA cuyo atributo final se llama exactamente
           `parametrize`
        2. y el receptor termina en `pytest.mark`

    Y la segunda no es la propuesta de R2, que basta con la primera: MEDIDO, las 17
    llamadas de este repo salen TODAS de `pytest.mark.parametrize`, de modo que
    anadirla no cambia el numero de hoy y quita una ambiguedad que no se paga
    hasta que aparezca el caso. Que es el mismo argumento del limite derivado
    del bloque: una cota o una regla mas estrecha que no cuesta nada ahora y
    evita un fallo mas adelante.

    Y SOLO NIVEL DE MODULO, por una razon que no es de estilo: pytest NO
    recoge una funcion anidada. De modo que un guardia que las contara estaria
    contando cosas que no se ejecutan, que es justo la clase de error que este
    bloque lleva cuarenta bloques corrigiendo.

    MEDIDO: hoy hay CERO anidadas. O sea que la regla no cambia el numero, y
    lo que cambia es que el numero significa lo que dice.
    """
    total = 0
    for nombre in sorted(os.listdir(directorio)):
        if not nombre.endswith('.py'):
            continue
        ruta = os.path.join(directorio, nombre)
        try:
            arbol = ast.parse(io.open(ruta, encoding='utf-8').read())
        except (SyntaxError, UnicodeDecodeError) as e:
            # Y NO un `continue`, que es lo que hacia antes.
            #
            # MEDIDO, y hoy no hay ningun fichero ilegible, de modo que el
            # `continue` no estaba produciendo un recuento incorrecto. Y eso es
            # «hoy no pasa», no «no puede pasar».
            #
            # Y por que importa: un `continue` que se traga un fichero
            # convierte el recuento en una DECLARACION —«hay 17 funciones
            # parametrizadas»— y si se tragara un fichero, la declaracion
            # seria falsa y nadie lo veria. Que es lo contrario de lo que hace
            # `_tests_de`, que PARA y nombra el fichero.
            #
            # Y el repo tiene ahora una politica sola, no dos: un fichero que
            # no se lee, para el inventario y nombra el fichero.
            raise AssertionError(
                '%s no se ha podido leer ni parsear (%s). Y no se salta: un '
                'fichero que no se lee es un fichero que no se cuenta, y un '
                'recuento al que le falta un fichero es una DECLARACION, no '
                'una medida.' % (nombre, e))
        modulos, marcas = _nombres_de_pytest(arbol)
        for nodo in arbol.body:
            if not (isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and nodo.name.startswith('test_')):
                continue
            for decorador in nodo.decorator_list:
                if _es_parametrize_de_pytest(decorador, modulos, marcas):
                    total += 1
    return total


def _nombres_de_pytest(arbol):
    """Los nombres con los que ESTE FICHERO se refiere a `pytest` y a `pytest.mark`.

    Y sale del ARBOL, y no de un patron: `import pytest as pt` liga `pt`, y
    `from pytest import mark` liga `mark`. Y el decorador se puede escribir con
    cualquiera de los dos.

    MEDIDO, por que esto hace falta: con la regla de la forma canonica
    (`receptor == 'pytest.mark'`) el detector NO contaba `@pt.mark.parametrize`,
    y ese no contar es un FALLO SILENCIOSO — un recuento que se equivoca en
    silencio y nadie lo ve, que es la clase de error que este bloque lleva
    cuarenta bloques corrigiendo.
    """
    modulos = set()
    marcas = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name == 'pytest':
                    modulos.add(alias.asname or 'pytest')
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.module == 'pytest' and not nodo.level:
                for alias in nodo.names:
                    if alias.name == 'mark':
                        marcas.add(alias.asname or 'mark')
    return modulos, marcas


def _es_parametrize_de_pytest(decorador, modulos=frozenset(), marcas=frozenset()):
    """¿Este decorador es un `@pytest.mark.parametrize`?

    Y la FORMA, que son tres condiciones:

        1. es una llamada con atributo, y el atributo se llama `parametrize`
        2. y el receptor es `pytest.mark` — la forma CANONICA
        3. o el receptor es un alias que este fichero declara de `pytest`, o
           de `pytest.mark`

    Y por que la segunda y la tercera van separadas y no juntas: la forma
    canonica no se puede confundir con nada —el nombre `pytest` no puede ser
    otra cosa—, y los alias si. Por eso la canonica se acepta SIEMPRE, y un
    alias SOLO si el propio fichero lo declara.

    Y MEDIDO, con casos inventados:

        decorador con la palabra pero que NO es pytest   texto=1 estructural=0
        decorador de pytest de verdad                     texto=1 estructural=1
        funcion test_ anidada con parametrize             texto=1 estructural=1
        `import pytest as pt` + `@pt.mark.parametrize`    NO lo cuenta (fallo)
        `from pytest import mark` + `@mark.parametrize`    NO lo cuenta (fallo)

    Y los dos ultimos son los que R2 senalo, y el arreglo no cuesta nada
    hoy: MEDIDO, las 17 llamadas del repo salen TODAS de
    `pytest.mark.parametrize`, de modo que reconocer los alias no cambia el
    numero de hoy y quita una clase de fallo silencioso que no se paga hasta
    que aparezca el caso.

    Y el CONTRATO, que es lo que el nombre promete. Antes el nombre decia
    «de verdad», que no es una propiedad: ahora dice lo que hace, que es la
    forma canonica MAS los alias que el fichero declara.
    """
    if not (isinstance(decorador, ast.Call)
            and isinstance(decorador.func, ast.Attribute)):
        return False
    if decorador.func.attr != 'parametrize':
        return False
    receptor = decorador.func.value
    # la forma canonica: `pytest.mark.parametrize`
    if (isinstance(receptor, ast.Attribute) and receptor.attr == 'mark'
            and isinstance(receptor.value, ast.Name)
            and receptor.value.id == 'pytest'):
        return True
    # `import pytest as pt`  ->  `pt.mark.parametrize`
    if (isinstance(receptor, ast.Attribute) and receptor.attr == 'mark'
            and isinstance(receptor.value, ast.Name)
            and receptor.value.id in modulos):
        return True
    # `from pytest import mark`  ->  `mark.parametrize`
    if isinstance(receptor, ast.Name) and receptor.id in marcas:
        return True
    return False
def test_no_ha_desaparecido_ningun_test():
    """Y que el recuento no se pueda quedar satisfecho por una lista vacia.

    Y aqui NO hay cifras, ni en este docstring ni en el comentario de las
    constantes, y antes si las habia. MEDIDO, lo que habia:

        el comentario:      tools 459, motor 834, recorder 4     suma 1297
        la constante:       {'tools': 461, 'motor': 834, ...}   suma 1299

    Y eso es un defecto, no cosmetico: las cifras son el OBJETO del guardia, y
    dos copias que no coinciden significan que hubo un momento en que una era
    la buena y la otra no. Una cifra al lado de la cifra buena es una medicion
    que no se puede repetir.

    Y en su lugar, la ORDEN que produce la medicion:

        python -m pytest tools/test_ejecutar_pytest.py -k no_ha_desaparecido

    Y el fallo de este test imprime, por carpeta, la cifra declarada y la
    medida, una al lado de otra. O sea que la medicion esta donde se ve.

    Y el suelo no es un total sino TRES cifras, una por carpeta. Porque un
    total con una cifra magica no dice nada cuando se rompe —dice «una de mas»
    y hay que adivinar donde— y una cifra por carpeta ya lo dice. Y ahora hay
    SEIS: tres de tests y tres de ficheros, que son dos medidas distintas. R2
    lo senala, y con razon: un `.py` con un solo test sigue siendo un fichero,
    y sin contarlos no hay forma de distinguir «he mirado el arbol entero» de
    «he mirado parte».

    Y EL ALCANCE, DICHO Y VIGILADO

    MEDIDO: hay CERO tests en subcarpetas, de modo que hoy «el repo entero» es
    cierto. Y «hoy» no es una propiedad, de modo que el guardia no baja pero
    FALLA si algun dia hay tests abajo.

    Y eso es preferible a bajar, y el motivo es concreto: un `.py` en una
    subcarpeta puede no ser un modulo de este repo, y bajar obligaria a
    decidirlo. Midiendo primero, la decision solo hace falta el dia que haya
    algo que decidir.

    Y el fallo que este guardia evita, MEDIDO, con el parche que lo produjo:

        @@ -3114,170 +3164 @@ BUSQUEDAS_ACEPTADAS = ()
        -def test_no_hay_busquedas_sobre_fuente_sin_declarar():
        -def test_el_inventario_de_busquedas_detecta_una_decoracion():
        -def test_el_barrido_de_mensajes_alcanza_los_raise_y_solo_los_de_tools():

    tres tests, el parse bien, y la suite sin un fallo. Un test que desaparece
    no rompe nada porque no hay nada que ejecutar, y ese es el motivo por el
    que hace falta un guardia que mire el RECUENTO y no el resultado de la
    suite: el resultado de la suite no puede notar que falta un test."""
    medido = {}
    medido_ficheros = {}
    for carpeta in CARPETAS_DEL_INVENTARIO:
        total, ficheros = _tests_de(os.path.join(ROOT, carpeta))
        medido[carpeta] = total
        medido_ficheros[carpeta] = ficheros
    assert medido == TESTS_POR_CARPETA, (
        'el numero de TESTS por carpeta no es el declarado:%s\n\n'
        'Si ha BAJADO, ha desaparecido un test, y eso no rompe nada por si '
        'mismo —no hay nada que ejecutar— y por eso hace falta este guardia.\n'
        '\n'
        'Si ha SUBIDO, hay que actualizar `TESTS_POR_CARPETA` a mano, y esa es '
        'la parte incomoda: es el precio de que anadir un test sea una decision '
        'consciente. Un guardia que se actualiza solo no vigila nada.'
        % chr(10).join('    %-9s declarado %4d   medido %4d'
                       % (c, TESTS_POR_CARPETA[c], medido[c])
                       for c in CARPETAS_DEL_INVENTARIO))
    assert medido_ficheros == FICHEROS_POR_CARPETA, (
        'el numero de FICHEROS por carpeta no es el declarado:%s\n\n'
        'Y esto es OTRA medida que la de tests, que es lo que R2 senala: un '
        '`.py` con un solo test sigue siendo un fichero. Sin esta comprobacion '
        'no hay forma de distinguir «he mirado el arbol entero» de «he mirado '
        'parte». Que es lo mismo que hace el guardia de caracteres de control '
        'con su `mirados`.'
        % chr(10).join('    %-9s declarado %4d   medido %4d'
                       % (c, FICHEROS_POR_CARPETA[c], medido_ficheros[c])
                       for c in CARPETAS_DEL_INVENTARIO))
    parametrizados = dict(
        (carpeta, _parametrizados(os.path.join(ROOT, carpeta)))
        for carpeta in CARPETAS_DEL_INVENTARIO)
    assert sum(parametrizados.values()) == PARAMETRIZADOS_ABAJO, (
        'el numero de funciones con parametrize es %d y el declarado es %d.%s%s'
        % (sum(parametrizados.values()), PARAMETRIZADOS_ABAJO, chr(10),
           chr(10).join('    %-9s medido %d' % (c, parametrizados[c])
                        for c in CARPETAS_DEL_INVENTARIO)))
    abajo = []
    for carpeta in CARPETAS_DEL_INVENTARIO:
        for fichero, cuenta in _tests_por_debajo_del_primer_nivel(os.path.join(ROOT,
                                                                 carpeta)):
            abajo.append('%s/%s  %d' % (carpeta, fichero, cuenta))
    assert not abajo, (
        'hay %d fichero(s) con tests POR DEBAJO del primer nivel:%s\n\n'
        'MEDIDO, hasta ahora no habia ninguno, y por eso el guardia no baja. '
        'O sea que el alcance «el repo entero» era cierto DE HOY, y «hoy» no '
        'es una propiedad.\n\n'
        'Y el arreglo NO es bajar sin mas: un `.py` en una subcarpeta puede no '
        'ser un modulo de este repo. El arreglo es decidir cual de las dos '
        'cosas es esta, y eso ya se puede decidir porque hay un caso.'
        % (len(abajo), chr(10).join('    %s' % x for x in abajo)))


# ============================ 23. LOS DOCSTRINGS DESCUADRADOS
#
# Y este es un tipo de incoherencia que no ha salido hasta ahora, y que es la
# clase de siempre con una razon nueva:
#
#     no es que la comprobacion mida mal. Es que NO HAY COMPROBACION.
#
# MEDIDO, con el AST —que sabe donde empieza y acaba cada docstring— y no con
# `grep`:
#
#     lineas de docstring sin la sangria de su bloque: 23, todas en
#     `_plantillas_de`, y alternando con nueve que si la tienen
#
# O sea que NO era un bloque entero sin sangrar. Y eso es PEOR, y el motivo es
# concreto: con un bloque entero sin sangrar un lector ve «esto no es codigo»
# y se para; con lineas alternadas el bloque parece codigo a medias, y el ojo
# lo acepta como algo raro sin pararse.
#
# Y NO ROMPE NADA: el parse pasa, la suite pasa, el fichero funciona. O sea que
# no hay nada que detecte el fallo salvo una comprobacion expresa.
#
# Y POR QUE EL GUARDIA VA CON EL AST Y NO CON `grep`
#
# MEDIDO, constantes con tres comillas dobles dentro, en este fichero: 0. O
# sea que hoy unas tres comillas dobles no son ambiguas. Y eso es «hoy no pasa»: manana puede haber
# una cadena normal que lo contenga, y un guardia por texto empezaria a contar
# delimitadores donde no los hay.
#
# El AST ya sabe cual es el delimitador —`ast.Expr` sobre una `Constant` de
# cadena ES el docstring—, de modo que no depende de que no haya casos raros.
# Y esa es la razon por la que en este bloque el texto se ha dejado de usar
# para esto.
#
# Y EL ALCANCE: `tools/`, que es lo mio. MEDIDO: los docstrings descuadrados
# estaban todos en `tools/`. Y `motor/` y la raiz quedan fuera, y eso esta
# escrito aqui y no solo en el mensaje del commit.
CARPETA_DE_DOCSTRINGS = 'tools'


# Los nodos que PUEDEN tener docstring, y la lista no es decorativa.
#
# MEDIDO, el motivo por el que esta lista existe: un `if` tambien tiene
# `body`, y su primera sentencia puede ser una expresion de cadena, y esa
# cadena NO es un docstring. El detector anterior la senalaba, y el nombre de
# la funcion miente: decia «docstrings descuadrados» de algo que no es un
# docstring.
#
# Y en Python un docstring es, exactamente, la primera expresion de cadena de
# un MODULO, una CLASE o una FUNCION. Y nada mas.
NODOS_CON_DOCSTRING = (ast.Module, ast.ClassDef, ast.FunctionDef,
                        ast.AsyncFunctionDef)


def _docstring_de(nodo):
    """El docstring de un nodo, o None. Y por el AST.

    Y SOLO para los nodos que pueden tenerlo, que son los de
    `NODOS_CON_DOCSTRING`. Y esa restriccion no es un detalle de estilo: es lo
    que separa «un docstring descolocado» de «una cadena en un bloque de
    control que el detector confundio con un docstring».

    Y MEDIDO, el motivo de no hacerlo por texto: en este fichero hay
    constantes de cadena que contienen comillas dobles, y NINGUNA contiene
    tres. De modo que un guardia por texto funcionaria hoy. Y «hoy» no es una
    propiedad.
    """
    if not isinstance(nodo, NODOS_CON_DOCSTRING):
        return None
    cuerpo = getattr(nodo, 'body', None)
    if not isinstance(cuerpo, list) or not cuerpo:
        return None
    primero = cuerpo[0]
    if (isinstance(primero, ast.Expr)
            and isinstance(primero.value, ast.Constant)
            and isinstance(primero.value.value, str)):
        return primero
    return None
def _docstrings_descuadrados(texto):
    """Los docstrings con lineas fuera de la sangria de su bloque.

    Y sale del ARBOL, que sabe donde empieza y acaba cada docstring. Con
    `grep` no se puede: unas comillas triples pueden abrir un bloque y cerrar otro, y una
    cadena normal puede contener tres comillas dobles sin ser un delimitador.

    Y DEVUELVE la linea CULPABLE, que es lo que hay que ir a ver.

    Y esto es una FUNCION y no un bloque dentro del test, por el motivo que se
    ha repetido en este bloque: una comprobacion que solo se puede ejecutar
    contra el repositorio tiene dientes para el repositorio y ninguno para si
    misma. Y el caso de esta necesita un fichero inventado, porque en el
    repositorio no hay ningun docstring descuadrado.

    Y DEVUELVE la linea de la primera suelta y no la de la apertura, y esa es la
    segunda de las dos opciones que ofrece R2 sobre el diagnostico. MEDIDO, en
    `_parametrizados`: la apertura era la 3792 y la culpable la 3823, y treinta
    lineas de distancia se convierten en un paseo.

    Y devuelve tambien CUANTAS, porque hay que saber si son tres o trescientas.

    Y lo que NO hace, y esta declarado en el docstring del test que la usa:
    no comprueba que la sangria sea multiplo de cuatro, ni tabs contra espacios,
    ni la sangria del codigo de al lado. MEDIDO, que ese limite no es teorico:
    un docstring cuya apertura no sea multiplo de cuatro PASARIA esta funcion.

    Y LO QUE YA NO HACE, y es lo que R2 senalo: ya NO mira cualquier nodo
    que tenga un `body`. Mira SOLO los nodos que pueden tener un docstring, que
    son los de `NODOS_CON_DOCSTRING`.

    Y por que importa, y no es una mania de R2: el detector produce un
    DIAGNOSTICO sobre un fichero. Si se equivoca de grupo, el nombre de la
    funcion miente, y quien lo lea buscara un docstring donde no hay ninguno.

    MEDIDO, con un caso inventado:

        cadena al principio de un `if`    ->  la senalaba  (no es un docstring)
        cadena al principio de un `for`   ->  la senalaba  (no es un docstring)
        cadena al principio de un `with`  ->  la senalaba  (no es un docstring)
        docstring de una funcion          ->  la senala    (si es lo que es)
        docstring de una clase            ->  la senala    (si es lo que es)

    Y el docstring de un MODULO no se comprueba, y por que: su bloque esta en
    la columna 0, de modo que la regla «menos sangrado que la apertura» no
    puede tener lugar nunca. No es un hueco del detector: es que la regla no
    aplica ahi.
    """
    arbol = ast.parse(texto)
    lineas = texto.split(chr(10))
    salida = []
    for nodo in ast.walk(arbol):
        primero = _docstring_de(nodo)
        if primero is None:
            continue
        apertura = primero.lineno
        sangria = (len(lineas[apertura - 1])
                   - len(lineas[apertura - 1].lstrip()))
        if sangria == 0:
            continue
        sueltas = [k for k in range(apertura, primero.end_lineno)
                   if lineas[k].strip()
                   and len(lineas[k]) - len(lineas[k].lstrip()) < sangria]
        if sueltas:
            salida.append((getattr(nodo, 'name', '<modulo>'),
                           sueltas[0] + 1, len(sueltas)))
    return salida
def test_no_hay_docstrings_descuadrados():
    """Que ningun docstring tenga lineas fuera de la sangria de su bloque.

    Y el criterio es la COLUMNA, no el texto: la sangria de la apertura es la
    que debe tener el resto, porque el bloque va dentro de un cuerpo y lo que
    esta sangrado es el cuerpo.

    Y EL ALCANCE REAL, que R2 senala mas ancho de lo que es

    Este guardia detecta lineas NO VACIAS cuya sangria es MENOR que la de la
    apertura del docstring. Y nada mas.

    O sea que NO comprueba que la sangria sea multiplo de cuatro, ni tabs
    contra espacios, ni la sangria de las lineas de codigo de al lado.

    Y MEDIDO, que ese limite no es teorico: un docstring cuya apertura no sea
    multiplo de cuatro pasaria este guardia. De modo que este test NO puede
    sostener «todos los docstrings estan bien puestos»; solo sostiene «no hay
    lineas que se salgan del bloque por la izquierda».

    Y un alcance escrito mas ancho que el real es una afirmacion que nadie
    puede fiscalizar, que es el motivo de escribirlo aqui y no solo en el
    mensaje del commit.

    Y por que este guardia y no el `ast.parse`: porque el `parse` ya pasa con
    un docstring descuadrado. MEDIDO: 23 lineas en `_plantillas_de`, el parse
    bien, y la suite bien. O sea que el fallo era invisible, y un fallo
    invisible necesita una comprobacion, no un parseo.

    Y el alcance es `tools/`, que es lo mio. Y esta declarado aqui y no en el
    mensaje del commit, que es donde se quedan las cosas que nadie vuelve a
    leer."""
    base = os.path.join(ROOT, CARPETA_DE_DOCSTRINGS)
    assert os.path.isdir(base), 'la carpeta tiene que existir: %s' % base
    descuadrados = []
    for nombre in sorted(os.listdir(base)):
        if not nombre.endswith('.py'):
            continue
        texto = io.open(os.path.join(base, nombre), encoding='utf-8').read()
        for funcion, linea, cuenta in _docstrings_descuadrados(texto):
            descuadrados.append('%s:%d «%s», la primera linea suelta de %d'
                                % (nombre, linea, funcion, cuenta))
    assert not descuadrados, (
        'hay %d docstring(s) con lineas fuera de la sangria de su bloque:%s\n\n'
        'MEDIDO, por que se nota: un bloque ENTERO sin sangrar hace que un '
        'lector vea «esto no es codigo» y se pare; lineas alternadas hacen que '
        'el bloque parezca codigo a medias, y el ojo lo acepta sin pararse.\n\n'
        'Y nada de esto rompe nada —el parse pasa y la suite pasa—, que es la '
        'razon por la que hace falta esta comprobacion y no un parseo.'
        % (len(descuadrados),
           chr(10).join('    %s' % x for x in descuadrados[:10])))
# ============================ 24. LOS GUARDIANES, CON CASOS INVENTADOS
#
# Y esto es lo que R1 dicta en las tareas 2, 3 y 5, y es lo mismo de siempre:
#
#     el test falla si hay tests en un tercer nivel
#     el test verifica que la línea señalada es la culpable
#     si se vuelve a poner apertura + 1, el test falla
#     el test que verifica que un nombre viejo no está, mira el código
#
# Y las tres son comprobaciones sobre instrumentacion NUEVA, que hasta ahora
# solo se comprobaba desde scripts de medicion que se descartan. O sea que
# estaban escritas y no eran parte del proyecto.
#
# Y las tres se pueden dar con un caso INVENTADO, que es justo lo que las
# tres piden.


def test_el_guardia_de_subcarpetas_lo_ve_a_tres_niveles():
    """Que el guardia vea un test a TRES niveles, que es lo que R2 pedia.

    Y el motivo de que este caso sea necesario, y no sea un lujo:

        R2, punto 1: detectaría `tools/nueva/test_x.py`, pero no
        `tools/nueva/otra/test_x.py`.

    Y MEDIDO: hoy hay CERO subcarpetas en las tres carpetas, de modo que la
    comprobacion del repositorio pasaria con cualquier cosa —incluido un
    guardia que NO bajara—.

    O sea que sin este caso, la afirmacion «es recursivo» no la sostiene nada:
    es una frase sobre el codigo, y las frases sobre el codigo son justo lo que
    este bloque lleva cuarenta bloques diciendo.

    Y el caso lleva TRES niveles y no uno, porque uno ya lo cubria la version
    anterior. Y lleva tambien un `.py` LIMPIO en un cuarto nivel, para que el
    guardia no acuse a quien no tiene nada que ver.

    Y la cuenta importa: se mira el NUMERO de tests que devuelve, no que devuelva
    algo. Un guardia que dice «he encontrado algo» pasa igual con un falso
    positivo."""
    with tempfile.TemporaryDirectory() as alta:
        niveles = ('uno', os.path.join('uno', 'dos'),
                   os.path.join('uno', 'dos', 'tres'),
                   os.path.join('uno', 'dos', 'tres', 'cuatro'))
        for nivel in niveles:
            os.makedirs(os.path.join(alta, nivel))
        # un test a DOS niveles
        io.open(os.path.join(alta, niveles[1], 'test_dos.py'), 'w',
                encoding='utf-8').write('def test_a_dos():' + chr(10)
                                         + '    pass' + chr(10))
        # un test a TRES niveles, que es el caso de R2
        io.open(os.path.join(alta, niveles[2], 'test_tres.py'), 'w',
                encoding='utf-8').write('def test_a_tres():' + chr(10)
                                         + '    pass' + chr(10)
                                         + 'def test_otro():' + chr(10)
                                         + '    pass' + chr(10))
        # un `.py` SIN tests a CUATRO niveles, que no debe aparecer
        io.open(os.path.join(alta, niveles[3], 'sintest.py'), 'w',
                encoding='utf-8').write('x = 1' + chr(10))
        # y una cache, que esta excluida por nombre
        os.makedirs(os.path.join(alta, '__pycache__'))
        io.open(os.path.join(alta, '__pycache__', 'test_cache.py'), 'w',
                encoding='utf-8').write('def test_no_debe_contar():' + chr(10))
        hallados = dict(_tests_por_debajo_del_primer_nivel(alta))

    esperados = {'uno/dos/test_dos.py': 1, 'uno/dos/tres/test_tres.py': 2}
    assert hallados == esperados, (
        'MEDIDO, el guardia devuelve %r y se esperaba %r.%s%s'
        'El caso de R2 es el segundo: un test a TRES niveles. Y el `cuatro` de '
        'mas no debe aparecer, ni el `__pycache__`. Y las CUENTAS, no solo las '
        'claves: un guardia que dice «he encontrado algo» pasa igual con un '
        'falso positivo.'
        % (hallados, esperados, chr(10), chr(10)))


def test_el_diagnostico_de_docstrings_senala_la_culpable():
    """Que la linea que dice el diagnostico sea LA CULPABLE, y no la apertura.

    Y por que el caso es inventado: MEDIDO, en el repositorio no hay ningun
    docstring descuadrado. O sea que la comprobacion real pasaria con
    cualquier numero, y el numero es justo lo que hay que comprobar.

    Y el caso lleva las DOS COSAS:

      - la apertura del docstring en la linea 2
      - la culpable en la linea 5, con tres espacios en vez de cuatro

    Y la distancia entre las dos es de tres lineas, que es pequena y suficiente:
    si el diagnostico volviera a senalar la apertura, el numero seria 2 y no 5,
    y la comprobacion falla.

    Y con esto queda cubierto lo que R1 dicta: «si se vuelve a poner
    `apertura + 1`, el test falla». Porque `+1` sobre la apertura daria 3, y 3
    tampoco es 5.

    Y la cuenta se mira tambien, porque «un fallo» y «cuatro fallos» no se
    distinguen con el mismo mensaje."""
    fuente = chr(10).join([
        'def _ejemplo():',
        '    """Una linea de apertura.',
        '',
        '    Una linea correcta.',
        '   Una linea con tres espacios.',
        '    Y otra correcta."""',
        'def test_algo():',
        '    pass',
    ])
    hallados = _docstrings_descuadrados(fuente)
    assert len(hallados) == 1, (
        'MEDIDO, se esperaba un docstring descuadrado y hay %d: %r. O sea que '
        'el detector no ve un caso que es facil de construir.' % (len(hallados),
                                                                   hallados))
    nombre, linea, cuenta = hallados[0]
    assert linea == 5, (
        'el diagnostico senala la linea %d y la culpable es la 5.%s%s'
        'MEDIDO: la apertura del docstring es la linea 2. O sea que senalar la '
        'apertura daria 2 y senalar la apertura mas uno daria 3, y ninguna de '
        'las dos es 5. Que es justo por lo que hace falta un caso: el '
        'diagnostico puede estar mal y no saberse.'
        % (linea, chr(10),
           chr(10).join('      linea %-3d %r' % (k + 1, l)
                        for k, l in enumerate(fuente.split(chr(10))))))
    assert cuenta == 1, (
        'la cuenta dice %d y hay una linea suelta. Y la cuenta importa porque '
        'sin ella un diagnostico que senala la linea 5 no dice si hay tres '
        'fallos mas abajo.' % cuenta)
    assert nombre == '_ejemplo', 'el nombre sale como %r' % nombre


def test_las_comprobaciones_de_este_fichero_miran_codigo_y_no_prosa():
    """Que las dos comprobaciones que fallaron por leer prosa miren el ARBOL.

    Y son dos, y las dos fallaron en el bloque anterior:

      - el nombre viejo de la funcion de subcarpetas, que sigue apareciendo en
        el comentario que EXPRICA por que se cambio;
      - el `apertura + 1`, que sigue apareciendo en el comentario que explica
        el error.

    O sea que las dos existen como TEXTO y no como CODIGO, y una comprobacion
    que busca texto las encuentra y dice que el problema sigue.

    Y el arreglo no es quitar el texto del comentario —que esta bien que este
    ahi—: es que la comprobacion mire el ARBOL, que distingue una definicion de
    una mencion.

    Y MEDIDO, que esto no es un detalle: la comprobacion por texto daba FALLA
    las dos veces, con el codigo ya correcto.

    Y lo que este test hace es mirar lo contrario de las dos: que en el ARBOL
    no haya ni la definicion ni la llamada, ni la suma. Que es lo que tiene que
    ser cierto, y no lo que el comentario diga."""
    arbol = ast.parse(io.open(__file__, encoding='utf-8').read())

    definiciones_old = [n.lineno for n in ast.walk(arbol)
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and n.name == '_tests_en_subcarpetas']
    llamadas_old = [n.lineno for n in ast.walk(arbol)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == '_tests_en_subcarpetas']
    assert not definiciones_old and not llamadas_old, (
        'la funcion vieja vuelve a existir o a llamarse, en las lineas %r y %r. '
        'Y OJO: en el TEXTO esta bien que aparezca, porque el comentario que '
        'explica el cambio la nombra. Lo que no puede es existir.'
        % (definiciones_old, llamadas_old))

    sumas = [n.lineno for n in ast.walk(arbol)
             if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add)
             and isinstance(n.left, ast.Name) and n.left.id == 'apertura'
             and isinstance(n.right, ast.Constant) and n.right.value == 1]
    assert not sumas, (
        'hay una suma `apertura + 1` en la linea %r, que es el desfase que este '
        'bloque acaba de corregir. Y MEDIDO, que ese `+1` senalaba una linea '
        'DESPUES de la real: `lineno` de Python ya es 1-based. Y en el TEXTO '
        'puede aparecer, porque el comentario lo explica.' % sumas)

# ============================ 25. LOS DOS HALFOS DE R2
#
# Y R2 senalo dos cosas, y las dos son de la misma familia: el detector
# reconocia MENOS de lo que dice reconocer, y en los dos casos por el mismo
# motivo —una forma concreta en vez de una identidad—.


def test_un_docstring_en_un_bloque_de_control_no_es_un_docstring():
    """Que una cadena al principio de un `if` no se senale como docstring.

    Y el caso es el de R2, literal:

        def ejemplo():
            if True:
                \"\"\"Una cadena que no es un docstring.
           Esta linea podria activar el detector.\"\"\"

    Y lo que se mide es que NO sale. MEDIDO, con el detector anterior, esa
    cadena SI salia, y con el nombre `<modulo>`, que es la pista: un modulo
    no tiene docstring dentro de un `if`.

    Y las dos mitades, porque solo con la primera el test pasaria con un
    detector que no mirase nada:

      1. la cadena en un bloque de control NO se senala;
      2. y el docstring de verdad, en el MISMO fichero, se senala.

    Y por que la segunda importa: un detector que no senala nada tambien
    cumple la primera. Y esa es la clase de verde que no dice nada.
    """
    fuente = chr(10).join([
        'def ejemplo():',
        '    if True:',
        '        """Una cadena que no es un docstring.',
        '   Esta linea podria activar el detector."""',
        '        return 1',
        '    return 2',
        '',
        '',
        'def otro():',
        '    """Una linea de apertura.',
        '',
        '    Una linea correcta.',
        '   Una linea con tres espacios.',
        '    Y otra correcta."""',
        '    return 3',
    ])
    hallados = _docstrings_descuadrados(fuente)
    nombres = [n for n, _l, _c in hallados]
    assert 'ejemplo' not in nombres, (
        'la cadena de un `if` se ha senalado como docstring: %r. Y no lo es: '
        'un docstring es la primera expresion de cadena de un modulo, una '
        'clase o una funcion, y nada mas.' % hallados)
    assert 'otro' in nombres, (
        'y el docstring de verdad NO se senala: %r. O sea que el detector ha '
        'dejado de mirar, que es un verde que no dice nada.' % hallados)


def test_una_cadena_en_un_for_o_en_un_with_tampoco_es_un_docstring():
    """Los otros dos bloques de control, porque el caso de R2 era el `if`.

    Y el motivo de no dejar solo el `if`: un detector que se corrige para UN
    caso y se deja los otros dos es un detector con una lista de casos
    exentos, que es la misma trampa que el rango de caracteres escrito a mano.
    """
    for cabecera in ('for i in (1, 2):', 'with open("x") as f:'):
        fuente = chr(10).join([
            'def ejemplo():',
            '    ' + cabecera,
            '        """Cadena dentro de un bloque de control.',
            '   Linea suelta."""',
            '        pass',
        ])
        hallados = _docstrings_descuadrados(fuente)
        assert not hallados, (
            'una cadena dentro de `%s` se ha senalado como docstring: %r'
            % (cabecera, hallados))


def test_los_alias_de_pytest_se_reconocen():
    """Que `@pt.mark.parametrize` y `@mark.parametrize` cuentan.

    Y por que importa mas de lo que parece: un NO contar es un FALLO
    SILENCIOSO. El recuento bajaria sin que nadie lo notase, y el recuento es
    una AFIRMACION que se publica.

    Y R2 lo senalo como una cuestion de contrato, no como un defecto: «reconoce
    la forma canonica, no todas las formas validas». Y hay dos salidas:
    restringir el contrato a la forma canonica, o reconocer los alias. La
    segunda es la que se ha tomado, porque MEDIDO las 17 llamadas del repo
    salen todas de la forma canonica —de modo que reconocer los alias NO
    cambia el numero de hoy— y quita una clase de fallo silencioso.

    Y el caso inventado es la prueba: sin el, el detector podria seguir sin
    reconocer los alias y el numero de hoy seria el mismo.
    """
    CASOS = (
        ('import pytest as pt', 'pt.mark.parametrize'),
        ('from pytest import mark', 'mark.parametrize'),
        ('import pytest', 'pytest.mark.parametrize'),
    )
    for importa, decorador in CASOS:
        fuente = chr(10).join([
            importa,
            '@%s("x", [1, 2])' % decorador,
            'def test_este_si():',
            '    pass',
        ])
        arbol = ast.parse(fuente)
        modulos, marcas = _nombres_de_pytest(arbol)
        d = arbol.body[1].decorator_list[0]
        assert _es_parametrize_de_pytest(d, modulos, marcas), (
            'con `%s` y `@%s` el decorador NO se reconoce, y eso es un fallo '
            'SILENCIOSO: el recuento baja sin que nadie lo note.'
            % (importa, decorador))


def test_un_decorador_ajeno_con_la_palabra_no_cuenta_nunca():
    """La mitad de la otra parte: que no cuente lo que no debe.

    Y el caso con un argumento que lleva la palabra, que es el que la regla
    de texto contaba. Y con un alias, que es la forma nueva:

        @no_es_parametrize(parametrizacion=[1, 2])   ->  no cuenta
        @pt.mark.parametrize_no_algo("x", [1])        ->  no cuenta
    """
    fuente = chr(10).join([
        'import pytest as pt',
        '',
        'def no_es_parametrize(x):',
        '    return x',
        '',
        '@no_es_parametrize(parametrizacion=[1, 2])',
        'def test_este_no_cuenta():',
        '    pass',
        '',
        '',
        '@pt.mark.parametrize_no_algo("x", [1])',
        'def test_este_tampoco():',
        '    pass',
    ])
    arbol = ast.parse(fuente)
    modulos, marcas = _nombres_de_pytest(arbol)
    contados = 0
    for nodo in arbol.body:
        if not (isinstance(nodo, ast.FunctionDef) and nodo.name.startswith('test_')):
            continue
        for decorador in nodo.decorator_list:
            if _es_parametrize_de_pytest(decorador, modulos, marcas):
                contados += 1
    assert contados == 0, (
        'han contado %d decoradores que no son de pytest. Y con la regla de '
        'texto el primero SI contaba.' % contados)

# ============================ 26. EL MUTANTE, DEL HISTORIAL
#
# Y esto es la tarea 5 de R1, y es la leccion del bloque anterior:
#
#     un caso que no muere ante un mutante equivocado no es un caso aprobado;
#     es un caso que solo se ha probado contra lo que su autor imagino
#
# Y el arreglo es una regla:
#
#     EL MUTANTE TIENE QUE SALIR DEL HISTORIAL, NO DE LA IMAGINACION.
#
# Y aqui no basta con DECIRLO: este test MONTIA el mutante con el codigo que
# hay en el historial, y comprueba que el test del `+1` lo mata. De modo que
# el mutante no puede dejar de ser el de verdad: se construye en cada
# ejecucion, desde `git`.


def _git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT,
                          capture_output=True).stdout.decode('utf-8', 'replace')


def _arbol_de(texto):
    return ast.parse(texto)


def _suma_de_mas_uno(arbol, base):
    """El `BinOp` `base + 1` de un arbol, o None.

    Y sale del ARBOL y no del texto, porque en el texto el nombre aparece
    tambien en los COMENTARIOS que explican el cambio. Y un mutante sacado
    de un comentario no es un mutante: es prosa.
    """
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add)
                and isinstance(nodo.left, ast.Name) and nodo.left.id == base
                and isinstance(nodo.right, ast.Constant)
                and nodo.right.value == 1):
            return nodo
    return None


def _expresion_de_la_linea(arbol, funcion):
    """(la funcion, la expresion) con la que calcula la linea que senala.

    Y se busca por su FORMA, y no por su texto: una suma de un indice y un
    uno. Y es la unica que hay en la funcion, de modo que si mañana aparece
    otra, este helper tiene que decirlo en vez de adivinar.
    """
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.FunctionDef) and nodo.name == funcion):
            continue
        candidatas = []
        for sub in ast.walk(nodo):
            if (isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Add)
                    and isinstance(sub.right, ast.Constant)
                    and sub.right.value == 1
                    and isinstance(sub.left, ast.Subscript)):
                candidatas.append(sub)
        assert len(candidatas) == 1, (
            'se esperaba UNA suma «indice + 1» en `%s`, y hay %d: %r. O sea '
            'que el mutante no se puede construir solo, y hay que rehacerlo.'
            % (funcion, len(candidatas), candidatas))
        return nodo, candidatas[0]
    return None, None


def test_el_mutante_del_uno_de_mas_sale_del_historial_y_mata_al_test():
    """Que el mutante sea el de VERDAD, y que el test del `+1` lo mate.

    Y la primera mitad es la importante, y es la que se puede hacer sola: el
    mutante se MONTA con el codigo que hay en el historial, encontrado con
    `git log -S` sobre el TEXTO DEL CODIGO —`% (nombre, apertura + 1,`— y no
    sobre la prosa.

    MEDIDO, y por que el texto del codigo y no «apertura + 1» a secas: en el
    texto de HOY la frase aparece en los COMENTARIOS que explican el cambio,
    de modo que una busqueda por la frase daria tambien el commit que la
    AÑADIO al comentario — y ese commit no es el que quito el codigo. Y con
    el texto del codigo, `git log -S` da exactamente dos commits: el que lo
    puso y el que lo quito.

    Y la segunda mitad: con ese mutante montado, el test del `+1` tiene que
    FALLAR. Y el fallo se busca con `assert`, y no con «no ha fallado», que es
    la confusion que el bloque anterior cometio.
    """
    REL = 'tools/test_ejecutar_pytest.py'
    CODIGO = '% (nombre, apertura + 1,'

    # 1. el commit que la quito: el que en su padre esta y en el mismo no.
    fijos = _git('log', '-S' + CODIGO, '--format=%H', '--', REL).split()
    assert fijos, (
        'no hay ningun commit que cambiara el numero de apariciones de %r. '
        'O sea que la historia no esta, y el mutante no se puede montar.'
        % CODIGO)
    quito = None
    for commit in fijos:
        propio = _git('show', '%s:%s' % (commit, REL))
        padre = _git('show', '%s^:%s' % (commit, REL))
        if not propio.strip() or not padre.strip():
            continue
        if (_suma_de_mas_uno(_arbol_de(padre), 'apertura') is not None
                and _suma_de_mas_uno(_arbol_de(propio), 'apertura') is None):
            quito = commit
            break
    assert quito, (
        'ninguno de los %d commits que tocaron %r quito la suma `apertura + 1`'
        % (len(fijos), CODIGO))

    # 2. el codigo de su padre, que es el mutante
    historico = _git('show', '%s^:%s' % (quito, REL))
    nodo_historico = _suma_de_mas_uno(_arbol_de(historico), 'apertura')
    assert nodo_historico is not None, (
        'el padre de %s no tiene la suma `apertura + 1`, y el mutante no se '
        'puede montar' % quito[:8])
    expresion_historica = ast.unparse(nodo_historico)

    # 3. el codigo de HOY, y el mutante: cambiar una cosa por la otra
    actual = io.open(os.path.join(ROOT, REL.replace('/', os.sep)),
                      encoding='utf-8').read()
    arbol_actual = _arbol_de(actual)
    funcion_actual, nodo_actual = _expresion_de_la_linea(
        arbol_actual, '_docstrings_descuadrados')
    assert nodo_actual is not None, (
        'la funcion `_docstrings_descuadrados` ya no calcula la linea con una '
        'suma, y el mutante no se puede montar.')
    expresion_actual = ast.unparse(nodo_actual)
    assert expresion_actual != expresion_historica, (
        'la expresion de HOY y la del historial son la misma: %r. O sea que el '
        'mutante seria el codigo correcto, y no mataria nada.'
        % expresion_actual)

    # 4. montar el mutante y comprobar que lo mata
    #
    # Y el recorte es el de la FUNCION, y no el de la expresion: el mutante
    # tiene que ser el modulo entero de la funcion, porque si no lo que se
    # ejecuta no es la funcion mutada sino un trozo suelto. MEDIDO, el
    # sintoma de hacerlo al reves: un `IndentationError` en la primera linea
    # del mutante.
    lineas = actual.split(chr(10))
    cuerpo = chr(10).join(lineas[funcion_actual.lineno - 1:
                                 funcion_actual.end_lineno])
    mutante = cuerpo.replace(expresion_actual, expresion_historica)
    assert expresion_historica in mutante, (
        'el mutante no se ha montado: %r no sale del cuerpo' % expresion_historica)

    espacio = {'ast': ast, '_docstring_de': _docstring_de}
    exec(compile(mutante, '<mutante-del-historial>', 'exec'), espacio)
    sustituta = espacio['_docstrings_descuadrados']

    original = _docstrings_descuadrados
    globals()['_docstrings_descuadrados'] = sustituta
    try:
        test_el_diagnostico_de_docstrings_senala_la_culpable()
        fallo = False
        detalle = 'el test ha PASADO con el mutante'
    except AssertionError as e:
        fallo = True
        detalle = str(e).split(chr(10))[0][:90]
    finally:
        globals()['_docstrings_descuadrados'] = original
    assert fallo, (
        'el mutante del historial —%r, del commit %s— NO ha matado el test '
        'del `+1`. O sea que el caso no cubre el defecto que dice cubrir.'
        % (expresion_historica, quito[:8]))
    print('   el mutante del historial: %r (commit %s) -> %s'
          % (expresion_historica, quito[:8], detalle))


def test_un_mutante_de_memoria_no_mata_nada():
    """La otra mitad, y es la que se MIDIO el bloque anterior.

    MEDIDO, y el caso de memoria:

        la variante ROTA que puse:   sueltas[0] + 1   ->  senala la 5   ->  el test PASA
        la variante ROTA de verdad:  apertura + 1     ->  senala la 3   ->  el test FALLA

    La primera no era la version anterior del codigo: era OTRA cosa que
    PARECE la version anterior. Y el caso no la mato, porque no podia: no era
    el fallo que se suponia que cubria.

    Y por que esto es un TEST y no un comentario: un mutante de memoria es
    indistinguible del de verdad HASTA QUE SE PRUEBA. Y aqui se prueba: se
    monta el codigo de HOY como si fuera el mutante, y se mira que no mata
    nada.

    Y el motivo por el que el codigo de HOY es el mutante de memoria tipico:
    es lo que se escribe de cabeza, porque es lo que se ve al leer el codigo
    sin ir a la historia. Y es CORRECTO. De modo que el caso pasaria, el
    guardarian estaria bien, y la hoja de ruta diria «cubierto». La cobertura
    aparente y la real habrian divergido sin que nadie lo viera.
    """
    REL = 'tools/test_ejecutar_pytest.py'
    actual = io.open(os.path.join(ROOT, REL.replace('/', os.sep)),
                      encoding='utf-8').read()
    funcion_actual, nodo = _expresion_de_la_linea(
        _arbol_de(actual), '_docstrings_descuadrados')
    assert nodo is not None
    expresion = ast.unparse(nodo)

    # el mutante de memoria: el codigo de HOY, puesto donde estaba el malo
    lineas = actual.split(chr(10))
    cuerpo = chr(10).join(lineas[funcion_actual.lineno - 1:
                                 funcion_actual.end_lineno])
    mutante = cuerpo.replace(expresion, expresion + ' + 0')
    assert mutante != cuerpo, (
        'el mutante de memoria es IGUAL al codigo de hoy, de modo que aqui no '
        'se ha montado nada. Y la conclusion del test —«un mutante de memoria '
        'no mata nada»— seria la de un mutante que no existe. Que es el mismo '
        'hueco que el del mutante escrito a mano, un nivel mas adentro: no '
        'basta con que el mutante no mate, hay que que sea EL mutante.')
    assert expresion + ' + 0' in mutante, (
        'y el mutante no lleva la expresion que deberia: %r' % expresion)
    espacio = {'ast': ast, '_docstring_de': _docstring_de}
    exec(compile(mutante, '<mutante-de-memoria>', 'exec'), espacio)

    original = _docstrings_descuadrados
    globals()['_docstrings_descuadrados'] = espacio['_docstrings_descuadrados']
    try:
        test_el_diagnostico_de_docstrings_senala_la_culpable()
        fallo = False
    except AssertionError:
        fallo = True
    finally:
        globals()['_docstrings_descuadrados'] = original
    assert not fallo, (
        'un mutante de memoria ha matado el test, y eso no deberia pasar: un '
        'mutante de memoria no es el defecto, es otra cosa que se parece.')

# ============================ 27. LA POLITICA DE LOS FICHEROS ILEGIBLES
#
# Y esto es la tarea 2 de R1, que es la que faltaba:
#
#     _parametrizados lanza AssertionError con el nombre del fichero, no continue
#     _tests_de tambien lanza, no continue
#     las dos funciones tienen la misma politica
#     si se vuelve al continue, el test falla
#
# Y la cuarta es la que hace que las otras tres valgan, y por eso el caso es
# INVENTADO: un fichero con sintaxis mala, en un directorio temporal.


def test_un_fichero_ilegible_hace_fallar_las_dos_cuentas():
    """Que un `.py` que no se puede leer PARA, en las dos funciones.

    Y el caso es inventado, y tiene que serlo: MEDIDO, en el repo no hay
    ningun fichero ilegible, de modo que la comprobacion real pasaria con
    CUALQUIER cosa —incluido un `continue`—.

    Y las dos mitades, porque son dos medidas distintas y una sola comprobacion
    no las cubre:

      1. `_parametrizados` lanza y nombra el fichero;
      2. `_tests_de` lanza y nombra el fichero.

    Y el motivo de que el mensaje nombre el fichero, y no solo de que lance: un
    `continue` que se traga un fichero convierte el recuento en una
    DECLARACION —«hay 17 funciones parametrizadas»— y si se tragara uno, la
    declaracion seria falsa y nadie lo veria. Un fallo con nombre se ve;
    un recuento sin fichero se come.
    """
    with tempfile.TemporaryDirectory() as alta:
        io.open(os.path.join(alta, 'roto.py'), 'w',
                encoding='utf-8').write('def f(:' + chr(10))
        for nombre, llamada in (('_parametrizados', _parametrizados),
                                ('_tests_de', _tests_de)):
            try:
                llamada(alta)
                fallo = None
            except AssertionError as e:
                fallo = str(e)
            except Exception as e:                  # noqa: BLE001
                fallo = '%s de Python, y no una AssertionError' % type(e).__name__
            assert fallo is not None, (
                '%s ha devuelto el recuento de un directorio con un fichero '
                'ilegible, y no ha fallado. O sea que se lo ha tragado, y el '
                'recuento es una DECLARACION sin el fichero que falta.'
                % nombre)
            assert 'roto.py' in fallo, (
                '%s ha fallado, pero el mensaje no nombra el fichero: %r. Un '
                'fallo sin nombre obliga a abrir el directorio a mano.'
                % (nombre, fallo[:160]))
            assert 'AssertionError' not in fallo, (
                '%s ha fallado con otra excepcion: %r' % (nombre, fallo[:160]))


def test_las_dos_funciones_tienen_la_misma_politica():
    """Que la politica sea UNA, y no dos.

    Y como se comprueba: por el ARBOL, y no por el texto. Y lo que se mira es
    que el manejador de la excepcion NO contenga un salto —un `continue` o un
    `break`—, y que su cuerpo sea un `raise`.

    Y por que el ARBOL y no el texto: en el texto de estos dos ficheros la
    palabra «continue» esta en los COMENTARIOS que explican por que se
    quito, y una comprobacion por texto las encontraria y diria que el
    problema sigue. Lo que no puede es EXISTIR.
    """
    arbol = ast.parse(io.open(__file__, encoding='utf-8').read())
    for nombre in ('_parametrizados', '_tests_de'):
        funcion = next(n for n in ast.walk(arbol)
                       if isinstance(n, ast.FunctionDef) and n.name == nombre)
        manejadores = [h for sub in ast.walk(funcion)
                       if isinstance(sub, ast.Try)
                       for h in sub.handlers]
        assert manejadores, (
            '%s no tiene ningun manejador de excepcion, y por tanto no tiene '
            'politica declarada para un fichero ilegible' % nombre)
        for manejador in manejadores:
            tipos = ast.unparse(manejador.type) if manejador.type else '?'
            assert 'SyntaxError' in tipos and 'UnicodeDecodeError' in tipos, (
                '%s maneja %s, y lo que tiene que manejar es un fichero que no '
                'se puede leer ni parsear' % (nombre, tipos))
            saltos = [n.lineno for n in ast.walk(manejador)
                      if isinstance(n, (ast.Break, ast.Continue))]
            assert not saltos, (
                '%s vuelve al `continue` en las lineas %r. Y un `continue` que '
                'se traga un fichero convierte el recuento en una declaracion.'
                % (nombre, saltos))
            raises = [n for n in ast.walk(manejador)
                      if isinstance(n, ast.Raise)]
            assert raises, (
                '%s no lanza nada en su manejador, y lo que tiene que hacer es '
                'PARAR y nombrar el fichero' % nombre)



# ============================ 28. LA DECLARACION, ATADA HALLAZGO POR HALLAZGO
#
# Y esto es el matiz que R2 senalo: que el documento que declara los hallazgos
# este asociado a los hallazgos de verdad, y no solo a sus nombres.


def test_el_docstring_descuadrado_declarado_esta_donde_dice():
    """Que la declaracion apunte al docstring REAL, y no a uno inventado.

    Y el motivo de que este test exista: la declaracion dice «el docstring
    descuadrado de `motor/asistente_live.py`», y sin comprobarlo el documento
    podria estar nombrando un desfase que ya no esta, o ninguno.

    Y la LINEA se compara con la del documento, y no solo el fichero. Y es el
    mismo patron que el hash de `CANAL_MANUAL_CERRADO.md`: una cifra
    declarada, y un test que la compara con la medida. Y una declaracion que
    nombra un sitio que ya no es el suyo es una declaracion falsa.

    Y MEDIDO, que el desfase sigue ahi: una linea a la columna 0 dentro de un
    docstring que esta a la columna 8.
    """
    with io.open(os.path.join(ROOT, 'motor', 'asistente_live.py'),
                 encoding='utf-8') as f:
        texto = f.read()
    hallados = _docstrings_descuadrados(texto)
    assert len(hallados) == 1, (
        'MEDIDO, en `motor/asistente_live.py` hay %d docstrings descuadrados, '
        'y la declaracion dice que hay uno: %r. O el desfase se ha corregido —y '
        'entonces la declaracion esta vieja— o hay otro, y la declaracion esta '
        'incompleta.' % (len(hallados), hallados))
    _nombre, linea, _cuenta = hallados[0]

    with io.open(os.path.join(ROOT, 'DOCS', 'HALLAZGOS_DECLARADOS.md'),
                 encoding='utf-8') as f:
        doc = f.read()
    filas = [l for l in doc.split(chr(10))
             if l.startswith('| `motor/asistente_live.py` |')]
    assert len(filas) == 1, (
        'la declaracion tiene %d filas para el docstring descuadrado, y se '
        'espera UNA: %r' % (len(filas), filas))
    celdas = [c.strip() for c in filas[0].strip('|').split('|')]
    assert len(celdas) == 3, (
        'la fila tiene %d celdas, y se esperan tres: fichero, linea y que es'
        % len(celdas))
    assert celdas[1] == str(linea), (
        'la declaracion dice la linea %s y la real es la %d. Y una declaracion '
        'que nombra un sitio que ya no es el suyo es una declaracion falsa.'
        % (celdas[1], linea))
    assert celdas[2], 'y la tercera celda, que es el QUE ES, esta vacia'

# ============================ 29. LOS ACUMULADORES DEL REPO, REVISADOS
#
# Y esto es el punto abierto que dejo abierto el bloque anterior, y que R2
# senalo: las 46 asignaciones `d[clave] = <lista o dict>` del repo eran
# «candidatos pendientes de revision individual», y yo habia escrito que eran
# «acumuladores de propiedades». Y eso era una AFIRMACION sin medir.
#
# Y este bloque mide, y declara, y vigila.


class _RastreadorDeSobrescrituras(ast.NodeVisitor):
    """Las asignaciones que sobrescriben, y si estan dentro de un bucle.

    Y una PILA de bucles, y no un `in`: lo que importa es si la asignacion se
    puede ejecutar mas de una vez para la MISMA clave, y eso lo decide el
    bucle mas cercano que la envuelve.
    """

    def __init__(self):
        self.pila = []
        self.hallados = []

    def _bucle(self, nodo, iterable):
        self.pila.append(iterable)
        self.generic_visit(nodo)
        self.pila.pop()

    def visit_For(self, nodo):
        self._bucle(nodo, ast.unparse(nodo.iter))

    def visit_AsyncFor(self, nodo):
        self._bucle(nodo, ast.unparse(nodo.iter))

    def visit_While(self, nodo):
        self._bucle(nodo, 'while')

    def visit_Assign(self, nodo):
        for t in nodo.targets:
            if not isinstance(t, ast.Subscript):
                continue
            if not isinstance(nodo.value, (ast.List, ast.Dict)):
                continue
            self.hallados.append((nodo.lineno, ast.unparse(t),
                                  bool(self.pila)))
        self.generic_visit(nodo)


def _asignaciones_que_sobrescriben():
    """(todas, en_bucle) de las asignaciones `d[clave] = <lista o dict>`.

    Y la forma que se busca es esa, y no cualquier `d[clave] = <valor>`,
    porque una asignacion de un numero, o de una cadena, NO PIERDE NADA: el
    valor es completo por definicion. Lo que pierde es una asignacion de una
    LISTA o de un DICCIONARIO, porque entonces el valor es una ACUMULACION y
    la anterior se pierde.

    Y MEDIDO, y por que la forma del ARBOL y no un `grep`: un `grep` por
    `] = [` encuentra tambien las asignaciones a indices de LISTAS, que no son
    diccionarios y no deducen nada.

    Y devuelve DOS listas, y la segunda es la que importa: las que estan
    dentro de un bucle, que son las UNICAS que pueden tener la clave
    repetida. Las demas se ejecutan una vez por llamada, y su clave se
    asigna una sola vez por construccion.
    """
    todas = []
    en_bucle = []
    for carpeta in CARPETAS_DEL_INVENTARIO:
        base = os.path.join(ROOT, carpeta)
        if not os.path.isdir(base):
            continue
        for sub, directorios, ficheros in os.walk(base):
            directorios[:] = [d for d in directorios
                              if d not in CARPETAS_QUE_NO_SE_MIRAN]
            for nombre in sorted(ficheros):
                if not nombre.endswith('.py'):
                    continue
                ruta = os.path.join(sub, nombre)
                rel = os.path.relpath(ruta, ROOT).replace(os.sep, '/')
                rastreador = _RastreadorDeSobrescrituras()
                rastreador.visit(ast.parse(
                    io.open(ruta, encoding='utf-8').read()))
                for linea, clave, dentro in rastreador.hallados:
                    todas.append((rel, linea, clave))
                    if dentro:
                        en_bucle.append((rel, linea, clave))
    return todas, en_bucle


# Los 8 sitios donde la clave puede REPETIRSE, y por que cada uno esta bien.
#
# Y MEDIDO, el barrido: 46 asignaciones `d[clave] = <lista o dict>` en el
# repo, de las que 38 estan FUERA de todo bucle —y ahi la clave se asigna una
# sola vez por construccion, de modo que sobrescribir no puede perder nada— y
# 8 dentro. Y esas 8 son las unicas que hay que mirar.
#
# Y el formato es (fichero, clave) -> porque. Y el PORQUE es lo que hace que
# esto sea una DECLARACION y no una lista: un test no puede juzgar un texto,
# pero si puede comprobar que NO FALTA ninguno.
ACUMULADORES_REPETIBLES = {
    ('tools/test_integrar_copia.py', 'pre[j]'):        'una LISTA y no un diccionario, y cada indice se escribe una vez: la forma es mas ancha que el defecto',    ('motor/preflop.py', 'tables[name]'):
        'la clave es el NOMBRE de una tabla, y las claves de un dict son '
        'unicas',
    ('tools/cuarentena.py', 'q[hid]'):
        'la clave es el IDENTIFICADOR de la mano, y cada mano se escribe una '
        'vez: la ultima escritura es la de esa misma mano, de modo que no se '
        'pierde nada. Y el sitio es de A1, que lo ha anadido con la '
        'cuarentena.',
    ('motor/test_ranges.py', 'rank_pair_data[rank_key]'):
        'la clave sale del INDICE del bucle, y un indice no se repite',
    ('motor/test_stats.py', 'streets[key]'):
        'las tres claves son LITERALES y distintas: flop, turn y river',
    ('tools/auditar_defectos_vs_denominadores.py', "h['winner']"):
        'la clave es LITERAL, pero el bucle SALE con `break` en cuanto la '
        'asigna, de modo que se asigna una sola vez',
    ('tools/equity_preflop_observables.py', 'cache[hid]'):
        'la clave es un id de MANO, y un id no se repite',
    ('tools/lector_estado.py', 'self.digit_templates[ch]'):
        'la clave es una clave de un dict, y las claves de un dict son unicas',
    ('tools/lector_estado.py', 'region_data[rname][v]'):
        'la clave REPETIDA es el objetivo: agrupa los ficheros que muestran el '
        'mismo valor. Y la asignacion va con una guardia `if v not in '
        'region_data[rname]`, que es lo que hace que sea un ACUMULADOR y no '
        'una sobrescritura',
    ('tools/reconstruir_derivados.py', 'hashes[name]'):
        'la clave es un NOMBRE de fichero, y la lista de nombres es una '
        'CONSTANTE con 7 nombres distintos',
}

# Y el total, que es una cifra y por lo tanto vive en una constante.
# Y MEDIDO, por que el numero se declara y no se deriva: la FORMA `d[clave] =
# <lista o dict>` no distingue un DICCIONARIO de una LISTA, y una lista no
# pierde nada al sobrescribir —cada indice se escribe una vez—. De modo que la
# forma es mas ANCHA que el defecto, y por eso el numero se declara: cada
# sitio nuevo es una decision, y el total es el que se vigila.
ASIGNACIONES_QUE_SOBRESCRIBEN = 48


# Los ficheros que estan fuera de las tres carpetas del inventario, y el
# motivo de cada uno.
#
# Y MEDIDO, el motivo de que esta lista exista: el codigo del repo vive en
# `tools/`, `motor/` y `recorder/`, y lo que se queda fuera no lo vigilaba
# NADA: ni el inventario, ni el control de caracteres, ni el de docstrings.
#
# Y un fichero que nadie vigila es un fichero que nadie lee. De modo que
# esta lista los NOMBRA, y el guardian de mas abajo falla si aparece uno que
# no este aqui. Que es lo contrario de ampliar la lista de excepciones: es
# obligar a decidir.
#
# Y los `.py`, los `.md` y los `.jsonl` de la raiz y de `trabajo/` estan
# ADEMAS bajo el barrido de caracteres, que los recorre. De modo que la lista
# no es una exccepcion: es la declaracion de POR QUE estan ahi.
#
# Y los `.txt` y el `.csv` de la raiz NO estan en esta lista, y el motivo esta
# en `tools/verificar_caracteres.py`: los `.txt` pueden estar en UTF-16LE, y
# la politica es de los `.txt` en general; y el `.csv` es una tabla de datos,
# no codigo ni documentacion del motor.
FUERA_DEL_INVENTARIO = {
    # el codigo
    'hand_editor.py':
        'el editor de la COPIA de trabajo, del trabajo en paralelo de la base',
    'trabajo/ABRIR_EDITOR_COPIA.py':
        'el lanzador del editor, del trabajo en paralelo de la base',
    # los documentos del trabajo en paralelo
    'APUESTAS_DIFICILES.md':
        'el catalogo de las apuestas que hay que mirar en las grabaciones',
    'AUDITORIA_SEMANTICA_GRABADOR.md':
        'la auditoria semantica del grabador',
    'FRONTERA_GRABADOR.md':
        'la frontera entre las dos generaciones de grabador',
    'INDICE_DEFECTOS.md':
        'el indice de los defectos que quedan por revisar',
    'PLAN_EDICION_DB.md':
        'el plan de edicion de la base',
    'REVISION_DIAGNOSTICO_GRABADOR.md':
        'la revision del diagnostico del grabador',
    'trabajo/BOTES_NO_ENCONTRADOS.md':
        'los botes que no cuadran con la grabacion',
    # los datos del trabajo en paralelo
    'trabajo/hands_db_edicion.jsonl':
        'la COPIA normalizada de la base, que A1 esta revisando',
    'trabajo/botes_aritmetica.jsonl':
        'los botes calculados con la aritmetica de la copia',
    'trabajo/botes_aritmetica_origen.jsonl':
        'los botes calculados con la aritmetica de siempre',
}


def test_el_codigo_fuera_del_inventario_esta_declarado():
    """Que no aparezca codigo fuera de las tres carpetas sin declararse.

    Y el motivo: el inventario, el control de caracteres y el de docstrings
    miran `tools/`, `motor/` y `recorder/`. Un `.py` en la raiz, o en
    `trabajo/`, no lo mira NINGUNO. Y si no esta declarado, no lo vigila nadie
    y no se sabe por que esta ahi.

    Y el fallo tiene que NOMBRAR el fichero, porque un guardián que dice
    «hay un problema» sin decir cual es un guardián que se mira por encima.
    """
    declarados = set(FUERA_DEL_INVENTARIO)
    vistos = []
    for nombre in sorted(os.listdir(ROOT)):
        ruta = os.path.join(ROOT, nombre)
        if nombre in CARPETAS_DEL_INVENTARIO or nombre.startswith('.'):
            continue
        if os.path.isfile(ruta) and nombre.endswith('.py'):
            vistos.append(nombre)
        elif os.path.isdir(nombre) and nombre == 'trabajo':
            for n2 in sorted(os.listdir(ruta)):
                if n2.endswith('.py'):
                    vistos.append('trabajo/' + n2)
    sin_declarar = sorted(set(vistos) - declarados)
    assert not sin_declarar, (
        'hay %d fichero(s) de codigo fuera de las carpetas del inventario y '
        'sin declarar: %r.\n\nY no declararlos no es una opcion: un '
        'fichero fuera del alcance de los guardianes no lo vigila nadie, y '
        'eso hay que decidirlo, no dejarlo.\n\nLos declarados, con su '
        'motivo: %r' % (len(sin_declarar), sin_declarar,
                        sorted(FUERA_DEL_INVENTARIO)))
    # Y lo declarado tiene que EXISTIR, que es la otra mitad: una declaracion
    # de algo que ya no esta es una declaracion falsa.
    # Y la otra mitad —«los declarados existen»— la comprueba
    # `test_los_ficheros_declarados_existen_y_estan_vigilados`, que mira los
    # DOCE y no solo los `.py`. Y aqui solo se comprueba que no haya codigo sin
    # declarar, que es lo propio de este test.


def test_los_ficheros_declarados_existen_y_estan_vigilados():
    """Que los doce declarados EXISTAN, y que los de texto esten vigilados.

    Y la segunda mitad es la que importa: un fichero declarado que ha
    desaparecido es un hueco nuevo, y la lista se queda con una entrada que no
    vigila nada. Y la tercera: los `.md` y los `.jsonl` declarados tienen que
    estar BAJO el barrido, que es lo que hace que la declaracion no sea una
    decoracion.
    """
    faltan = []
    for nombre in sorted(FUERA_DEL_INVENTARIO):
        ruta = os.path.join(ROOT, nombre.replace('/', os.sep))
        if not os.path.isfile(ruta):
            faltan.append(nombre)
    assert not faltan, (
        'hay %d fichero(s) declarados que no existen: %r. Y una declaracion '
        'de algo que no esta es una declaracion falsa.' % (len(faltan), faltan))
    import verificar_caracteres as VC
    sin_vigilar = []
    for nombre in sorted(FUERA_DEL_INVENTARIO):
        if not nombre.endswith(('.md', '.jsonl')):
            continue
        if not any(VC._coincide_con(patron, nombre)
                   for patron in VC.PATRONES):
            sin_vigilar.append(nombre)
    assert not sin_vigilar, (
        'estos ficheros estan declarados, pero el barrido de caracteres NO los '
        'mira: %r. Y una declaracion que no vigila nada es una decoracion.'
        % sin_vigilar)


def test_las_asignaciones_que_sobrescriben_estan_revisadas():
    """Que las 46 asignaciones del repo estan REVISADAS, y no supuestas.

    Y el cierre de un punto que el bloque anterior dejo ABIERTO, y que R2
    senalo: yo habia escrito que las 46 eran «acumuladores de propiedades», y
    eso era una afirmacion sin medir. MEDIDO: 46 en total, 38 fuera de todo
    bucle, y 8 dentro.

    Y las 38 de fuera se descartan por una razon MECANICA y no por opinion:
    sin bucle que las envuelva, la asignacion se ejecuta una vez por llamada,
    y su clave se asigna una sola vez. Sobrescribir no puede perder nada.

    Y las 8 de dentro SI pueden tener la clave repetida, de modo que cada una
    lleva escrito POR QUE esta bien. Y el motivo es PROSA leida por una
    persona, y un test no puede juzgarla: lo que el test puede es comprobar
    que NO FALTA ninguna, y que ninguno es un marcador de posicion.

    Y el reparto de las dos mitades, y por que el test compara CONJUNTOS: si
    un sitio nuevo aparece en un bucle, tiene que aparecer en la declaracion,
    y si uno sale, tiene que salir. Y la comparacion es de conjuntos porque
    lo que se mira es la IGUALDAD, no la pertenencia.
    """
    todas, en_bucle = _asignaciones_que_sobrescriben()
    assert len(todas) == ASIGNACIONES_QUE_SOBRESCRIBEN, (
        'hay %d asignaciones que sobrescriben, y el declarado es %d. Si se ha '
        'añadido una, hay que declararla; y si se ha quitado una, hay que '
        'bajar la cifra a mano. Las dos cosas son decisiones.'
        % (len(todas), ASIGNACIONES_QUE_SOBRESCRIBEN))

    medidos = set((f, c) for f, _l, c in en_bucle)
    declarados = set(ACUMULADORES_REPETIBLES)
    faltan = sorted(medidos - declarados)
    sobran = sorted(declarados - medidos)
    assert not faltan, (
        'hay %d sitio(s) donde la clave puede repetirse y NO estan '
        'declarados: %r. Y un sitio sin revisar es un sitio donde nadie ha '
        'mirado.' % (len(faltan), faltan))
    assert not sobran, (
        'hay %d sitio(s) declarados que ya no estan: %r. Y una declaracion de '
        'algo que ya no esta es una declaracion falsa.' % (len(sobran), sobran))

    for clave, porque in sorted(ACUMULADORES_REPETIBLES.items()):
        assert porque.strip(), (
            'el sitio %r no tiene porque escrito. Y un sitio sin porque es una '
            'lista, no una declaracion.' % (clave,))
        assert porque.strip(' .') not in ('-', '—', 'TODO', '...'), (
            'el porque de %r es un marcador de posicion.' % (clave,))
