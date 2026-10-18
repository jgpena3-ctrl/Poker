# -*- coding: utf-8 -*-
"""CORRER UN TEST DE PYTEST DESDE OTRO TEST, Y SABER QUE SE HA EJECUTADO.

QUE RESUELVE, y de donde sale

`pytest FICHERO -q ::test` no selecciona nada: exit 4, «no tests ran». Y 4 no
es 0, asi que un `assert returncode != 0` sobre eso PASA, en verde, sin que
se haya ejecutado un solo test.

Y eso no fue un fallo teorico de este bloque: lo hubo. Tres ficheros de test
usaban `!= 0` sobre el resultado de un subproceso, y ninguno comprobaba que
el test hubiera corrido. Si el selector se hubiera descolocado, los tres
habrian seguido dando verde.

MEDIDO, no supuesto

    FICHERO -q ::test   ->  codigo 4   (no se ha ejecutado nada)
    FICHERO::test       ->  codigo 1   (ha fallado el que se queria)

LAS CUATRO REGLAS, y por que las cuatro

1. EL SELECTOR VA ADJACENTE AL FICHERO: `FICHERO::test`, no `-q ::test`.

   Es la diferencia entre «ejecuta esto» y «no encuentra nada, y te lo dice
   con un codigo que parece un fallo». El orden importa porque pytest
   parsea los argumentos de izquierda a derecha.

   Y no se deja a la buena fe del que escribe: `auditar_comando()` RECHAZA
   un comando con el selector suelto. Un error de tecleo que se puede
   repetir no se corrige con cuidado, se corrige con una comprobacion.

   Y esa comprobacion vive FUERA de `construir()`, a proposito. La primera
   version la puso dentro, y alli es CODIGO MUERTO: `construir()` monta el
   comando ella misma, asi que la condicion no puede ser falsa nunca. Una
   comprobacion que no puede fallar no vigila nada — y da la sensacion de
   que vigila, que es peor que no tenerla.

   Por eso hay dos funciones: `construir()` monta, `auditar_comando()`
   juzga. Y la segunda juzga cualquier comando, incluido el que monta la
   primera.

2. EL CODIGO ES CONCRETO: 0 o 1. Nunca «distinto de cero».

   Un 4 — que significa «no se ha ejecutado nada» — tambien es «distinto de
   cero». Y un 5 — que significa «no se ha encontrado ningun test» — igual.
   Los dos pasan un `!= 0` en verde, que es exactamente el defecto.

3. LA SALIDA DICE CUANTOS, Y EN VERDE EL NOMBRE NO ESTA.

   Medido: con `-q --no-header`, un test que PASA imprime `.` y `1 passed`, y
   su nombre NO aparece en ningun sitio. O sea que buscar el nombre para
   probar que ha corrido, en verde, no se puede: sale falso siempre.

   Y en ROJO si aparece: `FAILED tools/x.py::test_nombre`.

   Asimetría que obliga a dos comprobaciones distintas, no a una con un `or`.
   En verde se mira el RECUENTO (`1 passed`); en rojo, el NOMBRE.

4. EN ROJO, EL NOMBRE TIENE QUE SER EL MIO.

   El codigo 1 dice que algo fallo. El nombre dice que fallo lo que yo
   queria. Un `import` roto da 1 sin que mi test llegara a ejecutarse, y es
   un fallo con otra causa — y un test de sensibilidad que cae por un import
   roto no ha acreditado nada.

   Y para un fichero ENTERO no hay nombre: se exige un recuento de fallos
   (`N failed`) en vez de un nombre. Que es la misma idea con el dato que
   esa forma de ejecucion da.

POR QUE UN MODULO Y NO TRES COPIAS

Tres ficheros usaban la comprobacion por su cuenta, cada una con su
`!= 0`. Que es lo que hace que un error se repita: si la regla esta escrita
tres veces, el proximo que la escriba mal solo tiene que equivocarse una.

LO QUE NO HACE

No interpreta el fallo. Dice que ha caido uno y que era el esperado; que lo
haya caido por la razon que se pretendia, lo comprueba el test de
aceptacion que esta al otro lado del subproceso.
"""
import os
import re
import subprocess
import sys

from retraccion_scan import DIR_DE_DOCUMENTOS

CODIGO_NINGUNO_EJECUTADO = 4      # INTERRUPTED: no se ha ejecutado nada
CODIGO_NINGUNO_ENCONTRADO = 5     # NO_TESTS_COLLECTED: no existe ese test

