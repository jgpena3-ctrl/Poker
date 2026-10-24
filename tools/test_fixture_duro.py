# -*- coding: utf-8 -*-
"""EL FIXTURE DURO, CONTRA LA COPIA REAL, Y SU DETERMINISMO.

Y lo que se comprueba aqui es lo que el bloque anterior afirmo y no fijo:

  · que el fixture duro es DETERMINISTA: dos construcciones dan el mismo sha,
    y con eso su sha se puede DECLARAR y no es memoria;
  · que el fixture duro NO TOCA los antes ni los straddles: la unica `b` que
    se convierte en `p` es la ciega del BB de importe 1.0, y ese es
    justamente el detalle que separaba el primer intento fallido;
  · que el fixture duro NO toca los botes: es un cambio de codificacion y de
    posts, y nada mas;
  · y QUE DIFIERE DE LA COPIA REAL EN LOS BOTES, y por que: MEDIDO, la copia
    real RESUELVE el bote de 689 de las 1055 manos, y el fixture no resuelve
    ninguno.

Y la comparacion con la copia real es de SOLO LECTURA, y si el fichero no
esta, el test se salta con el motivo declarado —que es mejor un test que no
comprueba nada con el motivo a la vista, que un test que se pasa sin
comprobar—.
"""
import hashlib
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import fixture_copia_sintetica as FIX   # noqa: E402

COPIA_REL = os.path.join(ROOT, 'trabajo', 'hands_db_edicion.jsonl')
DETALLE_REL = os.path.join(ROOT, 'trabajo', 'botes_aritmetica.jsonl')
CANON_REL = os.path.join(ROOT, 'data', 'hands_db.jsonl')


