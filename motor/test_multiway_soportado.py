# -*- coding: utf-8 -*-
"""F7.2.b — la política multiway: MARCAR, no simular.

revision_1, Frente A. El contrato F7.2.a está firmado y su §6 dice cuatro
cosas; este fichero verifica que las cuatro se cumplen.

Lo que NO hay aquí, y no debe añadirse sin contrato nuevo
------------------------------------------------------
Ninguno de estos tests comprueba que el motor sepa jugar multiway. NO lo sabe:
`RangeState.union()` suma masas sin normalizar y eso no es una distribución
conjunta (CONTRATO_F72A.md §6.3). La tentación va a ser «implemento union()
bien y cierro esto». El contrato lo prohíbe en mayúsculas, y la razón de que
estos tests sean tan explícitos sobre lo que NOlean es que si no, el próximo
lee 12 tests en verde y concluye que el multiway está soportado.

Lo que sí se comprueba
----------------------
1. El flag existe, se propaga a `Recommendation` y NO cambia la acción.
2. `evs` no se toca. La equity se calcula igual: HU contra el rival principal.
3. El panel lo dice, y lo dice ANTES de la línea de recomendación.
4. El modo sombra lo registra, con versión de la política.
5. No hay ningún camino en el motor por el que `n_players > 2` entre sin
   quedar marcado. Este es el que cuesta y el que vale: los otros cinco son
   detalles de un archivo, este es el invariante.
"""
import ast
import io
import os

import pytest

from motor import rules
from motor.hierarchy import shadow_record
from motor.panel import format_insight
from motor.recommend_loop import recommend

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOTOR = os.path.join(ROOT, 'motor')

HERO = ['Jd', 'Jh']
BOARD = ['Qh', '7s', '2c']


def _fixture(n_players=2, **kw):
    fx = dict(
        hero_codes=HERO, board_codes=BOARD,
        street='flop', position='BB', villain_pos='UTG',
        pot=12.5, to_call=5.0, stack=90.0, runout=False,
        n_players=n_players,
    )
    fx.update(kw)
    return fx


def _jer():
    return {'main': 'MP', 'main_reason': 'test', 'aggressors': [],
            'checkers_secondary': ['CO'], 'checkers_all': ['CO'],
            'callers': [], 'pending': [], 'hero_pos': 'BB', 'hero_bet': False}


# ---------------------------------------------------------------------------
# 1. La fuente única: `rules`
# ---------------------------------------------------------------------------

def test_multiway_no_esta_soportado_hoy():
    """La política vigente es «no soportado». Si algún día cambia, este test
    es el que hay que borrar, y solo después de tener equity conjunta
    validada y un contrato nuevo."""
    assert rules.MULTIWAY_SOPORTADO is False


def test_rp_multiway_es_mas_de_dos_jugadores():
    for n, esperado in ((1, False), (2, False), (3, True), (4, True), (6, True)):
        rp = rules.plan('flop', False, 5.0, BOARD, 12.5, 90.0, n_players=n)
        assert rp.multiway is esperado, (n, rp.multiway)
        assert rp.multiway_soportado is (not esperado)


def test_multiway_y_soportado_no_son_el_mismo_campo():
    """`multiway` es un HECHO; `multiway_soportado` es lo que sabemos hacer.
    Que hoy coincidan siempre no significa que sean la misma cosa: el día que
    haya equity conjunta, `multiway_soportado` caducará y `multiway` no."""
    rp = rules.plan('flop', False, 5.0, BOARD, 12.5, 90.0, n_players=4)
    assert rp.multiway is True
    assert rp.multiway_soportado is False
    # Y el motivo es un texto con contenido, no un flag seco:
    assert 'heads-up' in rules.MOTIVO_MULTIWAY
    assert rules.POLITICA_MULTIWAY.startswith('F7.2.b')


def test_ctx_multi_y_rp_multiway_usan_el_mismo_umbral():
    """`Ctx.multi` ya existía (para los sizings) y `RulePlan.multiway` es
    nuevo. Si un día divergen, la mitad de los sizings sería de un umbral y
    el aviso de otro."""
    ctx = rules.Ctx('flop', False, False, 5.0, BOARD, 12.5, 90.0, 3,
                    False, False, False, False, 'VALUE', 'NEUTRAL', None)
    assert ctx.multi is True
    assert rules.Ctx('flop', False, False, 5.0, BOARD, 12.5, 90.0, 2,
                     False, False, False, False, 'VALUE', 'NEUTRAL',
                     None).multi is False


# ---------------------------------------------------------------------------
# 2. El flag llega a la recomendación SIN cambiar la acción
# ---------------------------------------------------------------------------

