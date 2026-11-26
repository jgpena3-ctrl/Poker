"""Synthetic mechanical/numeric tests for the isolated MW equity core."""
import numpy as np
import pytest

from motor.cards import card_id
from motor.mw_equity import (
    MultiwayEquityError, OpponentRange, calculate_multiway_equity,
    sample_next_public_card,
)
from motor.ranges import COMBO0, COMBO1, N_COMBOS


def _combo_index(a, b):
    a, b = sorted((card_id(a), card_id(b)))
    return int(np.flatnonzero((COMBO0 == a) & (COMBO1 == b))[0])


def _range(identity, *combos):
    weights = np.zeros(N_COMBOS, dtype=np.float64)
    for cards, weight in combos:
        weights[_combo_index(*cards)] = weight
    return OpponentRange(identity, weights, 'synthetic test fixture', 'synthetic')


def test_exact_mw_equity_enumerates_joint_assignments_and_board_runouts():
    # Hero has an overpair on this river; both distinct villain combos lose.
    result = calculate_multiway_equity(
        ['As', 'Ad'], ['2c', '3d', '4h', '5s', '9c'],
        [_range('villain-a', (('Kc', 'Kd'), 1.0)),
         _range('villain-b', (('Qc', 'Qd'), 1.0))], exact=True)
    assert result.equity == 1.0
    assert result.valid_joint_assignments == 1
    assert result.rejected_joint_assignments == 0
    assert result.runouts_per_assignment == 1
    assert result.standard_error == 0.0
    assert result.model == \
        'independent_marginals_conditioned_on_no_card_collision'


def test_exact_mw_equity_shares_ties_across_every_active_player():
    result = calculate_multiway_equity(
        ['2c', '3d'], ['Ts', 'Js', 'Qs', 'Ks', 'As'],
        [_range('v1', (('2d', '3c'), 1.0)),
         _range('v2', (('4c', '5d'), 1.0))], exact=True)
    assert result.equity == pytest.approx(1 / 3)


def test_shared_blocker_collision_rejected_as_invalid_joint_deal():
    shared = ('Kc', 'Kd')
    with pytest.raises(MultiwayEquityError, match='ninguna asignación conjunta'):
        calculate_multiway_equity(
            ['As', 'Ad'], ['2c', '3d', '4h', '5s', '9c'],
            [_range('v1', (shared, 1.0)), _range('v2', (shared, 1.0))],
            exact=True)


def test_monte_carlo_abstains_when_no_joint_assignment_survives_blockers():
    shared = ('Kc', 'Kd')
    with pytest.raises(MultiwayEquityError, match='muestreo condicionado incompleto'):
        calculate_multiway_equity(
            ['As', 'Ad'], ['2c', '3d', '4h', '5s', '9c'],
            [_range('v1', (shared, 1.0)), _range('v2', (shared, 1.0))],
            samples=1, max_proposals=5, seed=11)


def test_explicit_dead_cards_are_blockers_and_cannot_overlap_known_cards():
    opponents = [_range('v1', (('Kc', 'Kd'), 1.0)),
                 _range('v2', (('Qc', 'Qd'), 1.0))]
    result = calculate_multiway_equity(
        ['As', 'Ad'], ['2c', '3d', '4h', '5s', '9c'], opponents,
        dead_cards=['Jc', 'Jd'], exact=True)
    assert result.dead_cards == ('Jc', 'Jd')
    assert result.runouts_per_assignment == 1
    with pytest.raises(MultiwayEquityError, match='solapa'):
        calculate_multiway_equity(
            ['As', 'Ad'], ['2c', '3d', '4h', '5s', '9c'], opponents,
            dead_cards=['As'])


def test_noneligible_live_range_blocks_cards_without_contesting_pot_layer():
    result = calculate_multiway_equity(
        ['As', 'Ad'], ['2c', '3d', '4h'],
        [_range('eligible-villain', (('Kc', 'Kd'), 1.0))],
        dead_ranges=[_range('sidepot-only-villain', (('Qc', 'Qd'), 1.0))],
        exact=True)
    assert result.opponents == ('eligible-villain',)
    assert result.blocking_players == ('sidepot-only-villain',)
    assert result.runouts_per_assignment == 903
    assert result.model == \
        'independent_marginals_conditioned_on_no_card_collision'


