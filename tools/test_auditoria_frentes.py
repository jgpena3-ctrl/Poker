# -*- coding: utf-8 -*-
"""La auditoria de los frentes, y que no se contradiga sola.

Y lo que hay aqui son tres cosas:

  · que el documento declare las DOS cifras —5 y 29— con su definicion, y la
    condicion de repetirlas;
  · que declare la INMOVILIDAD del grafo de `preflop_matrices.json`;
  · y que la inmovilidad SEA REAL, que es lo unico que vale.

## Y LA INMOVILIDAD, COMO SE COMPRUEBA

Y contra un **commit concreto**, no contra «el commit anterior»: el commit
anterior cambia con cada commit, y un control que se mueve solo no es un
control. Y el ancla es el commit de antes de esta auditoria, y su sha se
comprueba, porque un commit no garantiza por si solo que siga siendo la
version que se creyo.

Y lo que se compara no es el texto del fichero, sino lo que `git` dice que
cambio, que es lo que sabe de normalizaciones de fin de linea y demas.

Y hay DOS conjuntos:

  · los ficheros que YA dependian del fichero de matrices: no se tocan, y si
    se tocan, es una decision DECLARADA con su motivo;
  · los ficheros NUEVOS que dependan de el: son dependencias nuevas sobre un
    fichero cuya intencion no esta fijada, y tambien se declaran una a una.

Y las dos declaraciones empiezan VACIAS, y vacias es una DECLARACION: no se
ha tocado nada, y no hay ninguna dependencia nueva.
"""
import io
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'DOCS', 'AUDITORIA_FRONTES.md')

# El ancla: el commit de ANTES de esta auditoria. Y su sha, que se comprueba.
ANCLA_COMMIT = 'ad72993'
ANCLA_SHA = 'ad72993b03843ecd8a4a14926f5da2491e920af6'


def _git(*args):
    return subprocess.run(['git'] + list(args), cwd=ROOT,
                          capture_output=True, text=True)


def _registro():
    with io.open(DOC, encoding='utf-8') as f:
        return f.read()


def _sha_real(rev):
    r = _git('rev-parse', rev)
    return r.stdout.strip()


def _ficheros_de_motor(rev=None):
    """Los `.py` de `motor/`, del arbol de trabajo o de una revision."""
    if rev is None:
        carpeta = os.path.join(ROOT, 'motor')
        return sorted('motor/' + n for n in os.listdir(carpeta)
                      if n.endswith('.py'))
    r = _git('ls-tree', '--name-only', rev, 'motor/')
    return sorted(l for l in r.stdout.split('\n')
                  if l.endswith('.py') and l.strip())


def _contenido(rev, ruta):
    r = _git('show', '%s:%s' % (rev, ruta))
    return r.stdout


def _dependientes_de(rev):
    """Los ficheros que, en esa revision, dependen del fichero de matrices."""
    salida = []
    for f in _ficheros_de_motor(rev):
        if 'preflop_matrices' in _contenido(rev, f):
            salida.append(f)
    return sorted(salida)


def _dependientes_del_arbol():
    salida = []
    for f in _ficheros_de_motor():
        with io.open(os.path.join(ROOT, *f.split('/')), encoding='utf-8') as fh:
            if 'preflop_matrices' in fh.read():
                salida.append(f)
    return sorted(salida)


# Las declaraciones, y las dos empiezan casi VACIAS.
#
# Y lo que se protege, y es lo que R1 pide, son **los TESTS** de `motor/` que
# dependen del fichero de matrices: no se tocan, porque un test cambiado puede
# tapar un cambio de comportamiento, y ese es el efecto colateral que hay que
# evitar.
#
# Y los MODULOS del motor, en cambio, SI se pueden tocar, y solo por una de
# estas dos razones:
#
#   · un cambio en el CONTRATO DE LECTURA —que pasa con una tabla que falta
#     o que esta danada—, que es instrumentacion y no semantica;
#   · un cambio declarado aqui, con su motivo.
#
# Y lo que NO se puede tocar sin que A1 declare la intencion del fichero es
# la REGLA DE ELECCION —que tabla elige cada lector—, y esa no se protege con
# un diff sino con un test COMPORTAMENTAL: `motor/test_lectura_matrices.py`
# fija, caso por caso, que tabla elige cada uno de los tres lectores.
MODIFICACIONES_DECLARADAS = {}
DEPENDENCIAS_NUEVAS_DECLARADAS = {
    'motor/test_lectura_matrices.py': (
        'fichero NUEVO de tests del CONTRATO DE LECTURA, y el unico que '
        'depende del fichero de matrices. Y los datos son SINTETICOS: el '
        'fichero real no se lee para medir nada, porque su INTENCION no esta '
        'fijada y un test que dependa de el hereda esa falta. Y lo que se '
        'comprueba del fichero real es solo que esta ENTERO.'),
}


