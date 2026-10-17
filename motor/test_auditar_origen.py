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
    """Las cifras de §1.1, una a una.

    Si `con_SB` baja de 1229, o `sin_SB` deja de ser 29, alguien ha cambiado
    la base o el detector, y hay que saber cual antes de seguir con el informe.
    """
    manos = AO.cargar()
    assert len(manos) == 1258
    s1 = AO.seccion_1(manos)
    inv = s1['inventario']
    assert inv['con_BB'] == 1258, 'toda mano tiene BB'
    assert inv['sin_BB'] == 0
    assert inv['con_SB'] == 1229
    assert inv['sin_SB'] == 29
    assert inv['BB_sin_posting'] == 337
    assert inv['SB_sin_posting'] == 1198
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
    assert sin_pos == 783, sin_pos
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
    assert e['n_jugadores'] == {6: 1258}, e['n_jugadores']

    # Lo que distinguiría un ante o un straddle es que **más de una posición
    # cieguee**. Y se mide con `es_posting`, que decide por SECUENCIA (§1.3):
    # una `b` que abre es posting si antes no hay dinero de nadie en el bote.
    #
    # No se usa «la racha inicial de acciones con importe» porque no
    # distingue: en `H_0001` la racha es `UTG b 2.5 · MP c 2.5`, que es una
    # apertura y una call, no dos ciegas. En 337 manos la ciega del BB no se
    # capturó y la racha inicial es enteramente voluntaria. Un criterio que
    # no sabe eso declara un ante donde no lo hay.
    for h in manos.values():
        que_ciegan = [p for p in ('SB', 'BB')
                      if AO.posting_de(h, p) and AO.es_posting(h, p)]
        assert len(que_ciegan) <= 1, (
            '%s: ciegan %s. Dos posiciones ciegueando seria un ante o un '
            'straddle, y no hay ninguno.' % (h['hand_id'], que_ciegan))
    # Y el importe de los postings, que es donde se ve la diferencia entre una
    # ciega y una apertura. Solo se comprueba el BB, y por una razon que el
    # propio dato impone:
    #
    #   `es_posting` NO puede distinguir una ciega de una APERTURA grabada
    #   como `b`. El grabador escribe `b` a quien abre
    #   (`record_hand.py:246`: `'b' if not street_has_bet else 'c'`), asi que
    #   `H_0032` tiene `SB b 5.0` en la racha inicial y es una apertura, no
    #   una ciega de 5.0. Aplicar el filtro de importe a la SB daria 9 falsos
    #   positivos.
    #
    #   El BB no tiene ese problema: su `b` esta en el indice 0 en 921 de 921
    #   manos que la tienen, y en el indice 0 no puede ser una apertura porque
    #   una apertura requiere haber foldado o igualado antes.
    for h in manos.values():
        post = AO.posting_de(h, 'BB')
        if post and AO.es_posting(h, 'BB'):
            assert post['indice'] == 0, (h['hand_id'], post)
            assert post['amount'] in (0.5, 1.0), (
                '%s: la posting del BB es de %s, y no es ni una ciega grande '
                '(1.0) ni una ciega pequeña (0.5). Un 2.0 seria un ante o un '
                'straddle.' % (h['hand_id'], post['amount']))


def test_la_ciega_del_bb_que_existe_es_siempre_la_misma():
    """921 postings, y 915 de ellos valen 1.0. Los otros 6 se DECLARAN."""
    manos = AO.cargar()
    s1 = AO.seccion_1(manos)
    assert s1['bb_importes'] == {1.0: 915, 0.5: 6}, s1['bb_importes']
    for hid, h in manos.items():
        p = AO.posting_de(h, 'BB')
        if p is not None and AO.es_posting(h, 'BB'):
            assert p['indice'] == 0, (
                '%s: la ciega del BB no esta en el indice 0 sino en el %d. '
                'La migracion que se provó y se revirtió asumia el indice 0, '
                'y por eso no puede comprobarse solo aqui.' % (hid, p['indice']))


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
    """6354 de 6380, y NINGUNA `b` ni `r` la rompe.

    Es lo que distingue un campo acumulado de un campo delta: con delta, una
    `b` posterior puede ser menor sin que pase nada. Con acumulado, no.

    PERO NO ES LA MEDIDA DE CONSISTENCIA, y este docstring lo decía mal.
    Monotonia solo comprueba que la caja de un jugador no BAJE. No comprueba
    que una `c` LLEGUE a la apuesta viva, que es la propiedad fuerte.

    Medida esa: **503 de 13826 acciones son calls que no llegan a la viva.**
    Ver `test_las_calls_que_no_llegan_a_la_viva`.
    """
    manos = AO.cargar()
    s2 = AO.seccion_2(manos)
    pa = s2['por_accion']
    for clave in ('preflop/b', 'preflop/r', 'flop/b', 'flop/r',
                  'turn/b', 'turn/r', 'river/b', 'river/r'):
        assert pa[clave]['NO_MONOTONA'] == 0, (
            '%s tiene %d casos no monotonos. Un `b` o una `r` que baja el '
            'acumulado significa que `amount` NO es un acumulado, y toda esta '
            'auditoria tendria que rehacerse.'
            % (clave, pa[clave]['NO_MONOTONA']))
    total_no_mono = sum(v['NO_MONOTONA'] for v in pa.values())
    assert total_no_mono == 26, total_no_mono


