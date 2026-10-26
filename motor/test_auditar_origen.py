# -*- coding: utf-8 -*-
"""`tools/auditar_origen.py`: que los detectores sean fiables y no escriba.

Que hay que probar, y por que
-----------------------------
Un instrumento de auditoria tiene dos formas de mentir:

  1. dice que no hay nada. Un detector que no se contrasta con una respuesta
     conocida es una opinion. Y aqui el coste de creerselo es alto: se cierra
     la revision y el defecto se queda.
  2. escribe en la base. Este script SOLO propone. Y el encargo es explicito:
     la base no se toca mientras se investigan las inconsistencias.

La segunda se prueba de dos maneras, y las dos hacen falta: que correr la
auditoria no cambia el sha, y que el CHECK que vigila eso PUEDE FALLAR. Un
guard que solo se le ve pasar no se sabe si mira algo o si esta muerto.

Y hay una tercera cosa, mas sutil: que las cifras que salen esten FIJADAS. Sin
un test que las fije, un detector que empieza a devolver 0 casos —porque ha
dejado de mirar— pasa inadvertido, y «no hay nada que arreglar» es la peor
respuesta posible de un instrumento.
"""
import collections
import hashlib
import io
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn  # noqa: E402
from tools import auditar_origen as AO  # noqa: E402


