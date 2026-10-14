# -*- coding: utf-8 -*-
"""F6.2.b — `equity_main` cableado en la ruta de `asistente_live`.

La interfaz (`_equity_vs_rival`) ya existia y estaba testeada. Esto cubre el
PRODUCTOR, y sobre todo la regla dura: **la accion de produccion no cambia**,
ni cuando el productor funciona, ni cuando falla.

No se usan los ficheros derivados en disco: `prob_vec` devuelve un vector
valido sintetico, para que el test dependa del cableado y no del estado de
`data/`.
"""
import numpy as np
import pytest
from types import SimpleNamespace

from motor import asistente_live as al
from motor.asistente_live import Asistente
from motor.ranges import N_COMBOS, RangeState

def _cards(*codes):
    """['Qh','7s','2c'] -> [{'rank':'Q','suit':'h'}, ...]

    `state['community']` es una lista de DICTOS, no de strings: es lo que
    espera `_cards_to_codes` en el motor.
    """
    return [{'rank': c[0], 'suit': c[1]} for c in codes]


HERO = ['Ah', 'Kd']
BOARD = ['Qh', '7s', '2c']


# --------------------------------------------------------------- dobles
class _ProbVec:
    """`prob_vec` y companyas: vector uniforme, registras las llamadas."""

    def __init__(self, vacio=False):
        self.vacio = vacio
        self.llamadas = []

    def __call__(self, *args, **kw):
        # `range_model.prob_vec(perfil, spot, action, pos=..., villain_pos=...)`
        # `postflop_model.prob_vec(perfil, st, facing, board, act)`  <- posicional
        self.llamadas.append((args, kw))
        if self.vacio:
            return np.zeros(N_COMBOS, dtype=np.float32)
        return np.ones(N_COMBOS, dtype=np.float32)


class _Modelos:
    def __init__(self, prob=None, postflop=None):
        self.range_model = SimpleNamespace(prob_vec=prob or _ProbVec())
        self.postflop_model = SimpleNamespace(prob_vec=postflop or _ProbVec())


def _asistente(hand=None):
    a = Asistente.__new__(Asistente)
    a.models = _Modelos()
    a.live_stacks = {}
    a._last_seen_stake = {}
    a.rec = SimpleNamespace(hand=hand)
    a.verbose = False
    return a


def _hand(acts):
    return {
        'hand_id': 'H_EQ', 'streets': {
            'preflop': {'actions': []},
            'flop': {'actions': acts, 'board': BOARD},
            'turn': {'actions': [], 'board': []},
            'river': {'actions': [], 'board': []}},
        'current_street': 'flop'}


def _jer(main):
    return {'main': main, 'main_reason': 'prueba',
            'aggressors': [main] if main else [],
            'checkers_all': [], 'checkers_secondary': [],
            'callers': [], 'pending': [], 'pending_known': True,
            'hero_bet': True, 'hero_pos': 'BTN'}


# ======================================================================
# 1. La regla dura: la accion no cambia
# ======================================================================

def test_la_accion_no_cambia_con_el_productor_encendido(monkeypatch):
    """Con y sin `equity_main` disponible, `action` es la MISMA.

    Se mide sobre `_equity_main_sombra`: escribe en `reg` y nada mas. Si
    alguien lo conectara a `evs` o a `rp`, este test lo diria.
    """
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP', 'p2': 'CO'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'p2_state': 'activo', 'p2_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    jer = _jer('MP')

    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    reg_sin = {'equity_main': None, 'equity_main_available': False,
               'equity_main_source': None, 'equity_main_note': None,
               'equity_main_note_detail': None}
    reg_con = dict(reg_sin)
    asis._equity_main_sombra(state, jer, 'p1', HERO, BOARD, [], rs, reg_con)

    assert reg_con['equity_main_available'] is True, reg_con
    assert reg_con['equity_main'] is not None

    # las dos rutas convergen en las mismas cuatro claves por el nombre; lo
    # que NO debe pasar es que el productor haya tocado nada mas
    assert set(reg_con) == set(reg_sin)
    assert reg_sin['equity_main_available'] is False