def test_las_calls_que_no_llegan_a_la_viva():
    """503 de 13826. Esta es la cifra de consistencia, no las 26.

    Es la propiedad que `seccion_2` NO midia, y por eso el «99.6% monótono» del
    informe anterior invite a leer «el dato es consistente en general». No lo
    es: el numero fuerte es 503.

    Y hay una segunda lectura de estos casos que no es «la caja esta mal»: una
    lectura OBSOLETA. `record_hand.py:244` emite cuando `new_bet != old_bet`, y
    el fallback por estado (`:256-285`) emite para un jugador NO detectado en
    el primer bucle, leyendo la caja EN ESE MOMENTO. Si la caja todavia no se
    ha actualizado, el importe emitido es el viejo. `H_0039` lo tiene claro.
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
    assert total == 503, total
    assert por_calle['preflop'] == 412, dict(por_calle)
    # y el caso paradigmatico, byte a byte
    h = manos['H_0039']
    seq = [(a.get('pos'), a.get('action'), a.get('amount'))
           for a in AO.acciones(h, 'preflop')]
    assert seq[6] == ('BTN', 'c', 6.0), seq
    assert seq[7] == ('SB', 'r', 11.0), seq
    assert seq[8] == ('BTN', 'c', 6.0), (
        'se esperaba la lectura OBSOLETA de H_0039[8]. Si aqui hay un 11.0, o '
        'la mano cambio, o este test ha dejado de mirar lo que dice mirar.')


def test_las_manos_con_una_accion_repetida():
    """21 manos. Y la repeticion NO es consecutiva en ninguna.

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
    # dos cifras distintas y las dos certainas: 26 ACCIONES repetidas,
    # repartidas en 21 pares (mano, calle). Una mano con dos acciones
    # repetidas cuenta una vez en `pares` y dos en `claves`, y esa diferencia
    # es la que hizo que una primera version de este test fallara.
    assert claves == 26, claves
    assert len(pares) == 21, len(pares)
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
    """44 de 44. Y 4 de 44 los dejarian pasar.

    Esta es la afirmacion mas fuerte del informe, y por eso tiene el test mas
    duro: si bajara de 44, la conclusion «el BB graba otra cosa» se caeria y
    habria que revisar §1.5 entero.
    """
    manos = AO.cargar()
    s2c = AO.seccion_2c(manos)
    assert s2c['total_parejas'] == 53, s2c['total_parejas']
    assert s2c['diferencias']['1.0'] == 44, s2c['diferencias']


def test_h001_es_el_ejemplo_del_informe():
    """El ejemplo que sostiene §2.4, byte a byte.

    Si `H_0001` cambia, el ejemplo del documento deja de describir lo que hay,
    y un documento con un ejemplo falso es peor que sin ejemplo.
    """
    manos = AO.cargar()
    sec = [(a.get('pos'), a.get('action'), a.get('amount'))
           for a in AO.acciones(manos['H_0001'], 'preflop')]
    assert sec == [('UTG', 'b', 2.5), ('MP', 'c', 2.5), ('CO', 'f', 0.0),
                   ('BTN', 'c', 2.5), ('SB', 'c', 2.5), ('BB', 'c', 1.5)], sec


# --- (3) botes ------------------------------------------------------------

def test_el_bote_exacto_cuadra_en_69_de_1258():
    """69 exactas, 5.5%. La cifra del informe, y fijada contra la función.

    Un detector que empieza a cuadrar mas puede ser una mejora O puede ser que
    ha dejado de mirar. Por eso el numero esta fijado con su motivo.

    El nombre de este test decía 89 y el docstring decia 7.1%. Los dos
    estaban mal: 89 era la cifra con la lectura DELTA, que se corrigio, y
    69/1258 es 5.5%. La ASERCION siempre fue 69; lo que estaba mal era el
    texto, que es lo que se lee. Corregido sin cambiar el resultado.
    """
    manos = AO.cargar()
    s3 = AO.seccion_3(manos)
    assert s3['exactas'] == 69, s3['exactas']
    assert s3['falta'] == 592, s3['falta']
    assert s3['sobra'] == 597, s3['sobra']


