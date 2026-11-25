# -*- coding: utf-8 -*-
"""P0-3: muestra, prior, propagación y no interferencia numérica."""
import copy
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from motor.behavior import Oracle, build
from motor.decision import OracleResponse
from motor.learn import load_hands
from motor.player_ranges import ProfileRangeModel
from motor.postflop_ranges import PostflopRangeModel


def _hand(hid, rival_action='f', cards=('7c', '2d')):
    return {
        'hand_id': hid,
        'players': [
            {'pos': 'BTN', 'name': 'Hero', 'cards': ['Jd', 'Jh']},
            {'pos': 'BB', 'name': 'Rival', 'cards': list(cards)},
        ],
        'streets': {
            'preflop': {'actions': [
                {'pos': 'BTN', 'action': 'r', 'amount': 2.5},
                {'pos': 'BB', 'action': 'c', 'amount': 2.5},
            ]},
            'flop': {
                'board': ['Qh', '7s', '2c'],
                'actions': [
                    {'pos': 'BTN', 'action': 'b', 'amount': 3.0},
                    {'pos': 'BB', 'action': rival_action, 'amount': 0.0},
                ],
            },
        },
    }


def _table_fingerprint(model):
    payload = {
        'alpha': model.alpha,
        'n_buckets': model.n_buckets,
        'labels': model.labels,
        'opp': {'|'.join(map(str, k)): v for k, v in model.opp.items()},
        'cnt': {'|'.join(map(str, k)): v for k, v in model.cnt.items()},
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def test_reference_counts_and_probability_tables_match_pre_p03():
    hands = load_hands(reliable_only=True)
    model = PostflopRangeModel.from_hands(hands)
    assert len(hands) == model.n_hands_input == 877
    assert model.n_hands_used == model.n_hands_with_known_cards == 864
    assert model.n_hands_with_postflop_observation == 339
    assert model.n_observations_used == sum(model.opp.values()) == 1388
    assert len(model.opp) == 116
    assert _table_fingerprint(model) == \
        'ccfcb5586e0dd75c7583adc73da0dddbeb2effa7efa6fc9e65bd90a3e2530ffc'
    assert _table_fingerprint(model) == _table_fingerprint(
        PostflopRangeModel.from_hands(hands))


def test_evidence_decomposes_current_shrinkage_without_changing_p_action():
    hands = [_hand('f1'), _hand('f2'), _hand('c1', 'c', ('Ac', 'Ad'))]
    model = PostflopRangeModel.from_hands(hands,
                                          labels={'Rival': 'Timmy'})
    key = next(k for k in model.opp if k[0] == 'Timmy')
    before = _table_fingerprint(model)
    for action in ('x', 'b', 'c', 'f', 'r'):
        estimate = model.p_action(*key, action)
        evidence = model.evidence_for(*key, action)
        assert evidence['estimate'] == estimate
        assert evidence['observation_count'] == model.opp[key]
        assert evidence['action_observation_count'] == \
            model.cnt.get(key + (action,), 0)
        assert evidence['prior_weight'] == pytest.approx(
            model.alpha / (model.opp[key] + model.alpha))
        assert evidence['observation_weight'] == pytest.approx(
            model.opp[key] / (model.opp[key] + model.alpha))
        assert evidence['prior_weight'] + evidence['observation_weight'] == \
            pytest.approx(1.0)
        assert evidence['confidence'] == 'not_quantified'
    assert _table_fingerprint(model) == before


def test_empty_bucket_uses_empirical_frequency_without_uniform_prior():
    model = PostflopRangeModel(alpha=2.0)
    key = ('Timmy', 'flop', 'bet', 2)
    model.opp[key] = 2
    model.cnt[key + ('f',)] = 2
    assert model.p_action(*key, 'f') == pytest.approx(1.0)
    ev = model.evidence_for(*key, 'f')
    assert ev['model_prior_source'] == 'empirical_no_compatible_prior'
    assert ev['prior_probability'] == 'not_available'
    assert ev['prior_weight'] == 0.0
    assert ev['observation_weight'] == 1.0
    assert not ev['prior_dominated']
    assert ev['coverage'] == 'thin_observations_n_lt_3'

    empty_key = ('Timmy', 'flop', 'bet', 4)
    assert model.p_action(*empty_key, 'f') == 0.0
    no_evidence = model.evidence_for(*empty_key, 'f')
    assert no_evidence['coverage'] == 'no_evidence_no_prior'
    assert no_evidence['prior_probability'] == 'not_available'
    assert no_evidence['prior_weight'] is None


def test_oracle_evidence_reports_real_support_but_preserves_returned_n():
    actions = {'f': 0.6, 'c': 0.2, 'r': 0.1, 'x': 0.05, 'b': 0.05}
    oracle = Oracle({'profiles': {}, 'granular': {}, 'por_facing': {
        ('P', 'flop', 'bet'): dict(actions, n=8),
        ('P', 'flop', 'none'): dict(actions, n=12),
    }})
    dist = oracle.p_action('P', 'flop', 'cbet')
    assert dist['source'] == 'label' and dist['n'] == 0
    evidence = oracle.evidence('P', 'flop', 'cbet', distribution=dist)
    assert evidence['returned_n'] == 0
    assert evidence['support_observations'] == 20
    assert evidence['confidence'] == 'not_quantified'

    response = OracleResponse(oracle, 'P', ('flop', 'cbet', 'two_tone'))
    # OracleResponse usa returned_n=0, no el soporte agregado: alpha permanece
    # 0. El sidecar hace visible que el fallback sí sumó 20 observaciones.
    assert response.alpha == 0.0
    assert response.source == 'label'
    assert response.evidence['support_observations'] == 20

    model = PostflopRangeModel()
    model._oracle = oracle
    prior_only = model.evidence_for('P', 'flop', 'bet', 3, 'f')
    assert prior_only['observation_count'] == 0
    assert prior_only['coverage'] == 'prior_only'
    assert prior_only['prior_weight'] == 1.0
    assert prior_only['estimate'] == pytest.approx(
        oracle.p_action('P', 'flop', 'bet')['actions']['f'])


def test_population_facing_es_prior_general_y_label_no_es_prior_de_rango():
    actions = {'x': 0.1, 'b': 0.2, 'c': 0.3, 'f': 0.3, 'r': 0.1}
    oracle = Oracle({'profiles': {}, 'granular': {}, 'por_facing': {
        ('A', 'flop', 'cbet'): dict(actions, n=12),
        ('B', 'flop', 'cbet'): dict(actions, n=8),
        ('A', 'flop', 'bet'): dict(actions, n=40),
    }})
    model = PostflopRangeModel(alpha=2.0)
    model._oracle = oracle

    general = model.evidence_for('UNKNOWN', 'flop', 'cbet', 2, 'c')
    assert general['estimate'] == pytest.approx(actions['c'])
    assert general['model_prior_source'] == 'poblacion_facing'
    assert general['prior_returned_n'] == 0
    assert general['prior_support_observations'] == 20
    assert general['prior_weight'] == 1.0

    # El fallback de perfil mezcla otros facings y queda fuera del likelihood.
    key = ('A', 'flop', 'cbet', 2)
    model.opp[key] = 4
    model.cnt[key + ('c',)] = 1
    # Hay pool poblacional del mismo facing en el caso de perfil desconocido.

    only_other_facing = Oracle({'profiles': {}, 'granular': {}, 'por_facing': {
        ('A', 'flop', 'bet'): dict(actions, n=40),
        ('A', 'flop', 'none'): dict(actions, n=10),
    }})
    model._oracle = only_other_facing
    empirical = model.evidence_for('A', 'flop', 'cbet', 2, 'c')
    assert empirical['estimate'] == pytest.approx(0.25)
    assert empirical['model_prior_source'] == 'empirical_no_compatible_prior'
    assert empirical['prior_probability'] == 'not_available'
    assert empirical['prior_weight'] == 0.0
    assert empirical['observation_weight'] == 1.0
    assert empirical['prior_evidence']['source'] == 'label'


def test_oracle_response_metadata_does_not_change_response_vector():
    data = build([_hand('o1'), _hand('o2'), _hand('o3')],
                 labels={'Rival': 'P'}, min_n=1)
    oracle = Oracle(data)
    response = OracleResponse(oracle, 'P', ('flop', 'bet', 'two_tone'))
    equity = np.asarray([0.1, 0.5, 0.9])
    before = response(equity, 10.0, 30.0)
    original = oracle.evidence
    oracle.evidence = lambda *a, **k: {'confidence': 'tamper-probe'}
    response_without_detail = OracleResponse(
        oracle, 'P', ('flop', 'bet', 'two_tone'))
    after = response_without_detail(equity, 10.0, 30.0)
    oracle.evidence = original
    for lhs, rhs in zip(before, after):
        np.testing.assert_array_equal(lhs, rhs)
    assert response.alpha == response_without_detail.alpha
    assert response.pf_p == response_without_detail.pf_p
    oracle.evidence = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError('evidence failure'))
    response_error = OracleResponse(
        oracle, 'P', ('flop', 'bet', 'two_tone'))
    error_result = response_error(equity, 10.0, 30.0)
    for lhs, rhs in zip(before, error_result):
        np.testing.assert_array_equal(lhs, rhs)