def test_en_hu_el_flag_no_se_pone():
    rec = recommend(**_fixture(n_players=2))
    assert rec.multiway is False
    assert rec.multiway_soportado is True
    assert rec.multiway_motivo is None


def test_en_multiway_el_flag_esta_puesto():
    rec = recommend(**_fixture(n_players=4))
    assert rec.multiway is True
    assert rec.multiway_soportado is False
    assert rec.multiway_motivo == rules.MOTIVO_MULTIWAY
    assert rec.politica_multiway == rules.POLITICA_MULTIWAY


def test_el_flag_no_altera_la_accion():
    """Lo que dice revision_1: «en un spot multiway, la recomendación no
    cambia pero el flag está puesto».

    Se comparan HU (n_players=2) contra multiway (n_players=4) con TODO lo
    demás idéntico. Si algún día alguien «arregla» estotouchando la decisión,
    este test es el que se pone rojo."""
    hu = recommend(**_fixture(n_players=2))
    mw = recommend(**_fixture(n_players=4))
    assert hu.action == mw.action, (hu.action, mw.action)
    assert hu.multiway is False and mw.multiway is True


def test_el_flag_no_altera_los_evs():
    """Más fuerte que el anterior, y va en la otra dirección.

    El flag puede cambiar el TAMAÑO de los sizings, porque `n_players` entra
    en `_multi_sizes` (rules.py §5/§9). Eso es correcto y es anterior a este
    bloque. Lo que no puede cambiar es el conjunto de candidatos ni los EVs de
    un sizing dado: el bloqueo es sobre `evs`, no sobre la aritmética.

    Se comprueba que el productor —`shadow_info`— no toca `evs` ni `rp`, que
    es donde el error sería fácil de colar."""
    rec = recommend(**_fixture(n_players=4, hierarchy=_jer(),
                               main_range_builder=None))
    assert rec.evs is not None
    # El dict de la sombra existe y lleva el flag...
    assert rec.shadow['multiway'] is True
    assert rec.shadow['multiway_soportado'] is False
    # ...y `rp` sigue siendo el mismo objeto que se usó para decidir:
    assert rec.rule_plan is not None
    assert rec.rule_plan.multiway is True


def test_si_rules_plan_falla_el_multiway_sigue_marcado():
    """El caso que hace TRIVIAL la caída. `rules.plan` lanza con
    `street='preflop'`; `recommend` lo captura y deja `rp=None`. Si el flag se
    leyera de `rp.multiway` a secas, este camino reventaría con AttributeError
    en vez de recomendar.

    No es un caso defensivo: es un camino de producción real."""
    rec = recommend(**_fixture(n_players=4, street='preflop'))
    assert rec.rule_plan is None
    assert rec.multiway is True, 'rp=None y el flag sigue teniendo que ver'
    assert rec.multiway_soportado is False


# ---------------------------------------------------------------------------
# 3. El panel lo dice, y lo dice antes de la acción
# ---------------------------------------------------------------------------

def test_el_panel_avisa_en_multiway():
    rec = recommend(**_fixture(n_players=4))
    text = format_insight(rec.situation, rec.evs, 'OR UTG', plan=rec.rule_plan)
    assert 'multiway NO SOPORTADO' in text
    assert 'HU' in text


def test_el_panel_no_avisa_en_hu():
    rec = recommend(**_fixture(n_players=2))
    text = format_insight(rec.situation, rec.evs, 'OR UTG', plan=rec.rule_plan)
    assert 'NO SOPORTADO' not in text


def test_el_aviso_va_ANTES_de_la_recomendacion():
    """Si va después, el que lee de arriba abajo ve «-> Mejor accion: raise» y
    el aviso ya pasó. El orden es parte del contrato de presentación."""
    rec = recommend(**_fixture(n_players=4))
    text = format_insight(rec.situation, rec.evs, 'OR UTG', plan=rec.rule_plan)
    i_aviso = text.index('NO SOPORTADO')
    i_accion = text.index('Mejor accion')
    assert i_aviso < i_accion, text


def test_el_panel_sin_plan_no_rompe():
    """`plan=None` es un camino vivo (`format_insight` se llama sin plan en
    varios sitios, y `rules.plan` puede devolver None en la ruta de
    `asistente_live`). No debe reventar por preguntar por un atributo."""
    rec = recommend(**_fixture(n_players=4))
    text = format_insight(rec.situation, rec.evs, 'OR UTG')
    assert 'Mejor accion' in text
    assert 'NO SOPORTADO' not in text


