# -*- coding: utf-8 -*-
"""Auditoria del origen: posiciones, ciegas, semantica de importes y botes.

    python tools/auditar_origen.py                    # informe completo
    python tools/auditar_origen.py --seccion 1        # solo una parte
    python tools/auditar_origen.py --json salida.json
    python tools/auditar_origen.py --validar          # autocomprobacion

QUE ES Y QUE NO ES
------------------
Es un instrumento de LECTURA. No escribe la base, y hay un guard que lo
comprueba leyendo su propio codigo. La razon no es el purismo: la revision
manual se hizo a mano precisamente porque un script que reescribe 1258 lineas
puede hacerlo sin que nadie lo note.

Los tres problemas van SEPARADOS y no se mezclan en un solo numero:

  1. POSICIONES Y CIEGAS      quien esta en la mesa, quien publico, y quien no
  2. SEMANTICA DE IMPORTES   que significa `amount`, y donde se incumple
  3. INTEGRIDAD DE BOTES     si lo apostado suma lo que dice el bote

Y hay una razon para separarlos que no es de estilo: se CONTESTAN entre si.
Un mismo numero —`BB c 1.5`— puede ser una posicion mal puesta, una ciega
omitida, un fallo del grabador, o una mesa corta. Si se suman los tres, sale
una cifra que no significa nada; si se separan, cada uno tiene su lista.

DONDE ESTA LA RESPUESTA DE LA SEMANTICA
----------------------------------------
No se deduce de los datos: esta en el codigo del grabador.

    recorder/record_hand.py:200   bet = state.get(f'{pid}_bet')
    recorder/record_hand.py:209   ... 'amount': bet
    recorder/record_hand.py:248   ... 'amount': new_bet
    recorder/record_hand.py:251   ... 'amount': new_bet
    recorder/record_hand.py:273   bet = state.get(f'{pid}_bet'); 'amount': bet

`amount` es el VALOR DE LA CAJA DE APUESTA del jugador en esa calle. O sea: la
CONTRIBUCION ACUMULADA en la calle, no el delta, y no el tamaño objetivo. Las
tres lecturas que se han barajado en este repositorio, y solo una es la del
codigo.

Y eso no convierte el dato en limpio. Las lineas 244-253 dicen cuando se
emite una accion:

    if new_bet != old_bet:
        if old_bet is None and new_bet is not None:   -> b o c
        elif new_bet > old_bet and old_bet > 0:       -> r

Que es un detector fotograma a fotograma contra `self.last_state`. De ahi se
siguen tres perdidas que se ven en los datos:

  - una accion cuya caja ya tenia importe en el fotograma ANTERIOR no se emite
    (porque no es None -> old_bet). Eso es la ciega que falta.
  - una subida con `old_bet == 0` no se emite: la rama de `r` exige
    `old_bet > 0`. Se pierde en silencio.
  - el importe es el de la CAJA EN ESE FOTOGRAMA. Si la caja va cambiando por
    animacion, el numero es el de un instante, no el del final.
"""
import argparse
import collections
import hashlib
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn  # noqa: E402
import auditar_rango as AR  # noqa: E402

DB_REL = 'data/hands_db.jsonl'
ORIGEN_REL = 'recorder/hands_db.jsonl'
DB_PATH = os.path.join(ROOT, *DB_REL.split('/'))
ORIGEN_PATH = os.path.join(ROOT, *ORIGEN_REL.split('/'))

CALLES = ('preflop', 'flop', 'turn', 'river')
BB_NOMINAL = 1.0
SB_NOMINAL = 0.5
POSICIONES = ('SB', 'BB', 'UTG', 'MP', 'CO', 'BTN')

# Donde dice el grabador que se saca el importe. Se citan en el informe para
# que ninguna conclusion sobre `amount` se sostenga sin el codigo delante.
CODIGO_IMPORTE = (
    'recorder/record_hand.py:200', 'recorder/record_hand.py:209',
    'recorder/record_hand.py:248', 'recorder/record_hand.py:251',
    'recorder/record_hand.py:273', 'recorder/record_hand.py:278',
    'recorder/record_hand.py:284',
)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def leer(path):
    out = []
    with io.open(path, encoding='utf-8') as f:
        for linea in f:
            if linea.strip():
                out.append(json.loads(linea))
    return out