def test_vector_evidence_does_not_change_probability_vector():
    model = PostflopRangeModel.from_hands(
        [_hand('v1'), _hand('v2'), _hand('v3', 'c', ('Ac', 'Ad'))],
        labels={'Rival': 'Timmy'})
    board = ['Qh', '7s', '2c']
    before = model.prob_vec('Timmy', 'flop', 'bet', board, 'f').copy()
    detail = model.evidence_for_vector(
        'Timmy', 'flop', 'bet', board, 'f')
    after = model.prob_vec('Timmy', 'flop', 'bet', board, 'f')
    np.testing.assert_array_equal(before, after)
    assert len(detail['buckets']) == model.n_buckets
    assert detail['confidence'] == 'not_quantified'
    assert detail['observations_total'] == sum(
        x['observation_count'] for x in detail['buckets'])


def test_load_reports_lost_oracle_injection_without_restoring_it(tmp_path):
    hands = [_hand('l%d' % i) for i in range(4)]
    model = PostflopRangeModel.from_hands(hands,
                                          labels={'Rival': 'Timmy'})
    key = next(k for k, n in model.opp.items() if n >= 1)
    action = 'f'
    before = model.p_action(*key, action)
    path = tmp_path / 'postflop.json'
    model.save(str(path))
    loaded = PostflopRangeModel.load(str(path))
    assert loaded._oracle is None
    assert 'not serialized' in loaded._oracle_injection_source
    assert loaded._evidence_counts_known
    assert loaded.n_hands_input == model.n_hands_input
    assert loaded.n_observations_used == model.n_observations_used
    # La instancia cargada deja visible que perdió el Oracle, pero ahora usa
    # la frecuencia exacta de bucket si existe, no un prior plano implícito.
    assert loaded.p_action(*key, action) == pytest.approx(before)
    assert loaded.evidence_for(*key, action)['model_prior_source'] == \
        'empirical_no_compatible_prior'
    assert model._oracle is not None


