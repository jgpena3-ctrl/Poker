# -*- coding: utf-8 -*-
"""`diagnostico_grabador.py` y, sobre todo, el GRABADOR.

Que hay que probar, y por que no basta lo que habia
--------------------------------------------------
Hasta ahora la semantica del grabador se comprobaba buscando CADENAS DE TEXTO
en `record_hand.py`. Eso pasa aunque el comportamiento cambie, y no prueba
nada del comportamiento.

Aqui se ejecuta el codigo. Se construye un `HandRecorder` SIN capturador —con
`__new__`, para no abrir la camara— y se le llama a `detect_actions` con estados
fabricados a mano. Si el grabador cambia, estas pruebas se rompen; si cambia un
nombre de variable, no, que es justo lo que se quiere.

Y hay un segundo motivo, mas importante: la revision tecnica delega sus
conclusiones en el codigo del grabador, y no habia NINGUN test que ejecutara ese
codigo. Un diagnostico apoyado en lectura de codigo no esta verificado.

Lo que NO se prueba aqui, y se dice explicitamente:
  · que el OCR lea bien. Eso necesita una imagen.
  · que `BET_ROIS` cubra el elemento correcto. Tambien una imagen.
  · que `pot` y `pot_wide` sean la misma magnitud. Hace falta el codigo origen.

EL HALLAZGO QUE CORRIGE TODO LO ANTERIOR
---------------------------------------
La seccion (1) de este fichero ejecutaba `record_hand.HandRecorder`. Al
comprobar de donde sale el campo `allin` resulto que **`record_hand.py` no lo
escribe**: lo escribe `recorder_live.py`. Los dos grabadores apuntan a la
MISMA ruta (`data/hands_db.jsonl`), y en la base el campo esta en 1185 de 1258
manos.

O sea: **la base es una mezcla de dos grabadores**, y las pruebas de la
seccion (1) describen el que solo produjo 73 manos. Peor: `amount` no tiene una
semantica, tiene TRES, y cada una con la suya:

  · `record_hand.py:200`  -> la CAJA del jugador (`state[pid_bet]`)
  · `recorder_live.py:670` -> `prev_stake + prev_bet` (rama de all-in)
  · `recorder_live.py:699` -> `prev_stake - cur_stake`, el DELTA del stack,
                             redondeado por `_round_bet` (rama normal, ~98 %)

La tercera es la que explica casi todo, y es la que habria que usar. Las
pruebas de la seccion (1) siguen valiendo como caracterizacion de ESE codigo,
pero no como descripcion de la base. Por eso ahora se dizca cual de las tres
semanticas esta modelando cada caso sintetico.
"""
import collections
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'recorder'))

from tools import diagnostico_grabador as DG  # noqa: E402
from record_hand import PLAYER_IDS, HandRecorder, get_position  # noqa: E402

# Con `btn_player='hero'` los asientos son estos. Se fijan aqui porque el
# experimento depende de ellos, y porque son la prueba de que el boton
# determina la posicion: si esto cambia, el mapeo de ids cambia.
CON_HERO_BTN = {'BTN': 'hero', 'SB': 'p5', 'BB': 'p4', 'UTG': 'p3',
                'MP': 'p2', 'CO': 'p1'}
BB, SB, UTG, CO, MP, BTN = 'p4', 'p5', 'p3', 'p1', 'p2', 'hero'


def grabador(street_has_bet=False):
    """Un `HandRecorder` sin capturador, con lo minimo que pide detect_actions."""
    r = HandRecorder.__new__(HandRecorder)
    r.last_state = None
    r.street_bet = {}
    r.street_has_bet = street_has_bet
    r.hand = {'hand_id': 'T', 'btn_player': 'hero', 'current_street': 'preflop',
              'streets': {'preflop': {'actions': []}}, 'players': []}
    return r


def estado(bets, estados=None):
    s = {}
    for p in PLAYER_IDS:
        s['%s_bet' % p] = bets.get(p)
        s['%s_stake' % p] = 100.0
        s['%s_state' % p] = (estados or {}).get(p)
    return s


# ---------------------------------------------------------------------------
# (1) LA REGLA DE LA LETRA, EJECUTANDO EL CODIGO
#
# ATENCION: esta seccion modela `record_hand.py`, que produjo 73 de las 1258
# manos. La letra que se ve aqui NO es la letra de la base. Ver
# `test_la_base_son_dos_grabadores` y la cabecera del fichero.
# ---------------------------------------------------------------------------

def test_primera_apuesta_sin_apuesta_viva_previa_es_b():
    """Caja None -> X, sin apuesta viva en la calle: `b`."""
    r = grabador(street_has_bet=False)
    r.last_state = estado({BB: 1.0})
    got = r.detect_actions(estado({BB: 1.0, UTG: 2.5}))
    assert got == [{'pos': 'UTG', 'action': 'b', 'amount': 2.5}], got


def test_primera_apuesta_con_apuesta_viva_previa_es_call():
    """Caja None -> X, CON apuesta viva: `c`.

    Y esto es el hallazgo: la misma jugada, con la misma caja, se graba `b` o
    `c` segun si habia apuesta viva en la calle. La LETRA de la apertura dice
    si se capturo la ciega.
    """
    r = grabador(street_has_bet=True)
    r.last_state = estado({BB: 1.0})
    got = r.detect_actions(estado({BB: 1.0, UTG: 2.5}))
    assert got == [{'pos': 'UTG', 'action': 'c', 'amount': 2.5}], got


