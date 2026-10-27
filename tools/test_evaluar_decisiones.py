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
