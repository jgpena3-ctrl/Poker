# -*- coding: utf-8 -*-
"""Los contadores por etapa, probados con su COMPORTAMIENTO.

`revision_2` §1: el test anterior solo comprobaba que `sp_cortes` apareciera
antes de `villano_del_corte()`. Eso es estructura del codigo, no prueba de
que los contadores cuenten. Una refactorizacion podia conservar los nombres
de las variables y volver a romper la auditoria sin que nada se notara.

Aqui hay manos SINTETICAS que fallan a proposito en cada etapa, y se
comprueba el recuento. Si alguien rompe la cadena de filtros, el numero no
sale y el test falla.

NO se sustituye `hero_pos_de` ni `corte_de_decision`: las manos se
construyen para que el codigo de verdad las lea, y asi el test tambien
comprueba que el corte se situa donde uno creeria.
"""
import collections
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def ins():
    ruta = os.path.join(ROOT, 'tools', 'equity_preflop_observables.py')
    spec = importlib.util.spec_from_file_location('eqpobs', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _ModeloFalso:
    """Solo lo que `seleccionar_manos` necesita: `.perfil`."""

    def __init__(self, perfiles):
        self.perfil = dict((p, 'PEZ') for p in perfiles)


def _mano(idx, acciones, players):
    return {'hand_id': 'H_T%03d' % idx,
            'players': players,
            'streets': {'preflop': {'actions': acciones}}}


def _jugador(nombre, pos, cartas='AsKd'):
    d = {'pos': pos, 'name': nombre, 'stack': 100.0, 'active': True}
    if cartas is not None:
        d['cards'] = cartas
    return d


def _seleccionar(ins, manos, perfiles):
    etiqueta = dict((h['hand_id'], 1.0) for h in manos)
    por_id = dict((h['hand_id'], h) for h in manos)
    return ins.seleccionar_manos(etiqueta, por_id, _ModeloFalso(perfiles))


# Las manos se construyen para que `corte_de_decision` las lea bien. El corte
# cae en la accion del HERO, que es la que decide.
def _contra_subida(idx, villano='Villano', cartas='QhJd'):
    """El hero hace call facing una subida: spot facing_open."""
    return _mano(idx,
                 [{'pos': 'BB', 'action': 'r', 'amount': 3.0},
                  {'pos': 'SB', 'action': 'c', 'amount': 3.0}],
                 [_jugador('Jarduan', 'SB'), _jugador(villano, 'BB', cartas)])


def _abre_sin_mas(idx, villano='Villano'):
    """El hero abre y no hay nadie detras: spot no_raise, SIN RIVAL."""
    return _mano(idx,
                 [{'pos': 'SB', 'action': 'r', 'amount': 3.0}],
                 [_jugador('Jarduan', 'SB')])


# ------------------------------------------------------- el camino bueno
def test_una_mano_buena_pasa_las_cuatro_etapas(ins):
    trabajo, etapas, sin_rango, sp_cortes = _seleccionar(
        ins, [_contra_subida(1)], ['Villano'])

    assert len(trabajo) == 1, 'una mano bien formada tiene que entrar'
    assert trabajo[0]['spot'] == 'facing_open'
    assert trabajo[0]['villano'] == 'Villano'
    for etapa in ('1_corte_preflop', '2_cartas_hero', '3_rival', '4_perfil'):
        assert etapas[etapa]['__total__'] == 1, (
            'la etapa %s tiene que contar 1' % etapa)
    assert sin_rango == collections.Counter(), 'nada se deberia descartar'
    assert sp_cortes['facing_open'] == 1


# ------------------------------------------------- falla en la etapa 2
def test_sin_cartas_del_hero_muere_en_la_etapa_2(ins):
    h = _contra_subida(1)
    h['players'][0].pop('cards')
    trabajo, etapas, sin_rango, _ = _seleccionar(ins, [h], ['Villano'])

    assert trabajo == []
    assert etapas['1_corte_preflop']['__total__'] == 1
    assert etapas['2_cartas_hero']['__total__'] == 0, (
        'no puede pasar de la etapa 2 sin cartas')
    assert sin_rango['sin cartas del hero'] == 1
    assert 'sin villano identificado en el corte' not in sin_rango, (
        'un descarte no puede contar tambien en una etapa posterior')


# ------------------------------------------------- falla en la etapa 3
def test_sin_rival_muere_en_la_etapa_3(ins):
    trabajo, etapas, sin_rango, sp_cortes = _seleccionar(
        ins, [_abre_sin_mas(1)], ['Villano'])

    assert trabajo == []
    assert sp_cortes['no_raise'] == 1, 'el spot se cuenta antes de validar'
    assert etapas['2_cartas_hero']['__total__'] == 1
    assert etapas['3_rival']['__total__'] == 0
    assert sin_rango['sin villano identificado en el corte'] == 1


def test_no_raise_con_rival_si_pasa(ins):
    """La correccion del bloque anterior: sin subida previa, el rival es el
    PRIMER jugador que actua despues del hero. Antes esto se descartaba."""
    h = _mano(1,
              [{'pos': 'SB', 'action': 'r', 'amount': 3.0},
               {'pos': 'BB', 'action': 'f', 'amount': 0.0}],
              [_jugador('Jarduan', 'SB'), _jugador('Villano', 'BB', 'QhJd')])
    trabajo, etapas, sin_rango, _ = _seleccionar(ins, [h], ['Villano'])

    assert len(trabajo) == 1, (
        'un no_raise tiene rival: el siguiente en actuar. Antes se caia.')
    assert trabajo[0]['spot'] == 'no_raise'
    assert trabajo[0]['villano'] == 'Villano'
    assert sin_rango == collections.Counter()


# ------------------------------------------------- falla en la etapa 4
def test_villano_sin_perfil_muere_en_la_etapa_4(ins):
    trabajo, etapas, sin_rango, _ = _seleccionar(
        ins, [_contra_subida(1, villano='Fantasma')], ['Villano'])

    assert trabajo == []
    assert etapas['3_rival']['__total__'] == 1, (
        'el rival SI se identifica; lo que falta es el perfil')
    assert etapas['4_perfil']['__total__'] == 0
    assert sin_rango['villano sin perfil: cae al prior plano'] == 1


# ------------------------------------------- las etapas son ACUMULATIVAS
def test_cada_etapa_descuenta_lo_que_la_anterior_ya_no_admite(ins):
    """La columna que baja es la que localiza el descarte."""
    h2 = _contra_subida(2)
    h2['players'][0].pop('cards')

    manos = [
        _contra_subida(1),
        h2,                                    # muere en la 2
        _abre_sin_mas(3),                       # muere en la 3
        _contra_subida(4, villano='Fantasma'),  # muere en la 4
        _mano(5,
              [{'pos': 'SB', 'action': 'r', 'amount': 3.0},
               {'pos': 'BB', 'action': 'r', 'amount': 9.0},
               {'pos': 'SB', 'action': 'r', 'amount': 22.0},
               {'pos': 'BB', 'action': 'c', 'amount': 22.0}],
              [_jugador('Jarduan', 'SB'), _jugador('Villano', 'BB', 'QhJd')]),
    ]
    trabajo, etapas, sin_rango, _ = _seleccionar(
        ins, manos, ['Villano'])

    assert len(trabajo) == 2, 'solo las dos buenas se admiten'
    t = [etapas[e]['__total__'] for e in
         ('1_corte_preflop', '2_cartas_hero', '3_rival', '4_perfil')]
    assert t == [5, 4, 3, 2], (
        'las etapas tienen que ir bajando 5, 4, 3, 2 y se obtuvo %r' % t)
    assert sin_rango['sin cartas del hero'] == 1
    assert sin_rango['sin villano identificado en el corte'] == 1
    assert sin_rango['villano sin perfil: cae al prior plano'] == 1
    assert sum(sin_rango.values()) == 3, (
        'tres descartes, uno por etapa, y ninguno contado dos veces')
    assert trabajo[1]['spot'] == 'facing_3bet', (
        'tres subidas antes del corte son facing_3bet, no facing_open')


# ---------------------------------------------- la version, en la entrada
def test_la_entrada_de_cache_lleva_la_version(ins):
    """`calculada` cuenta solo si la VERSION coincide, y eso exige que la
    entrada la lleve."""
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index("cache[hid] = {'equity'")
    assert "'version': VERSION" in texto[i:i + 400], (
        'sin la version en la entrada, el filtro de `calculada` no puede '
        'distinguir una entrada vieja de una de ahora')


def test_la_columna_calculada_solo_cuenta_la_version_vigente(ins):
    """Y el filtro mira las dos cosas: que sea una mano ADMITIDA y que su
    version sea la actual."""
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index('def calculadas_para(spot):')
    cuerpo = texto[i:i + 700]
    assert "x['spot'] != spot" in cuerpo, 'filtra por spot'
    assert "hechos.get(x['id'])" in cuerpo, (
        'recorre las ADMITIDAS, no todas las entradas de la cache')
    assert "e.get('version') == VERSION" in cuerpo, (
        'y exige que la version sea la vigente')