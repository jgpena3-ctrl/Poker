"""Tests de los contratos puros de rango/equity HU-P2."""
import numpy as np
import pytest

from motor.hu_range_contracts import (
    ActionStatistics, CurrentBoardStrength, EquityToShowdown, GenericPrior,
    KnownCards, ObservedCombo, ObservedRange, build_estimated_range,
    current_board_strength, equity_to_showdown, estimated_range_to_state,
)
from motor.ranges import N_COMBOS, RangeError, RangeState


def _obs(hand_id='H_1', cards=('As', 'Kd'), source='showdown'):
    return ObservedCombo(hand_id=hand_id, exact_combo=cards,
                         reveal_source=source, reveal_event='showdown',
                         data_snapshot_hash='3f0e7e5e')


def _uniform_prior(**kw):
    return GenericPrior.flat('flat', value=1.0, **kw)


# ---------------------------------------------------------------------------
# Observaciones: exactas, sin normalizar
# ---------------------------------------------------------------------------

def test_known_cards_rechaza_duplicados_entre_grupos():
    with pytest.raises(ValueError):
        KnownCards(hero_hand=('As', 'Kd'), board=('As', '2c', '3d'))
    with pytest.raises(ValueError):
        KnownCards(hero_hand=('As', 'As'))


def test_known_cards_mascara_legal():
    kc = KnownCards(hero_hand=('As', 'Kd'), board=('2c', '7d', '9h'))
    assert kc.known_mask > 0
    assert kc.legal_mask.shape == (N_COMBOS,)
    assert kc.legal_mask.sum() < N_COMBOS


def test_observed_combo_no_admite_carta_repetida():
    with pytest.raises(ValueError):
        _obs(cards=('As', 'As'))


def test_observed_range_preserva_observaciones_y_no_es_distribucion():
    o1 = _obs('H_1', ('As', 'Kd'))
    o2 = _obs('H_2', ('As', 'Kd'))
    r = ObservedRange(player='V', street='river',
                      board=('2c', '7d', '9h', 'Ts', 'Jc'),
                      observations=(o1, o2), source_window='base',
                      data_snapshot_hash='3f0e7e5e')
    assert r.n_observations == 2
    assert r.is_distribution is False
    assert [o.hand_id for o in r.observations] == ['H_1', 'H_2']


# ---------------------------------------------------------------------------
# Estadística: denominador explícito, incertidumbre no inventada
# ---------------------------------------------------------------------------

def test_action_statistics_cero_denominador_no_inventa_frecuencia():
    s = ActionStatistics(scope='V', spot='OR_UTG', action='open',
                         numerator=0, denominator=0)
    assert s.frequency is None
    with pytest.raises(ValueError):
        ActionStatistics(scope='V', spot='OR_UTG', action='open',
                         numerator=0, denominator=0, frequency=0.0)


def test_action_statistics_frecuencia_derivada_y_validada():
    s = ActionStatistics(scope='V', spot='OR_UTG', action='open',
                         numerator=3, denominator=4)
    assert s.frequency == 0.75
    with pytest.raises(ValueError):
        ActionStatistics(scope='V', spot='OR_UTG', action='open',
                         numerator=3, denominator=4, frequency=0.5)
    with pytest.raises(ValueError):
        ActionStatistics(scope='V', spot='OR_UTG', action='open',
                         numerator=5, denominator=4)


def test_action_statistics_intervalo_exige_metodo_y_contiene_frecuencia():
    s = ActionStatistics(scope='V', spot='OR_UTG', action='open',
                         numerator=3, denominator=4, ci_low=0.3,
                         ci_high=0.9, ci_method='wilson')
    assert s.ci_method == 'wilson'
    with pytest.raises(ValueError):
        ActionStatistics(scope='V', spot='OR_UTG', action='open',
                         numerator=3, denominator=4, ci_low=0.3,
                         ci_high=0.9)
    with pytest.raises(ValueError):
        ActionStatistics(scope='V', spot='OR_UTG', action='open',
                         numerator=3, denominator=4, ci_low=0.8,
                         ci_high=0.9, ci_method='wilson')


# ---------------------------------------------------------------------------
# Prior: procedencia y cobertura
# ---------------------------------------------------------------------------

def test_generic_prior_valida_vector_y_procedencia():
    p = _uniform_prior()
    assert p.mass == N_COMBOS
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS - 1),
                     source='flat', coverage='unknown')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.zeros(N_COMBOS),
                     source='flat', coverage='unknown')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='flat', coverage='alias')


