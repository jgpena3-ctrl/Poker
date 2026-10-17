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


def test_alcanzar_la_viva_no_basta_para_ser_calculable():
    """La regla que el encargo decía insuficiente, comprobada.

    Una call puede ALCANZAR la viva y aun asi ser sospechosa: si su caja BAJO
    antes en la misma calle, hay una lectura obsoleta por medio, y la
    coherencia del importe final no dice nada sobre cuando se leyó.
    """
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 9.0}])
    res = DG.clasificar_aportado(h)
    segunda = [x for x in res if x['action'] == 'c'][1]
    assert abs(segunda['importe'] - 9.0) < 1e-6, segunda
    assert segunda['resultado'] != DG.CALCULABLE, (
        'una accion cuyo importe supera a la viva por 4.0 sale CALCULABLE. '
        'Llegar a la viva no es condicion suficiente.')


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


def test_un_allin_corto_no_se_declara_sospechoso():
    """Igualar el stack es una all-in legitima, no una lectura mala."""
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 5.0},
               {'pos': 'CO', 'action': 'c', 'amount': 3.0}],
              stacks={'CO': 3.0})
    res = DG.clasificar_aportado(h)
    co = [x for x in res if x['pos'] == 'CO'][0]
    assert co['resultado'] == DG.CALCULABLE, (
        'una all-in corta es legitima. Si sale sospechosa, el diagnostico '
        'esta marcando como defecto algo que es una jugada.')


# ---------------------------------------------------------------------------
# (5) LAS CIFRAS DE LA BASE
# ---------------------------------------------------------------------------

def test_las_498_no_las_503():
    """El numero depende de una regla, y la regla ahora esta escrita.

    El 503 de la revision tecnica calculaba la viva incluyendo tambien las
    calls. Con la regla documentada —la viva sale solo de `b` y `r`— son 498.
    Los 5 de diferencia son justamente los anomalos.
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
    assert total == 2558, total
    assert cortas == 498, cortas


def test_la_falta_de_uno_dominante_y_no_es_solo_del_bb():
    """337 de 498 con falta exactamente 1.0, en las seis posiciones.

    Es el hallazgo que hace que «es la ciega del BB» no alcance: la mitad de
    las de los que NO postearon tambien valen 1.0.
    """
    manos = DG.cargar()
    calls = []
    for h in manos.values():
        calls.extend(DG.calls_por_debajo(h))
    uno = sum(1 for c in calls if abs(c['falta'] - 1.0) < 0.05)
    assert len(calls) == 498, len(calls)
    assert uno == 337, uno
    por_pos = collections.Counter(c['pos'] for c in calls)
    assert por_pos['BB'] == 251, dict(por_pos)
    assert por_pos['MP'] > 0 and por_pos['CO'] > 0 and por_pos['UTG'] > 0


def test_la_clasificacion_sobre_la_base():
    manos = DG.cargar()
    tot = collections.Counter()
    for h in manos.values():
        for x in DG.clasificar_aportado(h):
            tot[x['resultado']] += 1
    assert tot[DG.CALCULABLE] == 5433, dict(tot)
    assert tot[DG.SOSPECHOSA] == 445, dict(tot)
    assert tot[DG.INDETERMINADA] == 96, dict(tot)


def test_las_repeticiones_no_son_consecutivas():
    manos = DG.cargar()
    reps = []
    for h in manos.values():
        reps.extend(DG.repeticiones(h))
    assert len(reps) == 26, len(reps)
    assert len({(r['hand_id'], r['calle']) for r in reps}) == 21
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

    Y no es una suposicion: 38 de los 202 ids de `allin` tienen un compromiso
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
    assert resueltos == 202, resueltos
    assert confirmados == 38, confirmados


def test_h0546_el_allin_apunta_al_que_se_fue():
    """El `allin` de H_0546 es CORRECTO.

    `allin: ['p1']` con `btn_player='p1'` resuelve a BTN, que es quien subio
    sus 52.3. El problema de esa mano esta solo en `final_pot`.
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