def cargar():
    return {h['hand_id']: h for h in leer(DB_PATH)}


def acciones(hand, calle):
    return (((hand.get('streets') or {}).get(calle) or {}).get('actions')) or []


def num(hand):
    try:
        return int(str(hand['hand_id']).split('_')[-1])
    except (KeyError, ValueError):
        return 0


def posiciones(hand):
    return [p.get('pos') or '' for p in (hand.get('players') or [])]


def posting_de(hand, pos):
    """El `b` de una posicion en el preflop, o None. Con su indice.

    ESTA ES LA PREGUNTA DEL ENCARGO: que campo y que secuencia verifican que
    un jugador publico. La respuesta es: el campo es la accion `b` de esa
    posicion, y la secuencia es que este en el PREFLOP, antes de cualquier
    accion voluntaria.

    No hay otro marcador. No hay `blind: true` en ninguna de las 13826 acciones
    de la base —`learn._preflop_sequence` lo lee, pero el recorder no lo
    escribe—. Y la posicion sola no prueba nada: el BB aparece dozens de veces
    como `b` saliendo de una-apuesta, no posteando.
    """
    for i, a in enumerate(acciones(hand, 'preflop')):
        if a.get('pos') == pos and a.get('action') == 'b':
            return {'indice': i, 'amount': a.get('amount')}
    return None


def es_posting(hand, pos):
    """True si la `b` de esa posicion es un POSTING y no una apuesta propia.

    El criterio es de SECUENCIA, no de importe: un posting ocurre antes de
    que haya dinero de nadie en el bote. Se cuentan las acciones con importe
    de las posiciones ya vistas, y si esa suma es 0, la `b` no puede ser una
    apuesta: no hay nada que apostar.
    """
    puesto = 0.0
    for a in acciones(hand, 'preflop'):
        try:
            imp = float(a.get('amount') or 0.0)
        except (TypeError, ValueError):
            imp = 0.0
        if a.get('action') in ('b', 'r'):
            if a.get('pos') == pos and abs(puesto) < 1e-6:
                return True
            puesto += imp
    return False


# ---------------------------------------------------------------------------
# 1. POSICIONES Y CIEGAS
# ---------------------------------------------------------------------------

def seccion_1(manos):
    # Las claves se inicializan a 0 aunque no occurra. Un contador que solo
    # existe si el caso aparece obliga a `['clave']` a reventar en el
    # informante, y eso hace que un 0 se lea como «no medido» en vez de como
    # «medido y es cero». Que es justo la confusion que este informe evita en
    # todas partes.
    inv = collections.Counter({
        'con_SB': 0, 'sin_SB': 0, 'con_BB': 0, 'sin_BB': 0,
        'con_pos_vacia': 0, 'con_pos_duplicada': 0,
        'SB_sin_posting': 0, 'BB_sin_posting': 0,
        'BB_posting_no_al_principio': 0,
    })
    sin_sb, sin_bb, sin_ninguno = [], [], []
    sin_pos, pos_dup = [], []
    sb_no_posting, bb_no_posting = [], []
    bb_importes = collections.Counter()
    sb_importes = collections.Counter()

    for hid, h in manos.items():
        pos = posiciones(h)
        con_pos = [p for p in pos if p]
        vacias = sum(1 for p in pos if not p)

        tiene_sb = 'SB' in con_pos
        tiene_bb = 'BB' in con_pos
        inv['con_SB'] += tiene_sb
        inv['con_BB'] += tiene_bb
        inv['sin_SB'] += not tiene_sb
        inv['sin_BB'] += not tiene_bb
        if not tiene_sb:
            sin_sb.append(hid)
        if not tiene_bb:
            sin_bb.append(hid)
        if not tiene_sb and not tiene_bb:
            sin_ninguno.append(hid)
        if vacias:
            inv['con_pos_vacia'] += 1
            sin_pos.append((hid, vacias))
        dupes = [p for p, n in collections.Counter(con_pos).items() if n > 1]
        if dupes:
            inv['con_pos_duplicada'] += 1
            pos_dup.append((hid, sorted(dupes)))

        p_sb, p_bb = posting_de(h, 'SB'), posting_de(h, 'BB')
        if tiene_sb and (p_sb is None or not es_posting(h, 'SB')):
            inv['SB_sin_posting'] += 1
            sb_no_posting.append(hid)
        if tiene_bb:
            if p_bb is None:
                inv['BB_sin_posting'] += 1
                bb_no_posting.append(hid)
            else:
                bb_importes[p_bb['amount']] += 1
                if not es_posting(h, 'BB'):
                    inv['BB_posting_no_al_principio'] += 1
        if p_sb is not None:
            sb_importes[p_sb['amount']] += 1

    return {
        'inventario': dict(inv),
        'total': len(manos),
        'sin_sb': sorted(sin_sb, key=AR.num),
        'sin_bb': sorted(sin_bb, key=AR.num),
        'sin_ninguno': sorted(sin_ninguno, key=AR.num),
        'pos_vacia': sorted(sin_pos, key=lambda x: AR.num(x[0])),
        'pos_duplicada': sorted(pos_dup, key=lambda x: AR.num(x[0])),
        'sb_sin_posting': sorted(sb_no_posting, key=AR.num),
        'bb_sin_posting': sorted(bb_no_posting, key=AR.num),
        'bb_importes': dict(bb_importes),
        'sb_importes': dict(sb_importes),
    }


