"""Tests del asistente en vivo (helpers de perfil PEZ/TIBURON y parsing)."""
from types import SimpleNamespace

import pytest

from motor.asistente_live import (Asistente, _cards_to_codes, _hero_bet_facing,
                                  _hero_cards, _hero_is_initiator, _hero_oop,
                                  _is_default_names, _preflop_spot,
                                  _street_of, _villain_postflop_actions)


# ---------------------------------------------------------------------------
# utilidades de estado / cartas
# ---------------------------------------------------------------------------

def test_cards_to_codes_dict():
    cards = [{'rank': 'A', 'suit': 's'}, {'rank': 'K', 'suit': 'd'}]
    assert _cards_to_codes(cards) == ['As', 'Kd']


def test_cards_to_codes_str():
    assert _cards_to_codes('AsKd') == ['As', 'Kd']


def test_hero_cards_only_known():
    state = {'hero_cards': [{'rank': '9', 'suit': 'c'},
                            {'rank': '2', 'suit': 's'},
                            {'rank': 'Q', 'suit': 'h'}]}
    assert _hero_cards(state) == ['9c', '2s']


def test_street_of():
    assert _street_of(0) == 'preflop'
    assert _street_of(2) == 'preflop'
    assert _street_of(3) == 'flop'
    assert _street_of(4) == 'turn'
    assert _street_of(5) == 'river'


def test_hero_oop_por_orden_del_flop():
    acts = [{'pos': 'hero', 'action': 'x'},
            {'pos': 'p1', 'action': 'b'}]
    # el orden real del flop manda, aunque la posición diga lo contrario
    assert _hero_oop('BB', 'UTG', acts)
    assert _hero_oop('UTG', 'BB', acts)


def test_hero_oop_fallback_por_posicion():
    # Orden postflop: SB, BB, CO, MP, UTG, BTN (el BTN actúa último)
    assert _hero_oop('SB', 'BB', None)            # SB antes que BB → OOP
    assert _hero_oop('BB', 'UTG', None)           # BB antes que UTG → OOP
    assert not _hero_oop('UTG', 'BB', None)       # UTG IP
    assert not _hero_oop('UTG', 'MP', None)       # UTG actúa después → IP
    assert _hero_oop('CO', 'BTN', None)           # CO antes que BTN → OOP
    assert not _hero_oop('BTN', 'UTG', None)      # BTN actúa último → IP


def test_hero_oop_desconocido_false():
    assert _hero_oop('', '', None) is False
    assert _hero_oop(None, 'UTG', None) is False


def test_hero_is_initiator_posicion_mesa_real():
    # el recorder graba posiciones de mesa ('CO'), no 'hero'
    h = {'streets': {'preflop': {'actions': [
        {'pos': 'CO', 'action': 'r', 'amount': 2.5},
        {'pos': 'BTN', 'action': 'c', 'amount': 2.5}]}}}
    assert _hero_is_initiator(h, 'CO')          # hero abre → cbet
    assert not _hero_is_initiator(h, 'BTN')     # BTN solo paga → no cbet
    assert not _hero_is_initiator(h, '')        # pos desconocida → False
    assert _hero_is_initiator(None, 'CO') is False


def test_hero_oop_posicion_mesa_real():
    # el hero (CO) actúa tras SB: SB pasa primero → hero NO es OOP
    acts = [{'pos': 'SB', 'action': 'x', 'amount': 0.0},
            {'pos': 'CO', 'action': 'x', 'amount': 0.0}]
    assert not _hero_oop('CO', 'BTN', acts)
    # si el hero es quien actúa primero → OOP
    acts2 = [{'pos': 'CO', 'action': 'x', 'amount': 0.0}]
    assert _hero_oop('CO', 'BTN', acts2)


# ---------------------------------------------------------------------------
# clasificación en vivo PEZ/TIBURON
# ---------------------------------------------------------------------------

_DEFAULT = {'hero': 'Hero', 'p1': 'Player1', 'p2': 'Player2',
            'p3': 'Player3', 'p4': 'Player4', 'p5': 'Player5'}


def test_default_names_detectados():
    assert _is_default_names(dict(_DEFAULT))


def test_nombres_personalizados_no_se_pisan():
    names = dict(_DEFAULT)
    names['p2'] = 'Elyessi27'
    assert not _is_default_names(names)


