"""Test de motor/stats.py — estadísticas de transición (§5.2)."""
import pytest

from motor.stats import TransitionStats


def _hand(preflop=None, flop=None, turn=None, river=None, players=None,
          hid='S_0001'):
    players = players or [
        {'name': 'Jarduan', 'pos': 'CO', 'cards': 'KhQh'},
        {'name': 'Villian', 'pos': 'BB', 'cards': ''},
    ]
    streets = {'preflop': {'actions': preflop or []}}
    for key, acts in (('flop', flop), ('turn', turn), ('river', river)):
        if acts is not None:
            streets[key] = {'actions': acts, 'board': []}
    return {'hand_id': hid, 'players': players, 'streets': streets,
            'showdown': {}}


# ---------------------------------------------------------------------------
# Preflop
# ---------------------------------------------------------------------------

def test_vpip_pfr_formulas():
    hands = [
        _hand(preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)]),
        _hand(preflop=[('CO', 'c', 1.0), ('BB', 'x', 0)]),  # limp walk
    ]
    agg = TransitionStats.from_hands(hands)
    j = agg.players['Jarduan']
    assert j.freq('vpip') == pytest.approx(1.0)   # 2/2 metió dinero
    assert j.freq('pfr') == pytest.approx(0.5)    # 1/2 fue raise
    v = agg.players['Villian']
    assert v.freq('vpip') == pytest.approx(0.0)   # nunca mete dinero
    assert v.freq('pfr') == pytest.approx(0.0)


def test_3bet_4bet_denominators():
    hand = _hand(preflop=[
        ('UTG', 'b', 2.5), ('CO', 'r', 8.0), ('BB', 'f', 0),
    ], players=[
        {'name': 'A', 'pos': 'UTG', 'cards': ''},
        {'name': 'Jarduan', 'pos': 'CO', 'cards': 'AhKh'},
        {'name': 'Villian', 'pos': 'BB', 'cards': ''},
    ])
    agg = TransitionStats.from_hands([hand])
    j = agg.players['Jarduan']
    assert j.freq('b3') == pytest.approx(1.0)     # 3bet inmediato
    v = agg.players['Villian']
    assert v.freq('b3') is None                   # no enfrenta el open
    assert v.freq('b4') == pytest.approx(0.0)     # facing_3bet, se dobla


def test_hero_flag():
    agg = TransitionStats.from_hands([
        _hand(preflop=[('CO', 'b', 2.5), ('BB', 'c', 2.5)])])
    assert agg.players['Jarduan'].hero is True
    assert agg.players['Villian'].hero is False


# ---------------------------------------------------------------------------
# Postflop: iniciativa
# ---------------------------------------------------------------------------

def test_cbet_and_fold_to_cbet():
    hand = _hand(
        preflop=[('CO', 'b', 2.5), ('BB', 'c', 2.5)],
        flop=[('CO', 'b', 3.0), ('BB', 'f', 0)],
    )
    agg = TransitionStats.from_hands([hand])
    j, v = agg.players['Jarduan'], agg.players['Villian']
    assert j.freq('cbet') == pytest.approx(1.0)
    assert v.freq('f2cb') == pytest.approx(1.0)


def test_no_cbet_when_donk_lead():
    # el BB lidera el flop sin ser agresor preflop -> no es cbet
    hand = _hand(
        preflop=[('CO', 'c', 1.0), ('BB', 'x', 0)],
        flop=[('BB', 'b', 2.0), ('CO', 'f', 0)],
    )
    agg = TransitionStats.from_hands([hand])
    v = agg.players['Villian']
    assert v.freq('cbet') is None       # su b no cuenta como c-bet
    assert v.freq('f2cb') is None       # y el fold de CO no es facing cbet
    j = agg.players['Jarduan']
    assert j.freq('f2cb') is None


def test_turn_barrel_and_fold_to_barrel():
    hand = _hand(
        preflop=[('CO', 'b', 2.5), ('BB', 'c', 2.5)],
        flop=[('CO', 'b', 3.0), ('BB', 'c', 3.0)],
        turn=[('CO', 'b', 8.0), ('BB', 'f', 0)],
    )
    agg = TransitionStats.from_hands([hand])
    j, v = agg.players['Jarduan'], agg.players['Villian']
    assert j.freq('bar') == pytest.approx(1.0)
    assert v.freq('f2bar') == pytest.approx(1.0)


def test_river_bet_initiative():
    hand = _hand(
        preflop=[('CO', 'b', 2.5), ('BB', 'c', 2.5)],
        flop=[('CO', 'b', 3.0), ('BB', 'x', 0)],
        turn=[('CO', 'b', 7.0), ('BB', 'f', 0)],
    )
    agg = TransitionStats.from_hands([hand])
    j = agg.players['Jarduan']
    assert j.freq('bar') == pytest.approx(1.0)
    assert j.freq('rb') is None          # no llegó a river


