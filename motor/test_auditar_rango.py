# -*- coding: utf-8 -*-
"""Los detectores de `auditar_rango.py` sobre casos CONOCIDOS.

review revision_2 §3: el detector de subidas implementaba una comprobación
distinta de la que su docstring prometia —comparaba contra la ciega nominal
en vez de contra la apuesta viva— y sin una prueba de casoado nadie puede
distinguir "detecta menos de lo que dice" de "detecta menos porque hay menos".

Aqui hay una mano minima por caso, con la respuesta ESPERADA escrita al lado.
Si el detector cambia de comportamiento, estos tests dicen en que caso, no
"solo hay otro numero".
"""
import copy

import pytest

from tools import auditar_rango as A

# --------------------------------------------------------------------------
# Constructor de manos minimas
# --------------------------------------------------------------------------
def mano(preflop=(), flop=(), turn=(), river=(), activos=('UTG', 'BB'),
         winner=None, showdown=None, players=None, pot=10.0, allin=None):
    jugadores = []
    for pos in activos:
        jugadores.append({'active': True, 'pos': pos, 'name': pos,
                         'stack': 100.0, 'cards': ''})
    if players:
        jugadores = players
    h = {
        'hand_id': 'H_TEST', 'date': '2026-01-01T00:00:00',
        'btn_idx': 0, 'btn_player': activos[0],
        'players': jugadores,
        'streets': {
            'preflop': {'actions': [dict(a) for a in preflop], 'board': []},
            'flop': {'actions': [dict(a) for a in flop], 'board': []},
            'turn': {'actions': [dict(a) for a in turn], 'board': []},
            'river': {'actions': [dict(a) for a in river], 'board': []},
        },
        'final_pot': pot, 'showdown': showdown or {}, 'winner': winner or [],
    }
    if allin is not None:
        h['allin'] = allin
    return h


def acc(pos, accion, amount=0.0):
    return {'pos': pos, 'action': accion, 'amount': amount}


# --------------------------------------------------------------------------
# IMPORTE_SUBIDA — los cuatro casos que pedia revision_2
# --------------------------------------------------------------------------

def test_subida_que_supera_la_ciega_pero_no_la_apuesta_viva():
    """revision_2 §3, caso 1.

    Hay una subida viva a 6.0 y despues alguien "subE" a 4.0. Supera la ciega
    (1.0), asi que la version anterior —que comparaba contra la ciega— no lo
    detectaba. Supera la ciega pero no la apuesta viva, que es lo que importa.
    """
    h = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 6.0),
                      acc('BB', 'r', 4.0)])
    fallos = A.importe_subida(h)
    assert len(fallos) == 1, fallos
    assert 'no supera la apuesta viva (6.0)' in fallos[0], fallos


def test_subida_valida_por_encima_de_la_apuesta_viva():
    """revision_2 §3, caso 2. No hay que señalar lo que es correcto."""
    h = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 6.0),
                      acc('BB', 'r', 12.0)])
    assert A.importe_subida(h) == []


def test_subida_a_la_apuesta_viva_exacta_tambien_falla():
    """Igual que la anterior no supera: subir "a" lo mismo no es subir."""
    h = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 6.0),
                      acc('BB', 'r', 6.0)])
    assert len(A.importe_subida(h)) == 1


def test_llamada_no_es_subida():
    """revision_2 §3, caso 3. Una llamada que no iguala el importe NO es una
    subida invalida: el detector no tiene que senalarla."""
    # el SB llama 3.0 a una apuesta viva de 6.0. Faltarian 3.0. Eso es un
    # defecto DISTINTO, y no lo declara esta clase.
    h = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 6.0),
                      acc('SB', 'c', 3.0)])
    assert A.importe_subida(h) == []


def test_cegas_seguidas_de_la_primera_accion_voluntaria():
    """revision_2 §3, caso 4.

    El suelo del preflop es la ciega grande SIEMPRE. Una mano sin la ciega del
    BB grabada —que es la firma de CM-004— no puede quedarse sin suelo, o
    cualquier subida pasaria el filtro.
    """
    sin_ciega = mano(preflop=[acc('UTG', 'r', 1.0)])
    assert len(A.importe_subida(sin_ciega)) == 1, (
        'una subida a la ciega sin ciega grabada tiene que、 seguir el suelo '
        'de 1.0')
    con_ciega = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 1.0)])
    assert len(A.importe_subida(con_ciega)) == 1
    valida = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 2.5)])
    assert A.importe_subida(valida) == []