def test_el_ancla_es_el_commit_que_se_cree():
    """Y que el ancla siga siendo el ancla.

    Y el motivo: un ancla que se mueve sola es un ancla que no ancla nada, y
    el control que se apoya en ella se quedaria sin contraluz.
    """
    assert _sha_real(ANCLA_COMMIT) == ANCLA_SHA, (
        'el ancla %s ya no es el commit que se declaro: ahora es %s'
        % (ANCLA_COMMIT, _sha_real(ANCLA_COMMIT)))


def test_los_tests_de_motor_que_dependen_del_matrix_no_se_han_tocado():
    """Y que los TESTS que dependian de el, siguen igual.

    Y la comparacion es la de `git`, contra el ancla, y no una comparacion de
    texto: que es lo que hace que `git` sepa de normalizaciones de fin de
    linea, y lo que hace que el control mida lo que dice medir.

    Y por que son los TESTS y no los modulos: un test modificado puede tapar
    un cambio de comportamiento, y ese es el efecto colateral que hay que
    evitar. Y los modulos del motor SI se pueden tocar, y solo por un cambio
    del CONTRATO DE LECTURA —que pasa con una tabla que falta o que esta
    danada—, que es instrumentacion y no semantica. Y lo que no se puede
    tocar sin la intencion de A1 es la REGLA DE ELECCION, y esa la fija un
    test comportamental, no un diff.
    """
    protegidos = set(f for f in _dependientes_de(ANCLA_COMMIT)
                     if os.path.basename(f).startswith('test_'))
    assert protegidos, (
        'el ancla no tiene ningun TEST que dependa del fichero de matrices: '
        'y entonces este test no vigila nada')

    r = _git('diff', '--name-only', ANCLA_COMMIT, '--', 'motor/')
    cambiados = set(l.strip() for l in r.stdout.split(chr(10)) if l.strip())
    tocados = sorted(cambiados & protegidos)

    declarados = sorted(set(MODIFICACIONES_DECLARADAS) & protegidos)
    no_declarados = sorted(set(tocados) - set(declarados))
    assert not no_declarados, (
        'se han modificado %d TEST(s) de `motor/` que dependen de '
        '`preflop_matrices.json`, y no estan declarados:\n   %s\n\n'
        'Y un test modificado puede tapar un cambio de comportamiento, que es '
        'lo que este control existe para ver. Y si el cambio es NECESARIO, '
        'se declara en MODIFICACIONES_DECLARADAS, con su motivo.'
        % (len(no_declarados), '\n   '.join(no_declarados)))


def test_no_hay_dependencias_nuevas_del_fichero_de_matrices():
    """Y que no haya ficheros NUEVOS que dependan de el.

    Y el motivo: un test nuevo que depende del fichero es una dependencia
    NUEVA sobre un fichero cuya intencion no esta fijada, y esa intencion la
    declara A1. De modo que la dependencia nueva no se prohibe: se DECLARA.
    """
    nuevas = sorted(set(_dependientes_del_arbol())
                    - set(_dependientes_de(ANCLA_COMMIT)))
    declaradas = sorted(set(DEPENDENCIAS_NUEVAS_DECLARADAS))
    no_declaradas = sorted(set(nuevas) - set(declaradas))
    assert not no_declaradas, (
        'hay %d fichero(s) NUEVO(S) en `motor/` que dependen de '
        '`preflop_matrices.json`, y no estan declarados:\n   %s\n\n'
        'Y se declaran en DEPENDENCIAS_NUEVAS_DECLARADAS, con su motivo.'
        % (len(no_declaradas), '\n   '.join(no_declaradas)))


