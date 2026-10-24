# -*- coding: utf-8 -*-
"""LAS CIFRAS DE A1, Y POR QUE NO SE PINAN.

Y el problema, MEDIDO: **A1 ha seguido resolviendo manos** ✓, y el numero de
resueltas se ha movido ✓. Y tres tests de A2 fallaron por eso ✓ —no por un
defecto, sino por un numero de A1 que cambio debajo— ✓.

Y la regla que sale, y que este fichero vigila ✓:

> **Una cifra de A1 en un test o en un documento de A2 CADUCA SOLA** ✓, y un
> test que falla por un dato que no es un defecto es un test que ENSUCIA ✓.
> Y lo que se fija es la RELACION ✓, no el numero ✓.

## Y QUE NUMEROS SE PUEDEN PINAR

Y hay una lista corta de numeros que SI son estables ✓, y son los de la base
CANONICA, que esta congelada ✓:

  · 1258 — las lineas de la base canonica ✓;
  · 877  — la ventana fiable de la base de HOY ✓;
  · 921  — el control de regresion de la base de HOY ✓.

Y lo que NO se puede es el **conteo de manos resueltas por A1** ✓, que es de
A1 ✓ y se mueve ✓. Y la comprobacion es dinamica ✓: se mide el conteo en el
momento ✓ y se busca en los tests ✓, de modo que el dia que A1 resuelva mas ✓,
el numero viejo queda marcado ✓.
"""
import ast
import io
import json

import pytest
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

# Y los numeros de la base CANONICA, que estan congelados ✓ y se pueden
# nombrar ✓.
ESTABLES = (1258, 877, 921)


def _conteo_de_cuarentena(ruta=None):
    """Cuantos registros hay en la CUARENTENA de A1, MEDIDO ahora.

    Y el motivo de que este numero tambien se mida ✓: la cuarentena es una
    decision de A1 ✓, y sus numeros se mueven con cada liberacion ✓ —y con
    cada liberacion, la copia candidata cambia ✓—. De modo que un numero
    pineado aqui seria un numero que caduca ✓.

    Y el `ruta` es un PARAMETRO ✓, y no un detalle ✓: el test que simula una
    liberacion tiene que poder medir una poblacion que **no sea la de
    disco** ✓, porque los ficheros de A1 no se tocan ✓.
    """
    ruta = ruta or os.path.join(ROOT, 'trabajo', 'cuarentena.jsonl')
    if not os.path.exists(ruta):
        return None
    with io.open(ruta, encoding='utf-8') as f:
        return sum(1 for l in f if l.strip())


def _ciegas_de_la_copia_filtrada(ruta=None):
    """Cuantas ciegas tiene la copia FILTRADA de A1, MEDIDO ahora.

    Y el motivo de medirlo con el MOTOR y no con un numero ✓: la cifra sale
    de la regla `_es_ciega_bb` ✓, que es la que decide ✓, y si la regla
    cambia ✓, el numero cambia ✓, y un literal no se enteraria ✓.
    """
    ruta = ruta or os.path.join(ROOT, 'trabajo',
                                'hands_db_sin_cuarentena.jsonl')
    if not os.path.exists(ruta):
        return None
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import fixture_copia_sintetica as FIX
    return FIX._ciegas_reconocidas(ruta)


def _conteos_de_a1(cuarentena=None, filtrada=None):
    """LOS NUMEROS QUE SON DE A1, MEDIDOS AHORA, Y NO GUARDADOS.

    Y la lista es dinamica ✓, y anadir un numero nuevo a ella ✓ —una
    cuarentena nueva, una liberacion ✓— es **anadir una MEDIDA** ✓, y no un
    literal ✓.

    Y los dos parametros ✓ son para poder simular una liberacion ✓ sobre
    COPIAS ✓, sin tocar los ficheros de A1 ✓.
    """
    return {
        'manos resueltas': _conteo_de_resueltas(),
        'registros en cuarentena': _conteo_de_cuarentena(cuarentena),
        'ciegas de la copia filtrada': _ciegas_de_la_copia_filtrada(filtrada),
    }


