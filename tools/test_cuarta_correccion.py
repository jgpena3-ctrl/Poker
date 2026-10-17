# -*- coding: utf-8 -*-
"""La cuarta correccion, comprobada sobre los documentos.

QUE COMPRUEBA

  T1  los tres documentos dicen que el 78 era 0
  T2  la separacion en dos problemas esta RETIRADA, y solo aparece citada
  T3  las cifras correctas (0 preflop, 48 postflop con 20 y 28) estan
      escritas, y no solo insinuadas
  T4  las cifras y frases retiradas no se AFIRMAN en ninguno

Y T4 no lo hace este fichero: lo hace `retraccion_scan`, que es el sitio
UNICO donde vive la regla. Antes la regla estaba copiada aqui y en
`test_retraccion_y_auc.py`, y las dos copias divergieron: una encontraba
«78» dentro de «378» y la otra se comia las citas.

Una copia de una regla dentro de un test no es un problema de estilo. Es
que cuando la regla cambia, cambia en un sitio, y el otro sigue con la
regla vieja diciendo que el documento esta bien. O que esta mal. Lo que
nunca pasa es que las dos sean ciertas a la vez.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from retraccion_scan import (                         # noqa: E402
    LOS_TRES, RETIRADAS, afirmada, afirmada_sin_negar, citada,
    leer, niega, frases_retiradas)

CUATRO = ('DECISION_OBJETIVO_AUC.md', 'LIMITACION_PREFLOP_AUC.md',
          'REPRESENTATIVIDAD_23.md', 'FASE_D_BLOQUEADA.md')


# ============================================ T1: el 78 era 0
def test_los_tres_dicen_que_el_78_era_cero():
    """Y no basta con mencionar 78: hay que decir que se retira, o el
    documento parece que siempre lo dijo."""
    for n in ('DECISION_OBJETIVO_AUC.md', 'LIMITACION_PREFLOP_AUC.md',
              'REPRESENTATIVIDAD_23.md'):
        texto = leer(n)
        assert '78' in texto, '%s no menciona el numero viejo' % n
        baja = texto.lower()
        dice = ('se retira' in baja or 'retirada' in baja
                or 'cuarta correcci' in baja or 'rehecha' in baja
                or 'retirado' in baja)
        assert dice, '%s menciona el 78 pero no dice que se retira' % n


def test_los_tres_dicen_que_la_preflop_esta_vacia():
    """No «de una sola clase». De una clase es un problema de clase; vacia
    es un problema de etiqueta, y se arregla distinto."""
    for n in ('DECISION_OBJETIVO_AUC.md', 'LIMITACION_PREFLOP_AUC.md',
              'REPRESENTATIVIDAD_23.md'):
        baja = leer(n).lower()
        assert 'vacía' in baja or 'vacia' in baja, (
            '%s no dice que la preflop este VACIA' % n)
        # y la frase de una sola clase, si aparece, tiene que ser negada
        for i, linea in enumerate(leer(n).split('\n'), 1):
            if 'una sola clase' in linea.lower() and not (
                    linea.lstrip().startswith('>') or niega(linea)):
                raise AssertionError(
                    '%s:%d afirma "una sola clase": %s'
                    % (n, i, linea.strip()[:70]))


def test_los_tres_dicen_el_motivo_real():
    """«La mano no llega a tener board». Es el motivo, y no un filtro."""
    for n in ('DECISION_OBJETIVO_AUC.md', 'LIMITACION_PREFLOP_AUC.md',
              'REPRESENTATIVIDAD_23.md'):
        texto = leer(n)
        hitos = (afirmada(texto, 'termina en el preflop')
                 + afirmada(texto, 'termina ahí')
                 + afirmada(texto, 'no tiene board'))
        assert hitos, (
            '%s no dice el MOTIVO: que el corte preflop solo cae en una mano '
            'que TERMINA en el preflop, y esa no tiene board, y sin board no '
            'hay ganador verificable' % n)


# ============================================ T2: la separacion, retirada
def test_la_separacion_en_dos_problemas_no_se_afirma():
    """"Arreglar el 1 no arregla el 2" era la separacion. Retirada: es UN
    problema, y cabe en una frase."""
    for n in CUATRO:
        texto = leer(n)
        for frase, _ctx in RETIRADAS:
            if 'arreglar el 1' not in frase and 'sesgo' not in frase:
                continue
            assert not afirmada_sin_negar(texto, frase), (
                '%s sigue AFIRMANDO la separacion en dos problemas (%r)'
                % (n, frase))


def test_los_tres_dicen_que_es_un_problema_no_dos():
    for n in ('DECISION_OBJETIVO_AUC.md', 'LIMITACION_PREFLOP_AUC.md',
              'REPRESENTATIVIDAD_23.md'):
        texto = leer(n)
        hitos = (afirmada(texto, 'Es **un** problema')
                 + afirmada(texto, 'es un problema')
                 + afirmada(texto, 'solo puede caer en una mano'))
        assert hitos, (
            '%s no dice que es UN problema, con su enunciado' % n)


# ============================================ T3: las cifras correctas
def test_las_cifras_correctas_estan_escritas():
    """0 preflop, y 48 postflop con 20 positivas y 28 negativas.

    Con `afirmada()` y no con `in texto`, porque un numero puede estar en el
    documento dentro de la tabla de la retraccion —que es una cita— y eso
    no cuenta como estar dicho.
    """
    for n in ('DECISION_OBJETIVO_AUC.md', 'LIMITACION_PREFLOP_AUC.md',
              'REPRESENTATIVIDAD_23.md'):
        texto = leer(n)
        assert afirmada(texto, '48'), '%s no dice 48 afirmandolo' % n
        assert afirmada(texto, '20') and afirmada(texto, '28'), (
            '%s no dice 20 y 28, que es la reparticion del postflop' % n)


# ============================================ T4: la regla vive en un sitio
def test_ningun_documento_afirma_una_frase_retirada():
    """T4 entero, sobre los cuatro documentos, con la regla de
    `retraccion_scan`."""
    for n in CUATRO:
        malas, _citadas = frases_retiradas(n)
        assert not malas, (
            '%s afirma %d cosa(s) retiradas:\n   %s'
            % (n, len(malas),
               '\n   '.join('%4d [%s] %s' % m for m in malas)))


def test_la_regla_no_vive_en_ningun_test():
    """Y que no vuelva a copiarse. La lista de frases retiradas tiene un
    solo sitio: si aparece en dos, divergen, y ya ha pasado."""
    import re
    for d in ('tools', 'motor'):
        ruta = os.path.join(ROOT, d)
        if not os.path.isdir(ruta):
            continue
        for n in sorted(os.listdir(ruta)):
            if not (n.startswith('test_') and n.endswith('.py')):
                continue
            if n == os.path.basename(__file__):
                continue
            with io.open(os.path.join(ruta, n), encoding='utf-8') as f:
                texto = f.read()
            assert 'RETIRADAS = (' not in texto, (
                'tools/%s declara RETIRADAS: la lista de frases retiradas '
                'tiene un solo sitio, que es retraccion_scan.py' % n)
            assert 'def niega(' not in texto, (
                'tools/%s define niega(): la regla de negacion tiene un solo '
                'sitio, que es retraccion_scan.py' % n)


# ============================================ y el escaner, probado
def test_el_escaner_ve_una_frase_afirmada_y_no_una_citada():
    """Un escaner que no ve nada no vigila.

    Y el experimento tiene que estar bien hecho, porque un laboratorio mal
    construido hace fallar al detector que esta bien:

    la afirmacion y su cita van en parrafos SEPARADOS. Una retraccion se
    escribe en su parrafo, y si se mezclan, el detector acierta al excusarla
    —el parrafo anuncia una retraccion— y parece que falla. El primer
    intento del laboratorio hacia justo eso.
    """
    texto = ('una linea normal\n'
             '| con etiqueta | 270 | que es la cifra retirada\n'
             '\n'
             '> ahora dice 270, y antes decia 270\n'
             '\n'
             'otra linea\n')
    assert afirmada(texto, '270') == [2], (
        'senalo %r: solo la linea 2 afirma; la 4 cita'
        % afirmada(texto, '270'))
    assert citada(texto, '270') is True
    assert afirmada_sin_negar(texto, '270') == [2]


def test_el_parrafo_es_el_alcance_de_la_retraccion():
    """Y que el alcance sea el PARRAFO, y no la linea ni el documento.

    Tres casos con la misma cifra y distinto contexto, y los tres tienen que
    salir distinto:

      - parrafo propio con «se retira»  -> NO cuenta como afirmacion
      - parrafo contiguo sin marcador   -> SI cuenta como afirmacion
      - documento entero con marcador   -> haria que el segundo no contase,
                                         y por eso el alcance no es el
                                         documento
    """
    texto = ('| con etiqueta | 270 | afirmada aqui\n'
             '\n'
             'se retira lo anterior: 270 era la cifra de la replica\n'
             '\n'
             'otra tabla\n'
             '| con etiqueta | 270 | y esta otra es distinta\n')
    assert afirmada_sin_negar(texto, '270') == [6], (
        'solo la de la linea 6 cuenta: la del 3 esta en un parrafo que se '
        'retira, y el de la linea 1 esta en otro que no. Salen %r'
        % afirmada_sin_negar(texto, '270'))


def test_el_escaner_entiende_la_negacion():
    """"No «de una sola clase»: ninguna" CONTIENE la frase y la NIEGA. Un
    escaner que no lo entiende senala la correccion, y eso hace que la
    gente deje de mirar."""
    texto = ('No «de una\n'
             'una sola clase»: ninguna.\n'
             '| hay datos de una sola clase | ✗ | tampoco |\n')
    assert afirmada(texto, 'una sola clase'), 'la ve: la frase esta'
    assert not afirmada_sin_negar(texto, 'una sola clase'), (
        'pero no como afirmacion, porque las dos apariciones la niegan')


def test_una_frase_que_es_una_negacion_no_se_filtra():
    """«no suficiente» y «no implementada» son afirmaciones EN NEGATIVO, y
    el filtro de polaridad las descartaba por llevar «no» —que es justo lo
    que las hace ser las frases que se buscan—.

    Un detector que exige «no está implementada» en un documento y no lo
    encuentra parece un fallo del documento cuando el documento esta bien.
    """
    texto = ('va medida y **no implementada**, y eso necesita un contrato.\n'
             '| | |\n'
             '|---|---:|\n'
             '| preflop | 0 |\n')
    assert afirmada(texto, 'no implementada') == [1]
    assert afirmada_sin_negar(texto, 'no implementada') == [1], (
        'y sin_negar tambien, porque la frase ya lleva su polaridad')
    assert afirmada(texto, 'no suficiente') == []
    assert afirmada_sin_negar(texto, 'no suficiente') == []


def test_el_escaner_distingue_los_numeros_por_token():
    """`78` NO es `378`. Y `378` es un numero legitimo: es el total de
    cortes con accion jugada bajo el corte en la primera.

    El escaner anterior no lo distinguia, y senalaba una linea correcta.
    """
    texto = '| cortes preflop de población B | 83 | 378 |\n'
    assert afirmada(texto, '78') == [], (
        'ha encontrado 78 dentro de 378: %r' % afirmada(texto, '78'))
    assert afirmada(texto, '378') == [1], 'pero 378 si es 378'


def test_el_escaner_aguanta_el_partido_de_linea():
    """`no\nimplementada` es `no implementada`. Un escaner que no lo sabe
    senala la frase que hace bien su trabajo.

    Y devuelve la linea donde EMPIEZA la coincidencia, que es la 2 y no la 3:
    si la frase esta partida, la linea que hay que mirar es la del principio,
    que es donde esta el modificador.
    """
    texto = 'una cosa\nva medida y no\nimplementada. Otra vez.\n'
    assert afirmada(texto, 'no implementada') == [2]
    assert afirmada(texto, 'implementada') == [3]
    assert not afirmada(texto, 'no esta implementada')


def test_retraccion_scan_es_lo_unico_que_declara_retiradas():
    """Y la comprobacion final, sobre el propio modulo."""
    fuente = io.open(os.path.join(ROOT, 'tools', 'retraccion_scan.py'),
                     encoding='utf-8').read()
    i = fuente.index('RETIRADAS = (')
    assert fuente.count('RETIRADAS = (') == 1, 'una sola definicion'
    assert 'arreglar el 1' in fuente[i:], 'y contiene la separacion retirada'
    assert len(RETIRADAS) >= 13, 'y la lista ha crecido, no se ha recortado'