# ============================================ escrito y no probado
#
# Un AMBITO —el de un test— con lo que se le ha hecho y EN ORDEN:
#
#     ('escrito', que)      una mutacion, por `escribir_documento`
#     ('ejecutado', test)   un test que se ha corrido contra el
#
# Y la REGLA es sobre la secuencia, no sobre el estado final:
#
#     una escritura va seguida de una ejecucion, antes de la siguiente
#     escritura del mismo directorio
#
# Y POR QUE UN REGISTRO Y NO UNA MARCA POR DIRECTORIO
#
# La marca era por directorio, y las tres roturas de un contrato comparten
# directorio: la ejecucion de la rotura COSMETICA desmarcaba lo que habia
# escrito la de AFIRMACION, y «escrito sin probar» queria decir «escrito y
# sin probar despues» — una condicion mas debil que aqui no se cumple
# nunca. MEDIDO: con la ejecucion del contenido borrada, daba `codigo = 0`.
#
# Y por que la secuencia y no un invariante de FUENTE, que es lo mismo:
# el de fuente —«entre dos escrituras hay una ejecucion»— da CINCO falsos
# positivos en `tools/`, y los cinco son ficheros que se CONSTRUYEN con
# varias escrituras. Esos no pasan por `escribir_documento`, y por eso aqui
# no cuentan.
_ALCANCE = None


class _Ambito:
    """El ambito del test actual. Y el `try/finally` va AQUI, no en el
    fixture.

    MEDIDO: pytest no deja llamar a un fixture directamente
    (`Fixture called directly`), y este `finally` es la rama de codigo que
    hay que comprobar — la excepcion que tira el ambito por debajo —. Si la
    logica viviera en el fixture, la prueba no se podria escribir.

    Y no la prueba reimplementando la logica, que es lo facil: seria probar
    una COPIA, y una copia puede tener un `finally` y el original no.
    """

    def __init__(self):
        self.anterior = None

    def __enter__(self):
        global _ALCANCE
        self.anterior = _ALCANCE
        _ALCANCE = {}
        return _ALCANCE

    def __exit__(self, exc_type, exc, tb):
        global _ALCANCE
        # Y RESTAURA el anterior, no pone None a pelo: `ambito()` anida, y
        # sin restauracion un ambito dentro de otro deja al exterior sin
        # registro — y el que abria el exterior creeria que tiene uno.
        _ALCANCE = self.anterior
        return False           # que la excepcion siga su camino


def ambito():
    """El ambito, como gestor de contexto.

    Y lo envuelve el `autouse` de `conftest.py`, que es quien decide que se
    abra SOLO. Que se abra solo es lo que evita que se tenga que acordarse."""
    return _Ambito()


def abrir_ambito():
    """Sin gestor de contexto, para lo que no pueda usar `with`.

    Y quien lo necesite tiene que acordarse de cerrar, que es justo lo que el
    `ambito()` evita. Por eso el fixture usa `ambito()` y no esto."""
    global _ALCANCE
    _ALCANCE = {}
    return _ALCANCE


def cerrar_ambito():
    """Lo contrario, para que el siguiente test no encuentre lo que este
    dejo. Sin esto el registro se pisa entre tests, que es MEDIDO."""
    global _ALCANCE
    _ALCANCE = None


def _exigir_ambito(que):
    if _ALCANCE is None:
        raise AssertionError(
            '%s se ha llamado FUERA de un test. Sin ambito no hay registro, '
            'y sin registro esta comprobacion no vigila nada: devolveria '
            '«nada pendiente» siempre, que es verde por no mirar. O se usa '
            'dentro de un test, o no se marca.' % que)
    return _ALCANCE


def escribir_documento(ruta, texto, que):
    """Escribe un documento mutado y REGISTRA que todavia no se ha probado.

    Y `que` es el nombre de la mutacion: es lo unico que aparecera en el
    fallo si llega a quedar sin probar, y un fallo que dice «falta probar»
    sin decir que es inaccionable.

    Y por `escribir_documento` y no un `f.write` a pelo: la marca es lo que
    distingue una MUTACION de un fichero que se esta CONSTRUYENDO. Un
    `f.write` no se marca porque no es una mutacion, y marcarlo haria que
    el invariante contara la construccion de un fixture como un defecto."""
    alcances = _exigir_ambito('escribir_documento()')
    with open(ruta, 'w', encoding='utf-8', newline='') as f:
        f.write(texto)
    directorio = os.path.dirname(os.path.abspath(ruta))
    alcances.setdefault(directorio, []).append(('escrito', que))
    return directorio