def test_generic_prior_alias_y_fallback_declaran_su_clave():
    alias = GenericPrior(key='4B_CO_vs_MP', vector=np.ones(N_COMBOS),
                         source='alias', coverage='alias',
                         alias_of='4B_CO_vs_BB', source_key='4B_CO_vs_BB')
    assert alias.alias_of == '4B_CO_vs_BB'
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='alias', coverage='alias')
    fallback = GenericPrior(key='x', vector=np.ones(N_COMBOS),
                            source='fallback', coverage='coverage_gap',
                            fallback_key='4B_CO_vs_BB',
                            fallback_reason='sin_tabla_exacta')
    assert fallback.fallback_key == '4B_CO_vs_BB'
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='fallback', coverage='coverage_gap')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='fallback', coverage='coverage_gap',
                     fallback_key='4B_CO_vs_BB')


# ---------------------------------------------------------------------------
# Rango estimado: blockers, reach y vacío explícito
# ---------------------------------------------------------------------------

def test_build_estimated_range_aplica_blockers_y_normaliza():
    kc = KnownCards(hero_hand=('As', 'Kd'))
    e = build_estimated_range(
        player='V', street='preflop', board=[], prior=_uniform_prior(),
        likelihood=np.ones(N_COMBOS), known_cards=kc, n_obs=2, n_opp=2)
    assert e.empty_status == 'usable'
    assert e.posterior is not None
    assert abs(float(e.posterior.sum()) - 1.0) < 1e-12
    assert float(e.posterior[~kc.legal_mask].sum()) == 0.0
    assert e.n_eff is not None and e.n_eff > 0


def test_build_estimated_range_vacio_no_se_convierte_en_ceros():
    e = build_estimated_range(
        player='V', street='preflop', board=[], prior=_uniform_prior(),
        likelihood=np.zeros(N_COMBOS), n_obs=0, n_opp=10)
    assert e.empty_status == 'empty'
    assert e.posterior is None
    assert e.empty_reason == 'likelihood_zero_after_blockers'
    with pytest.raises(RangeError):
        estimated_range_to_state(e)


def test_reach_declarado_no_se_multiplica_dos_veces():
    reach = np.zeros(N_COMBOS)
    reach[0] = 3.0
    like = np.ones(N_COMBOS)
    # Si el caller ya incorporó reach al likelihood, no se vuelve a aplicar.
    e1 = build_estimated_range(
        player='V', street='preflop', board=[], prior=_uniform_prior(),
        likelihood=like, reach=reach, reach_role='likelihood_component')
    assert abs(float(e1.posterior[0]) - 1.0 / N_COMBOS) < 1e-12
    # Como factor independiente se aplica exactamente una vez.
    e2 = build_estimated_range(
        player='V', street='preflop', board=[], prior=_uniform_prior(),
        likelihood=like, reach=reach, reach_role='independent_factor')
    assert e2.posterior[0] > e2.posterior[1]
    assert e2.reach_role == 'independent_factor'


def test_estimated_range_conserva_cobertura_del_prior():
    p = GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='fallback', coverage='coverage_gap',
                     fallback_key='OR_UTG',
                     fallback_reason='sin_tabla_exacta')
    e = build_estimated_range(
        player='V', street='preflop', board=[], prior=p,
        likelihood=np.ones(N_COMBOS))
    assert e.coverage == 'coverage_gap'
    assert e.prior_source == 'fallback'


# ---------------------------------------------------------------------------
# Fuerza actual vs showdown
# ---------------------------------------------------------------------------

def test_current_board_strength_rango_vacio_es_unknown_no_cero():
    r = current_board_strength(
        ('As', 'Kd'), ('2c', '7d', '9h'),
        RangeState(reach=np.zeros(N_COMBOS)))
    assert r.value is None
    assert r.coverage == 'unknown'
    assert r.reason


def test_current_board_strength_calcula_sin_runout():
    r = current_board_strength(('As', 'Kd'), ('2c', '7d', '9h'))
    assert r.coverage == 'usable'
    assert r.value is not None and 0.0 <= r.value <= 1.0
    assert r.method == 'equity_vs_range_current_board'
    assert r.n_combos > 0


def test_equity_to_showdown_river_exacto_y_sin_ci_inventado():
    r = equity_to_showdown(('As', 'Kd'), ('2c', '7d', '9h', 'Ts', 'Jc'),
                           n_runouts=1, n_combos=10)
    assert r.method == 'river_exact'
    assert r.value is not None and 0.0 <= r.value <= 1.0
    assert r.ci_low is None and r.ci_high is None
    assert r.uncertainty_reason is None


def test_equity_to_showdown_flop_es_reproducible_y_no_inventa_ci():
    a = equity_to_showdown(('As', 'Kd'), ('2c', '7d', '9h'),
                           n_runouts=2, n_combos=10, seed=11)
    b = equity_to_showdown(('As', 'Kd'), ('2c', '7d', '9h'),
                           n_runouts=2, n_combos=10, seed=11)
    assert a.value == b.value
    assert a.method == 'runout_mc'
    assert a.ci_low is None and a.ci_high is None
    assert a.uncertainty_reason