def test_legacy_load_does_not_confuse_observations_with_distinct_hands(tmp_path):
    model = PostflopRangeModel.from_hands(
        [_hand('legacy%d' % i) for i in range(4)],
        labels={'Rival': 'Timmy'})
    legacy_payload = model.to_json()
    legacy_payload.pop('evidence', None)  # formato anterior a P0-3
    path = tmp_path / 'legacy.json'
    path.write_text(json.dumps(legacy_payload), encoding='utf-8')
    loaded = PostflopRangeModel.load(str(path))
    key = next(iter(loaded.opp))
    evidence = loaded.evidence_for(*key, 'f')
    assert evidence['observation_count'] == loaded.opp[key]
    assert evidence['distinct_hand_count'] is None
    assert not loaded._evidence_counts_known
    assert loaded.n_hands_with_known_cards == loaded.n_hands_used


def test_p03_audit_recounts_window_and_p02_shadow_rows():
    from tools.auditar_muestra_postflop import audit

    result = audit(load_hands(reliable_only=True))
    assert result['hands']['received'] == 877
    assert result['hands']['counted_by_legacy_n_hands_used'] == 864
    assert result['hands']['with_at_least_one_effective_postflop_observation'] == 339
    assert result['observations']['effective_postflop'] == 1388
    assert result['observations']['candidate_rows_matching_builder'] == 1388
    assert result['observations']['cell_count'] == 116
    assert result['observations']['query_count_populated_cells'] == 580
    assert result['observations']['shadow_eligible'] == 1386
    assert result['observations']['shadow_restricted'] == 2
    assert result['observations']['cell_sample_bands'] == {
        'thin_observations_n_lt_3': 30,
        'limited_observations_n_lt_20': 68,
        'observations_n_ge_20': 18,
    }
    assert result['observations']['queries_prior_dominated'] == 150
    assert sum(len(cell['observation_trace'])
               for cell in result['cells']) == 1388
    for cell in result['cells']:
        assert len(cell['observation_trace']) == cell['observations']
        assert len(cell['contributing_hand_ids']) == cell['distinct_hands']
    assert result['fingerprints']['probability_tables_sha256'] == \
        'ccfcb5586e0dd75c7583adc73da0dddbeb2effa7efa6fc9e65bd90a3e2530ffc'
    assert result['fingerprints']['populated_query_estimates_sha256'] == \
        'a16b0572bbac94efcbf58572d692e1dd8789dab4b52ede5bebcc82045f3b975c'


