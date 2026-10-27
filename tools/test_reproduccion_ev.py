"""Prueba de reproducción del EV a partir de un registro v3."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np

from motor.decision import _response_array, compute_evs
from motor.ranges import RangeState
from motor.situation import situation


def _make_original():
    """Ejecuta el cálculo original y devuelve entradas, resultados y registro."""
    hero = ['As', 'Kd']
    board = ['Qh', '7s', '2c']
    pot = 12.5
    to_call = 4.0
    stack = 90.0
    villain_stack = 90.0
    effective_stack = min(stack, villain_stack)
    street = 'flop'
    hero_pos = 'BB'
    villain_pos = 'UTG'

    # Rango rival (simulado con uniforme para determinismo)
    reach = np.ones(1326, dtype=np.float32)
    rs = RangeState(reach=reach)
    rs.set_known_cards(list(hero) + list(board))

    # Respuesta del rival (OracleResponse con alpha=0 -> heurística pura)
    class FakeOracle:
        def p_action(self, *a, **k):
            return None  # alpha=0

    from motor.decision import OracleResponse
    resp = OracleResponse(FakeOracle(), 'TIBURON',
                          ('flop', 'cbet', 'DRY'), fade_n=20.0)

    sit = situation(hero, board, villain_reach=rs, pot_before_call=pot,
                    to_call=to_call, stack_effective=effective_stack,
                    position=hero_pos, street=street)

    bet_sizes = (0.25, 0.5, 0.75)
    raise_to = 13.0
    candidates = ('fold', 'call', 'raise', 'all_in')
    runout = True
    n_runouts = 100

    evs = compute_evs(hero, board, villain_reach=rs, pot=pot, to_call=to_call,
                       stack=stack, villain_stack=villain_stack,
                       response_fn=resp, runout=runout, n_runouts=n_runouts,
                       bet_sizes=bet_sizes, raise_to=raise_to,
                       candidates=candidates)

    # Construir registro v3
    reach_vector = [float(w) for w in rs.weights]
    record = {
        'schema_version': 3,
        'event_type': 'decision',
        'decision_id': 'repro-ev-1',
        'hand_id': 'H_REPRO_EV',
        'recorded_at': '2026-01-01T00:00:00+00:00',
        'motor_version': 'test',
        'known_at_decision': {
            'street': street,
            'hero_id': 'hero',
            'villain_id': 'p1',
            'hero_position': hero_pos,
            'villain_position': 'UTG',
            'pot': pot,
            'to_call': to_call,
            'effective_stack': effective_stack,
            'cards_known': {
                'hero': list(hero),
                'board': list(board),
            },
            'candidate_actions': list(candidates),
            'recommended_action': evs.best()[0],
            'equity': sit.equity,
            'ev_by_action': dict(evs.ev),
            'reproducibility': {
                'version': 3,
                'situation_inputs': {
                    'hero_codes': list(hero),
                    'board_codes': list(board),
                    'pot_before_call': pot,
                    'to_call': to_call,
                    'stack_effective': effective_stack,
                    'position': hero_pos,
                    'street': street,
                },
                'ev_inputs': {
                    'pot': pot,
                    'to_call': to_call,
                    'stack': stack,
                    'villain_stack': villain_stack,
                    'bet_sizes': list(bet_sizes),
                    'raise_to': raise_to,
                    'candidates': list(candidates),
                    'runout': runout,
                    'n_runouts': n_runouts,
                    'tree': False,
                },
                'reach_vector': reach_vector,
                'reach_combo_order': 'HAND_LABELS',
                'response_model_inputs': {
                    'profile': 'TIBURON',
                    'street': street,
                    'facing': 'cbet',
                    'texture': 'DRY',
                    'fade_n': 20.0,
                    'pf_p': resp.pf_p,
                    'pc_p': resp.pc_p,
                    'pr_p': resp.pr_p,
                    'alpha': resp.alpha,
                    'source': resp.source,
                    'sizing': resp.sizing,
                },
                'motor_settings': {
                    'runout': runout,
                    'n_runouts': n_runouts,
                    'tree': False,
                    'tree_n_street': 60,
                    'tree_n_finals': 6,
                    'tree_frac': 0.5,
                },
                'rules_inputs': {
                    'street': street,
                    'hero_initiator': True,
                    'to_call': to_call,
                    'pot': pot,
                    'stack': effective_stack,
                    'effective_stack': effective_stack,
                    'n_players': 2,
                    'facing_raise': False,
                    'hero_bet_flop': False,
                    'hero_oop': False,
                    'flop_checked': True,
                    'villain_bet_flop': False,
                    'hand_role': 'VALUE',
                    'range_advantage': 'HERO',
                    'nut_advantage': 'NEUTRAL',
                },
            },
        },
        'execution': {'status': 'pending', 'action': None},
        'outcome': {'status': 'pending'},
    }

    return hero, board, pot, to_call, stack, villain_stack, effective_stack, \
        street, hero_pos, rs, resp, evs, record


def test_ev_reproduction_from_v3_record():
    """Reproduce el EV completo a partir de un registro v3."""
    hero, board, pot, to_call, stack, villain_stack, effective_stack, \
        street, hero_pos, original_rs, original_resp, original_evs, record = \
        _make_original()

    # Extraer datos del registro (simulando lectura de JSONL)
    repro = record['known_at_decision']['reproducibility']
    si = repro['situation_inputs']
    ei = repro['ev_inputs']
    rmi = repro['response_model_inputs']
    rv = repro['reach_vector']

    # Reconstruir RangeState desde reach_vector
    reconstructed_rs = RangeState(reach=rv)
    reconstructed_rs.set_known_cards(list(si['hero_codes']) + list(si['board_codes']))

    # Reconstruir response_fn desde el estado guardado
    def reconstructed_response(villain_equity, amount, pot_val):
        if amount <= 0:
            e = np.asarray(villain_equity, dtype=np.float64)
            return np.zeros_like(e), np.ones_like(e), np.zeros_like(e)
        pf_e, pc_e, pr_e = _response_array(villain_equity, amount, pot_val)
        alpha = rmi['alpha']
        if alpha <= 0:
            return pf_e, pc_e, pr_e
        base = np.column_stack((pf_e, pc_e, pr_e))
        profile = np.clip(np.asarray((rmi['pf_p'], rmi['pc_p'], rmi['pr_p'])),
                          0.05, 0.90)
        scale = np.power(3.0 * profile, alpha)
        adjusted = base * scale
        adjusted /= adjusted.sum(axis=-1, keepdims=True)
        return adjusted[:, 0], adjusted[:, 1], adjusted[:, 2]

    # Reconstruir EV
    reconstructed_evs = compute_evs(
        si['hero_codes'], si['board_codes'],
        villain_reach=reconstructed_rs,
        pot=ei['pot'], to_call=ei['to_call'],
        stack=ei['stack'], villain_stack=ei['villain_stack'],
        response_fn=reconstructed_response,
        runout=ei['runout'], n_runouts=ei['n_runouts'],
        bet_sizes=tuple(ei['bet_sizes']),
        raise_to=ei['raise_to'],
        candidates=tuple(ei['candidates']),
    )

    # Comparar
    print('Original EVs:', original_evs.ev)
    print('Reconstructed EVs:', reconstructed_evs.ev)
    print('Chosen original:', original_evs.best()[0])
    print('Chosen reconstructed:', reconstructed_evs.best()[0])

    max_abs_error = 0.0
    max_rel_error = 0.0
    for action in original_evs.ev:
        orig = original_evs.ev[action]
        recon = reconstructed_evs.ev.get(action)
        if recon is None:
            print(f'  MISSING action in reconstructed: {action}')
            continue
        abs_err = abs(orig - recon)
        rel_err = abs_err / abs(orig) if abs(orig) > 1e-9 else 0.0
        max_abs_error = max(max_abs_error, abs_err)
        max_rel_error = max(max_rel_error, rel_err)
        print(f'  {action}: orig={orig:.10f} recon={recon:.10f} '
              f'abs_err={abs_err:.2e} rel_err={rel_err:.2e}')

    print(f'Max abs error: {max_abs_error:.2e}')
    print(f'Max rel error: {max_rel_error:.2e}')

    # Assertions
    assert reconstructed_evs.best()[0] == original_evs.best()[0]
    assert set(reconstructed_evs.ev.keys()) == set(original_evs.ev.keys())
    for action in original_evs.ev:
        assert abs(original_evs.ev[action] - reconstructed_evs.ev[action]) < 1e-6, \
            f'EV mismatch for {action}: {original_evs.ev[action]} vs {reconstructed_evs.ev[action]}'
    assert max_abs_error < 1e-6
    assert max_rel_error < 1e-6


if __name__ == '__main__':
    test_ev_reproduction_from_v3_record()
    print('PASS')