def test_subida_de_quien_ya_aposto_es_r():
    r = grabador(street_has_bet=True)
    r.last_state = estado({BB: 1.0, UTG: 2.5})
    got = r.detect_actions(estado({BB: 1.0, UTG: 9.0}))
    assert got == [{'pos': 'UTG', 'action': 'r', 'amount': 9.0}], got


def test_una_caja_en_cero_no_se_detecta():
    """El hallazgo que no esperaba, y que solo se ve ejecutando el codigo.

    La rama de `b`/`c` exige `old_bet is None` (`:245`) y la de `r` exige
    `old_bet > 0` (`:250`). Una caja en **0.0** no cumple ninguna de las dos, y
    el cambio a 6.0 **no emite nada**.

    O sea que el grabador solo ve a quien pasa de None, no de 0.0. Si la UI
    devolviera 0.0 en vez de None, se perderian TODAS las aperturas.
    """
    r = grabador(street_has_bet=True)
    r.last_state = estado({BB: 1.0, UTG: 0.0})
    assert r.detect_actions(estado({BB: 1.0, UTG: 6.0})) == []
    # y el mismo cambio desde None SI se ve
    r2 = grabador(street_has_bet=True)
    r2.last_state = estado({BB: 1.0, UTG: None})
    assert r2.detect_actions(estado({BB: 1.0, UTG: 6.0})) == [
        {'pos': 'UTG', 'action': 'c', 'amount': 6.0}]


def test_el_importe_emito_es_la_caja_nueva():
    """No hay ninguna resta en el codigo. El importe es `new_bet`, entero."""
    r = grabador(street_has_bet=True)
    r.last_state = estado({BB: 1.0, BTN: 6.0})
    got = r.detect_actions(estado({BB: 1.0, BTN: 11.0}))
    assert got == [{'pos': 'BTN', 'action': 'r', 'amount': 11.0}], got
    codigo = _codigo_del_grabador()
    assert 'new_bet - old_bet' not in codigo, (
        'el grabador RESTA. Si lo hace, `amount` es un delta y toda la '
        'documentacion de esta revision esta al reves.')


def _codigo_del_grabador():
    import io
    with io.open(os.path.join(ROOT, 'recorder', 'record_hand.py'),
                 encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
# (2) H_0039, REPRODUCIDO
# ---------------------------------------------------------------------------

def test_h0039_reproducido():
    """El eco del fallback, y la accion real que se pierde.

    La forma de `H_0039[8]` —el BTN vuelve a `c 6.0` despues de que la SB
    subiese a 11.0— se reproduce con estados sinteticos, y el resultado es
    DURO: el grabador emite DOS acciones para UNA accion real.
    """
    # 1. la primera call, por la via principal: correcta
    r = grabador(street_has_bet=True)
    r.last_state = estado({BB: 1.0, BTN: None})
    assert r.detect_actions(estado({BB: 1.0, BTN: 6.0})) == [
        {'pos': 'BTN', 'action': 'c', 'amount': 6.0}]

    # 2. la subida de la SB: sale `c`, no `r`
    r.last_state = estado({BB: 1.0, BTN: 6.0})
    sub = r.detect_actions(estado({BB: 1.0, BTN: 6.0, SB: 11.0}))
    assert sub == [{'pos': 'SB', 'action': 'c', 'amount': 11.0}], (
        'la subida de la SB sale `c`, no `r`: su caja estaba en None y la rama '
        'de `r` exige `old_bet > 0`. Si esto cambia, H_0039 ya no se explica '
        'como se explica.')

    # 3. el BTN actua pero su caja SIGUE en 6.0: el fallback emite el eco
    r.last_state = estado({BB: 1.0, BTN: 6.0, SB: 11.0})
    eco = r.detect_actions(estado({BB: 1.0, BTN: 6.0, SB: 11.0},
                                  estados={BTN: 'igualar'}))
    assert eco == [{'pos': 'BTN', 'action': 'c', 'amount': 6.0}], eco

    # 4. un fotograma despues, la caja ya sube: ahora si, con 11.0
    r.last_state = estado({BB: 1.0, BTN: 6.0, SB: 11.0}, {BTN: 'igualar'})
    real = r.detect_actions(estado({BB: 1.0, BTN: 11.0, SB: 11.0}))
    assert real == [{'pos': 'BTN', 'action': 'r', 'amount': 11.0}], real

    # 5. y si la caja nunca sube, NO se emite nada: la accion real se pierde
    r.last_state = estado({BB: 1.0, BTN: 6.0, SB: 11.0}, {BTN: 'igualar'})
    assert r.detect_actions(estado({BB: 1.0, BTN: 6.0, SB: 11.0},
                                   {BTN: 'igualar'})) == []


# ---------------------------------------------------------------------------
# (3) LA APUESTA VIVA
# ---------------------------------------------------------------------------

def _mano(acs, stacks=None):
    jugs = [{'pos': a['pos'], 'stack': (stacks or {}).get(a['pos'], 100.0),
             'active': True, 'name': a['pos'], 'cards': ''} for a in acs
            if a.get('pos')]
    return {'hand_id': 'T', 'streets': {
        'preflop': {'actions': acs, 'board': []},
        'flop': {'actions': [], 'board': []},
        'turn': {'actions': [], 'board': []},
        'river': {'actions': [], 'board': []}},
        'players': jugs, 'allin': [], 'final_pot': 0.0}


def test_la_viva_se_reinicia_en_cada_calle():
    """Una calle no hereda de la anterior.

    El grabador pone `street_bet = {p: None}` en `record_hand.py:316`, asi que
    tampoco tiene sentido sumarlas. Si este test falla, el cruce de calles se
    ha colado en el diagnostico.
    """
    h = {'hand_id': 'X', 'streets': {
        'preflop': {'actions': [{'pos': 'BB', 'action': 'b', 'amount': 1.0},
                                {'pos': 'UTG', 'action': 'r', 'amount': 9.0},
                                {'pos': 'MP', 'action': 'c', 'amount': 9.0}]},
        'flop': {'actions': [{'pos': 'BB', 'action': 'b', 'amount': 3.0},
                             {'pos': 'MP', 'action': 'c', 'amount': 3.0}]},
        'turn': {'actions': [{'pos': 'BB', 'action': 'b', 'amount': 5.0}]},
        'river': {'actions': []}},
        'players': [{'pos': p, 'stack': 100.0, 'active': True, 'name': p,
                     'cards': ''} for p in ('BB', 'UTG', 'MP')],
        'allin': [], 'final_pot': 0.0}
    ev_pf, fin_pf = DG.apuesta_viva(h, 'preflop')
    ev_fl, fin_fl = DG.apuesta_viva(h, 'flop')
    ev_tu, fin_tu = DG.apuesta_viva(h, 'turn')
    assert fin_pf == 9.0
    assert fin_fl == 3.0, 'la viva del flop no puede heredar los 9.0 del preflop'
    assert fin_tu == 5.0, 'la viva del turn no puede heredar el flop'
    # y dentro del preflop, la MP iguala a 9.0: llega
    assert DG.calls_por_debajo(h) == []


def test_una_call_que_llega_a_la_viva_no_se_reporta():
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
               {'pos': 'CO', 'action': 'c', 'amount': 3.0}])
    assert DG.calls_por_debajo(h) == []


