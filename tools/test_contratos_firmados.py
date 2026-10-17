# -*- coding: utf-8 -*-
"""Los dos contratos firmados siguen diciendo lo que el proyecto les pide.

POR QUE EXISTE

R2 lo senala como la laguna concreta de este bloque, y es la de mas
consecuencia: seis ficheros mencionan los contratos y **ninguno comprueba su
contenido**. El unico que se acerca comprueba que el encabezado `## Poblacion`
esté, y un encabezado sobrevive a que reescriban el apartado entero.

Y la laguna ha pasado de hipotetica a load-bearing: este mismo bloque afirma
que «la validez del filtro viene del contrato de inclusion». O sea que la
prueba que separa la causa de la validez se apoya en un contrato que nadie
vigila.

LO QUE HAY: HUELLA Y AFIRMACIONES

  - una **huella** del fichero, para que cualquier cambio se vea. Una huella
    avisa, pero no dice DE QUE, asi que sola obligaria a leer el diff entero.

  - y las **afirmaciones** de las que el proyecto depende, que son pocas y
    comprobables. Es lo que convierte un aviso en un diagnostico.

El fallo dice CUAL afirmacion falta. Un fallo de integridad que no dice que
falta obliga a ir a buscarlo, y entonces no se mira.
"""
import hashlib
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'DOCS')

# Las afirmaciones de las que el proyecto depende, por contrato.
#
# Cada una con su porque, porque un fallo que dice "falta X" obliga a mirar
# por que importa X, y esa es la mitad del trabajo de arreglarlo.
AFIRMACIONES = {
    'CONTRATO_L_SEC.md': (
        # la poblacion: de donde sale la VALIDEZ del filtro de particion
        ('la poblacion son solo las manos que el heroe continua',
         ('héro continúa', 'hero continúa', 'Solo manos donde el héroe',
          'Solo manos donde el hero'), 'La poblacion del AUC. De aqui sale '
         'la validez del filtro, y §4.3 del documento de la prediccion '
         'dice que la validez sale del contrato. Si esto deja de estar '
         'escrito, ese argumento se queda sin base.'),
        ('la particion es por identificador, no por contenido',
         ('sha256', 'hand_id'), 'La particion es sha256(hand_id) % 10 < 3. '
         'Que sea por identificador y no por contenido es lo que hace que '
         'no haya fuga entre entrenamiento y prueba.'),
        ('declara DEFAULT_ALPHA',
         ('DEFAULT_ALPHA',), 'Y que se declara, para que "no se calibra" '
         'sea una decision y no un olvido.'),
    ),
    'CONTRATO_PREFLOP.md': (
        ('la equity preflop va por enumeracion, y es retrospectiva',
         ('enumeraci', 'enumeración'), 'Es lo que hace que la via preflop '
         'este marcada observable: False. Si el contrato dejara de decirlo, '
         'alguien podria leerla como la equity de una decision.'),
        ('su varianza se declara admisible',
         ('varianza', 'variance'), 'Y que la varianza del muestreo se '
         'declare. Es lo que hace que el camino preflop sea implementable '
         'sin abrir una discusion nueva.'),
        ('declara DEFAULT_ALPHA',
         ('DEFAULT_ALPHA',), 'Igual que en el otro.'),
    ),
}


def _leer(nombre):
    """A traves de `retraccion_scan.leer()`, y no de `DOCS` directo.

    Y no por elegancia: porque si se lee del directorio fijo, este fichero
    no se puede ejecutar contra una copia rota del contrato. Y eso es
    justamente lo que hay que comprobar — que los tests CAIGAN cuando el
    contrato cambia — asi que leer del sitio fijo hacia imposible la
    comprobacion.

    El fallo sale asi: el test que rompe el contrato dice «los tests de los
    contratos NO han caido», y la conclusion apparent es que no vigilan.
    Lo que pasaba es que seguian leyendo el contrato bueno.
    """
    from retraccion_scan import leer
    return leer(nombre)


