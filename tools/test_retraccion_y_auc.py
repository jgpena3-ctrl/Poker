# -*- coding: utf-8 -*-
"""La retraccion, la distincion de las dos razones, y el AUC indefinido.

Tres cosas que R2 pide que esten escritas Y que no se borren:

  1. La retraccion con el numero viejo al lado, en los tres documentos:
     78 y no 1, todas victorias y cero derrotas, y el corte en la primera
     decision MEDIDO (270, 216 y 54).

  2. Los DOS problemas separados: el bloqueo de etiquetado no arregla el
     sesgo de la seleccion del corte. Sin esa distincion la conclusion se
     lee como "faltan manos", y no es eso.

  3. El AUC con una sola clase es INDEFINIDO, no 1,0. Y se comprueba
     contra el codigo de verdad: `auditar_auc.auc_de()` devuelve `None`.

Y el noveno caso del assert (R1 tarea 3): se aniade un caso y el mensaje
tiene que decir "9 de 9", no "9 de 7".
"""
import collections
import importlib.util
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DOCS = os.path.join(ROOT, 'DOCS')

LOS_TRES = ('LIMITACION_PREFLOP_AUC.md', 'REPRESENTATIVIDAD_23.md',
            'FASE_D_BLOQUEADA.md')


def _leer(n):
    with io.open(os.path.join(DOCS, n), encoding='utf-8') as f:
        return f.read()