def test_una_call_que_no_llega_se_reporta_con_su_falta():
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
               {'pos': 'CO', 'action': 'c', 'amount': 1.0}])
    cc = DG.calls_por_debajo(h)
    assert len(cc) == 1
    assert abs(cc[0]['falta'] - 2.0) < 1e-6, cc[0]


def test_un_c_cero_se_marca_y_no_se_confunde_con_una_call_corta():
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
               {'pos': 'CO', 'action': 'c', 'amount': 0.0}])
    cc = DG.calls_por_debajo(h)
    assert len(cc) == 1 and cc[0]['es_cero']


# ---------------------------------------------------------------------------
# (4) LA CLASIFICACION DE APORTADO
# ---------------------------------------------------------------------------

def test_una_secuencia_coherente_es_calculable():
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
               {'pos': 'CO', 'action': 'c', 'amount': 3.0}])
    for x in DG.clasificar_aportado(h):
        assert x['resultado'] == DG.CALCULABLE, x


def test_una_call_corta_sin_accion_previa_es_indeterminada():
    """Sin referencia anterior Y sin llegar a la viva: falta una captura.

    Y lo importante: **no devuelve importe**. Devolver 0 seria afirmar que el
    jugador no puso nada, que es otra cosa distinta de «no se puede saber».
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
               {'pos': 'CO', 'action': 'c', 'amount': 1.0}])
    res = DG.clasificar_aportado(h)
    corta = [x for x in res if x['action'] == 'c'][0]
    assert corta['resultado'] == DG.INDETERMINADA, corta
    assert corta['aportado'] is None, (
        'una aportacion indeterminada no puede devolver un numero. Si devuelve '
        '0, esta afirma que el jugador no puso nada.')


def test_una_call_que_supera_la_viva_es_sospechosa():
    """CASO A. Importe SUPERIOR a la apuesta viva.

    SEMANTICA MODELADA: `record_hand.py`, es decir `amount` = CAJA acumulada.
    Solo 73 de las 1258 manos son de ese grabador. Con la semantica del otro
    (`recorder_live.py`, `amount` = delta del stack) este caso NO es una
    anomalia: un delta puede pasarse de la viva sin decir nada raro. La
    prueba se queda como caracterizacion de la rama `or 0.0` del
    clasificador, no como afirmacion sobre la base.

    Qué anomalía introduce: una `c` que pasa de la viva. Una call cubre, no
    pasa. Y si el importe cuadra con la viva vigente y no con la anterior, la
    caja se leyó ANTES de actualizarse.

    Qué da el clasificador HOY: `SOSPECHOSA`, con el motivo «supera la viva».

    Lo que NO se afirma: que las dos acciones sean dos acciones reales. Con
    la semántica acumulada, un importe que sube sin que la suba del rival es
    exactamente lo que deja un eco del fallback (§ H_0039), pero el esquema
    no lleva fotogramas y no se puede distinguir de dos acciones de verdad.
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 9.0}])
    res = DG.clasificar_aportado(h)
    segunda = [x for x in res if x['pos'] == 'CO'][1]
    assert abs(segunda['importe'] - 9.0) < 1e-6, segunda
    assert segunda['resultado'] == DG.SOSPECHOSA, segunda
    assert 'supera la viva' in segunda['motivo'], segunda['motivo']