def test_default_name_parcial_no_considerado_default():
    assert not _is_default_names({'hero': 'Hero'})

class _NoModels:
    range_model = None


@pytest.fixture
def asis():
    a = Asistente.__new__(Asistente)
    a.models = _NoModels()
    a.live_stacks = {}
    a._last_seen_stake = {}
    a.rec = SimpleNamespace(hand=None)
    a.verbose = False
    return a


def test_perfil_pez_bajo_50bb(asis):
    assert asis._perfil_for('p1', {'p1_stake': 49.9}) == 'PEZ'


def test_perfil_tiburon_sobre_50bb(asis):
    assert asis._perfil_for('p1', {'p1_stake': 50.0}) == 'TIBURON'


def test_perfil_sin_stack_default_tiburon(asis):
    assert asis._perfil_for('p1', {}) == 'TIBURON'


def test_perfil_media_sesion_baja_pez(asis):
    # stack actual alto (ganó el bote) pero media de la sesión < 50 → PEZ
    asis.live_stacks['p1'] = [40.0, 45.0, 30.0]
    assert asis._perfil_for('p1', {'p1_stake': 90.0}) == 'PEZ'


def test_perfil_media_sesion_alta_tiburon(asis):
    asis.live_stacks['p1'] = [60.0, 70.0]
    assert asis._perfil_for('p1', {'p1_stake': 48.0}) == 'TIBURON'


def test_perfil_con_solo_media_tiburon(asis):
    asis.live_stacks['p1'] = [60.0]
    assert asis._perfil_for('p1', {}) == 'TIBURON'


def test_observe_stacks_dedup(asis):
    state = {'p1_state': 'activo', 'p1_stake': 40.0,
             'hero_state': 'activo', 'hero_stake': 100.0}
    asis._observe_stacks(state)
    asis._observe_stacks(state)          # mismo stack: no se repite
    asis._observe_stacks({'p1_state': 'activo', 'p1_stake': 45.0,
                          'hero_state': 'activo', 'hero_stake': 100.0})
    assert asis.live_stacks['p1'] == [40.0, 45.0]
    assert asis.live_stacks['hero'] == [100.0]


def test_villain_name_usa_nombre_configurado(asis, monkeypatch):
    import sys
    class _M:
        PLAYER_NAMES = {'p2': 'Elyessi27'}
    monkeypatch.setitem(sys.modules, 'recorder_live', _M())
    assert asis._villain_name('p2') == 'Elyessi27'


# ---------------------------------------------------------------------------
# hero por nombre (Jarduan) o asiento 'hero' por defecto
# ---------------------------------------------------------------------------

def test_hero_pid_por_nombre_jarduan(asis, monkeypatch):
    import sys
    class _M:
        PLAYER_NAMES = {'hero': 'Juanmabm', 'p1': 'Jarduan',
                        'p2': 'P2', 'p3': 'P3', 'p4': 'P4', 'p5': 'P5'}
    monkeypatch.setitem(sys.modules, 'recorder_live', _M())
    asis.hero_name = 'Jarduan'
    assert asis._hero_pid() == 'p1'


def test_hero_pid_fallback_asiento_hero(asis, monkeypatch):
    import sys
    class _M:
        PLAYER_NAMES = {'hero': 'Otro', 'p1': 'Pepe',
                        'p2': 'P2', 'p3': 'P3', 'p4': 'P4', 'p5': 'P5'}
    monkeypatch.setitem(sys.modules, 'recorder_live', _M())
    asis.hero_name = 'Jarduan'
    assert asis._hero_pid() == 'hero'


def test_hero_pid_por_nombre_en_hero(asis, monkeypatch):
    import sys
    class _M:
        PLAYER_NAMES = {'hero': 'Jarduan', 'p1': 'P1',
                        'p2': 'P2', 'p3': 'P3', 'p4': 'P4', 'p5': 'P5'}
    monkeypatch.setitem(sys.modules, 'recorder_live', _M())
    asis.hero_name = 'Jarduan'
    assert asis._hero_pid() == 'hero'


def test_hero_pid_sin_modulo_fallback(asis, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'recorder_live', None)
    asis.hero_name = 'Jarduan'
    assert asis._hero_pid() == 'hero'


