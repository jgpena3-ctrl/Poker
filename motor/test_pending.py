# -*- coding: utf-8 -*-
"""F6.1.b — contrato canónico de `pending`.

`pending` = siguen en la mano Y no han actuado en esta calle Y no son el hero.

Lo que estos tests protegen no es tanto el resultado como la HONESTIDAD del
resultado: antes, `classify_villains(acts, hero)` sin candidatos devolvía
`pending == []`, que se lee como "nadie está pendiente" cuando en realidad era
"nadie dijo quién está pendiente". Son cosas distintas.
"""
import pytest

from motor.hierarchy import classify_villains, pending_positions


def _acts(*pares):
    return [{'pos': p, 'action': a, 'amount': 1.0} for p, a in pares]


# --------------------------------------------------------------- el contrato

def test_activo_sin_acted_es_pending():
    acts = _acts(('MP', 'b'))
    assert pending_positions(acts, 'BTN', ['CO', 'SB']) == ['CO', 'SB']


def test_quien_ya_actuo_no_es_pending():
    acts = _acts(('MP', 'b'), ('CO', 'c'))
    assert pending_positions(acts, 'BTN', ['MP', 'CO', 'SB']) == ['SB']


def test_el_hero_nunca_es_pending():
    """El hero está activo y no ha-acting: aun así no es pendiente.

    Sin la condición 3 entraría como amenaza, que es el error que el
    comentario de `_jerarquia` documenta (el hero acababa en su propia lista).
    """
    acts = _acts(('MP', 'b'))
    # BTN (hero) no ha actuado en esta calle; CO tampoco
    assert pending_positions(acts, 'BTN', ['BTN', 'CO']) == ['CO']


def test_quien_no_esta_en_la_mano_no_es_pending():
    """El criterio que hace que `activos` sea obligatorio.

    Un jugador que NO actúa en la calle puede estar porque se fue, no porque
    tenga una decisión pendiente. Sin `activos` no hay forma de distinguirlo.
    """
    acts = _acts(('MP', 'b'))
    # SB no está en `activos` (se fue /|All-in antes de actuar)
    assert pending_positions(acts, 'BTN', ['MP', 'CO']) == ['CO']


def test_sin_duplicados_y_en_el_orden_de_activos():
    acts = _acts(('MP', 'b'))
    assert pending_positions(acts, 'BTN', ['SB', 'CO', 'SB', 'CO']) == \
        ['SB', 'CO']


def test_sin_actos_todo_activo_no_hero_es_pending():
    assert pending_positions([], 'BTN', ['UTG', 'MP', 'BTN']) == ['UTG', 'MP']


def test_entradas_invalidas_se_ignoran():
    acts = _acts(('MP', 'b'))
    assert pending_positions(acts, 'BTN', [None, '', 'SB']) == ['SB']


def test_acciones_sin_pos_no_rompen():
    acts = [{'action': 'b', 'amount': 1.0}, {'pos': 'MP', 'action': 'b'}]
    assert pending_positions(acts, 'BTN', ['MP', 'SB']) == ['SB']


# ------------------------------------------- "no se sabe" != "no hay ninguno"

def test_activos_none_devuelve_lista_vacia_pero_no_lo_declara_cierto():
    """El punto central del cambio.

    `pending == []` aquí NO significa "no hay pendientes". Significa "no hay
    información". Por eso el contrato lleva `pending_known` al lado: sin él, un
    vacío se confundiría con un dato.
    """
    acts = _acts(('MP', 'b'))
    jer = classify_villains(acts, 'BTN', None)
    assert jer['pending'] == []
    assert jer['pending_known'] is False, 'un vacío debe declararse INCERTO'


def test_activos_conocido_si_lo_declara():
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ['CO'])
    assert jer['pending'] == ['CO']
    assert jer['pending_known'] is True


def test_activos_vacio_si_es_verdad_no_incierto():
    """Distinguir "nadie está en la mesa" de "no lo sé" también cuenta."""
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', [])
    assert jer['pending'] == []
    assert jer['pending_known'] is True, 'con `activos=[]` sí se sabe: es []'


# ------------------------------------------------------------- el fallo ruidoso

def test_omitir_activos_es_error_no_un_vacio():
    """El contrato falla ruidoso, no devuelve un resultado plausible y falso."""
    with pytest.raises(TypeError):
        classify_villains(_acts(('MP', 'b')), 'BTN')


# ------------------------------------------------- equivalencia de comportamiento

def test_el_resultado_no_cambio_para_quien_ya_filtraba():
    """Quien pasaba candidatos pre-filtrados obtiene lo mismo.

    El llamador anterior hacía `[p for p in activos if p and p != hp and p not
    in acted]` y lo pasaba. La función canónica aplica esos MISMOS tres filtros,
    así que el resultado coincide. Si algún día cambia el contrato, esto falla.
    """
    acts = _acts(('MP', 'b'), ('BTN', 'c'), ('CO', 'x'))
    activos = ['UTG', 'MP', 'CO', 'SB']
    hp = 'BTN'

    antes = [p for p in activos if p and p != hp and p not in
             {a['pos'] for a in acts}]
    despues = pending_positions(acts, hp, activos)
    assert despues == antes == ['UTG', 'SB']


def test_la_clave_lista_no_es_una_etiqueta_de_rol():
    """`pending` es una lista de posiciones, no una etiqueta.

    Regresión contra el vocabulario de roles eliminado (`PENDING = 'pending'`),
    que sugería un valor y no un conjunto.
    """
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ['SB'])
    assert jer['pending'] == ['SB']
    assert isinstance(jer['pending'], list)