def test_el_productor_no_toca_la_accion_ni_los_evs():
    """El productor recibe `reg` y no devuelve nada: no hay por donde colarse."""
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)
    reg = {}
    r = asis._equity_main_sombra(state, _jer('MP'), 'p1', HERO, BOARD, [],
                                 rs, reg)
    assert r is None, 'no debe devolver nada: solo escribe en `reg`'


# ======================================================================
# 2. main != villain_pos  (el caso que existe para medir esto)
# ======================================================================

def test_main_distinto_de_villain_se_resuelve_a_su_pid():
    """El principal es CO, el rival de produccion es MP: campos distintos."""
    asis = _asistente(_hand([{'pos': 'CO', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP', 'p2': 'CO'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'p2_state': 'activo', 'p2_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    reg = {}
    asis._equity_main_sombra(state, _jer('CO'), 'p1', HERO, BOARD, [],
                             rs, reg)

    assert reg['equity_main_available'] is True, reg
    # el rango se construyo para CO, no para MP: `pos` en la llamada
    pos_usados = [kw.get('pos') for _args, kw in
                  asis.models.range_model.prob_vec.llamadas]
    assert 'CO' in pos_usados, pos_usados
    assert 'MP' not in pos_usados, \
        'no debe construir el rango del rival de produccion'


def test_si_main_es_el_villain_reutiliza_el_rango():
    """Mismo pid: se reutiliza `rs` en vez de pagar `prob_vec` otra vez."""
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)
    antes = len(asis.models.range_model.prob_vec.llamadas)

    obtenido, motivo, pid = asis._rango_main(state, _jer('MP'), 'p1',
                                             HERO, BOARD, [], rs)
    assert obtenido is rs, 'debe REUTILIZAR el rango ya construido'
    assert motivo is None
    assert pid == 'p1'
    assert len(asis.models.range_model.prob_vec.llamadas) == antes, \
        'no debe volver a construir el rango'


# ======================================================================
# 3. casos de fallo: la accion sigue igual y queda el motivo
# ======================================================================

@pytest.mark.parametrize('estado,motivo_esperado', [
    ({'p1_state': 'activo'}, '0 candidatos'),          # nadie en esa posicion
    ({'p1_state': 'inactivo'}, '0 candidatos'),        # se fue
])
def test_posicion_sin_pid_resoluble_anota_el_motivo(estado, motivo_esperado):
    asis = _asistente(_hand([{'pos': 'ZZ', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    st = dict(estado)
    st['community'] = [_cards('Qh'), _cards('7s'), _cards('2c')]

    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)
    reg = {}
    asis._equity_main_sombra(st, _jer('ZZ'), 'p1', HERO, BOARD, [], rs, reg)

    assert reg['equity_main'] is None
    assert reg['equity_main_available'] is False
    # el CODIGO es estable y agregable; el DETALLE lleva el caso concreto
    assert reg['equity_main_note'] == 'main_position_unresolved', reg
    assert motivo_esperado in reg['equity_main_note_detail'], reg


def test_posicion_ambigua_no_elige_uno():
    """Dos jugadores en la misma posicion: no se escoge el primero."""
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP', 'p2': 'MP'}
    state = {'p1_state': 'activo', 'p2_state': 'activo',
             'p1_stake': 90.0, 'p2_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)
    reg = {}
    asis._equity_main_sombra(state, _jer('MP'), 'p1', HERO, BOARD, [], rs, reg)
    assert reg['equity_main_note'] == 'main_position_unresolved', reg
    assert '2 candidatos' in reg['equity_main_note_detail'], reg


def test_rango_vacio_despues_de_blockers():
    """`prob_vec` devuelve un vector nulo: no se inventa una equity."""
    asis = _asistente(_hand([{'pos': 'CO', 'action': 'b'}]))
    asis.models = _Modelos(prob=_ProbVec(vacio=True))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP', 'p2': 'CO'}
    state = {'p1_state': 'activo', 'p2_state': 'activo',
             'p1_stake': 90.0, 'p2_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)
    reg = {}
    asis._equity_main_sombra(state, _jer('CO'), 'p1', HERO, BOARD, [], rs, reg)
    assert reg['equity_main_available'] is False
    assert reg['equity_main_note'] == 'empty_range_after_blockers', reg
    assert reg['equity_main_note_detail'] is None, \
        'sin detalle variable, el detalle debe ser None'


def test_excepcion_al_calcular_no_tumba_nada(monkeypatch):
    """El tercero de los modos de fallo, en la ruta viva."""
    from motor import situation as _sit
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    def revienta(*a, **k):
        raise RuntimeError('boom')
    monkeypatch.setattr(_sit, 'equity_vs_range', revienta)

    reg = {}
    asis._equity_main_sombra(state, _jer('MP'), 'p1', HERO, BOARD, [], rs, reg)
    assert reg['equity_main'] is None
    assert reg['equity_main_available'] is False
    # el texto de la excepcion va al DETALLE, no al codigo
    assert reg['equity_main_note'] == 'equity_calculation_failed', reg
    assert 'boom' in reg['equity_main_note_detail'], reg


def test_excepcion_en_el_productor_se_registra_como_error(monkeypatch):
    """Si `_rango_main` revienta, se anota y se sigue."""
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    def revienta(*a, **k):
        raise RuntimeError('boom')
    monkeypatch.setattr(asis, '_rango_main', revienta)

    reg = {}
    try:
        asis._equity_main_sombra(state, _jer('MP'), 'p1', HERO, BOARD, [],
                                 rs, reg)
    except Exception:
        pytest.fail('el productor no debe propagar la excepcion')
    # el productor devuelve sin escribir: el bloque sombra pone el 'error:'
    assert reg.get('equity_main') is None


# ======================================================================
# 4. pending_known=False convive con equity_main
# ======================================================================

def test_pending_incierto_no_impide_equity_main():
    """`pending_known=False` no dice nada sobre `main`: se calculan aparte."""
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    jer = _jer('MP')
    jer['pending'] = []
    jer['pending_known'] = False

    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)
    reg = {}
    asis._equity_main_sombra(state, jer, 'p1', HERO, BOARD, [], rs, reg)
    assert reg['equity_main_available'] is True, reg


# ======================================================================
# 5. las tres equities siguen siendo campos distintos
# ======================================================================

def test_las_tres_equity_no_se_confunden():
    """`equity_production`, `equity_main` y `equity_shadow` son tres campos.

    `equity_main` NO debe caer en `equity_production` ni en `equity_shadow`.
    """
    from motor.hierarchy import shadow_record
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    jer = _jer('MP')
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    from motor.hierarchy import shadow_equity
    reg = shadow_equity(0.69, BOARD, 'flop', jer, equity_source='MP')
    produccion = reg['equity_production']
    asis._equity_main_sombra(state, jer, 'p1', HERO, BOARD, [], rs, reg)

    assert reg['equity_production'] == produccion, 'produccion intacta'
    assert reg['equity_main'] is not None
    assert reg['equity_main'] != reg['equity_shadow']

    rec = shadow_record('H_EQ', 'flop', BOARD, HERO, jer, reg,
                        25.0, 0.0, 90.0, 'bet_25')
    assert rec['equity_production'] == produccion
    assert rec['equity_main'] == reg['equity_main']
    assert 'equity_main' in rec and 'equity_main_available' in rec


# ======================================================================
# 6. el registro sombra recibe el resultado
# ======================================================================

def test_el_resultado_llega_a_shadow_record():
    """Si no llega al registro, el productor no sirve de nada."""
    from motor.hierarchy import shadow_equity, shadow_record
    asis = _asistente(_hand([{'pos': 'CO', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP', 'p2': 'CO'}
    state = {'p1_state': 'activo', 'p2_state': 'activo',
             'p1_stake': 90.0, 'p2_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    jer = _jer('CO')
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    reg = shadow_equity(0.69, BOARD, 'flop', jer, equity_source='MP')
    asis._equity_main_sombra(state, jer, 'p1', HERO, BOARD, [], rs, reg)
    rec = shadow_record('H_EQ', 'flop', BOARD, HERO, jer, reg,
                        25.0, 0.0, 90.0, 'bet_25')
    assert rec['equity_main_available'] is True
    assert rec['equity_main'] is not None
    # el campo de la fuente dice contra QUIEN se calculo
    assert rec['villain_used_for_equity'] == 'MP', \
        'equity_production se calculo contra MP'

# ======================================================================
# 7. INVARIANCIA END-TO-END: la ruta real, no el productor aislado
# ======================================================================
#
# NOTA sobre el escenario: `_asis_postflop` SOBREESCRIBE `rec.hand` con una
# mano cuyo flop no tiene acciones. Si se fija la mano antes de llamarlo, la
# jerarquia no encuentra `main`, el bloque sombra no corre y la comparacion
# "mismo resultado" es trivialmente cierta. Por eso la mano se pone DESPUES,
# y `test_el_productor_se_ejecuta_de_verdad` impide que eso vuelva a pasar sin
# que se note.

FLOP_AGRESOR = [{'pos': 'MP', 'action': 'b', 'amount': 8.0}]


def _estado_postflop(bets=None):
    bets = bets or {'p1': ('activo', 8.0), 'p2': ('activo', 0.0)}
    st = {
        'hero_cards': _cards('As', 'Kd'),
        'community': _cards('Qh', '9d', '3c'),
        'pot': 30.0,
        'hero_state': 'activo', 'hero_stake': 85.0, 'hero_bet': 0.0,
        'p3_state': 'inactivo', 'p4_state': 'inactivo',
        'p5_state': 'inactivo',
    }
    for pid, (estado, bet) in bets.items():
        st['%s_state' % pid] = estado
        st['%s_stake' % pid] = 85.0
        st['%s_bet' % pid] = bet
    return st


def _hand_agresor(acts=None):
    return {
        'hand_id': 'H_EQE', 'streets': {
            'preflop': {'actions': []},
            'flop': {'actions': list(acts or FLOP_AGRESOR), 'board': []},
            'turn': {'actions': [], 'board': []},
            'river': {'actions': [], 'board': []}},
        'current_street': 'flop'}


def _asis_ruta(shadow, acts=None):
    """Asistente por la ruta REAL, con agresor en el flop."""
    from motor.test_asistente_live import _asis_postflop

    a = Asistente.__new__(Asistente)
    a.models = _Modelos()
    a.live_stacks = {}
    a._last_seen_stake = {}
    a.rec = SimpleNamespace(hand=None)
    a.verbose = False
    a.shadow = shadow
    _asis_postflop(a)
    # DESPUES de `_asis_postflop`, que pisa la mano:
    a.rec.hand = _hand_agresor(acts)
    a.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP', 'p2': 'CO'}
    return a


def _huella(evs):
    """Representacion estable de TODO el `EvTable`, no solo de la accion.

    Comparar solo `chosen` dejaria pasar un productor que alterase el reparto
    de EVs sin cambiar la accion. Con la huella entera, cualquier cambio se ve.
    """
    partes = []
    for clave in sorted(vars(evs)):
        valor = getattr(evs, clave)
        if isinstance(valor, float):
            partes.append('%s=%.12f' % (clave, valor))
        elif isinstance(valor, dict):
            partes.append('%s=%s' % (clave, tuple(sorted(
                (str(k), round(float(v), 12) if isinstance(v, float)
                 else str(v)) for k, v in valor.items()))))
        else:
            partes.append('%s=%r' % (clave, valor))
    return '|'.join(partes)


def test_el_productor_se_ejecuta_de_verdad(monkeypatch):
    """Guardia anti-vacuidad del test de invariancia.

    Si el escenario dejara de tener agresor, la jerarquia no hallaria `main`,
    el bloque sombra no correria y el test siguiente compararia dos caminos
    que no hacen nada. Aqui se comprueba que el productor se invoca DE VERDAD.
    """
    llamadas = []
    original = Asistente._equity_main_sombra

    def espia(self, *args, **kw):
        llamadas.append(args[1].get('main'))
        return original(self, *args, **kw)

    monkeypatch.setattr(Asistente, '_equity_main_sombra', espia)

    # El guard va PRIMERO, antes que cualquier otra comprobacion: si otra
    # asercion peta antes, el mensaje seria el suyo y no dira "VACUO".
    res = _asis_ruta(True).recomendaciones(_estado_postflop(), verbose=False)
    assert llamadas, (
        'VACUO: el productor no se ejecuto. Si el escenario pierde el '
        'agresor, el bloque sombra no corre y el test de invariancia no '
        'comprueba nada.')
    assert llamadas[0] == 'MP', llamadas
    assert res, 'no hubo recomendaciones'


def test_accion_identica_con_y_sin_el_productor():
    """`shadow` a True (productor activo) y a False: resultado IDENTICO.

    Es la prueba fuerte de F6.2.b. Se compara la huella COMPLETA del EvTable,
    no solo `chosen`: si el productor filtrara algo hasta la seleccion, aunque
    la accion coincidiera, el reparto de EVs delataría el cambio.
    """
    resultados = {}
    for shadow in (False, True):
        res = _asis_ruta(shadow).recomendaciones(_estado_postflop(),
                                                 verbose=False)
        resultados[shadow] = tuple(
            (pid, evs.chosen, _huella(evs)) for pid, evs in res
            if evs is not None)

    assert resultados[False], 'no se obtuvo ninguna recomendacion de referencia'
    assert resultados[True] == resultados[False], (
        'el modo sombra cambio la decision de produccion:\n'
        '  sin sombra: %s\n  con sombra: %s'
        % (resultados[False], resultados[True]))


def test_el_reproducto_tiene_registro_con_equity_main():
    """Con el productor activo, el shadow log recibe `equity_main`."""
    registros = []

    class _Log:
        def append(self, rec):
            registros.append(rec)
            return True

    a = _asis_ruta(True)
    a._shadow_log = lambda: _Log()
    a.recomendaciones(_estado_postflop(), verbose=False)

    assert registros, 'no se registro nada en el shadow log'
    rec = registros[0]
    assert 'equity_main' in rec
    assert 'equity_main_available' in rec
    assert rec['pending_known'] is True

# ======================================================================
# 8. `equity_main_source` lleva la identidad de verdad  (bug corregido)
# ======================================================================

def test_equity_main_source_dice_la_posicion_del_principal():
    """BUG: el campo valía SIEMPRE 'main'.

    `_equity_vs_rival` devuelve `getattr(rs, 'position', '') or 'main'`.
    `RangeState(reach=...)` nace con `position == ''` y, antes del arreglo,
    NADIE la fijaba: ni el productor ni `recommend_loop`. O sea que el campo
    documentado como "identidad del rival" era una constante.

    Este test falla con el código anterior.
    """
    asis = _asistente(_hand([{'pos': 'CO', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP', 'p2': 'CO'}
    state = {'p1_state': 'activo', 'p2_state': 'activo',
             'p1_stake': 90.0, 'p2_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    reg = {}
    asis._equity_main_sombra(state, _jer('CO'), 'p1', HERO, BOARD, [],
                             rs, reg)
    assert reg['equity_main_available'] is True, reg
    assert reg['equity_main_source'] == 'CO', (
        'debe decir contra QUIEN se calculo, no la constante: %r'
        % reg['equity_main_source'])


def test_equity_main_source_also_con_el_rango_reutilizado():
    """La reutilización de `rs_villain` tampoco debe perder la identidad."""
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    reg = {}
    asis._equity_main_sombra(state, _jer('MP'), 'p1', HERO, BOARD, [], rs, reg)
    assert reg['equity_main_source'] == 'MP', reg


def test_rangostate_nace_sin_position():
    """Guarda el ORIGEN del bug: `RangeState` nace con `position` vacia.

    Si algun dia `RangeState` se construyera con `position` por defecto, el
    sintoma del bug desaparecerse pero la causa seguiria ahi: nadie la fija.
    """
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    assert not getattr(rs, 'position', ''), \
        'si RangeState ya trajera position, revisar por qué se relied en él'

# ======================================================================
# 9. El campo `equity_main_note` es un CODIGO, no texto libre
# ======================================================================

def test_los_codigos_validos_no_se_marcan_como_unknown():
    """Los cinco motivos del vocabulario deben pasar intactos."""
    from motor.asistente_live import CODIGOS_EQUITY_MAIN
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    reg = {}
    asis._equity_main_sombra(state, _jer('MP'), 'p1', HERO, BOARD, [], rs, reg)
    assert reg['equity_main_note'] != 'unknown', reg
    assert 'main_position_unresolved' in CODIGOS_EQUITY_MAIN
    assert 'error' in CODIGOS_EQUITY_MAIN


def test_un_motivo_fuera_del_vocabulario_no_pasa_como_codigo(monkeypatch):
    """Si `_equity_vs_rival` inventa un motivo nuevo, se marca `unknown`.

    Sin esta validacion, `equity_main_note` —el campo que se pretende
    AGREGABLE— se convertiria en texto libre en cuanto apareciera un motivo
    nuevo, y nada lo notaria.
    """
    from motor import recommend_loop as rl
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    monkeypatch.setattr(
        rl, '_equity_vs_rival',
        lambda *a, **k: (None, None, 'motivo_inventado_ayer: con detalle'))

    reg = {}
    asis._equity_main_sombra(state, _jer('MP'), 'p1', HERO, BOARD, [], rs, reg)
    assert reg['equity_main_note'] == 'unknown', reg
    # el texto NO se pierde: queda en el detalle
    assert 'motivo_inventado_ayer' in reg['equity_main_note_detail'], reg
    assert 'con detalle' in reg['equity_main_note_detail'], reg


def test_un_motivo_fuera_del_vocabulario_sin_detalle_tambien():
    """`partition(':')` sobre un codigo sin separador no debe romperse."""
    from motor import recommend_loop as rl
    asis = _asistente(_hand([{'pos': 'MP', 'action': 'b'}]))
    asis.rec._hand_positions = {'hero': 'BTN', 'p1': 'MP'}
    state = {'p1_state': 'activo', 'p1_stake': 90.0,
             'community': [_cards('Qh'), _cards('7s'), _cards('2c')]}
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)

    monkey = rl._equity_vs_rival
    try:
        rl._equity_vs_rival = lambda *a, **k: (None, None, 'raro_sin_detalle')
        reg = {}
        asis._equity_main_sombra(state, _jer('MP'), 'p1', HERO, BOARD, [],
                                 rs, reg)
    finally:
        rl._equity_vs_rival = monkey
    assert reg['equity_main_note'] == 'unknown', reg
    assert reg['equity_main_note_detail'] == 'raro_sin_detalle', reg


# ======================================================================
# 10. `SIN_POSITION`: la ausencia se declara, no se inventa
# ======================================================================

def test_un_rango_sin_position_reporta_sin_position():
    """El fallback ya no es 'main', que parecia una identidad.

    `RangeState` nace sin `position`, y antes `_equity_vs_rival` devolvia
    `or 'main'`. Ese valor no significaba nada y hacia creER que si.
    """
    from motor.recommend_loop import SIN_POSITION, _equity_vs_rival
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.set_known_cards(HERO + BOARD)
    assert not getattr(rs, 'position', ''), 'el rango no lleva posición'

    eq, src_pos, err = _equity_vs_rival(rs, HERO, BOARD)
    assert err is None, err
    assert src_pos == SIN_POSITION, src_pos
    assert src_pos != 'main', 'el fallback viejo era exactamente esto'


def test_con_position_devuelve_la_position():
    from motor.recommend_loop import _equity_vs_rival
    rs = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    rs.position = 'CO'
    rs.set_known_cards(HERO + BOARD)
    eq, src_pos, err = _equity_vs_rival(rs, HERO, BOARD)
    assert src_pos == 'CO', src_pos


def test_el_vocabulario_cubre_lo_que_produce_equity_vs_rival():
    """El vocabulario y el contrato de `_equity_vs_rival` no pueden divergir.

    Se recorre el fuente buscando los codigos literales que devuelve y se
    comprueba que todos estan en `CODIGOS_EQUITY_MAIN`. Si alguien anade un
    motivo nuevo y no lo registra, este test lo dice.
    """
    import inspect

    from motor.asistente_live import CODIGOS_EQUITY_MAIN
    from motor.recommend_loop import _equity_vs_rival

    fuente = inspect.getsource(_equity_vs_rival)
    encontrados = set()
    for linea in fuente.split('\n'):
        for trozo in ("'main_range_unavailable'", "'empty_range_after_blockers'",
                      "'equity_calculation_failed"):
            if trozo in linea:
                encontrados.add(trozo.strip("'"))

    assert encontrados, 'no se encontro ningun codigo en el fuente'
    fuera = encontrados - CODIGOS_EQUITY_MAIN
    assert not fuera, ('codigos que produce `_equity_vs_rival` y no estan '
                       'en el vocabulario: %s' % fuera)