def test_hero_cards_of_lee_asiento_jarduan(asis, monkeypatch):
    import sys
    class _M:
        PLAYER_NAMES = {'hero': 'Juanmabm', 'p1': 'Jarduan',
                        'p2': 'P2', 'p3': 'P3', 'p4': 'P4', 'p5': 'P5'}
    monkeypatch.setitem(sys.modules, 'recorder_live', _M())
    asis.hero_name = 'Jarduan'
    state = {'p1_cards': [{'rank': 'A', 'suit': 's'},
                          {'rank': 'K', 'suit': 'd'}]}
    assert asis._hero_cards_of(state) == ['As', 'Kd']


def test_hero_cards_of_fallback_hero_cards(asis):
    asis.hero_name = 'Jarduan'
    state = {'hero_cards': [{'rank': '7', 'suit': 'c'},
                            {'rank': '2', 'suit': 's'}]}
    assert asis._hero_cards_of(state) == ['7c', '2s']


def test_hero_cards_of_asiento_hero(asis):
    asis.hero_name = 'Hero'
    state = {'hero_cards': [{'rank': 'Q', 'suit': 'h'},
                            {'rank': '3', 'suit': 'd'}]}
    assert asis._hero_cards_of(state) == ['Qh', '3d']


# ---------------------------------------------------------------------------
# turno del hero (botón o fallback lógico)
# ---------------------------------------------------------------------------

class _DummySM:
    def __init__(self, label=None):
        self.label = label

    def read(self, pil, pid):
        return self.label


class _DummyReader:
    def __init__(self, label=None):
        self.sm = _DummySM(label)


def _live_state(pot=3.0, hero='activo'):
    return {
        'pot': pot,
        'hero_state': hero,
        'hero_stake': 96.5,
        'hero_bet': 0.5,
        'p1_state': 'inactivo', 'p1_stake': None, 'p1_bet': 0.0,
        'p2_state': 'activo', 'p2_stake': 40.0, 'p2_bet': 1.0,
        'p3_state': 'inactivo', 'p3_stake': None, 'p3_bet': 0.0,
        'p4_state': 'inactivo', 'p4_stake': None, 'p4_bet': 0.0,
        'p5_state': 'inactivo', 'p5_stake': None, 'p5_bet': 0.0,
    }


def test_hero_act_con_boton_reconocido(asis):
    asis.reader = _DummyReader('igualar')
    assert asis._hero_act(_live_state(), None) is True


def test_hero_act_fallback_logico(asis):
    asis.reader = _DummyReader(None)      # botón NO reconocido
    assert asis._hero_act(_live_state(pot=3.0), None) is True


def test_hero_act_false_sin_pot(asis):
    asis.reader = _DummyReader(None)
    assert asis._hero_act(_live_state(pot=0.0), None) is False


def test_hero_act_false_si_fold(asis):
    asis.reader = _DummyReader('igualar')
    assert asis._hero_act(_live_state(pot=3.0, hero='inactivo'),
                          None) is False


def test_state_key_incluye_hand_id(asis):
    from types import SimpleNamespace
    st = _live_state()
    asis.rec = SimpleNamespace(hand=None)
    k1 = asis._state_key(st)
    asis.rec = SimpleNamespace(hand={'hand_id': 'H_42'})
    k2 = asis._state_key(st)
    assert k1 != k2        # mano nueva → siempre reinforma
    asis.rec = SimpleNamespace(hand={'hand_id': 'H_42'})
    assert asis._state_key(st) == k2


# ---------------------------------------------------------------------------
# recomendación PREFLOP (matrices data/preflop_matrices.json)
# ---------------------------------------------------------------------------

def _pf_state(btn='p3'):
    return {
        'pot': 1.5, 'btn': btn,
        'hero_state': 'activo', 'hero_stake': 90.4, 'hero_bet': 0.0,
        'hero_cards': [{'rank': '6', 'suit': 'c'}, {'rank': '4', 'suit': 's'}],
        'p1_state': 'activo', 'p1_stake': 109.5, 'p1_bet': 0.0,
        'p2_state': 'activo', 'p2_stake': 59.5, 'p2_bet': 0.0,
        'p3_state': 'activo', 'p3_stake': 101.5, 'p3_bet': 0.0,
        'p4_state': 'activo', 'p4_stake': 53.2, 'p4_bet': 0.5,
        'p5_state': 'activo', 'p5_stake': 59.0, 'p5_bet': 1.0,
    }


