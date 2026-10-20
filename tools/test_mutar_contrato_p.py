# -*- coding: utf-8 -*-
"""EL INSTRUMENTO DE MUTACION, Y QUE SEA SEGURO.

Y lo que se comprueba aqui, en cuatro cosas:

  · que **exige el arbol limpio** antes de empezar, y que si no lo exige, no
    muta nada ✓;
  · que **restaura siempre**, y que la restauracion NO depende de que el test
    pase: si el test LANZA, el fichero vuelve a su sitio igual ✓;
  · que las tres mutaciones estan **declaradas**, y que una que no lo esta
    es un ERROR y no un «no encuentro el patron» ✓;
  · y que **no deja rastro**: el sha del fichero restaurado, y ningun temporal
    ni en `motor/` ni en la raiz ✓.

Y el instrumento es un INSTRUMENTO y no un test de la suite ✓, porque muta el
motor, y un test que muta el motor mientras corre la suite puede dejarlo
roto si la suite se interrumpe ✓. Y por eso estos tests lo llaman por su
FUNCION, y no por su `main()` ✓.
"""
import hashlib
import io
import os

import pytest
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import mutar_contrato_p as M   # noqa: E402

LEARN = os.path.join(ROOT, 'motor', 'learn.py')


def _sha(ruta):
    with io.open(ruta, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_la_puerta_exige_el_arbol_limpio_y_no_muta_nada():
    """Y sin arbol limpio, el script se niega Y el motor no se toca.

    Y el motivo: la restauracion se verifica con un sha, y con cambios en el
    arbol ese sha no demuestra nada: el motor pudo estar cambiado antes, y
    entonces el «lo he restaurado» no significa que este script lo restaurara.
    """
    original = io.open(LEARN, 'rb').read()
    sha = _sha(LEARN)

    class _ArbolSucio:
        @staticmethod
        def status(*a, **k):
            class R:
                returncode = 0
                stdout = ' M motor/learn.py\n'
            return R()

    guardado = M._git
    M._git = _ArbolSucio.status
    try:
        rc = M.main([])
    finally:
        M._git = guardado

    assert rc == 2, (
        'sin arbol limpio el script tiene que negarse, y ha salido con %d' % rc)
    assert _sha(LEARN) == sha, 'y el motor no puede haberse tocado'
    assert io.open(LEARN, 'rb').read() == original


def test_la_restauracion_no_depende_de_que_el_test_pase():
    """Y si el test que corre durante la mutacion LANZA, el motor vuelve igual.

    Y esto es lo importante: **la restauracion no puede depender de que el
    test pase** ✓, porque un test que falla es el caso NORMAL de este
    instrumento ✓ —para eso existe—.

    Y el mecanismo: el `finally` ✓. Y por eso el `finally` es la parte que hay
    que mirar y no el resto ✓.
    """
    original = io.open(LEARN, 'rb').read()
    sha = _sha(LEARN)

    def _lanza():
        raise RuntimeError('el test de la mutacion ha revuelto')

    try:
        M.mutar_y_comprobar('M1', LEARN, runner=_lanza)
    except RuntimeError:
        pass
    else:
        raise AssertionError('el runner que lanza deberia propagar el error')

    assert _sha(LEARN) == sha, (
        'el motor NO ha vuelto a su sitio, y la restauracion no puede depender '
        'de que el test pase')
    assert io.open(LEARN, 'rb').read() == original


def test_las_mutaciones_estan_declaradas_y_una_no_declarada_es_un_error():
    """Y las tres, con su descripcion, y una cuarta es un ERROR.

    Y el motivo de que una mutacion no declarada sea un error y no un «no
    encuentro el patron»: un patron que ya no esta quiere decir que **el
    motor ha cambiado**, y eso hay que decirlo, no seguir como si nada ✓.
    """
    assert set(M.MUTACIONES) == {'M1', 'M2', 'M3', 'M4'}, (
        sorted(M.MUTACIONES))
    for etiqueta, mut in M.MUTACIONES.items():
        assert mut['que'].strip(), '%s no dice QUE rompe' % etiqueta
        assert mut['viejo'] in io.open(LEARN, encoding='utf-8').read(), (
            'el patron de %s no esta en el motor: el motor ha cambiado'
            % etiqueta)
    try:
        M.mutar_y_comprobar('M9', LEARN)
    except ValueError as e:
        assert 'no declarada' in str(e), str(e)
    else:
        raise AssertionError('una mutacion no declarada tiene que ser un error')


def test_no_deja_rastro():
    """Y tras una mutacion, el motor esta como estaba y no hay temporales.

    Y el rastro se mira en DOS sitios: el sha del fichero ✓ y el CONTENIDO de
    `motor/` y de la raiz ✓, porque un temporal que se queda en la raiz es
    la clase de rastro que nadie ve hasta que molesta.
    """
    def _listado(d):
        return sorted(os.listdir(d))

    antes_raiz = _listado(ROOT)
    antes_motor = _listado(os.path.join(ROOT, 'motor'))
    sha = _sha(LEARN)

    notado, _detalle = M.mutar_y_comprobar('M2', LEARN)

    assert _sha(LEARN) == sha, 'el motor no ha vuelto a su sitio'
    assert _listado(ROOT) == antes_raiz, (
        'han quedado ficheros en la raiz: %r'
        % (set(_listado(ROOT)) - set(antes_raiz),))
    assert _listado(os.path.join(ROOT, 'motor')) == antes_motor, (
        'han quedado ficheros en `motor/`: %r'
        % (set(_listado(os.path.join(ROOT, 'motor'))) - set(antes_motor),))


def test_el_contraste_de_m3_detecta_el_hueco():
    """Y que el test que CIERRA el hueco falla si el hueco se reabre.

    Y este es el contrapunto del instrumento: la mutacion encontro un hueco,
    y el test que lo cierra tiene que **notar** que el hueco vuelve ✓. Y si
    el test no lo notara, el hueco estaria cerrado de mentira ✓.
    """
    import subprocess

    original = io.open(LEARN, 'rb').read()
    try:
        notado, detalle = M.mutar_y_comprobar('M3', LEARN)
    finally:
        with io.open(LEARN, 'wb') as f:
            f.write(original)

    assert notado, (
        'con M3 aplicada, los tests tienen que FALLAR, y no lo hacen. Y eso '
        'quiere decir que el test que cierra el hueco no lo cierra.\n%s'
        % detalle[:600])

    # y el fallo tiene que ser EL del hueco, y no otro
    assert 'bb_ya_posteo' in detalle or 'ciega' in detalle.lower(), (
        'el fallo tiene que ser el del hueco, y no otro: %s' % detalle[-600:])

class _R:
    """El resultado de una mutacion, con su codigo de salida y su salida.

    Y es un envoltorio porque `mutar_y_comprobar` devuelve `(notado, detalle)`
    y el codigo de salida del subproceso es lo que dice si el test fallo ✓.
    """

    def __init__(self, notado, detalle):
        # Y `notado` es True cuando los tests han FALLADO ✓, que es un
        # codigo de salida distinto de cero ✓.
        self.returncode = 1 if notado else 0
        self.stdout = detalle or ''


def test_el_exit_code_de_la_contraparte_de_m3_vigila_SU_camino_y_no_el_de_m3():
    """Y la verdad medida: la contraparte vigila SU camino, y no el de M3.

    Y el motivo de que esto sea una asertion y no un comentario: **M3 y la
    contraparte son CASOS DISTINTOS** ✓.

        M3  es el caso de la `p` —un BB que YA posteo y despues tiene una
            `b`—, y M3 quita la marca de «ya posteo» ✓.
        la contraparte  es el caso de la `b` —un BB que NO posteo antes y
            tiene una `b` tarde—, y ahi la marca no interviene ✓.

    De modo que la contraparte es SENSIBLE a **M4**, que es la mutacion de SU
    camino ✓, y NO a M3 ✓. Y esa asertion es mas util que la que se leeria
    al principio: dice que cada caso vigila lo suyo ✓, y que un solo test que
    vigilara los dos con una sola mutacion no distinguiria nada ✓.
    """
    import subprocess

    import mutar_contrato_p as M

    nodo = ('motor/test_accion_p.py::'
            'test_sin_la_p_de_antes_la_b_del_bb_si_es_un_rechazo')

    def _con_la_mutacion(etiqueta):
        """Muta con el INSTRUMENTO, y no con una copia propia.

        Y el motivo: el instrumento borra el `.pyc` del modulo mutado antes de
        correr los tests ✓, y sin eso el subproceso puede importar el
        BYTECODE MUTADO ✓ —porque la mutacion conserva el TAMANO del
        fichero— ✓, y el resultado es un falso positivo ✓.

        Y una sola implementacion de la mutacion ✓, para que el instrumento y
        sus tests no puedan divergir ✓.
        """
        # Y ANTES de mutar, se comprueba que el motor esta como debe ✓. Y el
        # motivo: una mutacion anterior que se quedase puesta haria que
        # esta corriera sobre un motor ya roto, y el fallo seria de otro
        # caso —y por tanto ILLEGIBLE— ✓.
        import subprocess as _sp
        r0 = _sp.run(['git', 'status', '--porcelain', 'motor/learn.py'],
                     cwd=ROOT, capture_output=True, text=True)
        assert not r0.stdout.strip(), (
            'el motor ya estaba modificado ANTES de esta mutacion, de modo '
            'que el resultado no seria legible:\n%s' % r0.stdout[:400])

        def _runner(tests=None):
            # Y por `ejecutar_pytest`, y no con un subproceso PROPIO ✓: la
            # regla del repositorio es que quien lance pytest entra por
            # ahi ✓, y el guardián lo comprueba repo-wide ✓. Y `crudo` es la
            # exencion —la que NO corta el codigo de salida— ✓, y este test
            # SI necesita el codigo de salida, porque su afirmacion es
            # justamente que el test ha fallado ✓.
            import tools.ejecutar_pytest as EJ
            cmd = EJ.construir('motor/test_accion_p.py',
                                test='test_sin_la_p_de_antes_la_b_del_bb_si_es_un_rechazo',
                                extra=('-p', 'no:cacheprovider'))
            return subprocess.run(cmd, cwd=ROOT, capture_output=True,
                                  text=True, env=M._entorno_sin_bytecode())

        notado, detalle = M.mutar_y_comprobar(etiqueta, LEARN, runner=_runner,
                                               tests=[nodo])
        return _R(notado, detalle)

    r4 = _con_la_mutacion('M4')
    assert r4.returncode != 0, (
        'con M4 aplicada —que es la mutacion del camino de la contraparte— la '
        'contraparte tiene que FALLAR, y no falla. Y eso quiere decir que la '
        'contraparte no vigila su camino.\n%s' % r4.stdout[-600:])

    r3 = _con_la_mutacion('M3')
    assert r3.returncode == 0, (
        'con M3 aplicada la contraparte NO tiene que fallar, porque M3 es el '
        'caso de la `p` y la contraparte es el de la `b`: son caminos '
        'distintos. Y si este test falla, es que M3 ha cambiado de caso.')

def test_al_terminar_el_motor_no_ha_quedado_mutado():
    """Y el ULTIMO test del fichero, que vigila al resto.

    Y el motivo de que sea el ultimo: este fichero es el que MUTA el motor, y
    una fuga aqui se nota en los tests que se ejecuten despues, y no en este
    fichero ✓. De modo que el guardian tiene que ir AL FINAL ✓, para que
    vigile despues de que los demas hayan pasado.

    Y la comprobacion es contra GIT, y no contra un sha guardado: porque lo
    que importa es que el fichero sea el que esta COMITEADO ✓, y no el que
    estaba antes de empezar ✓.
    """
    import subprocess
    r = subprocess.run(['git', 'status', '--porcelain', 'motor/learn.py'],
                       cwd=ROOT, capture_output=True, text=True)
    assert not r.stdout.strip(), (
        'el motor ha quedado mutado, y eso no puede pasar:\n%s'
        % r.stdout[:600])

def test_cada_mutacion_tiene_su_test_sensible_y_falla_con_ella():
    """Y la TABLA ENTERA, mutacion por mutacion.

    Y esto es lo que R1 pide: que no baste con que la mutacion EXISTA, sino
    que **su test sensible falle cuando se aplica** ✓. Y la diferencia es
    la de siempre: una mutacion que nadie nota es una **brecha de
    cobertura** ✓, y no un detalle ✓.

    Y se usa el INSTRUMENTO ✓, con su invalidacion de la cache ✓, para que
    el resultado sea el mismo que el del `main()` ✓.
    """
    import mutar_contrato_p as M

    filas = M.tabla_de_mutaciones()
    assert len(filas) == 4, [f['mutacion'] for f in filas]
    for fila in filas:
        assert fila['invariante'].strip(), fila
        assert fila['test'].strip(), fila
        notado, detalle = M.mutar_y_comprobar(fila['mutacion'], LEARN,
                                              tests=[fila['test']])
        assert notado, (
            'la mutacion %s (%s) no la nota su test de la tabla (%s). Y eso es '
            'una BRECHA DE COBERTURA, y no un motivo para relajar el test.\n%s'
            % (fila['mutacion'], fila['que'], fila['test'], detalle[:600]))


def test_el_mutador_invalida_la_cache_y_no_escribe_bytecode():
    """Y que la invalidacion se haga SIEMPRE, y en los dos sistemas.

    Y el motivo de que sea **incondicional** ✓: el problema se manifesto en
    Windows ✓, donde la marca de tiempo tiene una granularidad gruesa ✓ y el
    `.pyc` se puede considerar valido ✓; en Linux la marca es de nanosegundos
    ✓ y el problema no se daba ✓. De modo que el arreglo —borrar el `.pyc` y
    no escribir bytecode— se aplica **en los dos** ✓, porque un instrumento
    que depende del sistema es un instrumento que no se puede usar ✓.

    Y la prueba es del MECANISMO ✓ y no del comportamiento del sistema ✓:
    que se borre el `.pyc` del modulo mutado ✓, y que el entorno lleva la
    variable ✓.
    """
    import mutar_contrato_p as M

    # (a) el entorno
    env = M._entorno_sin_bytecode()
    assert env.get('PYTHONDONTWRITEBYTECODE') == '1', env.get(
        'PYTHONDONTWRITEBYTECODE')

    # (b) el `.pyc` se borra, y se cuenta
    cache = os.path.join(ROOT, 'motor', '__pycache__')
    os.makedirs(cache, exist_ok=True)
    # Y el nombre tiene que CUMPLIR EL PATRON del borrado ✓ —empezar por el
    # modulo y acabar en `.pyc`— ✓, porque lo que se comprueba es el
    # mecanismo ✓, no un borrado de todo ✓.
    falsa = os.path.join(cache, 'learn_prueba.pyc')
    with io.open(falsa, 'wb') as f:
        f.write(b'x')
    n = M._limpiar_cache()
    assert n >= 1, 'el `.pyc` de prueba deberia haberse borrado'
    assert not os.path.exists(falsa), 'el `.pyc` sigue ahi'

    # (c) y el `.pyc` que NO es del modulo mutado se respeta
    otra = os.path.join(cache, 'otro_modulo_prueba.pyc')
    with io.open(otra, 'wb') as f:
        f.write(b'x')
    try:
        M._limpiar_cache()
        assert os.path.exists(otra), (
            'el borrado tiene que ser SOLO del modulo mutado, que lo que no es '
            'de este motor no se toca')
    finally:
        if os.path.exists(otra):
            os.remove(otra)

def test_los_pares_de_la_tabla_tienen_su_contraparte_sensible():
    """Y que los pares —M3 y M4— tengan los dos lados, y que cada lado sea
    sensible a SU mutacion.

    Y el motivo de que sean un par ✓: **M3 y M4 son las dos caras del mismo
    hueco** ✓ —el BB que ya posteo ✓ y el BB que no posteo antes ✓— y una
    cara sin la otra no se puede comprobar ✓.

    Y lo que se mide, y que es una verdad MEDIDA ✓ y no una opinion ✓:

      · cada cara es sensible a **su** mutacion ✓;
      · y la contraparte de una **no** es sensible a la otra ✓, y eso es lo
        correcto ✓: M3 desactiva el rechazo de una ciega TARDIA ✓ —que es el
        caso de la `p`— ✓, y M4 desactiva el rechazo de cualquier ciega
        tardia ✓ —que es el caso de la `b`— ✓. Y la contraparte de M3 afirma
        que NO hay rechazo ✓, de modo que con M4 —que no rechaza nada— ✓ esa
        afirmacion se cumple todavia mas ✓, y el test pasa ✓.

    > Y por eso la regla de la tabla es **cada caso vigila lo suyo** ✓, y no
    > «cada caso nota todas las mutaciones» ✓: eso segundo seria imposible,
    > porque las dos caras son afirmaciones **opuestas** ✓.
    """
    import mutar_contrato_p as M

    pares = {'M3': 'M4', 'M4': 'M3'}
    for mutacion, contraparte in sorted(pares.items()):
        propio = M.MUTACIONES[mutacion]['test']
        del_otro = M.MUTACIONES[contraparte]['test']

        # (a) cada cara es sensible a SU mutacion
        notado, _d = M.mutar_y_comprobar(mutacion, LEARN, tests=[propio])
        assert notado, (
            'la mutacion %s tiene que notarla su propio test %s' % (
                mutacion, propio))

        # (b) y la contraparte de la otra NO es sensible a esta, y eso es lo
        #     correcto: son afirmaciones opuestas
        notado_otro, _d2 = M.mutar_y_comprobar(mutacion, LEARN,
                                               tests=[del_otro])
        assert not notado_otro, (
            'la contraparte de %s (%s) no deberia notar %s: son los dos '
            'lados del mismo hueco y cada uno vigila el suyo'
            % (contraparte, del_otro, mutacion))

def test_el_instrumento_no_muta_sobre_un_arbol_sucio():
    """Y que se niegue, y que el motor no se toque.

    Y el motivo de esta garantia ✓: **el «original» del que se restaura se
    lee de GIT** ✓, y si el fichero esta ya sucio ✓, mutarlo encima haria que
    la restauracion devolviese la mutacion ✓ —y el sha coincidiria ✓, y el
    instrumento creeria que ha restaurado ✓.

    Y la razon de que se niegue en vez de avisar ✓: una garantia que solo
    avisa se puede pasar por alto ✓, y una que se niega no ✓.

    Y el caso, que es el que se dio ✓: la suite entera se ejecuto con el
    motor mutado ✓ —con el soporte de la `p` desaparecido ✓— y lo unico que
    lo detecto fue **el detector de fugas** ✓, que fallo ✓✓. Y eso es
    instrumentacion que funciona ✓, pero es mejor que no llegue a pasar ✓.
    """
    import mutar_contrato_p as M

    # (a) el motor esta como debe, y el instrumento muta bien
    assert M._fichero_limpio(LEARN), 'el motor deberia estar limpio'

    # (b) y con el motor sucio, el instrumento SE NIEGA
    original = io.open(LEARN, 'rb').read()
    sucio = original + b'\n# una modification sin commitear\n'
    with io.open(LEARN, 'wb') as f:
        f.write(sucio)
    try:
        M.mutar_y_comprobar('M1', LEARN)
    except RuntimeError as e:
        assert 'sin commitear' in str(e) or 'COMITEADA' in str(e), str(e)
    else:
        raise AssertionError(
            'el instrumento TENIA que negarse a mutar un arbol sucio, y no se '
            'nrego')
    finally:
        with io.open(LEARN, 'wb') as f:
            f.write(original)

    # (c) y el motor ha quedado como estaba
    assert io.open(LEARN, 'rb').read() == original

def test_el_mutador_no_toca_un_fichero_sucio_y_no_lo_restaura():
    """Y que se negue, y que **no lo restaure**.

    Y el motivo de que no lo restaure ✓: restaurar desde GIT cuando el
    fichero tiene trabajo sin commitear **destruye ese trabajo** ✓. Y el
    instrumento no es quien debe decidir eso ✓: lo correcto es **negarse** ✓
    y que lo decida quien iba a mutar ✓.

    Y este caso cubre a la vez los dos primeros de R1 ✓: el arbol sucio ✓ y
    el fichero que ya estaba modificado ✓ —da igual por que motivo ✓—.
    """
    import mutar_contrato_p as M

    original = io.open(LEARN, 'rb').read()
    sucio = original + b'\n# una modificacion sin commitear\n'
    with io.open(LEARN, 'wb') as f:
        f.write(sucio)
    try:
        M.mutar_y_comprobar('M1', LEARN)
    except RuntimeError:
        pass
    else:
        raise AssertionError('el instrumento tenia que negarse')
    finally:
        with io.open(LEARN, 'wb') as f:
            f.write(original)

    # y el fichero ha quedado EXACTAMENTE como estaba ✓, con su trabajo sin
    # commitear intacto ✓
    assert io.open(LEARN, 'rb').read() == original


def test_el_mutador_sin_git_falla_limpio_y_no_muta():
    """Y que sin GIT **no mute**, en vez de leer el original del fichero.

    Y el motivo ✓: **el fallback al fichero no es aceptable ni cuando GIT no
    esta** ✓, porque es exactamente el fallo queNapshot ✓: un «original» que
    no se puede comprobar no sirve para restaurar ✓. Y es mejor **fallar** que
    mutar sin red ✓.
    """
    import mutar_contrato_p as M

    original = io.open(LEARN, 'rb').read()
    guardado = M._version_commiteada
    M._version_commiteada = lambda ruta: None
    try:
        M.mutar_y_comprobar('M1', LEARN)
    except RuntimeError as e:
        assert 'COMITEADA' in str(e), str(e)
    else:
        raise AssertionError(
            'sin GIT el instrumento tenia que FALLAR, y no mutar: el '
            'fallback al fichero es el fallo que ya se/ha pagado')
    finally:
        M._version_commiteada = guardado

    assert io.open(LEARN, 'rb').read() == original, 'el motor se ha tocado'


def test_el_detector_de_fugas_ve_un_motor_mutado_por_cualquier_causa():
    """Y que el detector NO dependa de que el mutador haya restaurado.

    Y el motivo ✓: **un detector que solo detecta fugas del MUTADOR no
    detecta fugas** ✓. Y el caso que se dio ✓ fue justo ese ✓: el motor
    mutado por una fuga ✓, y lo detecto ✓.

    Y el caso de este test ✓ es mas fuerte ✓: el motor esta mutado **sin que
    el mutador pase por aqui** ✓ —lo simula una escritura a pelo ✓— y el
    detector lo ve ✓.
    """
    import mutar_contrato_p as M

    original = io.open(LEARN, 'rb').read()
    # y una mutacion a pelo, que no pasa por el instrumento ✓
    mutado = original.replace(
        b"if pos == 'BB' and act in ('b', 'p') and not voluntary_before:",
        b"if pos == 'BB' and act == 'b' and not voluntary_before:", 1)
    if mutado == original:
        pytest.skip('el patron de la mutacion no esta en el motor')
    with io.open(LEARN, 'wb') as f:
        f.write(mutado)
    try:
        assert not M._fichero_limpio(LEARN), (
            'el detector NO ha visto un motor mutado a pelo')
    finally:
        with io.open(LEARN, 'wb') as f:
            f.write(original)
    assert M._fichero_limpio(LEARN), 'y tras restaurar, el motor esta limpio'