def _sha_de_la_base():
    with open(AO.DB_PATH, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


# --- (0) la base no se toca ------------------------------------------------

def test_la_auditoria_no_escribe_la_base():
    """Mide el sha antes y despues de correr LAS TRES secciones.

    No se comprueba que el codigo «parezca» de solo lectura: se comprueba que
    la base tiene el mismo sha cuando el script termina.
    """
    antes = _sha_de_la_base()
    for seccion in (1, 2, 3):
        assert AO.main(['--seccion', str(seccion)]) == 0
    assert _sha_de_la_base() == antes, 'la auditoria cambio la base'


def test_el_volcado_json_no_toca_la_base(tmp_path):
    """Lo mismo con el volcado, que es la unica rama que escribe en disco."""
    antes = _sha_de_la_base()
    destino = tmp_path / 'salida.json'
    assert AO.main(['--json', str(destino)]) == 0
    assert _sha_de_la_base() == antes
    with io.open(str(destino), encoding='utf-8') as f:
        datos = json.load(f)
    assert datos['db_sha256'] == antes
    assert 's1' in datos and 's3' in datos


def test_el_sha_del_disco_es_el_declarado():
    """La premisa de todo: se audita lo que el manifiesto dice que hay."""
    assert _sha_de_la_base() == learn.HANDS_DB_SHA256, (
        'el disco tiene un sha que no es el declarado. O hay cambios sin '
        'commitear, o el manifiesto esta desfasado, y auditar no seria auditar '
        'la base canonica.')
    assert learn.HANDS_DB_COMMIT, 'no hay commit declarado'


@pytest.mark.parametrize('codigo', [
    "open(AO.DB_PATH, 'w')",
    'open(AO.ORIGEN_PATH, "w")',
    "open('data/hands_db.jsonl', 'a')",
    'open(ORIGEN_PATH, "w")',
    'os.replace(tmp, AO.DB_PATH)',
    'shutil.move(a, AO.DB_PATH)',
    'shutil.copyfile(a, AO.DB_PATH)',
])
def test_el_chequeo_de_escritura_detecta_lo_que_tiene_que_detectar(codigo):
    """Se planta la violacion y se exige que salte.

    Sin esto, el chequeo se veria pasar una vez y nadie sabria si mira algo.
    Es la diferencia entre un guard y una decoracion: un guard se prueba
    fallando.
    """
    assert AO.violaciones_de_escritura(codigo), (
        'el chequeo NO detecta %r. Si no puede fallar, no esta mirando nada.'
        % codigo)


def test_el_chequeo_no_dispara_con_lo_que_este_fichero_hace_de_verdad():
    """El otro lado: no puede que avise de lo legitimo.

    Este fichero SI escribe en disco, para el volcado `--json`. Si el chequeo
    protestara por eso, dejaria de avisar de lo que importa. Un guard que
    grita siempre es un guard apagado.
    """
    propio = io.open(os.path.join(ROOT, 'tools', 'auditar_origen.py'),
                     encoding='utf-8').read()
    assert AO.violaciones_de_escritura(propio) == []


def test_la_autocomprobacion_del_script_pasa():
    assert AO.validar() == 0


# --- (1) posiciones y ciegas ----------------------------------------------

def test_las_cifras_de_posiciones_estan_fijadas():
    """Las cifras de §1.1, una a una, sobre la base normalizada.

    Si `con_SB` baja de 1220, o `sin_SB` deja de ser 33, alguien ha cambiado
    la base o el detector, y hay que saber cual antes de seguir con el informe.
    """
    manos = AO.cargar()
    assert len(manos) == 1253
    s1 = AO.seccion_1(manos)
    inv = s1['inventario']
    assert inv['con_BB'] == 1253, 'toda mano tiene BB'
    assert inv['sin_BB'] == 0
    assert inv['con_SB'] == 1220
    assert inv['sin_SB'] == 33
    assert inv['BB_sin_posting'] == 0
    assert inv['SB_sin_posting'] == 0
    assert inv['con_pos_duplicada'] == 0


def test_un_jugador_sin_pos_es_uno_que_no_jugo():
    """La conclusion de §1.4, y la que mas cosas sostiene.

    `pos` vacia se leia como «la etiqueta se perdio». Si este test falla, la
    conclusion se cae y hay que reescribir §1.4 entero. Por eso se mide, y no
    se dice «parece que».
    """
    manos = AO.cargar()
    sin_pos = con_accion = 0
    for h in manos.values():
        posiciones_en_accion = {
            a.get('pos') for calle in AO.CALLES
            for a in AO.acciones(h, calle) if a.get('pos')}
        for p in h.get('players') or []:
            if p.get('pos'):
                continue
            sin_pos += 1
            # un jugador sin posicion no puede tener acciones: la posicion es
            # la unica clave, asi que una accion suya seria inasignable
            if any(not a.get('pos') for calle in AO.CALLES
                   for a in AO.acciones(h, calle)):
                con_accion += 1
    assert sin_pos == 804, sin_pos
    assert con_accion == 0, (
        '%d jugadores sin pos tienen acciones. La accion no se puede atribuir '
        'a nadie, porque `pos` es la unica clave. Si esto falla, la conclusion '
        'de §1.4 ya no vale.' % con_accion)


def test_no_hay_mesa_corta_ni_ante_ni_straddle():
    """Lo que §1.2 dice que NO hay, comprobado.

    Una afirmacion negativa sobre 1258 manos es la clase de conclusion que se
    acepta sin verificar. Esta se verifica.

    Y el criterio tiene que ser el CORRECTO, que no es «la primera accion es
    del BB»: en 337 manos la primera accion es de UTG o MP, y eso no es un
    ante, es que la ciega del BB no se capturó (§2.5). Lo que distinguiría un
    ante o un straddle es que **antes de que nadie actúe, más de una
    posición ciegue**, y con un importe que no sea el de una ciega.
    """
    import collections
    manos = AO.cargar()
    e = AO.seccion_1e(manos)
    assert e['n_jugadores'] == {6: 1253}, e['n_jugadores']

    # El ante y el straddle se descartan por IMPORTE y por POSICION: una
    # posta solo puede ser la ciega pequeña (0.5), la grande (1.0) o el limp
    # de 1.0 que la normalizacion codifica como `p`. Un ante sería menor y un
    # straddle mayor. Que haya varias `p` no es un ante: son ciegas y limps.
    for h in manos.values():
        for a in AO.acciones(h, 'preflop'):
            if a.get('action') != 'p':
                continue
            assert a.get('pos') in AO.POSICIONES, (h['hand_id'], a)
            assert float(a.get('amount') or 0.0) in (0.5, 1.0), (
                '%s: la posta de %s es de %s. Un importe que no sea 0.5, 1.0 '
                'seria un ante o un straddle, y no hay ninguno.'
                % (h['hand_id'], a.get('pos'), a.get('amount')))
    # Y el BB siempre postea, en el indice 0 o justo despues de la SB.
    for h in manos.values():
        post = AO.posting_de(h, 'BB')
        assert post is not None and AO.es_posting(h, 'BB'), h['hand_id']
        assert post['indice'] in (0, 1), (h['hand_id'], post)
        assert post['amount'] in (0.5, 1.0), (h['hand_id'], post)
        if post['indice'] == 1:
            primera = AO.acciones(h, 'preflop')[0]
            assert (primera.get('pos'), primera.get('action')) == ('SB', 'p'), (
                h['hand_id'], primera, post)


def test_la_ciega_del_bb_que_existe_es_siempre_la_misma():
    """1253 postings, y todos valen 1.0. La SB vale 0.5 en 1220."""
    manos = AO.cargar()
    s1 = AO.seccion_1(manos)
    assert s1['bb_importes'] == {1.0: 1253}, s1['bb_importes']
    assert s1['sb_importes'] == {0.5: 1220}, s1['sb_importes']
    for hid, h in manos.items():
        p = AO.posting_de(h, 'BB')
        if p is not None and AO.es_posting(h, 'BB'):
            assert p['indice'] in (0, 1), (
                '%s: la ciega del BB esta en el indice %d. Solo puede estar '
                'en 0 o justo despues de la SB.' % (hid, p['indice']))


# --- (2) semantica de importes -------------------------------------------

def test_la_semantica_viene_del_codigo_del_grabador_no_de_una_suposicion():
    """Que `amount` sea el acumulado esta en el codigo, y se comprueba ahi.

    No se contrasta con una cifra de la base —que es justamente lo que no
    decidia el agregado—, sino con el texto del grabador. Si alguien cambia
    la lectura del `_bet`, este test salta antes de que el informe diga otra
    cosa.
    """
    codigo = io.open(os.path.join(ROOT, 'recorder', 'record_hand.py'),
                     encoding='utf-8').read()
    assert "bet = state.get(f'{pid}_bet')" in codigo
    assert "'amount': bet" in codigo
    assert "'amount': new_bet" in codigo
    # y NO hay ninguna operacion que convierta new_bet en un delta
    assert 'new_bet - old_bet' not in codigo, (
        'el grabador RESTA. Si lo hace, `amount` es un delta y toda la '
        'documentacion de esta auditoria esta al reves.')


def test_la_serie_acumulada_es_monotona():
    """Solo UN caso no monotonico, declarado, y ninguna `r` lo rompe.

    Es lo que distingue un campo acumulado de un campo delta: con delta, una
    `b` posterior puede ser menor sin que pase nada. Con acumulado, no.

    El unico caso es `H_0357`: el BB postea 1.0 y luego aparece una `b` de
    0.5. Es un defecto de la mano, no de la lectura; se declara con su id
    para que no se cuele como normalidad.

    PERO NO ES LA MEDIDA DE CONSISTENCIA. Monotonia solo comprueba que la
    caja de un jugador no BAJE. La propiedad fuerte es que una `c` LLEGUE a
    la apuesta viva: hoy son **42 de 13826** las que no llegan.
    Ver `test_las_calls_que_no_llegan_a_la_viva`.
    """
    manos = AO.cargar()
    s2 = AO.seccion_2(manos)
    pa = s2['por_accion']
    for clave in ('preflop/r', 'flop/b', 'flop/r', 'turn/b', 'turn/r',
                  'river/b', 'river/r'):
        assert pa[clave]['NO_MONOTONA'] == 0, (
            '%s tiene %d casos no monotonos. Un `b` o una `r` que baja el '
            'acumulado significa que `amount` NO es un acumulado, y toda esta '
            'auditoria tendria que rehacerse.'
            % (clave, pa[clave]['NO_MONOTONA']))
    assert pa['preflop/b']['NO_MONOTONA'] == 1, pa['preflop/b']
    ejemplo = s2['ejemplos_no_monotona']['preflop/b'][0]
    assert ejemplo[0] == 'H_0357', ejemplo
    total_no_mono = sum(v['NO_MONOTONA'] for v in pa.values())
    assert total_no_mono == 1, total_no_mono


def test_las_calls_que_no_llegan_a_la_viva():
    """42 de 13826. Esta es la cifra de consistencia, no la de monotonia.

    La normalizacion redujo los calls por debajo de la viva de 503 a 42: el
    caso patologico de `H_0039` ya no existe. El que queda se declara con una
    mano concreta (`H_0058`), para que el test siga midiendo el defecto y no
    solo el total.
    """
    manos = AO.cargar()
    total = 0
    por_calle = collections.Counter()
    for h in manos.values():
        for calle in AO.CALLES:
            viva = 0.0
            for a in AO.acciones(h, calle):
                act = a.get('action')
                try:
                    imp = float(a.get('amount') or 0)
                except (TypeError, ValueError):
                    continue
                if act == 'c' and imp < viva - 1e-6:
                    total += 1
                    por_calle[calle] += 1
                if act in ('b', 'r', 'c'):
                    viva = max(viva, imp)
    assert total == 42, total
    assert dict(por_calle) == {'preflop': 8, 'flop': 12, 'turn': 12,
                               'river': 10}, dict(por_calle)
    # y el caso declarado, byte a byte
    h = manos['H_0058']
    seq = [(a.get('pos'), a.get('action'), a.get('amount'))
           for a in AO.acciones(h, 'river')]
    assert seq == [('BB', 'x', 0.0), ('MP', 'b', 15.3), ('BB', 'c', 9.1)], seq


def test_las_manos_con_una_accion_repetida():
    """2 acciones repetidas en 2 pares (mano, calle), y ninguna consecutiva.

    Eso importa para la formula `aportado = amount - acumulado_anterior`: una
    repeticion da `aportado = 0`, que es un importe inventado. Y como el
    esquema no guarda marca de tiempo, **no se puede distinguir** una repeticion
    de una lectura duplicada de un jugador que actuo dos veces con la misma
    caja.
    """
    manos = AO.cargar()
    claves = 0
    pares = set()
    consecutivas = 0
    for hid, h in sorted(manos.items()):
        for calle in AO.CALLES:
            acs = AO.acciones(h, calle)
            visto = collections.Counter(
                (a.get('pos'), a.get('action'), a.get('amount')) for a in acs)
            for k, v in visto.items():
                if v > 1:
                    claves += 1
                    pares.add((hid, calle))
            for i in range(len(acs) - 1):
                a, b = acs[i], acs[i + 1]
                if (a.get('pos') == b.get('pos')
                        and a.get('action') == b.get('action')
                        and a.get('amount') == b.get('amount')):
                    consecutivas += 1
    # dos cifras distintas y las dos ciertas: 2 ACCIONES repetidas,
    # repartidas en 2 pares (mano, calle). La normalizacion limpio el resto.
    assert claves == 2, claves
    assert len(pares) == 2, len(pares)
    assert consecutivas == 0, (
        '%d repeticiones consecutivas. Una repeticion CONSECUTIVA con la misma '
        'caja es la firma de una doble lectura, que es un defecto distinto del '
        'de una repeticion separada por otras acciones.' % consecutivas)


def test_las_no_monotonas_son_calls():
    """Las 26 son `c`, y 9 son el check que se graba como call."""
    manos = AO.cargar()
    pa = AO.seccion_2(manos)['por_accion']
    for clave in pa:
        if clave.endswith('/b') or clave.endswith('/r'):
            continue
        assert clave.endswith('/c'), clave


def test_el_patron_del_bb_es_exacto_no_aproximado():
    """51 de 52 parejas exactas; la unica diferencia se declara.

    La normalizacion alineo las cajas de SB y BB: el antiguo patron del BB que
    grababa otra cosa queda reducido a una pareja con -8.0 (`H_0104`).
    """
    manos = AO.cargar()
    s2c = AO.seccion_2c(manos)
    assert s2c['total_parejas'] == 52, s2c['total_parejas']
    assert s2c['diferencias'] == {'-8.0': 1, '0.0': 51}, s2c['diferencias']


def test_h001_es_el_ejemplo_del_informe():
    """El ejemplo que sostiene §2.4, byte a byte.

    Si `H_0001` cambia, el ejemplo del documento deja de describir lo que hay,
    y un documento con un ejemplo falso es peor que sin ejemplo.
    """
    manos = AO.cargar()
    sec = [(a.get('pos'), a.get('action'), a.get('amount'))
           for a in AO.acciones(manos['H_0001'], 'preflop')]
    assert sec == [('SB', 'p', 0.5), ('BB', 'p', 1.0), ('UTG', 'b', 2.5),
                   ('MP', 'c', 2.5), ('CO', 'f', 0.0), ('BTN', 'c', 2.5),
                   ('SB', 'c', 2.5), ('BB', 'c', 2.5)], sec


# --- (3) botes ------------------------------------------------------------

def test_el_bote_exacto_cuadra_en_373_de_1253():
    """373 exactas, 29.8%. La cifra de la base normalizada.

    Un detector que empieza a cuadrar mas puede ser una mejora O puede ser que
    ha dejado de mirar. Por eso el numero esta fijado con su motivo: la
    normalizacion convirtio las cajas en acumulados completos y el bote paso
    de cuadrar en 69 manos a cuadrar en 373.
    """
    manos = AO.cargar()
    s3 = AO.seccion_3(manos)
    assert s3['exactas'] == 373, s3['exactas']
    assert s3['falta'] == 3, s3['falta']
    assert s3['sobra'] == 877, s3['sobra']


def test_el_rake_no_explica_el_bote():
    """La regla del mantenedor, contra los datos. Y no cuadra mas que sin ella.

    `final_pot` ya descuenta el 5% hasta 2.5BB. Aplicarlo aqui cuadra **268**
    de 1253; sin rake, **373**. Una comision que se descuenta siempre no
    explica el bote: el ajuste sin rake sigue siendo mejor.

    Se deja escrito porque «me dijeron que hay rake» es el tipo de entrada que
    hace cuadrar cualquier cosa y no cuadrar nada.
    """
    import collections
    manos = AO.cargar()
    con_rake = sin_rake = 0
    for h in manos.values():
        pot = h.get('final_pot')
        if not isinstance(pot, (int, float)):
            continue
        _d, s = AO.aportar_por_jugador(h, 'TOTAL')
        if abs((s - min(0.05 * s, 2.5)) - pot) < 0.005:
            con_rake += 1
        if abs(s - pot) < 0.005:
            sin_rake += 1
    assert sin_rake == 373, sin_rake
    assert con_rake == 268, con_rake
    assert con_rake < sin_rake, 'el rake empeora el cuadre; si dejara de ' \
        'empeorarlo, la regla del rake tendria que revisarse'


def test_aportar_mas_que_el_stack_no_depende_del_rake():
    """12 manos. Es el invariante mas duro, porque no mira el bote."""
    manos = AO.cargar()
    s3 = AO.seccion_3(manos)
    inv = AO.seccion_3c(manos, s3)
    assert inv['I4_aporta_mas_que_stack'] == 12, inv['I4_aporta_mas_que_stack']
    assert inv['I2_bote_no_supera_aportado'] == 3
    assert inv['I1_bote_no_negativo'] is True


def test_h0546_ya_no_tiene_un_bote_que_no_aparece():
    """H_0546 quedo reparada por la normalizacion, y se fija el caso.

    Antes: `final_pot = 0.5` con 92.6 aportados. Ahora: `final_pot = 102.7`
    con 105.1 aportados, y las cajas finales de BTN y BB son las del all-in.
    Se conserva la comprobacion de la lectura TOTAL (ultimo valor de la caja,
    no suma de acciones).
    """
    manos = AO.cargar()
    h = manos['H_0546']
    detalle, suma = AO.aportar_por_jugador(h, 'TOTAL')
    assert round(suma, 1) == 105.1, (
        'H_0546 tiene que dar 105.1 con la lectura TOTAL. Si da otra cosa, la '
        'funcion esta sumando las acciones en vez de tomar el ultimo valor de '
        'cada caja.')
    assert h['final_pot'] == 102.7
    assert detalle['SB']['preflop'] == 0.5, detalle['SB']
    assert detalle['BTN']['preflop'] == 52.3, detalle['BTN']
    assert detalle['BB']['preflop'] == 52.3, detalle['BB']
    # el BTN se fue TODO el stack, que es lo que hace el all-in
    stacks = {p.get('pos'): p.get('stack') for p in h.get('players') or []}
    assert stacks['BTN'] == 52.3, stacks['BTN']


def test_el_esquema_no_tiene_id_pero_los_ids_son_asientos():
    """`winner`, `allin` y `btn_player` son ids de asiento, y se resuelven.

    No hay campo `_id`: la correspondencia es `players[PLAYER_IDS.index(x)]`,
    y por eso el contrato exige seis asientos. El informe anterior decia que
    eran irresolubles; era falso, y este test fija la lectura correcta.
    """
    from motor.multiway import PLAYER_IDS, contrato_orden_ok
    manos = AO.cargar()
    claves = {k for h in manos.values()
              for p in h.get('players') or [] for k in p}
    assert '_id' not in claves, claves
    assert 'id' not in claves, claves
    for h in manos.values():
        assert contrato_orden_ok(h), h['hand_id']
        for x in (h.get('winner') or []) + (h.get('allin') or []) + \
                [h.get('btn_player')]:
            if x is None:
                continue
            assert x in PLAYER_IDS, (h['hand_id'], x)
            assert PLAYER_IDS.index(x) < len(h['players']), (h['hand_id'], x)


# --- (4) el informe y el instrumento no divergen --------------------------

def test_el_json_y_el_informe_cuentan_lo_mismo():
    """Lo que se imprime y lo que se vuelca tienen que salir de la MISMA
    cuenta, no de dos calculos parecidos."""
    manos = AO.cargar()
    s1 = AO.seccion_1(manos)
    s3 = AO.seccion_3(manos)
    assert s1['total'] == s3['exactas'] + s3['sobra'] + s3['falta'], (
        'el reparto de §3 no cubre las 1253 manos')
    assert sum(v for k, v in s1['inventario'].items()
               if k in ('con_SB', 'sin_SB')) == 1253
    assert sum(v for k, v in s1['inventario'].items()
               if k in ('con_BB', 'sin_BB')) == 1253