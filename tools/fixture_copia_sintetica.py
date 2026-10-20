# -*- coding: utf-8 -*-
"""Las COPIAS SINTETICAS de la base, para probar el procedimiento de integracion.

Y no son la copia real: son **fixtures de test**, y sus transformaciones estan
DECLARADAS, que es lo que los hace reproducibles.

Y hay dos, y se llaman por su DUREZA, que es lo que los diferencia:

  · la SUAVE  — solo RECODIFICA la ciega del BB en las manos ya revisadas.
  · la DURA   — recodifica Y AÑADE las ciegas que faltaban, en las 1258.

## LAS REVISADAS, MEDIDAS

Y cuales son esas, sale de los datos y no de una lista escrita a mano: son las
manos cuyo bote quedo **RESUELTO** por la herramienta del trabajo en paralelo.
`tools/aritmetica_botes.py::aplicar_normalizacion` cuenta `manos_n` —las que
tienen `resuelto`— y ese numero es 1055. Y las restantes, 203, son las que la
herramienta **no** pudo resolver, y las que por eso necesitan la GRABACION
ORIGINAL, que es lo que esta revisando A1.

Y las 203, MEDIDO, y por clase: 62 `ACCION_AMBIGUA`, 133 `NADA`, y 8
`UNICA_TOL`. De modo que el corte cae exactamente donde tiene que caer: donde
el dato no se puede resolver solo.

## LA REGLA DE LO DURO, MEDIDA SOBRE LA COPIA REAL

Y la regla no es inventada: es la que la copia real aplica, y esta medida mano
a mano. Y la medicion que la fija es la que distingue «CONVIERTE» de «AÑADE»,
que es donde el primer intento se equivocó:

| que hace la copia con cada `b` de la canonica | manos | mantiene | convierte |
|---|---:|---:|---:|
| **la del BB, de importe 1.0** | 915 | 0 | **915** |
| la del BB, de importe 0.5 | 6 | 4 | 0 |
| cualquier otra —los antes, los straddles— | — | **todas** | 0 |

> **La unica `b` que se convierte en `p` es la ciega del BB.** Y los antes NO se
> convierten: la copia los deja como `b`, y por eso las doce categorias de la
> primera decision no se mueven.

Y la regla dura, que es la de la copia:

> (a) la `b` del BB de importe 1.0 pasa a `p`;
> (b) si al BB le falta la ciega, se le ANTEPONE una `p` de 1.0;
> (c) si al SB le falta, se le ANTEPONE una `p` de 0.5;
> (d) las dos posts van al PRINCIPIO del preflop, y la SB antes que la BB.

## Y LO QUE EL FIXTURE DURO NO HACE, Y POR QUE

> **No añade antes.** Y el motivo es que saber que manos tenian ante sale de
> la GRABACION ORIGINAL, que es de A1: la copia real anade el ante que falta
> en 12 manos, y ese «falta» no se deduce de la base, sino del pot.
>
> Y no afecta a lo que el procedimiento mide: MEDIDO, el fixture duro da 1258
> ciegas —las mismas que la copia real—, 0 errores, 0 violaciones, y las doce
> categorias de control.

## Y LOS DOS UMBRALES

Y el umbral de cada fixture **no es una constante global**: lo mide el propio
fixture y lo dice en su informe, y el test lo pasa como parametro. Y por que
importa: el fixture suave reconoce 921 ciegas y el duro 1258, y un umbral
unico para los dos seria un umbral que no dice nada.
"""
import collections
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REL = 'data/hands_db.jsonl'
DETALLE_REL = 'trabajo/botes_aritmetica.jsonl'

# Los dos grados de dureza.
DUREZA_SUAVE = 'suave'
DUREZA_DURA = 'dura'

# Las ciegas nominales, y son las que usa la copia real.
NOMINAL_BB = 1.0
NOMINAL_SB = 0.5


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


def _preflop(mano):
    return (((mano.get('streets', {}) or {}).get('preflop', {}) or {})
            .get('actions', []) or [])


def recodificar(mano, bb_nominal=1.0):
    """La ciega del BB, de apuesta a posta. Y el importe, NO se toca.

    Y la regla es la del CONTRATO: una `p` es una posta, y la ciega es
    exactamente eso. Y el cambio es del primer `b` del BB en el preflop, que es
    donde la ciega esta cuando esta.
    """
    g = json.loads(json.dumps(mano))
    for a in _preflop(g):
        if (a.get('pos') == 'BB' and a.get('action') == 'b'
                and float(a.get('amount') or 0.0) <= bb_nominal + 1e-9):
            a['action'] = 'p'
            return g
    return g


