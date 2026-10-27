# -*- coding: utf-8 -*-
"""El filtro de fold, y por que existe.

MEDIDO, con la poblacion de 23 tal como estaba: las 23 tienen y = 0. Las
75 de calibracion tambien. 98 de 98. No es que el heroe pierda siempre: es
que el corte (`corte_de_decision`) es la ULTIMA accion del heroe y acepta
'f', de modo que la poblacion preflop del instrumento era la poblacion de
los FOLDS.

Y un fold tiene y = 0 POR CONSTRUCCION. Meter 23 observaciones de una sola
clase en el AUC no anade manos: anade la regla de seleccion.

En la ventana de 877 manos: la ultima accion del heroe cae en preflop 637
veces —554 folds, 81 jugables, 2 checks— y de las 81 jugables NINGUNA tiene
etiqueta. Las 98 que si la tienen son todas folds.
"""
import collections
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def ins():
    ruta = os.path.join(ROOT, 'tools', 'equity_preflop_observables.py')
    spec = importlib.util.spec_from_file_location('eqpobs_fold', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _ModeloFalso:
    def __init__(self, perfiles):
        self.perfil = dict((p, 'PEZ') for p in perfiles)
        self.prob_vec = lambda *a, **k: None


def _mano(idx, hero_accion, spot='facing_open', villano='Villano'):
    """El heroe actua en SB con `hero_accion`; el villano abre en BB."""
    pre = []
    if spot == 'no_raise':
        pre = [{'pos': 'SB', 'action': 'r', 'amount': 3.0},
               {'pos': 'BB', 'action': 'c', 'amount': 3.0}]
    elif spot == 'facing_open':
        pre = [{'pos': 'BB', 'action': 'r', 'amount': 3.0}]
    elif spot == 'facing_3bet':
        pre = [{'pos': 'UTG', 'action': 'r', 'amount': 3.0},
               {'pos': 'BB', 'action': 'r', 'amount': 9.0}]
    pre.append({'pos': 'SB', 'action': hero_accion, 'amount': 3.0})
    return {'hand_id': 'H_F%03d' % idx,
            'players': [{'pos': 'SB', 'name': 'Jarduan', 'stack': 100.0,
                         'active': True, 'cards': 'AsKd'},
                        {'pos': 'BB', 'name': villano, 'stack': 100.0,
                         'active': True, 'cards': 'QhJd'}],
            'streets': {'preflop': {'actions': pre}}}


def _sel(ins, manos):
    et = dict((h['hand_id'], 1.0) for h in manos)
    pid = dict((h['hand_id'], h) for h in manos)
    return ins.seleccionar_manos(et, pid, _ModeloFalso(['Villano']))


# ---------------------------------------------- la accion que hace el heroe
@pytest.mark.parametrize('accion,juega', [
    ('b', True), ('c', True), ('r', True), ('x', True),
    ('f', False),
])
def test_lo_que_hace_el_heroe_en_el_corte_decide_si_entra(ins, accion, juega):
    trabajo, etapas, sin_rango, _ = _sel(ins, [_mano(1, accion)])
    assert len(trabajo) == (1 if juega else 0), (
        'el heroe hace %r y %s' % (accion, 'entra' if juega else 'no entra'))
    if not juega:
        assert sin_rango[ins.CLAVE_FOLD] == 1
        assert not trabajo


def test_un_fold_no_es_un_descarte_anonimo(ins):
    """Tiene su propia clave, no se mezcla con 'sin cartas' ni con 'spot sin
    alternativas'. Un descarte sin nombre no se puede auditar."""
    trabajo, _e, sin_rango, _ = _sel(ins, [_mano(1, 'f')])
    assert list(sin_rango) == [ins.CLAVE_FOLD]


# ---------------------------- el contador cuenta las que PASAN, no las que
def test_el_contador_de_la_etapa_cuenta_las_que_pasan(ins):
    """Este test existe porque lo escribi mal la primera vez: `_pasa` estaba
    ANTES del descarte, asi que la tabla decia 23 jugadas y descartaba 23 por
    no jugar. En la misma fila. Las dos cosas, y no se contradican."""
    trabajo, etapas, sin_rango, _ = _sel(ins, [_mano(1, 'f')])
    assert etapas['0_accion_jugada']['__total__'] == 0, (
        'llegan 1 y pasan 0: el contador dice las que pasan')
    assert etapas['1_corte_preflop']['__total__'] == 1, (
        'el corte SI se cuenta: la tabla tiene que enseyar donde se pierde')
    assert sin_rango[ins.CLAVE_FOLD] == 1
    assert trabajo == []


def test_el_corte_se_cuenta_antes_de_mirar_la_accion(ins):
    """Si el corte no se contara antes, la tabla enseñaria ceros donde hay
    manos y pareceria una poblacion vacia en vez de una poblacion
    descartada."""
    trabajo, etapas, _s, sp = _sel(ins, [_mano(1, 'f')])
    assert sum(sp.values()) == 1
    assert etapas['1_corte_preflop']['__total__'] == 1


# ------------------------------------ las acciones, contra el contrato
def test_las_acciones_jugadas_son_las_de_la_poblacion_b(ins):
    """`CONTRATO_L_SEC.md` §8: poblacion B = "el heroe continua o
    checkea". `x` es el check, `b` es la apuesta. Un fold no es ninguna de
    las dos, y por eso no esta."""
    assert set(ins.ACCIONES_JUGADAS) == {'b', 'c', 'r', 'x'}
    assert 'f' not in ins.ACCIONES_JUGADAS


def test_la_constante_explica_el_por_que(ins):
    """Una constante sin el motivo escrito es una constante que el proximo
    borra por>_parece>_innecesaria."""
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index('ACCIONES_JUGADAS = ')
    bloque = texto[max(0, i - 1500):i]
    assert 'FOLDEA' in bloque or 'fold' in bloque
    assert 'CONTRATO_L_SEC' in bloque, (
        'y tiene que decir de donde sale la poblacion, no deducirlo')


# ------------------------------------------------- y el dato que lo dispara
def test_en_la_poblacion_real_solo_entra_la_preflop_verificable(ins):
    """El dato que justifica todo esto. En la base canonica de 1253 SI
    entra una: H_0080, y=1. Su corte es la ultima accion del heroe en
    preflop, pero la mano siguio y tiene board y ganador, de modo que la
    etiqueta es legitima. El guardia pasa de «ninguna» a «exactamente esa».

    Medido: 24 cortes preflop en validacion, todos con el heroe foldeando,
    mas H_0080; 25 cortes en `sp` (14 no_raise, 9 facing_open, 2
    facing_3bet), y 24 descartes por fold.
    """
    from motor import learn, player_ranges
    ventana = learn.load_hands(reliable_only=True)
    ajuste = [h for h in ventana if not ins.cal.es_validacion(h['hand_id'])]
    labels = ins.eqm.perfiles_de(ajuste)
    model = player_ranges.ProfileRangeModel.from_hands(
        ajuste, labels=labels, alpha=player_ranges.DEFAULT_ALPHA)
    cal_, val_ = ins.cal.muestra()
    por_id = dict((h['hand_id'], h) for h in ventana)

    trabajo, _e, sin_rango, sp = ins.seleccionar_manos(dict(val_), por_id,
                                                       model)
    assert [t['id'] for t in trabajo] == ['H_0080'], (
        'si esto falla, el preflop de la poblacion B ha cambiado de verdad: '
        'mirar los descartes antes de tocar nada. Y el unico que entra es '
        'H_0080: %r' % ([t.get('id') for t in trabajo],))
    assert sum(sp.values()) == 25, 'los 25 cortes siguen estando ahi'
    assert sin_rango[ins.CLAVE_FOLD] == 24
    assert isinstance(val_, list) and val_, 'la muestra de validacion existe'
