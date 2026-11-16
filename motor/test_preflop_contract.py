"""Tests del contrato único de interpretación preflop (P0-1).

El contrato se ejecuta en sombra: no cambia la recomendación. Aquí se fijan
las semánticas que el parser viejo confundía y, sobre todo, se mide la deuda
que queda declarada antes de activarlo.
"""
import collections
from types import SimpleNamespace

import pytest

from motor.asistente_live import (Asistente, _preflop_raises, _preflop_spot)
from motor.learn import (classify_first_action, load_hands, preflop_events)
from motor.preflop_contract import (ShadowPreflopLog, actions_of,
                                    classify_action, context_at,
                                    first_decision,
                                    legacy_training_category, plan_from_context,
                                    table_plan, walk_preflop)


def _hand(actions, hand_id='H_CONTRATO'):
    normalizadas = []
    for a in actions:
        if isinstance(a, dict):
            normalizadas.append(a)
        else:
            normalizadas.append({'pos': a[0], 'action': a[1],
                                 'amount': a[2] if len(a) > 2 else None})
    return {'hand_id': hand_id,
            'streets': {'preflop': {'actions': normalizadas}}}


def _cls(actions, pos, legacy=False):
    return first_decision(_hand(actions), pos, legacy=legacy)


# ---------------------------------------------------------------------------
# Las confusiones que P0-1 tiene que separar
# ---------------------------------------------------------------------------

def test_r_como_apertura_no_es_3bet():
    acts = [('SB', 'p', 0.5), ('BB', 'p', 1.0), ('UTG', 'r', 2.5)]
    c = _cls(acts, 'UTG')
    assert c.category == 'open'
    assert (c.denom, c.context.raises_before) == ('no_raise', 0)
    # El parser live viejo decide por el carácter: `r` -> 3bet.
    assert _preflop_spot(_hand(acts), 'UTG') == ('facing_open', '3bet')


def test_r_como_resubida_si_es_3bet():
    acts = [('SB', 'p', 0.5), ('BB', 'p', 1.0),
            ('UTG', 'r', 2.5), ('MP', 'r', 8.0)]
    c = _cls(acts, 'MP')
    assert c.category == '3bet'
    assert c.context.raises_before == 1
    assert c.raise_number == 2
    assert c.bet_label == '3bet'


def test_b_mayor_de_1bb_en_cinco_contextos():
    # Apertura: no hay limpes ni subidas.
    c = _cls([('BB', 'p', 1.0), ('UTG', 'b', 2.5)], 'UTG')
    assert (c.category, c.context.raises_before, c.context.limps_before) == \
        ('open', 0, 0)

    # Raise sobre limpe: el limpe ocurre antes del open.
    c = _cls([('UTG', 'c', 1.0), ('MP', 'b', 3.0)], 'MP')
    assert (c.category, c.context.limps_before) == ('rol', 1)

    # Raise sobre limpe corto (b <= 1BB), que NO es una subida.
    c = _cls([('UTG', 'b', 1.0), ('MP', 'b', 3.0)], 'MP')
    assert (c.category, c.context.raises_before,
            c.context.limps_before) == ('rol', 0, 1)

    # 3bet normal: hay open y ningún caller de ese open.
    c = _cls([('UTG', 'b', 2.5), ('MP', 'b', 8.0)], 'MP')
    assert c.category == '3bet'
    assert c.context.callers_before == 0

    # Squeeze: hay open y alguien YA pagó la subida vigente.
    c = _cls([('UTG', 'b', 2.5), ('MP', 'c', 2.5),
              ('CO', 'b', 8.0)], 'CO')
    assert c.category == 'squeeze'
    assert c.context.callers_before == 1

    # 4bet registrado como `b`, no como `r`.
    c = _cls([('UTG', 'b', 2.5), ('MP', 'b', 8.0),
              ('CO', 'b', 20.0)], 'CO')
    assert c.category == '4bet'
    assert c.raise_number == 3


