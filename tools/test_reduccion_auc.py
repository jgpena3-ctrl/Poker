# -*- coding: utf-8 -*-
"""La reduccion a un numero: es la mediana, y para este AUC no importa.

AMBAS PARTES, Y LAS DOS IMPORTAN

La primera parte es que la cifra del documento no se desvie: el AUC con la
mediana tiene que seguir siendo el publicado, y las seis reducciones tienen
que seguir moviendolo lo mismo.

La segunda parte es mas importante: **la medicion tiene que REPRODUCIR la
cifra publicada antes de poder compararse con ella**. Si las seis reducciones
dan 0,83 y el publicado es 0,7667, la conclusion "la reduccion no importa"
seria sobre otra poblacion, y por tanto falsa. Esto comprueba que se esta
midiendo la poblacion correcta.

Y el filtro que hace falta es el que hace reproducible al AUC: la
VALIDACION. No la particion de folds, que fue el primer sospechoso y no era
nada: las 48 postflop con etiqueta son las 48 de poblacion B, cero folds.

QUE NO SE COMPRUEBA

  - que la mediana sea la reduccion CORRECTA. Que es correcto ponderar por
    bote es una cuestion de poker, no de codigo. Aqui se mide cuanto mueve.
  - la ponderacion por rival. No hay pesos definidos; definirlos es
    instrumentacion y otro bloque.
"""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DOC = os.path.join(ROOT, 'DOCS', 'QUE_REPRESENTA_LA_PREDICCION.md')

POB_B = ('b', 'c', 'r', 'x')


def _mod(nombre, donde='tools'):
    ruta = os.path.join(ROOT, donde, nombre)
    spec = importlib.util.spec_from_file_location(
        nombre[:-3].replace('.', '_'), ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope='module')
def contexto():
    """Lo que hace falta una vez: la instancia, la ventana y los modelos."""
    ar = _mod('auditar_representatividad.py')
    auc = _mod('auditar_auc.py')
    from motor import learn
    from motor import player_ranges
    ins = ar._inst()
    ventana = dict((h['hand_id'], h) for h in
                   learn.load_hands(reliable_only=True))
    ajuste = [h for h in ventana.values()
              if not ins.cal.es_validacion(h['hand_id'])]
    labels = ins.eqm.perfiles_de(ajuste)
    mod = {'preflop': player_ranges.ProfileRangeModel.from_hands(
        ajuste, alpha=player_ranges.DEFAULT_ALPHA), 'postflop': None}
    filas = ar.medir_todas_calles(ins, ventana, 'ultima')
    return ar, auc, ins, ventana, labels, mod, filas


def _reducciones(contexto, solo_validacion=True):
    """{reduccion: (positivas, negativas)} y el numero de rivales."""
    ar, _auc, ins, ventana, labels, mod, filas = contexto
    out = {k: ([], []) for k in ('mediana', 'media', 'primero', 'ultimo',
                                 'minimo', 'maximo')}
    n_rivales = []
    for f in filas:
        if not (f['jugada'] and f['viable'] and f['y'] is not None):
            continue
        if f['calle'] == 'preflop' or f['accion'] not in POB_B:
            continue
        if solo_validacion and not ins.cal.es_validacion(f['id']):
            continue
        h = ventana[f['id']]
        r = ins.eqm.equity_de_mano(h, labels, mod)
        if r is None or len(r) != 3 or r[0] is None:
            continue
        eqs, det = r[0], r[1]
        vals = list(eqs.values())
        if not vals or det.get('observable') is False:
            continue
        n_rivales.append(len(vals))
        orden = list(eqs.keys())
        red = {'mediana': det['mediana'],
               'media': sum(vals) / len(vals),
               'primero': eqs[orden[0]], 'ultimo': eqs[orden[-1]],
               'minimo': min(vals), 'maximo': max(vals)}
        for k, v in red.items():
            (out[k][0] if f['y'] == 1.0 else out[k][1]).append(v)
    return out, n_rivales


