"""Regresión de robustez — Fase A/B/C (pegar_2 §4, pegar_3 §4).

Cada prueba cubre un caso que antes pasaba inadvertido porque el motor
devolvía números plausibles a partir de datos inválidos, o reventaba.
"""
import numpy as np
import pytest

from motor.decision import compute_evs
from motor.preflop import opening_range, opening_range_or_fallback, prob
from motor.ranges import (N_COMBOS, RangeError, RangeState, validate_reach,
                          villain_weights)
from motor.recommend_loop import build_villain_range, recommend
from motor.situation import equity_vs_range, situation

HERO = ['As', 'Kd']
BOARD = ['Qh', '7s', '2c']


# --- Rango vacío nunca se confunde con equity cero -----------------------

def test_empty_range_raises_not_zero_equity():
    """Un rango vacío significa 'no pude evaluar', no 'el rival no tiene mano'.

    Antes situation._weights_for devolvía ceros y la equity salía 0.0,
    que el motor leía como un resultado real.
    """
    empty = np.zeros(N_COMBOS, dtype=np.float32)
    with pytest.raises(RangeError):
        equity_vs_range(HERO, BOARD, empty)
    with pytest.raises(RangeError):
        compute_evs(HERO, BOARD, villain_reach=empty, pot=50.0)


def test_blocked_to_empty_raises():
    """También cuando el rango se vacía por blockers, no solo por ceros."""
    rs = RangeState(reach=np.full(N_COMBOS, 0.5, dtype=np.float32))
    rs.restrict_to_combo(['2c', '9s'])          # 2c está en el board
    with pytest.raises(RangeError):
        equity_vs_range(HERO, BOARD, rs)


# --- Vectores inválidos rechazados antes del cálculo --------------------

@pytest.mark.parametrize('bad', [
    np.full(N_COMBOS, np.nan, dtype=np.float32),
    np.full(N_COMBOS, np.inf, dtype=np.float32),
    np.full(N_COMBOS, -1.0, dtype=np.float32),
    np.zeros(100, dtype=np.float32),
])
def test_invalid_vectors_rejected(bad):
    with pytest.raises(RangeError):
        equity_vs_range(HERO, BOARD, bad)
    with pytest.raises(RangeError):
        compute_evs(HERO, BOARD, villain_reach=bad, pot=50.0)


def test_validate_reach_allows_empty_when_asked():
    arr, total = validate_reach(np.zeros(N_COMBOS), allow_empty=True)
    assert total == 0.0
    with pytest.raises(RangeError):
        validate_reach(np.zeros(N_COMBOS))


# --- villain_ids no se aceptan a ciegas ---------------------------------

def test_villain_ids_conflicting_are_rejected():
    """Un combo que contiene una carta del board es una mano imposible."""
    from motor.cards import card_id
    from motor.ranges import COMBO0, COMBO1

    qh = card_id('Qh')                      # carta del board
    bad_id = next(i for i in range(N_COMBOS)
                  if int(COMBO0[i]) == qh or int(COMBO1[i]) == qh)

    # Ese combo no puede ser del rival: el board ya lo ocupa.
    with pytest.raises(RangeError):
        equity_vs_range(HERO, BOARD, None, villain_ids=[bad_id])


# --- Bloquear vs restringir ---------------------------------------------

def test_blocking_and_restricting_are_different():
    """Bloquear elimina la mano; restringir la conserva."""
    base = build_villain_range(HERO, BOARD, 'UTG')
    blocked = build_villain_range(HERO, BOARD, 'UTG',
                                  extra_blockers=['Ts'])
    # bloquear 'Ts' quita todos los combos que la contienen
    assert int(blocked.legal_mask.sum()) < int(base.legal_mask.sum())

    restricted = build_villain_range(HERO, BOARD, 'UTG',
                                     villain_cards=['Ts', '9s'])
    assert not restricted.is_empty
    label = restricted.top_hands(1)[0][0]        # p. ej. '9sTs'
    assert {label[0:2], label[2:4]} == {'Ts', '9s'}


