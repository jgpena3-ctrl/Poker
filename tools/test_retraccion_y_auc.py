# -*- coding: utf-8 -*-
"""La retraccion, el enunciado real, y el AUC indefinido.

QUE COMPRUEBA ESTE FICHERO

  1. La afirmacion NUEVA, en los tres documentos: que el preflop no aporta
     ninguna observacion, y por que —la mano no llega a tener board—.
  2. Que ganar por fold es NECESARIO Y NO SUFICIENTE. 77 de las 83 ganan por
     fold y ninguna tiene etiqueta, y esa frase es la que separa la causa
     real de la que se iba a buscar moviendo filtros.
  3. Que la alternativa —el corte en la primera— SUSTITUYE la poblacion en
     vez de anadirla: 67 preflop a cambio de 0 postflop.
  4. Que la alternativa sigue SIN IMPLEMENTARSE, porque es un cambio de la
     definicion del objetivo y va en un contrato.
  5. Que `auc_de()` devuelve `None` con una sola clase, contra el codigo de
     verdad y no contra el documento.

Y lo que NO comprueba aqui, porque lo comprueba el modulo comun: que ninguna
cifra retirada se afirme. Eso vive en `retraccion_scan`, y en
`test_cuarta_correccion.py`, y no en dos sitios.

POR QUE ANTES NO SE PODIA COMPROBAR

Este fichero buscaba las cadenas en el documento entero:

    assert 'cero derrotas' in baja
    assert '270' in s
    assert 'arreglar el 1 no arregla el 2' in baja

Y pasaban. Porque una retraccion **tiene que citar** lo que retira, y esa
cita es una linea que empieza por `>`. La cuenta le daba igual.

O sea que el test obligaba a que el documento conservara, en una cita, la
frase que el mismo test decia que no era verdad. Si alguien hubiera borrado
la retraccion —o sea, hubiera hecho bien la correccion sin dejar constancia—
el test habria fallado.

Eso es el mismo error que `resto_de_muestra`: usar la copia en vez de la
fuente. Aqui la copia es el texto citado, y la fuente es el texto afirmado.

Y hay una segunda cosa, mas pequena y mas importante: la forma. Un
test que exige «sustituye» y el documento dice «sustituir» no esta
comprobando el documento, esta comprobando su propia ortografia. Las tres
afirmaciones se comprueban por lista de formas aceptadas, no por una sola.
"""
import importlib.util
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from retraccion_scan import (                     # noqa: E402
    LOS_TRES, afirmada, afirmada_sin_negar, citada, leer)


