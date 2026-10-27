import json

from tools.evaluar_decisiones import evaluate_file


def _decision(decision_id='d1', *, recommended='call', hand_id='H1', **extra):
    event = {
        'schema_version': 1,
        'event_type': 'decision',
        'decision_id': decision_id,
        'hand_id': hand_id,
        'recorded_at': '2026-01-01T00:00:00+00:00',
        'motor_version': 'build-test',
        'known_at_decision': {
            'street': 'flop',
            'hero_position': 'BTN',
            'villain_position': 'UTG',
            'pot': 10.0,
            'to_call': 2.0,
            'cards_known': {'hero': ['As', 'Kd'], 'board': ['Qh', '7s', '2c']},
            'candidate_actions': ['fold', 'call'],
            'recommended_action': recommended,
            'equity': 0.55,
            'ev_by_action': {'fold': 0.0, 'call': 1.0},
            'villain_range': {
                'combo_weights': [['QhQs', 1.0]],
                'representation': 'combo_probability_by_hand_label',
            },
        },
        'execution': {'status': 'pending', 'action': None},
        'outcome': {'status': 'pending'},
    }
    event.update(extra)
    return event


def _resolution(decision_id='d1', *, action='c', hand_id='H1', **outcome):
    return {
        'schema_version': 1,
        'event_type': 'resolution',
        'decision_id': decision_id,
        'hand_id': hand_id,
        'recorded_at': '2026-01-01T00:01:00+00:00',
        'execution': {
            'status': 'recorded' if action is not None else 'not_observed',
            'action': ({'pos': 'BTN', 'action': action, 'amount': 2.0}
                       if action is not None else None),
        },
        'outcome': {'status': 'recorded', **outcome},
    }


def _write(path, *objects):
    path.write_text(''.join(json.dumps(x) + '\n' for x in objects),
                    encoding='utf-8')


def test_pending_decision_is_not_scored_or_called_resolved(tmp_path):
    source = tmp_path / 'pending.jsonl'
    _write(source, _decision())

    report = evaluate_file(source)

    assert report['integrity']['pending_decisions'] == ['d1']
    assert report['concordance']['numerator'] == 0
    assert report['concordance']['denominator'] == 0
    decision = report['decisions'][0]
    assert decision['concordance']['reason'] == 'decision_pending'
    assert decision['reasonableness']['status'] == 'not_evaluated'
    assert decision['observed_result']['status'] == 'pending'


def test_resolved_call_and_call_are_concordant(tmp_path):
    source = tmp_path / 'concordant.jsonl'
    _write(source, _decision(), _resolution(
        final_pot=14.0, winner_ids=['hero'],
        showdown={'winner1': 'BTN'}, revealed_cards={'BTN': 'AsKd'}))

    report = evaluate_file(source)

    assert report['integrity']['linked_decisions'] == 1
    assert report['concordance']['numerator'] == 1
    assert report['concordance']['denominator'] == 1
    assert report['decisions'][0]['concordance']['status'] == 'concordant'
    assert report['decisions'][0]['observed_result']['status'] == 'available'


def test_resolved_different_action_is_discordant(tmp_path):
    source = tmp_path / 'discordant.jsonl'
    _write(source, _decision(recommended='call'), _resolution(action='f'))

    report = evaluate_file(source)

    assert report['concordance']['numerator'] == 0
    assert report['concordance']['denominator'] == 1
    assert report['concordance']['discordant'] == 1
    assert report['decisions'][0]['concordance']['status'] == 'discordant'


def test_orphan_resolution_is_reported(tmp_path):
    source = tmp_path / 'orphan.jsonl'
    _write(source, _resolution(decision_id='missing'))

    report = evaluate_file(source)

    assert report['integrity']['orphan_resolutions'] == ['missing']
    assert report['decisions'] == []
    assert report['concordance']['denominator'] == 0


