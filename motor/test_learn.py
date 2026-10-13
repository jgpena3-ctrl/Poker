"""Test de motor/learn.py — extracción de frecuencias preflop."""
import pytest

from motor.learn import (
    CATEGORY_DENOM, HERO_NAMES, PreflopEvent, PreflopStats,
    classify_first_action, hand_known, load_hands, preflop_events,
)


def _hand(hand_id='H_9001', players=None, preflop=None):
    players = players or [
        {'name': 'Jarduan', 'pos': 'CO', 'cards': 'JdTd'},
        {'name': 'Villian', 'pos': 'BB', 'cards': ''},
    ]
    return {
        'hand_id': hand_id,
        'players': players,
        'streets': {'preflop': {'actions': preflop or []}},
    }


# ---------------------------------------------------------------------------
# classify_first_action — cobertura de todas las categorías
# ---------------------------------------------------------------------------

def test_classify_no_raise_state():
    assert classify_first_action('f', 0, 0, 0)[:2] == ('fold', 'no_raise')
    assert classify_first_action('c', 1.0, 0, 0)[:2] == ('limp', 'no_raise')
    assert classify_first_action('b', 2.5, 0, 0)[:2] == ('open', 'no_raise')
    assert classify_first_action('b', 3.0, 0, 1)[:2] == ('rol', 'no_raise')
    assert classify_first_action('c', 1.0, 0, 1)[:2] == ('call_limp', 'no_raise')
    assert classify_first_action('x', 0, 0, 2)[:2] == ('bb_check', 'no_raise')


def test_classify_facing_open():
    assert classify_first_action('c', 2.5, 1, 0)[:2] == ('call_open', 'facing_open')
    assert classify_first_action('r', 4.0, 1, 0)[:2] == ('3bet', 'facing_open')
    assert classify_first_action('f', 0, 1, 0)[:2] == ('fold_vs_open', 'facing_open')
    # squeeze exige un CALLER del open (callers>=1), no un limpe.
    # OJO: `callers` va por keyword; el 5o positional es `bb`.
    assert classify_first_action('r', 4.0, 1, 0, callers=1)[:2] == \
        ('squeeze', 'facing_open')
    # un limpe anterior al open NO convierte en squeeze el 3bet posterior
    assert classify_first_action('r', 4.0, 1, 1, callers=0)[:2] == \
        ('3bet', 'facing_open')


def test_classify_facing_3bet():
    assert classify_first_action('c', 9.0, 2, 0)[:2] == ('call_3bet', 'facing_3bet')
    assert classify_first_action('r', 12.0, 2, 0)[:2] == ('4bet', 'facing_3bet')
    assert classify_first_action('f', 0, 2, 0)[:2] == ('fold_vs_3bet', 'facing_3bet')


def test_classify_unknown_action_raises():
    with pytest.raises(ValueError):
        classify_first_action('z', 0, 0, 0)


def test_denom_consistency():
    for cat, denom in CATEGORY_DENOM.items():
        assert denom in ('no_raise', 'facing_open', 'facing_3bet')
    assert set(CATEGORY_DENOM.values()) == {'no_raise', 'facing_open', 'facing_3bet'}
    for cat in ('open', 'limp', 'rol', 'call_open', '3bet', 'squeeze', '4bet'):
        assert cat in CATEGORY_DENOM


# ---------------------------------------------------------------------------
# preflop_events sobre una mano sintética
# ---------------------------------------------------------------------------

def test_events_single_hand():
    hand = _hand(preflop=[
        {'pos': 'CO', 'action': 'b', 'amount': 2.5},
        {'pos': 'BB', 'action': 'f', 'amount': 0},
    ])
    events = preflop_events(hand)
    co = events[0]
    bb = events[1]
    assert len(events) == 2
    assert (co.player, co.category, co.denom, co.hand_known) == \
        ('Jarduan', 'open', 'no_raise', True)
    assert (bb.player, bb.category, bb.denom, bb.hand_known) == \
        ('Villian', 'fold_vs_open', 'facing_open', False)