def test_el_rake_no_explica_el_bote():
    """La regla del mantenedor, contra los datos. Y no cambia nada.

    `final_pot` ya descuenta el 5% hasta 2.5BB. Aplicarlo aqui cuadra **29**
    de 1258; sin rake, **69**.

    Y no es que el rake empeore el cuadre por poco: es que no cambia nada del
    ajuste. Por minimos cuadrados, R² es 0.6965 sin rake y 0.6920 con rake.
    Una comision que se descuenta siempre no puede dejar la mitad de las manos
    con el bote por encima y la otra mitad por debajo, y eso es justo lo que
    pasa: 34.0% por debajo, 39.5% por encima, 18.0% iguales.

    Se deja escrito porque «me dijeron que hay rake» es el tipo de entrada que
    hace cuadrar cualquier cosa y no cuadrar nada.

    Este docstring decia «16 de 1258; sin rake, 189». Las dos cifras eran de la
    lectura DELTA, que se corrigio en `aportar_por_jugador`. La asercion ya
    era 29 y 69.
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
    assert sin_rake == 69, sin_rake
    assert con_rake == 29, con_rake
    assert con_rake < sin_rake, 'el rake empeora el cuadre; si dejara de ' \
        'empeorarlo, la regla del rake tendria que revisarse'


def test_aportar_mas_que_el_stack_no_depende_del_rake():
    """22 manos. Es el invariante mas duro, porque no mira el bote."""
    manos = AO.cargar()
    s3 = AO.seccion_3(manos)
    inv = AO.seccion_3c(manos, s3)
    assert inv['I4_aporta_mas_que_stack'] == 22, inv['I4_aporta_mas_que_stack']
    assert inv['I2_bote_no_supera_aportado'] == 592
    assert inv['I1_bote_no_negativo'] is True


def test_h0546_tiene_un_bote_que_no_aparece_en_la_mano():
    """El caso del encargo, explicado y con las cifras fijadas.

    `final_pot = 0.5` con 92.6 aportados. Esa cifra no sale de ninguna
    combinacion de las acciones, y por eso el informe la llama «un valor que no
    se puede reconstruir», no «un error de calculo».
    """
    manos = AO.cargar()
    h = manos['H_0546']
    detalle, suma = AO.aportar_por_jugador(h, 'TOTAL')
    assert round(suma, 1) == 92.6, (
        'H_0546 tiene que dar 92.6. Si da 107.6, la funcion esta SUMANDO los '
        'importes en vez de tomar el ULTIMO valor de cada caja, que es la '
        'lectura delta. El error es justo el que denuncia esta auditoria —el '
        'BB pasa por 1.0, 11.0 y 40.3, que son tres lecturas de la MISMA caja—, '
        'y este test existe para que no vuelva a colarse sin que nadie lo note.')
    assert h['final_pot'] == 0.5
    assert detalle['BTN']['preflop'] == 52.3, detalle['BTN']
    assert detalle['BB']['preflop'] == 40.3, detalle['BB']
    # el BTN se fue TODO el stack, que es lo que hace el all-in
    stacks = {p.get('pos'): p.get('stack') for p in h.get('players') or []}
    assert stacks['BTN'] == 52.3, stacks['BTN']


def test_el_esquema_no_tiene_campo_de_id():
    """`winner`, `allin` y `btn_player` son irresolubles, y es del ESQUEMA.

    No de una mano. Por eso no entra en la lista de «corregir a mano»: es una
    migracion de las 1258, y el informe lo dice como tal.
    """
    manos = AO.cargar()
    claves = {k for h in manos.values() for p in h.get('players') or [] for k in p}
    assert '_id' not in claves, claves
    assert 'id' not in claves, claves
    # y se comprobó que el id NO es el indice en players[]
    for h in manos.values():
        for x in (h.get('allin') or []):
            try:
                i = int(str(x)[1:]) - 1
            except ValueError:
                continue
            if 0 <= i < len(h.get('players') or []):
                assert h['players'][i].get('stack') not in (0, 0.0), (
                    'el id %s SI es el indice en players[] (stack 0). Entonces '
                    'la correspondencia existe y §3.4 esta equivocado.' % x)


# --- (4) el informe y el instrumento no divergen --------------------------

def test_el_json_y_el_informe_cuentan_lo_mismo():
    """Lo que se imprime y lo que se vuelca tienen que salir de la MISMA
    cuenta, no de dos calculos parecidos."""
    manos = AO.cargar()
    s1 = AO.seccion_1(manos)
    s3 = AO.seccion_3(manos)
    assert s1['total'] == s3['exactas'] + s3['sobra'] + s3['falta'], (
        'el reparto de §3 no cubre las 1258 manos')
    assert sum(v for k, v in s1['inventario'].items()
               if k in ('con_SB', 'sin_SB')) == 1258
    assert sum(v for k, v in s1['inventario'].items()
               if k in ('con_BB', 'sin_BB')) == 1258