def test_b_menor_igual_1bb_es_limpe_corto():
    for amount in (0.5, 1.0):
        c = _cls([('UTG', 'b', amount)], 'UTG')
        assert (c.category, c.short_limp, c.context.raises_before) == \
            ('limp', True, 0)
    # El limpe corto cuenta como limpe para el que viene detrás.
    c = _cls([('UTG', 'b', 1.0), ('MP', 'c', 1.0)], 'MP')
    assert (c.category, c.context.limps_before) == ('call_limp', 1)
    c = _cls([('UTG', 'b', 1.0), ('MP', 'b', 3.0)], 'MP')
    assert (c.category, c.context.limps_before) == ('rol', 1)
    # El parser viejo lo llama open; el contrato no.
    assert _preflop_spot(_hand([('UTG', 'b', 1.0)]), 'UTG') == \
        ('no_raise', 'open')


def test_c_tras_limpe_y_c_contra_open_son_distintos():
    c = _cls([('UTG', 'c', 1.0), ('MP', 'f', 0.0),
              ('CO', 'c', 1.0)], 'CO')
    assert c.category == 'call_limp'
    c = _cls([('UTG', 'b', 2.5), ('CO', 'c', 2.5)], 'CO')
    assert c.category == 'call_open'
    c = _cls([('UTG', 'b', 2.5), ('MP', 'b', 8.0),
              ('CO', 'c', 8.0)], 'CO')
    assert c.category == 'call_3bet'
    c = _cls([('UTG', 'b', 2.5), ('MP', 'b', 8.0),
              ('CO', 'b', 20.0), ('BTN', 'c', 20.0)], 'BTN')
    assert c.category == 'call_4bet'
    assert c.range_query_status == 'no_table'


def test_check_de_bb_y_check_de_otra_posicion():
    bb = _cls([('SB', 'p', 0.5), ('BB', 'p', 1.0),
               ('UTG', 'f', 0.0), ('SB', 'f', 0.0),
               ('BB', 'x', 0.0)], 'BB')
    assert (bb.category, bb.denom, bb.status) == \
        ('bb_check', 'no_raise', 'resolved')
    # La opción del BB también existe después de limpes, sin subida.
    bb_limp = _cls([('UTG', 'c', 1.0), ('BB', 'x', 0.0)], 'BB')
    assert (bb_limp.category, bb_limp.context.limps_before) == \
        ('bb_check', 1)

    otra = _cls([('SB', 'p', 0.5), ('BB', 'p', 1.0),
                 ('UTG', 'x', 0.0)], 'UTG')
    assert otra.status == 'unresolved'
    assert (otra.category, otra.reason) == ('check_non_bb',
                                            'check_fuera_de_BB')

    sin_pos = classify_action('x', 0.0)
    assert (sin_pos.status, sin_pos.category, sin_pos.reason) == \
        ('unresolved', 'check_pos_unknown', 'check_sin_posicion')

    con_subida = _cls([('BB', 'p', 1.0), ('UTG', 'b', 2.5),
                       ('BB', 'x', 0.0)], 'BB')
    assert con_subida.status == 'unresolved'
    assert con_subida.reason == 'BB_no_puede_pasar_con_subida'


def test_fold_y_sin_decision_voluntaria():
    assert _cls([('UTG', 'f', 0.0)], 'UTG').category == 'fold'
    assert _cls([('UTG', 'b', 2.5), ('MP', 'f', 0.0)], 'MP').category == \
        'fold_vs_open'
    assert _cls([('UTG', 'b', 2.5), ('MP', 'b', 8.0),
                 ('CO', 'f', 0.0)], 'CO').category == 'fold_vs_3bet'
    # Una posta no es una decisión: el BB sigue sin haber decidido.
    posts = _cls([('SB', 'p', 0.5), ('BB', 'p', 1.0)], 'BB')
    assert (posts.status, posts.reason) == ('unresolved', 'sin_decision')
    # La ciega antigua grabada como `b` tampoco es una decisión.
    blind = _cls([('BB', 'b', 1.0)], 'BB')
    assert (blind.status, blind.reason) == ('unresolved', 'sin_decision')


def test_4bet_y_posteriores_se_declaran_sin_tabla():
    acts = [('UTG', 'b', 2.5), ('MP', 'b', 8.0),
            ('CO', 'b', 20.0), ('BTN', 'b', 50.0)]
    c = _cls(acts, 'BTN')
    assert (c.category, c.raise_number, c.bet_label) == \
        ('5bet', 4, '5bet')
    assert c.range_query is None
    assert c.range_query_status == 'no_table'

    acts += [('SB', 'b', 120.0)]
    c = _cls(acts, 'SB')
    assert c.category == '6bet_plus'
    assert c.range_query_status == 'no_table'

    c = _cls([('UTG', 'b', 2.5), ('MP', 'b', 8.0),
              ('CO', 'b', 20.0), ('BTN', 'f', 0.0)], 'BTN')
    assert c.category == 'fold_vs_4bet'
    assert c.range_query_status == 'no_range'


