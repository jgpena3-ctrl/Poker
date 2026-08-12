"""Test de motor/panel.py y motor/recommend_loop.py — orquestador anytime."""
import numpy as np
import pytest

from motor.decision import compute_evs
from motor.panel import format_evs, format_cards, format_insight, format_situation
from motor.recommend_loop import Recommendation, build_villain_range, recommend
from motor.situation import situation


def _fixture():
    return dict(
        hero_codes=['Jd', 'Jh'],
        board_codes=['Qh', '7s', '2c'],
        street='flop', position='BB', villain_pos='UTG',
        pot=12.5, to_call=5.0, stack=90.0,
    )


def _villain():
    fx = _fixture()
    return build_villain_range(fx['hero_codes'], fx['board_codes'], 'UTG')


# ---------------------------------------------------------------------------
# panel
# ---------------------------------------------------------------------------

def test_format_cards():
    assert format_cards(['Ah', 'Kd']) == 'Ah Kd'


def test_format_situation_section():
    fx = _fixture()
    sit = situation(fx['hero_codes'], fx['board_codes'], villain_reach=_villain(),
                    pot_before_call=fx['pot'], to_call=fx['to_call'],
                    stack_effective=fx['stack'], position='BB', street='flop')
    out = format_situation(sit)
    assert 'Equity' in out and '1081 combos' in out
    assert 'Pot odds' in out and 'SPR' in out


def test_format_evs_marks_best():
    fx = _fixture()
    evs = compute_evs(fx['hero_codes'], fx['board_codes'],
                      villain_reach=_villain(), pot=12.5, to_call=0, stack=90)
    out = format_evs(evs)
    best = evs.best()[0]
    assert out.count('<==') == 1
    assert out.splitlines()[0].endswith('<==')
    assert best in out.splitlines()[0]


def test_format_insight_shows_recommendation():
    fx = _fixture()
    rec = recommend(**fx)
    text = format_insight(rec.situation, rec.evs, 'OR UTG')
    assert 'Mejor accion' in text
    assert rec.action in text


# ---------------------------------------------------------------------------
# recommend_loop
# ---------------------------------------------------------------------------

def test_recommend_returns_fields():
    fx = _fixture()
    rec = recommend(**fx)
    assert isinstance(rec, Recommendation)
    assert rec.action in ('fold', 'check', 'call', 'bet_25', 'bet_50',
                          'bet_75', 'all_in')
    assert rec.elapsed_ms >= 0
    assert rec.stages['total'] == pytest.approx(rec.elapsed_ms, abs=1e-6)
    assert rec.stages['budget'] > 0  # holgura sobrante del deadline


def test_recommend_without_bet_in_front():
    fx = _fixture()
    fx['to_call'] = 0.0
    rec = recommend(**fx)
    assert 'check' in rec.evs.ev
    assert 'call' not in rec.evs.ev


def test_recommend_with_reach_vector():
    fx = _fixture()
    reach = np.ones(1326, dtype=np.float32)
    rec = recommend(**fx, villain_reach=reach)
    assert rec.villain_label == 'rango dado'


def test_recommend_with_range_state():
    fx = _fixture()
    rec = recommend(**fx, villain_reach=_villain())
    assert rec.villain_label == 'rango dado'


def test_on_progress_called():
    fx = _fixture()
    logs = []
    recommend(**fx, on_progress=logs.append)
    assert any('ms' in log for log in logs)


def test_build_villain_range_blockers():
    rs = build_villain_range(['Jd', 'Jh'], ['Qh', '7s', '2c'], 'UTG')
    assert int(rs.legal_mask.sum()) == 1081  # C(47,2): hero + 3 del board
    known = rs.blockers
    assert known & (1 << card_of('2c'))  # 2c del board marcado como blocker


def test_build_villain_range_extra_cards():
    rs = build_villain_range(['Jd', 'Jh'], ['Qh', '7s', '2c'], 'UTG',
                             villain_cards=['Ts'])
    assert int(rs.legal_mask.sum()) == 1035  # C(46,2): una carta conocida más


def test_deadline_param_accepted():
    fx = _fixture()
    rec = recommend(**fx, deadline_s=0.05)
    assert 0 <= rec.stages['budget'] < 100  # deadline de 50 ms respetado
    assert rec.action  # recomendación siempre disponible


def test_runout_flag_uses_mc_only_off_river():
    fx = _fixture()  # flop JdJh vs OR UTG
    base = recommend(**fx)
    assert base.runout is False
    assert 'sorteo' not in base.text
    with_run = recommend(**fx, runout=True)
    assert with_run.runout is True
    assert 'sorteo de turn+river' in with_run.text
    # las ramas agresivas no cambian (siguen con equity determinista)
    assert with_run.evs.ev['bet_50'] == pytest.approx(base.evs.ev['bet_50'])
    # en river no hay sorteo: la marca no aparece y nada cambia
    fx_river = dict(fx, board_codes=['Qh', '7s', '2c', '9d', '5h'])
    rec_river = recommend(**fx_river, runout=True)
    assert 'sorteo' not in rec_river.text


def card_of(code):
    from motor.cards import card_id
    return card_id(code)