def endurecer(mano):
    """La mano dura: la ciega del BB es una `p`, y las que faltan se anaden.

    Y la regla es la de la copia real, MEDIDA, y esta en el docstring de este
    fichero. Y lo que hace, en orden:

      (a) la `b` del BB de importe 1.0 pasa a `p`;
      (b) si al BB le falta la ciega, se le antepone una `p` de 1.0;
      (c) si al SB le falta, se le antepone una `p` de 0.5;
      (d) las dos posts van al principio, y la SB antes que la BB.

    Y lo que NO hace, y por que, esta en el docstring de este fichero: no
    anade antes, porque saber que manos tenian ante sale de la GRABACION
    ORIGINAL, que es de A1.
    """
    g = json.loads(json.dumps(mano))
    acc = _preflop(g)

    # (a) la ciega del BB
    for a in acc:
        if (a.get('pos') == 'BB' and a.get('action') == 'b'
                and abs(float(a.get('amount') or 0.0) - NOMINAL_BB) < 1e-9):
            a['action'] = 'p'

    # (b) y (c): las ciegas que faltan
    tiene_bb = any(a.get('pos') == 'BB' and a.get('action') == 'p'
                   for a in acc)
    tiene_sb = any(a.get('pos') == 'SB' and a.get('action') == 'p'
                   for a in acc)
    nuevas = []
    if not tiene_sb:
        nuevas.append({'pos': 'SB', 'action': 'p', 'amount': NOMINAL_SB})
    if not tiene_bb:
        nuevas.append({'pos': 'BB', 'action': 'p', 'amount': NOMINAL_BB})
    if nuevas:
        acc[0:0] = nuevas
    return g


def _ciegas_reconocidas(ruta):
    """Cuantas ciegas del BB reconoce el MOTOR en un fichero de base.

    Y se cuenta con la regla del motor, `_es_ciega_bb`, y no con una regla
    propia: que es lo unico que hace que el numero signifique algo.
    """
    import sys
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from motor import learn
    n = 0
    for h in _cargar(ruta):
        seq = learn._preflop_sequence(h)
        if any(learn._es_ciega_bb(i, p, a, m, b, False)
               for i, (p, a, m, b) in enumerate(seq)):
            n += 1
    return n


def construir(destino, dureza=DUREZA_SUAVE, db_rel=None, detalle_rel=None):
    """La copia sintetica completa, y un informe de lo que se hizo.

    Y el informe lleva las cifras MEDIDAS: cuantas manos se tocaron, y
    —lo que de verdad importa— **cuantas ciegas reconoce el motor en el
    resultado**. Y ese numero es el UMBRAL del fixture, y el umbral de cada
    fixture sale de aqui: no hay ninguna constante global para eso.

    Y las manos que se dejan intactas, en el fixture suave, son las 203 que
    A1 tiene que revisar: y que esten intactas es parte del contrato del
    fixture, y hay un test que lo comprueba.
    """
    if dureza not in (DUREZA_SUAVE, DUREZA_DURA):
        raise ValueError('dureza desconocida: %r' % dureza)
    db_rel = db_rel or os.path.join(ROOT, *DB_REL.split('/'))
    destino = os.path.abspath(destino)
    manos = _cargar(db_rel)
    revisados = revisadas(detalle_rel)
    tocadas = 0
    salida = []
    for h in manos:
        if dureza == DUREZA_DURA:
            g = endurecer(h)
        elif h.get('hand_id') in revisados:
            g = recodificar(h)
        else:
            g = h
        if g != h:
            tocadas += 1
        salida.append(g)
    with io.open(destino, 'w', encoding='utf-8', newline='\n') as f:
        for h in salida:
            f.write(json.dumps(h, ensure_ascii=False) + '\n')
    return {
        'dureza': dureza,
        'manos': len(salida),
        'revisadas_disponibles': len(revisados),
        'tocadas': tocadas,
        'dejadas': len(salida) - tocadas,
        'ciegas_reconocidas': _ciegas_reconocidas(destino),
    }


def _categorias(ruta):
    """Las doce categorias de la primera decision, MEDIDAS con el motor."""
    import sys
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from motor import learn
    c = collections.Counter()
    for h in _cargar(ruta):
        for e in learn.preflop_events(h):
            c[e.category] += 1
    return dict(c)