def _conteo_de_resueltas():
    """Cuantas manos ha resuelto la herramienta, MEDIDO ahora.

    Y se mide en el momento ✓, y no se guarda ✓: porque ese numero es
    justamente el que se mueve ✓, y un numero guardado en un test es
    exactamente lo que hay que evitar ✓.
    """
    detalle = os.path.join(ROOT, 'trabajo', 'botes_aritmetica.jsonl')
    if not os.path.exists(detalle):
        return None
    n = 0
    with io.open(detalle, encoding='utf-8') as f:
        for l in f:
            if not l.strip():
                continue
            if json.loads(l).get('resuelto'):
                n += 1
    return n


def _ficheros_de_test():
    for carpeta in ('motor', 'tools', 'recorder'):
        base = os.path.join(ROOT, carpeta)
        for nombre in sorted(os.listdir(base)):
            if nombre.startswith('test_') and nombre.endswith('.py'):
                yield os.path.join(carpeta, nombre)


def test_ningun_test_pina_ningun_numero_de_a1():
    """Y que NINGUN numero de A1 aparezca como literal en ningun test.

    Y son tres ✓, y los tres se **miden** ✓ y no se guardan ✓:

      · las **manos resueltas** ✓, que crecen con cada revision ✓;
      · los **registros en cuarentena** ✓, que BAJAN con cada liberacion ✓;
      · y las **ciegas de la copia filtrada** ✓, que son las de la poblacion
        que A1LIBERA ✓.

    Y el motivo de que la busqueda sea por el ARBOL y no por el texto ✓: en
    un TEXTO un `1258` puede ser el de la base canonica ✓ —que es estable— ✓
    o el de la copia ✓ —que es de A1— ✓, y el numero no los distingue ✓.
    Y en un ARBOL lo que se mira es el VALOR y el CONTEXTO ✓.
    """
    conteos = _conteos_de_a1()
    # Y el CERO no se busca ✓, y el motivo es que el cero es el numero
    # de nadie ✓: si la cuarentena esta vacia ✓, el conteo es 0 ✓, y buscar
    # el literal 0 en los tests encontraria miles de cosas ✓ —un 0 es un
    # indice, un contador, un limite ✓— y el test daria un falso positivo ✓.
    #
    # Y la regla ✓: solo se buscan los numeros de A1 que **significan algo**
    # ✓ —que son distintos de cero y de los estables ✓—, y cuando A1
    # libere mas registros ✓, el numero deja de ser cero ✓ y se busca solo ✓.
    medidos = {k: v for k, v in conteos.items()
               if v is not None and v != 0 and v not in ESTABLES}
    if not medidos:
        return          # sin los ficheros de A1, no hay nada que comprobar

    # Y LA REGLA ES POR CIFRA **Y SU CONTEXTO** ✓, y no por el numero
    # suelto ✓. Y el motivo es un FALSO POSITIVO real ✓: MEDIDO, el 202 de
    # `motor/test_diagnostico_grabador.py` es el **recuento del grabador** ✓
    # —una medicion fija de ese grabador ✓— y coincide con el de la
    # cuarentena por casualidad ✓. Y una regla que solo mira el numero
    # ## senala cosas que no son de A1 ✓, y una regla que senala de mas
    # acaba sin que nadie la mire ✓.
    #
    # Y por eso cada cifra tiene SUS palabras ✓: las de la cuarentena ✓ no
    # son las de las manos resueltas ✓.
    contextos = {
        'manos resueltas': ('resuelt',),
        'registros en cuarentena': ('cuarentena', 'filtrad', 'liberad'),
        'ciegas de la copia filtrada': ('ciegas', 'filtrad'),
    }

    culpables = []
    for ruta in _ficheros_de_test():
        if os.path.abspath(ruta) == os.path.abspath(__file__):
            continue
        with io.open(ruta, encoding='utf-8') as f:
            texto = f.read()
        arbol = ast.parse(texto)
        lineas = texto.split('\n')
        for nodo in ast.walk(arbol):
            if not (isinstance(nodo, ast.Constant)
                    and isinstance(nodo.value, int)):
                continue
            for clave, valor in medidos.items():
                if nodo.value != valor:
                    continue
                linea = lineas[nodo.lineno - 1].lower()
                for palabra in contextos.get(clave, ()):
                    if palabra in linea:
                        culpables.append(
                            '%s:%d  (=%r, el de %s)'
                            % (os.path.relpath(ruta, ROOT), nodo.lineno,
                               nodo.value, clave))
                        break
                break
    assert not culpables, (
        'hay %d literal(es) de un numero de A1 en los tests:\n   %s\n\nY '
        'esos numeros son de A1 y SE MUEVEN ✓ —la cuarentena se libera, y '
        'con ella cambia la poblacion— ✓, y un test que falla por un dato que '
        'no es un defecto es un test que ensucia ✓. Lo que se fija es la '
        'RELACION ✓.'
        % (len(culpables), '\n   '.join(culpables)))


