"""Test de motor/learn.py — extracción de frecuencias preflop."""
import pytest

from motor.learn import (
    CATEGORY_DENOM, HERO_NAMES, PreflopEvent, PreflopStats,
    classify_first_action, hand_known, load_hands, preflop_events,
)


def _hand(hand_id='H_9001', players=None, preflop=None):
    players = players or [
        {'name': 'Jarduan', 'pos': 'CO', 'cards': 'JdTd'},
        {'name': 'Villian', 'pos': 'BB', 'cards': ''},
    ]
    return {
        'hand_id': hand_id,
        'players': players,
        'streets': {'preflop': {'actions': preflop or []}},
    }


# ---------------------------------------------------------------------------
# classify_first_action — cobertura de todas las categorías
# ---------------------------------------------------------------------------

def test_classify_no_raise_state():
    assert classify_first_action('f', 0, 0, 0)[:2] == ('fold', 'no_raise')
    assert classify_first_action('c', 1.0, 0, 0)[:2] == ('limp', 'no_raise')
    assert classify_first_action('b', 2.5, 0, 0)[:2] == ('open', 'no_raise')
    assert classify_first_action('b', 3.0, 0, 1)[:2] == ('rol', 'no_raise')
    assert classify_first_action('c', 1.0, 0, 1)[:2] == ('call_limp', 'no_raise')
    assert classify_first_action('x', 0, 0, 2)[:2] == ('bb_check', 'no_raise')


def test_classify_facing_open():
    assert classify_first_action('c', 2.5, 1, 0)[:2] == ('call_open', 'facing_open')
    assert classify_first_action('r', 4.0, 1, 0)[:2] == ('3bet', 'facing_open')
    assert classify_first_action('r', 4.0, 1, 1)[:2] == ('squeeze', 'facing_open')
    assert classify_first_action('f', 0, 1, 0)[:2] == ('fold_vs_open', 'facing_open')


def test_classify_facing_3bet():
    assert classify_first_action('c', 9.0, 2, 0)[:2] == ('call_3bet', 'facing_3bet')
    assert classify_first_action('r', 12.0, 2, 0)[:2] == ('4bet', 'facing_3bet')
    assert classify_first_action('f', 0, 2, 0)[:2] == ('fold_vs_3bet', 'facing_3bet')


def test_classify_unknown_action_raises():
    with pytest.raises(ValueError):
        classify_first_action('z', 0, 0, 0)


def test_denom_consistency():
    for cat, denom in CATEGORY_DENOM.items():
        assert denom in ('no_raise', 'facing_open', 'facing_3bet')
    assert set(CATEGORY_DENOM.values()) == {'no_raise', 'facing_open', 'facing_3bet'}
    for cat in ('open', 'limp', 'rol', 'call_open', '3bet', 'squeeze', '4bet'):
        assert cat in CATEGORY_DENOM


# ---------------------------------------------------------------------------
# preflop_events sobre una mano sintética
# ---------------------------------------------------------------------------

def test_events_single_hand():
    hand = _hand(preflop=[
        {'pos': 'CO', 'action': 'b', 'amount': 2.5},
        {'pos': 'BB', 'action': 'f', 'amount': 0},
    ])
    events = preflop_events(hand)
    co = events[0]
    bb = events[1]
    assert len(events) == 2
    assert (co.player, co.category, co.denom, co.hand_known) == \
        ('Jarduan', 'open', 'no_raise', True)
    assert (bb.player, bb.category, bb.denom, bb.hand_known) == \
        ('Villian', 'fold_vs_open', 'facing_open', False)


def test_hero_always_known_even_without_cards():
    hand = _hand(
        players=[
            {'name': 'Jarduan', 'pos': 'UTG', 'cards': ''},
            {'name': 'Villian', 'pos': 'BB', 'cards': ''},
        ],
        preflop=[('UTG', 'b', 2.5), ('BB', 'x', 0)],
    )
    events = preflop_events(hand)
    assert events[0].hand_known is True  # hero sin cards: igual conocida
    assert events[1].hand_known is False


def test_first_decision_only():
    hand = _hand(preflop=[
        ('CO', 'c', 1.0),        # limp
        ('CO', 'f', 0.0),        # segunda acción no cuenta
        ('BB', 'r', 5.0),        # no_raise? raises_before incluye 0 raises → open
    ])
    events = preflop_events(hand)
    cols = [ev.pos for ev in events]
    assert cols == ['CO', 'BB']
    assert events[0].category == 'limp'


