# -*- coding: utf-8 -*-
"""`revision_2` §1 y §3: el INFORME cuenta una version y el CALCULO
reciclaba otra. La divergencia entre ambos es la misma clase de error que
el resto de este bloque, y por eso tiene un test propio.
"""
import importlib.util
import os

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def ins():
    ruta = os.path.join(ROOT, 'tools', 'equity_preflop_observables.py')
    spec = importlib.util.spec_from_file_location('eqpobs', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------- la condicion, tal cual esta
def test_la_reutilizacion_exige_version_estimador_semilla_y_rango(ins):
    """El `if hid in cache and 'equity' in cache[hid]` de antes ignoraba
    todo eso. El informe exigia la VERSION y el calculo no, o sea que
    Informe y calculo podian mirar cosas distintas sin que se notara."""
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index('entrada = cache.get(hid)')
    cuerpo = texto[i:i + 1400]
    for condicion in ("entrada.get('version') == VERSION",
                      "entrada.get('estimador') == ESTIMADOR",
                      "entrada.get('semilla') == t['semilla']",
                      "entrada.get('n_combos') == N_COMBOS",
                      "entrada.get('villano') == t['villano']",
                      "entrada.get('spot') == t['spot']",
                      "entrada.get('hero') == t['hero']"):
        assert condicion in cuerpo, (
            'la reutilizacion de la AGREGADA tiene que exigir %s' % condicion)
    assert 'continue' in cuerpo, 'y saltar el calculo si todo coincide'


def test_el_antiguo_continue_que_ignoraba_todo_no_vuelve(ins):
    """El sintoma concreto: si vuelve, el informe miente sin querer."""
    texto = open(ins.__file__, encoding='utf-8').read()
    assert "if hid in cache and 'equity' in cache[hid]:" not in texto, (
        'vuelve el continue que ignora version, estimador, semilla y rango')


def test_lo_que_no_coincide_se_avisa(ins):
    """Recalcular en silencio es peor que recalcular: parece que se ha
    guardado."""
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index('entrada = cache.get(hid)')
    assert 'se recalcula' in texto[i:i + 1600], (
        'cuando la entrada no coincide hay que DECIRLO, no recalcular en '
        'silencio')


# ---------------------------------- la equity por combo NO lleva version
def test_la_equity_por_combo_no_necesita_version(ins):
    """`equity_preflop_contra_combo` es una funcion pura de las dos manos: no
    depende del estimador ni de la VERSION. Reutilizarla sin comprobar nada
    es CORRECTO, y exigirle la version seria tirar trabajo bueno."""
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index("clave = '%s|%d,%d'")
    cuerpo = texto[i:i + 500]
    assert "cache.get(clave)" in cuerpo
    assert 'version' not in cuerpo.split('nuevos += 1')[0].split(
        "clave = '%s|%d,%d'")[1], (
        'la equity por combo no se filtra por version: depende solo de las '
        'dos manos')
    assert 'es una funcion pura' in texto, (
        'y el motivo tiene que estar escrito, que es lo que lo justifica')


# ------------------------------------------------ el TOTAL de calculada
def test_el_total_se_cuenta_con_la_misma_funcion(ins):
    """`total_calc = 0` y nunca se incrementa: la fila TOTAL decia 0 con
    subtotales positivos. Un total mal hecho es peor que no tenerlo."""
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index('total_calc = calculadas_para(None)')
    assert i > 0, (
        'el TOTAL tiene que venir de calculadas_para(None), no de un 0 '
        'literal que nadie incrementa')
    i2 = texto.index('def calculadas_para(spot):')
    cuerpo = texto[i2:i2 + 800]
    assert 'if spot is not None and x[\'spot\'] != spot' in cuerpo, (
        'spot=None significa TOTAL, y tiene que usar el MISMO filtro')


def test_calculadas_para_none_da_el_total(ins):
    """Y que de verdad sume, que es lo que no hacia."""
    texto = open(ins.__file__, encoding='utf-8').read()
    assert 'total_calc = calculadas_para(None)' in texto
    assert 'total_calc += ' not in texto, (
        'ya no se acumula a mano: sale de la funcion, que es lo que evita '
        'que se olvide incrementar')


# ------------------------------------------------------ el id ausente
def test_el_id_ausente_no_es_un_keyerror_desnudo(ins):
    texto = open(ins.__file__, encoding='utf-8').read()
    i = texto.index('if hid not in por_id:')
    assert 'id_desconocido(hid, por_id)' in texto[i:i + 200], (
        'un ID ausente tiene que pasar por el diagnostico, no reventar')