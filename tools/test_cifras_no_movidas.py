# -*- coding: utf-8 -*-
"""LAS CIFRAS PUBLICADAS, Y QUE H1 Y H2 NO LAS HAYAN MOVIDO.

Y el motivo de este fichero: H1 y H2 son correcciones de DEFECTOS del
contrato de lectura —una tabla dañada es una tabla ausente, y la forma de la
matriz se comprueba—. Y una correccion de defecto **no debe mover ninguna
cifra publicada**, porque si las mueve, eso ya no es una correccion: es una
recalibracion, y las recalibraciones van DESPUES de la adopcion.

Y la forma de comprobarlo, que es la del proyecto: **el antes y el despues,
en el mismo fichero, con el dato real**. Y no es un «antes» de memoria: es
la implementacion anterior, escrita aqui como referencia, y las dos se
ejecutan sobre el fichero real y tienen que dar lo mismo.

Y si alguna vez dejaran de coincidir, el test falla —que es lo que se quiere—,
y entonces lo que se declara no es un arreglo: es una recalibracion, con
dueno y condicion de activacion.
"""
import io
import json
import os
import sys
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import player_ranges                  # noqa: E402
from motor.profile import _COMBO, load_base_rates   # noqa: E402

MATRICES = os.path.join(ROOT, 'data', 'preflop_matrices.json')


def _version_anterior_de_las_tasas(matrices_path):
    """`load_base_rates` ANTES de H1: se come las filas malas y sigue.

    Y la referencia esta aqui, y no en un commit, porque un commit se
    reescribe y una referencia en el test no. Y el motivo de que sea la
    version ANTERIOR y no una idealized: el objetivo es comprobar que la
    correccion no mueve nada, y eso solo se comprueba contra lo que habia.
    """
    if not matrices_path or not os.path.exists(matrices_path):
        return {}
    tables = json.load(open(matrices_path, encoding='utf-8')).get('tables', {})
    rates = {}
    for name, t in tables.items():
        matrix = t.get('matrix')
        if not isinstance(matrix, list) or len(matrix) != 13:
            continue
        total_w = total_p = 0.0
        for i, row in enumerate(matrix):
            if not isinstance(row, list) or len(row) != 13:
                continue
            for j, freq in enumerate(row):
                try:
                    f = float(freq)
                except (TypeError, ValueError):
                    continue
                w = _COMBO.get((i, j), 1)
                total_w += w
                total_p += f * w
        rates[name] = total_p / total_w if total_w else 0.0
    return rates


def test_h1_no_mueve_las_tasas_publicadas():
    """Y que las 117 tasas base sean EXACTAMENTE las de antes.

    Y el numero importa: son las 117 tablas del fichero real, y el fichero
    real esta entero —MEDIDO, 0 tablas dañadas—, de modo que el caso que H1
    cambia —una tabla dañada— no se da, y por eso las tasas no se mueven.
    """
    antes = _version_anterior_de_las_tasas(MATRICES)
    despues = load_base_rates(MATRICES)
    assert len(despues) == 117, len(despues)
    assert despues == antes, (
        'H1 ha movido las tasas base. Y las diferencias son: %r'
        % {k: (antes.get(k), despues.get(k))
           for k in set(antes) | set(despues)
           if antes.get(k) != despues.get(k)})


def test_h2_no_mueve_los_priors():
    """Y que el prior de cada tabla siga siendo su matriz.

    Y el motivo de que se compare con la matriz cruda y no con el prior
    anterior: el prior anterior ERA la matriz cruda, sin mirar la forma. Y
    en el fichero real todas las matrices son de 13x13 —MEDIDO—, de modo que
    las dos dan lo mismo, y la comprobacion de la forma no ha movido nada.
    """
    with io.open(MATRICES, encoding='utf-8') as f:
        tablas = json.load(f)['tables']
    acciones = {v: k for k, v in player_ranges.CAT_TABLE.items()}
    m = player_ranges.ProfileRangeModel()
    comprobadas = 0
    with warnings.catch_warnings():
        # Y los avisos se ignoran aqui: algunos priors avisan de que no hay
        # tabla exacta, y eso es lo esperado, y no es lo que este test mide.
        warnings.simplefilter('ignore')
        for nombre, t in tablas.items():
            # Y el nombre se descompone, porque `_prior_grid` elige por
            # posicion y por PAR de posiciones: y sin el rival, una tabla
            # `3B_BB_vs_SB` no es la que se elige, sino el prior plano.
            #
            # Y el motivo de que esto sea un detalle y no un problema: es
            # exactamente la REGLA DE ELECCION del lector, y la regla dice
            # «la exacta por posicion, y si no, la de la pareja». Y el test
            # tiene que pasar por la misma regla.
            partes = nombre.split('_')
            prefijo, pos = partes[0], partes[1]
            vs = partes[3] if len(partes) > 3 and partes[2] == 'vs' else ''
            accion = acciones.get(prefijo)
            if accion is None:
                continue
            got = m._prior_grid(accion, pos, vs)
            esperado = np.asarray(t['matrix'], dtype=np.float32)
            assert np.allclose(got, esperado), (
                'el prior de %r ya no es su matriz: H2 ha movido algo'
                % nombre)
            comprobadas += 1
    # Y el numero: MEDIDO, 41 de las 117 tablas son alcanzables por
    # `_prior_grid`, que es el que tiene una REGLA DE ELECCION; las otras 76
    # son de prefijos que el mapa de acciones no cubre, y no se que pueden
    # elegir. Y el numero se fija para que se note si el mapa cambia.
    assert comprobadas == 41, (
        'se han comprobado %d tablas, y eran 41: si el mapa de acciones ha '
        'cambiado, hay que revisar este test' % comprobadas)