def test_live_abstiene_si_no_puede_verificar_likelihood_del_sidecar():
    from motor.asistente_live import Asistente

    hands = [_hand('live%d' % i, 'f' if i % 2 else 'c',
                   ('7c', '2d') if i % 2 else ('Ac', 'Ad'))
             for i in range(6)]
    labels = {'Hero': 'PEZ', 'Rival': 'TIBURON'}
    range_model = ProfileRangeModel.from_hands(hands, labels=labels)
    oracle = Oracle(build(hands, labels=labels, min_n=1))
    postflop = PostflopRangeModel.from_hands(hands, labels=labels)
    postflop._oracle = oracle
    models = SimpleNamespace(range_model=range_model, oracle=oracle,
                             postflop_model=postflop)
    recorded = {
        'hand_id': 'LIVE_EVIDENCE',
        'streets': {
            'preflop': {'actions': [
                {'pos': 'BTN', 'action': 'r', 'amount': 2.5},
                {'pos': 'BB', 'action': 'c', 'amount': 2.5}]},
            'flop': {'board': ['Qh', '7s', '2c'], 'actions': [
                {'pos': 'BTN', 'action': 'b', 'amount': 3.0},
                {'pos': 'BB', 'action': 'c', 'amount': 3.0}]},
        },
    }
    assistant = Asistente.__new__(Asistente)
    assistant.models = models
    assistant.oracle = oracle
    assistant.rec = SimpleNamespace(
        hand=recorded, _hand_positions={'hero': 'BTN', 'p1': 'BB'})
    assistant.verbose = False
    assistant.shadow = False
    assistant.runout = False
    assistant.live_stacks = {}
    assistant._last_seen_stake = {}
    assistant.decision_log = None
    state = {
        'pot': 20.0,
        'hero_state': 'activo', 'hero_stake': 90.0, 'hero_bet': 0.0,
        'p1_state': 'activo', 'p1_stake': 90.0, 'p1_bet': 5.0,
        'p2_state': 'inactivo', 'p3_state': 'inactivo',
        'p4_state': 'inactivo', 'p5_state': 'inactivo',
    }
    visible_a = []
    def capture_a(text, ev, _sit, _label):
        visible_a.append((text, ev.chosen, dict(ev.ev)))

    reco_a = assistant._recomendacion_para(
        state, 'hero', ['As', 'Kd'], ['Qh', '7s', '2c'], 'p1', [],
        verbose=False, on_reco=capture_a, seed=19)
    assert reco_a is not None
    assert reco_a.model_evidence['confidence'] == 'not_quantified'
    assert reco_a.model_evidence['postflop_range_queries']

    original = postflop.evidence_for_vector
    postflop.evidence_for_vector = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError('sidecar disabled'))
    visible_b = []
    def capture_b(text, ev, _sit, _label):
        visible_b.append((text, ev.chosen, dict(ev.ev)))

    reco_b = assistant._recomendacion_para(
        state, 'hero', ['As', 'Kd'], ['Qh', '7s', '2c'], 'p1', [],
        verbose=False, on_reco=capture_b, seed=19)
    postflop.evidence_for_vector = original
    assert reco_b is None
    assert visible_a and not visible_b
    assert assistant.last_reco_reason == (
        'postflop_range_incomplete:'
        'postflop_likelihood_evidence_error:sidecar disabled')