def _registrar_ejecucion(directorio, test):
    """Un test se ha corrido contra ese directorio. Con ORDEN, que es lo que
    hace falta: el fallo anterior venia de perder el orden.

    Y va DESPUES del corte de 4 y 5, que es donde se ve si el test ha
    corrido de verdad: desmarcar antes seria el error que este bloque lleva
    veintiocho rondas corrigiendo —un instrumento que dice «probado» sin
    haber probado— con otro nombre."""
    if directorio and _ALCANCE is not None:
        _ALCANCE.setdefault(directorio, []).append(
            ('ejecutado', test or 'el fichero entero'))


def sin_probar():
    """Las escrituras que no tienen una ejecucion ANTES de la siguiente.

    Y son pares `(que, directorio)`, en orden, que es como los muestra el
    fallo. Que sea una lista y no un conjunto no es estilo: dos mutaciones
    en el mismo directorio no son una, y contarlas como una seria el mismo
    error del que este bloque lleva veintiocho rondas — hacer bien la
    comprobacion sobre un objeto que no es el que hay que mirar."""
    alcances = _exigir_ambito('sin_probar()')
    pendientes = []
    for directorio in sorted(alcances):
        escritura = None
        for tipo, que in alcances[directorio]:
            if tipo == 'escrito':
                if escritura is not None:
                    pendientes.append((escritura[1], directorio))
                escritura = (tipo, que)
            else:                      # una ejecucion la absuelve
                escritura = None
        if escritura is not None:
            pendientes.append((escritura[1], directorio))
    return pendientes


QUE_SIGNIFICA = {
    0: 'todo verde',
    1: 'ha fallado ALGO',
    2: 'interrumpido',
    3: 'error interno de pytest',
    4: ' USO INTERNO DE PYTEST: NO SE HA EJECUTADO NINGUN TEST',
    5: 'NO SE HA ENCONTRADO NINGUN TEST',
}


# =================================================== la regla, juzgada aparte
def auditar_comando(cmd):
    """Juzga un comando de pytest Builtin y devuelve None, o falla.

    Deliberadamente aparte de `construir()`: si la comprobacion viviera
    dentro de la que monta el comando, no podria fallar nunca. Y ahi esta su
    valor — juzga un comando ya escrito, incluido el de cualquiera."""
    cmd = list(cmd)
    for i, a in enumerate(cmd):
        if a == '--':
            break
        if a.startswith('::'):
            # hay un selector suelto: hay que mirar lo que va justo antes
            anterior = cmd[i - 1] if i else ''
            assert anterior.endswith('.py'), (
                'el selector `%s` va suelto, sin el fichero delante. pytest '
                'parsea de izquierda a derecha, asi que lo que ha leido antes '
                '—`%s`— no era un selector de fichero y esto no selecciona '
                'nada: da %d («no tests ran»), que no es 0 y por tanto pasa un '
                '`!= 0` en verde.\n'
                '  Poner el selector ADJACENTE: FICHERO::test'
                % (a, anterior, CODIGO_NINGUNO_EJECUTADO))
    # Y «menciona un fichero» es «el argumento CONTIENE `.py`», no
    # «el argumento ACABA en `.py`». Con el selector pegado
    #
    #     test_causa_no_validez.py::test_la_prueba_causal_sigue_en_pie
    #
    # lo que acaba en `.py` no es nada: es el nombre del test. Y una
    # version anterior usaba `endswith('.py')`, con lo que rechazaba
    # justo los comandos bien formados — la version mas absurda de
    # tener codigo muerto: no es que no vigile, es que vigila lo
    # contrario de lo que dice.
    assert any('.py' in a for a in cmd), (
        'el comando no menciona ningun fichero .py, asi que pytest '
        'correria sobre el directorio entero. Eso no es lo que se ha '
        'pedido: %r' % cmd)
    return None