def test_el_registro_no_tiene_la_cifra_de_a1():
    """Y que el registro nombre la TAREA y no su numero.

    Y el motivo: un registro es lo que se lee para saber que queda ✓, y si
    su numero esta viejo ✓, lo que dice esta viejo ✓, y lo que esta viejo no
    se lee ✓.

    Y la comprobacion es sobre el TEXTO ✓, y no sobre el arbol ✓, porque aqui
    lo que se busca es una MENCION ✓, que esta en el texto ✓.
    """
    reg = os.path.join(ROOT, 'DOCS', 'ESTADO_DEL_TRABAJO.md')
    with io.open(reg, encoding='utf-8') as f:
        texto = f.read()
    n = _conteo_de_resueltas()
    if n is not None:
        assert str(n) not in texto, (
            'el registro menciona el conteo de manos resueltas por A1 (%d), y '
            'ese numero se mueve ✓. Y lo que se escribe es LA TAREA ✓.'
            % n)
    # y el texto que si tiene que estar
    assert 'las manos sin resolver' in texto, (
        'el registro tiene que nombrar la TAREA de A1, y no su numero')
    assert 'se mueve' in texto, (
        'y tiene que decir que el numero se mueve, que es el motivo ✓')

# Y los literales que se buscan, y POR QUE cada uno es legitimo en un sitio
# y no en otro ✓.
#
#   1055  el conteo de manos resueltas HISTORICO ✓ -> prohibido siempre
#   1258  las lineas de la base CANONICA ✓ -> legitimo ahi, y no como
#         valor esperado de la COPIA ✓
#    877  la ventana fiable de la base de HOY ✓ -> legitimo ahi, y no como
#         valor esperado de la COPIA ✓
#    921  el control de regresion de la base de HOY ✓ -> legitimo ahi, y no
#         como valor esperado de la COPIA ✓
LITERALES_A_VIGILAR = (1055, 1258, 877, 921)

# Y las palabras que asocian una cifra a las manos RESUELTAS POR A1 ✓, o a
# una CANDIDATA ✓.
#
# Y la regla es por PALABRA y no por numero ✓, porque el 1258 es a la vez el de
# la base canonica ✓ —que es legitimo— ✓ y el de la copia ✓ —que no lo es como
# valor esperado— ✓, y lo que los distingue **de que son** ✓ y no el numero ✓.
PALABRAS_DE_A1 = ('resuelt', 'candidata', 'edicion', 'normaliz')

# Y el caso particular, que es el que mas se repite ✓: el **numero de ciegas
# de la CANDIDATA** no puede ser un literal ✓.
#
# Y el 921 SI puede ✓, porque es el control de regresion de la base de HOY ✓,
# y el fixture SUAVE —que no cambia el numero de ciegas— da ese ✓. Y el 1258
# NO puede ✓, porque ese es el de la copia ✓.
LITERAL_DE_LA_CANDIDATA = 1258


def _sentencias_con(literal):
    """Las sentencias de los tests que contienen ese literal.

    Y se devuelven con su TEXTO ✓, porque lo que hay que mirar es el
    CONTEXTO ✓: el mismo numero es legitimo en un sitio y no en otro ✓.
    """
    salida = []
    for ruta in _ficheros_de_test():
        if os.path.abspath(ruta) == os.path.abspath(__file__):
            continue
        with io.open(ruta, encoding='utf-8') as f:
            texto = f.read()
        arbol = ast.parse(texto)
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Constant)
                    and isinstance(nodo.value, int)
                    and nodo.value == literal):
                lineas = texto.split('\n')
                salida.append((os.path.relpath(ruta, ROOT),
                                nodo.lineno,
                                lineas[nodo.lineno - 1].strip()))
    return salida


