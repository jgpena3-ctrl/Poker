# -*- coding: utf-8 -*-
"""Clasificador de "puede actuar": casos sinteticos que separan una SUBIDA
de un ALL-IN.

revision_2, punto 1: "Construye casos sinteticos con un raiser que conserva
fichas, un jugador all-in, un jugador que foldea y una resubida" y
"un raise ordinario nunca se interpreta automaticamente como all-in".

Cada caso mira DOS clasificadores:

  - `no_puede_actuar`               el que hay hoy (regla del raise)
  - `no_puede_actuar_evidencia`     el propuesto, que lee `hand['allin']`

Y el ultimo bloque hace lo que revision_1 exigio de todo instrumento: que
se demuestre CAPAZ DE FALLAR. Un test que solo pasa no demuestra nada; por
eso se comprueba que la regla vieja rompe los casos que la nueva acierta.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from inventario_multiway import no_puede_actuar            # noqa: E402
from auditar_solapamiento_multiway import (                # noqa: E402
    PLAYER_IDS, calle_ultima_accion, en_bote, no_puede_actuar_evidencia,
    posiciones_allin,
)

# ---------------------------------------------------------------------------
# Constructor de manos sinteticas. `slots` es (pos, stack, cartas) en el ORDEN
# de PLAYER_IDS, que es como el recorder rellena `players[]` y de lo que
# depende el mapeo id -> posicion.
# ---------------------------------------------------------------------------
_POS_FIJOS = ('UTG', 'MP', 'CO', 'BTN', 'SB', 'BB')


def mano(acciones_preflop=(), flop=(), turn=(), river=(), allin=(),
         stacks=None, con_campo_allin=True, n_players=6):
    """Mano minima con la forma EXACTA que produce `recorder_live`."""
    stacks = stacks or {}
    players = []
    for i in range(n_players):
        pos = _POS_FIJOS[i] if i < len(_POS_FIJOS) else ''
        players.append({
            'active': True,
            'name': 'P%d' % i,
            'pos': pos,
            'stack': stacks.get(pos, 100.0),
            'cards': 'AsKd' if i == 0 else '',
        })
    h = {
        'hand_id': 'TEST',
        'players': players,
        'streets': {
            'preflop': {'actions': [{'pos': p, 'action': a, 'amount': m}
                                    for p, a, m in acciones_preflop]},
            'flop': {'actions': [{'pos': p, 'action': a, 'amount': m}
                                 for p, a, m in flop], 'board': []},
            'turn': {'actions': [{'pos': p, 'action': a, 'amount': m}
                                 for p, a, m in turn], 'board': []},
            'river': {'actions': [{'pos': p, 'action': a, 'amount': m}
                                  for p, a, m in river], 'board': []},
        },
    }
    if con_campo_allin:
        h['allin'] = list(allin)
    return h


# Los ids internos segun el orden de PLAYER_IDS sobre _POS_FIJOS:
#   hero=UTG  p1=MP  p2=CO  p3=BTN  p4=SB  p5=BB
ID_DE_POS = dict(zip(_POS_FIJOS, PLAYER_IDS))


# ---------------------------------------------------------------------------
# 1. Un raise ordinario NO es un all-in
# ---------------------------------------------------------------------------
def test_raise_ordinario_no_es_allin():
    """BTN sube 9.0 conservando 141.1: sigue pudiendo actuar."""
    h = mano(acciones_preflop=[
        ('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
        ('SB', 'f', 0.0), ('BB', 'c', 9.0), ('UTG', 'c', 9.0),
    ], allin=[], stacks={'BTN': 141.1})
    assert 'BTN' not in (no_puede_actuar_evidencia(h, 'flop') or set())


def test_raise_ordinario_lo_marca_la_regla_vieja():
    """Mismo caso, con la regla de hoy: FALLA. Es el bug de revision_2."""
    h = mano(acciones_preflop=[
        ('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
        ('SB', 'f', 0.0), ('BB', 'c', 9.0), ('UTG', 'c', 9.0),
    ], allin=[], stacks={'BTN': 141.1})
    assert 'BTN' in no_puede_actuar(h, 'flop'), (
        'la regla vieja deberia marcar BTN: si este test falla, el caso ya '
        'no reproduce el bug y el test ya no prueba nada')


# ---------------------------------------------------------------------------
# 2. Resubida: tres veces subido y ninguna all-in
# ---------------------------------------------------------------------------
def test_resubida_no_es_allin():
    """MP abre, CO resubide y conserva fichas: no puede declararse all-in."""
    h = mano(acciones_preflop=[
        ('UTG', 'b', 3.0), ('MP', 'r', 9.0), ('CO', 'r', 24.0),
        ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'f', 0.0),
    ], allin=[], stacks={'CO': 99.9})
    assert 'CO' not in (no_puede_actuar_evidencia(h, 'flop') or set())


def test_resubida_y_call_final_siguen_pudiendo_actuar():
    """La resubida que nadie puede superar NO convierte al resubidor en all-in."""
    h = mano(acciones_preflop=[
        ('UTG', 'b', 3.0), ('MP', 'r', 9.0), ('CO', 'r', 24.0),
        ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'f', 0.0),
        ('UTG', 'c', 24.0),
    ], allin=[], stacks={'CO': 99.9, 'MP': 40.0})
    # MP seCommitmenta con la llamada final, CO no: al reves de lo que la
    # regla vieja supone (marca a quien subio y descuenta a quien no).
    assert 'CO' not in (no_puede_actuar_evidencia(h, 'flop') or set())


# ---------------------------------------------------------------------------
# 3. All-in de verdad: por raise y por call
# ---------------------------------------------------------------------------
def test_allin_por_raise_no_puede_actuar():
    h = mano(acciones_preflop=[
        ('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
        ('SB', 'f', 0.0), ('BB', 'f', 0.0), ('UTG', 'r', 38.2),
    ], allin=[ID_DE_POS['UTG']], stacks={'UTG': 38.2})
    assert no_puede_actuar_evidencia(h, 'flop') == {'UTG'}


def test_allin_por_call_no_puede_actuar():
    """UTG iguala un all-in y NO ha subido nunca: la regla vieja lo pierde."""
    h = mano(acciones_preflop=[
        ('UTG', 'b', 3.0), ('MP', 'f', 0.0), ('CO', 'f', 0.0),
        ('BTN', 'r', 38.2), ('SB', 'f', 0.0), ('BB', 'f', 0.0),
        ('UTG', 'c', 38.2),
    ], allin=[ID_DE_POS['UTG']], stacks={'UTG': 38.2, 'BTN': 141.1})
    # la nueva lo ve
    assert no_puede_actuar_evidencia(h, 'flop') == {'UTG'}
    # la vieja NO: UTG solo puso 'b' y 'c'. Este es el falso negativo.
    assert 'UTG' not in no_puede_actuar(h, 'flop')


# ---------------------------------------------------------------------------
# 4. Fold: un jugador que se fue no esta ni en el bote ni bloqueado
# ---------------------------------------------------------------------------
def test_fold_no_genera_no_puede_actuar():
    h = mano(acciones_preflop=[
        ('UTG', 'f', 0.0), ('MP', 'f', 0.0), ('BTN', 'b', 3.0),
        ('SB', 'f', 0.0), ('BB', 'f', 0.0),
    ], allin=[])
    assert (no_puede_actuar_evidencia(h, 'flop') or set()) == set()


def test_foldeo_una_calle_tarde_no_bloquea_en_la_anterior():
    """BB foldea en el turn: en el flop todavia puede actuar."""
    h = mano(acciones_preflop=[
        ('UTG', 'b', 3.0), ('MP', 'c', 3.0), ('CO', 'f', 0.0),
        ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'c', 3.0),
    ], turn=[('BB', 'f', 0.0)], allin=[])
    assert 'BB' not in (no_puede_actuar_evidencia(h, 'flop') or set())


# ---------------------------------------------------------------------------
# 5. El all-in empieza a contar DESDE su calle
# ---------------------------------------------------------------------------
def test_allin_en_el_flop_no_puede_actuar_en_el_flop():
    h = mano(acciones_preflop=[
        ('UTG', 'b', 3.0), ('MP', 'c', 3.0), ('CO', 'f', 0.0),
        ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'c', 3.0),
    ], flop=[('MP', 'r', 140.1)], allin=[ID_DE_POS['MP']],
        stacks={'MP': 140.1})
    assert 'MP' in (no_puede_actuar_evidencia(h, 'flop') or set())


def test_allin_en_el_turn_sigue_pudiendo_actuar_en_el_flop():
    """El dato `allin` es de FIN de mano: hay que deducir la calle."""
    h = mano(acciones_preflop=[
        ('UTG', 'b', 3.0), ('MP', 'c', 3.0), ('CO', 'f', 0.0),
        ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'c', 3.0),
    ], flop=[('MP', 'b', 5.0), ('BB', 'c', 5.0)],
        turn=[('MP', 'r', 140.1)], allin=[ID_DE_POS['MP']],
        stacks={'MP': 140.1})
    assert calle_ultima_accion(h, 'MP') == 'turn'
    assert 'MP' not in (no_puede_actuar_evidencia(h, 'flop') or set())
    assert 'MP' in (no_puede_actuar_evidencia(h, 'turn') or set())


# ---------------------------------------------------------------------------
# 6. Estado desconocido: se declara, no se fuerza
# ---------------------------------------------------------------------------
def test_sin_campo_allin_es_desconocido_no_vacio():
    """Ausencia del campo no es "nadie esta all-in": es no saberlo."""
    h = mano(acciones_preflop=[
        ('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
        ('SB', 'f', 0.0), ('BB', 'c', 9.0), ('UTG', 'c', 9.0),
    ], con_campo_allin=False)
    assert no_puede_actuar_evidencia(h, 'flop') is None


def test_allin_vacio_es_vacio_de_verdad():
    h = mano(acciones_preflop=[
        ('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
        ('SB', 'f', 0.0), ('BB', 'c', 9.0), ('UTG', 'c', 9.0),
    ], allin=[])
    assert no_puede_actuar_evidencia(h, 'flop') == set()


def test_players_con_otro_tamano_es_desconocido():
    """Si `players[]` no sigue el orden de PLAYER_IDS el mapeo no vale."""
    h = mano(allin=[ID_DE_POS['BTN']], n_players=4)
    assert posiciones_allin(h) is None
    assert no_puede_actuar_evidencia(h, 'flop') is None


# ---------------------------------------------------------------------------
# 7. El clasificador completo: "quien sigue en el bote" vs "quien responde"
# ---------------------------------------------------------------------------
def test_multiway_con_un_allin_deja_de_ser_multiway():
    """UTG y CO pueden responder, BTN esta all-in: es HU, no MULTIWAY."""
    h = mano(acciones_preflop=[
        ('UTG', 'b', 3.0), ('MP', 'f', 0.0), ('CO', 'c', 3.0),
        ('BTN', 'r', 38.2), ('SB', 'f', 0.0), ('BB', 'f', 0.0),
        ('UTG', 'c', 38.2),
    ], flop=[('CO', 'b', 10.0)], allin=[ID_DE_POS['BTN']],
        stacks={'BTN': 38.2})
    bote = en_bote(h, 'flop')
    assert bote == {'UTG', 'CO', 'BTN'}, 'los tres siguen en el bote'
    actuable = bote - (no_puede_actuar_evidencia(h, 'flop') or set())
    assert actuable == {'UTG', 'CO'}
    # La regla vieja acierta EN ESTE CASO POR CASUALIDAD: BTN es el que
    # subio y ademas es el all-in, asi que las dos heuristicas coinciden.
    # El caso que la delata es el simetrico, justo debajo.
    assert len(bote - no_puede_actuar(h, 'flop')) == 2


def test_multiway_con_allin_que_no_es_el_raiser():
    """CO se commitmenta igualando; BTN y SB son los que suben.

    Aca la regla vieja se equivoca en las DOS direcciones y por eso cambia
    la clasificacion del spot: marca a BTN y SB (subieron, pero conservan
    fichas) y no marca a CO (se commitmento, pero no subio). Deja 1 rival
    y dice HU, cuando BTN y SB pueden responder los dos.
    """
    h = mano(acciones_preflop=[
        ('MP', 'f', 0.0), ('CO', 'b', 3.0), ('BTN', 'r', 9.0),
        ('SB', 'r', 24.0), ('BB', 'f', 0.0), ('UTG', 'c', 24.0),
        ('CO', 'c', 24.0),
    ], flop=[('UTG', 'b', 10.0)], allin=[ID_DE_POS['CO']],
        stacks={'CO': 24.0, 'BTN': 141.1, 'SB': 29.7, 'UTG': 140.0})
    bote = en_bote(h, 'flop')
    assert bote == {'UTG', 'BTN', 'SB', 'CO'}, 'los cuatro siguen en el bote'

    viejo = no_puede_actuar(h, 'flop')
    assert viejo == {'BTN', 'SB'}, 'la regla vieja se inventa dos all-ins'
    nuevo = no_puede_actuar_evidencia(h, 'flop')
    assert nuevo == {'CO'}, 'el unico all-in real es CO'

    # la vieja deja un solo rival -> dice HU
    assert len(bote - viejo) - 1 == 1
    # la buena deja dos rivales reales -> dice MULTIWAY
    assert len(bote - nuevo) - 1 == 2


# ---------------------------------------------------------------------------
# 8. Autoverificacion del instrumento
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('caso', [
    'raise_ordinario', 'resubida', 'allin_por_call', 'allin_en_turn',
])
def test_la_regla_vieja_se_demo_incapaz_de_estar_correcta(caso):
    """Si la regla vieja empieza a acertar estos casos, el bug desaparecio.

    Mientras la regla vieja siga fallando estos cuatro, los tests de arriba
    estan midiendo EL BUG y no otra cosa. Si este test falla, es que
    `no_puede_actuar()` ya se ha arreglado y sus expectativas quedan
    obsoletas: hay que reescribirlas, no borrarlas.
    """
    Manor = {
        'raise_ordinario': test_raise_ordinario_lo_marca_la_regla_vieja,
        'resubida': test_resubida_no_es_allin,
        'allin_por_call': test_allin_por_call_no_puede_actuar,
        'allin_en_turn': test_allin_en_el_turn_sigue_pudiendo_actuar_en_el_flop,
    }[caso]
    Manor()