def test_next_board_card_sampling_respects_all_private_hands_and_seed():
    ranges = [_range('v1', (('Kc', 'Kd'), 1.0)),
              _range('v2', (('Qc', 'Qd'), 1.0))]
    first = sample_next_public_card(
        ['As', 'Ad'], ['2c', '3d', '4h'], ranges,
        samples=25, seed=47)
    second = sample_next_public_card(
        ['As', 'Ad'], ['2c', '3d', '4h'], ranges,
        samples=25, seed=47)
    assert first == second
    assert first.model == \
        'independent_marginals_conditioned_on_no_card_collision'
    assert all(card not in {'As', 'Ad', '2c', '3d', '4h',
                            'Kc', 'Kd', 'Qc', 'Qd'}
               for card in first.cards)


def test_exact_next_board_card_enumerates_supported_cards_and_probabilities():
    result = sample_next_public_card(
        ['As', 'Ad'], ['2c', '3d', '4h'],
        [_range('v1', (('Kc', 'Kd'), 1.0)),
         _range('v2', (('Qc', 'Qd'), 1.0))], exact=True)
    assert result.exact
    assert len(result.cards) == 43
    assert len(result.cards) == len(result.probabilities)
    assert sum(result.probabilities) == pytest.approx(1.0)
    assert set(result.cards).isdisjoint(
        {'As', 'Ad', '2c', '3d', '4h', 'Kc', 'Kd', 'Qc', 'Qd'})


def test_exact_reports_joint_collisions_and_conditions_on_legal_assignments():
    r1 = _range('v1', (('Kc', 'Kd'), 1.0), (('Qc', 'Qd'), 1.0))
    r2 = _range('v2', (('Kc', 'Kd'), 1.0), (('Jc', 'Jd'), 1.0))
    result = calculate_multiway_equity(
        ['As', 'Ad'], ['2c', '3d', '4h', '5s', '9c'], [r1, r2], exact=True)
    assert result.valid_joint_assignments == 3
    assert result.rejected_joint_assignments == 1
    assert result.valid_joint_mass == pytest.approx(0.75)


def test_monte_carlo_is_seeded_and_reports_sampling_uncertainty():
    opponents = [
        _range('v1', (('Kc', 'Kd'), 1.0)),
        _range('v2', (('Qc', 'Qd'), 1.0)),
    ]
    args = (['As', 'Ad'], ['2c', '3d', '4h'], opponents)
    first = calculate_multiway_equity(*args, samples=40, seed=19)
    second = calculate_multiway_equity(*args, samples=40, seed=19)
    assert first.equity == second.equity
    assert first.proposals == second.proposals
    assert first.samples == 40
    assert first.standard_error is not None
    assert 0 <= first.equity <= 1


def test_known_blockers_remove_combos_and_empty_range_fails_closed():
    r = _range('v1', (('As', 'Kd'), 1.0), (('Kc', 'Qd'), 1.0))
    result = calculate_multiway_equity(
        ['As', 'Ad'], ['2c', '3d', '4h', '5s'],
        [r, _range('v2', (('Jc', 'Jh'), 1.0))], samples=8, seed=3)
    assert result.removed_combos_by_known_blockers[0] == 1
    assert result.equity is not None


def test_rejects_observed_or_statistical_input_as_probability_model():
    weights = np.ones(N_COMBOS)
    with pytest.raises(MultiwayEquityError, match='source_kind'):
        OpponentRange('v1', weights, 'showdown observation', 'observed')
    with pytest.raises(MultiwayEquityError, match='source_kind'):
        OpponentRange('v1', weights, 'action counts', 'statistics')


def test_exact_work_cap_abstains_instead_of_silently_sampling():
    broad = _range('v1', (('Kc', 'Kd'), 1.0), (('Qc', 'Qd'), 1.0))
    other = _range('v2', (('Jc', 'Jd'), 1.0), (('Tc', 'Td'), 1.0))
    with pytest.raises(MultiwayEquityError, match='excede límite'):
        calculate_multiway_equity(
            ['As', 'Ad'], ['2c', '3d', '4h'], [broad, other], exact=True,
            max_exact_work=10)
