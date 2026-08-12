"""Test de motor/profile.py — perfiles de jugador (§5.4-§5.6)."""
import pytest

from motor.profile import (PlayerProfile, Profiles, STAT_BINS, beta_mass,
                           load_base_rates)
from motor.stats import TransitionStats


def _hand(preflop=None, flop=None, hid='P_0001', players=None):
    players = players or [
        {'name': 'Jarduan', 'pos': 'CO', 'cards': ''},
        {'name': 'Villian', 'pos': 'BB', 'cards': ''},
    ]
    streets = {'preflop': {'actions': preflop or []}}
    if flop is not None:
        streets['flop'] = {'actions': flop, 'board': []}
    return {'hand_id': hid, 'players': players, 'streets': streets,
            'showdown': {}}


def make_profile(name, counts, stats=None, n=50):
    """counts: {stat: (opp, act)}; stats opcional para omega."""
    if stats is None:
        stats = {s: (a / o) for s, (o, a) in counts.items() if o}
    return PlayerProfile(player=name, n=n, stats=stats, counts=counts)


# --- beta_mass -------------------------------------------------------

def test_beta_mass_matches_intuition():
    # 10/10 llamadas: la masa se concentra en la tasa real (100%)
    above = beta_mass(10, 10, 0.8)              # P(rate >= 0.8)
    assert 0.0 < above <= 1.0
    # 1/1 muestra diminuta: capacidad de sorpresa -> probabilidades pequeñas
    small = beta_mass(1, 1, 0.95)
    assert small < 0.5
    assert beta_mass(100, 99, 0.9) > beta_mass(10, 9, 0.9)


# --- buckets ---------------------------------------------------------

def test_bucket_mode_large_sample():
    p = make_profile('x', {'vpip': (300, 240), 'pfr': (300, 180)},
                     stats={'vpip': 0.8, 'pfr': 0.6})
    assert p.bins['vpip'] == 'loose'        # 80% -> loose bin
    assert p.bins['pfr'] == 'high'          # 60% -> high


def test_bucket_small_sample_reverts_to_prior():
    p = make_profile('x', {'vpip': (2, 1)}, stats={'vpip': 0.5})
    assert p.bins['vpip'] != 'n/a'
    assert p.confidence < 0.85   # muestra diminuta: posterior poco firme


def test_no_opps_na():
    p = make_profile('x', {'vpip': (0, 0), 'pfr': (2, 1)}, )
    assert p.bins['vpip'] == 'n/a'
    assert p.bins['pfr'] != 'n/a'


# --- etiqueta --------------------------------------------------------

def test_archetypes():
    cases = [
        ({'vpip': 'tight', 'pfr': 'high'}, 'TAG'),
        ({'vpip': 'tight', 'pfr': 'low'}, 'Nit'),
        ({'vpip': 'loose', 'pfr': 'low'}, 'Loose-passive'),
        ({'vpip': 'loose', 'pfr': 'high'}, 'LAG'),
        ({'vpip': 'mid', 'pfr': 'low'}, 'Passive-reg'),
    ]
    for bins, expected in cases:
        b = dict(bins)
        b.setdefault('b3', 'n/a')
        assert _archetype_of(b) == expected


def _archetype_of(bins):
    from motor.profile import _archetype
    return _archetype(bins)


# --- confianza / fiabilidad ------------------------------------------

def test_confidence_grows_with_sample():
    small = make_profile('a', {'vpip': (20, 12)}, stats={'vpip': 0.6}, n=20)
    big = make_profile('b', {'vpip': (400, 240)}, stats={'vpip': 0.6}, n=400)
    assert big.confidence > small.confidence


def test_reliability_bands():
    assert make_profile('p', {'vpip': (1, 1)}, n=10).reliability() == 'probable'
    assert make_profile('p', {'vpip': (1, 1)}, n=100).reliability() == 'confiable'
    assert make_profile('p', {'vpip': (1, 1)}, n=5000).reliability() == 'individual'


# --- omega -----------------------------------------------------------

def test_omega_ratio_and_clamp():
    rates = {'OR_UTG': 0.12}
    p = make_profile('x', {'vpip': (10, 5)}, stats={'pfr': 0.31})
    assert p.omega('OR_UTG', rates) == pytest.approx(0.31 / 0.12)
    p_high = make_profile('x', {'vpip': (1, 1)}, stats={'pfr': 0.9})
    assert p_high.omega('OR_UTG', rates) <= 4.0          # clamp alto
    p_low = make_profile('x', {'vpip': (1, 1)}, stats={'pfr': 0.01})
    assert p_low.omega('OR_UTG', rates) >= 0.25          # clamp bajo
    assert p_low.omega('OR_UTG', {}) is None             # sin tasa base


def test_stat_for_table():
    from motor.profile import _stat_for_table
    assert _stat_for_table('OR_UTG') == 'pfr'
    assert _stat_for_table('3B_CO_vs_BTN') == 'b3'
    assert _stat_for_table('Call_OR_BB_vs_SB') == 'pfr'
    assert _stat_for_table('CBET_FLOP') == 'cbet'


# --- integración -------------------------------------------------------

def test_from_hands_and_report():
    hands = [
        {'hand_id': 'A', 'players': [
            {'name': 'Jarduan', 'pos': 'CO', 'cards': ''},
            {'name': 'Villian', 'pos': 'BB', 'cards': ''}],
         'streets': {'preflop': {'actions': [('CO', 'b', 2.5), ('BB', 'f', 0)]}},
         'showdown': {}},
        {'hand_id': 'B', 'players': [
            {'name': 'Jarduan', 'pos': 'CO', 'cards': 'KhQh'},
            {'name': 'Villian', 'pos': 'BB', 'cards': ''}],
         'streets': {'preflop': {'actions': [('CO', 'c', 1.0), ('BB', 'x', 0)]}},
         'showdown': {}},
    ]
    profs = Profiles.from_hands(hands, matrices_path=None)
    jp = profs.profiles['Jarduan']
    assert jp.hero is True
    assert jp.n == 2
    assert 'vpip' in jp.stats and 0.5 <= jp.stats['vpip'] <= 1.0
    text = profs.report(players=['Jarduan'])
    assert 'Jarduan' in text
    d = profs.to_dict()
    assert 'Jarduan' in d and 'label' in d['Jarduan']


def test_base_rates_real_matrix():
    rates = load_base_rates()
    assert rates['OR_UTG'] > 0.10
    assert rates['OR_BTN'] > rates['OR_UTG']
    assert abs(sum(1 for v in rates.values() if v > 0)) > 50


def test_omega_integration_real_matrix():
    rates = load_base_rates()
    p = make_profile('z', {'vpip': (1, 1)}, stats={'pfr': 0.25})
    w = p.omega('OR_UTG', rates)
    assert w is not None and 0.25 <= w <= 4.0