def test_hero_sin_cards_no_es_mano_conocida():
    """Un hero sin cartas NO cuenta como mano conocida (F2.6).

    Antes `hand_known` devolvía True para Jarduan siempre, lo que inventaba
    información que el recorder no registró. Ver PROYECTO.md §6.1.
    """
    hand = _hand(
        players=[
            {'name': 'Jarduan', 'pos': 'UTG', 'cards': ''},
            {'name': 'Villian', 'pos': 'BB', 'cards': ''},
        ],
        preflop=[('UTG', 'b', 2.5), ('BB', 'x', 0)],
    )
    events = preflop_events(hand)
    assert events[0].hand_known is False   # hero sin cartas
    assert events[1].hand_known is False
    assert hand_known('Jarduan', '') is False
    assert hand_known('Jarduan', 'AsKd') is True


def test_first_decision_only():
    hand = _hand(preflop=[
        ('CO', 'c', 1.0),        # limp
        ('CO', 'f', 0.0),        # segunda acción no cuenta
        ('BB', 'r', 5.0),        # no_raise? raises_before incluye 0 raises → open
    ])
    events = preflop_events(hand)
    cols = [ev.pos for ev in events]
    assert cols == ['CO', 'BB']
    assert events[0].category == 'limp'


def test_rol_and_squeeze_sequences():
    hand = _hand(
        preflop=[('UTG', 'c', 1.0), ('CO', 'r', 4.0), ('BB', 'f', 0)],
        players=[
            {'name': 'A', 'pos': 'UTG', 'cards': ''},
            {'name': 'Jarduan', 'pos': 'CO', 'cards': 'AhKh'},
            {'name': 'Villian', 'pos': 'BB', 'cards': ''},
        ],
    )
    events = preflop_events(hand)
    by_pos = {e.pos: e for e in events}
    assert by_pos['UTG'].category == 'limp'
    assert by_pos['CO'].category == 'rol'
    assert by_pos['CO'].prereq[0] == 'UTG:c'


def test_squeeze_detection():
    hand = _hand(
        preflop=[('UTG', 'b', 2.5), ('CO', 'c', 2.5), ('BTN', 'r', 8.0)],
        players=[
            {'name': 'A', 'pos': 'UTG', 'cards': ''},
            {'name': 'B', 'pos': 'CO', 'cards': ''},
            {'name': 'Jarduan', 'pos': 'BTN', 'cards': ''},
        ],
    )
    by_name = {e.player: e for e in preflop_events(hand)}
    assert by_name['Jarduan'].category == 'squeeze'
    assert by_name['B'].category == 'call_open'


def test_bb_check_walk():
    hand = _hand(
        preflop=[('BTN', 'c', 1.0), ('BB', 'x', 0)],
        players=[
            {'name': 'A', 'pos': 'BTN', 'cards': ''},
            {'name': 'Jarduan', 'pos': 'BB', 'cards': ''},
        ],
    )
    by_name = {e.player: e for e in preflop_events(hand)}
    assert by_name['A'].category == 'limp'
    assert by_name['Jarduan'].category == 'bb_check'


def test_invalid_preflop_inputs_skip():
    hand = _hand(preflop=[{'pos': '', 'action': 'b', 'amount': 2}])
    assert preflop_events(hand) == []
    hand2 = _hand(preflop=[{'pos': 'CO', 'action': '', 'amount': 2}])
    assert preflop_events(hand2) == []


# ---------------------------------------------------------------------------
# Agregación de frecuencias
# ---------------------------------------------------------------------------

def test_stats_frequency_denominators():
    hands = [
        _hand('A', preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)]),
        _hand('B', preflop=[('CO', 'b', 2.5), ('BB', 'c', 2.5)]),
    ]
    stats = PreflopStats.from_hands(hands)
    assert stats.freq('Jarduan', 'open') == pytest.approx(1.0)   # 2/2 opp
    assert stats.freq('Jarduan', 'limp') == pytest.approx(0.0)   # 0/2 opp
    assert stats.opportunities('Villian', 'call_open') == 2
    assert stats.cats['Jarduan']['open'] == 2
    assert stats.cats['Villian']['fold_vs_open'] == 1
    assert stats.cats['Villian']['call_open'] == 1