# ================================================== la medicion es la buena
def test_la_mediana_reproduce_el_auc_publicado(contexto):
    """LA COMPROBACION DE FONDO. Sin esto, todo lo de abajo compara otra
    poblacion y no lo sabe.

    El AUC publicado es n = 11, AUC 0,7667, IC [0,4333; 1,0000], y sale de
    la MEDIANA sobre la particion de validacion. Si al medirlo aqui no sale
    lo mismo, el filtro esta mal y hay que arreglar el filtro, no el numero.
    """
    _ar, auc, *_resto = contexto
    red, _n = _reducciones(contexto)
    pos, neg = red['mediana']
    assert len(pos) == 6 and len(neg) == 5, (
        'la poblacion del AUC es 6 ganadoras y 5 perdedoras, y sale %d y %d'
        % (len(pos), len(neg)))
    a = auc.auc_de(pos, neg)
    assert abs(a - 0.7667) < 5e-4, (
        'el AUC con la mediana es %r, y el publicado es 0,7667' % a)
    lo, hi = auc.ic_bootstrap(pos, neg)
    assert abs(lo - 0.4333) < 5e-4 and abs(hi - 1.0) < 5e-4, (
        'el IC es [%r, %r], y el publicado es [0,4333; 1,0000]' % (lo, hi))


def test_el_filtro_de_validacion_es_el_que_importa(contexto):
    """Y que el filtro de la particion es el que hace falta, no el de los
    folds. Este fue el primer sospechoso y resulto ser el equivocado."""
    ar, _auc, ins, ventana, _labels, _mod, filas = contexto
    con_fold = [f for f in filas
                if f['jugada'] and f['viable'] and f['y'] is not None
                and f['calle'] != 'preflop']
    acciones = set(f['accion'] for f in con_fold)
    assert not (acciones & {'f'}), (
        'hay folds entre las observaciones con etiqueta: %r. Antes de que los '
        'hubiera, la medicion con 47 observaciones NO era por los folds' % acciones)
    sin_validar = [f for f in con_fold if not ins.cal.es_validacion(f['id'])]
    assert len(sin_validar) > 30, (
        'y hay %d observaciones de calibracion fuera del AUC: sin el filtro de '
        'validacion se mide otra poblacion' % len(sin_validar))


# ================================================== cuanto mueve
def test_cuantas_observaciones_tienen_mas_de_un_rival(contexto):
    """En la poblacion del AUC es 1 de 11. Y es el motivo de que el recorrido
    sea pequeno: las otras 10 tienen una sola equity, y para una sola equity
    todas las reducciones coinciden."""
    red, n_rivales = _reducciones(contexto)
    multi = sum(1 for n in n_rivales if n > 1)
    assert len(n_rivales) == 11, 'observaciones medidas: %d' % len(n_rivales)
    assert multi == 1, (
        'ahora %d de las 11 tienen mas de un rival, y el documento dice 1'
        % multi)


def test_el_recorrido_entre_reducciones_es_menor_que_el_ic(contexto):
    """El veredicto del documento. Y el IC, no un cero: porque con 11
    observaciones cualquier cosa mueve un AUC, y lo que hay que ver es si
    mueve MAS que la incertidumbre que ya esta declarada."""
    ar, auc, *_resto = contexto
    red, _n = _reducciones(contexto)
    aucs = {}
    for k, (pos, neg) in red.items():
        assert pos and neg, '%s no tiene las dos clases' % k
        aucs[k] = auc.auc_de(pos, neg)
    recorrido = max(aucs.values()) - min(aucs.values())
    lo, hi = auc.ic_bootstrap(*red['mediana'])
    amplitud = hi - lo
    assert abs(recorrido - 0.0333) < 5e-4, (
        'el recorrido es %.4f, y el documento dice 0,0333' % recorrido)
    assert recorrido < amplitud, (
        'la reduccion mueve MAS que el IC: %.4f contra %.4f. El veredicto del '
        'documento seria el contrario' % (recorrido, amplitud))


def test_las_seis_reducciones_son_una_de_ellas_o_otra(contexto):
    """Que el documento no invente una septima. Las seis, y solo cuatro
    valores distintos: con una sola equity, mediana, media, primero y minimo
    coinciden."""
    ar, auc, *_resto = contexto
    red, _n = _reducciones(contexto)
    vals = set()
    for k, (pos, neg) in red.items():
        vals.add(round(auc.auc_de(pos, neg), 4))
    assert vals <= {0.7667, 0.8000}, (
        'valores de AUC que el documento no menciona: %r' % vals)


def test_el_documento_lo_dice(contexto):
    """Y que las cifras del documento siguen ahi."""
    with open(DOC, encoding='utf-8') as f:
        doc = f.read()
    assert 'auditar_auc.py:299' in doc, 'la linea de codigo de la reduccion'
    assert "r[1]['mediana']" in doc, 'y la reduccion, textual'
    assert '1 de las 11' in doc, 'y por que el recorrido es pequeno'
    assert '0,0333' in doc and '0,5667' in doc, 'y las dos cifras'
    assert 'reproduce el AUC publicado exacto' in doc, (
        'y la regla de que una medicion comparada con una cifra publicada tiene '
        'que reproducirla')