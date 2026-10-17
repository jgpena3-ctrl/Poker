# -*- coding: utf-8 -*-
"""Diagnostico del grabador: apuesta viva, calls corto, repeticiones.

    python tools/diagnostico_grabador.py
    python tools/diagnostico_grabador.py --json salida.json
    python tools/diagnostico_grabador.py --validar

QUE ES Y POR QUE EXISTE
-----------------------
La revision tecnica dio «503 de 13826 acciones son calls que no llegan a la
apuesta viva». Esa cifra la calculo un script suelto, NO `auditar_origen.py`, y
eso ya es un problema metodologico: una cifra que no sale del instrumento
auditado no es reproducible por el instrumento. Este modulo lo arregla: la
apuesta viva se define aqui, con las reglas escritas, y el numero sale de aqui.

ADEMAS, y esto importa mas: `seccion_2` de `auditar_orango.py` NO calculates
apuesta viva. Lleva `puesto[pos]` —la caja de cada jugador— y su «no monotona»
compara esa caja consigo misma. Es otra propiedad distinta, y ahora estan las
dos con nombre.

LAS REGLAS DE LA APUESTA VIVA
-----------------------------
La semantica de `amount` la fija `recorder/record_hand.py`: es la CAJA del
jugador en esa calle (`state[f'{pid}_bet']`). Por tanto:

    viva de la calle = el maximo de cajas visto hasta ahora

Y cada accion hace:

    b   amount >= viva   (es una apuesta: iguala o supera)   viva <- amount
    r   amount >  viva   (es una subida)                    viva <- amount
    c   amount == viva   (iguala)                           viva no cambia
    x   amount == 0      (check)                            viva no cambia
    f   amount == 0      (se va)                            viva no cambia

La viva se REINICIA a 0 en cada calle: el recorder hace
`self.street_bet = {p: None}` y `self.street_has_bet = False` en
`record_hand.py:316-317`, y la caja de la UI tambien se reinicia. Mezclar
calles seria sumar cricket y golf.

LO QUE ESTE MODULO NO HACE
--------------------------
No atribuye causa. Una call por debajo de la viva es una ANOMALIA OBSERVADA:
puede ser una lectura obsoleta, un all-in corto, un redondeo del OCR, una
apuesta no observada, o un orden de captura. Aqui se separa cada caso por
evidencia, pero no se le pone nombre.

Tampoco corrige el importe. Ni lo sustituye por la viva: hacer eso convertiria
una hipotesis en un dato, que es justo lo que hay que evitar.
"""
import argparse
import collections
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn  # noqa: E402
from auditar_origen import CALLES, acciones, cargar, posting_de, posiciones  # noqa

EPS = 1e-6

# Los cortes de diferencia. Separar el redondeo del resto es el punto: una
# diferencia de 0.1 y una de 8.0 no son el mismo defecto, y mezclarlas en un
# solo numero las hace parecer la misma cosa.
CORTES = (
    ('redondeo   (<=0.15)', 0.15),
    ('pequena    (0.15-0.5)', 0.5),
    ('media      (0.5-2.0)', 2.0),
    ('grande     (>2.0)', float('inf')),
)


def apuesta_viva(hand, calle):
    """La apuesta viva de una calle, con la regla escrita mas arriba.

    Devuelve una lista de eventos con el estado de la viva ANTES de cada accion,
    que es lo que hace falta para diagnosticar: saber que se esperaba, no solo
    que paso.
    """
    viva = 0.0
    eventos = []
    for i, a in enumerate(acciones(hand, calle)):
        act = a.get('action')
        try:
            imp = float(a.get('amount') or 0.0)
        except (TypeError, ValueError):
            continue
        eventos.append({'i': i, 'pos': a.get('pos'), 'action': act,
                        'amount': imp, 'viva_antes': viva})
        if act in ('b', 'r'):
            viva = max(viva, imp)
        # c, x y f no mueven la viva
    return eventos, viva


def stacks_de(hand):
    out = {}
    for p in hand.get('players') or []:
        pos = p.get('pos')
        if not pos:
            continue
        try:
            out[pos] = float(p.get('stack') or 0.0)
        except (TypeError, ValueError):
            out[pos] = None
    return out


