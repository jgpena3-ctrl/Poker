"""Tests del extractor de observations (motor/observations.py)."""
import pytest

from motor.observations import (Observation, behavior_table, extract_hand,
                                extract_hands)


def _hand(**over):
    h = {
        'hand_id': 'T001',
        'players': [
            {'pos': 'BTN', 'name': 'X', 'stack': 100, 'cards': ''},
            {'pos': 'BB', 'name': 'Y', 'stack': 100, 'cards': ''},
            {'pos': 'UTG', 'name': 'Z', 'stack': 100, 'cards': ''},
        ],
        'streets': {},
    }
    h.update(over)
    return h


def _street(actions, board=None):
    d = {'actions': actions}
    if board:
        d['board'] = board
    return d


def test_pot_before_y_facing_preflop():
    hand = _hand(streets={'preflop': _street([
        {'pos': 'BTN', 'action': 'b', 'amount': 2.0},
        {'pos': 'BB', 'action': 'r', 'amount': 2.0},
        {'pos': 'BTN', 'action': 'c', 'amount': 4.0},
    ])})
    obs = extract_hand(hand)
    assert len(obs) == 3
    b1, b2, c1 = obs
    assert b1.pot_before == 0.0          # primera decisión: sin aportes
    assert b1.facing == 'none'
    assert b1.pot_type == 'SRP'
    assert b2.pot_before == 2.0
    assert b2.facing == 'bet'
    assert b2.action == 'r'
    assert b2.sizing == 1.0              # 2 / 2
    assert b2.pot_type == '3BP'
    assert c1.pot_before == 4.0
    assert c1.facing == 'raise'          # hay un raise que enfrentar
    assert c1.raised_before == 2         # raises previos: b + r


def test_initiator_cbet_se_etiqueta():
    hand = _hand(streets={
        'preflop': _street([{'pos': 'UTG', 'action': 'b', 'amount': 3.0},
                            {'pos': 'BB', 'action': 'c', 'amount': 2.0}]),
        'flop': _street([
            {'pos': 'UTG', 'action': 'b', 'amount': 4.0},
            {'pos': 'BB', 'action': 'c', 'amount': 4.0}],
            board=['5d', '6d', '9s']),
    })
    obs = [o for o in extract_hand(hand) if o.street == 'flop']
    utg_b, bb_c = obs
    assert bb_c.facing == 'cbet'         # el iniciador líder en flop
    assert utg_b.facing == 'none'
    assert bb_c.texture_class == 'two_tone'   # 5d,6d diamantes + pica
    assert utg_b.sizing == 4.0 / 5.0


def test_barrel_en_turn_con_otro_agresor():
    hand = _hand(streets={
        'preflop': _street([{'pos': 'BTN', 'action': 'b', 'amount': 1.0},
                            {'pos': 'BB', 'action': 'c', 'amount': 1.0}]),
        'flop': _street([{'pos': 'BTN', 'action': 'b', 'amount': 2.0},
                         {'pos': 'BB', 'action': 'f', 'amount': 0.0}],
                        board=['5d', '6d', '9s']),
        'turn': _street([{'pos': 'BB', 'action': 'b', 'amount': 3.0},
                         {'pos': 'BTN', 'action': 'c', 'amount': 3.0}],
                        board=['5d', '6d', '9s', '2c']),
    })
    obs = [o for o in extract_hand(hand) if o.street == 'turn']
    assert obs[0].facing == 'none'           # BB lidera: no hay apuesta aún
    assert obs[0].sizing == 3.0 / 4.0
    assert obs[1].facing == 'bet'
    assert obs[1].sizing is None             # el call no tiene sizing


def test_board_incompleto_no_revienta():
    hand = _hand(streets={
        'preflop': _street([{'pos': 'UTG', 'action': 'b', 'amount': 1.0}]),
        'flop': _street([{'pos': 'UTG', 'action': 'b', 'amount': 1.0}],
                        board=['5d']),      # recorder colgó 1 carta
    })
    obs = extract_hand(hand)
    assert obs[1].texture_class is None
    assert obs[1].board == '5d'