def test_fuerza_actual_y_showdown_son_resultados_distintos():
    current = current_board_strength(('As', 'Kd'), ('2c', '7d', '9h'))
    showdown = equity_to_showdown(('As', 'Kd'), ('2c', '7d', '9h'),
                                  n_runouts=2, n_combos=10)
    assert current.result_definition != showdown.result_definition
    assert current.method != showdown.method
    assert current.as_dict()['value'] is not None
    assert showdown.as_dict()['value'] is not None

def test_generic_prior_rechaza_procedencia_incompleta():
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='observed_exact', coverage='exact')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='flat', coverage='exact')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='manual', coverage='alias')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='alias', coverage='exact')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='fallback', coverage='coverage_gap',
                     fallback_reason='sin_tabla_exacta')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='fallback', coverage='coverage_gap',
                     fallback_key='4B_CO_vs_BB')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='fallback', coverage='unknown',
                     fallback_key='4B_CO_vs_BB',
                     fallback_reason='sin_tabla_exacta')
    with pytest.raises(ValueError):
        GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='preflop_table', coverage='exact')
    p = GenericPrior(key='x', vector=np.ones(N_COMBOS),
                     source='preflop_table', coverage='exact',
                     provenance={'table': 'OR_UTG'})
    assert p.provenance == {'table': 'OR_UTG'}


def test_observed_range_valida_board_por_street_y_sin_solape():
    empty = ()
    for street, board in (
            ('preflop', ('2c',)),
            ('flop', ('2c', '7d')),
            ('turn', ('2c', '7d', '9h')),
            ('river', ('2c', '7d', '9h', 'Ts'))):
        with pytest.raises(ValueError):
            ObservedRange(player='V', street=street, board=board,
                          observations=empty, source_window='base',
                          data_snapshot_hash='3f0e7e5e')
    observed = _obs(cards=('2c', 'Kd'))
    with pytest.raises(ValueError):
        ObservedRange(player='V', street='flop',
                      board=('2c', '7d', '9h'), observations=(observed,),
                      source_window='base',
                      data_snapshot_hash='3f0e7e5e')
    valid = ObservedRange(player='V', street='flop',
                          board=('2c', '7d', '9h'),
                          observations=(_obs(cards=('As', 'Kd')),),
                          source_window='base',
                          data_snapshot_hash='3f0e7e5e')
    assert valid.board == ('2c', '7d', '9h')


def test_build_estimated_range_exige_board_coherente():
    with pytest.raises(ValueError):
        build_estimated_range(
            player='V', street='flop', board=(), prior=_uniform_prior(),
            likelihood=np.ones(N_COMBOS))
    kc = KnownCards(hero_hand=('As', 'Kd'),
                    board=('2c', '7d', '9h'))
    with pytest.raises(ValueError):
        build_estimated_range(
            player='V', street='flop', board=('2c', '7d', '9s'),
            prior=_uniform_prior(), likelihood=np.ones(N_COMBOS),
            known_cards=kc)


def test_action_statistics_intervalo_sin_denominador_es_invalido():
    with pytest.raises(ValueError):
        ActionStatistics(scope='V', spot='OR_UTG', action='open',
                         numerator=0, denominator=0, ci_low=0.0,
                         ci_high=1.0, ci_method='wilson')


def test_current_board_strength_estado_y_ids_coherentes():
    with pytest.raises(ValueError):
        CurrentBoardStrength(
            hero_hand=('As', 'Kd'), board=('2c', '7d', '9h'),
            value=None, method='x', coverage='usable', n_combos=1)
    with pytest.raises(ValueError):
        CurrentBoardStrength(
            hero_hand=('As', 'Kd'), board=('2c', '7d', '9h'),
            value=0.5, method='x', coverage='unknown', n_combos=1,
            reason='r')
    with pytest.raises(ValueError):
        CurrentBoardStrength(
            hero_hand=('As', 'Kd'), board=('2c', '7d', '9h'),
            value=None, method='x', coverage='unknown', n_combos=0)
    with pytest.raises(ValueError):
        current_board_strength(('As', 'Kd'), ('2c', '7d', '9h'),
                               villain_ids=[0, 0])


def test_equity_to_showdown_no_declara_ci_sin_metodo():
    with pytest.raises(ValueError):
        EquityToShowdown(
            hero_hand=('As', 'Kd'), board=('2c', '7d', '9h'),
            value=0.5, method='runout_mc', n_runouts=1,
            n_combos_sampled=1, seed=1, ci_low=0.1, ci_high=0.9)


def test_equity_to_showdown_postflop_informa_los_combos_evaluados():
    a = equity_to_showdown(('As', 'Kd'), ('2c', '7d', '9h'),
                           n_runouts=1, n_combos=1, seed=11)
    b = equity_to_showdown(('As', 'Kd'), ('2c', '7d', '9h'),
                           n_runouts=1, n_combos=200, seed=11)
    current = current_board_strength(('As', 'Kd'), ('2c', '7d', '9h'))
    assert a.n_combos_sampled == b.n_combos_sampled
    assert a.n_combos_sampled == current.n_combos