def test_duplicate_decision_id_is_ambiguous_and_excluded(tmp_path):
    source = tmp_path / 'duplicate.jsonl'
    _write(source, _decision(), _decision(), _resolution())

    report = evaluate_file(source)

    assert report['integrity']['duplicate_ids']['decision_events'] == [
        {'decision_id': 'd1', 'lines': [1, 2]},
    ]
    assert report['integrity']['ambiguous_decision_ids'] == ['d1']
    assert report['concordance']['denominator'] == 0
    assert all(d['integrity']['status'] == 'ambiguous_duplicate_id'
               for d in report['decisions'])


def test_duplicate_resolution_id_is_ambiguous_and_excluded(tmp_path):
    source = tmp_path / 'duplicate-resolution.jsonl'
    _write(source, _decision(), _resolution(), _resolution())

    report = evaluate_file(source)

    assert report['integrity']['duplicate_ids']['resolution_events'] == [
        {'decision_id': 'd1', 'lines': [2, 3]},
    ]
    assert report['concordance']['denominator'] == 0
    assert report['decisions'][0]['concordance']['reason'] == \
        'duplicate_resolution_id'


def test_malformed_json_and_invalid_event_fields_are_reported(tmp_path):
    source = tmp_path / 'malformed.jsonl'
    source.write_text('{not-json}\n' + json.dumps({
        'event_type': 'decision', 'decision_id': 'bad',
    }) + '\n', encoding='utf-8')

    report = evaluate_file(source)

    assert [item['line'] for item in report['integrity']['malformed_events']] == [1, 2]
    assert 'invalid_json' in report['integrity']['malformed_events'][0]['errors']
    assert 'unsupported_or_missing_schema_version' in \
        report['integrity']['malformed_events'][1]['errors']
    assert report['decisions'][0]['integrity']['status'] == 'malformed'


def test_unknown_fields_are_reported_but_not_rejected(tmp_path):
    source = tmp_path / 'extension.jsonl'
    event = _decision(extra_top_level='preserved-by-reader')
    event['known_at_decision']['new_engine_metric'] = 0.25
    _write(source, event)

    report = evaluate_file(source)

    assert report['integrity']['valid_events'] == 1
    assert report['integrity']['malformed_events'] == []
    assert report['decisions'][0]['integrity']['unknown_fields'] == [
        'event.extra_top_level', 'known_at_decision.new_engine_metric',
    ]


def test_missing_result_and_revealed_cards_are_not_inferred(tmp_path):
    source = tmp_path / 'no-result.jsonl'
    _write(source, _decision(), _resolution(
        action=None, final_pot=None, winner_ids=None, showdown=None,
        revealed_cards={}))

    report = evaluate_file(source)
    result = report['decisions'][0]['observed_result']

    assert result['status'] == 'unavailable'
    assert result['available_fields'] == []
    assert result['empty_fields'] == ['revealed_cards']
    assert set(result['missing_fields']) == {
        'final_pot', 'winner_ids', 'showdown'}
    assert report['concordance']['denominator'] == 0


def test_reader_is_reproducible_and_does_not_change_input(tmp_path):
    source = tmp_path / 'stable.jsonl'
    _write(source, _decision(), _resolution(action='c'))
    original = source.read_bytes()

    first = evaluate_file(source)
    second = evaluate_file(source)

    assert first == second
    assert source.read_bytes() == original


def test_schema_v2_reproducibility_fields_are_validated(tmp_path):
    source = tmp_path / 'repro.jsonl'
    event = _decision()
    event['schema_version'] = 3
    event['known_at_decision']['reproducibility'] = {
        'version': 3,
        'rules_inputs': {'street': 'flop', 'n_players': 2},
        'situation_inputs': {'hero_codes': ['As', 'Kd']},
        'ev_inputs': {'pot': 12.5, 'runout': True},
        'villain_range_inputs': {'profile': 'TIBURON'},
        'response_model_inputs': {'profile': 'TIBURON', 'fade_n': 20.0},
        'motor_settings': {'runout': True, 'n_runouts': 100},
        'reach_vector': [0.0, 0.1, 0.2],
        'reach_combo_order': 'HAND_LABELS',
        'runout': True,
    }
    _write(source, event)

    report = evaluate_file(source)

    assert report['integrity']['valid_events'] == 1
    assert report['integrity']['malformed_events'] == []
    assert 'reproducibility' in report['decisions'][0]['information_available']
    decision_data = report['decisions'][0]['decision_data']
    assert decision_data['reproducibility']['version'] == 3
    assert decision_data['reproducibility']['reach_vector'] == [0.0, 0.1, 0.2]