def test_una_caja_que_baixa_es_sospechosa():
    """CASO B. DISMINUCIÓN real de la caja, que el caso A no tenía.

    SEMANTICA MODELADA: `record_hand.py` (`amount` = caja acumulada). Y aqui
    hay que avisar de algo importante: **con la semantica de `recorder_live.py`
    (`amount` = delta del stack) esta prueba no tiene sentido**. Alli dos
    acciones del mismo jugador SI pueden bajar, porque cada importe es un
    delta independiente, no un acumulado. Marcar un delta descendente como
    sospechoso seria un falso positivo sistematico sobre el 94 % de la base.

    Lo que NO se afirma: que esto caracterice la base. Caracteriza la rama del
    clasificador que trata la caja como acumulada.

    Qué anomalía introduce: la caja del MISMO jugador BAJA entre dos acciones
    suyas en la misma calle. Con la semántica acumulada eso no puede ocurrir,
    así que o hay una lectura obsoleta o los dos registros no son dos acciones
    reales.

    Por qué esta prueba estaba mal antes: la anterior se llamaba
    `test_alcanzar_la_viva_no_basta_para_ser_calculable` y su comentario
    hablaba de «la caja bajó antes», pero sus datos iban de **5.0 a 9.0**, que
    es una subida. La prueba no demostraba lo que su nombre y su comentario
    decían. Se separa en A y B, y cada una construye la anomalía que dice.

    Qué da el clasificador HOY: las dos acciones de la bajada salen
    `SOSPECHOSA`, y la segunda con `aportado` **negativo**.
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 5.0},
               {'pos': 'CO', 'action': 'r', 'amount': 9.0},
               {'pos': 'CO', 'action': 'c', 'amount': 5.0}])
    res = DG.clasificar_aportado(h)
    ultima = [x for x in res if x['pos'] == 'CO'][2]
    assert abs(ultima['importe'] - 5.0) < 1e-6, ultima
    assert ultima['resultado'] == DG.SOSPECHOSA, ultima
    assert ultima['aportado'] == -4.0, ultima
    # [DEFECTO CONOCIDO] una aportacion NEGATIVA sale SOSPECHOSA y no
    # INDETERMINADA. Nadie aporta fichas negativas: un negativo aqui es la
    # senal de que la caja se leyo antes de tiempo, que es un dato que no se
    # puede usar, no uno que se puede usar con signo. Propuesto, no aplicado.


def test_un_duplicado_da_aportado_cero_y_se_marca_sospechoso():
    """Una repeticion NO se resuelve como «el jugador no puso nada».

    Da 0 por diferencia, que es aritmeticamente cierto y semanticamente
    falso. El resultado tiene que ser SOSPECHOSA, nunca CALCULABLE con 0.
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
               {'pos': 'SB', 'action': 'r', 'amount': 5.0},
               {'pos': 'UTG', 'action': 'c', 'amount': 1.0}])
    res = DG.clasificar_aportado(h)
    segunda = [x for x in res if x['pos'] == 'UTG' and x['action'] == 'c'][1]
    assert segunda['aportado'] == 0.0, 'la diferencia aritmetica es 0'
    assert segunda['resultado'] != DG.CALCULABLE, (
        'un duplicado no puede salir CALCULABLE con 0: 0 significa «no puso», '
        'y aqui significa «no se sabe».')


def test_un_redondeo_no_se_declara_sospechoso():
    """0.1 de diferencia es de la escala del OCR, no un defecto."""
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 4.9}])
    res = DG.clasificar_aportado(h)
    co = [x for x in res if x['pos'] == 'CO'][0]
    assert co['resultado'] == DG.CALCULABLE, co


def _mano_un_importe(importe, accion='c', stacks=None, base=1.0):
    """Una mano minima con UNA accion cuyo `amount` es el valor pedido.

    `importe` se pasa tal cual: si es la cadena `'AUSENTE'` no se escribe la
    clave, y si es `None` se escribe con valor None. Asi se puede distinguir
    «no esta la clave» de «esta y vale None», que el clasificador NO.
    """
    acs = [{'pos': 'BB', 'action': 'b', 'amount': base}]
    if accion == 'c':
        acs += [{'pos': 'UTG', 'action': 'r', 'amount': 5.0},
                {'pos': 'CO', 'action': accion}]
    else:
        acs += [{'pos': 'UTG', 'action': accion}]
    if importe == 'AUSENTE':
        # la clave `c` no la trae de serie; pop con default para no reventar
        acs[-1].pop('amount', None)
    else:
        acs[-1]['amount'] = importe
    return _mano(acs, stacks=stacks)


def test_importe_ausente_se_confunde_con_cero():
    """[DEFECTO] La clave `amount` AUSENTE se lee como 0.0.

    `float(a.get('amount') or 0.0)` no distingue tres cosas que son tres:

      · la clave no existe          -> sale 0.0
      · la clave existe con None    -> sale 0.0
      · la clave existe con 0.0     -> sale 0.0

    Y de ahi sale un motivo INVENTADO: un importe ausente se reporta como
    «c 0.0: el grabador traduce un check a call», que es una explicacion
    sobre el grabador hecha con un dato que no existe. Si el campo se perdio,
    no sabemos nada de ese importe; no sabemos que fuera un check.

    En la base actual hay 0 importes ausentes entre las 5974 de b/c/r, asi
    que esto NO ha contaminado los conteos. Es un defecto latente, no un
    error de datos. Se fija el comportamiento, no se corrige.
    """
    h = _mano_un_importe('AUSENTE')
    res = DG.clasificar_aportado(h)
    co = [x for x in res if x['pos'] == 'CO'][0]
    assert co['resultado'] == DG.SOSPECHOSA, co
    assert 'traduce un check' in co['motivo'], (
        'el motivo prohibido aparece con un importe AUSENTE: %s' % co['motivo'])


def test_importe_none_tambien_se_confunde():
    """[DEFECTO] `amount: None` explicitado sale igual que ausente.

    Y sale por el mismo motivo inventado. Aqui la diferencia con el caso
    anterior es que el dato se LOSTO de forma explicita: el grabador sabe que
    no lo tiene, y el diagnostico lo cuenta igual que si fuera un cero.
    """
    h = _mano_un_importe(None)
    res = DG.clasificar_aportado(h)
    co = [x for x in res if x['pos'] == 'CO'][0]
    assert co['resultado'] == DG.SOSPECHOSA, co
    assert co['importe'] == 0.0, (
        'un None deberia llegar como None, no convertido a 0.0: %s' % co)


