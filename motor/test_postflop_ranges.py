"""test_postflop_ranges.py — PostflopRangeModel (P(A|H, street, facing, perfil))."""
import numpy as np
import pytest

from motor import postflop_ranges as pf
from motor import ranges as rng


def _hand(hid, vil_action, cards=None, vl_amt=0.0):
    """Mano sintética: Hero (BTN) abre preflop y apuesta el flop; `Rival`
    (BB) responde con `vil_action` (f/c/b/r) con cartas conocidas."""
    return {
        'hand_id': hid,
        'players': [
            {'pos': 'BTN', 'name': 'Hero', 'cards': ['Jd', 'Jh']},
            {'pos': 'BB', 'name': 'Rival', 'cards': cards or []},
        ],
        'streets': {
            'preflop': {'actions': [
                {'pos': 'BTN', 'action': 'r', 'amount': 2.5},
                {'pos': 'BB', 'action': 'c', 'amount': 2.0},
            ]},
            'flop': {
                'board': ['Qh', '7s', '2c'],
                'actions': [
                    {'pos': 'BTN', 'action': 'b', 'amount': 3.0},
                    {'pos': 'BB', 'action': vil_action, 'amount': vl_amt},
                ],
            },
        },
    }


def test_strength_buckets_top_es_AA():
    from motor.cards import card_id

    board = [card_id('Qh'), card_id('7s'), card_id('2c')]
    scores, buckets = pf._strength_buckets(board)
    assert buckets.shape == (rng.N_COMBOS,)
    assert set(buckets) <= set(range(5))
    aa = [i for i, l in enumerate(rng.HAND_LABELS)
          if l[0] == 'A' and l[2] == 'A']
    assert buckets[aa[0]] == 4                  # AA → bucket más alto
    qh = [i for i, l in enumerate(rng.HAND_LABELS) if l.startswith('Qh')]
    assert buckets[qh[0]] == 0                  # ilegal del board → inerte


def test_from_hands_buckets_y_oportunidades():
    # Rival siempre 72o (flop seco Q72) y siempre fold: 8 oportunidades
    hands = [_hand(f'h{i}', 'f', cards=['7c', '2d']) for i in range(8)]
    m = pf.PostflopRangeModel.from_hands(hands, labels={'Rival': 'Timmy'})
    n = sum(v for k, v in m.opp.items()
            if k[0] == 'Timmy' and k[1] == 'flop')
    assert n == 8


def test_p_action_sin_datos_prior_oracle():
    hands = [_hand('x', 'f') for _ in range(8)]
    m = pf.PostflopRangeModel.from_hands(hands, labels={'Rival': 'Timmy'})
    prior = m._prior('Timmy', 'flop', 'bet')
    assert prior is not None
    for a in ('x', 'b', 'c', 'f', 'r'):
        assert 0.0 <= m.p_action('Timmy', 'flop', 'bet', 1, a) <= 1.0


def test_board_ids_carta_duplicada_es_none():
    from motor.cards import card_id

    bid = pf._board_ids('5d,6d,9s,5d')          # '5d' repetida: roto
    assert bid is None
    ok = pf._board_ids('5d,6d,9s,2c')
    assert ok is not None and len(ok) == 4
    assert ok[0] == card_id('5d')


def test_prob_vec_forma_y_valores():
    # rival: folds con 69o (aire -> bucket 0), calls con AA (bucket 4):
    # la evidencia debe hacer P(call) dependiente de la fuerza de la mano
    hands = [_hand('x', 'c', cards=['Ac', 'Ad'])] * 1
    hands += [_hand('y', 'f', cards=['6h', '9d'])] * 3
    m = pf.PostflopRangeModel.from_hands(hands, labels={'Rival': 'Timmy'})
    vc = m.prob_vec('Timmy', 'flop', 'cbet', ['Qh', '7s', '2c'], 'c')
    vf = m.prob_vec('Timmy', 'flop', 'cbet', ['Qh', '7s', '2c'], 'f')
    assert vc.shape == (rng.N_COMBOS,)
    assert np.all(vc >= 0.0) and np.all(vc <= 1.0)
    aa = [i for i, l in enumerate(rng.HAND_LABELS)
          if l[0] == 'A' and l[2] == 'A'][0]
    air = [i for i, l in enumerate(rng.HAND_LABELS)
           if l in ('6h9d', '6d9c', '6c9s', '6s9h')][0]
    assert float(vc[aa]) >= 0.5          # AA llama fuerte
    assert float(vc[air]) < 0.2          # el aire apenas llama
    assert float(vf[air]) > float(vf[aa])
    assert float(vc.sum()) > 0.0 and float(vf.sum()) > 0.0