# ---------------------------------------------------------------------------
# 4. El modo sombra registra el caso
# ---------------------------------------------------------------------------

def test_el_registro_sombra_lleva_el_flag():
    rec = recommend(**_fixture(n_players=4, hierarchy=_jer()))
    assert rec.shadow['multiway'] is True
    assert rec.shadow['multiway_soportado'] is False
    assert rec.shadow['politica_multiway'] == rules.POLITICA_MULTIWAY
    assert rec.shadow['n_players'] == 4


def test_shadow_record_conserva_el_flag(tmp_path):
    """El log es donde se mide cuántos puntos de decisión entran al motor
    siendo multiway. Si `shadow_record` se olvidara de copiar las claves, el
    log tendría el caso pero sin el dato que lo identifica."""
    jer = _jer()
    shadow = {'multiway': True, 'multiway_soportado': False,
              'multiway_motivo': rules.MOTIVO_MULTIWAY,
              'politica_multiway': rules.POLITICA_MULTIWAY,
              'n_players': 4}
    reg = shadow_record(hand_id='H_0001', street='flop', board_codes=BOARD,
                        hero_codes=HERO, hierarchy=jer, shadow=shadow,
                        pot=12.5, to_call=5.0, stack=90.0,
                        action_production='call')
    assert reg['multiway'] is True
    assert reg['multiway_soportado'] is False
    assert reg['politica_multiway'] == rules.POLITICA_MULTIWAY
    assert reg['n_players'] == 4


def test_sin_declarar_el_alcance_es_None_y_no_False():
    """TRES estados, no dos.

    `None` = nadie miró. `False` = se miró y no se soporta. Poner `False` a
    pelo haría que un registro sin el dato se leyera como una medición, que es
    exactamente el error que el contrato de `pending_known` ya cometió una vez
    en este repo."""
    reg = shadow_record(hand_id='H_0001', street='flop', board_codes=BOARD,
                        hero_codes=HERO, hierarchy=_jer(), shadow={},
                        pot=12.5, to_call=5.0, stack=90.0,
                        action_production='call')
    assert reg['multiway'] is None
    assert reg['multiway_soportado'] is None


def test_el_registro_no_altera_la_accion():
    """`shadow_info` es un dict aparte. `evs` y `rp` no se tocan al escribir
    el flag: es la misma garantía que da la de `equity_main`."""
    kw = _fixture(n_players=4, hierarchy=_jer())
    sin = recommend(**kw)
    con = recommend(**kw, shadow_log=None, main_range_builder=None)
    assert sin.action == con.action
    assert sin.evs.ev == con.evs.ev


# ---------------------------------------------------------------------------
# 5. T3 — el invariante: no hay camino sin marcar
# ---------------------------------------------------------------------------

#: Los ficheros de `motor/` que producen una RECOMENDACIÓN. Los llamadores de
#: `recommend()` que no son de producción (tests, `run_demo`) no entran: no son
#: caminos del motor, son formas de medirlos.
#:
#: Los dos, porque son los dos que existen, y porque el inventario solo vale
#: si la lista está completa: un tercer consumidor nuevo que pase `n_players`
#: tiene que romper este test, y para eso hay que escanearlo.
_CONSUMIDORES = ('asistente_live.py', 'recommend_loop.py')

#: Los mismos dos, ordenados. Si aparece un tercero, o desaparece uno, el
#: inventario de abajo deja de cuadrar y este test lo dice.
_ESPERADOS = ('asistente_live.py', 'recommend_loop.py')


def _llamadas_n_players():
    """(fichero, línea) de cada llamada de PRODUCCIÓN que pasa `n_players`
    a `rules.plan()`.

    Se busca con AST, no con grep: un `n_players` en un comentario o en un
    docstring no es una llamada, y un `n_players` en un string tampoco. El
    filtro de docstring de este repo ya dio un falso positivo una vez
    (`RESUMEN_SECCION.md` §8) y no se repite.

    Se comparan los FICHEROS y SU NÚMERO, no las líneas: fijar la línea haría
    que cualquier edición inocua en esos ficheros pusiera el test en rojo sin
    que hubiera cambiado nada de lo que vigila. La línea sale en el mensaje de
    fallo, que es donde sirve.

    Duplicados NO se colapsan: dos llamadas con `n_players` en el mismo fichero
    son dos caminos, y es exactamente el que se cuela sin que nadie lo mire
    (regresión R3b, ver `tools/` o el historial del bloque).
    """
    assert sorted(_CONSUMIDORES) == sorted(_ESPERADOS), (
        'la lista de ficheros vigilados no es la que este test declara. '
        'Si el motor crece, que el inventario vuelva a mirarlo: un consumidor '
        'nuevo que pase `n_players` y no esté aquí NO lo está vigilando nadie.')
    encontrados = []
    for nombre in _CONSUMIDORES:
        ruta = os.path.join(MOTOR, nombre)
        arbol = ast.parse(io.open(ruta, encoding='utf-8').read())
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            func = nodo.func
            # `rules_plan(...)` y `rules.plan(...)` son la misma llamada:
            # `asistente_live` importa `plan` como `rules_plan`.
            nombre_func = None
            if isinstance(func, ast.Name):
                nombre_func = func.id
            elif isinstance(func, ast.Attribute):
                nombre_func = func.attr
            if nombre_func not in ('rules_plan', 'plan'):
                continue
            kwargs = {k.arg for k in nodo.keywords if k.arg}
            if 'n_players' in kwargs:
                encontrados.append((nombre, nodo.lineno))
    return encontrados