def test_el_suelo_se_reinicia_en_cada_calle():
    """Postflop: `amount` es el total de esa calle, y el bote no arrastra."""
    h = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 6.0),
                      acc('BB', 'c', 6.0)],
             flop=[acc('BB', 'b', 2.0), acc('UTG', 'c', 2.0)])
    assert A.importe_subida(h) == []


# --------------------------------------------------------------------------
# SIN_RESPUESTA_BB — las DOS metricas, separadas
# --------------------------------------------------------------------------

def test_el_patron_historico_no_debe_contarse_como_ausencia():
    """review revision_2 §2, y es el fallo mas importante de este bloque.

    La funcion devolvia un texto no vacio TAMBIEN cuando el BB habia
    respondido, y `auditar()` registra cualquier retorno verdadero. O sea: el
    detector registraba como hallazgo casos en los que su propio mensaje decia
    "no falta nada". Que `--validar` reprodujera 652 confirmaba que
    reproducia un contador, no que identificara ausencias.

    Ahora hay DOS funciones con dos nombres que no se pueden confundir, y esta
    prueba fija la diferencia:
    """
    respondio = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 4.0),
                              acc('BB', 'f', 0.0)])
    # el PATRON se cumple: el preflop cierra con una subida de un no-BB
    assert 'el BB responde' in A.patron_bb_sin_respuesta(respondio)
    # pero la AUSENCIA no se cumple: el BB contesto
    assert A.ausencia_respuesta_bb(respondio) is None
    # y las dos metricas existen con nombres distintos
    assert 'PATRON_BB_SIN_RESPUESTA' in [c for c, _e, _f
                                         in A.METRICAS_NO_FALLA]
    assert 'AUSENCIA_RESPUESTA_BB' in [c for c, _e, _f, _n in A.CLASES]


def test_el_bloque_de_ausencias_no_incluye_a_quien_respondio():
    h = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 4.0),
                      acc('BB', 'f', 0.0)])
    h2 = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 4.0),
                       acc('BB', 'c', 4.0)])
    for x in (h, h2):
        assert A.ausencia_respuesta_bb(x) is None, (
            'el BB respondio (%s): no es una ausencia' % x)
    # el que no responde, si
    y = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 4.0)])
    assert A.ausencia_respuesta_bb(y), 'aqui el BB no responde'


def test_el_bloque_de_ausencias_excluye_a_quien_ya_foldeo_antes():
    """Si el BB ya esta folded antes de la subida, esta fuera de la mano."""
    h = mano(preflop=[acc('BB', 'b', 1.0), acc('UTG', 'r', 2.5),
                      acc('BB', 'f', 0.0), acc('UTG', 'r', 7.0)])
    assert A.ausencia_respuesta_bb(h) is None, (
        'el BB ya habia foldeado: no le falta nada')


def test_los_bloques_dan_cifras_distintas():
    """El patron historico y las ausencias tienen que ser numeros distintos.

    Si coincidieran, uno de los dos esta mal. hoy: 652 y 23 en la base
    completa.
    """
    manos = A.cargar_commit(A.COMMIT_ANTES)
    patron = sum(1 for h in manos if A.sin_respuesta_bb(h))
    ausencias = sum(1 for h in manos if A.ausencia_respuesta_bb(h))
    assert patron == 652, patron
    assert ausencias == 23, ausencias
    assert ausencias < patron


# --------------------------------------------------------------------------
# ACCION_DESPUES_FOLD
# --------------------------------------------------------------------------

def test_actuar_despues_de_haber_foldeado():
    h = mano(preflop=[acc('UTG', 'f', 0.0), acc('MP', 'c', 1.0),
                      acc('UTG', 'x', 0.0)])
    fallos = A.accion_despues_fold(h)
    assert len(fallos) == 1 and 'UTG' in fallos[0], fallos