def test_prob_vec_rango_estado_update():
    # 3 folds débiles + 3 calls de AA: P(fold)~0.5 para todo el rango
    hands = [_hand('x', 'c', cards=['Ac', 'Ad']) for _ in range(3)]
    hands += [_hand('y', 'f', cards=['6h', '9d']) for _ in range(3)]
    m = pf.PostflopRangeModel.from_hands(hands, labels={'Rival': 'Tim'})
    v = m.prob_vec('Tim', 'flop', 'cbet', ['Qh', '7s', '2c'], 'f')
    rs = rng.uniform_range(cards=[])
    pre = float(rs.reach.sum())
    rs.update(v)
    assert float(rs.reach.sum()) < pre       # P(fold) reduce la masa
    assert float(rs.reach.sum()) > pre * 0.3  # y no la colapsa a 0


def test_consistencia_masa_update():
    """Pegar7 §14.3: el update conserva la masa por línea: la masa que se
    transfiere a la rama + la que queda fuera = masa inicial."""
    hands = [_hand('x', 'c', cards=['Ac', 'Ad']) for _ in range(3)]
    hands += [_hand('y', 'f', cards=['6h', '9d']) for _ in range(3)]
    m = pf.PostflopRangeModel.from_hands(hands, labels={'Rival': 'Tim'})
    vc = m.prob_vec('Tim', 'flop', 'cbet', ['Qh', '7s', '2c'], 'c')
    vf = m.prob_vec('Tim', 'flop', 'cbet', ['Qh', '7s', '2c'], 'f')

    rs = rng.uniform_range(cards=['Jd', 'Jh'])          # blockers reales
    pre = float(rs.reach.sum())
    rs_c = rng.uniform_range(cards=['Jd', 'Jh'])
    rs_c.update(vc)
    masa_c = float(rs_c.reach.sum())
    residuo = float((rs.reach * (1.0 - vc)).sum())
    assert abs(masa_c + residuo - pre) < 1e-2           # conservación
    assert 0.0 <= masa_c <= pre                          # P<=1, ≥0

    rs_f = rng.uniform_range(cards=['Jd', 'Jh'])
    rs_f.update(vf)
    masa_f = float(rs_f.reach.sum())
    assert abs(masa_f + float((rs.reach * (1.0 - vf)).sum()) - pre) < 1e-2
    assert masa_f < pre

    # sin update: masa intacta
    rs0 = rng.uniform_range(cards=['Jd', 'Jh'])
    assert float(rs0.reach.sum()) == pre


def test_prob_vec_suma_por_combo_estable():
    """Sanity del modelo: las P de acciones excluyentes del mismo facing
    deben sumar ≈1 por combo (se estiman por separado; la mayoría debe
    caer en [0.9, 1.1])."""
    hands = [_hand('x', 'c', cards=['Ac', 'Ad']) for _ in range(3)]
    hands += [_hand('y', 'f', cards=['6h', '9d']) for _ in range(3)]
    m = pf.PostflopRangeModel.from_hands(hands, labels={'Rival': 'Tim'})
    board = ['Qh', '7s', '2c']
    vals = np.zeros((rng.N_COMBOS, 5), dtype=np.float32)
    for i, a in enumerate(('x', 'b', 'c', 'f', 'r')):
        vals[:, i] = m.prob_vec('Tim', 'flop', 'cbet', board, a)
    s = vals.sum(axis=1)
    ok = float(((s > 0.9) & (s < 1.1)).mean())
    assert ok > 0.8
    # con más evidencia la suma se acerca a 1: celdas con datos dominan
    assert float(vals.max()) <= 1.0


def test_save_load_roundtrip(tmp_path):
    hands = [_hand('x', 'f', cards=['7c', '2d']) for _ in range(4)]
    m = pf.PostflopRangeModel.from_hands(hands, labels={'Rival': 'Tim'})
    p = tmp_path / 'pf.json'
    m.save(str(p))
    m2 = pf.PostflopRangeModel.load(str(p))
    assert m2.alpha == m.alpha
    assert m2.n_buckets == m.n_buckets
    assert m2.labels == m.labels
    assert m2.opp == m.opp
    assert m2.cnt == m.cnt


def test_recommend_con_update_postflop():
    from motor.learn import load_hands
    from motor.player_ranges import ProfileRangeModel
    from motor.recommend_loop import recommend

    hands = load_hands()
    m = ProfileRangeModel.from_hands(hands)
    pm = pf.PostflopRangeModel.from_hands(hands)
    rec = recommend(['Jd', 'Jh'], ['Qh', '7s', '2c'],
                    street='flop', position='BB', villain_pos='BTN',
                    pot=12.5, to_call=5.0, stack=90.0,
                    range_model=m, villain_player='NESANVAR',
                    postflop_model=pm,
                    villain_postflop=[('flop', 'bet', 'c')])
    assert rec.action in ('fold', 'check', 'call', 'bet_25', 'bet_50',
                          'bet_75', 'all_in')
    assert rec.elapsed_ms > 0