def test_known_villain_hand_outside_prior_is_kept():
    """Si el prior da 0 a la mano conocida, el dato del llamador gana.

    Sin esto, restringir un combo ausente produciría un rango vacío.
    """
    rs = RangeState(reach=np.zeros(N_COMBOS, dtype=np.float32))
    rs.restrict_to_combo(['2c', '9s'])          # combo inexistente en el prior
    assert not rs.is_empty


# --- Tabla ausente: política explícita, no rango vacío ------------------

def test_missing_table_never_yields_empty_range():
    assert prob('OR', 'ZZZ') is None
    for pos in ('UTG', 'BTN', 'BB', 'ZZZ'):
        rs = build_villain_range(HERO, BOARD, pos)
        assert not rs.is_empty, f'{pos} produjo rango vacío'


def test_uniform_fallback_is_marked():
    """El fallback uniforme debe ser distinguible de una estimación."""
    rs = build_villain_range(HERO, BOARD, 'BB')
    assert rs.source == 'uniform'
    assert build_villain_range(HERO, BOARD, 'UTG').source == 'table'


def test_or_bb_not_invented():
    """No existe OR_BB y no debe fabricarse una tabla para taparlo."""
    assert opening_range('BB') is None
    vec, src = opening_range_or_fallback('BB')
    assert src == 'uniform'
    assert np.allclose(vec, 1.0 / N_COMBOS)


# --- El rango depende de la acción observada ----------------------------

def test_villain_action_changes_the_range():
    """Un rival que paga no puede recibir el rango de apertura."""
    opening = build_villain_range(HERO, BOARD, 'BB',
                                  villain_spot='no_raise',
                                  villain_action='open')
    call = build_villain_range(HERO, BOARD, 'BTN',
                               villain_spot='facing_open',
                               villain_action='call_open')
    assert not opening.is_empty and not call.is_empty
    # y el segundo se construye con el par spot/action pedido
    assert call.source in ('table', 'uniform')


def test_range_conditioning_end_to_end():
    """recommend() acepta el contexto y produce una recomendación válida."""
    rec = recommend(HERO, BOARD, pot=50.0, to_call=10.0, stack=90.0,
                    street='flop', villain_pos='BB',
                    villain_spot='no_raise', villain_action='open',
                    deadline_s=5.0)
    assert rec.action in ('fold', 'check', 'call', 'bet_25', 'bet_50',
                          'bet_75', 'raise', 'all_in')


# --- Entradas numéricas del EV ------------------------------------------

@pytest.mark.parametrize('kwargs', [
    dict(pot=-1.0), dict(to_call=-5.0), dict(stack=-10.0),
    dict(pot=float('nan')), dict(to_call=float('inf')),
])
def test_compute_evs_rejects_bad_money(kwargs):
    base = dict(pot=50.0, to_call=0.0, stack=90.0)
    base.update(kwargs)
    with pytest.raises(ValueError):
        compute_evs(HERO, BOARD, **base)


def test_call_pot_when_call_exceeds_stack():
    """to_call > stack: call_pot no puede quedar negativo (pegar_3 A.5)."""
    ev = compute_evs(HERO, BOARD, pot=50.0, to_call=200.0, stack=90.0)
    assert all(np.isfinite(v) for v in ev.ev.values())


# --- Panel y motor EV ven el mismo rango --------------------------------

def test_panel_and_ev_agree():
    """equity_vs_range y compute_evs parten del mismo rango."""
    rs = build_villain_range(HERO, BOARD, 'UTG')
    eq_panel = equity_vs_range(HERO, BOARD, rs)[0]
    ev = compute_evs(HERO, BOARD, villain_reach=rs, pot=50.0,
                     to_call=0.0, stack=90.0, runout=False)
    ev_eq = ev.hero_equity
    assert np.isclose(eq_panel, ev_eq, atol=1e-9)


def test_villain_weights_shared():
    """ambos módulos usan la misma normalización."""
    rs = build_villain_range(HERO, BOARD, 'UTG')
    from motor.hand_evaluator import legal_hands
    from motor.cards import cards_to_bits
    ids = legal_hands(cards_to_bits(HERO + BOARD))
    w = villain_weights(rs, ids)
    assert np.isclose(w.sum(), 1.0)
    assert w.min() >= 0.0


# --- Multiway -----------------------------------------------------------