def test_importe_cero_legitimo_no_se_confunde_con_ausente():
    """Un 0.0 REAL no es lo mismo que un 0.0 inventado.

    Una call de 0.0 es un check, y el diagnostico lo trata distinto. El
    problema no es ese camino: es que los tres casos anteriores caen en el
    mismo. Aqui se deja constancia de que el camino del 0.0 real funciona.
    """
    h = _mano_un_importe(0.0)
    res = DG.clasificar_aportado(h)
    co = [x for x in res if x['pos'] == 'CO'][0]
    assert co['resultado'] == DG.SOSPECHOSA, co
    assert co['importe'] == 0.0, co


def test_importe_no_convertible_es_indeterminada():
    """Un importe que no es numero NO se puede usar, y sale como tal.

    Este es el unico de los cinco que esta bien, y conviene que lo este: es el
    criterio que las otras dos rutas deberian seguir.
    """
    h = _mano_un_importe('no-es-un-numero')
    res = DG.clasificar_aportado(h)
    co = [x for x in res if x['pos'] == 'CO'][0]
    assert co['resultado'] == DG.INDETERMINADA, co
    assert co['importe'] is None, co


def test_apuesta_viva_descarta_lo_ilegible():
    """El filtro tambien se come los importes ilegibles, pero sin avisar.

    `apuesta_viva` hace `continue` sobre lo que no convierte. Eso esta bien
    como decision (una viva ilegible no se puede comparar), pero el efecto es
    que la lista sale MAS CORTA que la calle. Quien la use para indexar por
    posicion tiene que saber eso, y hoy no hay ninguna asercion que lo fije.
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 'ilegible'},
               {'pos': 'CO', 'action': 'c', 'amount': 3.0}])
    eventos, n_vivas = DG.apuesta_viva(h, 'preflop')
    assert len(eventos) < 4, 'la calle tiene 4 acciones con dinero'
    assert all(e['viva_antes'] >= 0 for e in eventos), eventos


def test_un_allin_corto_es_calculable():
    """All-in aparente, caso 1: sin otras anomalías.

    Qué anomalía introduce: el jugador iguala con todo su stack y su caja no
    llega a la viva porque no pudo. Es una jugada legítima.

    Qué da HOY: `CALCULABLE`.

    Lo que se sigue SIN poder afirmar: que sea un all-in confirmado. Lo que
    hay es una **coincidencia aritmética** entre `amount` y `stack`, y que los
    dos campos sean comparables —que midan lo mismo y en el mismo instante—
    no está demostrado. Ver `test_el_allin_no_esta_confirmado`.

    Y en el caso de `recorder_live.py` la comparacion es ademas numericamente
    sucia: en la rama de all-in el importe es `prev_stake + prev_bet`, o sea
    que ya lleva la apuesta dentro, mientras `stack` es el stack del jugador.
    Que coincidan no es ni siquiera una igualdad entre cosas homogeneas.
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 3.0}],
              stacks={'CO': 3.0})
    res = DG.clasificar_aportado(h)
    co = [x for x in res if x['pos'] == 'CO'][0]
    assert co['resultado'] == DG.CALCULABLE, co
    assert co['aportado'] == 3.0, co


def test_allin_con_accion_repetida_sale_calculable():
    """All-in aparente, caso 2: ACCIÓN REPETIDA con importe == stack.

    Y aquí está el defecto más serio del clasificador: la rama del all-in
    devuelve `CALCULABLE` **sin mirar las demás sospechas**. Una acción
    repetida con aportación 0 sale `CALCULABLE`, y una repetición es
    justamente lo que NO se puede usar como dato.

    Se fija el comportamiento ACTUAL, no el deseado. La corrección propuesta
    está en el informe y **no se aplica aquí**, porque cambiaría los tres
    conteos publicados.
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'c', 'amount': 3.0},
               {'pos': 'SB', 'action': 'r', 'amount': 5.0},
               {'pos': 'UTG', 'action': 'c', 'amount': 3.0}],
              stacks={'UTG': 3.0})
    res = DG.clasificar_aportado(h)
    utg = [x for x in res if x['pos'] == 'UTG']
    assert len(utg) == 2
    for x in utg:
        # [DEFECTO CONOCIDO] las dos salen CALCULABLE, incluida la repetida,
        # cuya aportacion es 0. Una repeticion con aporte 0 no es un dato.
        assert x['resultado'] == DG.CALCULABLE, x
    assert utg[1]['aportado'] == 0.0, utg[1]


def test_allin_con_caja_incoherente_sale_calculable():
    """All-in aparente, caso 3: CAJA PREVIA INCOHERENTE, ultimo importe == stack.

    La caja del jugador fue 5.0, luego 9.0, y la última acción vuelve a 4.0.
    Eso es imposible con la semántica acumulada. Y como 4.0 coincide con su
    stack, la rama del all-in lo declara `CALCULABLE` con **aportado −5.0**.

    Nadie aporta fichas negativas. Un negativo no es un dato con signo: es la
    señal de que la caja se leyó antes de tiempo.
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 5.0},
               {'pos': 'CO', 'action': 'r', 'amount': 9.0},
               {'pos': 'CO', 'action': 'c', 'amount': 4.0}],
              stacks={'CO': 4.0})
    res = DG.clasificar_aportado(h)
    co = [x for x in res if x['pos'] == 'CO']
    ultima = co[-1]
    # [DEFECTO CONOCIDO] las dos primeras si se marcan; la ultima sale
    # CALCULABLE con un aporte negativo.
    assert ultima['resultado'] == DG.CALCULABLE, ultima
    assert ultima['aportado'] == -5.0, ultima