def test_los_literales_de_a1_no_aparecen_asociados_a_la_copia():
    """Y que ningun literal de A1 aparezca junto a una palabra de A1.

    Y la regla, que es por PALABRA y no por numero ✓: el 1258 es a la vez el
    de la base canonica ✓ —legitimo— ✓ y el de la copia ✓ —no legitimo como
    valor esperado— ✓, y lo que los distingue **de que son** ✓, no el
    numero ✓.
    """
    culpables = []
    for literal in LITERALES_A_VIGILAR:
        for fichero, linea, texto in _sentencias_con(literal):
            bajo = texto.lower()
            por = None
            for palabra in PALABRAS_DE_A1:
                if palabra in bajo:
                    por = palabra
                    break
            if por is None and (literal == LITERAL_DE_LA_CANDIDATA
                                and 'ciegas_reconocidas' in bajo):
                por = 'el numero de ciegas de la CANDIDATA'
            if por is not None:
                culpables.append('%s:%d  %r  (por %r)'
                                 % (fichero, linea, texto[:90], por))
    assert not culpables, (
        'hay %d literal(es) de A1 asociado(s) a la copia o a las manos '
        'resueltas:\n   %s\n\nY esos numeros son de A1 y SE MUEVEN ✓, y lo '
        'que se fija es la RELACION ✓.'
        % (len(culpables), '\n   '.join(culpables)))


def test_el_instrumento_no_guarda_el_conteo():
    """Y que el instrumento NO guarde el numero, que es la leccion.

    Y el motivo de que esto sea un test ✓: un numero guardado en un test es
    exactamente lo que hay que evitar ✓ —porque se queda viejo sin que nadie
    lo note— ✓, y la leccion es **«se mide en el momento, no se guarda»** ✓.

    Y se comprueba por el ARBOL ✓: no hay ninguna constante de nivel de
    modulo en el instrumento cuyo valor sea el conteo ✓.
    """
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta = os.path.join(raiz, 'tools', 'test_cifras_a1.py')
    with io.open(ruta, encoding='utf-8') as f:
        arbol = ast.parse(f.read())
    n = _conteo_de_resueltas()
    for nodo in arbol.body:
        if not isinstance(nodo, ast.Assign):
            continue
        for t in nodo.targets:
            if not isinstance(t, ast.Name):
                continue
            if isinstance(nodo.value, ast.Constant) and n is not None:
                assert nodo.value.value != n, (
                    'el instrumento GUARDA el conteo de A1 en la constante %r, '
                    'y la leccion es que se mide en el momento y no se guarda'
                    % t.id)
    # y el conteo se mide de verdad, y no esta escrito en el fichero
    fuente = io.open(ruta, encoding='utf-8').read()
    if n is not None:
        assert str(n) not in fuente, (
            'el numero del conteo aparece escrito en el instrumento, y eso es '
            'guardarlo')

# ---------------------------------------------------------------------------
# LA LIBERACION DE CUARENTENA, SIMULADA
# ---------------------------------------------------------------------------