def test_stats_mix_known_unknown():
    hands = [
        _hand('A', preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)]),
        _hand('B',
              preflop=[('CO', 'b', 2.5), ('BB', 'c', 2.5)],
              players=[
                  {'name': 'Jarduan', 'pos': 'CO', 'cards': '7h2d'},
                  {'name': 'Villian', 'pos': 'BB', 'cards': 'KsQs'},
              ]),
    ]
    stats = PreflopStats.from_hands(hands)
    # Villian: 1 mano desconocida (no_raise), 1 conocida
    assert stats.denoms['Villian']['facing_open'] == 2
    assert stats.known['Villian']['facing_open'] == 1


def test_stats_to_dict_and_report():
    hands = [_hand('A', preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)])]
    stats = PreflopStats.from_hands(hands)
    d = stats.to_dict()
    assert d['hands'] == 1
    assert 'Jarduan' in d['cats'] and d['cats']['Jarduan']['open'] == 1
    text = stats.report(players=['Jarduan', 'Villian'])
    assert 'Jarduan' in text
    assert 'Villian' in text


def test_load_hands_skips_garbage(tmp_path):
    p = tmp_path / 'db.jsonl'
    p.write_text(
        'not json\n'
        '{"streets":{}}\n'                              # sin players
        '{"players":[]}\n'                              # sin streets
        '{"hand_id":"OK","players":[],"streets":{}}\n', # válida
        encoding='utf-8')
    hands = load_hands(str(p))
    assert len(hands) == 1
    assert hands[0]['hand_id'] == 'OK'


def _db_lines(n):
    return ''.join(
        '{"hand_id":"H_%04d","players":[],"streets":{}}\n' % (i + 1)
        for i in range(n))


def test_load_hands_max_hands_limita_lineas(tmp_path):
    p = tmp_path / 'db.jsonl'
    p.write_text(_db_lines(5), encoding='utf-8')
    assert len(load_hands(str(p))) == 5
    assert len(load_hands(str(p), max_hands=3)) == 3
    assert len(load_hands(str(p), max_hands=1)) == 1
    assert len(load_hands(str(p), max_hands=99)) == 5
    assert load_hands(str(p), max_hands=None) != []


def test_load_hands_max_hands_cero_o_negativo(tmp_path):
    p = tmp_path / 'db.jsonl'
    p.write_text(_db_lines(3), encoding='utf-8')
    assert load_hands(str(p), max_hands=0) == []
    assert load_hands(str(p), max_hands=-5) == []


def test_load_hands_reliable_only_usa_constante(tmp_path, monkeypatch):
    p = tmp_path / 'db.jsonl'
    p.write_text(_db_lines(1200), encoding='utf-8')
    import motor.learn as learn_mod
    monkeypatch.setattr(learn_mod, 'RELIABLE_HANDS', 900)
    assert len(load_hands(str(p), reliable_only=True)) == 900
    assert len(load_hands(str(p), reliable_only=True, max_hands=50)) == 50


# ---------------------------------------------------------------------------
# Regresión F2: ciega del BB, limps y folds (revision_1/2)
# ---------------------------------------------------------------------------

def test_ciega_bb_no_es_decision():
    """El 'b' inicial del BB es ciega: no emite evento."""
    h = _hand(preflop=[('BB', 'b', 1.0), ('UTG', 'f', 0), ('MP', 'f', 0)])
    evs = preflop_events(h)
    assert [e.pos for e in evs] == ['UTG', 'MP']
    assert all(e.category != 'limp' for e in evs)


def test_folds_contra_ciega_son_no_raise():
    """Tras la ciega (no una subida) todo fold es `fold`, no `fold_vs_open`."""
    h = _hand(preflop=[('BB', 'b', 1.0), ('UTG', 'f', 0), ('MP', 'f', 0),
                       ('CO', 'f', 0)])
    cats = [e.category for e in preflop_events(h)]
    assert cats == ['fold', 'fold', 'fold']
    assert all(c == 'fold' for c in cats)