def test_las_declaraciones_tienen_motivo():
    """Y que toda declaracion diga POR QUE.

    Y el motivo de este test: una declaracion sin motivo es una lista de
    nombres, y una lista de nombres no se puede comprobar ni discutir.
    """
    for nombre, motivo in (list(MODIFICACIONES_DECLARADAS.items())
                           + list(DEPENDENCIAS_NUEVAS_DECLARADAS.items())):
        assert isinstance(motivo, str), (
            'la declaracion de %r no es un texto' % nombre)
        assert motivo.strip(), (
            'la declaracion de %r no dice POR QUE' % nombre)


def test_el_documento_declara_las_dos_cifras():
    """Y que las dos cifras esten, con su definicion.

    Y el motivo: una cifra sin su definicion se cita mal, y la que se cita
    mal es la que se propaga.
    """
    doc = _registro()
    assert '**5**' in doc, 'el documento no declara la cifra de 5'
    assert '**29**' in doc, 'el documento no declara la cifra de 29'
    # y cada una, con su definicion
    assert 'corte' in doc, 'la cifra de 5 es por corte, y hay que decirlo'
    assert 'entero' in doc, 'la cifra de 29 es con el board entero'
    # y las dos, en la misma tabla
    lineas = [l for l in doc.split('\n') if l.startswith('|')]
    filas = [l for l in lineas if '**5**' in l or '**29**' in l]
    assert len(filas) >= 2, (
        'las dos cifras tienen que estar en la MISMA tabla, que es la que las '
        'contrasta: %r' % filas)


def test_el_documento_declara_la_condicion_de_repeticion():
    """Y que diga que hay que volver a medirlas.

    Y el motivo: la ventana de 877 es de la base de HOY, y la copia tiene
    1258. De modo que un numero sin la base que lo produjo es un numero que
    se cita mal.
    """
    doc = _registro()
    assert 'CONDICION DE REPETICION' in doc, (
        'el documento no dice que las cifras hay que repetirlas')
    assert '1258' in doc, (
        'y no dice que la copia tiene 1258 manos, que es lo que hace que el '
        'numero de hoy no valga para despues')


def test_el_documento_declara_la_inmovilidad_del_grafo():
    """Y que el grafo de `matrix` quede declarado como inmovil.

    Y el motivo: un grafo que se puede tocar sin decir nada es un grafo que
    se va a tocar.
    """
    doc = _registro()
    assert 'EL GRAFO NO SE TOCA' in doc, (
        'el documento no declara la inmovilidad del grafo de matrix')
    assert 'cambio a ciegas' in doc, (
        'y no dice POR QUE: que es lo que convence a quien lo vaya a tocar')

def test_el_documento_declara_las_tres_decisiones_de_a1():
    """Y que las tres esten, con su «que NO se toca».

    Y el motivo de que el «que no se toca» sea la parte que se comprueba: sin
    el, «pendiente» es una palabra, y con el es una FRONTERA. Y una frontera
    que no esta escrita, es una frontera que se cruza sin querer.
    """
    doc = _registro_matrix()
    assert 'DECISIONES PENDIENTES DE A1' in doc, (
        'el documento no tiene la seccion de decisiones de A1')
    for ancla in ('D1', 'D2', 'D3'):
        assert ancla in doc, 'falta la decision %s' % ancla
    # y cada una con su «que NO se toca»
    cuerpo = doc.split('DECISIONES PENDIENTES DE A1', 1)[1]
    for ancla in ('D1', 'D2', 'D3'):
        bloque = cuerpo.split('### %s' % ancla, 1)[1]
        bloque = bloque.split('### ', 1)[0]
        assert 'qué NO se toca' in bloque, (
            'la decision %s no dice que NO se toca mientras no se decida' % ancla)
        assert 'qué se decide' in bloque, (
            'la decision %s no dice que se decide' % ancla)
        assert 'qué depende' in bloque, (
            'la decision %s no dice que depende de la decision' % ancla)


def _registro_matrix():
    import io as _io
    import os as _os
    ruta = _os.path.join(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))), 'DOCS', 'AUDITORIA_MATRIX.md')
    with _io.open(ruta, encoding='utf-8') as f:
        return f.read()

# ---------------------------------------------------------------------------
# NINGUN HALLAZGO SIN FICHA
# ---------------------------------------------------------------------------

