"""Test de motor/decision.py — EV inmediato (MVP 1), respuesta modelada."""
import numpy as np
import pytest

from motor.decision import (
    ACTIONS, BET_LABELS, EvTable, compute_evs, default_response,
    runout_equity,
)
from motor.ranges import COMBO0, COMBO1, RangeState


def test_actions_complete():
    assert ACTIONS == ('fold', 'check', 'call', 'bet_25', 'bet_50', 'bet_75', 'all_in')


def test_default_response_is_probability():
    for amount, pot in [(20, 50), (100, 40), (5, 200)]:
        for e in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0):
            pf, pc, pr = default_response(e, amount, pot)
            assert np.isclose(pf + pc + pr, 1.0)
            assert 0.0 <= pf <= 1.0 and 0.0 <= pc <= 1.0 and 0.0 <= pr <= 1.0


def test_response_geometry():
    # Un rival sin equity casi siempre se pliega; uno con figuras resube algo
    pf_weak, _, pr_weak = default_response(0.05, 10, 20)
    pf_strong, _, pr_strong = default_response(0.95, 10, 20)
    assert pf_weak > pf_strong
    assert pr_strong > pr_weak
    # apuesta de 0 no cambia nada: call 100%
    assert default_response(0.5, 0, 100) == (0.0, 1.0, 0.0)


def test_ev_table_best_is_available():
    evs = compute_evs(['As', 'Kd'], ['Qh', '7s', '2c'],
                      pot=12.5, to_call=0, stack=90)
    assert isinstance(evs, EvTable)
    assert evs.best()[0] in ACTIONS
    # sin bet en curso no puede haber call
    assert set(evs.ev) == {'fold', 'check', 'bet_25', 'bet_50', 'bet_75', 'all_in'}
    evs_call = compute_evs(['As', 'Kd'], ['Qh', '7s', '2c'],
                           pot=12.5, to_call=4, stack=90)
    assert set(evs_call.ev) == {'fold', 'call', 'bet_25', 'bet_50', 'bet_75', 'all_in'}


def test_ev_constraints():
    ev = compute_evs(['As', 'Kd'], ['Qh', '7s', '2c'],
                     pot=12.5, to_call=0, stack=90)
    assert ev.ev['fold'] == 0.0
    assert ev.ev['check'] == ev.hero_equity * 12.5  # check = equity × pot

    # con bet en curso, check no disponible y call ≠ 0
    ev2 = compute_evs(['As', 'Kd'], ['Qh', '7s', '2c'],
                      pot=12.5, to_call=5.0, stack=90)
    assert 'check' not in ev2.ev
    assert ev2.ev['call'] == ev2.hero_equity * (12.5 + 10) - 5.0


def test_ev_degenerate_win():
    # Hero con la mano más fuerte posible vs un solo combo perdedor:
    # AA vs reach solo en 22 (rank 0), tablero sin A ni 2 → hero gana siempre.
    hero, board = ['Ah', 'Ad'], ['Qh', '7s', '9c']
    reach = np.zeros(1326, dtype=np.float32)
    for i, (a, b) in enumerate(zip(COMBO0, COMBO1)):
        if a // 4 == 0 and b // 4 == 0:  # 22
            reach[i] = 1.0
    ev = compute_evs(hero, board, villain_reach=reach, pot=50, to_call=0, stack=100)
    assert ev.hero_equity == pytest.approx(1.0)

    # call (si hubiera bet) = equity×pot_after − to_call
    ev_call = compute_evs(hero, board, villain_reach=reach,
                          pot=40, to_call=10, stack=100)
    assert ev_call.ev['call'] == pytest.approx(1.0 * (40 + 20) - 10)