def test_sin_stack_la_allin_no_se_puede_detectar():
    """All-in aparente, caso 4: la posición no tiene stack.

    Sin stack **no hay con qué comparar**, así que la rama del all-in no
    puede dispararse. Es lo correcto: un all-in es una afirmación sobre el
    stack del jugador.

    Y el efecto secundario es que la acción cae en `INDETERMINADA` si tampoco
    hay acción previa. Que es correcto por otra razón: sin referencia
    anterior y sin llegar a la viva, no hay forma de saber cuánto puso.
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 2.0}],
              stacks={'BB': 1.0, 'UTG': 100.0})
    res = DG.clasificar_aportado(h)
    co = [x for x in res if x['pos'] == 'CO'][0]
    assert co['resultado'] == DG.INDETERMINADA, co
    assert co['aportado'] is None, co


def test_la_base_son_dos_grabadores():
    """La regresion mas importante de este fichero.

    `data/hands_db.jsonl` esta escrito por DOS programas distintos:

      · 1182 manos de `recorder_live.py`, que pone el campo `allin`;
      · 71 manos de `record_hand.py`, que no lo pone.

    El bloque pequeno sigue siendo H_0001..H_0073, pero la adopcion retiro
    `H_0028` y `H_0072`, asi que ya no es contiguo. Se declaran las dos
    ausencias en vez de fingir que el bloque sigue intacto.

    Por que importa: todo lo que se mida sobre la base sin separar los dos
    grupos esta mezclando dos instrumentos con semanticas de `amount`
    distintas.

    Se fija el reparto como regresion. Si alguien normaliza la base y mete el
    campo que falta en las 71, esta prueba se rompe y obliga a volver a
    pensar el resto.
    """
    import json
    import io
    ruta = os.path.join(ROOT, 'data', 'hands_db.jsonl')
    con, sin = [], []
    for linea in io.open(ruta, encoding='utf-8'):
        if not linea.strip():
            continue
        # sobre el dict parseado, no sobre el texto: `allin` puede aparecer
        # como valor de una clave cualquiera y daria un falso positivo
        (con if 'allin' in json.loads(linea) else sin).append(linea)
    assert len(con) == 1182, 'manos de recorder_live: %d' % len(con)
    assert len(sin) == 71, 'manos de record_hand: %d' % len(sin)

    ids = sorted(int(json.loads(x)['hand_id'].split('_')[-1]) for x in sin)
    assert ids == [i for i in range(1, 74) if i not in (28, 72)], (
        'las 71 sin `allin` ya no son H_0001..H_0073 menos H_0028 y H_0072: '
        '%s..%s' % (ids[0], ids[-1]))


def test_la_apertura_cambia_tras_la_normalizacion():
    """La LETRA ya no separa los dos grabadores, y se fija el nuevo reparto.

    Antes de normalizar, `recorder_live` emitia casi siempre `b` como primera
    accion voluntaria porque contaba la ciega como apuesta viva. La
    normalizacion convirtio las ciegas en `p` y recodifico las aperturas, asi
    que ahora la primera `b`/`c`/`r` es una decision real: la mayoria son
    calls (limps) y raises. El corte por `allin` sigue siendo valido; lo que
    ya no vale es usar la letra como huella del grabador.
    """
    import collections
    import io
    import json

    ruta = os.path.join(ROOT, 'data', 'hands_db.jsonl')
    c = collections.defaultdict(collections.Counter)
    for linea in io.open(ruta, encoding='utf-8'):
        if not linea.strip():
            continue
        h = json.loads(linea)
        grupo = 'live' if 'allin' in h else 'hand'
        acs = (h.get('streets', {}).get('preflop', {}) or {}).get('actions', [])
        for a in acs:
            if a.get('action') in ('b', 'c', 'r'):
                c[grupo][a['action']] += 1
                break
    # Medido sobre la base normalizada. El grupo `hand` conserva su mezcla;
    # el `live` ya no es un `b` por cada siete.
    assert dict(c['hand']) == {'b': 31, 'c': 29, 'r': 4}, dict(c['hand'])
    assert dict(c['live']) == {'b': 100, 'c': 520, 'r': 467}, dict(c['live'])
    assert c['live']['c'] > c['live']['r'] > c['live']['b'], dict(c['live'])


def test_el_allin_no_esta_confirmado():
    """Lo que la coincidencia aritmética NO demuestra.

    `amount == stack` dice que los dos números coinciden. NO dice que los dos
    campos midan lo mismo, ni que sean del mismo instante, ni que la acción
    sea real.

    El campo `allin` es el que declara el all-in, y lo escribe
    `recorder_live.py:1040` a partir de una condicion CONCRETA y legible:
    el stack del jugador paso a `None` sin que estuviera difuminado
    (`recorder_live.py:669`). Eso si es una senal de all-in. La coincidencia
    de `amount` con `stack` solo es **compatible** con una.

    Y hay un problema mas: `allin` solo existe en una parte de la base.
    """
    import io
    codigo = io.open(os.path.join(ROOT, 'recorder', 'recorder_live.py'),
                     encoding='utf-8').read()

    # la condicion que DECLARA el all-in: el stack pasa a None y el jugador
    # no esta difuminado
    i = codigo.find('cur_stake is None and not dimmed')
    assert i != -1, (
        'no se encuentra la condicion de all-in de recorder_live.py. Si ha '
        'cambiado, esta prueba tiene que cambiar con ella: es la unica fuente '
        'documentada de que un allin sea un allin y no una cuenta.')
    rama = codigo[i:i + 600]
    assert '_allin_players.add(pid)' in rama, (
        'la rama de all-in ya no marca al jugador. El campo `allin` se '
        'vaciaria y las 1182 manos que lo tienen perderian su unica senal.')
    # y la lista final filtra por activo, que es el defecto INC-002 / H_0851
    j = codigo.find("out['allin']")
    assert j != -1
    assert "p['active']" in codigo[j:j + 300], (
        'la lista `allin` vuelve a no filtrar por `active`.INC-002 / H_0851 '
        'vuelve: un jugador que se compromete y foldea sale en `allin`.')

    # [P] follow-up importante: en esa rama el importe es
    #     round((prev_stake or 0) + prev_bet, 2), o sea STACK ANTES + CAJA.
    #     Compararlo con `stack` compara contra una cantidad que ya lleva la
    #     apuesta dentro. La coincidencia no es ni siquiera numericamente
    #     limpia; ver el informe.


def test_el_campo_allin_no_lo_escribe_record_hand():
    """Por que `SIN_ALLIN` NO significa «pos vacia = no jogo».

    `record_hand.py` y `recorder_live.py` escriben a la MISMA ruta
    (`data/hands_db.jsonl`). Uno pone el campo `allin` y el otro no. Asi que
    la ausencia del campo es la HUELLA de que esa mano la escribio el otro
    grabador.

    Mi explicacion anterior («`allin` vacio significa que el jugador no
    llego a jugar») era COMPATIBLE con los datos y FALSA en el mecanismo.
    Esta prueba es la que la desmonta.
    """
    import io
    rh = io.open(os.path.join(ROOT, 'recorder', 'record_hand.py'),
                 encoding='utf-8').read()
    rl = io.open(os.path.join(ROOT, 'recorder', 'recorder_live.py'),
                 encoding='utf-8').read()
    assert 'allin' not in rh, (
        'record_hand.py ha pasado a escribir `allin`. Si los dos escriben el '
        'campo, la huella de que grabador produjo cada mano desaparece y esta '
        'prueba pierde su sentido.')
    assert 'allin' in rl, 'recorder_live.py debe seguir escribiendo `allin`'
    # y los dos escriben a la misma ruta: por eso se mezclaron
    assert 'hands_db.jsonl' in rh and 'hands_db.jsonl' in rl, (
        'los dos grabadores tienen que seguir apuntando a la misma ruta. Si '
        'alguno cambia OUTPUT_PATH, la mezcla historica deja de poder '
        'reconstruirse con el campo `allin`.')


# ---------------------------------------------------------------------------
# (5) LAS CIFRAS DE LA BASE
# ---------------------------------------------------------------------------

def test_las_42_calls_por_debajo_de_la_viva():
    """La normalizacion redujo el defecto de 498 a 42.

    La regla no cambio: la viva sale solo de `b` y `r`. Lo que cambio es la
    base, que ahora trae las cajas completas y los calls alineados. Quedan 42
    calls que no llegan, y se fijan para que el detector siga mirando.
    """
    manos = DG.cargar()
    total = 0
    cortas = 0
    for h in manos.values():
        for calle in DG.CALLES:
            ev, _v = DG.apuesta_viva(h, calle)
            for e in ev:
                if e['action'] != 'c':
                    continue
                total += 1
                if e['viva_antes'] > 1e-6 and e['amount'] < e['viva_antes'] - 1e-6:
                    cortas += 1
    assert total == 2603, total
    assert cortas == 42, cortas


def test_la_falta_ya_no_es_dominante_pero_sigue_sin_ser_solo_del_bb():
    """De las 42 calls cortas, solo 3 tienen falta 1.0 y 10 son del BB.

    El hallazgo original —«es la ciega del BB»— ya no explica la mayoria:
    hay calls cortas en las seis posiciones. Se fija el reparto para que el
    detector no se convierta en una explicacion unica.
    """
    manos = DG.cargar()
    calls = []
    for h in manos.values():
        calls.extend(DG.calls_por_debajo(h))
    uno = sum(1 for c in calls if abs(c['falta'] - 1.0) < 0.05)
    assert len(calls) == 42, len(calls)
    assert uno == 3, uno
    por_pos = collections.Counter(c['pos'] for c in calls)
    assert por_pos['BB'] == 10, dict(por_pos)
    assert por_pos['MP'] > 0 and por_pos['CO'] > 0 and por_pos['UTG'] > 0


def test_la_clasificacion_sobre_la_base():
    manos = DG.cargar()
    tot = collections.Counter()
    for h in manos.values():
        for x in DG.clasificar_aportado(h):
            tot[x['resultado']] += 1
    assert tot[DG.CALCULABLE] == 5001, dict(tot)
    assert tot[DG.SOSPECHOSA] == 29, dict(tot)
    assert tot[DG.INDETERMINADA] == 23, dict(tot)


def test_el_desglose_por_accion_por_resultado_es_coherente():
    """La prueba 2D, en UNA sola pasada, sobre la base normalizada.

    La matriz ya no es la del informe antiguo (5433/445/96): la normalizacion
    arreglo las cajas y el total baja a 5053. Se fija la matriz entera y se
    exige que:

      1. las filas sumen el total de la matriz;
      2. las columnas sumen el total de la matriz;
      3. las columnas sumen exactamente los totales absolutos publicados.

    Si alguna vez el clasificador cambia, esto se rompe en vez de dejar dos
    numeros que ya no hablan entre si.
    """
    manos = DG.cargar()
    matriz = collections.defaultdict(collections.Counter)
    for h in manos.values():
        for x in DG.clasificar_aportado(h):
            matriz[x['action']][x['resultado']] += 1

    esperado = {'b': {DG.CALCULABLE: 1444, DG.SOSPECHOSA: 4},
                'c': {DG.CALCULABLE: 2559, DG.SOSPECHOSA: 21,
                      DG.INDETERMINADA: 23},
                'r': {DG.CALCULABLE: 998, DG.SOSPECHOSA: 4}}
    assert {k: dict(v) for k, v in matriz.items()} == {
        k: {r: n for r, n in v.items() if n} for k, v in esperado.items()}, (
        {k: dict(v) for k, v in matriz.items()})

    total_matriz = sum(sum(f.values()) for f in matriz.values())
    assert total_matriz == 5053, total_matriz
    for accion, fila in matriz.items():
        assert sum(fila.values()) == sum(esperado[accion].values()), accion
    assert (sum(matriz['b'][r] for r in matriz['b'])
            + sum(matriz['c'][r] for r in matriz['c'])
            + sum(matriz['r'][r] for r in matriz['r'])) == total_matriz

    col = collections.Counter()
    for fila in matriz.values():
        col.update(fila)
    assert col[DG.CALCULABLE] == 5001, dict(col)
    assert col[DG.SOSPECHOSA] == 29, dict(col)
    assert col[DG.INDETERMINADA] == 23, dict(col)


def test_el_reparto_por_accion_suma_el_total_de_la_base():
    """Que el total de la matriz sea el de las acciones que aportan.

    `f` y `x` no aportan y quedan fuera a proposito; que el total cuadre con
    la suma de las tres acciones que aportan es la comprobacion de que la
    exclusion es la que se cree que es.
    """
    manos = DG.cargar()
    tot = collections.Counter()
    for h in manos.values():
        for x in DG.clasificar_aportado(h):
            tot[x['action']] += 1
    assert tot['b'] == 1448, dict(tot)
    assert tot['c'] == 2603, dict(tot)
    assert tot['r'] == 1002, dict(tot)
    assert sum(tot.values()) == 5053, dict(tot)


def test_las_repeticiones_no_son_consecutivas():
    manos = DG.cargar()
    reps = []
    for h in manos.values():
        reps.extend(DG.repeticiones(h))
    assert len(reps) == 2, len(reps)
    assert len({(r['hand_id'], r['calle']) for r in reps}) == 2
    assert sum(1 for r in reps if r['consecutiva']) == 0, (
        'una repeticion CONSECUTIVA con la misma caja es la firma de una doble '
        'lectura, que es un defecto distinto del de una repeticion separada.')


# ---------------------------------------------------------------------------
# (6) LA CORRECCION DE §7: LOS IDS SI SE RESUELVEN
# ---------------------------------------------------------------------------

def test_los_ids_se_resuelven_con_el_boton():
    """CORRECCION de informes anteriores.

    Se dijo que `winner`, `allin` y `btn_player` eran irresolubles por falta de
    un campo `pid`. Es FALSO: `get_position(pid, btn_player)` los traduce.

    Y no es una suposicion: 46 de los 204 ids de `allin` tienen un compromiso
    exactamente igual a su stack, que es la definicion de all-in.
    """
    manos = DG.cargar()
    resueltos = 0
    confirmados = 0
    for h in manos.values():
        btn = h.get('btn_player')
        if btn not in PLAYER_IDS:
            continue
        stacks = {p.get('pos'): p.get('stack')
                  for p in h.get('players') or [] if p.get('pos')}
        for x in (h.get('allin') or []):
            pos = get_position(str(x), btn)
            if not pos:
                continue
            resueltos += 1
            st = stacks.get(pos)
            if st is None:
                continue
            compromiso = 0.0
            for calle in DG.CALLES:
                ultimo = {}
                for a in DG.acciones(h, calle):
                    if a.get('action') in ('b', 'c', 'r'):
                        try:
                            ultimo[a.get('pos')] = float(a.get('amount') or 0)
                        except (TypeError, ValueError):
                            pass
                compromiso += ultimo.get(pos, 0.0)
            if abs(compromiso - float(st)) <= 0.05:
                confirmados += 1
    assert resueltos == 204, resueltos
    assert confirmados == 46, confirmados


def test_h0546_el_allin_apunta_al_que_se_fue():
    """El `allin` de H_0546 es CORRECTO.

    `allin: ['p1']` con `btn_player='p1'` resuelve a BTN, que es quien subio
    sus 52.3. La normalizacion tambien arreglo `final_pot` (102.7 frente a
    105.1 aportados); este test sigue fijando la parte del all-in.
    """
    manos = DG.cargar()
    h = manos['H_0546']
    pos = get_position('p1', h['btn_player'])
    assert pos == 'BTN', pos
    stacks = {p.get('pos'): p.get('stack') for p in h.get('players') or []}
    assert stacks['BTN'] == 52.3
    ultimo = {}
    for a in DG.acciones(h, 'preflop'):
        if a.get('action') in ('b', 'c', 'r'):
            ultimo[a.get('pos')] = a.get('amount')
    assert ultimo['BTN'] == 52.3, ultimo['BTN']


# ---------------------------------------------------------------------------
# (7) LA AUTOCOMPROBACION DEL INSTRUMENTO
# ---------------------------------------------------------------------------

def test_la_autocomprobacion_del_instrumento_pasa():
    assert DG.validar() == 0


def test_el_instrumento_no_escribe_la_base():
    """El SHA antes y despues de las TRES zonas."""
    import hashlib

    import auditar_origen as AO

    def sha():
        with open(AO.DB_PATH, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    antes = sha()
    DG.analizar()
    assert sha() == antes