# -*- coding: utf-8 -*-
"""La auditoría de `rules.py`: el camino de decisión, con estados sintéticos.

Y son estados **SINTÉTICOS y pequeños**, y no la base, porque la pregunta es
sobre el MOTOR: qué rutas devuelven una acción sin cumplir su contrato, y
qué estados inválidos degradan en silencio.

Y los hallazgos, con su medición, están en `DOCS/AUDITORIA_RULES.md`.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import rules                      # noqa: E402
from motor.decision import EvTable           # noqa: E402

BOARD = ['As', 'Kd', '7c']
BASE = dict(street='flop', hero_initiator=False, to_call=0.0,
            board_codes=BOARD, pot=20.0, stack=100.0, n_players=2)


class _Plan(object):
    """Un plan minimo, con lo que `select_best` mira."""

    def __init__(self, candidates):
        self.candidates = candidates


# --- lo que el contrato EXIGE que se lance ---------------------------------

def test_la_calle_invalida_se_lanza():
    """C2 lo declara, y el codigo lo cumple."""
    with pytest.raises(ValueError):
        rules.plan(**dict(BASE, street='preflop'))


def test_el_to_call_negativo_se_lanza():
    """Y el codigo lo comprueba, aunque el contrato no lo mencione."""
    with pytest.raises(ValueError):
        rules.plan(**dict(BASE, to_call=-1.0))


def test_el_facing_raise_sin_to_call_se_lanza():
    """Y este tambien: un facing raise con to_call 0 es una situacion imposible."""
    with pytest.raises(ValueError):
        rules.plan(**dict(BASE, facing_raise=True))


# --- el suelo del fold, y la etiqueta que puede no estar en el plan ---------

def test_el_fold_es_el_suelo_y_puede_no_estar_en_el_plan():
    """Que el fold se devuelva aunque el plan no lo ofrezca.

    Y esto NO es un defecto: es lo que dice el contrato FIRMADO
    (`CONTRATO_C4.md` §2.1 y §2.4: el fold es el baseline, y «fold se
    considera siempre primero»).

    Y lo que el test fija es la COMPORTACION, para que no se mueva en
    silencio. Y de paso deja a la vista la imprecisión del RESUMEN
    (`CONTRATOS_RULES.md` §C4), que dice que «la etiqueta devuelta está
    siempre en rp.candidates». Ver `DOCS/AUDITORIA_RULES.md`.
    """
    rp = _Plan(('check',))
    etiqueta, valor = rules.select_best(EvTable({'fold': 5.0, 'check': 1.0}), rp)
    assert (etiqueta, valor) == ('fold', 5.0), (etiqueta, valor)
    assert etiqueta not in rp.candidates, (
        'este caso es el que hace que el resumen del contrato y el contrato '
        'firmado no digan lo mismo')

    # Y al reves: si el check vale mas, gana el check. Que no sea «siempre
    # fold», sino «fold si no hay nada mejor».
    etiqueta, valor = rules.select_best(EvTable({'fold': 0.1, 'check': 1.0}), rp)
    assert (etiqueta, valor) == ('check', 1.0), (etiqueta, valor)


def test_sin_plan_se_consideran_todas_las_claves():
    """Y sin plan, C4 §2.5: todas las claves de la tabla."""
    etiqueta, valor = rules.select_best(EvTable({'check': 2.0, 'bet_50': 1.0}))
    assert (etiqueta, valor) == ('check', 2.0), (etiqueta, valor)


# --- los estados invalidos que degradan en SILENCIO -----------------------

# Las CINCO precondiciones que `plan()` no comprueba, y el estado invalido
# que representa cada una. Y el estado invalido va en la propia tabla, para
# que se lea con la fila y no haya que ir a buscarlo.
#
# Y el motivo de que esten aqui, y no en el documento: una comprobacion que
# solo esta escrita en un documento es una promesa. Y esta comprueba que cada
# una produce un plan, que es lo que hace que el hueco sea VISIBLE.
LAS_CINCO = (
    ({'board_codes': ['As', 'Kd']},
     'un board incompleto, de modo que la TEXTURA es desconocida'),
    ({'pot': -1.0},
     'un bote NEGATIVO, que no puede existir'),
    ({'stack': -1.0},
     'un stack NEGATIVO, que no puede existir'),
    ({'stack': 0.0},
     'un stack de CERO, sin fichas para actuar'),
    ({'n_players': 0},
     'CERO jugadores en la mesa, que no es una mesa'),
)


@pytest.mark.parametrize('cambio,estado', LAS_CINCO)
def test_los_estados_invalidos_degradan_en_silencio(cambio, estado):
    """Que el estado invalido NO se lance, y que quede DECLARADO.

    Y aqui esta el hallazgo de la auditoria: `plan()` comprueba dos
    precondiciones (`to_call` negativo y `facing_raise` sin `to_call`) y deja
    pasar cinco mas, **en silencio**. Y el contrato C2 declara «board
    completo» como precondicion, y un board de dos cartas no lanza: sale un
    plan con la textura a `None`, que en la nota se ve como un `?`.

    Y el test fija la COMPORTACION, que es lo que hace que el hueco sea
    visible: si manana `plan()` empieza a lanzar, este test falla y obliga a
    revisar el contrato. Ver `DOCS/AUDITORIA_RULES.md`.
    """
    rp = rules.plan(**dict(BASE, **cambio))
    assert rp.candidates, (
        'el plan tiene que tener candidatas, y el estado invalido que '
        'representa esta fila es: %s. Y el hecho de que salga un plan es el '
        'defecto.' % (estado,))
    assert rp.spot != 'unknown', 'y no puede ser un plan sin regla'


def test_el_board_incompleto_se_ve_en_la_nota():
    """Y el unico rastro del board incompleto es un `?` en la nota.

    Y eso es un rastro DEBIL: es una nota, no un error, y un `?` en un texto
    puede pasar inadvertido. Es lo que hace que el hueco sea un hueco y no un
    fallo.
    """
    rp = rules.plan(**dict(BASE, board_codes=['As', 'Kd']))
    assert '?' in rp.note, (
        'sin board completo la textura es None, y la nota deberia decirlo: %r'
        % (rp.note,))