def test_recom_preflop_apertura_mano_debil(asis):
    evs = asis._recom_preflop(_pf_state(), ['6c', '4s'], 'UTG', 0.0, 1.5,
                              1.0, 'PEZ', 'x', None, False)
    assert evs is not None and evs.preflop
    assert evs.best()[0] == 'retirar'


def test_recom_preflop_apertura_mano_fuerte(asis):
    evs = asis._recom_preflop(_pf_state(), ['As', 'Ks'], 'BTN', 0.0, 1.5,
                              1.0, 'TIBURON', 'x', None, False)
    assert evs.best()[0] == 'subir'


def test_recom_preflop_facing_apertura_sube(asis):
    asis.rec.hand = {'hand_id': 'T', 'streets': {
        'preflop': {'actions': [
            {'pos': 'BB', 'action': 'b', 'amount': 1.0},
            {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        ]}}}
    evs = asis._recom_preflop(_pf_state(), ['As', 'Ks'], 'BB', 0.0, 2.0,
                              2.5, 'TIBURON', 'x', None, False)
    assert evs.best()[0] == 'subir'


def test_recom_preflop_bb_pasa_sin_raise(asis):
    evs = asis._recom_preflop(_pf_state(), ['6c', '4s'], 'BB', 1.0, 1.5,
                              0.0, 'PEZ', 'x', None, False)
    assert evs.best()[0] == 'pasar'


def _pf_hand(actions):
    asis = None  # placeholder; se asigna en cada test
    return {'hand_id': 'T', 'streets': {'preflop': {'actions': actions}}}


def test_recom_preflop_vs_limp_rol(asis):
    # UTG limpa → hero MP consulta la tabla ROL_MP (AKs: over-limp 100%)
    asis.rec.hand = _pf_hand([
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
    ])
    evs = asis._recom_preflop(_pf_state(), ['As', 'Ks'], 'MP', 0.0, 1.0,
                              1.0, 'PEZ', 'x', None, False)
    assert evs.best()[0] == 'igualar'
    assert evs.ev['igualar'] == 1.0


def test_recom_preflop_limp_bb_check_o_subir(asis):
    # Limp delante y hero en BB: ROL_BB 87o=0 → subir (iso); JTs=1 → pasar
    asis.rec.hand = _pf_hand([
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
    ])
    evs = asis._recom_preflop(_pf_state(), ['8c', '7h'], 'BB', 1.0, 1.0,
                              0.0, 'PEZ', 'x', None, False)
    assert evs.best()[0] == 'subir'
    evs2 = asis._recom_preflop(_pf_state(), ['Jc', 'Ts'], 'BB', 1.0, 1.0,
                               0.0, 'PEZ', 'x', None, False)
    assert evs2.best()[0] == 'pasar'


def test_recom_preflop_vs_5bet_call(asis):
    # 4 raises del rival → 5-bet: Call_5B_CO_vs_SB AKs = 1 → igualar
    asis.rec.hand = _pf_hand([
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'SB', 'action': 'r', 'amount': 8.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 20.0},
        {'pos': 'SB', 'action': 'r', 'amount': 65.0},
    ])
    evs = asis._recom_preflop(_pf_state(), ['As', 'Ks'], 'CO', 0.0, 5.0,
                              65.0, 'TIBURON', 'x', None, False)
    assert evs.best()[0] == 'igualar'


def test_recom_preflop_sb_no_pide_call_sin_tabla(asis):
    # SB vs apertura: NO existe tabla Call_OR_SB_* → no se inventa un call
    # (lo más apegado a las tablas): igualar queda en 0.
    asis.rec.hand = _pf_hand([
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'BTN', 'action': 'r', 'amount': 2.5},
    ])
    evs = asis._recom_preflop(_pf_state(), ['As', 'Ks'], 'SB', 0.0, 2.0,
                              2.5, 'TIBURON', 'x', None, False)
    assert evs is not None
    assert evs.ev['igualar'] == 0.0
    assert evs.best()[0] in ('subir', 'retirar')


def test_recom_preflop_bb_no_call_3bet(asis):
    # BB frente a un 3-bet: no existe Call_3B_BB_* (4B-or-fold) → igualar 0.
    asis.rec.hand = _pf_hand([
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 2.5},
        {'pos': 'SB', 'action': 'r', 'amount': 8.0},
    ])
    evs = asis._recom_preflop(_pf_state(), ['As', 'Ks'], 'BB', 1.0, 5.0,
                              8.0, 'TIBURON', 'x', None, False)
    assert evs is not None
    assert evs.ev['igualar'] == 0.0