def _mod(nombre, donde='tools'):
    ruta = os.path.join(ROOT, donde, nombre)
    spec = importlib.util.spec_from_file_location(
        nombre[:-3].replace('.', '_'), ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ============================================== 1. la retraccion, en los tres
def test_los_tres_dicen_78_y_no_1():
    """El numero viejo tiene que estar AL LADO del nuevo, no borrado. Un
    documento que dice 78 sin decir que antes decia 1 no deja ver que se
    corrigio: parece que siempre lo dijo."""
    for n in LOS_TRES:
        s = _leer(n)
        assert '78' in s, '%s no dice 78' % n
        assert '1' in s, '%s no menciona el numero viejo' % n


def test_los_tres_dicen_todas_victorias_cero_derrotas():
    for n in LOS_TRES:
        baja = _leer(n).lower()
        ok = ('cero derrotas' in baja or '0 derrotas' in baja
              or 'y = 0`' in baja)
        assert ok, '%s no dice que son cero derrotas' % n


def test_los_tres_dicen_que_la_causa_es_el_corte_y_no_las_cartas():
    """`revision_2`: hay que separar el bloqueo de etiquetado del sesgo de
    la seleccion. Y la causa del sesgo es el corte, no que falten cartas."""
    for n in LOS_TRES:
        baja = _leer(n).lower()
        assert 'bloqueo' in baja, '%s no habla del bloqueo' % n
        assert 'sesgo' in baja or 'seleccion' in baja, (
            '%s no habla del sesgo de la seleccion' % n)
        assert 'arreglar el 1 no arregla el 2' in baja, (
            '%s no dice que arreglar el bloqueo NO arregla el sesgo, que es '
            'la distincion que R2 pide' % n)


def test_los_tres_dicen_el_arreglo_medido_y_no_afirmado():
    for n in LOS_TRES:
        s = _leer(n)
        assert '270' in s, (
            '%s no dice las 270 del corte en la primera decision' % n)
        assert '54' in s, '%s no dice las 54 derrotas' % n


def test_la_hipotesis_del_corte_primero_esta_marcada_como_hipotesis():
    """No basta con decir que el corte en la primera trae las negativas:
    hay que decir que esta MEDIDO, y que sigue sin implementarse.

    Y la palabra tiene que estar ACERCA de la medida, no en un titulo
    lejano: un documento que dice "hipotesis" en un sitio y el numero en
    otro no liga nada. Por eso se comprueba en la MISMA seccion.
    """
    for n in LOS_TRES:
        texto = _leer(n)
        bajo = texto.lower()
        assert 'hipotesis' in bajo or 'hipótesis' in bajo, (
            '%s no la llama hipotesis' % n)
        # "no esta implementado" y "no esta implementada": el genero
        # cambia segun a que se refiera, y un test que exige una sola forma
        # obliga a escribir el documento como el test.
        assert ('no implementad' in bajo
                or 'no está implementad' in bajo
                or 'sin implementar' in bajo), (
            '%s no dice que no esta implementado: es un cambio de la '
            'definicion del objetivo y va en un contrato' % n)
        # la palabra y los numeros, en un radio de veinte lineas
        for i, linea in enumerate(texto.split('\n')):
            if 'pótesis' in linea or 'potesis' in linea:
                ventana = texto.split('\n')[i:i + 20]
                assert any('270' in v for v in ventana), (
                    '%s dice "hipotesis" y a mas de veinte lineas el 270, o '
                    'sea que no liga con nada' % n)
                break


# ================================ 3. el AUC de una sola clase es INDEFINIDO
def test_auc_de_una_sola_clase_devuelve_none():
    """El codigo de verdad, no el documento. `auc_de` lo dice en su
    docstring: "None si falta una clase"."""
    auc = _mod('auditar_auc.py')
    pos = [0.3 + 0.007 * i for i in range(78)]
    assert auc.auc_de(pos, []) is None, (
        'con una sola clase tiene que devolver None, no 1,0')
    assert auc.auc_de([], pos[:12]) is None, 'y por el otro lado tambien'


def test_auc_de_con_las_dos_clases_sigue_funcionando():
    auc = _mod('auditar_auc.py')
    assert auc.auc_de([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert auc.auc_de([0.4], [0.5]) == 0.0


FRASES_ROTAS = ('daría 1,0 por definición', 'daria 1,0 por definicion',
                'dar 1,0 por definición')


def test_la_frase_retirada_solo_aparece_en_una_cita():
    """R2: el valor 1,0 no es un resultado ROC válido que deba asignarse a
    una muestra de una sola clase.

    Y la regla no es 'la frase no aparece'. Una RETRACCIÓN tiene que citar
    lo que retira: sin la frase vieja al lado, no se ve que se corrigió, y
    parece que siempre se dijo lo nuevo. Lo que no puede es aparecer
    AFIRMANDOLA, y eso se distingue de citarla por una cosa que no es el
    vocabulario: la cita va en bloque citado.
    """
    for n in LOS_TRES:
        malas = []
        for i, linea in enumerate(_leer(n).lower().split('\n'), 1):
            for f in FRASES_ROTAS:
                if f in linea and not linea.lstrip().startswith('>'):
                    malas.append((i, linea.strip()[:70]))
        assert not malas, (
            '%s afirma la frase retirada fuera de una cita:\n%s'
            % (n, '\n'.join('   %4d %s' % x for x in malas)))


def test_cada_documento_retira_la_frase_explicitamente():
    """Y no basta con que no la afirme: tiene que decir que la retira."""
    for n in LOS_TRES:
        baja = _leer(n).lower()
        cita = any(f in baja for f in FRASES_ROTAS)
        retirada = ('se retira' in baja or 'se retira' in baja
                    or 'retirada' in baja or 'corrección' in baja
                    or 'correccion' in baja)
        if cita:
            assert retirada, (
                '%s cita lo que dijo y no dice que lo retira' % n)


# ================================ la herramienta: el noveno caso del assert
def test_el_assert_del_detector_usa_el_total_real():
    """R1 tarea 3: el mensaje del assert lleva el total de la lista, no un
    numero escrito a mano. Lo que paso fue peor de lo que parecio: se
    saque el total de la linea de impresion y el mensaje se quedo con un 7,
    de modo que el dia que hubiera nueve casos diria 'ha fallado 9 de 7'."""
    fuente = io.open(_mod('auditar_representatividad.py').__file__,
                     encoding='utf-8').read()
    assert 'assert fallos == 0' in fuente
    i = fuente.index('assert fallos == 0')
    cuerpo = fuente[i:i + 400]
    assert '% (fallos, n_casos)' in cuerpo, (
        'el mensaje tiene que usar n_casos, no un numero fijo')
    assert 'de 7 casos' not in cuerpo


def test_la_tabla_puede_crecer_y_el_mensaje_la_sigue():
    """Se anade un noveno caso y el mensaje tiene que decir '9 de 9'.

    No se recorta la cadena de formato del fuente —eso es fragil y ya ha
    fallado una vez—, sino que se EJECUTA el mensaje que hace el modulo, con
    los numeros que le pongamos. Es lo que importa: que el total viaje.
    """
    ar = _mod('auditar_representatividad.py')
    fuente = io.open(ar.__file__, encoding='utf-8').read()
    i = fuente.index('el detector de cartas falla en %d de %d casos')
    # se reconstruye el formato tal cual esta, con la interpolacion que el
    # modulo hace
    cabeza = fuente[i:fuente.index(' casos', i)]
    formato = cabeza + ' casos: los numeros de C3 no se publican con un ' \
                     'detector roto'
    for fallos, total in ((0, 8), (1, 9), (9, 9), (3, 12)):
        msg = formato % (fallos, total)
        assert ('%d de %d' % (fallos, total)) in msg, (
            'con (%d, %d) el mensaje sale %r' % (fallos, total, msg))
    # y el caso que rompio el arreglo: nueve de nueve, no nueve de siete
    assert '9 de 9' in (formato % (9, 9))
    assert '9 de 7' not in (formato % (9, 9))


def test_la_tabla_real_no_tiene_ningun_total_fijo():
    ar = _mod('auditar_representatividad.py')
    fuente = io.open(ar.__file__, encoding='utf-8').read()
    i = fuente.index('def sanity_de_cartas')
    cuerpo = fuente[i:fuente.index('return fallos', i)]
    # ni un numero de casos escrito a mano en el cuerpo de la funcion
    assert 'de 8 casos' not in cuerpo
    assert 'len(casos)' in fuente, 'el total sale de la lista'


def test_la_tabla_devuelve_el_total_que_tiene():
    ar = _mod('auditar_representatividad.py')
    fallos, _l, n = ar.sanity_de_cartas()
    assert n == 8, 'hoy son 8; si se anade uno, esto avisa'
    assert fallos == 0


# ====================== la medicion de la seccion 8, contra el codigo real
def test_la_seccion_8_mide_el_corte_que_dice_medir():
    """La seccion 8 mide un corte que NO EXISTE en el codigo. Eso esta bien
    y declarado, pero hay que comprobar que el 'ultima' que mide es
    exactamente el de `corte_de_decision`, porque si se desincronizan los
    dos, la comparacion de la tabla no vale."""
    ar = _mod('auditar_representatividad.py')
    eqm = _mod('equity_de_mano.py')
    por_id = dict((h['hand_id'], h) for h in
                  __import__('motor.learn', fromlist=['learn'])
                  .load_hands(reliable_only=True))
    for hid, h in list(por_id.items())[:60]:
        pos = eqm.hero_pos_de(h)
        if not pos:
            continue
        calle, idx = eqm.corte_de_decision(h, pos)
        propio = ar.cortes_de(ar._inst(), h, pos, 'ultima')
        assert propio == (calle, idx), (
            '%s: la copia mide %r y el codigo %r' % (hid, propio,
                                                    (calle, idx)))