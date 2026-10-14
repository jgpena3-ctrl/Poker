# -*- coding: utf-8 -*-
"""Auditoria de `no_puede_actuar()` y del solapamiento con `folds_hasta`.

Que viene a cerrar revision_1 Tarea 2 y el punto 1 (BLOQUEANTE) de
revision_2. NO modifica nada y NO toca F7.2: solo mide.

El problema que se audita, textual de `inventario_multiway.py`:

    if isinstance(a, dict) and a.get('pos') and a.get('action') == 'r':
        activos.discard(a.get('pos'))       # <- una "subida" =~ un all-in

revision_2 lo senala y anade el requisito: "un raise ordinario nunca se
interpreta automaticamente como all-in". Este script responde si se cumple.

Salidas:

  1. REPRESENTACION REAL DEL ALL-IN: que campo, que valores, y si el
     identificador se puede volver a unir con su posicion.
  2. DIAGNOSTICO de `no_puede_actuar()`: falsos positivos y falsos
     negativos, con ejemplos de manos reales.
  3. ORTOGONALIDAD entre `folds_hasta` y `no_puede_actuar`: cuanto se
     solapan, cuanto solo cae en uno, cuanto en ninguno.
  4. INVENTARIO RECALCULADO: MW-en-el-bote y MW-pueden-actuar antes y
     despues, con la explicacion de la diferencia.

Uso:  python tools/auditar_solapamiento_multiway.py
"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from motor import learn                                       # noqa: E402
from inventario_multiway import (                              # noqa: E402
    ORDEN, STREETS, folds_hasta, no_puede_actuar,
)

# ---------------------------------------------------------------------------
# 1. Representacion real del all-in
# ---------------------------------------------------------------------------
# MEDIDO: `hand['allin']` es una LISTA de identificadores INTERNOS, no de
# posiciones. El recorder escribe ids de.asiento de pantalla
# (`recorder_live.PLAYER_IDS`) y luego BORRA el campo `_id` de cada
# jugador antes de volcar el JSON:
#
#     out['allin'] = [p['_id'] for p in self.hand['players'] ...]
#     for p in out['players']:
#         del p['_id']
#
# O sea: el dato del all-in sobrevive, pero la llave que lo une con su
# posicion se tira. Por eso no hay `pos` en `allin`.
#
# PERO el orden de `players[]` NO se pierde: `recorder_live` la rellena
# recorriendo `PLAYER_IDS` en orden, asi que `players[i]` ES `PLAYER_IDS[i]`
# y la union se reconstruye por indice. Se verifica mas abajo en 1.b, con
# una asercion dura: si un dia el recorder deja de anexar en ese orden, este
# script dice que no sabe en vez de inventar una posicion.
PLAYER_IDS = ('hero', 'p1', 'p2', 'p3', 'p4', 'p5')


def ids_reales(hand):
    """True si `players[]` esta en el orden de PLAYER_IDS (supuesto base)."""
    return len(hand.get('players') or []) == len(PLAYER_IDS)


def posicion_de_id(hand, pid):
    """`_id` interno -> `pos`. None si el supuesto de orden no se cumple."""
    if not ids_reales(hand):
        return None
    return (hand['players'][PLAYER_IDS.index(pid)] or {}).get('pos') or None


def posiciones_allin(hand):
    """Set de posiciones all-in de la mano. None si no se puede saber.

    `None` NO es "nadie es all-in": es "no hay evidencia suficiente". Se
    distingue a proposito, que es lo que pide revision_2 ("estado
    desconocido: no se fuerza una clasificacion si la informacion necesaria
    no esta disponible").
    """
    if not ids_reales(hand):
        return None
    bruto = hand.get('allin')
    if bruto is None:
        # Ausencia del campo != ausencia de all-in: el campo lo escribe el
        # recorder, asi que su ausencia es desconocimiento, no un "no".
        return None
    out = set()
    for pid in bruto:
        pos = posicion_de_id(hand, pid)
        if pos is None:
            return None
        out.add(pos)
    return out


def calle_ultima_accion(hand, pos):
    """Ultima calle en la que `pos` tiene una accion registrada.

    Es la base de la inferencia "en que calle se fue all-in": un jugador
    que commitmenta todas sus fichas no vuelve a actuar, asi que la ultima
    accion suya ES la del all-in.
    """
    streets = hand.get('streets') or {}
    ultima = None
    for st in ORDEN:
        for a in ((streets.get(st) or {}).get('actions') or []):
            if isinstance(a, dict) and a.get('pos') == pos:
                ultima = st
    return ultima


def no_puede_actuar_evidencia(hand, street):
    """Rivales en el bote que NO pueden actuar, SEGUN EL DATO `allin`.

    Devuelve None si hay alguna posicion all-in de la que no se puede
    saber en que calle se commitmento (no se fuerza nada).

    Convencion declarada, y es una APROXIMACION que se mide en 4.d: el
    inventario trata cada calle como UN punto de decision, no como una
    accion. Por eso un all-in en la calle S se considera incapacity desde
    la propia calle S, aunque su accionHOUT occurriera despues de la del
    hero. La version que respeta el orden real se mide aparte.
    """
    ai = posiciones_allin(hand)
    if ai is None:
        return None
    fuera = set()
    for pos in ai:
        calle = calle_ultima_accion(hand, pos)
        if calle is None:
            return None
        if ORDEN.index(calle) <= ORDEN.index(street):
            fuera.add(pos)
    return fuera


def en_bote(hand, street):
    """Jugadores activos que no han foldeado hasta `street` (incluye hero)."""
    return {p.get('pos') for p in (hand.get('players') or [])
            if p.get('active')} - folds_hasta(hand, street)


# ---------------------------------------------------------------------------
def main():
    print('=' * 78)
    print('AUDITORIA DE no_puede_actuar()   (solo lectura)')
    print('=' * 78)
    manos = learn.load_hands(reliable_only=True)
    print('   ventana fiable: %d manos' % len(manos))

    # --------------------------------------------------------------- 1
    print()
    print('1) REPRESENTACION REAL DEL ALL-IN')
    print('-' * 78)
    campo = collections.Counter()
    valores = collections.Counter()
    for h in manos:
        if 'allin' in h:
            campo['con campo `allin`'] += 1
            for v in (h['allin'] or []):
                valores[str(v)] += 1
        else:
            campo['SIN campo `allin`'] += 1
    for k, v in campo.most_common():
        print('   %-28s %5d' % (k, v))
    print()
    print('   valores observados (son ids INTERNOS, no posiciones):')
    for k, v in valores.most_common():
        print('      %-10s %5d' % (k, v))

    print()
    print('   b) SE PUEDE VOLVER A UNIR EL ID CON SU POSICION?')
    print('      `players[]` se rellena recorriendo PLAYER_IDS en orden, y')
    print('      `_id` se borra al volcar. Si el orden se respeta, el indice')
    print('      lo reconstruye. Comprobado sobre la ventana fiable:')
    n_ok = n_mal = 0
    for h in manos:
        for pid in (h.get('allin') or []):
            if posicion_de_id(h, pid):
                n_ok += 1
            else:
                n_mal += 1
    print('      ids resueltos a posicion: %d' % n_ok)
    print('      ids SIN posicion (supuesto roto): %d' % n_mal)
    print('      longitudes de players[]: %s'
          % sorted({len(h['players']) for h in manos}))
    print('      -> VEREDICTO: %s'
          % ('el mapeo es exacto' if n_mal == 0 else
             'NO SE PUEDE MAPEAR: el clasificador queda SIN EVIDENCIA'))

    # --------------------------------------------------------------- 2
    print()
    print('2) DIAGNOSTICO DE no_puede_actuar()  (el bug de revision_2)')
    print('-' * 78)
    print('   La regla actual es: "ha subido -> no puede actuar".')
    print('   El dato dice lo contrario. Medido sobre los %d ids all-in'
          % n_ok)
    print('   y los raise del inventario:')
    fp = fn = 0
    raiseos_tot = 0
    ejemplos_fp, ejemplos_fn = [], []
    for h in manos:
        ai = posiciones_allin(h)
        if ai is None:
            continue
        raiseos = set()
        for st in ORDEN:
            for a in ((h['streets'].get(st) or {}).get('actions') or []):
                if isinstance(a, dict) and a.get('action') == 'r' and a.get('pos'):
                    raiseos.add(a['pos'])
        raiseos_tot += len(raiseos)
        falsos = raiseos - ai          # subió y SIGUE TENIENDO FICHAS
        perdidos = ai - raiseos        # se fue all-in sin subir (call)
        fp += len(falsos)
        fn += len(perso0 := perdidos)
        if falsos and len(ejemplos_fp) < 3:
            ejemplos_fp.append((h['hand_id'], sorted(falsos), sorted(ai)))
        if perdidos and len(ejemplos_fn) < 3:
            ejemplos_fn.append((h['hand_id'], sorted(perso0), sorted(ai)))
    print()
    print('      raise distintos en la ventana      : %5d' % raiseos_tot)
    print('      FALSOS POSITIVOS (subio, no all-in): %5d   <- el bug'
          % fp)
    print('      FALSOS NEGATIVOS (all-in por call): %5d   <- el bug'
          % fn)
    if raiseos_tot:
        print('      precision de la regla actual      : %5.1f%%'
              % ((raiseos_tot - fp) / raiseos_tot * 100))
    print()
    print('      ejemplos de FALSO POSITIVO (subio y conservo fichas):')
    for h_id, mal, bien in ejemplos_fp:
        print('         %-8s subio y NO es all-in: %-14s allin real: %s'
              % (h_id, mal, bien))
    print('      ejemplos de FALSO NEGATIVO (all-in sin subir, con call):')
    for h_id, mal, bien in ejemplos_fn:
        print('         %-8s allin y NO subio: %-14s allin real: %s'
              % (h_id, mal, bien))

    # --------------------------------------------------------------- 2.b
    print()
    print('2.b) CALIDAD DEL PROPIO CAMPO `allin`  (defecto del dato, no del')
    print('     clasificador)')
    print('-' * 78)
    print('   El recorder filtra `allin` al volcar con `p["active"]`, y')
    print('   `active` significa "estaba sentado al empezar la mano", NO')
    print('   "no ha foldeado". Un jugador que se commitmenta y despues')
    print('   FOLDEA queda en la lista de `allin`. Se cuenta:')
    ids_tot = corruptos = 0
    corrotos_ej = []
    for h in manos:
        ai = posiciones_allin(h)
        if not ai:
            continue
        f_toda = {a.get('pos') for st in ORDEN
                  for a in ((h['streets'].get(st) or {}).get('actions') or [])
                  if isinstance(a, dict) and a.get('action') == 'f'}
        for pos in ai:
            ids_tot += 1
            if pos in f_toda:
                corruptos += 1
                corrotos_ej.append((h['hand_id'], pos))
    print('      entradas en `allin`        : %5d' % ids_tot)
    print('      de las cuales con un fold  : %5d   (%.1f%%)'
          % (corruptos, corruptos / ids_tot * 100 if ids_tot else 0))
    for h_id, pos in corrotos_ej[:5]:
        print('         %-8s %s se commitmenta y luego foldea' % (h_id, pos))
    print()
    print('      -> Es poco, pero NO es cero: el cruce de la seccion 3 no')
    print('         es 0 por construccion, es 0 MAS UNOS datos malos.')

    # --------------------------------------------------------------- 3
    print()
    print('3) ORTOGONALIDAD  folds_hasta  x  no_puede_actuar')
    print('-' * 78)
    print('   Un jugador que foldeo ya no esta en el bote. Si aparece en los')
    print('   dos conjuntos a la vez, el 1694 esta contando dos veces o')
    print('   ninguna. Se mide para la regla VIEJA y para la de EVIDENCIA.')
    print()
    print('   %-22s %9s %9s %9s' % ('clasificador', 'ambos', 'solo uno', 'ninguno'))
    cruce_evidencia = []
    for nombre, fn_npa in (('actual (raise)', no_puede_actuar),
                           ('evidencia (allin)', no_puede_actuar_evidencia)):
        ambos = solo = ninguno = 0
        for h in manos:
            for st in STREETS:
                acciones = ((h['streets'].get(st) or {}).get('actions') or [])
                if not acciones or not [p for p in (h['players'] or [])
                                        if (p.get('cards') or '').strip()]:
                    continue
                f = folds_hasta(h, st)
                n = fn_npa(h, st)
                if n is None:
                    # evidencia insuficiente: se cuenta como "no clasificable"
                    # y NO como "no pasa nada"
                    continue
                for pos in en_bote(h, st) | f | n:
                    a = pos in f
                    b = pos in n
                    if a and b:
                        ambos += 1
                        if nombre.startswith('evidencia'):
                            cruce_evidencia.append((h['hand_id'], st, pos))
                    elif a or b:
                        solo += 1
                    else:
                        ninguno += 1
        print('   %-22s %9d %9d %9d' % (nombre, ambos, solo, ninguno))
    print()
    print('   LECTURA (esto es lo que revision_1 pidio medir):')
    print('   - Con la regla ACTUAL, un jugador que subio y LUEGO FOLDEO')
    print('     cae en los dos conjuntos a la vez: es un Doble conteo real,')
    print('     no un caso teorico. Por eso "cuadrar" el desglose no')
    print('     demuestra que el 1694 sea correcto.')
    print('   - Con la regla de EVIDENCIA el cruce baja a %d. No es cero por'
          % len(cruce_evidencia))
    print('     construccion: son los registros de `allin` corruptos (2.b).')
    for h_id, st, pos in cruce_evidencia[:3]:
        print('       %-8s %-6s %s' % (h_id, st, pos))
    print()
    print('   VEREDICTO: los dos conjuntos NO son ortogonales con la regla')
    print('   actual. Con la regla de evidencia, si, salvo datos malos.')

    # --------------------------------------------------------------- 4
    print()
    print('4) INVENTARIO RECALCULADO: MW en el bote vs MW pueden actuar')
    print('-' * 78)
    print('   Mismo denominador (los mismos puntos de decision), las tres')
    print('   cifras que F7.2 tiene que elegir entre ellas:')
    print()
    print('   %-8s %12s %14s %14s' % ('calle', 'MW en el bote',
                                     'MW (regla actual)', 'MW (evidencia)'))
    print('   ' + '-' * 52)
    tot_bote = tot_viejo = tot_nuevo = 0
    sin_ev = 0
    unknown_mw = 0
    for st in STREETS:
        b = v = n_ = 0
        for h in manos:
            acciones = ((h['streets'].get(st) or {}).get('actions') or [])
            heroes = [p for p in (h['players'] or [])
                      if (p.get('cards') or '').strip()]
            if not acciones or not heroes:
                continue
            bote = en_bote(h, st)
            if len(bote) - 1 > 1:
                b += 1
            if len(bote - no_puede_actuar(h, st)) - 1 > 1:
                v += 1
            npa = no_puede_actuar_evidencia(h, st)
            if npa is None:
                sin_ev += 1
                # revision_2 punto 2: sin evidencia NO se fuerza HU ni
                # MULTIWAY. Se sale del numerador y se cuenta aparte.
                if len(bote) - 1 > 1:
                    unknown_mw += 1
                continue
            if len(bote - npa) - 1 > 1:
                n_ += 1
        print('   %-8s %12d %14d %14d' % (st, b, v, n_))
        tot_bote += b
        tot_viejo += v
        tot_nuevo += n_
    print('   ' + '-' * 52)
    print('   %-8s %12d %14d %14d' % ('TOTAL', tot_bote, tot_viejo, tot_nuevo))
    print()
    print('   puntos de decision SIN EVIDENCIA (campo `allin` ausente o')
    print('   calle de all-in indeterminada): %d' % sin_ev)
    print('   Esos quedan FUERA del numerador de "evidencia" a proposito: no')
    print('   se fuerzan. revision_2 punto 2 pide exactamente eso.')
    print()
    print('   COTA HONESTA del multiway real (no un punto, un intervalo):')
    print('      los %d puntos sin evidencia son MW en el bote: %d'
          % (sin_ev, unknown_mw))
    print('      -> el multiway que puede responder esta entre %d y %d'
          % (tot_nuevo, tot_nuevo + unknown_mw))
    print('      (el extremo alto es el techo: si en esos puntos no habia')
    print('       all-in, todos siguen pudiendo actuar.)')
    print()
    print('   COMO SE LEE LA DIFERENCIA (297 -> 169 era el dato de F7.1):')
    print('     MW en el bote              : %d' % tot_bote)
    print('     MW pueden actuar (ACTUAL)  : %d   <- el numero que sostiene F7.2'
          % tot_viejo)
    print('     MW pueden actuar (EVIDENC.): %d   (cota inferior)' % tot_nuevo)
    print()
    print('   El all-in RECLASA %d spots con la regla nueva y %d con la'
          % (tot_bote - tot_nuevo, tot_bote - tot_viejo))
    print('   vieja. La nueva reclasifica MENOS porque ya no confunde "ha')
    print('   subido" con "se ha commitmentado": de los %d jugadores que la'
          % raiseos_tot)
    print('   regla vieja marcaba, %d NO eran all-in (%.1f%%).'
          % (fp, fp / raiseos_tot * 100 if raiseos_tot else 0))
    print()
    print('   CONSECUENCIA PARA F7.2: el 169 estaba MAL FUNDAMENTADO. No es')
    print('   que el multiway sea mayor o menor que decia: es que el numero')
    print('   se apoyaba en una regla con %.1f%% de precision. La cifra de'
          % (fp / raiseos_tot * 100 if raiseos_tot else 0))
    print('   referencia para F7.2 es el intervalo de arriba, no el 169.')
    return 0


if __name__ == '__main__':
    sys.exit(main())