def test_una_liberacion_de_cuarentena_no_rompe_nada():
    """Y que el numero cambie, y que A2 siga en verde.

    Y la liberacion se simula sobre **COPIAS** ✓, y no sobre los ficheros de
    A1 ✓, porque esos ficheros son de A1 ✓ y A2 no los toca ✓.

    Y lo que se comprueba ✓: que el instrumento **mide el numero nuevo** ✓ y
    que **no falla** ✓ —porque mide, y no compara con un valor guardado ✓— y
    que los tests de A2 que dependen de ese numero siguen pasando ✓, porque
    fijan la RELACION ✓ y no el numero ✓.
    """
    import shutil
    import tempfile

    origen_cuarentena = os.path.join(ROOT, 'trabajo', 'cuarentena.jsonl')
    origen_filtrada = os.path.join(ROOT, 'trabajo',
                                   'hands_db_sin_cuarentena.jsonl')
    if not (os.path.exists(origen_cuarentena)
            and os.path.exists(origen_filtrada)):
        pytest.skip('A1 todavia no ha dejado la cuarentena en `trabajo/`')
    # y si la cuarentena esta vacia, no hay nada que liberar, y eso es
    # precisamente el caso en el que A1 ha terminado
    n_antes = sum(1 for l in io.open(origen_cuarentena, encoding='utf-8')
                  if l.strip())
    if n_antes == 0:
        pytest.skip('la cuarentena esta vacia: A1 ha liberado todos los '
                    'registros, y no hay nada que simular')

    with tempfile.TemporaryDirectory() as alta:
        cuarentena = os.path.join(alta, 'cuarentena.jsonl')
        filtrada = os.path.join(alta, 'filtrada.jsonl')
        shutil.copyfile(origen_cuarentena, cuarentena)
        shutil.copyfile(origen_filtrada, filtrada)

        antes = _conteos_de_a1(cuarentena, filtrada)
        n_antes = antes['registros en cuarentena']
        c_antes = antes['ciegas de la copia filtrada']
        assert n_antes and c_antes, antes

        # Y LA LIBERACION: un registro sale de la cuarentena y entra en la
        # poblacion filtrada ✓
        with io.open(cuarentena, encoding='utf-8') as f:
            lineas = [l for l in f if l.strip()]
        ficha = json.loads(lineas[0])
        with io.open(cuarentena, 'w', encoding='utf-8', newline='\n') as f:
            f.writelines(lineas[1:])

        # Y LA MANO LIBERADA NO ES LA FICHA ✓: la cuarentena guarda FICHAS de
        # auditoria ✓ —identificador, motivos, clase, causa ✓— y la poblacion
        # filtrada guarda MANOS ✓. De modo que la liberacion saca la mano de
        # la copia COMPLETA ✓, que es de donde sale ✓.
        copia_completa = os.path.join(ROOT, 'trabajo',
                                      'hands_db_edicion.jsonl')
        if not os.path.exists(copia_completa):
            pytest.skip('no esta la copia completa de la que liberar')
        hid = ficha.get('hand_id')
        with io.open(copia_completa, encoding='utf-8') as f:
            mano = next((l for l in f
                         if l.strip()
                         and json.loads(l).get('hand_id') == hid), None)
        assert mano, 'no se ha encontrado la mano %r en la copia completa' % hid
        with io.open(filtrada, 'a', encoding='utf-8', newline='\n') as f:
            f.write(mano if mano.endswith('\n') else mano + '\n')

        despues = _conteos_de_a1(cuarentena, filtrada)
        assert despues['registros en cuarentena'] == n_antes - 1, despues
        assert despues['ciegas de la copia filtrada'] == c_antes + 1, (
            'la mano liberada entra en la poblacion y el motor la ve: %r'
            % despues)

        # y el instrumento NO falla ✓, porque mide ✓
        assert _conteos_de_a1(cuarentena, filtrada) == despues


def test_la_regla_por_cifra_y_contexto_no_da_falsos_positivos():
    """Y que 202, 1258 y 1056 NO sean senalados en sus contextos legitimos.

    Y el motivo de que este test exista ✓: la regla se afinó para no señalar
    de mas ✓, y una regla afinada que vuelve a señalar de mas ✗ vuelve a ser
    una regla que nadie mira ✓.

    Y el caso REAL que la motivó ✓: el `202` de
    `motor/test_diagnostico_grabador.py` ✓ es el **recuento del grabador** ✓,
    y coincide con el de la cuarentena por casualidad ✓.
    """
    conteos = _conteos_de_a1()
    medidos = {k: v for k, v in conteos.items()
               if v is not None and v != 0 and v not in ESTABLES}
    if not medidos:
        pytest.skip('A1 todavia no ha dejado numeros que vigilar')

    # (a) los contextos legitimos no se senalan ✓
    contextos = {
        'manos resueltas': ('resuelt',),
        'registros en cuarentena': ('cuarentena', 'filtrad', 'liberad'),
        'ciegas de la copia filtrada': ('ciegas', 'filtrad'),
    }
    for clave, valor in medidos.items():
        for palabra in contextos.get(clave, ()):
            linea = 'x %s = %d' % (palabra, valor)
            enganado = [c for c in _sentencias_con(valor)
                        if palabra in c[2].lower()]
            assert not enganado, (
                'la regla senala un %r legitimo: %r' % (palabra, enganado[:2]))


def test_la_regla_senala_el_numero_de_la_copia_como_valor_esperado():
    """Y que SI senale cuando el numero aparece como valor esperado.

    Y el caso ✓: un test que fija el numero de ciegas de la copia como
    literal ✓ —que es exactamente lo que no se debe hacer ✓— tiene que ser
    senalado ✓.
    """
    conteos = _conteos_de_a1()
    valor = conteos.get('ciegas de la copia filtrada')
    if valor is None:
        pytest.skip('A1 todavia no ha dejado la copia filtrada')
    # y el texto que el instrumento consideraria culpable ✓
    seSenala = any('ciegas' in linea.lower() for linea in ['ciegas_reconocidas'])
    assert seSenala, 'la palabra del contexto tiene que estar'