def test_falta_de_dato_y_secuencia_ambigua_no_se_inventan():
    c = _cls([{'pos': 'UTG', 'action': 'b'}], 'UTG')
    assert (c.status, c.reason) == ('unresolved', 'importe_ausente')

    c = _cls([{'pos': 'UTG', 'action': 'z'}], 'UTG')
    assert (c.status, c.reason) == ('unresolved', 'accion_desconocida')

    c = _cls([{'action': 'b', 'amount': 2.5}], '')
    assert (c.status, c.reason) == ('unresolved', 'pos_ausente')

    c = _cls([{'pos': 'UTG', 'amount': 2.5}], 'UTG')
    assert (c.status, c.reason) == ('unresolved', 'accion_ausente')

    c = _cls([('UTG', 'b', 2.5), ('MP', 'r', 2.5)], 'MP')
    assert (c.status, c.reason) == ('unresolved',
                                    'subida_sin_incremento')
    # La acción siguiente hereda la ambigüedad; no se reclasifica como si
    # nada hubiera pasado.
    c = _cls([('UTG', 'b', 2.5), ('MP', 'r', 2.5),
              ('CO', 'c', 2.5)], 'CO')
    assert c.status == 'unresolved'
    assert c.reason.startswith('secuencia_ambigua:')

    assert _cls([], 'BTN').reason == 'sin_decision'
    assert first_decision(None, 'BTN').reason == 'sin_decision'


def test_rango_declarado_para_categorias_sin_celda():
    assert _cls([('BB', 'p', 1.0), ('UTG', 'b', 2.5)],
                'UTG').range_query_status == 'available'
    assert _cls([('UTG', 'f', 0.0)], 'UTG').range_query_status == 'no_range'
    assert _cls([('UTG', 'x', 0.0)], 'UTG').range_query_status == 'unresolved'


# ---------------------------------------------------------------------------
# Paridad con el entrenamiento y con la referencia antigua
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def hands_877():
    return load_hands(reliable_only=True)


def test_adaptador_legado_reproduce_el_clasificador_historico():
    casos = [
        ('f', 0.0, 0, 0, 0), ('f', 0.0, 1, 0, 0),
        ('f', 0.0, 2, 0, 0), ('x', 0.0, 0, 0, 0),
        ('c', 1.0, 0, 0, 0), ('c', 1.0, 0, 1, 0),
        ('c', 2.5, 1, 0, 0), ('b', 1.0, 0, 0, 0),
        ('b', 2.5, 0, 0, 0), ('b', 3.0, 0, 1, 0),
        ('r', 2.5, 0, 0, 0), ('r', 8.0, 1, 0, 0),
        ('r', 8.0, 1, 0, 1), ('r', 20.0, 2, 0, 0),
    ]
    for action, amount, raises, limps, callers in casos:
        old = classify_first_action(action, amount, raises, limps, 1.0,
                                    callers)
        new = legacy_training_category(action, amount, raises, limps,
                                        callers, 1.0)
        assert new == old
    with pytest.raises(ValueError):
        legacy_training_category('z', 0.0, 0, 0, 0, 1.0)
    # Una posta no es una decisión y el adaptador histórico sigue lanzando.
    with pytest.raises(ValueError):
        legacy_training_category('p', 1.0, 0, 0, 0, 1.0)


def test_paridad_legado_con_los_4594_eventos_de_la_ventana(hands_877):
    total = 0
    for hand in hands_877:
        for ev in preflop_events(hand):
            got = first_decision(hand, ev.pos, legacy=True)
            assert (got.category, got.denom) == (ev.category, ev.denom)
            total += 1
    assert total == 4594