def test_recom_preflop_suma_100(asis):
    # 44 vs apertura MP en BB: 3B=0.25 + Call_OR=1.0 (suma 1.25) → se escala
    # a 0.20/0.80 y la suma de acciones mostrada es exactamente 100%.
    asis.rec.hand = _pf_hand([
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'MP', 'action': 'r', 'amount': 2.5},
    ])
    evs = asis._recom_preflop(_pf_state(), ['4c', '4d'], 'BB', 1.0, 3.5,
                              2.5, 'TIBURON', 'x', None, False)
    assert evs is not None
    total = sum(evs.ev.values())
    assert abs(total - 1.0) < 1e-9, f'suma={total:.3f}'
    assert evs.ev['igualar'] == pytest.approx(0.8)
    assert evs.ev['subir'] == pytest.approx(0.2)
    assert evs.best()[0] == 'igualar'


# ---------------------------------------------------------------------------
# congelar la mano del hero: fuente de verdad = cartas al inicio de la mano
# ---------------------------------------------------------------------------

def test_recomendacion_usa_cartas_inicio_no_ocr():
    import recorder_live as rl
    from recorder_live import LiveRecorder
    from motor.asistente_live import Asistente

    a = Asistente.__new__(Asistente)
    a.models = None
    a.oracle = None
    a.rec = LiveRecorder()
    a.verbose = False
    a.live_stacks = {}
    a._last_seen_stake = {}
    a.runout = False
    a.hero_name = 'Jarduan'

    prev = dict(rl.PLAYER_NAMES)
    rl.PLAYER_NAMES['p4'] = 'Jarduan'
    try:
        # La mano registrada al inicio congela 'AhKd'; el OCR del frame
        # (p4_cards) está corrupto, como tras un fold.
        a.rec.hand = {
            'hand_id': 'H_X',
            'players': [
                {'_id': 'p4', 'pos': 'BTN', 'name': 'Jarduan',
                 'cards': 'AhKd', 'active': True},
                {'_id': 'p1', 'pos': 'UTG', 'name': 'P1',
                 'cards': '', 'active': True},
            ],
            'streets': {'preflop': {'actions': []}},
            'current_street': 'preflop',
        }
        a.rec._hand_positions = {'p4': 'BTN', 'p1': 'UTG'}
        state = {
            'hero_cards': [{'rank': '8', 'suit': 'c'}, {'rank': '4', 'suit': 's'}],
            'p4_cards': [{'rank': '2', 'suit': 'd'}, {'rank': '9', 'suit': 'h'}],
            'p4_state': 'activo', 'p4_stake': 90.0, 'p4_bet': 0.0,
            'hero_state': 'inactivo',
            'p1_state': 'activo', 'p1_stake': 100.0, 'p1_bet': 0.0,
            'p2_state': 'inactivo', 'p3_state': 'inactivo',
            'p5_state': 'inactivo',
            'pot': 1.5, 'btn': 'p3',
        }
        got = []
        res = a.recomendacion(state, verbose=False,
                              on_reco=lambda t, e, s, l: got.append((e, s)))
        assert res is not None
        assert got, 'on_reco no se invocó'
        assert got[0][1].hero_codes == ('Ah', 'Kd')
    finally:
        rl.PLAYER_NAMES.update(prev)
        rl.PLAYER_NAMES.pop('p4', None)
        for k in list(rl.PLAYER_NAMES):
            if k == 'p4':
                del rl.PLAYER_NAMES[k]


def test_recom_preflop_sorteo_ponderado(asis):
    # OR_CO 98s = 0.5 → subir/retirar 50/50; 401 muestras (seed distinta, stream
    # fijo y reproducible) deben reproducir ~los pesos, no el argmax seco.
    asis.rec.hand = None
    n = 401
    subir = sum(
        1 for s in range(n)
        if asis._recom_preflop(_pf_state(), ['9s', '8s'], 'CO', 0.0, 1.5,
                               1.0, 'PEZ', 'x', None, False,
                               seed=s).chosen == 'subir')
    frac = subir / n
    assert 0.40 <= frac <= 0.60, f'frac={frac:.3f}'