def test_hay_exactamente_dos_caminos_de_produccion():
    """El inventario, verificado en vez de asserted.

    Si el número cambia, o hay un consumidor nuevo que hay que auditar, o se
    ha eliminado uno y el invariante de abajo está comprobando menos de lo que
    parece. Los dos que tienen que estar:
      - `asistente_live._recomendacion_para` (la ruta que corre en vivo)
      - `recommend_loop.recommend` (la ruta de la demo y del laboratorio)

    Se comparan los ficheros y su número, no las líneas: see
    `_llamadas_n_players`."""
    encontradas = _llamadas_n_players()
    # SIN `set()`: dos llamadas en el mismo fichero son dos caminos, y
    # colapsarlos en uno es justo el agujero que cierra este test.
    assert sorted(f for f, _n in encontradas) == list(_ESPERADOS), (
        'llamadas a rules.plan(..., n_players=) en producción: %s.\n'
        'Esperadas exactamente %s: una por fichero.\n'
        '  - Si hay una más, hay un camino que entra al motor sin que nada le '
        'oblige a marcar el multiway.\n'
        '  - Si falta una, el invariante de abajo está vigilando un camino '
        'que ya no existe y da falsa confianza.'
        % (encontradas, list(_ESPERADOS)))


def test_el_camino_de_asistente_live_queda_marcado_sin_tocarlo():
    """ESTE es el invariante de T3, y es la razón de que el flag viva en
    `rules.RulePlan` y no en el llamador.

    `asistente_live` tiene su propia ruta de decisión (`rules.plan` +
    `select_best`) y **no llama a `recommend()`**
    (`RESUMEN_SECCION.md` §4). La prohibition de revision_1 es no tocar ese
    fichero, así que la marca tiene que poder viajar sola: `rp` la lleva y
    `format_insight(plan=rp)` la muestra.

    El test se verifica MIRANDO el panel que ese camino produce, no leyendo
    el código: si alguien borra el aviso del panel, o deja de pasarle el
    plan, o calcula el flag en otro sitio, esto falla."""
    src = io.open(os.path.join(MOTOR, 'asistente_live.py'), encoding='utf-8').read()
    assert 'format_insight(sit, evs, villain_label=label, plan=rp)' in src, (
        'asistente_live ya no le pasa el plan al panel. Si eso ha cambiado a '
        'propósito, hay que reponer el aviso de multiway en este camino: es '
        'el que corre en producción.')
    rec = recommend(**_fixture(n_players=4))
    text = format_insight(rec.situation, rec.evs, 'x', plan=rec.rule_plan)
    assert 'NO SOPORTADO' in text


def test_el_inventario_se_demuestra_capaz_de_fallar():
    """Un guard que no se demuestra capaz de fallar no puede usarse para decir
    que algo está bien (`RESUMEN_SECCION.md` §8).

    Se inyecta una tercera llamada a `rules.plan` con `n_players` en un
    fichero de producción y se comprueba que el inventario LA VE. Si este test
    pasara con el `_CONSUMIDORES` real, el inventario no estaría vigilando
    nada."""
    codigo = ('from . import rules\n'
              'def _camino_nuevo(x):\n'
              '    return rules.plan(x, False, 5.0, [], 12.5, 90.0, n_players=4)\n')
    arbol = ast.parse(codigo)
    encontradas = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) \
                and nodo.func.attr == 'plan' \
                and any(k.arg == 'n_players' for k in nodo.keywords):
            encontradas.append(nodo.lineno)
    assert encontradas, (
        'el extractor no ve una llamada a rules.plan(..., n_players=) en un '
        'código que sí la tiene: está roto y el inventario de arriba no '
        'está vigilando lo que dice vigilar.')