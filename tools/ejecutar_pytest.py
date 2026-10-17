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

CODIGO_NINGUNO_EJECUTADO = 4      # INTERRUPTED: no se ha ejecutado nada
CODIGO_NINGUNO_ENCONTRADO = 5     # NO_TESTS_COLLECTED: no existe ese test

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
    return codigo, salida


def afirmar_caida(fichero, test=None, env=None, cwd=None, cuando=''):
    """Afirma que HA CAIDO: codigo 1, y la salida lo demuestra.

    Las dos mitades por separado, porque son dos pruebas distintas. El 1
    dice que algo fallo; la segunda dice que fallo lo que yo queria. Con
    `test=None` —el fichero entero— la segunda es un RECUENTO de fallos,
    que es lo que esa forma de ejecucion da."""
    codigo, salida = correr(fichero, test, env=env, cwd=cwd)
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
        m = re.findall(r'(\d+) failed', salida)
        assert m, (
            'el codigo 1 dice que algo fallo, pero la salida no da ningun '
            'recuento de fallos. O sea que el fallo no es de un test: es de la '
            'coleccion o de una importacion.\n\nSalida:\n%s' % salida[-1200:])
    else:
        assert '::%s' % test in salida and 'FAILED' in salida, (
            'el codigo 1 dice que algo fallo, pero la salida no nombra %s con '
            'FAILED. O sea que el fallo es de otro sitio —una importacion '
            'rota, una coleccion que no encuentra nada— y no de la '
            'comprobacion que este test cree que esta acreditando.\n'
            '  Nota: en VERDE el nombre no sale; en ROJO si, y con `FAILED`. '
            'Por eso son dos comprobaciones distintas.\n\nSalida:\n%s'
            % (test, salida[-1200:]))
    return salida


def afirmar_verde(fichero, test=None, env=None, cwd=None):
    """Afirma que PASA: codigo 0 y el RECUENTO de los que han pasado.

    Y el recuento, y no el nombre: MEDIDO, un test que pasa con `-q` imprime
    `.` y `1 passed`, y su nombre no aparece. Buscarlo seria falso siempre."""
    codigo, salida = correr(fichero, test, env=env, cwd=cwd)
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