def calls_por_debajo(hand):
    """Las calls cuya caja no llega a la viva, con todo el contexto.

    NO atribuye causa. Rellena los HECHOS que permiten atribuirlas despues:
    cuanto falta, si el jugador ya habia acted antes, si tiene acciones
    despues, si su importe iguala su stack, y si hay un `c 0.0` —que el
    grabador produce cuando traduce un check (`record_hand.py:218`,
    `'pasar': 'c'`)—.
    """
    stacks = stacks_de(hand)
    out = []
    for calle in CALLES:
        acs = acciones(hand, calle)
        eventos, _v = apuesta_viva(hand, calle)
        # indice -> (pos, accion, veces que aparece ese jugador antes/despues)
        for k, ev in enumerate(eventos):
            if ev['action'] != 'c':
                continue
            viva = ev['viva_antes']
            if viva <= EPS or ev['amount'] >= viva - EPS:
                continue
            pos = ev['pos']
            antes = [x for x in acs[:ev['i']]
                     if x.get('pos') == pos and x.get('action') in ('b', 'c', 'r')]
            despues = [x for x in acs[ev['i'] + 1:]
                       if x.get('pos') == pos and x.get('action') in ('b', 'c', 'r')]
            st = stacks.get(pos)
            falta = round(viva - ev['amount'], 4)
            out.append({
                'hand_id': hand.get('hand_id'),
                'calle': calle,
                'indice': ev['i'],
                'pos': pos,
                'action': ev['action'],
                'amount': ev['amount'],
                'viva': round(viva, 4),
                'falta': falta,
                'caja_previa_misma_calle': antes[-1]['amount'] if antes else None,
                'acciones_previas_mismo_jugador': len(antes),
                'acciones_posteriores': len(despues),
                'stack': st,
                'iguala_stack': (st is not None
                                 and abs(ev['amount'] - st) <= 0.05),
                'es_cero': ev['amount'] <= EPS,
                'accion_anterior': (
                    '%s %s %s' % (acs[ev['i'] - 1].get('pos'),
                                  acs[ev['i'] - 1].get('action'),
                                  acs[ev['i'] - 1].get('amount'))
                    if ev['i'] > 0 else None),
                'allin_declarado': hand.get('allin') or [],
            })
    return out


def corte_de(falta):
    for etiqueta, limite in CORTES:
        if falta <= limite + EPS:
            return etiqueta
    return CORTES[-1][0]


# ---------------------------------------------------------------------------
# Repeticiones
# ---------------------------------------------------------------------------

def repeticiones(hand):
    """Acciones (pos, accion, importe) que aparecen mas de una vez en una calle.

    NO las llama duplicados. Una repeticion es compatible con tres cosas que el
    esquema no distingue:

      1. el jugador actuo dos veces y su caja coincidio (improbable pero posible)
      2. el grabador emitio dos veces por el fallback de estado
         (`record_hand.py:256-285`, que emite para un jugador NO detectado en
         el primer bucle)
      3. la caja se leyo antes de actualizarse

    Lo que se devuelve es la SECUENCIA, para que se vea cual de las tres encaja
    en cada caso.
    """
    out = []
    for calle in CALLES:
        acs = acciones(hand, calle)
        grupos = collections.defaultdict(list)
        for i, a in enumerate(acs):
            grupos[(a.get('pos'), a.get('action'), a.get('amount'))].append(i)
        for clave, indices in grupos.items():
            if len(indices) > 1:
                entre = acs[indices[0] + 1:indices[1]]
                out.append({
                    'hand_id': hand.get('hand_id'),
                    'calle': calle,
                    'clave': list(clave),
                    'indices': indices,
                    'consecutiva': (indices[1] == indices[0] + 1),
                    'entre_acciones': [
                        '%s %s %s' % (x.get('pos'), x.get('action'),
                                      x.get('amount')) for x in entre],
                    'mismo_jugador_entre_medio': any(
                        x.get('pos') == clave[0] for x in entre),
                    'viva_entre': [
                        e['viva_antes'] for e in apuesta_viva(hand, calle)[0]
                        if indices[0] < e['i'] < indices[1]],
                })
    return out


# ---------------------------------------------------------------------------
# Clasificacion de la aportacion
# ---------------------------------------------------------------------------

