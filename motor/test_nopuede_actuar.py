# -*- coding: utf-8 -*-
"""La regla del raise queda rechazada: estos casos la desmontan.

La implementacion canonica esta en `motor/multiway.py` y se prueba en
`motor/test_multiway.py`. Aqui quedan los casos SINTETICOS que separan una
SUBIDA de un ALL-IN, que es lo que pidio revision_1 para poder firmar el
contrato F7.2.a sin fear de que la regla nueva vuelva a ser la vieja.

La regla del raise vive aqui como ESPECIMEN CONGELADO, no como
implementacion: `_regla_del_raise_rechazada`. Vive en el fichero de test y
no en `motor/` a proposito, para que se pueda demostrar que falla sin
tenerla cableada en ningun sitio. `test_no_hay_dos_implementaciones` (en
`motor/test_multiway.py`) vigila que no vuelva a existir una copia viva.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from motor.multiway import (                                # noqa: E402
    PLAYER_IDS, acciones, clasificar_decision, en_bote,
    en_bote_en_instante, folds_hasta, instante_decision, no_puede_actuar,
    no_puede_actuar_en_instante, posiciones_allin, puede_responder,
)

_POS_FIJOS = ('UTG', 'MP', 'CO', 'BTN', 'SB', 'BB')
ID_DE_POS = dict(zip(_POS_FIJOS, PLAYER_IDS))


def mano(preflop=(), flop=(), turn=(), river=(), allin=(),
         stacks=None, con_campo_allin=True, n_players=6):
    """Mano minima con la forma EXACTA que produce `recorder_live`."""
    stacks = stacks or {}
    players = [{'active': True, 'name': 'P%d' % i,
                'pos': _POS_FIJOS[i] if i < len(_POS_FIJOS) else '',
                'stack': stacks.get(_POS_FIJOS[i], 100.0),
                'cards': 'AsKd' if i == 0 else ''}
               for i in range(n_players)]
    h = {'hand_id': 'TEST', 'players': players,
         'streets': {st: {'actions': [{'pos': p, 'action': a, 'amount': m}
                                       for p, a, m in acts], 'board': []}
                     for st, acts in (('preflop', preflop), ('flop', flop),
                                      ('turn', turn), ('river', river))}}
    if con_campo_allin:
        h['allin'] = list(allin)
    return h


# ---------------------------------------------------------------------------
# ESPECIMEN CONGELADO DE LA REGLA RECHAZADA
# ---------------------------------------------------------------------------
def _regla_del_raise_rechazada(hand, street):
    """La regla de F7.1: "ha subido -> no puede actuar". NO SE USA EN EL MOTOR.

    Se conserva para poder medir su error y para que los tests de abajo
    Demonstrate que sigue siendo incapaz de estar bien. Medido: 14,6% de
    precision sobre la ventana fiable.
    """
    streets = hand.get('streets') or {}
    activos = {p.get('pos') for p in (hand.get('players') or [])
               if p.get('active')}
    for st in ('preflop', 'flop', 'turn', 'river'):
        for a in ((streets.get(st) or {}).get('actions') or []):
            if isinstance(a, dict) and a.get('pos') and a.get('action') == 'r':
                activos.discard(a.get('pos'))
        if st == street:
            break
    return {p.get('pos') for p in (hand.get('players') or [])
            if p.get('active')} - activos


# ===========================================================================
# 1. Un raise ordinario NO es un all-in
# ===========================================================================
def test_raise_ordinario_no_es_allin():
    """BTN sube 9.0 conservando 141.1 de stack: sigue pudiendo actuar."""
    h = mano(preflop=[('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
                      ('SB', 'f', 0.0), ('BB', 'c', 9.0), ('UTG', 'c', 9.0)],
             allin=[], stacks={'BTN': 141.1})
    assert 'BTN' not in no_puede_actuar(h, 'flop')


def test_la_regla_rechazada_marca_el_raise_ordinario():
    """Su error principal, aislado: confunde subir con comprometerse."""
    h = mano(preflop=[('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
                      ('SB', 'f', 0.0), ('BB', 'c', 9.0), ('UTG', 'c', 9.0)],
             allin=[], stacks={'BTN': 141.1})
    assert 'BTN' in _regla_del_raise_rechazada(h, 'flop')


# ===========================================================================
# 2. Resubida: tres veces subido y ninguno all-in
# ===========================================================================
def test_resubida_no_es_allin():
    """MP abre, CO resubide y conserva fichas: no es all-in."""
    h = mano(preflop=[('UTG', 'b', 3.0), ('MP', 'r', 9.0), ('CO', 'r', 24.0),
                      ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'f', 0.0)],
             allin=[], stacks={'CO': 99.9})
    assert 'CO' not in no_puede_actuar(h, 'flop')


def test_resubida_no_superada_tampoco_es_allin():
    """Que nadie supere la resubida no convierte al resubidor en all-in."""
    h = mano(preflop=[('UTG', 'b', 3.0), ('MP', 'r', 9.0), ('CO', 'r', 24.0),
                      ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'f', 0.0),
                      ('UTG', 'c', 24.0)],
             allin=[], stacks={'CO': 99.9, 'MP': 40.0})
    assert 'CO' not in no_puede_actuar(h, 'flop')


# ===========================================================================
# 3. All-in de verdad: por raise y por call
# ===========================================================================
def test_allin_por_raise_no_puede_actuar():
    h = mano(preflop=[('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
                      ('SB', 'f', 0.0), ('BB', 'f', 0.0), ('UTG', 'r', 38.2)],
             allin=[ID_DE_POS['UTG']], stacks={'UTG': 38.2})
    assert no_puede_actuar(h, 'flop') == {'UTG'}


def test_allin_por_call_no_puede_actuar():
    """Iguala un all-in sin haber subido nunca: la regla vieja lo pierde.

    Es el falso negativo que Nobody had on the radar: un `call` a un
    all-in no registra `'r'`, asi que la regla del raise no lo ve nunca.
    """
    h = mano(preflop=[('UTG', 'b', 3.0), ('MP', 'f', 0.0), ('CO', 'f', 0.0),
                      ('BTN', 'r', 38.2), ('SB', 'f', 0.0), ('BB', 'f', 0.0),
                      ('UTG', 'c', 38.2)],
             allin=[ID_DE_POS['UTG']], stacks={'UTG': 38.2, 'BTN': 141.1})
    assert no_puede_actuar(h, 'flop') == {'UTG'}
    assert 'UTG' not in _regla_del_raise_rechazada(h, 'flop')


# ===========================================================================
# 4. Fold
# ===========================================================================
def test_fold_no_genera_no_puede_actuar():
    h = mano(preflop=[('UTG', 'f', 0.0), ('MP', 'f', 0.0), ('BTN', 'b', 3.0),
                      ('SB', 'f', 0.0), ('BB', 'f', 0.0)],
             allin=[])
    assert no_puede_actuar(h, 'flop') == set()


def test_foldeo_una_calle_tarde_no_bloquea_en_la_anterior():
    """BB foldea en el turn: en el flop todavia puede actuar."""
    h = mano(preflop=[('UTG', 'b', 3.0), ('MP', 'c', 3.0), ('CO', 'f', 0.0),
                      ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'c', 3.0)],
             turn=[('BB', 'f', 0.0)], allin=[])
    assert 'BB' not in no_puede_actuar(h, 'flop')


def test_fold_posterior_al_allin_es_registro_corrupto():
    """CASO LIMITE CONOCIDO (INC-002), no un fallo de la regla.

    El recorder filtra `allin` con `p['active']`, que significa "estaba
    sentado al empezar". Un jugador que se commitmenta y despues foldea
    se queda en la lista. La regla lo cree: es un dato malo, no una
    inferencia. 1 caso en 900.
    """
    h = mano(preflop=[('UTG', 'b', 3.0), ('MP', 'c', 3.0), ('CO', 'f', 0.0),
                      ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'c', 3.0)],
             flop=[('UTG', 'b', 10.0), ('BB', 'f', 0.0)],
             allin=[ID_DE_POS['UTG']])
    assert 'BB' in folds_hasta(h, 'flop')
    assert 'UTG' in no_puede_actuar(h, 'flop'), 'y aun asi lo da por all-in'
    # lo que NO hace es marcar a BB, que solo folteo:
    assert 'BB' not in no_puede_actuar(h, 'flop')


# ===========================================================================
# 5. Calle del all-in
# ===========================================================================
def test_allin_en_una_calle_no_bloquea_en_la_anterior():
    h = mano(preflop=[('UTG', 'b', 3.0), ('MP', 'c', 3.0), ('CO', 'f', 0.0),
                      ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'c', 3.0)],
             flop=[('MP', 'b', 5.0), ('BB', 'c', 5.0)],
             turn=[('MP', 'r', 140.1)], allin=[ID_DE_POS['MP']],
             stacks={'MP': 140.1})
    assert 'MP' not in no_puede_actuar(h, 'flop')
    assert 'MP' in no_puede_actuar(h, 'turn')


def test_allin_en_el_flop_bloquea_desde_el_flop():
    h = mano(preflop=[('UTG', 'b', 3.0), ('MP', 'c', 3.0), ('CO', 'f', 0.0),
                      ('BTN', 'f', 0.0), ('SB', 'f', 0.0), ('BB', 'c', 3.0)],
             flop=[('MP', 'r', 140.1)], allin=[ID_DE_POS['MP']],
             stacks={'MP': 140.1})
    assert 'MP' in no_puede_actuar(h, 'flop')


# ===========================================================================
# 6. Los tres casos de "sin evidencia"
# ===========================================================================
def test_caso_1_campo_allin_ausente():
    h = mano(preflop=[('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
                      ('SB', 'f', 0.0), ('BB', 'c', 9.0), ('UTG', 'c', 9.0)],
             con_campo_allin=False)
    assert posiciones_allin(h) is None
    assert no_puede_actuar(h, 'flop') is None
    assert no_puede_actuar_en_instante(h, 'flop', 0) is None
    assert puede_responder(h, 'flop', 0) is None


def test_caso_2_calle_de_allin_indeterminada():
    """Esta en `allin` pero no tiene ninguna accion: no se sabe cuando."""
    # MP no aparece en NINGUNA accion de la mano.
    h = mano(preflop=[('CO', 'f', 0.0), ('BTN', 'r', 9.0), ('SB', 'f', 0.0),
                      ('BB', 'c', 9.0), ('UTG', 'c', 9.0)],
             allin=[ID_DE_POS['MP']])
    assert posiciones_allin(h) == {'MP'}
    assert no_puede_actuar(h, 'flop') is None


def test_caso_3_players_con_otro_tamano():
    h = mano(allin=[ID_DE_POS['BTN']], n_players=4)
    assert posiciones_allin(h) is None
    assert no_puede_actuar(h, 'flop') is None


def test_allin_vacio_es_vacio_de_verdad():
    """`allin: []` SI es informacion: significa que nadie se commitmento."""
    h = mano(preflop=[('MP', 'f', 0.0), ('CO', 'f', 0.0), ('BTN', 'r', 9.0),
                      ('SB', 'f', 0.0), ('BB', 'c', 9.0), ('UTG', 'c', 9.0)],
             allin=[])
    assert posiciones_allin(h) == set()
    assert no_puede_actuar(h, 'flop') == set()
    assert puede_responder(h, 'flop', 0) is not None


# ===========================================================================
# 7. Decision completa
# ===========================================================================
def test_multiway_con_allin_que_no_es_el_raiser():
    """CO se commitmenta igualando; BTN y SB son los que suben.

    La regla del raise se equivoca en las dos direcciones: marca a BTN y
    SB (subieron, pero conservan fichas) y no marca a CO (se commitmento,
    pero no subio). Deja un solo rival y dice HU, cuando BTN y SB pueden
    responder los dos.
    """
    h = mano(preflop=[('MP', 'f', 0.0), ('CO', 'b', 3.0), ('BTN', 'r', 9.0),
                      ('SB', 'r', 24.0), ('BB', 'f', 0.0), ('UTG', 'c', 24.0),
                      ('CO', 'c', 24.0)],
             flop=[('UTG', 'b', 10.0)], allin=[ID_DE_POS['CO']],
             stacks={'CO': 24.0, 'BTN': 141.1, 'SB': 29.7, 'UTG': 140.0})
    bote = en_bote(h, 'flop') | {'UTG'}
    assert bote == {'UTG', 'BTN', 'SB', 'CO'}, 'los cuatro siguen en el bote'

    viejo = _regla_del_raise_rechazada(h, 'flop')
    assert viejo == {'BTN', 'SB'}, 'la regla vieja se inventa dos all-ins'
    nuevo = no_puede_actuar(h, 'flop')
    assert nuevo == {'CO'}, 'el unico all-in real es CO'

    assert len(bote - viejo) - 1 == 1, 'con la vieja sale HU'
    assert len(bote - nuevo) - 1 == 2, 'con la buena sale MULTIWAY'


def test_desconocido_no_se_colapsa_en_hu():
    """Sin evidencia, la clasificacion es DESCONOCIDO y no HU."""
    h = mano(preflop=[('MP', 'f', 0.0), ('CO', 'b', 3.0), ('BTN', 'r', 9.0),
                      ('SB', 'f', 0.0), ('BB', 'c', 9.0), ('UTG', 'c', 9.0)],
             flop=[('UTG', 'b', 10.0)], con_campo_allin=False)
    r = clasificar_decision(h, 'flop')
    assert r['clase'] == 'DESCONOCIDO'
    assert r['sin_evidencia'] is True
    assert r['pueden'] is None


# ===========================================================================
# 8. Autoverificacion: la regla rechazada sigue sin poder estar bien
# ===========================================================================
@pytest.mark.parametrize('caso', ['raise_ordinario', 'allin_por_call',
                                  'multiway'])
def test_la_regla_rechazada_no_puede_estar_correcta(caso):
    """Si algun dia esta funcion acertara estos casos, hay que borrarla.

    Mientras siga fallando, los tests de arriba estan midiendo EL BUG y no
    otra cosa. Si este test falla de verdad, la regla nueva se ha
    fusionado con la vieja por error y estas expectativas estan obsoletas.
    """
    fn = {
        'raise_ordinario': test_la_regla_rechazada_marca_el_raise_ordinario,
        'allin_por_call': test_allin_por_call_no_puede_actuar,
        'multiway': test_multiway_con_allin_que_no_es_el_raiser,
    }[caso]
    fn()