"""Fixtures sinteticas para auditar estados HU en varias calles."""


def _base(**overrides):
    state = {
        'btn': 'hero',
        'hero_state': 'activo',
        'p1_state': 'activo',
        'p2_state': 'sin jugador',
        'p3_state': 'sin jugador',
        'p4_state': 'sin jugador',
        'p5_state': 'sin jugador',
        'hero_stake': 99.5,
        'p1_stake': 99.0,
        'hero_bet': 0.5,
        'p1_bet': 1.0,
        'pot': 1.5,
        'hero_cards': ['As', 'Kd'],
        'p1_cards': None,
        'community': [],
        'hand_state': 'in_progress',
    }
    state.update(overrides)
    return state


def _cards(*codes):
    return [{'rank': code[:-1], 'suit': code[-1]} for code in codes]


HU_STATE_FIXTURES = {
    'preflop_sb_to_act': _base(player_to_act='hero'),
    'preflop_bb_option': _base(
        hero_stake=99.0, p1_stake=99.0, hero_bet=1.0, p1_bet=1.0,
        pot=2.0, player_to_act='p1'),
    'flop_bb_first_checked': _base(
        hero_stake=99.0, p1_stake=99.0, hero_bet=0.0, p1_bet=0.0,
        pot=2.0, community=_cards('2c', '7h', 'Qs'), player_to_act='p1'),
    'turn_hero_facing_bet': _base(
        hero_stake=97.0, p1_stake=97.0, hero_bet=0.0, p1_bet=2.0,
        pot=6.0, community=_cards('2c', '7h', 'Qs', 'Jh'),
        player_to_act='hero'),
    'river_no_bet': _base(
        hero_stake=95.0, p1_stake=95.0, hero_bet=0.0, p1_bet=0.0,
        pot=10.0, community=_cards('2c', '7h', 'Qs', 'Jh', '3d'),
        player_to_act='p1'),
}


def hu_state_fixtures():
    """Devuelve copias para que cada prueba pueda mutarlas sin contaminar."""
    return {name: dict(state) for name, state in HU_STATE_FIXTURES.items()}