def test_recom_preflop_seed_determinista(asis):
    import random
    asis.rec.hand = None
    seq = [asis._recom_preflop(_pf_state(), ['9s', '8s'], 'CO', 0.0, 1.5,
                               1.0, 'PEZ', 'x', None, False,
                               seed=s).chosen for s in range(10)]
    seq2 = [asis._recom_preflop(_pf_state(), ['9s', '8s'], 'CO', 0.0, 1.5,
                                1.0, 'PEZ', 'x', None, False,
                                seed=s).chosen for s in range(10)]
    assert seq == seq2


def test_villain_id_mayor_stack_activo(asis):
    state = {
        'hero_state': 'activo',
        'p1_state': 'activo', 'p1_stake': 40.0,
        'p2_state': 'activo', 'p2_stake': 90.0,
        'p3_state': 'inactivo', 'p3_stake': 200.0,
    }
    assert asis._villain_id(state) == 'p2'


def test_villain_id_elige_agresor_cuando_enfrenta_apuesta(asis):
    # p4 (BTN corto) apostó 5.0 y p2 (pila grande pasiva) solo igualó:
    # el rival para recomendar es el agresor p4, no el de mayor stack.
    state = {
        'hero_state': 'activo', 'hero_bet': 3.1,
        'p2_state': 'activo', 'p2_stake': 112.0, 'p2_bet': 3.1,
        'p4_state': 'activo', 'p4_stake': 38.2, 'p4_bet': 8.1,
    }
    assert asis._villain_id(state) == 'p4'


def test_villain_id_mayor_stack_si_hero_apuesta(asis):
    # el hero ya pagó todo: nadie le debe → rival principal = mayor stack
    state = {
        'hero_state': 'activo', 'hero_bet': 8.1,
        'p2_state': 'activo', 'p2_stake': 112.0, 'p2_bet': 8.1,
        'p4_state': 'activo', 'p4_stake': 38.2, 'p4_bet': 8.1,
    }
    assert asis._villain_id(state) == 'p2'


def test_villain_id_none_sin_rivales(asis):
    state = {'hero_state': 'activo',
             'p1_state': 'inactivo', 'p2_state': 'inactivo',
             'p3_state': 'inactivo', 'p4_state': 'inactivo',
             'p5_state': 'inactivo'}
    assert asis._villain_id(state) is None


# ---------------------------------------------------------------------------
# rango inicial del rival según su preflop
# ---------------------------------------------------------------------------

def _hand_with_preflop(actions):
    return {'streets': {'preflop': {'actions': actions}}}


def test_preflop_spot_open():
    h = _hand_with_preflop([{'pos': 'UTG', 'action': 'b', 'amount': 3.0}])
    assert _preflop_spot(h, 'UTG') == ('no_raise', 'open')


def test_preflop_spot_call():
    h = _hand_with_preflop([{'pos': 'MP', 'action': 'c', 'amount': 1.0}])
    assert _preflop_spot(h, 'MP') == ('facing_open', 'call_open')


def test_preflop_spot_3bet():
    h = _hand_with_preflop([{'pos': 'CO', 'action': 'r', 'amount': 9.0}])
    assert _preflop_spot(h, 'CO') == ('facing_open', '3bet')


def test_preflop_spot_bb_check():
    h = _hand_with_preflop([{'pos': 'BB', 'action': 'x', 'amount': 0.0}])
    assert _preflop_spot(h, 'BB') == ('no_raise', 'limp')


def test_preflop_spot_sin_accion_open():
    assert _preflop_spot(None, 'UTG') == ('no_raise', 'open')


# ---------------------------------------------------------------------------
# acciones postflop del rival → (street, facing, action)
# ---------------------------------------------------------------------------

def _hand(values):
    return {'streets': values}


def test_villain_postflop_flop_cbet():
    h = _hand({'preflop': {'actions': [{'pos': 'BTN', 'action': 'b',
                                        'amount': 2.0}]},
               'flop': {'actions': [{'pos': 'BTN', 'action': 'b',
                                     'amount': 3.0},
                                    {'pos': 'BB', 'action': 'c',
                                     'amount': 3.0}]}})
    acts = _villain_postflop_actions(h, 'BB')
    assert acts == [('flop', 'cbet', 'c', '')]