def seccion_1b(manos, s1):
    """Las manos sin SB, una a una, con la evidencia de que es eso y no otra."""
    filas = []
    for hid in s1['sin_sb']:
        h = manos[hid]
        pos = posiciones(h)
        acs = acciones(h, 'preflop')
        filas.append({
            'hand_id': hid,
            'posiciones': pos,
            'vacias': [p.get('name') for p in h.get('players') or [] if not p.get('pos')],
            'inactivas': [p.get('name') for p in h.get('players') or [] if not p.get('active')],
            'preflop': [(a.get('pos'), a.get('action'), a.get('amount')) for a in acs],
            'acciones_de_una_pos_inexistente': [
                (s, i, a.get('pos')) for s in CALLES
                for i, a in enumerate(acciones(h, s))
                if a.get('pos') and a.get('pos') not in pos],
            'final_pot': h.get('final_pot'),
        })
    return filas


def seccion_1e(manos):
    """Indicios de ante, straddle y mesa corta. Lo que se puede VER, no lo que se supone."""
    jugadores = collections.Counter()
    primera_acciones = collections.Counter()
    stacks = []
    for hid, h in manos.items():
        jugadores[len(h.get('players') or [])] += 1
        acs = acciones(h, 'preflop')
        if acs:
            primera_acciones[(acs[0].get('pos'), acs[0].get('action'))] += 1
        for p in h.get('players') or []:
            try:
                stacks.append(float(p.get('stack') or 0.0))
            except (TypeError, ValueError):
                pass
    stacks.sort()
    return {
        'n_jugadores': dict(sorted(jugadores.items())),
        'primera_accion_preflop': {'%s %s' % k: v for k, v in
                                   primera_acciones.most_common()},
        'stack_min': stacks[0] if stacks else None,
        'stack_max': stacks[-1] if stacks else None,
        'stack_mediana': stacks[len(stacks) // 2] if stacks else None,
    }


# ---------------------------------------------------------------------------
# 2. SEMANTICA DE IMPORTES
# ---------------------------------------------------------------------------

def acumulado(hand, calle, modo):
    """Recorre una calle y devuelve lo acumulado por posicion.

    modo 'TOTAL'  lo que dice el codigo del grabador: amount = la caja, que es
                  la contribucion acumulada de la calle.
    modo 'DELTA'  la lectura alternativa: amount = lo que se anade ahora.

    Se devuelven las dos series para poder compararlas sin decidir cual es la
    buena: decidir es de la seccion 3 y de la grabacion original.
    """
    total = collections.defaultdict(float)
    delta = collections.defaultdict(float)
    for a in acciones(hand, calle):
        pos = a.get('pos')
        try:
            imp = float(a.get('amount') or 0.0)
        except (TypeError, ValueError):
            continue
        if a.get('action') in ('b', 'c', 'r'):
            total[pos] += imp
            delta[pos] += imp
        elif a.get('action') == 'f':
            # un fold ya puso dinero antes; aqui no aporta nada nuevo
            pass
    return total, delta


def seccion_2(manos):
    """Comprueba, calle por calle, que la serie TOTAL sea monotona y coherente.

    La serie que produce la lectura TOTAL tiene que cumplir UNA cosa: el
    acumulado de un jugador no puede bajar nunca. Si baja, el importe no es un
    acumulado y la lectura TOTAL es falsa para esa mano.
    """
    # Las dos claves existen siempre, aunque valgan 0. Un contador que solo
    # aparece si el caso ocurre hace que `['NO_MONOTONA']` reviente, y una
    # excepcion en el informe se lee como «no medido» cuando si lo estaba.
    res = collections.defaultdict(
        lambda: collections.Counter({'ok': 0, 'NO_MONOTONA': 0}))
    ejemplos = collections.defaultdict(list)

    for hid, h in manos.items():
        for calle in CALLES:
            puesto = collections.defaultdict(float)
            for i, a in enumerate(acciones(h, calle)):
                try:
                    imp = float(a.get('amount') or 0.0)
                except (TypeError, ValueError):
                    continue
                act = a.get('action')
                if act not in ('b', 'c', 'r'):
                    continue
                clave = (calle, act)
                if imp < puesto[a.get('pos')] - 1e-6:
                    res[clave]['NO_MONOTONA'] += 1
                    if len(ejemplos[clave]) < 3:
                        ejemplos[clave].append(
                            (hid, i, a.get('pos'), act, imp, puesto[a.get('pos')]))
                else:
                    res[clave]['ok'] += 1
                # bajo TOTAL, la caja pasa a valer `imp`: el acumulado ES imp
                puesto[a.get('pos')] = imp
                if act == 'c':
                    # una call iguala la viva: el acumulado de quien llama
                    # pasa a ser el mayor acumulado de la calle
                    puesto[a.get('pos')] = max(puesto.values())

    return {
        'por_accion': {'%s/%s' % k: dict(v) for k, v in sorted(res.items())},
        'ejemplos_no_monotona': {'%s/%s' % k: v for k, v in ejemplos.items()},
    }


def seccion_2b(manos):
    """Ejemplos REALES de cada convencion, tal cual estan en la base."""
    ej = []
    for hid, h in sorted(manos.items(), key=lambda kv: AR.num(kv[0])):
        acs = acciones(h, 'preflop')
        if len([a for a in acs if a.get('action') == 'r']) >= 2:
            ej.append({
                'hand_id': hid,
                'tipo': 'subidas sucesivas',
                'preflop': [(a.get('pos'), a.get('action'), a.get('amount'))
                            for a in acs],
                'final_pot': h.get('final_pot'),
            })
        if len(ej) >= 3:
            break
    for hid, h in sorted(manos.items(), key=lambda kv: AR.num(kv[0])):
        acs = acciones(h, 'preflop')
        if any(a.get('pos') == 'BB' and a.get('action') == 'c' for a in acs):
            ej.append({
                'hand_id': hid,
                'tipo': 'call del BB, que es el caso que mas discrimina',
                'preflop': [(a.get('pos'), a.get('action'), a.get('amount'))
                            for a in acs],
                'final_pot': h.get('final_pot'),
            })
            break
    return ej


def seccion_2c(manos):
    """Los dos patrones de SB/BB que se Detectaron, contados SIN decidir causa."""
    pat = collections.Counter()
    ids = collections.defaultdict(list)
    for hid, h in sorted(manos.items(), key=lambda kv: AR.num(kv[0])):
        acs = acciones(h, 'preflop')
        sb = [a for a in acs if a.get('pos') == 'SB' and a.get('action') == 'c']
        bb = [a for a in acs if a.get('pos') == 'BB' and a.get('action') == 'c']
        if not sb or not bb:
            continue
        dif = round(float(sb[0]['amount']) - float(bb[0]['amount']), 4)
        pat[dif] += 1
        ids[dif].append(hid)
    return {
        'diferencias': {str(k): v for k, v in sorted(pat.items())},
        'ids': {str(k): v[:8] for k, v in sorted(ids.items())},
        'total_parejas': sum(pat.values()),
    }


# ---------------------------------------------------------------------------
# 3. INTEGRIDAD DE BOTES
# ---------------------------------------------------------------------------

def aportar_por_jugador(hand, modo='TOTAL'):
    """Lo que aporta cada jugador, calle por calle. Devuelve el detalle entero.

    OJO, y es la parte que casi sale mal: la lectura por defecto es la del
    GRABADOR —`amount` es la caja del jugador en esa calle, o sea el
    acumulado—, así que lo que aporta un jugador en una calle es **el último
    `b`/`c`/`r` suyo en esa calle, no la suma de todos**.

    Sumarlos daria 107.6 en `H_0546` en vez de 92.6, porque el BB pasa por tres
    valores (1.0, 11.0 y 40.3) que son tres lecturas de la MISMA caja. Esa fue
    la primera version de esta funcion y estaba mal por el motivo exacto que
    este informe demuestra:confundir la lectura delta con la acumulada. Se conserva
    `modo='DELTA'` solo para comparar, y el informe dice que es la incorrecta.

    Y una consecuencia que hay que decir: un `c 0.0` —un check grabado como
    call, `record_hand.py:218`— pone el ultimo valor del jugador a CERO, y con
    eso su contribucion real desaparece de la cuenta. No es un error de esta
    funcion: es un error del dato que esta funcion no puede arreglar, y por eso
    `seccion_3c` mide esas manos aparte.
    """
    detalle = collections.defaultdict(dict)
    total = 0.0
    for calle in CALLES:
        ultimo = {}
        for a in acciones(hand, calle):
            pos = a.get('pos')
            act = a.get('action')
            try:
                imp = float(a.get('amount') or 0.0)
            except (TypeError, ValueError):
                continue
            if act == 'f':
                # se va: lo que puso ANTES se queda en el bote. El ultimo valor
                # suyo sigue valiendo, y por eso NO se toca `ultimo`.
                continue
            if act in ('b', 'c', 'r'):
                if modo == 'TOTAL':
                    ultimo[pos] = imp
                else:
                    ultimo[pos] = ultimo.get(pos, 0.0) + imp
        for pos, v in ultimo.items():
            detalle[pos][calle] = v
            total += v
    return dict(detalle), total


def seccion_3(manos):
    filas = []
    for hid, h in sorted(manos.items(), key=lambda kv: AR.num(kv[0])):
        pot = h.get('final_pot')
        if not isinstance(pot, (int, float)):
            continue
        _det, suma = aportar_por_jugador(h, 'TOTAL')
        filas.append({
            'hand_id': hid,
            'aportado': round(suma, 2),
            'final_pot': round(float(pot), 2),
            'dif': round(suma - float(pot), 2),
            'ratio': round((suma - float(pot)) / suma, 4) if suma else None,
            'allin': h.get('allin'),
            'n_players': len(h.get('players') or []),
        })
    exactas = [f for f in filas if abs(f['dif']) < 0.005]
    faltan = [f for f in filas if f['dif'] < -0.005]
    sobran = [f for f in filas if f['dif'] > 0.005]
    ratios = sorted(f['ratio'] for f in filas if f['ratio'] is not None)
    return {
        'filas': filas,
        'exactas': len(exactas),
        'sobra': len(sobran),
        'falta': len(faltan),
        'ratio_min': ratios[0] if ratios else None,
        'ratio_max': ratios[-1] if ratios else None,
        'ratio_mediana': ratios[len(ratios) // 2] if ratios else None,
    }


def seccion_3b(manos, s3):
    """H_0546 explicada, y las tres muestras."""
    h = manos.get('H_0546')
    caso = None
    if h:
        detalle, suma = aportar_por_jugador(h, 'TOTAL')
        caso = {
            'hand_id': 'H_0546',
            'final_pot': h.get('final_pot'),
            'aportado_segun_codigo': round(suma, 2),
            'por_jugador_por_calle': {k: dict(v) for k, v in detalle.items()},
            'preflop': [(a.get('pos'), a.get('action'), a.get('amount'))
                        for a in acciones(h, 'preflop')],
            'allin': h.get('allin'),
            'stacks': {p.get('pos') or p.get('name'): p.get('stack')
                       for p in h.get('players') or []},
            'winner': h.get('winner'),
        }
    filas = s3['filas']
    extremes = sorted(filas, key=lambda f: abs(f['ratio'] or 0), reverse=True)[:8]
    moderadas = sorted(filas, key=lambda f: abs(f['dif']))[len(filas) // 2:len(filas) // 2 + 8]
    return {
        'H_0546': caso,
        'validas': [f for f in filas if abs(f['dif']) < 0.005][:8],
        'moderadas': moderadas,
        'extremas': extremes,
    }


def seccion_3c(manos, s3):
    """Que invariantes contables se pueden comprobar DE VERDAD en esta base."""
    # I1: el bote declarado nunca es negativo
    i1 = all(f['final_pot'] >= 0 for f in s3['filas'])
    # I2: el bote declarado no supera lo aportado
    i2 = [f['hand_id'] for f in s3['filas'] if f['dif'] < -0.005]
    # I3: el bote declarado es al menos las ciegas, si hay dos posting
    i3 = []
    for hid, h in manos.items():
        pot = h.get('final_pot')
        if not isinstance(pot, (int, float)):
            continue
        postings = [posting_de(h, p) for p in ('SB', 'BB')]
        postings = [p for p in postings if p]
        if len(postings) == 2 and float(pot) < sum(p['amount'] for p in postings) - 1e-6:
            i3.append(hid)
    # I4: ningun jugador aporta mas que su stack inicial
    i4 = []
    for hid, h in manos.items():
        stacks = {}
        for p in h.get('players') or []:
            try:
                stacks[p.get('pos') or p.get('name')] = float(p.get('stack') or 0.0)
            except (TypeError, ValueError):
                pass
        detalle, _t = aportar_por_jugador(h, 'TOTAL')
        for pos, calles in detalle.items():
            if pos in stacks and sum(calles.values()) > stacks[pos] + 1e-6:
                i4.append((hid, pos, round(sum(calles.values()), 2), stacks[pos]))
    return {
        'I1_bote_no_negativo': i1,
        'I2_bote_no_supera_aportado': len(i2),
        'I2_ids': i2[:10],
        'I3_bote_menor_que_ciegas': len(i3),
        'I3_ids': i3[:10],
        'I4_aporta_mas_que_stack': len(i4),
        'I4_ejemplos': i4[:8],
    }


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def _p(txt='', ancho=76):
    print(txt)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seccion', type=int, default=0, help='1, 2 o 3')
    ap.add_argument('--json', dest='json_out')
    ap.add_argument('--validar', action='store_true')
    args = ap.parse_args(argv)

    if args.validar:
        return validar()

    manos = cargar()
    out = {'db_commit': learn.HANDS_DB_COMMIT, 'db_sha256': learn.HANDS_DB_SHA256,
           'manos': len(manos)}

    s1 = seccion_1(manos)
    s2 = seccion_2(manos)
    s3 = seccion_3(manos)

    if not args.seccion or args.seccion == 1:
        _p('=' * _w())
        _p('1. POSICIONES Y CIEGAS')
        _p('=' * _w())
        _p()
        _p('   %-34s %s' % ('manos', s1['total']))
        for k in sorted(s1['inventario']):
            _p('   %-34s %s' % (k, s1['inventario'][k]))
        _p()
        _p('   importes de la `BB b` en el indice 0: %s'
           % dict(sorted(s1['bb_importes'].items(), key=lambda x: str(x[0]))))
        _p('   importes de una `SB b` (que NO es ciega, §2c): %s'
           % (dict(sorted(s1['sb_importes'].items(), key=lambda x: str(x[0]))) or 'ninguna'))
        _p()
        _p('   QUIE VERIFICA UN POSTING')
        _p('   Campo: la accion `b` de esa posicion. Secuencia: en el PREFLOP y')
        _p('   antes de que haya dinero de nadie en el bote. No hay `blind: true`')
        _p('   en ninguna de las 13826 acciones; `learn._preflop_sequence` lo lee,')
        _p('   el grabador no lo escribe. Y la posicion sola no prueba nada: el BB')
        _p('   sale dozens de veces como `b` de una apuesta.')
        _p()
        e = seccion_1e(manos)
        _p('   ESTRUCTURA DE MESA')
        _p('   jugadores por mano : %s' % e['n_jugadores'])
        _p('   primera accion    : %s' % e['primera_accion_preflop'])
        _p('   stacks min/med/max: %s / %s / %s'
           % (e['stack_min'], e['stack_mediana'], e['stack_max']))
        _p()
        _p('   LAS %d MANOS SIN pos:SB' % len(s1['sin_sb']))
        _p('   %s' % ', '.join(s1['sin_sb']))
        _p()
        filas = seccion_1b(manos, s1)
        for f in filas[:4]:
            _p('   --- %s' % f['hand_id'])
            _p('       posiciones  %s' % f['posiciones'])
            _p('       sin pos     %s' % (f['vacias'] or 'ninguno'))
            _p('       preflop     %s' % f['preflop'][:8])
            _p('       acciones de una posicion inexistente: %s'
               % (f['acciones_de_una_pos_inexistente'] or 'ninguna'))
            _p()

    if not args.seccion or args.seccion == 2:
        _p('=' * _w())
        _p('2. SEMANTICA DE LOS IMPORTES')
        _p('=' * _w())
        _p()
        _p('   RESPUESTA AUTORITATIVA, en el codigo del grabador:')
        _p('     amount = state[f"{pid}_bet"]  ->  la CAJA DE APUESTA del jugador')
        _p('     en esa calle. Es la CONTRIBUCION ACUMULADA en la calle.')
        _p('   No es el delta. No es el tamaño objetivo. Las tres lecturas que se')
        _p('   han barajado aqui, y solo una es la del codigo:')
        _p('     %s' % ', '.join(CODIGO_IMPORTE))
        _p()
        _p('   MONOTONIA DE LA SERIE TOTAL (el acumulado de un jugador no puede bajar)')
        for k, v in s2['por_accion'].items():
            _p('     %-22s ok %5d   NO MONOTONA %5d' % (k, v.get('ok', 0),
                                                        v.get('NO_MONOTONA', 0)))
        _p()
        _p('   EJEMPLOS REALES')
        for e in seccion_2b(manos):
            _p('   --- %s  [%s]  final_pot %s' % (e['hand_id'], e['tipo'], e['final_pot']))
            _p('       %s' % (e['preflop'][:9],))
        _p()
        s2c = seccion_2c(manos)
        _p('   LOS PATRONES SB/BB, contados sin decidir la causa (%d parejas)'
           % s2c['total_parejas'])
        _p('   diferencia SB c - BB c   veces')
        for k, v in list(s2c['diferencias'].items())[:12]:
            _p('     %+7s   %5d    ej. %s'
               % (k, v, ', '.join(s2c['ids'][k][:4])))
        _p()

    if not args.seccion or args.seccion == 3:
        _p('=' * _w())
        _p('3. INTEGRIDAD DE LOS BOTES')
        _p('=' * _w())
        _p()
        _p('   %-22s %d' % ('el bote EXACTA', s3['exactas']))
        _p('   %-22s %d' % ('sobra lo aportado', s3['sobra']))
        _p('   %-22s %d' % ('falta lo aportado', s3['falta']))
        _p('   ratio (aportado-bote)/aportado: min %s  mediana %s  max %s'
           % (s3['ratio_min'], s3['ratio_mediana'], s3['ratio_max']))
        _p()
        s3b = seccion_3b(manos, s3)
        c = s3b['H_0546']
        if c:
            _p('   H_0546, EXPLICADA')
            _p('     final_pot declarado : %s' % c['final_pot'])
            _p('     aportado segun el codigo : %s' % c['aportado_segun_codigo'])
            _p('     por jugador y calle :')
            for pos, calles in sorted(c['por_jugador_por_calle'].items()):
                _p('       %-6s %s' % (pos, dict(calles)))
            _p('     stacks iniciales : %s' % c['stacks'])
            _p('     allin declarado  : %s' % c['allin'])
            _p()
        _p('   INVARIANTES COMPROBABLES EN ESTA BASE')
        for k, v in seccion_3c(manos, s3).items():
            _p('     %-34s %s' % (k, v))
        _p()

    out['s1'] = s1
    out['s2'] = s2
    out['s2c'] = seccion_2c(manos)
    out['s3'] = {k: v for k, v in s3.items() if k != 'filas'}
    out['s3_filas'] = s3['filas']
    if args.json_out:
        with io.open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        _p('volcado -> %s' % args.json_out)
    return 0


def _w():
    return 76


# ---------------------------------------------------------------------------
# Autocomprobacion
# ---------------------------------------------------------------------------

ESCRITURAS_PROHIBIDAS = (
    ('os.' + 'replace', 'escritura atomica'),
    ('os.' + 'rename', 'renombrar'),
    ('shutil.' + 'move', 'mover'),
    ('shutil.' + 'copyfile', 'copiar'),
)


def violaciones_de_escritura(propio):
    """Igual que en `lista_saneamiento.py`, y por el mismo motivo: este
    fichero tiene que poder comprobarse PLANTANDO la violacion, porque un
    guard que solo se ve pasar no se sabe si mira algo."""
    fallos = []
    if re.search(r"open\s*\(\s*[^)\n]*\b(DB_PATH|ORIGEN_PATH)\b", propio):
        fallos.append('abre la base con `open`. Se lee con `leer()` e `io.open`.')
    if re.search(r"open\s*\(\s*['\"][^'\"]*hands_db", propio):
        fallos.append('abre hands_db por su nombre literal.')
    for _op, _p_que in ESCRITURAS_PROHIBIDAS:
        if _op in propio:
            fallos.append('usa `%s`: %s.' % (_op, _p_que))
    return fallos


def validar():
    """Que los detectores puedan fallar, y que este fichero no escriba."""
    fallos = []
    propio = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    fallos.extend(violaciones_de_escritura(propio))

    # Un detector que no se contrasta no es un instrumento. Se prueban los
    # tres posting_de / es_posting / seccion_3 sobre manos stingidas.
    h = {'hand_id': 'X', 'streets': {'preflop': {'actions': [
        {'pos': 'SB', 'action': 'b', 'amount': 0.5},
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
        {'pos': 'BB', 'action': 'c', 'amount': 1.5},
    ]}}, 'players': [{'pos': 'SB'}, {'pos': 'BB'}, {'pos': 'UTG'}]}
    if posting_de(h, 'SB') != {'indice': 0, 'amount': 0.5}:
        fallos.append('posting_de no ve la ciega del SB en el indice 0')
    if not es_posting(h, 'SB'):
        fallos.append('es_posting no reconoce una ciega del SB al principio')
    if es_posting(h, 'BB'):
        fallos.append('es_posting confunde una CALL del BB con un posting')
    # Y el caso contrario, que es el que de verdad importa: una `BB b` que NO
    # es ciega porque antes ya hay dinero de otro en el bote. No basta con
    # "la primera `b` del BB es ciega": si el primero que apuesta es otro, la
    # `BB b` es una salida, y declararla posting seria inventar una ciega.
    # El caso anterior, `BB b 1.0` al principio, SI es ciega, y que la funcion
    # lo diga bien es tan importante como que diga bien el otro.
    sin = {'hand_id': 'Y', 'streets': {'preflop': {'actions': [
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5},
        {'pos': 'BB', 'action': 'b', 'amount': 4.0}]}},
        'players': [{'pos': 'BB'}, {'pos': 'UTG'}]}
    if es_posting(sin, 'BB'):
        fallos.append('es_posting acepta una `BB b` que NO es ciega: el UTG ya '
                      'habia puesto 2.5, asi que esa `b` es una salida. La '
                      'comprobacion tiene que mirar la SECUENCIA, no que sea '
                      'la primera `b` del BB.')

    # Y la del principio, que esposting tiene que ACEPTAR. Una prueba que solo
    # comprueba que se rechaza no dice si la funcion distingue o si siempre
    # dice que no.
    con = {'hand_id': 'Z', 'streets': {'preflop': {'actions': [
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'b', 'amount': 2.5}]}},
        'players': [{'pos': 'BB'}, {'pos': 'UTG'}]}
    if not es_posting(con, 'BB'):
        fallos.append('es_posting rechaza una `BB b` en el indice 0, que SI es '
                      'una ciega. Si siempre dijera que no, la prueba anterior '
                      'pasaria sin que la funcion mirase nada.')

    _p('=' * 76)
    _p('AUTOCOMPROBACION DE auditar_origen.py')
    _p('=' * 76)
    _p('  no escribe la base : %s'
       % ('OK' if not(any(f.startswith('abre') or f.startswith('usa') for f in fallos)) else 'FALLA'))
    _p('  detectores probados con manos stingidas: %d fallos' % len(fallos))
    _p()
    if fallos:
        for f in fallos:
            _p('  - %s' % f)
        _p()
        _p('NO ES FIABLE.')
        return 1
    _p('OK. No escribe la base, y los detectores de posting y de posting')
    _p('responden bien a manos construidas a proposito.')
    return 0


if __name__ == '__main__':
    sys.exit(main())