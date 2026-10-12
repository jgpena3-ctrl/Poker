"""Tests de la jerarquía de rivales y su modo sombra.

Dos garantías:

1. La clasificación hace lo que dice (agresor > checker > pendiente).
2. El modo sombra NO altera la recomendación. Es un instrumento de
   medición, no una corrección: si cambiara una acción, estaría
   calibrando con 36 manos por escenario.
"""
import json
import os

import pytest

from motor.hierarchy import (AGGRESSOR, CHECKER, PENDING, ShadowLog,
                             classify_villains, passive_penalty,
                             shadow_equity, shadow_record, texture_key)
from motor.recommend_loop import recommend

BOARD_FLOOP = ['Qh', '7s', '2c']
BOARD_WET = ['Qh', '7s', '2c']          # dos tonos + board mojado
HERO = ['As', 'Kd']


# --- textura y penalización ---------------------------------------------

def test_texture_key():
    assert texture_key(BOARD_FLOOP) in ('rainbow', 'two_tone', 'monotone')
    assert texture_key(None) == 'rainbow'
    assert texture_key(['Qh']) == 'rainbow'


def test_penalizacion_cero_sin_checkers():
    assert passive_penalty(BOARD_FLOOP, 'flop', 0) == 0.0


def test_penalizacion_crece_con_checkers():
    p0 = passive_penalty(BOARD_FLOOP, 'turn', 0)
    p1 = passive_penalty(BOARD_FLOOP, 'turn', 1)
    p2 = passive_penalty(BOARD_FLOOP, 'turn', 2)
    assert p0 == 0.0
    assert 0 < p1 < p2


def test_penalizacion_es_lineal_no_exponencial():
    """El error de `eq ** n` sería enorme: aquí dobla, no se cuadruplica.

    Medido: añadir un checker en turn baja ~2 puntos (69% -> 67%, n=36).
    Una forma exponencial con rango uniforme quitaría ~50.
    """
    p1 = passive_penalty(BOARD_FLOOP, 'turn', 1)
    p2 = passive_penalty(BOARD_FLOOP, 'turn', 2)
    assert p2 <= 2.0 * p1 + 1e-9          # lineal
    assert p2 < 4.0 * p1                    # y no p2 ≈ p1^2
    assert p1 < 0.10                        # penalización pequeña


def test_penalizacion_turn_es_la_calibrada():
    """Turn+seco es el escenario con dato directo: ~0.02."""
    p = passive_penalty(['Qh', '7s', '2c'], 'turn', 1)
    assert 0.01 <= p <= 0.03


def test_penalizacion_crece_en_flop_mas_que_turn():
    """Flop deja dos cartas por salir, turn una."""
    f = passive_penalty(BOARD_FLOOP, 'flop', 1)
    t = passive_penalty(BOARD_FLOOP, 'turn', 1)
    assert f > t


def test_penalizacion_river_la_mas_baja():
    r = passive_penalty(BOARD_FLOOP, 'river', 1)
    t = passive_penalty(BOARD_FLOOP, 'turn', 1)
    assert r < t


def test_penalizacion_saturada():
    """Muchos checkers no pueden invertir la equity."""
    p = passive_penalty(BOARD_FLOOP, 'flop', 500)
    assert p <= 0.5


def test_board_con_pareja_penaliza_mas():
    """Un board con pareja es más peligroso que uno liso."""
    liso = passive_penalty(['Qh', '7s', '2c'], 'turn', 1)
    pareado = passive_penalty(['Qh', 'Qh', '2c'], 'turn', 1)
    assert pareado > liso


# --- clasificación -------------------------------------------------------

def _acts(*pares):
    return [{'pos': p, 'action': a} for p, a in pares]


def test_elige_ultimo_agresor():
    acts = _acts(('UTG', 'b'), ('MP', 'r'), ('CO', 'c'))
    h = classify_villains(acts, 'BTN')
    assert h['main'] == 'MP'
    assert 'agresor' in h['main_reason']


def test_hero_que_tiene_bet_enfrenta_al_agresor():
    acts = _acts(('UTG', 'b'), ('CO', 'r'), ('BTN', 'c'))
    h = classify_villains(acts, 'BTN')
    assert h['main'] == 'CO'


