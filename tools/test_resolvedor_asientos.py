# -*- coding: utf-8 -*-
"""Los scripts de `tools/` no vuelven a deducir la butaca por su cuenta."""
import ast
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import auditar_muestra_lsec as lsec                      # noqa: E402
import auditar_rango as rango                            # noqa: E402
import calibrar as cal                                   # noqa: E402
import equity_de_mano as equity                          # noqa: E402
from motor.multiway import (                             # noqa: E402
    PLAYER_IDS, ContratoAsientosInvalido, posicion_de_id,
)

POSICIONES = ('UTG', 'MP', 'CO', 'BTN', 'SB', 'BB')
RESOLVEDORES = (rango.pos_de_pid, cal.id_a_pos, lsec.id_a_pos,
                equity.id_a_pos)


def mano(n_players=6):
    return {'players': [{'pos': POSICIONES[i]}
                        for i in range(n_players)]}


@pytest.mark.parametrize('resolver', RESOLVEDORES)
def test_resuelven_las_seis_butacas(resolver):
    h = mano()
    for pos, pid in zip(POSICIONES, PLAYER_IDS):
        assert resolver(h, pid) == pos


@pytest.mark.parametrize('resolver', RESOLVEDORES)
def test_id_desconocido_es_none(resolver):
    assert resolver(mano(), 'p9') is None


@pytest.mark.parametrize('resolver', RESOLVEDORES)
def test_contrato_roto_se_rechaza(resolver):
    with pytest.raises(ContratoAsientosInvalido):
        resolver(mano(n_players=4), 'hero')


def test_no_queda_una_tabla_de_asientos_en_tools():
    for nombre in ('auditar_rango.py', 'calibrar.py',
                   'auditar_muestra_lsec.py', 'equity_de_mano.py'):
        ruta = os.path.join(ROOT, 'tools', nombre)
        arbol = ast.parse(io.open(ruta, encoding='utf-8').read())
        usos = [n for n in ast.walk(arbol)
                if isinstance(n, ast.Attribute) and n.attr == 'index'
                and isinstance(n.value, ast.Name)
                and n.value.id in ('PID', 'PLAYER_IDS')]
        assert not usos, '%s vuelve a mapear el id por indice' % nombre