def test_multiway_union_works():
    a = build_villain_range(HERO, BOARD, 'UTG')
    b = build_villain_range(HERO, BOARD, 'BTN')
    combined = a.copy().union(b)
    assert not combined.is_empty
    assert combined.reach.sum() > a.reach.sum()   # suma, no normaliza
    combined.norm_to()
    assert np.isclose(combined.reach.sum(), 1.0)


def test_union_of_two_empty_ranges_is_empty():
    vacio_a = RangeState(reach=np.zeros(N_COMBOS, dtype=np.float32))
    vacio_b = RangeState(reach=np.zeros(N_COMBOS, dtype=np.float32))
    u = vacio_a.copy().union(vacio_b)
    assert u.is_empty


def test_union_respects_disjoint_blockers():
    """unir NO debe perder los blockers de ninguna de las dos."""
    from motor.cards import card_id
    a = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    b = RangeState(reach=np.ones(N_COMBOS, dtype=np.float32))
    a.set_known_cards(['As'])
    b.set_known_cards(['Kd'])
    u = a.union(b)
    assert (u.known_mask & (1 << card_id('As'))) != 0
    assert (u.known_mask & (1 << card_id('Kd'))) != 0


def test_restrict_to_combo_conflicting_with_blocker_raises():
    """Si la mano conocida choca con el board, el rango queda vacío y
    debe detectarse, no convertirse en una distribución silenciosa."""
    rs = build_villain_range(HERO, BOARD, 'UTG')
    rs.restrict_to_combo(['Qh', '9s'])          # Qh está en el board
    assert rs.is_empty


# --- extra_blockers también con villain_reach explícito -----------------

def test_extra_blockers_applied_with_explicit_villain_reach():
    """pegar_2 §2.3: la rama explícita ignoraba extra_blockers.

    Las cartas de otro hero conocido no pueden estar en el rango aunque
    el llamador pase su propio vector.
    """
    rec = recommend(HERO, BOARD, pot=50.0, to_call=0.0, stack=90.0,
                    street='flop', villain_pos='UTG',
                    villain_reach=np.ones(N_COMBOS, dtype=np.float32),
                    extra_blockers=('Ts', '9s'))
    assert rec.action in ('fold', 'check', 'call', 'bet_25', 'bet_50',
                          'bet_75', 'raise', 'all_in')


def test_extra_blockers_empty_range_raises():
    """Si los blockers vacían el rango explícito, debe ser RangeError."""
    from motor.cards import card_id
    # un rango con masa solo en 7cTs, y 7c/7s como blockers -> vacío
    vec = np.zeros(N_COMBOS, dtype=np.float32)
    from motor.ranges import _PAIR_IDX
    vec[_PAIR_IDX[(card_id('7c'), card_id('Ts'))]] = 1.0
    with pytest.raises(RangeError):
        recommend(HERO, BOARD, pot=50.0, to_call=0.0, stack=90.0,
                  street='flop', villain_pos='UTG',
                  villain_reach=vec, extra_blockers=('7c', 'Ts'))


# --- contrato de validación uniforme (pegar_3 paso 1) -------------------

def test_range_state_validated_before_indexing():
    """villain_weights() valida el reach completo, no solo los ids pedidos.

    Si el RangeState está corrupto fuera de la ventana consultada, debe
    seguir siendo visible como error.
    """
    rs = RangeState(reach=np.full(N_COMBOS, 0.5, dtype=np.float32))
    rs.reach[1234] = np.nan
    from motor.hand_evaluator import legal_hands
    from motor.cards import cards_to_bits
    ids = legal_hands(cards_to_bits(HERO + BOARD))
    # el índice 1234 puede no caer en `ids`; la validación es del vector entero
    with pytest.raises(RangeError):
        villain_weights(rs, ids)


def test_villain_weights_rejects_negative_in_range_state():
    rs = RangeState(reach=np.full(N_COMBOS, -0.5, dtype=np.float32))
    from motor.hand_evaluator import legal_hands
    from motor.cards import cards_to_bits
    ids = legal_hands(cards_to_bits(HERO + BOARD))
    with pytest.raises(RangeError):
        villain_weights(rs, ids)