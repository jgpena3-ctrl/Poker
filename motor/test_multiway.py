# -*- coding: utf-8 -*-
"""`motor/multiway.py` — el contrato de "puede actuar".

Tres bloques:

  1. CONTRATO DE ORDEN. El mapeo de `allin` a posicion depende de que
     `players[]` siga el orden de PLAYER_IDS. Eso no se deduce del dato:
     se deduce del CODIGO DEL RECORDER, y por eso se lee con AST en vez
     de confiar en que siga siendo cierto.
  2. TEMPORALIDAD. Casos donde el orden de las acciones cambia el
     resultado, que es lo que la regla por calle no veía.
  3. NO HAY DOS IMPLEMENTACIONES. Si aparece una segunda copia de la
     regla, el bug de la regla del raise vuelve por la puerta de atras.
"""
import ast
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from motor import multiway                                  # noqa: E402
from motor.multiway import (                                # noqa: E402
    PLAYER_IDS, HU, MULTIWAY, DESCONOCIDO, SIN_DECISION,
    acciones, clasificar_decision, en_bote_en_instante,
    folds_hasta, hero_pos, instante_decision, no_puede_actuar,
    no_puede_actuar_en_instante, posiciones_allin, puede_responder,
    secuencia, ultima_accion,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


# ===========================================================================
# 1. CONTRATO DE ORDEN
# ===========================================================================
def test_contrato_orden_players():
    """`players[]` se rellena recorriendo PLAYER_IDS, y `_id` se borra.

    revision_2 lo pedia explicitamente: que el supuesto este respaldado
    por el codigo del recorder y protegido por un test, no por un
    comentario. Si alguien reordena el `append` o deja de borrar `_id`,
    este test falla en vez de que una cifra falsa llegue a un documento.
    """
    src = io.open(os.path.join(ROOT, 'recorder', 'recorder_live.py'),
                  encoding='utf-8').read()
    tree = ast.parse(src)
    bucles = [n for n in ast.walk(tree)
              if isinstance(n, ast.For)
              and isinstance(n.iter, ast.Name)
              and n.iter.id == 'PLAYER_IDS'
              and any('players' in ast.dump(x) and 'append' in ast.dump(x)
                      for x in ast.walk(n))]
    assert bucles, 'no hay `for pid in PLAYER_IDS: ... players.append(...)`'
    # el `_id` se borra al volcar: por eso `allin` guarda ids internos.
    # Ojo: es `del p['_id']`, un Subscript, NO un Attribute.
    borrados = [n for n in ast.walk(tree)
                if isinstance(n, ast.Delete)
                and any(isinstance(t, ast.Subscript)
                        and isinstance(t.slice, ast.Constant)
                        and t.slice.value == '_id'
                        for t in ast.walk(n))]
    assert borrados, 'ya no se borra `_id`: el mapeo de `allin` cambia de golpe'


def test_orden_players_se_verifica_en_la_ventana_fiable():
    """Y ademas, en los datos reales, la longitud es la que el mapeo pide."""
    from motor import learn
    for h in learn.load_hands(reliable_only=True):
        assert multiway.contrato_orden_ok(h), (
            'una mano con %d jugadores rompe el indice de PLAYER_IDS'
            % len(h['players']))


def test_id_interno_se_resuelve_a_posicion():
    h = mano(allin=[ID_DE_POS['SB']])
    assert posiciones_allin(h) == {'SB'}


def test_mapeo_roto_es_desconocido_no_excepcion():
    h = mano(allin=[ID_DE_POS['BTN']], n_players=4)
    assert posiciones_allin(h) is None
    assert no_puede_actuar(h, 'flop') is None


# ===========================================================================
# 2. TEMPORALIDAD
# ===========================================================================
def test_secuencia_ordena_por_calle_y_por_accion():
    h = mano(preflop=[('UTG', 'b', 3.0), ('BTN', 'c', 3.0)],
             flop=[('BTN', 'b', 10.0)])
    s = secuencia(h)
    assert s[0] == ((0, 0), 'UTG', 'b')
    assert s[-1] == ((1, 0), 'BTN', 'b')
    assert [c for c, _, _ in s] == sorted(c for c, _, _ in s)


def test_allin_posterior_no_bloquea_la_decision_anterior():
    """revision_2: un rival puede actuar ANTES de que otro se commitmente.

    El hero checkea en el indice 0. BTN se commitmenta en el indice 2. En
    el instante del check, BTN todavia puede responder: la regla por calle
    lo bloqueaba desde el principio del flop.
    """
    h = mano(preflop=[('UTG', 'f', 0.0), ('BTN', 'b', 3.0), ('SB', 'f', 0.0),
                      ('BB', 'f', 0.0)],
             flop=[('UTG', 'x', 0.0), ('MP', 'b', 8.0), ('BTN', 'r', 38.2)],
             allin=[ID_DE_POS['BTN']])
    assert no_puede_actuar(h, 'flop') == {'BTN'}, 'por calle: bloqueado'
    assert no_puede_actuar_en_instante(h, 'flop', 0) == set(), \
        'por instante: aun puede responder'
    # BTN entra porque TODAVIA no se ha commitmentado en este
    # instante: es justo lo que la regla por calle se pierde.
    assert puede_responder(h, 'flop', 0) == {'MP', 'CO', 'BTN'}

def test_allin_anterior_si_bloquea():
    """El caso inverso: si el commitmentio precede a la decision, bloquea."""
    h = mano(preflop=[('UTG', 'f', 0.0), ('BTN', 'b', 3.0), ('SB', 'f', 0.0),
                      ('BB', 'f', 0.0)],
             flop=[('BTN', 'r', 38.2), ('MP', 'c', 38.2), ('UTG', 'x', 0.0)],
             allin=[ID_DE_POS['BTN']])
    assert no_puede_actuar_en_instante(h, 'flop', 2) == {'BTN'}


def test_fold_posterior_no_saca_al_hero_de_su_decision():
    """El hero apuesta, ve una resubida y foltea: SI es una decision suya.

    Con un corte por calle, `folds_hasta` ya lo habia excluido y el punto
    desaparecia del numerador.
    """
    h = mano(preflop=[('UTG', 'b', 3.0), ('BTN', 'c', 3.0), ('SB', 'f', 0.0),
                      ('BB', 'f', 0.0)],
             flop=[('UTG', 'b', 10.0), ('MP', 'r', 30.0), ('UTG', 'f', 0.0)],
             allin=[])
    assert instante_decision(h, 'flop') == 0
    r = clasificar_decision(h, 'flop')
    assert r['clase'] in (HU, MULTIWAY)
    assert r['instante'] == 0


def test_decision_de_fold_no_entra_en_hu_ni_multiway():
    """Folding es decision, pero no consulta equity: se cuenta aparte."""
    h = mano(preflop=[('BTN', 'b', 3.0), ('SB', 'f', 0.0), ('BB', 'f', 0.0)],
             flop=[('MP', 'b', 10.0), ('UTG', 'f', 0.0)], allin=[])
    r = clasificar_decision(h, 'flop')
    assert r['instante'] == 1
    assert acciones(h, 'flop')[1]['action'] == 'f'


def test_calle_sin_accion_del_hero_no_es_decision():
    h = mano(preflop=[('BTN', 'b', 3.0), ('SB', 'f', 0.0), ('BB', 'f', 0.0)],
             flop=[('MP', 'x', 0.0), ('CO', 'x', 0.0)], allin=[])
    assert instante_decision(h, 'flop') is None
    assert clasificar_decision(h, 'flop')['clase'] == SIN_DECISION


def test_sin_cards_no_hay_hero():
    h = mano(preflop=[('BTN', 'b', 3.0)], allin=[])
    h['players'][0]['cards'] = ''
    assert hero_pos(h) is None
    assert clasificar_decision(h, 'flop')['clase'] == SIN_DECISION


# ===========================================================================
# 3. NO HAY DOS IMPLEMENTACIONES
# ===========================================================================
def test_no_hay_dos_implementaciones():
    """`no_puede_actuar` se define UNA vez, en `motor/multiway.py`.

    revision_1 Tarea 3: la regla tiene que vivir en `motor/`, no en un
    script de auditoria. Si queda una copia en `tools/`, el motor acaba
    usando una y el inventario la otra, y divergen sin que nada falle.
    """
    definiciones = []
    for sub in ('motor', 'tools', 'recorder'):
        d = os.path.join(ROOT, sub)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.py'):
                continue
            ruta = os.path.join(d, fn)
            try:
                tree = ast.parse(io.open(ruta, encoding='utf-8').read())
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if isinstance(n, ast.FunctionDef) and n.name in (
                        'no_puede_actuar', 'no_puede_actuar_en_instante'):
                    definiciones.append('%s/%s:%d' % (sub, fn, n.lineno))
    assert definiciones == ['motor/multiway.py:%d' % n
                            for n in _lineas_de(multiway, 'no_puede_actuar',
                                                'no_puede_actuar_en_instante')], \
        'la regla esta definida en mas de un sitio: %s' % definiciones


def _lineas_de(modulo, *nombres):
    src = io.open(modulo.__file__, encoding='utf-8').read().split('\n')
    return [i for i, l in enumerate(src, 1)
            if any(l.strip().startswith('def %s(' % n) for n in nombres)]


def test_el_auditor_importa_la_regla_no_la_copia():
    """El script de auditoria tiene que IMPORTAR de motor/multiway."""
    src = io.open(os.path.join(ROOT, 'tools',
                               'auditar_solapamiento_multiway.py'),
                  encoding='utf-8').read()
    tree = ast.parse(src)
    importa = any(
        isinstance(n, ast.ImportFrom) and n.module == 'motor.multiway'
        for n in ast.walk(tree))
    assert importa, 'el auditor ya no importa de motor.multiway'
    # y no vuelve a definirla
    assert not any(isinstance(n, ast.FunctionDef)
                   and n.name.startswith('no_puede_actuar')
                   for n in ast.walk(tree))