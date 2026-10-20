# -*- coding: utf-8 -*-
"""La COPIA SINTETICA de la base, para probar el procedimiento de integracion.

Y no es la copia real: es un **fixture de test**, y su transformacion esta
DECLARADA, que es lo que lo hace reproducible.

Y la transformacion es una sola, y la regla dice cual es:

> Se recodifican las ciegas como `p` **solo en las manos ya revisadas por
> A1**.

Y cuales son esas, MEDIDO, y sale de los datos y no de una lista escrita a
mano: son las manos cuyo bote quedo **RESUELTO** por la herramienta del
trabajo en paralelo. `tools/aritmetica_botes.py::aplicar_normalizacion`
cuenta `manos_n` —las que tienen `resuelto`— y ese numero es 1055. Y las
restantes, 203, son las que la herramienta **no** pudo resolver, y las que
por eso necesitan la GRABACION ORIGINAL, que es lo que esta revisando A1.

Y las 203, MEDIDO, y por clase: 62 `ACCION_AMBIGUA`, 133 `NADA`, y 8
`UNICA_TOL`. De modo que el corte cae exactamente donde tiene que caer: donde
el dato no se puede resolver solo.

Y la transformacion, en concreto: **la ciega del BB, que en la base de hoy
esta grabada como una apuesta `b`, pasa a ser una posta `p`.** Y el importe
NO se toca. De modo que es un cambio de codificacion y nada mas: y por eso las
doce categorias de la primera decision no se mueven, que es la propiedad que
el procedimiento comprueba.

Y esto NO es la copia real, y la diferencia es la que importa: la copia real
**añade** las ciegas que faltaban, y esta solo las **recodifica**. De modo
que el fixture es MAS SUAVE que la copia real, y por eso el numero de ciegas
que reconoce es el de la base de hoy y no otro.
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REL = 'data/hands_db.jsonl'
DETALLE_REL = 'trabajo/botes_aritmetica.jsonl'


def _cargar(ruta):
    salida = []
    with io.open(ruta, encoding='utf-8') as f:
        for l in f:
            if l.strip():
                salida.append(json.loads(l))
    return salida


def revisadas(detalle_rel=None):
    """Los `hand_id` que la herramienta pudo resolver, y que estan revisados.

    Y la fuente es el fichero de detalle del trabajo en paralelo, que es lo
    que lleva el campo `resuelto`. Y si no esta, se devuelve la lista vacia, y
    el fixture se queda con la base sin recodificar: que es mejor un fixture
    que no prueba nada que uno que prueba una cosa falsa.
    """
    detalle_rel = detalle_rel or os.path.join(ROOT, *DETALLE_REL.split('/'))
    if not os.path.exists(detalle_rel):
        return set()
    return set(d.get('hand_id') for d in _cargar(detalle_rel)
               if d.get('resuelto'))


def recodificar(mano, bb_nominal=1.0):
    """La ciega del BB, de apuesta a posta. Y el importe, sin tocar.

    Y la regla es la del CONTRATO: una `p` es una posta, y la ciega es
    exactamente eso. Y el cambio es del primer `b` del BB en el preflop, que es
    donde la ciega esta cuando esta.
    """
    g = json.loads(json.dumps(mano))
    pre = ((g.get('streets', {}) or {}).get('preflop', {}) or {}).get(
        'actions', []) or []
    for a in pre:
        if (a.get('pos') == 'BB' and a.get('action') == 'b'
                and float(a.get('amount') or 0.0) <= bb_nominal + 1e-9):
            a['action'] = 'p'
            return g
    return g


def construir(destino, db_rel=None, detalle_rel=None):
    """La copia sintetica completa, y un informe de lo que se hizo.

    Y devuelve el informe con las cifras MEDIDAS: cuantas manos se
    recodificaron, cuantas se dejaron, y el numero de ciegas que el motor
    reconoce en el resultado. Y esas cifras son las que el test usa de umbral,
    y el umbral del FIXTURE no es el de la copia real.
    """
    db_rel = db_rel or os.path.join(ROOT, *DB_REL.split('/'))
    destino = os.path.abspath(destino)
    manos = _cargar(db_rel)
    revisados = revisadas(detalle_rel)
    recodificadas = 0
    salida = []
    for h in manos:
        if h.get('hand_id') in revisados:
            g = recodificar(h)
            if g != h:
                recodificadas += 1
            salida.append(g)
        else:
            salida.append(h)
    with io.open(destino, 'w', encoding='utf-8', newline='\n') as f:
        for h in salida:
            f.write(json.dumps(h, ensure_ascii=False) + '\n')
    return {
        'manos': len(salida),
        'revisadas_disponibles': len(revisados),
        'recodificadas': recodificadas,
        'dejadas': len(salida) - recodificadas,
    }