def test_schema_v1_records_are_still_accepted(tmp_path):
    source = tmp_path / 'legacy.jsonl'
    event = _decision()
    _write(source, event)

    report = evaluate_file(source)

    assert report['integrity']['valid_events'] == 1
    assert report['integrity']['malformed_events'] == []
    assert report['decisions'][0]['integrity']['status'] in ('valid', 'pending')


def test_oracle_response_state_reconstructs_behavior(tmp_path):
    """Reconstruye OracleResponse.__call__ a partir del estado guardado."""
    import numpy as np
    from motor.decision import OracleResponse, _response_array

    # Simular un OracleResponse con estado conocido.
    # Con alpha=0.5, pf_p=0.1, pc_p=0.7, pr_p=0.2:
    #   profile = [0.1, 0.7, 0.2] clipped to [0.05, 0.90]
    #   scale = (3 * profile) ^ 0.5
    #   adjusted = base * scale, normalized
    pf_p, pc_p, pr_p = 0.1, 0.7, 0.2
    alpha = 0.5
    villain_eq = np.array([0.3, 0.5, 0.7])
    amount = 5.0
    pot = 12.5

    # Original: usar OracleResponse con alpha > 0
    class FakeOracle:
        def p_action(self, *a, **k):
            return {'actions': {'f': 0.1, 'c': 0.7, 'r': 0.2}, 'n': 10,
                    'source': 'granular', 'sizing': 0.5}

    original = OracleResponse(FakeOracle(), 'TIBURON', ('flop', 'cbet', 'DRY'),
                              fade_n=20.0)
    orig_pf, orig_pc, orig_pr = original(villain_eq, amount, pot)

    # Reconstructed: usar el estado guardado
    profile = np.clip(np.asarray((pf_p, pc_p, pr_p)), 0.05, 0.90)
    scale = np.power(3.0 * profile, alpha)
    pf_e, pc_e, pr_e = _response_array(villain_eq, amount, pot)
    base = np.column_stack((pf_e, pc_e, pr_e))
    adjusted = base * scale
    adjusted /= adjusted.sum(axis=-1, keepdims=True)
    recon_pf, recon_pc, recon_pr = adjusted[:, 0], adjusted[:, 1], adjusted[:, 2]

    assert np.allclose(orig_pf, recon_pf)
    assert np.allclose(orig_pc, recon_pc)
    assert np.allclose(orig_pr, recon_pr)


def test_schema_v3_oracle_response_state_is_accepted(tmp_path):
    source = tmp_path / 'oracle.jsonl'
    event = _decision()
    event['schema_version'] = 3
    event['known_at_decision']['reproducibility'] = {
        'version': 3,
        'response_model_inputs': {
            'profile': 'TIBURON', 'street': 'flop', 'facing': 'cbet',
            'texture': 'DRY', 'fade_n': 20.0,
            'pf_p': 0.1, 'pc_p': 0.7, 'pr_p': 0.2,
            'alpha': 0.5, 'source': 'granular', 'sizing': 0.5,
        },
        'reach_vector': [0.0, 0.1],
        'reach_combo_order': 'HAND_LABELS',
    }
    _write(source, event)

    report = evaluate_file(source)

    assert report['integrity']['valid_events'] == 1
    assert report['integrity']['malformed_events'] == []
    repro = report['decisions'][0]['decision_data']['reproducibility']
    assert repro['response_model_inputs']['pf_p'] == 0.1
    assert repro['response_model_inputs']['alpha'] == 0.5
    assert repro['response_model_inputs']['source'] == 'granular'