def test_rol_and_squeeze_sequences():
    hand = _hand(
        preflop=[('UTG', 'c', 1.0), ('CO', 'r', 4.0), ('BB', 'f', 0)],
        players=[
            {'name': 'A', 'pos': 'UTG', 'cards': ''},
            {'name': 'Jarduan', 'pos': 'CO', 'cards': 'AhKh'},
            {'name': 'Villian', 'pos': 'BB', 'cards': ''},
        ],
    )
    events = preflop_events(hand)
    by_pos = {e.pos: e for e in events}
    assert by_pos['UTG'].category == 'limp'
    assert by_pos['CO'].category == 'rol'
    assert by_pos['CO'].prereq[0] == 'UTG:c'


def test_squeeze_detection():
    hand = _hand(
        preflop=[('UTG', 'b', 2.5), ('CO', 'c', 2.5), ('BTN', 'r', 8.0)],
        players=[
            {'name': 'A', 'pos': 'UTG', 'cards': ''},
            {'name': 'B', 'pos': 'CO', 'cards': ''},
            {'name': 'Jarduan', 'pos': 'BTN', 'cards': ''},
        ],
    )
    by_name = {e.player: e for e in preflop_events(hand)}
    assert by_name['Jarduan'].category == 'squeeze'
    assert by_name['B'].category == 'call_open'


def test_bb_check_walk():
    hand = _hand(
        preflop=[('BTN', 'c', 1.0), ('BB', 'x', 0)],
        players=[
            {'name': 'A', 'pos': 'BTN', 'cards': ''},
            {'name': 'Jarduan', 'pos': 'BB', 'cards': ''},
        ],
    )
    by_name = {e.player: e for e in preflop_events(hand)}
    assert by_name['A'].category == 'limp'
    assert by_name['Jarduan'].category == 'bb_check'


def test_invalid_preflop_inputs_skip():
    hand = _hand(preflop=[{'pos': '', 'action': 'b', 'amount': 2}])
    assert preflop_events(hand) == []
    hand2 = _hand(preflop=[{'pos': 'CO', 'action': '', 'amount': 2}])
    assert preflop_events(hand2) == []


# ---------------------------------------------------------------------------
# Agregación de frecuencias
# ---------------------------------------------------------------------------

def test_stats_frequency_denominators():
    hands = [
        _hand('A', preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)]),
        _hand('B', preflop=[('CO', 'b', 2.5), ('BB', 'c', 2.5)]),
    ]
    stats = PreflopStats.from_hands(hands)
    assert stats.freq('Jarduan', 'open') == pytest.approx(1.0)   # 2/2 opp
    assert stats.freq('Jarduan', 'limp') == pytest.approx(0.0)   # 0/2 opp
    assert stats.opportunities('Villian', 'call_open') == 2
    assert stats.cats['Jarduan']['open'] == 2
    assert stats.cats['Villian']['fold_vs_open'] == 1
    assert stats.cats['Villian']['call_open'] == 1


def test_stats_mix_known_unknown():
    hands = [
        _hand('A', preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)]),
        _hand('B',
              preflop=[('CO', 'b', 2.5), ('BB', 'c', 2.5)],
              players=[
                  {'name': 'Jarduan', 'pos': 'CO', 'cards': '7h2d'},
                  {'name': 'Villian', 'pos': 'BB', 'cards': 'KsQs'},
              ]),
    ]
    stats = PreflopStats.from_hands(hands)
    # Villian: 1 mano desconocida (no_raise), 1 conocida
    assert stats.denoms['Villian']['facing_open'] == 2
    assert stats.known['Villian']['facing_open'] == 1


def test_stats_to_dict_and_report():
    hands = [_hand('A', preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)])]
    stats = PreflopStats.from_hands(hands)
    d = stats.to_dict()
    assert d['hands'] == 1
    assert 'Jarduan' in d['cats'] and d['cats']['Jarduan']['open'] == 1
    text = stats.report(players=['Jarduan', 'Villian'])
    assert 'Jarduan' in text
    assert 'Villian' in text


def test_load_hands_skips_garbage(tmp_path):
    p = tmp_path / 'db.jsonl'
    p.write_text(
        'not json\n'
        '{"streets":{}}\n'                              # sin players
        '{"players":[]}\n'                              # sin streets
        '{"hand_id":"OK","players":[],"streets":{}}\n', # válida
        encoding='utf-8')
    hands = load_hands(str(p))
    assert len(hands) == 1
    assert hands[0]['hand_id'] == 'OK'


def test_hero_names_default():
    assert 'Jarduan' in HERO_NAMES
    assert hand_known('Jarduan', '') is True
    assert hand_known('Villian', '') is False
    assert hand_known('Villian', 'KsQs') is True