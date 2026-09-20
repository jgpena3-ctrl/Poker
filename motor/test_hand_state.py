"""Test de motor/hand_state.py — clasificación del hand_role (§1/§4-§6)."""
from motor.hand_state import classify, range_advantage


# ---------------------------------------------------------------------------
# strength y draw
# ---------------------------------------------------------------------------

def test_classify_straight_flush_draw_combo():
    hs = classify(['7s', '6s'], ['9s', '8s', '2d'])
    assert hs.strength == 'HIGH_CARD'
    assert hs.draw == 'COMBO'          # OESD + FD
    assert hs.role == 'STRONG_DRAW'


def test_classify_oesd_only():
    hs = classify(['7d', '6c'], ['9s', '8s', '2d'])
    assert hs.strength == 'HIGH_CARD'
    assert hs.draw == 'OESD'
    assert hs.role == 'STRONG_DRAW'


def test_classify_gutshot():
    # 6-5 frente a 9-8: solo el 7 completa → gutshot
    hs = classify(['6s', '5s'], ['9h', '8h', '2d'])
    assert hs.draw == 'GUTSHOT'
    assert hs.role == 'WEAK_DRAW'


def test_classify_wheel_oesd():
    # 4-5 con 2-3 en mesa: A o 6 completan → OESD (A baja cuenta)
    hs = classify(['5s', '4s'], ['2h', '3c', '9d'])
    assert hs.draw == 'OESD'


def test_classify_backdoor_flush():
    hs = classify(['As', 'Ks'], ['Qs', '7d', '2c'])
    assert hs.strength == 'HIGH_CARD'
    assert hs.draw == 'BDFD'
    assert hs.role == 'WEAK_DRAW'


def test_classify_air():
    hs = classify(['As', 'Kd'], ['Qh', '7s', '2c'])
    assert hs.strength == 'HIGH_CARD'
    assert hs.draw == 'NONE'
    assert hs.role == 'AIR'


def test_classify_pair_is_medium():
    hs = classify(['Ac', 'Ad'], ['Qh', '7s', '2c'])
    assert hs.strength == 'PAIR'
    assert hs.role == 'MEDIUM'


def test_classify_two_pair_value():
    hs = classify(['Qh', '7d'], ['Qs', '7s', '2c'])
    assert hs.strength == '2PAIR'
    assert hs.role == 'VALUE'


def test_classify_set_strong_value():
    hs = classify(['9h', '9d'], ['9s', '8s', '7d'])
    assert hs.strength == 'SET'
    assert hs.role == 'STRONG_VALUE'
    assert hs.draw == 'NONE'


def test_classify_flush_strong():
    hs = classify(['As', 'Ks'], ['7s', '3s', '8s'])
    assert hs.strength == 'FLUSH'
    assert hs.role == 'STRONG_VALUE'


def test_nut_advantage_approx():
    assert classify(['As', 'Ks'], ['Qh', '7d', '2c']).nut_advantage() == 'VILLAIN'
    assert classify(['As', '9h'], ['Qh', '7d', '2c']).nut_advantage() == 'VILLAIN'
    assert classify(['7d', '6c'], ['9s', '8s', '2d']).nut_advantage() == 'NEUTRAL'


def test_flush_beats_nut_approx():
    assert classify(['Ah', 'Kh'], ['Qh', '7h', '2h']).nut_advantage() == 'HERO'


# ---------------------------------------------------------------------------
# range_advantage por equity
# ---------------------------------------------------------------------------

def test_range_advantage():
    assert range_advantage(0.60) == 'HERO'
    assert range_advantage(0.45) == 'NEUTRAL'
    assert range_advantage(0.50) == 'NEUTRAL'
    assert range_advantage(0.40) == 'VILLAIN'