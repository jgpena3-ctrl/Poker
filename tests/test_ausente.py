import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'recorder'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from recorder_live import LiveRecorder, PLAYER_IDS

def frame(btn='p1', states=None, stakes=None, bets=None, com=None, pot=3.0):
    st = {'btn': btn, 'pot': pot, 'community': com or []}
    for p in PLAYER_IDS:
        st[f'{p}_state'] = (states or {}).get(p)
        st[f'{p}_stake'] = (stakes or {}).get(p)
        st[f'{p}_bet'] = (bets or {}).get(p, None)
    return st

log = lambda *a, **k: None

# ---------------- TEST A: hand start with hero already 'ausente' ----------------
r = LiveRecorder()
b = 0
# btn=p1 -> p2=SB p3=BB p4=UTG p5=MP hero=CO p1=BTN
s = frame(states={'p4': 'retirarse', 'p5': 'retirarse', 'hero': 'ausente'},
          stakes={'hero': 21.5, 'p1': 50.0, 'p2': 40.0, 'p3': 30.0,
                  'p4': 60.0, 'p5': 75.0},
          bets={'p2': 1.0, 'p3': 2.0})
r._ensure_hand_id()
r._assign_cards_by_name(s)
r.start_hand(s)
r.process_frame(s, None, log=log)
a = r.hand['streets']['preflop']['actions']
print('TEST A acciones preflop:', [(x['pos'], x['action'], x['amount']) for x in a])
folds = [x['pos'] for x in a if x['action'] == 'f']
assert folds == ['UTG', 'MP', 'CO'], f'folds esperados UTG,MP,CO -> {folds}'
assert 'CO' in r._folded_positions, 'hero (CO) debe estar marcado como folded'
print('TEST A OK: hero ausente al inicio -> fold CO registrado')

# ---------------- TEST B: hero goes 'ausente' mid-hand (flop) ----------------
# 3 jugadores en mano (hero, p1, p2): el fold de hero NO debe finalizar la mano
r2 = LiveRecorder()
s1 = frame(states={'p1': 'subir', 'hero': 'igualar'}, stakes={'hero': 19.5, 'p1': 46.5, 'p2': 40.0},
           bets={'p1': 3.5, 'hero': 3.5, 'p2': 1.0}, pot=7.0)
r2._ensure_hand_id()
r2._assign_cards_by_name(s1)
r2.start_hand(s1)
r2.process_frame(s1, None, log=log)
assert r2.hand is not None, 'mano no iniciada'
r2.detect_street_change({'btn': 'p1', 'community': [{'rank': '2', 'suit': 'd'}, {'rank': 'J', 'suit': 's'}, {'rank': '4', 'suit': 's'}]})
s2 = frame(states={'p1': 'pasar', 'hero': 'ausente'}, stakes={'hero': 19.5, 'p1': 46.5, 'p2': 40.0},
           bets={'p1': None, 'hero': None, 'p2': 1.0}, com=[{'rank': '2', 'suit': 'd'}, {'rank': 'J', 'suit': 's'}, {'rank': '4', 'suit': 's'}], pot=7.0)
r2.detect_street_change(s2)
r2.process_frame(s2, None, log=log)
assert r2.hand is not None, 'mano no debe finalizar con 2 jugadores vivos'
a2 = r2.hand['streets']['flop']['actions']
a_pf = r2.hand['streets']['preflop']['actions']
print('TEST B acciones preflop:', [(x['pos'], x['action'], x['amount']) for x in a_pf])
print('TEST B acciones flop:', [(x['pos'], x['action'], x['amount']) for x in a2])
assert any(x['pos'] == 'CO' and x['action'] == 'f' for x in a_pf), 'hero debe foldearse (preflop, detección por lag)'
print('TEST B OK: ausente mid-hand -> fold registrado')

# ---------------- TEST C: finalización automática de manos ----------------
def make_hand(states, stakes, bets, pot=3.0):
    r = LiveRecorder()
    s = frame(states=states, stakes=stakes, bets=bets, pot=pot)
    r._ensure_hand_id()
    r.start_hand(s)
    return r, s

# C1: check-check con 4 folds NO finaliza (2 vivos)
r, s = make_hand(
    states={'hero': 'pasar', 'p1': 'pasar',
            'p2': 'retirarse', 'p3': 'retirarse', 'p4': 'retirarse', 'p5': 'retirarse'},
    stakes={'hero': 20.0, 'p1': 20.0, 'p2': 0.0, 'p3': 0.0, 'p4': 0.0, 'p5': 0.0},
    bets={'hero': 2.0, 'p1': 2.0})
for pos in ['SB', 'BB', 'UTG', 'MP']:
    r._folded_positions.add(pos)
assert not r._is_hand_over(s), 'C1: check-check no debe finalizar'
print('TEST C1 OK: check-check no finaliza')

# C2: flicker 'inactivo' de un contendiente NO finaliza (bug reportado)
s['hero_state'] = 'inactivo'
assert not r._is_hand_over(s), 'C2: flicker inactivo no debe finalizar'
print('TEST C2 OK: flicker inactivo no finaliza')

# C3: bet-call NO finaliza
s2 = dict(s)
s2['hero_state'] = 'apostar'
s2['p1_state'] = 'igualar'
assert not r._is_hand_over(s2), 'C3: bet-call no debe finalizar'
print('TEST C3 OK: bet-call no finaliza')

# C4: all-in cuenta como jugador en juego -> NO finaliza
r3, s3 = make_hand(
    states={'p2': 'retirarse', 'p3': 'retirarse', 'p4': 'retirarse', 'p5': 'retirarse'},
    stakes={'hero': 0.0, 'p1': 20.0, 'p2': 0.0, 'p3': 0.0, 'p4': 0.0, 'p5': 0.0},
    bets={'hero': 18.0, 'p1': 2.0})
for pos in ['SB', 'BB', 'UTG', 'MP']:
    r3._folded_positions.add(pos)
r3._allin_players.add('hero')
assert not r3._is_hand_over(s3), 'C4: all-in + 1 vivo no debe finalizar'
print('TEST C4 OK: all-in no descuenta')

# C5: todos menos 1 con fold real -> finaliza (incluso con all-in restante)
s4 = dict(s3)
s4['p1_state'] = 'retirarse'
s4['p1_stake'] = None
s4['p1_bet'] = None
assert r3._is_hand_over(s4), 'C5: 5 folds + all-in debe finalizar'
print('TEST C5 OK: todos menos 1 fold -> finaliza')

# C6: mano corta con silla vacía en showdown NO finaliza
r6, s6 = make_hand(
    states={'hero': 'retirarse', 'p1': 'retirarse', 'p2': 'pasar', 'p3': 'pasar', 'p4': 'retirarse'},
    stakes={'hero': 0.0, 'p1': 0.0, 'p2': 20.0, 'p3': 20.0, 'p4': 0.0},
    bets={'hero': None, 'p1': None, 'p2': 2.0, 'p3': 2.0, 'p4': None})
for pos in ['CO', 'BTN', 'UTG']:
    r6._folded_positions.add(pos)
assert not r6._is_hand_over(s6), 'C6: mano corta check-check no debe finalizar'
print('TEST C6 OK: silla vacía no cuenta como fold')

print('ALL TESTS PASSED')