CALCULABLE = 'CALCULABLE'
SOSPECHOSA = 'SOSPECHOSA'
INDETERMINADA = 'INDETERMINADA'


def clasificar_aportado(hand):
    """Para cada accion con dinero, si su aportación es calculable.

    Devuelve (resultado, importe_calculado, motivo). `importe_calculado` es
    None cuando el resultado no es CALCULABLE — y eso es deliberado: devolver
    0 seria afirmar que el jugador no puso nada, que es otra cosa distinta de
    «no se puede saber».

    REGLAS, y el por que de cada una:

    CALCULABLE
        No hay ninguna de las condiciones de sospecha. La caja es coherente con
        la viva y con lo que el jugador ya habia puesto en la calle.

    SOSPECHOSA
        El calculo se puede hacer, pero depende de una lectura o una secuencia
        anomala. Se devuelve el importe CON SU ORIGEN, marcada la sospecha.

    INDETERMINADA
        Faltan las referencias necesarias: no se puede saber cuanto puso el
        jugador en esa accion.

    Y una regla NEGATIVA que importa mas de lo que parece:

        Que una call alcance la viva NO basta para declararla calculable. La
        reaching-viva es NECESARIA pero no SUFICIENTE, porque una lectura
        obsoleta puede por casualidad alcanzar la viva, y porque un jugador
        puede tener una caja que cuadra y aun asi haber acted cuando la caja
        ya habia cambiado.
        Del mismo modo, que no haya accion previa NO basta: puede no haberla
        porque la captura la perdio.
    """
    resultado = []
    stacks = stacks_de(hand)
    for calle in CALLES:
        acs = acciones(hand, calle)
        caja_previa = {}
        # Una pasada previa para detectar acciones repetidas de este jugador.
        #
        # [DEFECTO CORREGIDO] Antes se calculaba tambien
        #   repetidas = {(r['calle'], tuple(r['clave'])) for r in repeticiones(hand)}
        # y NO SE USABA. Es decir, `clasificar_aportado` llamaba a
        # `repeticiones()`, pagaba el coste, y luego repetia la deteccion con
        # su propio `vistos`. Dos detecciones paralelas de lo mismo, una
        # muerta, que pueden divergir sin que nada lo note.
        #
        # Ahora hay UNA sola deteccion, la de `vistos`, que queda indicada
        # abajo. La consequence que queda es que `repeticiones()` —que si
        # aporta la secuencia y la viva entre las repeticiones— no se usa
        # aqui. Es una limitacion, no un error: `clasificar_aportado` no
        # necesita la secuencia, solo la cuenta.
        vistos = collections.Counter(
            (a.get('pos'), a.get('action'), a.get('amount')) for a in acs
            if a.get('action') in ('b', 'c', 'r'))
        # la viva ANTES de cada accion, que es lo que hace falta para
        # decir «esperaba X y llego Y»
        eventos, _v = apuesta_viva(hand, calle)
        viva_por_indice = {e['i']: e['viva_antes'] for e in eventos}

        for i, a in enumerate(acs):
            act = a.get('action')
            if act not in ('b', 'c', 'r'):
                continue
            try:
                imp = float(a.get('amount') or 0.0)
            except (TypeError, ValueError):
                resultado.append({'indice': i, 'calle': calle, 'pos': a.get('pos'),
                                  'action': act, 'importe': None,
                                  'resultado': INDETERMINADA,
                                  'motivo': 'importe ilegible'})
                continue
            pos = a.get('pos')
            previa = caja_previa.get(pos)
            viva = viva_por_indice.get(i, 0.0)
            sospecha = []

            if imp <= EPS:
                sospecha.append('c 0.0: el grabador traduce un check a call '
                                "(record_hand.py:218, 'pasar': 'c')")
            if vistos[(pos, act, a.get('amount'))] > 1:
                sospecha.append('accion repetida en la misma calle')
            if act == 'c' and viva > EPS and imp < viva - 0.15:
                sospecha.append('no alcanza la viva (%.1f vs %.1f)' % (imp, viva))
            elif act == 'c' and viva > EPS and imp > viva + 0.15:
                # Una call que SUPERA la viva también es anómala: una call
                # cubre, no pasa. Y es el mismo defecto de lectura que el
                # otro lado, mirado al revés: si el importe cabe con la
                # vigente y no con la anterior, la caja se leyó antes de
                # actualizarse. Se lo cazó `test_alcanzar_la_viva_no_basta`.
                sospecha.append('supera la viva (%.1f vs %.1f)' % (imp, viva))
            if previa is not None and imp < previa - EPS:
                sospecha.append('la caja BAJA respecto a la anterior del mismo '
                                'jugador en la calle (%.1f -> %.1f)'
                                % (previa, imp))
            st = stacks.get(pos)
            if st is not None and imp > st + EPS:
                sospecha.append('supera su stack (%.1f > %.1f)' % (imp, st))
            todo_allin = (st is not None and st > EPS
                          and abs(imp - st) <= 0.05)

            caja_previa[pos] = imp

            calculado = (imp - previa) if previa is not None else imp

            if todo_allin:
                # Una all-in CORTA es una jugada legitima: el jugador se fue
                # con lo que tenia. Su caja no llega a la viva porque no
                # pudo, y eso no es una lectura mala.
                #
                # Y el dato trae la evidencia: `imp == stack`. Sin esta
                # rama, una all-in corta salia INDETERMINADA, que es FALSO:
                # el importe SI se sabe, es el stack.
                #
                # Lo caza `test_un_allin_corto_no_se_declara_sospechoso`.
                res = CALCULABLE
                motivo = ('all-in corta: la caja es exactamente su stack, '
                          'que es evidencia suficiente')
            elif not sospecha:
                res = CALCULABLE
                motivo = 'caja coherente'
            elif previa is None and imp > EPS:
                # sin referencia anterior solo se puede calcular si la caja
                # cuadra con la viva: si no, hay algo antes que no se capturo
                if act == 'c' and viva > EPS and abs(imp - viva) > 0.15:
                    res = INDETERMINADA
                    motivo = ('sin accion previa del jugador y no llega a la '
                              'viva: no se puede saber si falta una captura')
                else:
                    res = SOSPECHOSA
                    motivo = '; '.join(sospecha)
            else:
                res = SOSPECHOSA
                motivo = '; '.join(sospecha)

            resultado.append({
                'indice': i, 'calle': calle, 'pos': pos, 'action': act,
                'importe': imp,
                'aportado': calculado if res != INDETERMINADA else None,
                'resultado': res, 'motivo': motivo,
            })
    return resultado


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def analizar():
    manos = cargar()
    calls = []
    reps = []
    por_clase = collections.Counter()
    por_corte = collections.Counter()
    por_pos = collections.Counter()
    por_calle_c = collections.Counter()
    llamadas_totales = 0

    for h in manos.values():
        c = calls_por_debajo(h)
        calls.extend(c)
        reps.extend(repeticiones(h))
        for calle in CALLES:
            for a in acciones(h, calle):
                if a.get('action') == 'c':
                    llamadas_totales += 1
        for x in c:
            por_calle_c[x['calle']] += 1
            por_corte[corte_de(x['falta'])] += 1
            por_pos[x['pos']] += 1
            if x['es_cero']:
                por_clase['c 0.0 (check traducido)'] += 1
            if x['iguala_stack']:
                por_clase['iguala su stack (all-in corto posible)'] += 1
            if x['acciones_previas_mismo_jugador'] > 0:
                por_clase['tiene accion previa del mismo jugador'] += 1
            if x['acciones_posteriores'] > 0:
                por_clase['tiene acciones posteriores'] += 1
            if x['stack'] is None:
                por_clase['pos sin stack (no evaluable)'] += 1

    return {
        'manos': len(manos),
        'llamadas_totales': llamadas_totales,
        'calls_por_debajo': len(calls),
        'calls': calls,
        'por_calle': dict(por_calle_c),
        'por_corte': dict(por_corte),
        'por_pos': dict(por_pos),
        'rasgos': dict(por_clase),
        'repeticiones': reps,
        'repeticiones_claves': len(reps),
        'repeticiones_pares': len({(r['hand_id'], r['calle']) for r in reps}),
        'repeticiones_consecutivas': sum(1 for r in reps if r['consecutiva']),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json', dest='json_out')
    ap.add_argument('--validar', action='store_true')
    args = ap.parse_args(argv)

    if args.validar:
        return validar()

    r = analizar()
    print('=' * 76)
    print('DIAGNOSTICO DEL GRABADOR')
    print('=' * 76)
    print()
    print('   manos                    %d' % r['manos'])
    print('   calls examinadas         %d' % r['llamadas_totales'])
    print('   calls por debajo de viva %d  (%.1f%% de las calls)'
          % (r['calls_por_debajo'],
             100.0 * r['calls_por_debajo'] / max(1, r['llamadas_totales'])))
    print()
    print('   POR CALLE')
    for k in CALLES:
        if k in r['por_calle']:
            print('      %-9s %4d' % (k, r['por_calle'][k]))
    print()
    print('   POR CANTIDAD QUE FALTA')
    for etiqueta, _l in CORTES:
        if etiqueta in r['por_corte']:
            print('      %-22s %4d' % (etiqueta, r['por_corte'][etiqueta]))
    print()
    print('   POR POSICION')
    for k, v in sorted(r['por_pos'].items(), key=lambda x: -x[1]):
        print('      %-6s %4d' % (k, v))
    print()
    print('   RASGOS (un caso puede tener varios)')
    for k, v in sorted(r['rasgos'].items(), key=lambda x: -x[1]):
        print('      %-42s %4d' % (k, v))
    print()
    print('   REPeticiones')
    print('      claves repetidas        %d' % r['repeticiones_claves'])
    print('      pares (mano, calle)     %d' % r['repeticiones_pares'])
    print('      consecutivas            %d' % r['repeticiones_consecutivas'])
    consec = [x for x in r['repeticiones'] if x['consecutiva']]
    medio = [x for x in r['repeticiones']
             if not x['consecutiva'] and x['mismo_jugador_entre_medio']]
    print('      con el MISMO jugador en medio: %d' % len(medio))
    print()
    print('   LAS 10 CON MAS FALTA')
    for c in sorted(r['calls'], key=lambda x: -x['falta'])[:10]:
        print('      %-8s %-8s[%d] %-4s c %7.1f  viva %7.1f  falta %6.1f  '
              'stack %s  previa %s'
              % (c['hand_id'], c['calle'], c['indice'], c['pos'], c['amount'],
                 c['viva'], c['falta'], c['stack'],
                 c['acciones_previas_mismo_jugador']))
    print()

    if args.json_out:
        with io.open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump(r, f, indent=2, ensure_ascii=False, default=str)
        print('volcado -> %s' % args.json_out)
    return 0


# ---------------------------------------------------------------------------
# Autocomprobacion: los detectores tienen que poder FALLAR
# ---------------------------------------------------------------------------

def _mano(acciones_preflop, stacks=None):
    """Una mano minima para probar el diagnostico."""
    jugs = [{'pos': p, 'stack': (stacks or {}).get(p, 100.0), 'active': True,
             'name': p, 'cards': ''}
            for p in {a['pos'] for a in acciones_preflop if a.get('pos')}]
    return {'hand_id': 'T', 'streets': {
        'preflop': {'actions': acciones_preflop, 'board': []},
        'flop': {'actions': [], 'board': []},
        'turn': {'actions': [], 'board': []},
        'river': {'actions': [], 'board': []}},
        'players': jugs, 'allin': [], 'final_pot': 0.0}


def validar():
    fallos = []

    # la apuesta viva sube con b y r, y no con c, x ni f
    h = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
               {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
               {'pos': 'CO', 'action': 'c', 'amount': 3.0},
               {'pos': 'CO', 'action': 'x', 'amount': 0.0},
               {'pos': 'BTN', 'action': 'f', 'amount': 0.0}])
    ev, final = apuesta_viva(h, 'preflop')
    vivas = [e['viva_antes'] for e in ev]
    if vivas != [0.0, 1.0, 3.0, 3.0, 3.0]:
        fallos.append('la apuesta viva no evoluciona bien: %s' % vivas)
    if final != 3.0:
        fallos.append('la viva final deberia ser 3.0, es %s' % final)

    # una call que llega a la viva NO se reporta
    if calls_por_debajo(h):
        fallos.append('una call que alcanza la viva se reporta como corta')

    # una call que no llega, SÍ, y con la diferencia bien calculada
    h2 = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
                {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
                {'pos': 'CO', 'action': 'c', 'amount': 1.0}])
    cc = calls_por_debajo(h2)
    if len(cc) != 1 or abs(cc[0]['falta'] - 2.0) > EPS:
        fallos.append('no detecta la call corta, o calcula mal la falta: %s' % cc)
    if cc[0]['es_cero']:
        fallos.append('marca como c 0.0 una call de 1.0')

    # un c 0.0 con la viva viva SÍ se marca como posible check traducido
    h2b = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
                 {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
                 {'pos': 'CO', 'action': 'c', 'amount': 0.0}])
    cb = calls_por_debajo(h2b)
    if len(cb) != 1 or not cb[0]['es_cero']:
        fallos.append('no marca el c 0.0 como posible check traducido')

    # la repeticion se detecta, y se ve lo que hay EN MEDIO
    h3 = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
                {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
                {'pos': 'CO', 'action': 'f', 'amount': 0.0},
                {'pos': 'UTG', 'action': 'c', 'amount': 1.0}])
    rr = repeticiones(h3)
    if len(rr) != 1:
        fallos.append('no detecta la repeticion')
    elif rr[0]['consecutiva']:
        fallos.append('dice que la repeticion es consecutiva y hay un CO entre')
    elif rr[0]['mismo_jugador_entre_medio']:
        fallos.append('dice que el mismo jugador esta en medio y es un CO')

    # Y el caso REAL, que es el de H_0039: la repeticion separada por la subida de
    # OTRO jugador, y la segunda call no llega a la viva.
    #
    # `mismo_jugador_entre_medio` casi nunca es cierto, y con razon: para que un
    # jugador repitiese su propia caja tendria que haber actuation entre medias
    # con el mismo importe, lo que no ocurre. El campo se queda por si aparece,
    # pero la firma que de verdad importa es la de H_0039.
    h4 = _mano([{'pos': 'BB', 'action': 'b', 'amount': 1.0},
                {'pos': 'UTG', 'action': 'c', 'amount': 1.0},
                {'pos': 'SB', 'action': 'r', 'amount': 5.0},
                {'pos': 'UTG', 'action': 'c', 'amount': 1.0}])
    r4 = repeticiones(h4)
    if len(r4) != 1:
        fallos.append('no detecta la repeticion separada por una subida')
    else:
        if r4[0]['consecutiva']:
            fallos.append('la llama consecutiva cuando hay una subida en medio')
        if r4[0]['mismo_jugador_entre_medio']:
            fallos.append('dice que el mismo jugador esta en medio, y es la SB')
        # y la segunda call queda por debajo de la viva de 5.0
        cc4 = calls_por_debajo(h4)
        if not any(x['indice'] == 3 and abs(x['falta'] - 4.0) < EPS
                   for x in cc4):
            fallos.append('la segunda call repetida no sale como corta: %s' % cc4)

    # la clasificacion: una call coherente es CALCULABLE, una corta no
    res_ok = clasificar_aportado(_mano([
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
        {'pos': 'CO', 'action': 'c', 'amount': 3.0}]))
    if any(x['resultado'] != CALCULABLE for x in res_ok):
        fallos.append('una secuencia coherente no es CALCULABLE: %s' % res_ok)
    res_mal = clasificar_aportado(_mano([
        {'pos': 'BB', 'action': 'b', 'amount': 1.0},
        {'pos': 'UTG', 'action': 'r', 'amount': 3.0},
        {'pos': 'CO', 'action': 'c', 'amount': 1.0}]))
    if not any(x['resultado'] != CALCULABLE for x in res_mal):
        fallos.append('una call que no llega a la viva sale CALCULABLE')
    if any(x['aportado'] is None and x['resultado'] == INDETERMINADA
           for x in res_mal) is False:
        fallos.append('la call corta sin previa deberia ser INDETERMINADA')

    print('=' * 74)
    print('AUTOCOMPROBACION DE diagnostico_grabador.py')
    print('=' * 74)
    print()
    if fallos:
        for f in fallos:
            print('  - %s' % f)
        print()
        print('NO ES FIABLE.')
        return 1
    print('OK. La apuesta viva evoluciona como dice la regla, la call que llega')
    print('no se reporta, la que no llega si, y la repeticion se ve.')
    return 0


if __name__ == '__main__':
    sys.exit(main())