def test_villain_postflop_multis_turn():
    h = _hand({'preflop': {'actions': [{'pos': 'UTG', 'action': 'b',
                                        'amount': 2.0}]},
               'flop': {'actions': [{'pos': 'UTG', 'action': 'b',
                                      'amount': 3.0}]},
               'turn': {'actions': [{'pos': 'UTG', 'action': 'b',
                                      'amount': 6.0},
                                     {'pos': 'MP', 'action': 'c',
                                      'amount': 6.0}]}})
    acts = _villain_postflop_actions(h, 'MP')
    assert acts == [('turn', 'barrel', 'c', '')]


def test_villain_postflop_con_facing_raise():
    h = _hand({'preflop': {'actions': [{'pos': 'BB', 'action': 'b',
                                        'amount': 1.0}]},
               'flop': {'actions': [{'pos': 'MP', 'action': 'b',
                                     'amount': 3.0},
                                    {'pos': 'BB', 'action': 'r',
                                     'amount': 9.0}]}})
    acts = _villain_postflop_actions(h, 'BB')
    # el rival (agresor preflop) vio el DONK de MP (bote subido por BB) y subió
    assert acts == [('flop', 'donk', 'r', '')]


def test_villain_postflop_sin_mano():
    assert _villain_postflop_actions(None, 'MP') == []


def test_villain_postflop_lead_donk_bote_subido():
    h = _hand({'preflop': {'actions': [{'pos': 'CO', 'action': 'b',
                                        'amount': 2.5}]},
               'flop': {'actions': [{'pos': 'MP', 'action': 'b', 'amount': 3.0},
                                     {'pos': 'CO', 'action': 'c', 'amount': 3.0}]}})
    acts = _villain_postflop_actions(h, 'CO')
    # MP lideró el flop sin ser agresor preflop, en bote subido → DONK
    assert acts == [('flop', 'donk', 'c', '')]


def test_villain_postflop_lead_propia_facing_none():
    h = _hand({'preflop': {'actions': [{'pos': 'CO', 'action': 'b',
                                        'amount': 2.5}]},
               'flop': {'actions': [{'pos': 'MP', 'action': 'b', 'amount': 3.0},
                                     {'pos': 'CO', 'action': 'f', 'amount': 0.0}],
                        'board': ['Qh', '7s', '2c']},
               'turn': {'actions': [{'pos': 'MP', 'action': 'b', 'amount': 6.0}],
                        'board': ['3d']}})
    acts = _villain_postflop_actions(h, 'MP')
    # la APUESTA PROPIA del rival (lead) siempre etiqueta facing 'none'
    # (paridad con observations), nunca ''
    assert acts == [('flop', 'none', 'b', 'Qh,7s,2c'), ('turn', 'none', 'b', '3d')]


def test_villain_postflop_limp_no_donk():
    h = _hand({'preflop': {'actions': [{'pos': 'UTG', 'action': 'x',
                                        'amount': 0.0},
                                        {'pos': 'BB', 'action': 'x',
                                         'amount': 0.0}]},
               'flop': {'actions': [{'pos': 'MP', 'action': 'b', 'amount': 2.0},
                                     {'pos': 'UTG', 'action': 'c', 'amount': 2.0}]}})
    # bote LIMPEADO: el lead de MP es un 'bet' genérico, NO un donk
    assert _villain_postflop_actions(h, 'UTG') == [('flop', 'bet', 'c', '')]


def test_hero_bet_facing_donk():
    # hero lidera sin ser iniciador, en bote subido (flop/turn) → el rival
    # ve un 'donk'; en bote limpeado sigue siendo 'bet'
    assert _hero_bet_facing('flop', False, True) == 'donk'
    assert _hero_bet_facing('turn', False, True) == 'donk'
    assert _hero_bet_facing('flop', True, True) == 'cbet'
    assert _hero_bet_facing('turn', True, True) == 'barrel'
    assert _hero_bet_facing('flop', False, False) == 'bet'
    assert _hero_bet_facing('river', False, True) == 'bet'


def _obs_pairs(hand, pos):
    from motor.observations import extract_hand
    out = []
    for o in extract_hand(hand):
        if o.pos != pos or o.street == 'preflop' or o.action == 'x':
            continue
        # Usar el board de la calle del hand, no el acumulado
        streets = hand.get('streets', {})
        board_list = streets.get(o.street, {}).get('board', []) or []
        board_str = ','.join(str(c) for c in board_list)
        out.append((o.street, o.facing, o.action, board_str))
    return out


