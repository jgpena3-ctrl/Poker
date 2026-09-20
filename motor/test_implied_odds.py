from .implied_odds import (analizar_call, equity_desde_outs,
                           equity_regla, pot_odds_necesarias)


def test_equity_flush_draw_flop():
    # 9 outs con dos cartas por venir: 1 - C(38,2)/C(47,2) ~ 34.97%
    esperado = 1 - (38 * 37) / (47 * 46)
    assert abs(equity_desde_outs(9, 2) - esperado) < 1e-12


def test_equity_flush_draw_turn():
    assert abs(equity_desde_outs(9, 1) - 9 / 46) < 1e-12


def test_equity_sin_outs():
    assert equity_desde_outs(0, 2) == 0.0


def test_regla_del_4_y_2():
    assert abs(equity_regla(9, 2) - 0.36) < 1e-9
    assert abs(equity_regla(9, 1) - 0.18) < 1e-9


def test_pot_odds():
    assert abs(pot_odds_necesarias(100, 300) - 0.25) < 1e-9
    assert pot_odds_necesarias(0, 100) == 0.0


def test_call_rentable_no_pide_extra():
    a = analizar_call(9, 2, 100, 300)
    assert a.rentable_directo
    assert a.extra_necesario == 0.0
    assert a.ev_directo > 0


def test_call_no_rentable_calcula_implied():
    a = analizar_call(9, 1, 100, 300)  # equity ~19.6% < 25% requerida
    assert not a.rentable_directo
    e = 9 / 46
    assert abs(a.extra_necesario - (100 / e - 400)) < 1e-9
    # el extra como porcentaje del bote + call: 111.11 / 400 ~ 27.78%
    assert abs(a.extra_pct_bote_call - ((100 / e - 400) / 400)) < 1e-9
    assert abs(a.cobro_minimo_al_completar - 100 / e) < 1e-9


def test_call_cero_es_gratis():
    a = analizar_call(9, 2, 0, 100)
    assert a.rentable_directo
    assert a.pot_odds == 0.0
    assert a.extra_necesario == 0.0