def test_deuda_legada_y_restricciones_p02_quedan_visibles(hands_877):
    """El modo estricto NO finge que el entrenamiento viejo era correcto.

    Las 49 diferencias vienen de que el contador legado cuenta un limpe corto
    `b` como subida para el jugador siguiente. Se conservan los 29 checks fuera
    de BB; además, H_0357 deja visible que la segunda acción del BB contradice
    su posta y contamina cuatro decisiones posteriores según P0-2.
    """
    same = 0
    diffs = []
    unresolved = []
    for hand in hands_877:
        for ev in preflop_events(hand):
            got = first_decision(hand, ev.pos)
            if not got.resolved:
                unresolved.append((ev.category, got.category))
            elif (got.training_category, got.training_denom) != \
                    (ev.category, ev.denom):
                diffs.append((ev.category, got.training_category))
            else:
                same += 1
    # Dos calls de la fuente no declaran all-in ni semantica incremental.
    # El contrato estricto no los convierte en calls completos: H_0589 y
    # H_0740 quedan unresolved y se restan de los estados "same".
    assert same == 4499
    assert len(diffs) == 60
    assert len(unresolved) == 35
    assert collections.Counter(unresolved) == {
        ('bb_check', 'check_non_bb'): 29,
        ('fold', 'unknown'): 2,
        ('open', 'unknown'): 1,
        ('fold_vs_open', 'unknown'): 1,
        ('call_open', 'unknown'): 2,
    }
    assert collections.Counter(diffs) == {
        ('fold_vs_open', 'fold'): 14,
        ('call_open', 'call_limp'): 13,
        ('fold_vs_3bet', 'fold_vs_open'): 13,
        ('3bet', 'rol'): 4,
        ('call_3bet', 'call_open'): 3,
        ('squeeze', 'rol'): 2,
        ('fold', 'fold_vs_open'): 4,
        ('open', '3bet'): 2,
        ('fold_vs_open', 'open'): 2,
        ('fold_vs_open', 'fold_vs_3bet'): 2,
        ('call_open', 'call_3bet'): 1,
    }


def test_las_162_b_mayor_1bb_y_las_15_b_menor_igual_1bb(hands_877):
    total = collections.Counter()
    cats = collections.Counter()
    for hand in hands_877:
        for step in walk_preflop(hand):
            if step.raw.action != 'b':
                continue
            amount = step.raw.amount or 0.0
            bucket = '>1' if amount > 1.0 else '<=1'
            total[bucket] += 1
            cls = step.classification
            cats[(bucket, cls.category, cls.status)] += 1
    assert total == {'>1': 162, '<=1': 15}
    assert cats == {
        ('>1', 'open', 'resolved'): 115,
        ('>1', 'rol', 'resolved'): 44,
        ('>1', '3bet', 'resolved'): 2,
        ('<=1', 'limp', 'resolved'): 14,
        ('<=1', 'unknown', 'unresolved'): 1,
        ('>1', 'unknown', 'unresolved'): 1,
    }


def test_serving_viejo_y_contrato_nuevo_difieren_en_3967_estados(hands_877):
    same = 0
    diff = 0
    unresolved = 0
    for hand in hands_877:
        for ev in preflop_events(hand):
            old = _preflop_spot(hand, ev.pos)
            new = first_decision(hand, ev.pos)
            if not new.resolved:
                unresolved += 1
            elif old != (new.denom, new.category):
                diff += 1
            else:
                same += 1
    assert (same, diff, unresolved) == (591, 3968, 35)


@pytest.mark.xfail(strict=True,
                   reason='La desalineación actual se mantiene en sombra: '
                          '_preflop_spot sigue leyendo el último carácter. '
                          'Cuando se active el contrato, este xfail pasará a '
                          'XPASS y exigirá actualizar el test.')
def test_xfail_paridad_serving_viejo_877(hands_877):
    """Demuestra, de forma ejecutable, que HOY no hay paridad live."""
    for hand in hands_877:
        for ev in preflop_events(hand):
            old = _preflop_spot(hand, ev.pos)
            new = first_decision(hand, ev.pos)
            if not new.resolved:
                continue
            assert old == (new.denom, new.category)


def test_estado_de_tablas_del_heroe_difiere_en_208_estados(hands_877):
    same = 0
    diff = 0
    unresolved = 0
    for hand in hands_877:
        acts = actions_of(hand)
        for ev in preflop_events(hand):
            prefix = []
            seen = False
            for a in acts:
                if a.get('pos') == ev.pos:
                    seen = True
                    break
                prefix.append(a)
            if not seen:
                continue
            old_n, old_vs, _old_amount = _preflop_raises(prefix, ev.pos)
            old_limp = False
            raise_seen = False
            for a in prefix:
                if a.get('pos') == ev.pos:
                    continue
                if a.get('action') == 'r':
                    raise_seen = True
                elif a.get('action') == 'c' and not raise_seen:
                    old_limp = True
            plan = plan_from_context(context_at(prefix))
            if plan.status != 'resolved':
                unresolved += 1
            elif (old_n, bool(old_limp), old_vs) != \
                    (plan.raises_before, plan.limps_before > 0, plan.vs_pos):
                diff += 1
            else:
                same += 1
    assert (same, diff, unresolved) == (4379, 213, 2)