def test_foldear_y_no_volver_a_actuar_no_es_fallo():
    h = mano(preflop=[acc('UTG', 'f', 0.0), acc('MP', 'c', 1.0)])
    assert A.accion_despues_fold(h) == []


# --------------------------------------------------------------------------
# ACCION_FANTASMA
# --------------------------------------------------------------------------

def test_accion_de_una_posicion_que_no_esta_en_la_mesa():
    h = mano(preflop=[acc('CO', 'f', 0.0)], activos=('UTG', 'BB'))
    assert A.accion_fantasma(h) == ['CO']


def test_accion_de_una_posicion_que_si_esta_no_es_fantasma():
    h = mano(preflop=[acc('BB', 'b', 1.0)], activos=('UTG', 'BB'))
    assert A.accion_fantasma(h) == []


# --------------------------------------------------------------------------
# ESTADO DE LOS JUGADORES — las cuatro clases nuevas
# --------------------------------------------------------------------------

def test_activo_sin_posicion():
    h = mano(players=[
        {'active': True, 'pos': '', 'name': 'sin_asiento'},
        {'active': True, 'pos': 'BB', 'name': 'sentado'},
        {'active': False, 'pos': '', 'name': 'fuera'},
    ])
    assert A.activo_sin_posicion(h) == ['sin_asiento sin pos']


def test_activo_sin_accion_no_cuenta_al_que_foldeo_ni_al_allin():
    h = mano(preflop=[acc('UTG', 'f', 0.0), acc('MP', 'c', 1.0)],
             activos=('UTG', 'MP', 'CO'), allin=['p2'])
    # UTG foldeo; CO (p3) esta all-in; MP actuo. Nadie queda sin accion.
    assert A.activo_sin_accion(h) == []


def test_activo_sin_accion_detecta_al_que_nunca_actuo():
    h = mano(preflop=[acc('UTG', 'f', 0.0), acc('BB', 'x', 0.0)],
             activos=('UTG', 'MP', 'BB'))
    assert A.activo_sin_accion(h) == ['MP sin accion ni fold ni all-in']


def test_activo_sin_accion_calle_detecta_al_que_desaparece():
    h = mano(preflop=[acc('BB', 'p', 1.0), acc('UTG', 'x', 0.0),
                      acc('BB', 'x', 0.0)],
             flop=[acc('UTG', 'b', 2.0)], activos=('UTG', 'BB'))
    # el BB actuo en preflop, pero no en el flop, donde si hubo accion.
    assert A.activo_sin_accion_calle(h) == ['BB sin accion en flop']


def test_activo_sin_accion_calle_no_cuenta_al_que_ya_foldeo_ni_al_allin():
    h = mano(preflop=[acc('BB', 'p', 1.0), acc('UTG', 'f', 0.0)],
             flop=[acc('BB', 'b', 2.0)], activos=('UTG', 'BB'))
    assert A.activo_sin_accion_calle(h) == []
    # el BB esta all-in: no se le exige accion en el flop; UTG si desaparece.
    h2 = mano(preflop=[acc('BB', 'p', 1.0), acc('UTG', 'x', 0.0)],
              flop=[acc('BB', 'b', 2.0)], activos=('UTG', 'BB'),
              allin=['p1'])
    fallos = A.activo_sin_accion_calle(h2)
    assert 'BB sin accion en flop' not in fallos, fallos
    assert fallos == ['UTG sin accion en flop'], fallos


def test_inactivo_con_posicion_es_metrica_y_no_defecto():
    h = mano(players=[
        {'active': False, 'pos': 'SB', 'name': 'ausente'},
        {'active': False, 'pos': '', 'name': 'fuera'},
        {'active': True, 'pos': 'BB', 'name': 'sentado'},
    ])
    assert A.inactivo_con_posicion(h) == ['SB(ausente)']
    assert 'INACTIVO_CON_POSICION' in [c for c, _e, _f
                                       in A.METRICAS_NO_FALLA]
    assert 'INACTIVO_CON_POSICION' not in [c for c, _e, _f, _n in A.CLASES]