def test_ciega_bb_detectada_aunque_haya_folds_antes():
    """Folds antes del 'b' del BB no deben romper la detección de la ciega."""
    h = _hand(preflop=[('UTG', 'f', 0), ('MP', 'f', 0), ('BB', 'b', 1.0),
                       ('CO', 'f', 0)])
    evs = preflop_events(h)
    bb = [e for e in evs if e.pos == 'BB']
    assert bb == []          # la ciega sigue sin ser decisión
    assert [e.category for e in evs] == ['fold', 'fold', 'fold']


def test_call_contra_raise_no_es_limp():
    """Un 'c' que enfrenta una subida no cuenta como limpe posterior.

    UTG abre, MP paga (call_open), CO sube: como ya hay una apuesta y alguien
    dentro, la subida de CO es un SQUEEZE, no un 3bet pelado.
    """
    h = _hand(preflop=[('UTG', 'r', 3.0), ('MP', 'c', 3.0), ('CO', 'b', 9.0)])
    evs = preflop_events(h)
    assert evs[0].category == 'open'
    assert evs[1].category == 'call_open'
    # CO sube con raises_before=1 y hay una llamada detras -> squeeze
    assert evs[2].category == 'squeeze'


def test_limp_corto_es_limp_no_open():
    """'b' de 1BB sin subida previa es limpe (F2.2), incluso con limpes previos."""
    assert classify_first_action('b', 1.0, 0, 0) == ('limp', 'no_raise')
    assert classify_first_action('b', 1.0, 0, 2) == ('limp', 'no_raise')
    assert classify_first_action('b', 2.5, 0, 0) == ('open', 'no_raise')
    assert classify_first_action('b', 2.5, 0, 1) == ('rol', 'no_raise')


def test_stats_agrega_por_posicion():
    """from_hands agrega por (jugador, posición) además de por jugador."""
    hands = [_hand('A', preflop=[('CO', 'b', 2.5), ('BB', 'f', 0)])]
    st = PreflopStats.from_hands(hands)
    assert sum(st.denoms_pos[('Jarduan', 'CO')].values()) == 1
    assert st.opportunities('Jarduan', pos='CO') == 1
    assert st.opportunities('Jarduan', 'open', pos='CO') == 1
    assert st.freq('Jarduan', 'open', pos='CO') == pytest.approx(1.0)
    # el total NO es el denominador de 'open': no_raise != facing_open
    assert st.opportunities('Jarduan') == 1


def test_stats_to_dict_incluye_posiciones():
    st = PreflopStats.from_hands([_hand('A', preflop=[('CO', 'b', 2.5)])])
    d = st.to_dict()
    assert 'denoms_pos' in d and 'cats_pos' in d
    assert 'Jarduan|CO' in d['denoms_pos']


# ---------------------------------------------------------------------------
# Checklist de aceptación de revision_2 (8/8)
# ---------------------------------------------------------------------------

def test_aceptacion_1_bb_marcada_no_es_open_ni_limp():
    """[ ] Un BB con blind explícita nunca se contabiliza como open ni limp."""
    h = _hand(preflop=[{'pos': 'BB', 'action': 'b', 'amount': 1.0,
                        'blind': True}, ('UTG', 'f', 0.0)])
    evs = preflop_events(h)
    assert [e.pos for e in evs] == ['UTG']
    assert not any(e.pos == 'BB' for e in evs)


def test_aceptacion_2_limp_seguido_de_raise_no_son_dos_subidas():
    """[ ] Un limp seguido de raise produce un limp y una subida real."""
    h = _hand(preflop=[('MP', 'c', 1.0), ('CO', 'r', 3.0), ('BTN', 'c', 3.0)])
    evs = preflop_events(h)
    assert [e.category for e in evs] == ['limp', 'rol', 'call_open']
    # el BTN ve UNA subida, no dos: por eso call_open y no call_3bet
    assert evs[2].category == 'call_open'


