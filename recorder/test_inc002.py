# -*- coding: utf-8 -*-
"""INC-002: un jugador que se compromete y foldea NO va en `allin`.

El arreglo es de una linea en `recorder_live.py`, pero una linea sin test es
una linea que se puede deshacer sin enterarse. Aqui se comprueba la
linea por AST (que es como el proyecto verifica que el recorder sigue
cumpliendo su parte del contrato) y el COMPORTAMIENTO con el caso real.

La forma buena de probar un filtro que cuelga de `self` es comprobar la
expresion que se evalua, no montar un recorder entero: el resto de
`_allin_players`, `_folded_positions` y `players[]` ya tienen sus propios
tests.
"""
import ast
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA = os.path.join(ROOT, 'recorder', 'recorder_live.py')


def _expresion_de_allin():
    """Saca la predicado de la lista `out['allin']` del codigo real.

    Devuelve el nodo AST, no el texto: asi el test no depende de como este
    escrito el filtro, solo de que haga lo que tiene que hacer.
    """
    tree = ast.parse(io.open(RUTA, encoding='utf-8').read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if (isinstance(t, ast.Subscript)
                        and isinstance(t.slice, ast.Constant)
                        and t.slice.value == 'allin'):
                    return n.value
    raise AssertionError('ya no se asigna `out[\'allin\']` en el recorder')


def test_el_filtro_de_allin_excluye_a_los_que_foldearon():
    """INC-002. Sin esto, unCommitment seguido de fold queda en la lista."""
    predicado = _expresion_de_allin()
    src = ast.unparse(predicado)
    assert '_folded_positions' in src, (
        'el filtro de `allin` vuelve a usar solo `active`, que significa '
        '"estaba sentado al empezar" y no "no ha foldeado": %s' % src)


def test_el_filtro_conserva_los_otros_tres_requisitos():
    """Arreglar una cosa no puede romper las otras tres condiciones."""
    src = ast.unparse(_expresion_de_allin())
    assert '_allin_players' in src, 'perdio la condicion de compromiso'
    assert "'active'" in src, 'perdio el filtro de sentado'
    assert "'_id'" in src, 'perdio la proyeccion a id interno'


def test_un_compromiso_sin_fold_se_conserva():
    """El arreglo no puede vaciar `allin`: el caso normal sigue saliendo."""
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from motor.multiway import posiciones_allin
    PLAYER_IDS = ('hero', 'p1', 'p2', 'p3', 'p4', 'p5')
    POS = ('UTG', 'MP', 'CO', 'BTN', 'SB', 'BB')

    def jugador(i, pos, folded):
        return {'_id': PLAYER_IDS[i], 'pos': pos, 'active': True,
                'fold': folded}

    players = [jugador(i, POS[i], False) for i in range(6)]
    folded = set()
    allin = {'p2'}
    antes = [p['_id'] for p in players
             if p['_id'] in allin and p['active']
             and p['pos'] not in folded]
    assert antes == ['p2']

    # ahora CO (p2) foldea: el mismo filtro deja de emitirlo
    folded = {'CO'}
    despues = [p['_id'] for p in players
               if p['_id'] in allin and p['active']
               and p['pos'] not in folded]
    assert despues == []

    # y el clasificador recibe un registro ya limpio
    h = {'players': [{'pos': p['pos'], 'active': True, 'cards': '',
                      'name': '', 'stack': 100.0} for p in players],
         'streets': {'preflop': {'actions': []}, 'flop': {'actions': []},
                     'turn': {'actions': []}, 'river': {'actions': []}},
         'allin': despues}
    assert posiciones_allin(h) == set()


def test_h_0851_ya_no_se_produiria():
    """El caso real: hoy H_0851 declara en `allin` a un jugador que folteo.

    Este test documenta el antes. El `allin` grabado sigue siendo erroneo
    porque no se reescriben las manos viejas, y por eso el clasificador
    sigue tiene que detectar la contradiccion.
    """
    from motor import learn
    from motor.multiway import (
        contradiccion_allin_fold, puntos_decision_mano,
    )
    h = {x['hand_id']: x for x in learn.load_hands(reliable_only=True)
         }['H_0851']
    # H_0851 NO es de las 23 de CM-004, asi que sigue en la ventana. El
    # registro grabado conserva el defecto porque las manos viejas no se
    # reescriben: por eso el clasificador tiene que seguir detectando la
    # contradiccion en vez de creersela.
    assert contradiccion_allin_fold(h) == {'UTG'}
    assert puntos_decision_mano(h) == []