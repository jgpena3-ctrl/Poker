# -*- coding: utf-8 -*-
"""Mide el `bb_check` perdido y clasifica las manos para la migracion.

Correction (post revision_1/revision_2)
---------------------------------------
La version anterior clasificaba con este filtro:

    propias = [x for x in bbs if x[1] != 'b' or x[3]]

Es decir,.trataba CUALQUIER accion 'b' del BB como si fuera su ciega. Eso
daba 41 manos, pero en 16 de ellas la entrada `BB b` esta DESPUES de acciones
voluntarias: la ciega no puede ir ahi. `learn._es_ciega_bb` exige
`not voluntary_before` precisamente por eso, y el motor lee esa entrada como
una SUBIDA voluntaria del BB.

En esas 16 el BB ya ha actuado, asi que no le falta un check: le sobra una
subida que no ocurrio. Anadir el check no las arregla.

Este script clasifica con la MISMA logica que el motor (`preflop_events`), no
con una reimplementacion, para que inventario y motor no puedan divergir.

Uso:  python tools/auditar_bb_check.py [--json]
"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor import learn  # noqa: E402


def _entradas_bb_rechazadas(h):
    """Entradas `BB b` que el motor NO reconocio como ciega obligatoria.

    Se reproduce el recorrido de `preflop_events` (que mantiene
    `voluntary_before`) usando la propia funcion `learn._es_ciega_bb`, en vez
    de mirar el campo `blind` del dato: los datos antiguos no lo traen y la
    ciega se reconoce estructuralmente. Mirar el campo daria ~523 falsos
    positivos.

    Devuelve [(indice, importe, causa)] con la causa en:
      'tras_accion_voluntaria'  -> la ciega esta mal ORDENADA (defecto de dato)
      'importe_sobre_nominal'   -> la regla antigua `amount <= bb` la rechazo
                                    (defecto del motor, ya corregido)
    """
    seq = learn._preflop_sequence(h)
    rechazadas = []
    voluntary_before = False
    for i, (pos, act, amount, is_blind) in enumerate(seq):
        if learn._es_ciega_bb(i, pos, act, amount, is_blind,
                              voluntary_before, learn.BB):
            if act in ('b', 'r', 'c'):
                voluntary_before = True
            continue
        if pos == 'BB' and act == 'b':
            causa = ('tras_accion_voluntaria' if voluntary_before
                     else 'importe_sobre_nominal')
            rechazadas.append((i, amount, causa))
        if act in ('b', 'r', 'c'):
            voluntary_before = True
    return rechazadas


def clasificar(h):
    """(clase, detalle) con la misma logica que motor.learn.preflop_events."""
    st = h.get('streets', {}) or {}
    pf = (st.get('preflop') or {}).get('actions') or []
    flop = (st.get('flop') or {}).get('actions') or []
    board = (st.get('flop') or {}).get('board') or []
    if not pf:
        return 'sin_preflop', None

    eventos = [e for e in learn.preflop_events(h) if e.pos == 'BB']

    if eventos:
        cat = eventos[0].category
        if _entradas_bb_rechazadas(h):
            return 'ciega_mal_puesta', cat
        return 'registrado', cat

    if flop or board:
        return 'check_perdido', None
    return 'ambiguo', None


def main():
    hands = learn.load_hands(reliable_only=True)

    conteo = collections.Counter()
    ids_por_clase = collections.defaultdict(list)
    cat_por_clase = collections.defaultdict(collections.Counter)
    causas = collections.Counter()
    manos_por_causa = collections.defaultdict(set)

    for h in hands:
        clase, cat = clasificar(h)
        conteo[clase] += 1
        ids_por_clase[clase].append(h.get('hand_id'))
        if cat:
            cat_por_clase[clase][cat] += 1
        for _i, _amt, causa in _entradas_bb_rechazadas(h):
            causas[causa] += 1
            manos_por_causa[causa].add(h.get('hand_id'))

    total = sum(v for k, v in conteo.items() if k != 'sin_preflop')
    print('ventana: %d manos con preflop' % total)
    print()
    etiquetas = [
        ('registrado', 'BB con accion registrada:            '),
        ('check_perdido', 'BB sin accion y preflop cerrado:      '),
        ('ciega_mal_puesta', 'BB con la ciega puesta mal:         '),
        ('ambiguo', 'BB aun en preflop (ambiguo):           '),
    ]
    for clave, etiq in etiquetas:
        n = conteo[clave]
        pct = n / total * 100 if total else 0
        print('  %s %4d  (%5.1f%%)' % (etiq, n, pct))
    print()

    # ---- subrepresentacion del bb_check, sobre bases coherentes -----------
    perdidos = conteo['check_perdido']
    check_real = len([e for h in hands for e in learn.preflop_events(h)
                      if e.category == 'bb_check'])
    if check_real + perdidos:
        print('  bb_check observado            : %4d' % check_real)
        print('  bb_check inferible (perdidos) : %4d' % perdidos)
        print('  -> subrepresentacion real     : %4.1f%%  (%d de %d eventos)'
              % (perdidos / (check_real + perdidos) * 100, perdidos,
                 check_real + perdidos))
        print('     NOTA: la version anterior de este script daba 4.9% usando')
        print('     como denominador las %d manos con "cualquier accion del BB",'
              % conteo['registrado'])
        print('     no los %d eventos bb_check. Bases distintas, numeros sin'
              % check_real)
        print('     relacion. Aqui se usa una sola base.')
    print()

    # ---- el defecto nuevo -------------------------------------------------
    print('  DEFECTO NUEVO: la ciega del BB esta DESPUES de acciones')
    print('  voluntarias, asi que el motor la lee como una subida suya.')
    print('  Estas manos NO son un check perdido: anadir el check no las')
    print('  arregla, y corregirlas exigiria inventar un orden que los datos')
    print('  no dicen. Se dejan fuera de CM-003.')
    print('  Que categoria se les asigna en su lugar:')
    for cat, n in cat_por_clase['ciega_mal_puesta'].most_common():
        print('     %-12s %3d' % (cat, n))
    print('     TOTAL      %3d  (ataques al BB que pueden no haber ocurrido)'
          % sum(cat_por_clase['ciega_mal_puesta'].values()))
    print()

    print('  POR QUE se rechaza cada entrada `BB b` (desglose reproducible):')
    if not causas:
        print('     ninguna entrada rechazada.')
    for causa, n in causas.most_common():
        etiqueta = ('tras_accion_voluntaria'
                    if causa == 'tras_accion_voluntaria'
                    else 'importe_sobre_nominal')
        mano = 'defecto de DATO (ciega mal ordenada)'
        if causa != 'tras_accion_voluntaria':
            mano = 'defecto del MOTOR (regla antigua amount<=bb)'
        print('     %-26s %3d entradas en %2d manos  <- %s'
              % (etiqueta, n, len(manos_por_causa[causa]), mano))
    if 'importe_sobre_nominal' in causas:
        print('     (el defecto del motor se corrigio en el commit 9f4869f; si')
        print('      reaparece, es una regresion)')
    print()

    print('  Manos migrables (check perdido), %d:' % perdidos)
    print('     ' + ', '.join(ids_por_clase['check_perdido']))
    print()

    print('  Manos bloqueadas (ciega mal puesta), %d:' % conteo['ciega_mal_puesta'])
    print('     ' + ', '.join(ids_por_clase['ciega_mal_puesta']))
    print()

    print('CONCLUSION')
    print('  El check del BB SÍ es recuperable: si el preflop cerro, la calle se')
    print('  termino y el BB, sin accion propia, hizo check. Eso da %d manos.'
          % perdidos)
    print('  Las otras %d tienen la ciega mal puesta: otro defecto, medido y'
          % conteo['ciega_mal_puesta'])
    print('  documentado, no resuelto aqui.')

    if '--json' in sys.argv:
        out = os.path.join(ROOT, 'data', 'bb_check_perdidos.json')
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'migrables': ids_por_clase['check_perdido'],
                       'bloqueadas': ids_por_clase['ciega_mal_puesta'],
                       'check_perdido': perdidos,
                       'ciega_mal_puesta': conteo['ciega_mal_puesta'],
                       'cat_asignada_bloqueadas': dict(
                           cat_por_clase['ciega_mal_puesta'])}, f, indent=2)
        print('\n-> %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