def test_ev_folding_rival_loses_value():
    # Rival solo 22 (pareja baja) vs AA: un bet lo hace fold casi siempre
    hero, board = ['As', 'Ah'], ['Qh', '7s', '9c']  # sin 2 en el board
    reach = np.zeros(1326, dtype=np.float32)
    for i, (a, b) in enumerate(zip(COMBO0, COMBO1)):
        if a // 4 == 0 and b // 4 == 0:
            reach[i] = 1.0
    ev = compute_evs(hero, board, villain_reach=reach, pot=50, to_call=0, stack=100)
    # p_fold(22 vs AA, apuesta 12.5 en 50) → 0.98; EV ≈ 0.98·50 + call marginal
    assert ev.ev['bet_25'] > 45
    assert ev.ev['all_in'] > 40


def test_ev_bets_grow_with_pot_geography():
    # Sin bet y pot 0: check y bet 0; all-in no puede ganar nada (EV ≤ 0)
    ev = compute_evs(['As', 'Kd'], ['Qh', '7s', '2c'], pot=0, to_call=0, stack=100)
    assert ev.ev['bet_25'] == 0.0 and ev.ev['check'] == 0.0
    assert ev.ev['all_in'] <= 0.0


def test_recommend_via_best():
    ev = compute_evs(['As', 'Kd'], ['Qh', '7s', '2c'], pot=100, to_call=45, stack=90)
    label, value = ev.best()
    assert label in ACTIONS
    assert value == max(ev.ev.values())


def test_compute_evs_requires_hand():
    with pytest.raises(ValueError):
        compute_evs(['As'], ['Qh', '7s', '2c'])


def _reach_single_below_pair():
    reach = np.zeros(1326, dtype=np.float32)
    for i, (a, b) in enumerate(zip(COMBO0, COMBO1)):
        if a // 4 == 0 and b // 4 == 0:  # 22
            reach[i] = 1.0
    return reach


def test_runout_equity_river_is_deterministic():
    # En river no hay cartas por sacar: runout equivale a la equity exacta
    hero, board, reach = ['Ah', 'Ad'], ['Qh', '7s', '9c', '3d', '5h'], \
        _reach_single_below_pair()
    ev = compute_evs(hero, board, villain_reach=reach, pot=50,
                     to_call=0, stack=100)
    re = runout_equity(hero, board, reach)
    assert re == pytest.approx(ev.hero_equity)
    assert re == pytest.approx(1.0)


def test_runout_equity_flop_matches_deterministic_sanity():
    # AA vs 22 en flop sin 2 ni A: con sorteo de turn+river sigue ganando
    # ~todo el tiempo (el 22 solo gana haciendo trío 2 y AA sin trío A),
    # pero la equity MC no puede superar 1.0 y debe quedar cerca.
    hero, board, reach = ['As', 'Ad'], ['Qh', '7s', '9c'], \
        _reach_single_below_pair()
    re = runout_equity(hero, board, reach, n_runouts=400)
    assert 0.80 <= re <= 1.0
    det = compute_evs(hero, board, villain_reach=reach, pot=50,
                      to_call=0, stack=100).hero_equity
    assert re < det  # el segundo ganador (2 sobre 2) ahora cuesta no cerrar


def test_compute_evs_runout_uses_mc_only_off_river():
    hero, board, reach = ['As', 'Ad'], ['Qh', '7s', '9c'], \
        _reach_single_below_pair()
    base = compute_evs(hero, board, villain_reach=reach, pot=50,
                       to_call=0, stack=100)
    with_run = compute_evs(hero, board, villain_reach=reach, pot=50,
                           to_call=0, stack=100, runout=True, n_runouts=300)
    assert with_run.ev['check'] != base.ev['check']
    assert with_run.hero_equity == pytest.approx(
        runout_equity(hero, board, reach, n_runouts=300))

    # En river el runout no cambia nada (no hay cartas por sacar)
    river = ['Qh', '7s', '9c', '3d', '5h']
    base_r = compute_evs(hero, river, villain_reach=reach, pot=50,
                         to_call=0, stack=100)
    with_run_r = compute_evs(hero, river, villain_reach=reach, pot=50,
                             to_call=0, stack=100, runout=True)
    assert with_run_r.hero_equity == pytest.approx(base_r.hero_equity)