def test_pendientes_no_son_checkers():
    """Quien aún no ha actuado puede resubir: no se penaliza como draw."""
    acts = _acts(('UTG', 'b'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN', pending_positions=['CO', 'SB'])
    assert 'CO' in h['pending']
    assert 'SB' in h['pending']
    assert 'CO' not in h['checkers']
    assert 'SB' not in h['checkers']


def test_checkers_quedan_fuera_del_principal():
    acts = _acts(('UTG', 'x'), ('MP', 'x'), ('BTN', 'x'))
    h = classify_villains(acts, 'BTN')
    assert h['main'] == 'MP'                  # el último que checkeó
    assert h['checkers'] == ['UTG']
    assert 'BTN' not in h['checkers']


def test_sin_agresion_usa_posicion():
    acts = _acts(('BTN', 'x'))
    h = classify_villains(acts, 'BTN', pending_positions=['CO'])
    assert h['main'] == 'CO' or h['main'] is None


def test_clasificacion_no_mezcla_rangos():
    """La jerarquía elige UN rival, no combina varios."""
    acts = _acts(('UTG', 'b'), ('MP', 'r'), ('BTN', 'c'))
    h = classify_villains(acts, 'BTN')
    assert isinstance(h['main'], str)
    assert h['aggressors'] == ['UTG', 'MP']
    assert h['main'] == h['aggressors'][-1]


def test_hero_sin_acciones_devuelve_estructura_vacia():
    h = classify_villains([], 'BTN')
    assert h['main'] is None
    assert h['checkers'] == []
    assert h['pending'] == []


# --- cálculo sombra ------------------------------------------------------

def test_shadow_equity_reduce_y_marca_experimental():
    jer = classify_villains(_acts(('UTG', 'x'), ('MP', 'b')), 'BTN')
    jer['checkers'] = ['UTG']
    s = shadow_equity(0.50, BOARD_FLOOP, 'turn', jer)
    assert s['equity_shadow'] < s['equity_main']
    assert s['n_checker'] == 1
    assert s['penalty'] > 0
    assert s['experimental'] is True


def test_shadow_equity_sin_checkers_no_cambia():
    jer = classify_villains(_acts(('MP', 'b')), 'BTN')
    s = shadow_equity(0.50, BOARD_FLOOP, 'turn', jer)
    assert s['equity_shadow'] == s['equity_main']
    assert s['delta'] == 0.0


def test_pendientes_no_entran_en_la_penalizacion():
    """Un pendiente no es un checker: siguen siendo amenaza activa."""
    jer = {'main': 'MP', 'checkers': [], 'pending': ['CO', 'SB']}
    s = shadow_equity(0.50, BOARD_FLOOP, 'turn', jer)
    assert s['penalty'] == 0.0
    assert s['n_pending'] == 2
    assert s['equity_shadow'] == 0.50


# --- log ----------------------------------------------------------------

def test_shadow_log_escribe_jsonl(tmp_path):
    p = tmp_path / 'shadow.jsonl'
    lg = ShadowLog(path=str(p))
    rec = shadow_record('H_1', 'flop', BOARD_FLOOP, HERO,
                        classify_villains(_acts(('MP', 'b')), 'BTN'),
                        shadow_equity(0.5, BOARD_FLOOP, 'flop',
                                      {'checkers': [], 'pending': []}),
                        10.0, 0.0, 90.0, 'bet_25')
    assert lg.append(rec) is True
    rows = [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 1
    assert rows[0]['hand_id'] == 'H_1'
    assert rows[0]['experimental'] is True


def test_shadow_log_desactivado_no_escribe(tmp_path):
    p = tmp_path / 'shadow.jsonl'
    lg = ShadowLog(path=str(p), enabled=False)
    assert lg.append({'a': 1}) is False
    assert not p.exists()


def test_shadow_log_fallo_no_propaga(tmp_path):
    """Ruta no escribible: se pierde la fila, nunca el motor."""
    lg = ShadowLog(path=str(tmp_path / 'no' / 'dir' / 'x.jsonl'))
    assert lg.append({'a': 1}) is False


# --- LA GARANTÍA IMPORTANTE ---------------------------------------------

def test_shadow_no_altera_la_accion():
    """Con y sin contexto de jerarquía, la acción es idéntica.

    Es la garantía central del modo sombra. Si este test falla, el motor
    está calibrando con 36 manos por escenario.
    """
    jer = classify_villains(_acts(('UTG', 'x'), ('MP', 'b'), ('CO', 'x')),
                            'BTN', pending_positions=['SB'])
    jer['checkers'] = ['UTG', 'CO']
    base = dict(hero_codes=HERO, board_codes=BOARD_FLOOP, pot=25.0,
                to_call=0.0, stack=90.0, street='flop', position='BTN',
                villain_pos='MP', deadline_s=5.0, runout=False)
    sin = recommend(**base)
    con = recommend(**base, hierarchy=jer)
    assert con.action == sin.action
    assert con.value == pytest.approx(sin.value, abs=1e-12)
    # y la sombra sí calculó algo
    assert con.shadow is not None
    assert con.shadow['n_checker'] == 2
    assert con.shadow['equity_shadow'] < con.shadow['equity_main']


def test_shadow_sin_contexto_no_hay_registro():
    base = dict(hero_codes=HERO, board_codes=BOARD_FLOOP, pot=25.0,
                to_call=0.0, stack=90.0, street='flop', position='BTN',
                villain_pos='MP', deadline_s=5.0, runout=False)
    rec = recommend(**base)
    assert rec.shadow is None


def test_shadow_no_rompe_con_contexto_raro():
    """Un contexto malformado no puede tumbar la recomendación."""
    base = dict(hero_codes=HERO, board_codes=BOARD_FLOOP, pot=25.0,
                to_call=0.0, stack=90.0, street='flop', position='BTN',
                villain_pos='MP', deadline_s=5.0, runout=False)
    roto = {'main': None, 'checkers': None, 'pending': None}
    rec = recommend(**base, hierarchy=roto)
    assert rec.action in ('fold', 'check', 'call', 'bet_25', 'bet_50',
                          'bet_75', 'raise', 'all_in')