def test_paridad_train_serve_labels_donk():
    # MISMA mano → observations (train) y _villain_postflop_actions (serve)
    # etiquetan el fighting del rival con las mismas celdas (anti-skew).
    hand = {
        'hand_id': 'H_PARR',
        'players': [{'pos': 'CO', 'name': 'CO', 'cards': ''},
                    {'pos': 'MP', 'name': 'MP', 'cards': ''},
                    {'pos': 'BB', 'name': 'BB', 'cards': ''}],
        'streets': {
            'preflop': {'actions': [
                {'pos': 'BB', 'action': 'b', 'amount': 1.0},
                {'pos': 'MP', 'action': 'c', 'amount': 1.0},
                {'pos': 'CO', 'action': 'r', 'amount': 3.5}]},
            'flop': {'actions': [
                {'pos': 'BB', 'action': 'x', 'amount': 0.0},
                {'pos': 'MP', 'action': 'b', 'amount': 4.0},
                {'pos': 'CO', 'action': 'c', 'amount': 4.0}],
                'board': ['Qh', '7s', '2c']},
            'turn': {'actions': [
                {'pos': 'MP', 'action': 'b', 'amount': 9.0},
                {'pos': 'BB', 'action': 'f', 'amount': 0.0},
                {'pos': 'CO', 'action': 'r', 'amount': 22.0}],
                'board': ['3d']},
        },
    }
    for vpos in ('MP', 'CO', 'BB'):
        assert _obs_pairs(hand, vpos) == _villain_postflop_actions(hand, vpos)


# ---------------------------------------------------------------------------
# reglas postflop en la recomendación (pegar.txt §21/§22)
# ---------------------------------------------------------------------------

def test_recomendacion_postflop_filtra_por_reglas():
    import numpy as np
    from recorder_live import LiveRecorder
    from motor.asistente_live import Asistente

    class _Rng:
        def prob_vec(self, perfil, spot, action, pos=None):
            return np.ones(1326, dtype=np.float32)

    class _Ora:
        def p_action(self, *a, **k):
            return None

    class _Pf:
        _oracle = _Ora()

        def prob_vec(self, *a, **k):
            return np.ones(1326, dtype=np.float32)

    a = Asistente.__new__(Asistente)
    a.models = SimpleNamespace(range_model=_Rng(), postflop_model=_Pf())
    a.oracle = _Ora()
    a.rec = LiveRecorder()
    a.verbose = False
    a.live_stacks = {}
    a._last_seen_stake = {}
    a.runout = False

    # Mano: hero abre preflop (iniciador §3); p1 solo iguala y checkea el
    # flop → la regla deja cbet (check/bet_25 en board Q72r, DRY) en vez de
    # evaluar todas las apuestas.
    a.rec.hand = {
        'hand_id': 'H_X', 'btn_player': 'p3',
        'streets': {
            'preflop': {'actions': [
                {'pos': 'hero', 'action': 'b', 'amount': 3.0},
                {'pos': 'p1', 'action': 'c', 'amount': 3.0}]},
            'flop': {'actions': []},
            'turn': {'actions': []},
            'river': {'actions': []},
        },
        'current_street': 'flop',
    }
    a.rec._hand_positions = {'hero': 'BB', 'p1': 'UTG',
                             'p2': 'BTN', 'p3': 'BTN', 'p4': 'BTN', 'p5': 'BTN'}
    state = {
        'hero_cards': [{'rank': 'A', 'suit': 's'}, {'rank': 'K', 'suit': 'd'}],
        'community': [{'rank': 'Q', 'suit': 'h'},
                      {'rank': '7', 'suit': 's'}, {'rank': '2', 'suit': 'c'}],
        'pot': 12.5,
        'hero_state': 'activo', 'hero_stake': 85.0, 'hero_bet': 1.0,
        'p1_state': 'activo', 'p1_stake': 90.0, 'p1_bet': 0.0,
        'p2_state': 'inactivo', 'p3_state': 'inactivo',
        'p4_state': 'inactivo', 'p5_state': 'inactivo',
    }
    evs = a.recomendacion(state, verbose=False)
    assert evs is not None
    assert evs.spot == 'cbet'
    assert 'bet_25' in evs.ev
    assert 'bet_50' not in evs.ev          # §21: solo candidatas
    assert 'bet_66' not in evs.ev
    assert 'all_in' not in evs.ev
    assert evs.chosen in ('check', 'bet_25')
    assert 'c-bet' in getattr(evs, 'rule_note', '')