def test_compute_evs_runout_turn_uses_mc():
    hero, board, reach = ['As', 'Ad'], ['Qh', '7s', '9c', '2d'], \
        _reach_single_below_pair()
    base = compute_evs(hero, board, villain_reach=reach, pot=50,
                       to_call=0, stack=100)
    with_run = compute_evs(hero, board, villain_reach=reach, pot=50,
                           to_call=0, stack=100, runout=True, n_runouts=300)
    assert with_run.ev['check'] != base.ev['check']


# ---------------------------------------------------------------------------
# Árbol de una calle (MVP 2 completo): pagos intermedios
# ---------------------------------------------------------------------------

def _always_fold_response(eq_v, amount, pot):
    n = len(eq_v)
    return np.ones(n), np.zeros(n), np.zeros(n)


def test_tree_river_equals_mvp1():
    # En river no hay calle siguiente: el árbol no cambia nada
    hero, reach = ['As', 'Ad'], _reach_single_below_pair()
    river = ['Qh', '7s', '9c', '3d', '5h']
    base = compute_evs(hero, river, villain_reach=reach, pot=50,
                       to_call=0, stack=100)
    tree = compute_evs(hero, river, villain_reach=reach, pot=50,
                       to_call=0, stack=100, tree=True)
    assert tree.ev == base.ev
    assert tree.hero_equity == base.hero_equity


def test_tree_call_when_rival_always_folds_next_street():
    hero, board, reach = ['As', 'Ad'], ['Qh', '7s', '9c'], \
        _reach_single_below_pair()
    ev = compute_evs(hero, board, villain_reach=reach, pot=40, to_call=10,
                     stack=100, tree=True,
                     response_fn=_always_fold_response,
                     tree_n_street=40, tree_n_finals=3)
    # Si el rival se pliega siempre en el turn, el call gana el bote pot+t
    assert ev.ev['call'] == pytest.approx(40 + 10)
    ev0 = compute_evs(hero, board, villain_reach=reach, pot=40, to_call=0,
                      stack=100, tree=True,
                      response_fn=_always_fold_response,
                      tree_n_street=40, tree_n_finals=3)
    assert ev0.ev['check'] == pytest.approx(40)


def test_tree_deterministic():
    hero, board, reach = ['As', 'Ad'], ['Qh', '7s', '9c'], \
        _reach_single_below_pair()
    kw = dict(villain_reach=reach, pot=50, to_call=0, stack=100, tree=True,
              tree_n_street=40, tree_n_finals=3)
    a = compute_evs(hero, board, **kw)
    b = compute_evs(hero, board, **kw)
    assert a.ev == b.ev


def test_tree_changes_passive_and_bet_branches():
    hero, board, reach = ['As', 'Ad'], ['Qh', '7s', '9c'], \
        _reach_single_below_pair()
    base = compute_evs(hero, board, villain_reach=reach, pot=50,
                       to_call=0, stack=100)
    tr = compute_evs(hero, board, villain_reach=reach, pot=50, to_call=0,
                     stack=100, tree=True, tree_n_street=50,
                     tree_n_finals=4)
    assert tr.ev['check'] != base.ev['check']
    assert tr.ev['bet_25'] != base.ev['bet_25']
    assert tr.ev['bet_50'] != base.ev['bet_50']
    assert tr.ev['all_in'] == base.ev['all_in']  # all-in no tiene calle futura
    base_call = compute_evs(hero, board, villain_reach=reach, pot=50,
                            to_call=5, stack=100)
    tr_call = compute_evs(hero, board, villain_reach=reach, pot=50,
                          to_call=5, stack=100, tree=True,
                          tree_n_street=50, tree_n_finals=4)
    assert tr_call.ev['call'] != base_call.ev['call']