def test_aceptacion_3_raise_sobre_limp_es_rol():
    """[ ] Una subida posterior al limp se clasifica como raise-over-limp."""
    h = _hand(preflop=[('MP', 'c', 1.0), ('CO', 'r', 3.0), ('BTN', 'f', 0.0)])
    evs = preflop_events(h)
    assert evs[1].category == 'rol'
    assert evs[1].denom == 'no_raise'      # no cuenta como facing_open
    assert evs[2].category == 'fold_vs_open'


def test_aceptacion_4_folds_antes_no_alteran_la_ciega():
    """[ ] Los folds previos a la ciega no alteran su clasificación."""
    a = _hand('A', preflop=[('BB', 'b', 1.0), ('UTG', 'f', 0), ('CO', 'f', 0)])
    b = _hand('B', preflop=[('UTG', 'f', 0), ('CO', 'f', 0), ('BB', 'b', 1.0)])
    ca = [e.category for e in preflop_events(a)]
    cb = [e.category for e in preflop_events(b)]
    assert ca == ['fold', 'fold']
    assert cb == ['fold', 'fold']


def test_aceptacion_5_squeeze_necesita_apuesta_previa():
    """squeeze = subir cuando alguien YA PAGO la apuesta vigente.

    Secuencias exactas (revision_2 pide fijar esta semantica con test):
      - open -> call -> raise = squeeze (hay un caller del open)
      - open -> raise = 3bet pelado
      - limp -> open over limp -> raise = 3bet (el limp NO es caller)
    """
    squeeze = _hand('A', preflop=[('UTG', 'b', 2.5), ('CO', 'c', 2.5),
                                  ('BTN', 'r', 8.0)])
    assert preflop_events(squeeze)[2].category == 'squeeze'

    tresbet = _hand('B', preflop=[('UTG', 'b', 2.5), ('CO', 'r', 8.0)])
    assert preflop_events(tresbet)[1].category == '3bet'

    # El caso que la revision_1 destapo (13 falsos squeezes en las 900):
    # un limpe NO convierte en squeeze el 3bet posterior, porque el limpe
    # ocurrio ANTES del open y por tanto nadie ha pagado ese open.
    falso = _hand('C', preflop=[('UTG', 'c', 1.0),      # limp
                                ('MP', 'r', 3.0),       # open over limp
                                ('CO', 'r', 8.0)])      # 3bet del CO
    assert preflop_events(falso)[2].category == '3bet'


def test_squeeze_regresion_sobre_las_900():
    """Progreso de la correccion de squeeze: 95 -> 7 -> 32 -> 26.

    - 95 : `limps` contaba cualquier 'c' (los callers del open contaban como
           limpes), lo que inflaba squeeze.
    - 7  : se conto `limps` solo con raises==0 y se rompio squeeze del todo.
    - 32 : se separo `callers`, pero `limps_before` seguia contando.
    - 26 : squeeze = `callers >= 1` unicamente (estado actual).
    """
    st = PreflopStats.from_hands(load_hands(reliable_only=True))
    total = sum(st.cats[p]['squeeze'] for p in st.cats)
    assert total == 26, 'squeeze=%d, se esperaba 26' % total


def test_aceptacion_6_bb_no_detectado_si_hay_limp_antes():
    """Un 'b' del BB por encima de la ciega tras un limp NO es la ciega."""
    h = _hand(preflop=[('MP', 'c', 1.0), ('BB', 'b', 1.0)])
    evs = preflop_events(h)
    bb = [e for e in evs if e.pos == 'BB']
    assert bb, 'con un limp previo no puede assumeirse que sea la ciega'
    assert bb[0].category in ('rol', 'limp')


def test_hero_names_default():
    assert 'Jarduan' in HERO_NAMES
    assert hand_known('Jarduan', '') is False
    assert hand_known('Villian', '') is False
    assert hand_known('Villian', 'KsQs') is True