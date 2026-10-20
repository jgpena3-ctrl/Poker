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

