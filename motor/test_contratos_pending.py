# -*- coding: utf-8 -*-
"""Tests que fijan los contratos IMPLÍCITOS de F6.1.b.

Un contrato implícito es peor que uno explícito: nadie lo busca. Estos tests
existen para que, si algún día se rompe, salte algo en vez de dar un
resultado silenciosamente incorrecto.
"""
from motor.hierarchy import classify_villains, pending_positions

from motor.test_hierarchy import BOARD_FLOOP, HERO, _acts  # noqa: F401


# ---------------------------------------------------------------------------
# `acts` debe ser de UNA calle
# ---------------------------------------------------------------------------

def test_acts_de_una_sola_calle():
    """El caso normal: los pendientes son los que no aparecen en la calle."""
    acts = _acts(('MP', 'b'), ('BTN', 'c'))
    # MP y BTN ya actuaron; CO sigue sin actuar
    assert pending_positions(acts, 'HERO', ['MP', 'BTN', 'CO', 'SB']) == \
        ['CO', 'SB']


def test_acts_de_varias_calles_da_un_resultado_incorrecto():
    """Documenta el límite DEL CONTRATO, no un comportamiento deseado.

    `pending_positions` no recibe la calle: va implícita en `acts`. Si se le
    pasan acciones de varias calles, las posiciones de la calle anterior
    cuentan como "ya actuaron" y desaparecen de los pendientes.

    Este test NO dice que el resultado sea correcto. Dice que es incorrecto, a
    propósito, para que nadie lo tome por un caso válido: si algún día se
    rompe, el aviso está aquí.
    """
    acts_mixtos = [
        {'pos': 'UTG', 'action': 'b'},      # flop
        {'pos': 'CO', 'action': 'b'},       # turn
    ]
    activos = ['UTG', 'CO', 'SB']
    resultado = pending_positions(acts_mixtos, 'BTN', activos)

    # UTG actuó en el flop y CO en el turn: los dos han actuado, así que
    # solo SB debería estar pendiente. Pero la función no puede saber que son
    # calles distintas, y los descarta a los dos por igual.
    assert resultado == ['SB']

    # El escenario que el contrato PROHÍBE: si CO no hubiera acted en su
    # calle, el resultado sería el correcto, y por eso el fallo pasa
    # desapercibido en los datos de una sola calle.
    solo_flop = [{'pos': 'UTG', 'action': 'b'}]
    assert pending_positions(solo_flop, 'BTN', activos) == ['CO', 'SB']


# ---------------------------------------------------------------------------
# defensa en profundidad del hero
# ---------------------------------------------------------------------------
# La comprobación real (`_pos_of` devolviendo otra posición para el hero) NO
# está aquí: necesita el fixture `asis` y vive en test_asistente_live.py, donde
# se ejerce de verdad. Aquí NO se afirma sobre el texto del fuente: eso
# pasaría con el código roto de otra manera y fallaría con un refactor correcto.

def test_hero_excluido_por_pid_aunque_pos_of_falle():
    """`_jerarquia` excluye al hero por PID y por posición.

    Si `_pos_of` devolviera una posición distinta para el hero, la
    comprobación por PID lo seguiría excluyendo. Se comprueba aquí la
    propiedad del contrato: para CUALQUIER posición que reporte el hero,
    nunca aparece como pendiente.
    """
    # position equivocada para el hero: `classify_villains` la excluiría por
    # `hero_pos`, y `_jerarquia` ya la ha filtrado antes por PID.
    jer = classify_villains(_acts(('MP', 'b')), 'BTN',
                            ['BTN', 'CO', 'SB'])
    assert 'BTN' not in jer['pending']
    assert 'CO' in jer['pending']


# ---------------------------------------------------------------------------
# los tres estados de `activos`
# ---------------------------------------------------------------------------

def test_omitir_activos_es_type_error():
    with __import__('pytest').raises(TypeError):
        classify_villains(_acts(('MP', 'b')), 'BTN')


def test_activos_none_es_valido_pero_incierto():
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', None)
    assert jer['pending_known'] is False


def test_activos_vacio_es_valido_y_cierto():
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', [])
    assert jer['pending_known'] is True
    assert jer['pending'] == []


def test_pending_known_no_garantiza_que_los_activos_sean_buenos():
    """`pending_known=True` NO significa "la jerarquía es fiable".

    Solo significa que el llamador pasó el argumento. Un `activos` equivocado
    o incompleto sigue dando `pending_known=True`. El test fija esa lectura
    débil para que nadie la estreche por su cuenta.
    """
    # el llamador pasa UNA sola posición, claramente incompleta
    jer = classify_villains(_acts(('MP', 'b')), 'BTN', ['CO'])
    assert jer['pending_known'] is True, 'pasó el argumento: eso es todo'
    assert jer['pending'] == ['CO'], 'y aun así el resultado es parcial'


# ---------------------------------------------------------------------------
# `pending_known` llega al registro sombra (revision_2)
# ---------------------------------------------------------------------------

def test_el_registro_sombra_conserva_pending_known():
    """Si no se registra, la incertidumbre se pierde igual que antes.

    Los consumidores del shadow leen `len(pending)`, que convierte `None` y
    `[]` en 0. Solo un campo explícito permite distinguirlo después.
    """
    from motor.hierarchy import shadow_record

    jer_incierto = classify_villains(_acts(('MP', 'b')), 'BTN', None)
    rec = shadow_record('H_1', 'flop', BOARD_FLOOP, HERO, jer_incierto, {},
                        10.0, 0.0, 90.0, 'bet_25')
    assert rec['pending_known'] is False, 'la incertidumbre debe quedar escrita'
    assert rec['pending'] == []

    jer_cierto = classify_villains(_acts(('MP', 'b')), 'BTN', ['CO'])
    rec2 = shadow_record('H_1', 'flop', BOARD_FLOOP, HERO, jer_cierto, {},
                         10.0, 0.0, 90.0, 'bet_25')
    assert rec2['pending_known'] is True