def _sha(ruta):
    with io.open(ruta, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def _construir(dureza, etiqueta):
    alta = tempfile.mkdtemp(prefix='fx_%s_' % etiqueta)
    ruta = os.path.join(alta, 'candidata.jsonl')
    informe = FIX.construir(ruta, dureza=dureza)
    return ruta, informe


def test_el_fixture_duro_es_determinista():
    """Y que dos construcciones den el MISMO sha.

    Y el motivo de que esto sea un test y no una frase: el fixture es la
    base de las pruebas del procedimiento, y si su contenido dependiera de
    un diccionario o de un conjunto, sus shas serian distintos cada vez y
    el sha declarado no valdria para nada.
    """
    r1, _i1 = _construir(FIX.DUREZA_DURA, 'a')
    r2, _i2 = _construir(FIX.DUREZA_DURA, 'b')
    try:
        assert _sha(r1) == _sha(r2), (
            'el fixture duro no es determinista: %r y %r'
            % (_sha(r1)[:16], _sha(r2)[:16]))
    finally:
        for r in (r1, r2):
            os.remove(r)
            os.rmdir(os.path.dirname(r))


def test_el_fixture_duro_no_toca_los_antes_ni_los_straddles():
    """Y el detalle que separa el duro del primer intento, que convertia los
    antes y movia las doce categorias.

    Y la regla, MEDIDA sobre la copia real: **la unica `b` que se convierte
    en `p` es la ciega del BB de importe 1.0**. Y todo lo demas —los antes,
    que son una `b` de 1.0 de OTRO puesto, y los straddles, que son una `b`
    de mas de 1.0— se queda como estaba.

    Y el motivo de que el test lo mire en las DOS fuentes: el fixture
    convierte la ciega del BB y no toca ninguna otra, y la copia real lo
    mismo, y esa es la prueba de que el fixture se parece a la copia.
    """
    ruta, _informe = _construir(FIX.DUREZA_DURA, 'antes')
    try:
        with io.open(ruta, encoding='utf-8') as f:
            duras = [json.loads(l) for l in f if l.strip()]
        with io.open(CANON_REL, encoding='utf-8') as f:
            base = {json.loads(l)['hand_id']: json.loads(l)
                    for l in f if l.strip()}

        convertidas = 0
        for h in duras:
            hb = base[h['hand_id']]
            ab = FIX._preflop(hb)
            ad = FIX._preflop(h)
            # Y LA CIEGA DEL BB, que es lo unico que se convierte.
            #
            # Y la cuenta va sobre la BASE, y no sobre el fixture: en el
            # fixture la ciega ya es una `p`, y en la base es una `b`. Y el
            # numero es el de la base, que es donde esta la cuenta.
            ciegas_base = [a for a in ab
                           if a.get('action') == 'b'
                           and a.get('pos') == 'BB'
                           and abs(float(a.get('amount') or 0) - 1.0) < 1e-9]
            ciegas_duras = [a for a in ad
                            if a.get('action') == 'p'
                            and a.get('pos') == 'BB'
                            and abs(float(a.get('amount') or 0) - 1.0) < 1e-9]
            assert len(ciegas_duras) >= len(ciegas_base), (
                'la ciega del BB disappeared en %s' % h['hand_id'])
            convertidas += len(ciegas_base)

            # y lo demas: los antes y los straddles siguen siendo `b`, y con
            # el MISMO importe. Y la comparacion es sobre las DECISIONES,
            # con la regla del motor —una posta y la ciega del BB no son
            # decisiones—, porque el fixture ANTEPONE las posts y comparar
            # posicionalmente compararia una `p` con una `b`.
            dec_base = _decisiones(hb)
            dec_dura = _decisiones(h)
            assert dec_base == dec_dura, (
                'las decisiones cambiaron en %s: %r -> %r'
                % (h['hand_id'], dec_base[:4], dec_dura[:4]))
        # y el numero: MEDIDO, la ciega del BB de importe 1.0 esta en 915 manos
        assert convertidas == 915, convertidas
    finally:
        os.remove(ruta)
        os.rmdir(os.path.dirname(ruta))


def test_el_fixture_duro_no_toca_los_botes():
    """Y que los botes sean los de la base de hoy, uno a uno.

    Y el motivo de que esto sea un test: el fixture duro es un cambio de
    CODIFICACION y de posts. Si tocara un bote, estaria resolving una
    aritmetica que es de A1, y el fixture mediria otra cosa.
    """
    ruta, _informe = _construir(FIX.DUREZA_DURA, 'botes')
    try:
        with io.open(ruta, encoding='utf-8') as f:
            duras = {json.loads(l)['hand_id']: json.loads(l)
                     for l in f if l.strip()}
        with io.open(CANON_REL, encoding='utf-8') as f:
            base = {json.loads(l)['hand_id']: json.loads(l)
                    for l in f if l.strip()}
        distintos = [hid for hid, h in duras.items()
                     if abs(float(h.get('final_pot') or 0)
                            - float(base[hid].get('final_pot') or 0)) > 1e-6]
        assert not distintos, (
            'el fixture duro cambia el bote de %d manos, y no deberia: %r'
            % (len(distintos), distintos[:8]))
    finally:
        os.remove(ruta)
        os.rmdir(os.path.dirname(ruta))


def test_el_fixture_duro_contra_la_copia_real_en_las_1055_resueltas():
    """Y la comparacion mano a mano con la copia real, en las resueltas.

    Y lo que se compara NO es «las dos dan lo mismo» —no dan lo mismo, y no
    deben—: es que **la copia real resuelve el bote y el fixture no**. Y las
    dos reglas, medidas:

      · la copia real: su `final_pot` es el bote RESUELTO por la herramienta;
      · el fixture duro: su `final_pot` es el de la base de HOY.

    Y la relacion que se fija, y que es estable, es que **las manos en las
    que difieren son exactamente las manos en las que la base de hoy y la
    copia difieren**. Y no se fija el numero —que es el dato de A1 y puede
    cambiar cuando cierre las 203— sino la relacion, que es la regla.
    """
    if not os.path.exists(COPIA_REL):
        pytest.skip('la copia real no esta en el repo: `trabajo/'
                    'hands_db_edicion.jsonl`. Y se verifico contra ella en el '
                    'bloque 7e0b3c7, y aqui solo se fija que el fixture es '
                    'determinista y que su sha no cambia.')
    if not os.path.exists(DETALLE_REL):
        pytest.skip('el detalle de la aritmetica no esta en el repo: '
                    '`trabajo/botes_aritmetica.jsonl`')

    ruta, _informe = _construir(FIX.DUREZA_DURA, 'copia')
    try:
        with io.open(ruta, encoding='utf-8') as f:
            duras = {json.loads(l)['hand_id']: json.loads(l)
                     for l in f if l.strip()}
        with io.open(COPIA_REL, encoding='utf-8') as f:
            copia = {json.loads(l)['hand_id']: json.loads(l)
                     for l in f if l.strip()}
        with io.open(CANON_REL, encoding='utf-8') as f:
            base = {json.loads(l)['hand_id']: json.loads(l)
                    for l in f if l.strip()}
        detalle = {}
        with io.open(DETALLE_REL, encoding='utf-8') as f:
            for l in f:
                if l.strip():
                    d = json.loads(l)
                    detalle[d['hand_id']] = d

        # Y las manos resueltas son las del detalle, pero la copia puede
        # tener MENOS manos que la base canonica —A1 ha resuelto y quitado las
        # ambiguas—, de modo que la comparacion es sobre las manos COMUNES ✓.
        # Y las manos resueltas son las del detalle, pero la copia puede
        # tener MENOS manos que la base canonica —A1 ha resuelto y quitado las
        # ambiguas—, de modo que la comparacion es sobre las manos COMUNES ✓.
        resueltas = [hid for hid, d in detalle.items() if d.get('resuelto')]

        # (a) la copia real lleva el bote resuelto EN LA MAYORIA, y las
        # excepciones son de A1 ✓ —una subida no pagada cambia el neto, y
        # eso es de A1— ✓.
        comunes = [hid for hid in resueltas if hid in copia]
        con_resuelto = 0
        for hid in comunes:
            objetivo = float(detalle[hid]['resuelto'].get('pot_objetivo') or 0)
            if abs(float(copia[hid].get('final_pot') or 0) - objetivo) < 1e-6:
                con_resuelto += 1
        assert con_resuelto > len(comunes) * 0.9, (
            'la copia real solo lleva el bote resuelto en %d de %d manos, y '
            'eso es demasiado para que sean excepciones'
            % (con_resuelto, len(comunes)))

        # (b) el fixture NO resuelve ninguno: lleva el de la base de hoy.
        difieren_dura = set()
        difieren_base = set()
        for hid in comunes:
            if (abs(float(duras[hid].get('final_pot') or 0)
                    - float(copia[hid].get('final_pot') or 0)) > 1e-6):
                difieren_dura.add(hid)
            if (abs(float(base[hid].get('final_pot') or 0)
                    - float(copia[hid].get('final_pot') or 0)) > 1e-6):
                difieren_base.add(hid)
        assert difieren_dura == difieren_base, (
            'el fixture duro difiere de la copia real en %d manos, y la base '
            'de hoy difiere en %d, y las dos conjuntos tienen que ser el '
            'mismo: el fixture no resuelve botes'
            % (len(diferen_dura), len(diferen_base)))

        # (c) el fixture cubre TODAS las manos resueltas ✓, aunque algunas
        # esten en cuarentena (y por tanto no en la copia) ✓
        assert set(FIX.revisadas()) >= set(resueltas), (
            'el fixture no cubre todas las manos resueltas')
    finally:
        os.remove(ruta)
        os.rmdir(os.path.dirname(ruta))


import pytest   # noqa: E402

from tools.integrar_copia import _importes_de_decision as _decisiones  # noqa: E402