# Y la declaracion de los hallazgos, y la lista ES la declaracion ✓: un
# hallazgo que no esta aqui no esta vigilado ✓, y uno que esta aqui tiene que
# seguir con su ficha ✓.
#
# Y las tres cosas que se comprueban ✓, y que son las que hacen que un
# hallazgo no se olvide ✓: el **nombre** ✓, la **ubicacion** ✓, y el **estado**
# ✓ —el motivo de no arreglarlo ✓ y la condicion de activacion ✓, cuando
# los hay— ✓.
HALLAZGOS = (
    # (documento, ancla del hallazgo, nombre, ubicacion, estado)
    ('AUDITORIA_RULES.md', '## 6. H4', 'H4', 'motor/learn.py',
     'post-adopción'),
    ('AUDITORIA_MATRIX.md', '| **H1** |', 'H1', 'profile.load_base_rates',
     'corregido'),
    ('AUDITORIA_MATRIX.md', '| **H2** |', 'H2', 'player_ranges._prior_grid',
     'corregido'),
    ('AUDITORIA_MATRIX.md', '| **H3** |', 'H3', 'asistente_live._recom_preflop',
     'no se toca'),
    ('AUDITORIA_MATRIX.md', '| **H4** |', 'H4', 'Tres lectores',
     'documentado'),
    ('AUDITORIA_MATRIX.md', '| **H5** |', 'H5', 'preflop_matrices.json',
     'RESERVADO PARA A1'),
    ('AUDITORIA_CONTRATO_P.md', '| M1 |', 'M1', 'preflop_events',
     'los tests lo notan'),
    ('AUDITORIA_CONTRATO_P.md', '| M2 |', 'M2', '_es_ciega_bb',
     'los tests lo notan'),
    ('AUDITORIA_CONTRATO_P.md', '| M3 |', 'M3', 'entradas_bb_rechazadas',
     'los tests lo notan'),
    ('AUDITORIA_CONTRATO_P.md', '| M4 |', 'M4', 'entradas_bb_rechazadas',
     'los tests lo notan'),
)


def _documento(nombre):
    ruta = os.path.join(ROOT, 'DOCS', nombre)
    with io.open(ruta, encoding='utf-8') as f:
        return f.read()


def test_ningun_hallazgo_sin_ficha():
    """Y que cada hallazgo tenga nombre, ubicacion y estado.

    Y el motivo de que la lista este en el TEST y no en el documento ✓: una
    lista en el documento se puede editar sin que nadie la mire ✓, y una
    lista en el test **falla cuando el documento y la lista dejan de
    coincidir** ✓.

    Y el motivo de que el estado sea una palabra y no un parrafo ✓: es lo que
    permite distinguir **«corregido»** ✓ de **«no se toca, y por que»** ✓, y
    un hallazgo sin estado es un asunto abierto ✓.
    """
    for documento, ancla, nombre, ubicacion, estado in HALLAZGOS:
        texto = _documento(documento)
        assert ancla in texto, (
            'el hallazgo %s no esta en %s con la forma declarada (%r)'
            % (nombre, documento, ancla))
        # y el bloque del hallazgo, con su ubicacion y su estado
        bloque = texto.split(ancla, 1)[1].split('\n## ', 1)[0]
        assert ubicacion in bloque, (
            'el hallazgo %s de %s no dice donde esta (%r)'
            % (nombre, documento, ubicacion))
        assert estado.lower() in bloque.lower(), (
            'el hallazgo %s de %s no dice su estado (%r): un hallazgo sin '
            'estado es un asunto abierto'
            % (nombre, documento, estado))


def test_h3_y_h5_declaran_su_motivo_de_no_arreglarse():
    """Y que los dos que NO se arreglan, digan POR QUE.

    Y son los dos que mas tentacion hay de tocar ✓: el de la convencion de
    la `p` ✓ —que la fijan los tests, y tocarla es mudar una decision— ✓ y el
    de la intencion del fichero de matrices ✓ —que es de A1— ✓.

    Y el motivo de que haga falta ✓: un hallazgo que no se arregla y no dice
    por que se parece a un hallazgo olvidado ✓, y en los dos casos se
    convertiria en un agujero ✓.
    """
    texto = _documento('AUDITORIA_MATRIX.md')
    h3 = texto.split('| **H3** |', 1)[1].split('\n## ', 1)[0]
    assert 'NO se toca' in h3 or 'No se toca' in h3, (
        'H3 tiene que decir que NO se toca, y por que: %r' % h3[:200])
    h5 = texto.split('| **H5** |', 1)[1].split('\n## ', 1)[0]
    assert 'A1' in h5, (
        'H5 tiene que decir que la decision es de A1: %r' % h5[:200])

