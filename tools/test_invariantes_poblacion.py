# -*- coding: utf-8 -*-
"""Las invariantes que `revision_2` pide explicitly, sobre `seleccionar_manos`.

  - Cada mano se descarta en UNA sola primera etapa; no puede aparecer en
    dos contadores de descarte.
  - Las cantidades de cada etapa se calculan sobre las manos que LLEGARON
    a ella.
  - Un `no_raise` con rival identificable entra en `trabajo`.
  - Un spot desconocido se informa, pero no entra en la poblacion.
  - Una etiqueta cuyo `hand_id` no existe en `por_id` produce un
    diagnostico explicito, no un `KeyError` sin contexto.
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


def _facing_open(idx, villano='Villano'):
    return _mano(idx,
                 [{'pos': 'BB', 'action': 'r', 'amount': 3.0},
                  {'pos': 'SB', 'action': 'c', 'amount': 3.0}],
                 [_jugador('Jarduan', 'SB'), _jugador(villano, 'BB', 'QhJd')])


def _no_raise_con_rival(idx, villano='Villano'):
    return _mano(idx,
                 [{'pos': 'SB', 'action': 'r', 'amount': 3.0},
                  {'pos': 'BB', 'action': 'f', 'amount': 0.0}],
                 [_jugador('Jarduan', 'SB'), _jugador(villano, 'BB', 'QhJd')])


def _seleccionar(ins, manos, perfiles):
    etiqueta = dict((h['hand_id'], 1.0) for h in manos)
    por_id = dict((h['hand_id'], h) for h in manos)
    return ins.seleccionar_manos(etiqueta, por_id, _ModeloFalso(perfiles))


# --------------------------------- cada mano se descarta UNA sola vez
def test_ninguna_mano_aparece_en_dos_descartes(ins):
    """Y no solo el total: el motivo es UNO por mano."""
    h2 = _facing_open(2)
    h2['players'][0].pop('cards')
    h3 = _mano(3, [{'pos': 'SB', 'action': 'r', 'amount': 3.0}],
               [_jugador('Jarduan', 'SB')])
    h4 = _facing_open(4, villano='Fantasma')

    trabajo, etapas, sin_rango, _ = _seleccionar(
        ins, [_facing_open(1), h2, h3, h4], ['Villano'])

    assert len(trabajo) == 1
    motivos = {k: v for k, v in sin_rango.items() if v}
    assert len(motivos) == 3, (
        'tres descartes con tres motivos distintos: %r' % motivos)
    assert sum(motivos.values()) == 3
    # y cada etapa pierde exactamente una
    tot = [etapas[e]['__total__'] for e in
           ('1_corte_preflop', '2_cartas_hero', '3_rival', '4_perfil')]
    assert tot == [4, 3, 2, 1], 'cada etapa pierde exactamente una: %r' % tot


# ------------------------- las etapas se cuentan sobre las que llegaron
def test_cada_etapa_parte_de_lo_que_llego_a_ella(ins):
    """La etapa 3 no puede contar mas que la etapa 2, porque solo cuenta
    las manos que pasaron la 2."""
    h2 = _facing_open(2)
    h2['players'][0].pop('cards')
    trabajo, etapas, _sin, _ = _seleccionar(
        ins, [_facing_open(1), h2, _facing_open(3)], ['Villano'])

    e = etapas
    assert e['1_corte_preflop']['__total__'] == 3
    assert e['2_cartas_hero']['__total__'] == 2, 'una se cae sin cartas'
    assert e['3_rival']['__total__'] == 2, 'ninguna mas se cae aqui'
    assert e['4_perfil']['__total__'] == 2


def test_el_spot_es_el_denominador_de_la_etapa_1(ins):
    trabajo, etapas, sin_rango, sp_cortes = _seleccionar(
        ins, [_facing_open(1), _no_raise_con_rival(2)], ['Villano'])

    assert sum(sp_cortes.values()) == 2, 'todo corte preflop cuenta'
    assert etapas['1_corte_preflop']['__total__'] == 2
    assert sp_cortes['facing_open'] == 1
    assert sp_cortes['no_raise'] == 1


# ----------------------------------------- el no_raise con rival entra
def test_no_raise_con_rival_entra(ins):
    trabajo, etapas, sin_rango, _ = _seleccionar(
        ins, [_no_raise_con_rival(1)], ['Villano'])
    assert len(trabajo) == 1
    assert trabajo[0]['spot'] == 'no_raise'
    assert sin_rango == collections.Counter()


# ------------------------------------ el spot desconocido se INFORMA
def test_un_spot_desconocido_se_cuenta_pero_no_entra(ins, monkeypatch):
    """`sp_cortes[spot]` va antes de validar, asi que un spot raro aparece
    con su clave. Y no entra en la poblacion.

    El monkeypatch es para forzar un spot que ACCIONES_SPOT no declara,
    porque en los datos reales solo salen los tres.
    """
    orig = ins.mano_del_spot
    monkeypatch.setattr(ins, 'mano_del_spot',
                        lambda h, calle, hero, idx: 'spot_inventado')
    trabajo, etapas, sin_rango, sp_cortes = _seleccionar(
        ins, [_facing_open(1)], ['Villano'])

    assert trabajo == [], 'un spot no declarado no puede entrar'
    assert sp_cortes['spot_inventado'] == 1, (
        'pero tiene que verse: un spot desconocido que desaparece es un '
        'descarte invisible')
    assert sin_rango['spot sin alternativas declaradas'] == 1
    monkeypatch.setattr(ins, 'mano_del_spot', orig)


# -------------------------------------- el hand_id ausente, explicito
def test_un_hand_id_ausente_dice_que_falta(ins):
    """Antes reventaba con `KeyError: 'H_FANTASMA'`, que dice el symptom
    y no la causa."""
    por_id = {}                     # la ventana NO tiene la mano
    with pytest.raises(KeyError) as e:
        ins.seleccionar_manos({'H_FANTASMA': 1.0}, por_id,
                              _ModeloFalso(['Villano']))
    m = str(e.value)
    assert 'H_FANTASMA' in m, 'dice QUE falta'
    assert 'ventana' in m or 'particion' in m, (
        'y dice DONDE deberia estar, para que el error sea util')


def test_el_diagnostico_del_id_ausente_explica_las_dos_causas(ins):
    """Hay dos razones posibles y el mensaje tiene que nombrarlas."""
    with pytest.raises(KeyError) as exc:
        ins.id_desconocido('H_X', {})
    m = str(exc.value)
    assert 'H_X' in m
    assert 'particion' in m and 'ventana' in m
    assert 'no se puede saber cual' in m, (
        'nombrar las dos causas es lo que lo hace util: sin eso solo sabes '
        'que algo falta')