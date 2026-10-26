# -*- coding: utf-8 -*-
import json

import pytest

from tools.reparar_asientos import (
    cargar_manos, ids_fuera_de_rango, leer_lineas, reparar, verificar,
)


def _jugador(nombre, pos='', active=True):
    return {'name': nombre, 'pos': pos, 'active': active, 'stack': 100.0}


def _mano(hid, players, btn='p5', winner=None):
    return {
        'hand_id': hid,
        'players': players,
        'btn_player': btn,
        'winner': winner or [],
        'allin': [],
        'streets': {'preflop': {'actions': []}},
    }


def _seis():
    return [
        _jugador('A', 'SB'), _jugador('B', 'BB'), _jugador('C', ''),
        _jugador('D', 'CO'), _jugador('E', 'MP'), _jugador('F', 'BTN'),
    ]


def _lineas(manos):
    return [json.dumps(h, ensure_ascii=False) for h in manos]


def test_repara_la_mano_corta_y_no_toca_las_demas():
    ref = [_mano('H_1', _seis())]
    corta = _seis()[:2] + _seis()[3:]
    corta[1]['pos'] = 'BB'
    corta[2]['pos'] = 'MP'
    base = [_mano('H_1', corta, winner=['p5']), _mano('H_2', _seis())]
    salida, informe = reparar(_lineas(base), _lineas(ref))
    manos = cargar_manos(salida)
    assert [p['name'] for p in manos[0]['players']] == list('ABCDEF')
    assert manos[0]['players'][3]['pos'] == 'MP'
    assert manos[0]['players'][2] == _seis()[2]
    assert salida[1] == _lineas(base)[1]
    assert informe['reparadas'] == ['H_1']
    assert informe['problemas_antes'] == 1
    assert informe['problemas_despues'] == 0
    assert informe['huecos']['1'] == 1


def test_es_idempotente():
    ref = [_mano('H_1', _seis())]
    base = [_mano('H_1', _seis()[:5])]
    salida, informe = reparar(_lineas(base), _lineas(ref))
    assert informe['reparadas'] == ['H_1']
    salida2, informe2 = reparar(salida, _lineas(ref))
    assert salida2 == salida
    assert informe2['reparadas'] == []


def test_falla_si_la_mano_tiene_nombres_repetidos():
    ref = [_mano('H_1', _seis())]
    corta = _seis()[:5]
    corta[1]['name'] = corta[0]['name']
    with pytest.raises(ValueError, match='nombres repetidos'):
        reparar(_lineas([_mano('H_1', corta)]), _lineas(ref))


def test_falla_si_el_nombre_no_esta_en_la_referencia():
    ref = [_mano('H_1', _seis())]
    corta = _seis()[:5]
    corta[0] = _jugador('Z', 'SB')
    base = [_mano('H_1', corta)]
    with pytest.raises(ValueError, match='no esta una sola vez'):
        reparar(_lineas(base), _lineas(ref))


def test_falla_si_la_mano_no_esta_en_la_referencia():
    base = [_mano('H_9', _seis()[:5])]
    with pytest.raises(ValueError, match='no esta en la referencia'):
        reparar(_lineas(base), _lineas([_mano('H_1', _seis())]))


def test_verifica_ids_fuera_de_rango():
    h = _mano('H_1', _seis()[:5], winner=['p5'])
    assert ('winner', 'p5') in ids_fuera_de_rango(h)
    assert verificar([h])
    assert verificar([_mano('H_2', _seis())]) == []


def test_una_referencia_corta_es_un_error():
    ref = [_mano('H_1', _seis()[:5])]
    with pytest.raises(ValueError, match='seis asientos'):
        reparar(_lineas([_mano('H_1', _seis()[:4])]), _lineas(ref))