def test_initiative_passes_when_other_bets():
    # Villian hi erea flop y lider en turn: CO deja de ser el initiator
    hand = _hand(
        preflop=[('CO', 'b', 2.5), ('BB', 'c', 2.5)],
        flop=[('CO', 'b', 3.0), ('BB', 'r', 9.0), ('CO', 'f', 0)],
        turn=[('BB', 'b', 12.0)],
    )
    agg = TransitionStats.from_hands([hand])
    v = agg.players['Villian']
    assert v.freq('bar') == pytest.approx(1.0)   # iniciativa tras el check-raise
    j = agg.players['Jarduan']
    assert j.freq('bar') is None


def test_multiway_facing_both():
    hand = _hand(
        preflop=[('CO', 'b', 2.5), ('BTN', 'c', 2.5), ('BB', 'c', 2.5)],
        flop=[('CO', 'b', 3.0), ('BTN', 'c', 3.0), ('BB', 'f', 0)],
        players=[
            {'name': 'Jarduan', 'pos': 'CO', 'cards': ''},
            {'name': 'BTNx', 'pos': 'BTN', 'cards': ''},
            {'name': 'Villian', 'pos': 'BB', 'cards': ''},
        ],
    )
    agg = TransitionStats.from_hands([hand])
    j = agg.players['Jarduan']
    assert j.freq('cbet') == pytest.approx(1.0)
    assert agg.players['BTNx'].freq('c2cb') == pytest.approx(1.0)
    assert agg.players['Villian'].freq('f2cb') == pytest.approx(1.0)


# --- WTSD / W$SD ------------------------------------------------------------

def test_wtsd_wsd_showdown():
    hand = {
        'hand_id': 'S_2',
        'players': [
            {'name': 'Jarduan', 'pos': 'CO', 'cards': 'KhQh'},
            {'name': 'Villian', 'pos': 'BB', 'cards': '7d7c'},
        ],
        'streets': {'preflop': {'actions': [('CO', 'b', 2.5), ('BB', 'c', 2.5)]}},
        'showdown': {'winner1': 'CO (Jarduan)'},
    }
    agg = TransitionStats.from_hands([hand])
    j, v = agg.players['Jarduan'], agg.players['Villian']
    assert j.freq('wtsd') is None      # hero: sus cartas no indican llegada
    assert v.freq('wtsd') == pytest.approx(1.0)     # villano: revelado
    assert v.freq('wsd') == pytest.approx(0.0)     # perdió


def test_wtsd_requires_showdown_section():
    # sin sección showdown en la mano: nadie "llegó al showdown"
    hand = _hand(preflop=[('CO', 'b', 2.5), ('BTN', 'c', 2.5)], players=[
        {'name': 'A', 'pos': 'CO', 'cards': ''},
        {'name': 'Villian', 'pos': 'BTN', 'cards': '9s9d'},
    ])
    agg = TransitionStats.from_hands([hand])
    v = agg.players['Villian']
    assert v.freq('wtsd') is None


def test_wtsd_no_showdown_winner_is_zero():
    # si hay showdown pero el jugador no se revela: 0 llegar
    hand = {
        'hand': 'S_3',
        'players': [
            {'name': 'A', 'pos': 'CO', 'cards': ''},
            {'name': 'Villian', 'pos': 'BB', 'cards': ''},
        ],
        'streets': {'preflop': {'actions': [('CO', 'b', 2.5), ('BB', 'x', 0)]}},
        'showdown': {'winner1': 'CO (A)'},
    }
    agg = TransitionStats.from_hands([hand])
    v = agg.players['Villian']
    assert v.freq('wtsd') == pytest.approx(0.0)


def test_wtsd_survivorship_respect():
    # Villain no llega al flop (fold preflop): ni oportunidad de WTSD
    hands = [
        _hand(preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)]),
    ]
    agg = TransitionStats.from_hands(hands)
    v = agg.players['Villian']
    assert v.freq('wtsd') is None       # agility: 0
    assert v.freq('vpip') == pytest.approx(0.0)


# --- bordes ----------------------------------------------------------

def test_empty_flops_no_cbet_noise():
    hand = _hand(preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)])
    agg = TransitionStats.from_hands([hand])
    j = agg.players['Jarduan']
    assert j.freq('cbet') is None
    assert j.freq('f2cb') is None


def test_report_and_to_dict():
    agg = TransitionStats.from_hands([
        _hand(preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)])])
    text = agg.report()
    assert 'PLAYER' in text and 'Jarduan' in text
    d = agg.to_dict()
    assert d['Jarduan']['stats']['vpip'] == [1, 1]
    assert d['Villian']['hero'] is False