def test_board_acumulado_turn_y_river():
    # formato real de la DB: turn/river guardan solo la carta nueva
    hand = _hand(streets={
        'preflop': _street([{'pos': 'UTG', 'action': 'b', 'amount': 1.0},
                            {'pos': 'BB', 'action': 'c', 'amount': 1.0}]),
        'flop': _street([{'pos': 'UTG', 'action': 'b', 'amount': 2.0},
                         {'pos': 'BB', 'action': 'c', 'amount': 2.0}],
                        board=['5d', '6d', '9s']),
        'turn': _street([{'pos': 'BB', 'action': 'b', 'amount': 3.0},
                         {'pos': 'UTG', 'action': 'c', 'amount': 3.0}],
                        board=['2c']),
        'river': _street([{'pos': 'BB', 'action': 'b', 'amount': 4.0},
                          {'pos': 'UTG', 'action': 'c', 'amount': 4.0}],
                         board=['Qh']),
    })
    t = [o for o in extract_hand(hand) if o.street == 'turn']
    r = [o for o in extract_hand(hand) if o.street == 'river']
    assert t[0].board == '5d,6d,9s,2c'       # flop + carta del turn
    assert r[0].board == '5d,6d,9s,2c,Qh'     # acumulado completo
    assert t[0].texture_class is not None and r[0].texture_class is not None


def test_board_acumulado_no_colisiona():
    # el formato de boards completos (tests/simulado) no se toca
    hand = _hand(streets={
        'preflop': _street([{'pos': 'UTG', 'action': 'b', 'amount': 1.0}]),
        'turn': _street([{'pos': 'UTG', 'action': 'b', 'amount': 1.0}],
                        board=['5d', '6d', '9s', '2c']),
    })
    t = [o for o in extract_hand(hand) if o.street == 'turn']
    assert t[0].board == '5d,6d,9s,2c'
    # carta duplicada con el flop → no se acumula (se descarta aguas abajo)
    hand2 = _hand(streets={
        'preflop': _street([{'pos': 'UTG', 'action': 'b', 'amount': 1.0}]),
        'flop': _street([{'pos': 'UTG', 'action': 'b', 'amount': 1.0}],
                        board=['5d', '6d', '9s']),
        'turn': _street([{'pos': 'BB', 'action': 'b', 'amount': 1.0}],
                        board=['5d']),
    })
    t2 = [o for o in extract_hand(hand2) if o.street == 'turn']
    assert t2[0].board == '5d'               # duplicada: sin acumular


def test_spr_y_stack_efectivo():
    hand = _hand(streets={
        'preflop': _street([{'pos': 'UTG', 'action': 'b', 'amount': 3.0},
                            {'pos': 'BTN', 'action': 'b', 'amount': 3.0}]),
    })
    btn = [o for o in extract_hand(hand) if o.pos == 'BTN'][0]
    assert btn.stack_effective == 100.0    # aún no ha aportado
    assert btn.spr == 100.0 / 3.0


def test_hallazgo_heros():
    hand = _hand(players=[
        {'pos': 'BTN', 'name': 'Jarduan', 'stack': 100, 'cards': 'JdTd'},
        {'pos': 'BB', 'name': 'X', 'stack': 100, 'cards': ''},
    ], streets={'preflop': _street([
        {'pos': 'BTN', 'action': 'b', 'amount': 2.0},
        {'pos': 'BB', 'action': 'c', 'amount': 2.0}])})
    obs = extract_hand(hand)
    assert obs[0].kind == 'hero' and obs[0].hand_known
    assert obs[1].kind == 'villain' and not obs[1].hand_known


def test_behavior_table_filtra_min_n_y_day():
    o1 = Observation(hand_id='h1', street='flop', player='A',
                     kind='villain', pos='BTN', action='b', amount=5.0,
                     sizing=1.0, pot_before=5.0, stack_effective=100,
                     spr=20.0, pot_type='SRP', players_active=2, board='',
                     texture_class='rainbow', facing='none', raised_before=0,
                     preflop_sequence='BTN:b', hand_known=False, cards='')
    o2 = Observation(**{**vars(o1), 'hand_id': 'h2', 'action': 'c',
                        'amount': 4.0, 'sizing': None, 'player': 'B'})
    o3 = Observation(**{**vars(o1), 'hand_id': 'h3', 'action': 'f',
                       'amount': 0.0, 'sizing': None, 'player': 'B'})
    t = behavior_table([o1, o2, o3], {'A': 'LAG', 'B': 'LAG'}, min_n=2)
    key = ('LAG', 'flop', 'rainbow', 'none')
    assert key in t
    cellA = t[key]
    assert cellA['n'] == 3 and cellA['b'] == round(1 / 3, 3)
    assert cellA['sizing_mean'] == round(1.0 / 1, 3)
    t2 = behavior_table([o1, o2, o3], {'A': 'LAG', 'B': 'LAG'}, min_n=5)
    assert not t2