# ---------------------------------------------------------------------------
# Sombra: registra sin cambiar la recomendación
# ---------------------------------------------------------------------------

def _asis(hand=None):
    a = Asistente.__new__(Asistente)
    a.rec = SimpleNamespace(hand=hand)
    a.verbose = False
    a.live_stacks = {}
    a._last_seen_stake = {}
    a.models = SimpleNamespace()
    a.shadow = True
    a._preflop_shadow_log_obj = ShadowPreflopLog()
    return a


def test_sombra_de_spot_registra_viejo_nuevo_contexto_y_diferencia():
    hand = _hand([('SB', 'p', 0.5), ('BB', 'p', 1.0),
                  ('UTG', 'r', 2.5)])
    a = _asis(hand)
    a._preflop_shadow_spot('test_consumer', 'UTG', 'facing_open', '3bet')
    rec = a._preflop_shadow_log_obj.records[-1]
    assert rec['consumer'] == 'test_consumer'
    assert rec['old'] == {'spot': 'facing_open', 'action': '3bet',
                          'vs_pos': ''}
    assert rec['new']['spot'] == 'no_raise'
    assert rec['new']['action'] == 'open'
    assert rec['new']['status'] == 'resolved'
    assert rec['new']['classification']['context']['raises_before'] == 0
    assert rec['difference'] is True
    assert rec['unresolved'] is False
    assert 'spot_accion' in rec['difference_fields']


def test_sombra_de_heroe_registra_el_estado_de_las_tablas():
    hand = _hand([('BB', 'p', 1.0), ('UTG', 'b', 2.5),
                  ('MP', 'c', 2.5)])
    a = _asis(hand)
    a._preflop_shadow_hero(actions_of(hand), 'MP')
    rec = a._preflop_shadow_log_obj.records[-1]
    assert rec['consumer'] == 'hero_preflop_tables'
    assert rec['old']['n_raises'] == 0
    assert rec['new']['raises_before'] == 1
    assert rec['new']['table_raise'] == '3B'
    assert rec['new']['table_call'] == 'Call_OR'
    assert rec['difference'] is True
    assert 'n_raises' in rec['difference_fields']


def test_sombra_no_cambia_la_recomendacion_preflop():
    hand = _hand([('BB', 'p', 1.0), ('UTG', 'b', 2.5)], 'H_SOMBRA')
    a = _asis(hand)
    state = {'pot': 2.0, 'hero_state': 'activo', 'p1_state': 'activo',
             'p2_state': 'activo', 'p3_state': 'activo',
             'p4_state': 'activo', 'p5_state': 'activo'}

    a._preflop_shadow_log_obj = ShadowPreflopLog(enabled=False)
    antes = a._recom_preflop(state, ['As', 'Ks'], 'BTN', 0.0, 2.0, 2.5,
                             'TIBURON', 'x', None, False, seed=7)
    a._preflop_shadow_log_obj = ShadowPreflopLog(enabled=True)
    despues = a._recom_preflop(state, ['As', 'Ks'], 'BTN', 0.0, 2.0, 2.5,
                               'TIBURON', 'x', None, False, seed=7)

    assert antes is not None and despues is not None
    assert antes.ev == despues.ev
    assert antes.chosen == despues.chosen
    assert antes.candidate_actions == despues.candidate_actions
    assert a._preflop_shadow_log_obj.count == 1
    assert a._preflop_shadow_log_obj.records[0]['difference'] is True


def test_log_de_sombra_no_escribe_en_data_por_defecto(tmp_path):
    log = ShadowPreflopLog()
    assert log.path is None
    assert log.append({'difference': True}) is True
    assert log.count == 1
    assert log.differences() == [{'difference': True}]

    path = tmp_path / 'shadow_preflop.jsonl'
    log2 = ShadowPreflopLog(path=str(path))
    assert log2.append({'id': 1}) is True
    assert path.read_text(encoding='utf-8').strip() == '{"id": 1}'