# =================================================== montar y correr
def construir(fichero, test=None, extra=()):
    """El comando, con el selector ADJACENTE."""
    fichero = str(fichero)
    if not os.path.isabs(fichero):
        fichero = os.path.join(os.getcwd(), fichero)
    assert os.path.exists(fichero), 'el fichero no existe: %s' % fichero
    sel = fichero if test is None else '%s::%s' % (fichero, test)
    cmd = [sys.executable, '-m', 'pytest', sel,
           '-q', '--no-header', '-p', 'no:cacheprovider'] + list(extra)
    auditar_comando(cmd)
    return cmd


def crudo(fichero, test=None, env=None, cwd=None, extra=()):
    """El codigo de pytest, SIN cortar. Y solo para comprobar que el corte
    funciona.

    Y hay una sola excepcion a la regla del repositorio, y es esta. El
    conflicto es real y medido: `test_el_exit_code_4_significa_que_no_se_ha_
    ejecutado_nada` verifica que el 4 significa «no se ha ejecutado nada», y
    `correr` corta ese 4 a proposito porque es el codigo que hace pasar en
    verde a un `!= 0`. El test que verifica la regla no puede usar la regla.

    O sea que hay dos preguntas y hacen falta dos puertas:

        ¿ha corrido el test que quiero?     -> `correr`
        ¿qué codigo ha dado pytest?          -> `crudo`

    Y el nombre es lo que hace que la excepcion sea visible: en cualquier
    sitio donde aparezca `crudo`, se lee «esto esta mirando el codigo en
    crudo, y tiene un motivo». La comprobacion repo-wide exige ademas que el
    fichero que lo use hable del exit code en su nombre, que es un criterio
    tonto y estricto, y es preferible a «este fichero se lo permite» — que
    es una excepcion que se extiende sola."""
    cmd = construir(fichero, test, extra)
    r = subprocess.run(cmd, cwd=cwd or os.getcwd(), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, r.stdout.decode('utf-8', 'replace')


def correr(fichero, test=None, env=None, cwd=None, extra=()):
    """El codigo y la salida, con 4 y 5 YA DESCARTADOS.

    Lo unico que se descarta aqui: el resto lo lee el que llama, porque cada
    uno espera una cosa distinta."""
    cmd = construir(fichero, test, extra)
    r = subprocess.run(cmd, cwd=cwd or os.getcwd(), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    salida = r.stdout.decode('utf-8', 'replace')
    codigo = r.returncode
    assert codigo not in (CODIGO_NINGUNO_EJECUTADO,
                          CODIGO_NINGUNO_ENCONTRADO), (
        'pytest ha dado %d (%s), que NO es un fallo de test: es que no se ha '
        'ejecutado nada. Un `assert != 0` sobre esto pasa en verde.\n'
        'Comando: %r\n\nSalida:\n%s'
        % (codigo, QUE_SIGNIFICA.get(codigo, '?'), cmd, salida[-900:]))
    # Y ahora si: se ha ejecutado un test contra ese directorio, y con un
    # codigo de veras. Lo que hubiera escrito ahi ha pasado por un test.
    #
    # Y va DESPUES del corte de 4 y 5, y no antes: desmarcar un directorio
    # cuyo test no llego a ejecutarse es exactamente el error que este
    # bloque lleva veintiocho rondas corrigiendo —un instrumento que dice
    # «probado» sin haber probado— pero con otro nombre.
    _registrar_ejecucion((env or {}).get(DIR_DE_DOCUMENTOS), test)
    return codigo, salida


def afirmar_caida(fichero, test=None, env=None, cwd=None, cuando='',
                 extra=()):
    """Afirma que HA CAIDO: codigo 1, y la salida lo demuestra.

    Las dos mitades por separado, porque son dos pruebas distintas. El 1
    dice que algo fallo; la segunda dice que fallo lo que yo queria. Con
    `test=None` —el fichero entero— la segunda es un RECUENTO de fallos,
    que es lo que esa forma de ejecucion da."""
    codigo, salida = correr(fichero, test, env=env, cwd=cwd,
                            extra=extra)
    if cuando:
        salida = '%s\n\n%s' % (cuando, salida)
    # Y el NOMBRE del objetivo en todos los mensajes, no solo en el ultimo.
    # Un mensaje que no dice de que test habla obliga a abrir el comando a
    # mano, y en un fallo de subprocess eso es un paso de mas en el sitio
    # donde menos pasos hay.
    cual = test or 'el fichero entero %s' % fichero
    assert codigo == 1, (
        'esperaba que CAESE «%s» y ha dado %d (%s). Un 0 significa que la '
        'rotura no ha roto nada; un 2 o un 3, que se ha interrumpido. '
        'Ninguno de los dos es «el test ha fallado».\n\nSalida:\n%s'
        % (cual, codigo, QUE_SIGNIFICA.get(codigo, '?'), salida[-1200:]))
    if test is None:
        # Con el FICHERO ENTERO no hay un nombre mio que exigir: todos tienen
        # que caer. Lo que se puede exigir son dos cosas, y las dos.
        #
        # (1) un RECUENTO de fallos MAYOR QUE CERO. Y mayor que cero, no
        #     «presente»: `re.findall(r'(\d+) failed', '0 failed in 0.05s')`
        #     devuelve `['0']`, o sea que `assert m` se cumplia con un cero.
        #     MEDIDO, no supuesto.
        #
        # (2) al menos una linea `FAILED`. Sin ella, lo que ha caido no es un
        #     test: es una importacion rota o un error de coleccion, que dan
        #     el MISMO codigo de salida. Y un 1 por un `import` roto no es
        #     «el mecanismo ha detectado la rotura»: es que no se ha podido
        #     mirar. Que es este error, una escala mas abajo.
        m = re.findall(r'(\d+) failed', salida)
        assert m and int(m[-1]) >= 1, (
            'esperaba ver fallos de TEST en «%s» y la salida dice %s. El '
            'codigo 1 dice que algo fallo, pero o no hubo fallos, o hubo '
            'errores de coleccion o de importacion —que son otra cosa y dan '
            'el mismo codigo—. Un `assert` sobre la presencia de un numero '
            'acepta un cero, y hay que pedir el numero.\n\nSalida:\n%s'
            % (cual, m or 'nada', salida[-1200:]))
        caidos = re.findall(r'^FAILED \S+::', salida, re.M)
        assert caidos, (
            'hay recuento de fallos pero ninguna linea `FAILED fichero::test`. '
            'O sea que lo que ha caido no son tests: es la coleccion o una '
            'importacion. Y esto no acredita que el mecanismo haya detectado '
            'nada, sino que no se ha podido mirar.\n\nSalida:\n%s'
            % salida[-1200:])
    else:
        # Con un TEST concreto: su nombre, EN UNA LINEA QUE EMPIEZA POR
        # `FAILED`. Con solo `FAILED in salida` bastaba con que la palabra
        # apareciera por cualquier motivo —y el nombre estar en una linea
        # suelta, que puede ser el mensaje de otro fallo—.
        lineas = re.findall(r'^FAILED \S+::' + re.escape(test) + r'\b',
                            salida, re.M)
        assert lineas, (
            'esperaba ver `FAILED ...::%s` y no esta. El codigo 1 dice que '
            'algo fallo, pero no que fuera ESTE test: puede ser una '
            'importacion rota, que da el mismo codigo, o un fallo de otro '
            'sitio.\n'
            '  MEDIDO antes: en VERDE el nombre NO sale en la salida; en ROJO '
            'si, y precedido de `FAILED`. Por eso el nombre se exige con su '
            'linea, y no suelto.\n\nSalida:\n%s'
            % (test, salida[-1200:]))
    return salida


def afirmar_verde(fichero, test=None, env=None, cwd=None, extra=()):
    """Afirma que PASA: codigo 0 y el RECUENTO de los que han pasado.

    Y el recuento, y no el nombre: MEDIDO, un test que pasa con `-q` imprime
    `.` y `1 passed`, y su nombre no aparece. Buscarlo seria falso siempre."""
    codigo, salida = correr(fichero, test, env=env, cwd=cwd,
                            extra=extra)
    cual = test or 'el fichero entero %s' % fichero
    assert codigo == 0, (
        'esperaba que PASASE «%s» y ha dado %d (%s).\n\nSalida:\n%s'
        % (cual, codigo, QUE_SIGNIFICA.get(codigo, '?'), salida[-1200:]))
    assert 'no tests ran' not in salida, (
        'la salida dice «no tests ran», asi que no se ha ejecutado nada:\n%s'
        % salida[-600:])
    m = re.findall(r'(\d+) passed', salida)
    assert m and int(m[-1]) >= 1, (
        'esperaba ver «1 passed» de «%s» y la salida dice: no dice cuantos '
        'han pasado. Si no lo dice, no se sabe si se ha ejecutado el que '
        'queria o ninguno.\n\nSalida:\n%s' % (cual, salida[-900:]))
    return salida