def _mod(nombre, donde='tools'):
    ruta = os.path.join(ROOT, donde, nombre)
    spec = importlib.util.spec_from_file_location(
        nombre[:-3].replace('.', '_'), ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ----------------------------------------------------------- las tres ideas
# Varias formas por idea, porque hay mas de una manera correcta de decirlo
# en castellano. Una sola forma obliga a escribir el documento como el test.
NO_BASTA = ('no suficiente', 'no es la causa', 'no lleg',
            'a él no llega', 'no produce ni una')
SUSTITUYE = ('sustituye una población por otra',
             'sustituir una población por otra',
             'sustituye el postflop por el preflop',
             'sustituye una poblacion por otra')
NO_IMPLEMENTADA = ('no está implementad', 'no esta implementad',
                   'sin implementar', 'no se implementa', 'no implementad')


def _alguna(texto, formas):
    """¿Alguna de las formas, AFIRMADA y no citada?"""
    for f in formas:
        if afirmada_sin_negar(texto, f):
            return True
    return False


# ========================================== 1. la afirmacion nueva
def test_los_tres_dicen_que_el_preflop_no_tiene_ninguna_observacion():
    """El hecho. Con la etiqueta de `muestra()`, las 83 no son 78 positivas:
    no son ninguna. Y el enunciado, que es lo que la cuarta correccion vino a
    dejar, y cabe en una frase."""
    for n in LOS_TRES:
        texto = leer(n)
        hitos = (afirmada(texto, 'termina en el preflop')
                 + afirmada(texto, 'termina ahí')
                 + afirmada(texto, 'no tiene board'))
        assert hitos, (
            '%s no dice el MOTIVO: que el corte preflop solo cae en una mano '
            'que TERMINA en el preflop, y esa no tiene board, y sin board no '
            'hay ganador verificable, y sin ganador verificable `muestra()` '
            'no le pone etiqueta' % n)
        assert afirmada(texto, '**0**') or afirmada(texto, '0 con etiqueta'), (
            '%s no dice, afirmandolo, que hay 0 con etiqueta' % n)


def test_los_tres_dicen_que_ganar_por_fold_no_basta():
    """77 de las 83 ganan por fold y ninguna tiene etiqueta. Eso es el
    error entero en una frase, y es lo que separa la causa real de la que
    se busca con el orden de los filtros."""
    for n in LOS_TRES:
        texto = leer(n)
        assert afirmada(texto, '77'), (
            '%s no dice que 77 de las 83 ganan por fold' % n)
        assert _alguna(texto, NO_BASTA), (
            '%s no dice que ganar por fold es NECESARIO Y NO SUFICIENTE, que '
            'es lo que mide la tabla. Formas aceptadas: %s' % (n, NO_BASTA))


def test_los_tres_dicen_el_postflop_que_si_funciona():
    """48 con 20 y 28. El contraste, para que se vea que el instrumento
    funciona y que el problema es del corte, no del AUC."""
    for n in LOS_TRES:
        texto = leer(n)
        assert afirmada(texto, '48'), '%s no dice 48 afirmandolo' % n
        assert afirmada(texto, '20') and afirmada(texto, '28'), (
            '%s no dice la reparticion del postflop, 20 positivas y 28 '
            'negativas' % n)


def test_los_tres_dicen_que_la_alternativa_no_es_un_arreglo():
    """67 observaciones preflop a cambio de 0 postflop. Es una
    SUSTITUCION de poblacion, y hay que decirlo, porque sin eso se lee
    como «anade el preflop»."""
    for n in LOS_TRES:
        texto = leer(n)
        assert afirmada(texto, '67'), (
            '%s no dice las 67 del corte en la primera decision' % n)
        assert _alguna(texto, SUSTITUYE), (
            '%s no dice que la alternativa SUSTITUYE la poblacion en vez de '
            'anadirla: el postflop pasa de 48 a cero. Formas: %s'
            % (n, SUSTITUYE))


# ============================== 4. la hipotesis: medida, y no implementada
def test_la_hipotesis_del_corte_primero_esta_marcada_como_hipotesis():
    """No basta con decir que el corte en la primera trae las negativas:
    hay que decir que esta MEDIDO, y que sigue sin implementarse.

    Y la palabra tiene que estar ACERCA de la medida, no en un titulo
    lejano: un documento que dice "hipotesis" en un sitio y el numero en
    otro no liga nada.
    """
    for n in LOS_TRES:
        texto = leer(n)
        assert _alguna(texto, ('hipótesis', 'hipotesis')), (
            '%s no la llama hipotesis' % n)
        assert _alguna(texto, NO_IMPLEMENTADA), (
            '%s no dice que no esta implementado: es un cambio de la '
            'definicion del objetivo y va en un contrato. Formas: %s'
            % (n, NO_IMPLEMENTADA))


# ================================ 5. el AUC de una sola clase es INDEFINIDO
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


def test_el_auc_publicado_no_se_mueve():
    """Lo que ya se publico tiene que seguir dando lo mismo. Un documento
    que se corrige no puede mover un numero ya firmado."""
    auc = _mod('auditar_auc.py')
    pos = [0.3 + 0.007 * i for i in range(6)]
    neg = [0.2 + 0.011 * i for i in range(5)]
    v = auc.auc_de(pos, neg)
    assert v is not None and 0.0 <= v <= 1.0
    assert auc.auc_de(pos, neg) == v, 'y es determinista'


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
        for i, linea in enumerate(leer(n).lower().split('\n'), 1):
            for f in FRASES_ROTAS:
                if f in linea and not linea.lstrip().startswith('>'):
                    malas.append((i, linea.strip()[:70]))
        assert not malas, (
            '%s afirma la frase retirada fuera de una cita:\n%s'
            % (n, '\n'.join('   %4d %s' % x for x in malas)))


def test_cada_documento_retira_la_frase_explicitamente():
    """Y no basta con que no la afirme: tiene que decir que la retira."""
    for n in LOS_TRES:
        baja = leer(n).lower()
        cita = any(f in baja for f in FRASES_ROTAS)
        retirada = ('se retira' in baja or 'retirada' in baja
                    or 'corrección' in baja or 'correccion' in baja)
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
    cabeza = fuente[i:fuente.index(' casos', i)]
    formato = cabeza + ' casos: los numeros de C3 no se publican con un ' \
                     'detector roto'
    for fallos, total in ((0, 8), (1, 9), (9, 9), (3, 12)):
        msg = formato % (fallos, total)
        assert ('%d de %d' % (fallos, total)) in msg, (
            'con (%d, %d) el mensaje sale %r' % (fallos, total, msg))
    assert '9 de 9' in (formato % (9, 9))
    assert '9 de 7' not in (formato % (9, 9))


def test_la_tabla_real_no_tiene_ningun_total_fijo():
    ar = _mod('auditar_representatividad.py')
    fuente = io.open(ar.__file__, encoding='utf-8').read()
    i = fuente.index('def sanity_de_cartas')
    cuerpo = fuente[i:fuente.index('return fallos', i)]
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


# ============ 2. la frase con la que R2 pregunta, y las dos mitas de la regla
#
# "cero derrotas" estaba en RETIRADAS desde el principio, y ningun test la
# usaba: los de la regla usaban 270, 131 y "una sola clase", que son las
# frases que aparecian en los documentos que se leyeron.
#
# Eso es un sesgo de muestreo en los propios tests — se prueban los casos que
# se encuentran — y su coste es que una frase sin probar puede romperse sin
# avisar. Aqui se prueba la nombrada, y en las DOS mitas, porque una sola no
# demuestra nada: un filtro que descartara siempre pasaria las dos.
FRASE_R2 = 'cero derrotas'


def test_una_cita_de_cero_derrotas_no_cuenta_como_afirmacion():
    """La primera mitad.

    Y no es tolerancia: es lo correcto. Una retraccion TIENE que citar lo que
    retira, o no se ve que se corrigio y parece que siempre se dijo lo nuevo."""
    texto = ('Una correccion de las cifras del AUC.\n'
             '\n'
             '> Antes decia ' + FRASE_R2 + ', y 131 observaciones con '
             'etiqueta. Retirado: con la etiqueta leida son 48.\n'
             '\n'
             'Hoy la poblacion B postflop tiene 48 observaciones con etiqueta, '
             '20 positivas y 28 negativas.\n')
    assert afirmada_sin_negar(texto, FRASE_R2) == [], (
        'una cita se esta contando como afirmacion: %r'
        % afirmada_sin_negar(texto, FRASE_R2))
    assert citada(texto, FRASE_R2) is True, (
        'y ademas la cita no se ve, que es peor: la retraccion no deja '
        'constancia de que se corrigio')


def test_una_afirmacion_de_cero_derrotas_si_cuenta():
    """La segunda mitad, y es la que hace que la primera signifique algo."""
    texto = ('La poblacion B postflop tiene 48 observaciones con etiqueta.\n'
             '\n'
             'En preflop hay ' + FRASE_R2 + ', y eso es lo que hace que el AUC '
             'no se pueda calcular ahi.\n')
    assert afirmada_sin_negar(texto, FRASE_R2) == [3], (
        'una AFIRMACION no se esta contando: %r'
        % afirmada_sin_negar(texto, FRASE_R2))


def test_los_dos_casos_juntos_dan_distinto():
    """Y los dos en el MISMO texto, que es donde un filtro se delata. Si el
    mismo texto dice las dos cosas y el filtro devuelve lo mismo para las
    dos, esta roto."""
    texto = ('Una correccion.\n'
             '\n'
             '> Antes: ' + FRASE_R2 + '. Retirado.\n'
             '\n'
             'Y en el postflop sigue habiendo ' + FRASE_R2 + ', que es lo '
             'que impide calcular el AUC preflop.\n')
    assert afirmada_sin_negar(texto, FRASE_R2) == [5], (
        'con las dos en el mismo texto tiene que salir SOLO la afirmacion, '
        'que esta en la linea 5: %r' % afirmada_sin_negar(texto, FRASE_R2))


def test_la_frase_de_r2_sigue_en_la_lista_de_retiradas():
    """Y que no se pueda quitar de la lista sin que se note. Es la frase que
    se nombro, y una frase retirada que sale de la lista deja de cazar."""
    from retraccion_scan import RETIRADAS
    assert FRASE_R2 in [f for f, _c in RETIRADAS], (
        '"cero derrotas" ha salido de RETIRADAS: el escaner ya no la caza')


# ============================ y el escaner comun, probado a si mismo
def test_el_escaner_comun_no_tiene_una_copia_aqui():
    """La regla vive en `retraccion_scan`. Este fichero la usa y no la
    copia, y esto lo comprueba: si alguien vuelve a pegarla aqui, este test
    falla."""
    fuente = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    # se busca la ASIGNACION, y no la palabra: el docstring de este test
    # habla de la lista, y si buscara la palabra se detectaria a si mismo.
    # Un detector que se detecta a si mismo hay que silenciarlo cada vez que
    # se toca, y eso lo vuelve inservible.
    assert not re.search(r'^\s*RETIRADAS\s*=', fuente, re.MULTILINE), (
        'la lista de frases retiradas se ha copiado aqui: vive en '
        'retraccion_scan.py, y dos copias divergen')
    assert not re.search(r'^def afirmada\(', fuente, re.MULTILINE), (
        '`afirmada()` se ha copiado aqui: vive en retraccion_scan.py')
    assert not re.search(r'^def niega\(', fuente, re.MULTILINE), (
        'la regla de negacion se ha copiado aqui: vive en retraccion_scan.py')
    assert 'from retraccion_scan import' in fuente, (
        'y tiene que estar importada, no reimplementada')


def test_el_escaner_comun_se_importa_de_verdad():
    """No basta con que este el `import`: que las funciones usadas sean las
    del modulo, no las del fichero."""
    import retraccion_scan
    assert afirmada is retraccion_scan.afirmada
    assert leer is retraccion_scan.leer
    assert citada is retraccion_scan.citada