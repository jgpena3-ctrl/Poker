import pytest

from motor.pot_layers import (
    PotLayerError, build_pot_layers, settle_pot_layers,
)


def test_three_unequal_contributions_build_main_and_side_pots():
    result = build_pot_layers({'hero': 100, 'villain-a': 50, 'villain-b': 25})
    assert [pot.amount for pot in result.pots] == [75.0, 50.0]
    assert [pot.eligible for pot in result.pots] == [
        ('hero', 'villain-a', 'villain-b'), ('hero', 'villain-a')]
    assert result.returned_uncalled == (('hero', 50.0),)
    assert result.total_contributed == 175.0
    assert result.total_pot == 125.0


def test_folded_contribution_remains_in_pot_but_folded_player_cannot_win():
    result = build_pot_layers(
        {'hero': 100, 'villain-a': 50, 'villain-b': 50},
        folded={'villain-b'})
    assert len(result.pots) == 1
    assert result.pots[0].amount == 150.0
    assert result.pots[0].contributors == ('hero', 'villain-a', 'villain-b')
    assert result.pots[0].eligible == ('hero', 'villain-a')
    assert result.returned_uncalled == (('hero', 50.0),)


def test_equal_contributions_have_one_pot_and_no_return():
    result = build_pot_layers({'hero': 42, 'v1': 42, 'v2': 42})
    assert len(result.pots) == 1
    assert result.pots[0].amount == 126
    assert result.returned_uncalled == ()


def test_unmatched_top_contribution_is_returned_to_live_contributor():
    result = build_pot_layers({'hero': 20, 'v1': 10})
    assert result.pots[0].amount == 20
    assert result.returned_uncalled == (('hero', 10.0),)
    assert result.total_contributed == result.total_pot + 10


@pytest.mark.parametrize('contributions', [
    {}, {'hero': -1, 'v1': 2}, {'hero': float('nan'), 'v1': 2},
    {'hero': True, 'v1': 2}, {'hero': 0, 'v1': 0},
])
def test_invalid_contributions_fail_closed(contributions):
    with pytest.raises(PotLayerError):
        build_pot_layers(contributions)


def test_folded_player_with_unmatched_top_layer_is_rejected():
    with pytest.raises(PotLayerError, match='jugador que foldeó'):
        build_pot_layers({'folded': 100, 'hero': 50}, folded={'folded'})


def test_unknown_fold_identity_is_rejected():
    with pytest.raises(PotLayerError, match='sin contribución'):
        build_pot_layers({'hero': 10}, folded={'other'})


def test_four_players_with_different_all_in_stacks_make_three_layers():
    result = build_pot_layers(
        {'hero': 120, 'short': 25, 'middle': 70, 'deep': 120})
    assert [pot.amount for pot in result.pots] == [100, 135, 100]
    assert [pot.eligible for pot in result.pots] == [
        ('hero', 'short', 'middle', 'deep'),
        ('hero', 'middle', 'deep'), ('hero', 'deep')]
    assert result.returned_uncalled == ()
    assert result.total_pot == result.total_contributed == 335


def test_layer_with_single_eligible_player_still_contains_called_dead_money():
    result = build_pot_layers(
        {'hero': 50, 'caller': 50, 'folded-a': 50},
        folded={'caller', 'folded-a'})
    assert result.pots[0].amount == 150
    assert result.pots[0].eligible == ('hero',)


def test_sidepot_layer_can_exclude_hero():
    result = build_pot_layers(
        {'hero': 25, 'v1': 50, 'v2': 100, 'v3': 100})
    assert result.pots[0].eligible == ('hero', 'v1', 'v2', 'v3')
    assert result.pots[1].eligible == ('v1', 'v2', 'v3')
    assert result.pots[2].eligible == ('v2', 'v3')
    assert result.returned_uncalled == ()


def test_ties_are_split_per_layer_and_total_chips_are_conserved():
    layers = build_pot_layers({'hero': 100, 'v1': 50, 'v2': 25})
    settlement = settle_pot_layers(
        layers, {25.0: ('hero', 'v2'), 50.0: ('v1',)})
    assert dict(settlement.payouts) == {
        'hero': 87.5, 'v1': 50.0, 'v2': 37.5}
    assert settlement.total_awarded == layers.total_contributed == 175


def test_tie_in_each_layer_is_split_independently():
    layers = build_pot_layers({'hero': 60, 'v1': 60, 'v2': 30})
    assert [pot.amount for pot in layers.pots] == [90.0, 60.0]
    assert [pot.eligible for pot in layers.pots] == [
        ('hero', 'v1', 'v2'), ('hero', 'v1')]
    settlement = settle_pot_layers(
        layers, {30.0: ('hero', 'v2'), 60.0: ('hero', 'v1')})
    assert dict(settlement.payouts) == {
        'hero': 75.0, 'v1': 30.0, 'v2': 45.0}
    assert settlement.total_awarded == layers.total_contributed == 150.0


def test_tie_winners_must_be_eligible_and_declared_for_each_layer():
    layers = build_pot_layers({'hero': 50, 'v1': 25, 'v2': 25})
    with pytest.raises(PotLayerError, match='no elegible'):
        settle_pot_layers(layers, {25.0: ('hero', 'not-in-pot')})
    with pytest.raises(PotLayerError, match='cada capa'):
        settle_pot_layers(layers, {})