def test_los_contratos_dicen_lo_que_el_proyecto_les_pide():
    """Y el fallo dice cual falta, y por que importa."""
    faltan = []
    for nombre, afirmaciones in AFIRMACIONES.items():
        texto = _leer(nombre).lower()
        for etiqueta, formas, porque in afirmaciones:
            if not any(f.lower() in texto for f in formas):
                faltan.append('%s: %s\n      por que: %s'
                              % (nombre, etiqueta, porque))
    assert not faltan, (
        'los contratos firmados ya no dicen lo que el proyecto les pide:\n   '
        + '\n   '.join(faltan))


def test_los_contratos_no_cambian_sin_que_se_sepa():
    """La huella. Y NO es lo unico: la de arriba comprueba el contenido, y
    esta comprueba que no se haya movido nada.

    Las dos juntas dicen cosas distintas:

      - el contenido  -> si el contrato sigue VALIENDO
      - la huella     -> si el contrato sigue IGUAL

    Y la segunda es la que hace ruido pronto. Un cambio legitimo va a
    cambiar la huella, y ese cambio tiene que ser explicito: o se
    actualiza el valor aqui, o se discute. Un contrato firmado que cambia
    en silencio no esta firmado.
    """
    HUELLAS = {
        'CONTRATO_L_SEC.md': (
            '52815666f8ac396ef35c5b55039f7a3c',
            'el objetivo, la poblacion, la etiqueta y las exclusiones',
        ),
        'CONTRATO_PREFLOP.md': (
            '39b0acf37f41f24d5f903ef8ba09e8d5',
            'el camino de equity preflop y su varianza',
        ),
    }
    cambios = []
    for nombre, (esperada, que) in sorted(HUELLAS.items()):
        import retraccion_scan as _rs
        h = hashlib.sha256(
            _leer(nombre).encode('utf-8')).hexdigest()
        if h[:32] != esperada:
            cambios.append(
                '%s (%s)\n      era %s\n      ahora %s'
                % (nombre, que, esperada, h[:32]))
    assert not cambios, (
        'los contratos firmados han cambiado:\n   ' + '\n   '.join(cambios))


def test_no_basta_con_que_exista_el_encabezado():
    """La trampa, escrita como test.

    Un test que comprueba que el encabezado `## Poblacion` existe pasaria
    aunque alguien reescribiera el apartado entero. El encabezado sobrevive
    a casi todo, que es justo lo que lo hace inutil.

    Este test falla si el apartado desaparece, y el de arriba falla si el
    CONTENIDO deja de decir lo que tiene que decir. Son cosas distintas, y
    hace falta la segunda.
    """
    texto = _leer('CONTRATO_L_SEC.md')
    assert '## Poblaci' in texto, 'el apartado de poblacion ha desaparecido'
    # y el contenido, que es lo que de verdad importa
    baja = texto.lower()
    assert 'héro continúa' in baja or 'hero continúa' in baja, (
        'el apartado sigue ahi y ya no dice que la poblacion es solo donde '
        'el heroe continua. El encabezado por si solo no protege nada')


def test_la_huella_no_sustituye_al_contenido_y_el_contenido_no_a_la_huella():
    """Que las dos comprobaciones sean independientes de verdad.

    Una version de este fichero solo tenia la huella. Y con solo la huella, un
    cambio que no altera lo que el contrato DICE pasaria por todo. Y con solo
    el contenido, un cambio de redaccion irrelevante haria fallar el test, y
    a la tercera vez nadie lo mira.
    """
    fuente = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    assert 'hashlib.sha256' in fuente, 'la huella'
    assert 'AFIRMACIONES' in fuente, 'el contenido'
    # y que las dos esten en tests DISTINTOS, que es lo que las hace
    # independientes: en el mismo test, la que falle arrastra a la otra
    defs = [l for l in fuente.split('\n') if l.startswith('def test_')]
    assert len(defs) >= 4, (
        'este fichero tiene %d tests: cada comprobacion va en el suyo, '
        'porque juntas no se distinguen los fallos' % len(defs))
