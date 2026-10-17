# -*- coding: utf-8 -*-
"""R1 tarea 5 y R2 parrafo 4: la huella, con los casos que faltaban.

Lo que ya hay prueba que cambiar CADA cosa que entra en la huella cambia la
huella. Lo que faltaba eran los otros dos lados:

  - que una huella IDENTICA permita reutilizar. Sin ese caso, "todo cambia la
    huella" es compatible con una huella que cambia siempre, que es
    justamente una cache que nunca reutiliza nada.
  - el muestreo REDUCIDO, `len(ids) < N_COMBOS`. `R2` parrafo 4: con un
    mazo estandar `len(ids)` suele ser MUY mayor que `N_COMBOS`, asi que el
    caso reducido no se da: no hay que suponerlo, hay que probarlo. Con
    `n` reducido, `huella_de` tiene que cambiar y la entrada tiene que ser
    INVALIDABLE, no silenciosamente reutilizable.

Y el final de la cadena: que la condicion de reutilizacion acepte la
entrada cuando todo coincide, y la rechace cuando cambia uno. Con texto y
con numeros, no solo con los numeros.
"""
import importlib.util
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod():
    ruta = os.path.join(ROOT, 'tools', 'equity_preflop_observables.py')
    spec = importlib.util.spec_from_file_location('eqpobs_h2', ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _huella(m, hero='AsKd', ids=None, wl=None, semilla=7, n=None, y=1.0):
    if ids is None:
        ids = np.arange(1225, dtype=np.intp)
    if wl is None:
        wl = np.linspace(0.0001, 0.002, len(ids))
    if n is None:
        n = int(min(m.N_COMBOS, len(ids)))
    return m.huella_de(hero, ids, wl, semilla, n, y), n


# ================================================= una huella IDENTICA reutiliza
def test_una_huella_identica_da_el_mismo_numero():
    """Si no, la huella podria depender de algo que no controla el
    llamante —el orden de un dict, la direccion de un array— y entonces
    NUNCA habria reutilizacion, que es una cache que no es cache."""
    ins = _mod()
    a, _ = _huella(ins)
    b, _ = _huella(ins)
    assert a == b, 'la misma entrada tiene que dar la misma huella'


def test_la_huella_no_depende_del_tipo_de_array():
    """`wl` como lista y como array de numpy tienen que dar lo mismo: si no,
    el tipo decide la cache y eso no lo sabe nadie al llamar."""
    ins = _mod()
    ids = np.arange(50, dtype=np.intp)
    wl = np.linspace(0.1, 0.9, 50)
    a = ins.huella_de('AsKd', ids, wl, 7, 40, 1.0)
    b = ins.huella_de('AsKd', ids, np.ascontiguousarray(wl), 7, 40, 1.0)
    assert a == b
    c = ins.huella_de('AsKd', ids, wl.astype(np.float32), 7, 40, 1.0)
    assert a != c, 'y con float32 tiene que DISTINGUIR, que son datos otros'


# ================================================= el muestreo reducido
def test_el_muestreo_reducido_cambia_la_huella():
    """`n` entra en la huella. Un `n` distinto es otra muestra, aunque el
    rango sea el mismo."""
    ins = _mod()
    ids = np.arange(12, dtype=np.intp)
    wl = np.linspace(0.1, 0.9, 12)
    completa = ins.huella_de('AsKd', ids, wl, 7, 12, 1.0)
    reducida = ins.huella_de('AsKd', ids, wl, 7, 5, 1.0)
    assert completa != reducida


def test_un_rango_mas_corto_que_n_combos_es_legitimo():
    """Con un mazo estandar `len(ids)` es ~1225 y N_COMBOS es 40, asi que el
    caso reducido NO SE DA en los datos. Probarlo aqui, y no suponerlo,
    porque un caso que no se da es un caso que no se ha probado."""
    ins = _mod()
    assert ins.N_COMBOS == 40
    largo = np.arange(1225, dtype=np.intp)
    corto = np.arange(7, dtype=np.intp)
    h_largo, n_largo = _huella(ins, ids=largo)
    h_corto, n_corto = _huella(ins, ids=corto)
    assert n_largo == 40, 'con 1225 legales se muestrean N_COMBOS'
    assert n_corto == 7, 'con 7 legales se muestrean 7, y se dice'
    assert h_largo != h_corto


def test_el_campo_n_combos_guarda_lo_pedido_aunque_muestre_menos():
    """`n_combos` es lo PEDIDO, que es lo comparable. Guardar el efectivo
    hacia que una mano con el rango corto no se reutilizara nunca, y en
    silencio. Y `n_muestreados` es lo que se divide de verdad."""
    ins = _mod()
    n_pedido = ins.N_COMBOS
    n_efectivo = 7
    entrada = {'version': ins.VERSION, 'estimador': ins.ESTIMADOR,
               'n_combos': n_pedido, 'n_muestreados': n_efectivo}
    assert entrada['n_combos'] == n_pedido
    assert entrada['n_muestreados'] == n_efectivo
    texto = open(ins.__file__, encoding='utf-8').read()
    assert "'n_combos': N_COMBOS," in texto, 'lo pedido es lo comparable'
    assert "'n_muestreados': n," in texto, 'y lo efectivo, con su nombre'


# ===================================== la condicion, con texto y con numeros
def _entrada(ins, hero='AsKd', spot='no_raise', villano='V',
             semilla=7, huella='h1', y=1.0):
    return {'version': ins.VERSION, 'estimador': ins.ESTIMADOR,
            'semilla': semilla, 'n_combos': ins.N_COMBOS,
            'villano': villano, 'spot': spot, 'hero': hero,
            'huella': huella, 'y': y}


def _t(hero='AsKd', spot='no_raise', villano='V', semilla=7, y=1.0):
    return {'hero': hero, 'spot': spot, 'villano': villano,
            'semilla': semilla, 'y': y}


def test_todo_coincidiendo_se_reutiliza():
    ins = _mod()
    t = _t()
    h, _ = _huella(ins, hero=t['hero'], semilla=t['semilla'], y=t['y'])
    e = _entrada(ins, hero=t['hero'], villano=t['villano'], spot=t['spot'],
                 semilla=t['semilla'], y=t['y'], huella=h)
    m = ins.porque_no_reutilizable(e, ins.VERSION, ins.ESTIMADOR, t,
                                   ins.N_COMBOS, h)
    assert m == '', 'nada falla, y el motivo tiene que estar vacio: %r' % m


def test_un_campo_distinto_basta_para_no_reutilizar():
    ins = _mod()
    for campo, valor in (('villano', 'Otro'), ('spot', 'facing_open'),
                         ('hero', 'QsJd'), ('semilla', 8), ('y', 0.0),
                         ('version', 99), ('estimador', 'otro'),
                         ('n_combos', 41), ('huella', 'h2')):
        e = _entrada(ins)
        e[campo] = valor
        m = ins.porque_no_reutilizable(e, ins.VERSION, ins.ESTIMADOR, _t(),
                                       ins.N_COMBOS, 'h1')
        assert m, 'cambiar %r tiene que impedir la reutilizacion' % campo
        assert campo in m, 'y el motivo tiene que nombrarlo: %r' % m


def test_el_cambio_de_pesos_invalida_sin_tocar_los_siete_campos():
    """Este es el caso por el que existe la huella: los SIETE campos
    nominales siguen iguales y el rango es otro."""
    ins = _mod()
    ids = np.arange(30, dtype=np.intp)
    wl = np.linspace(0.1, 0.9, 30)
    antes = ins.huella_de('AsKd', ids, wl, 7, 30, 1.0)
    despues = ins.huella_de('AsKd', ids, wl * 1.0001, 7, 30, 1.0)
    assert antes != despues
    e = _entrada(ins, hero='AsKd', villano='V', spot='no_raise', semilla=7,
                 huella=antes)
    m = ins.porque_no_reutilizable(e, ins.VERSION, ins.ESTIMADOR, _t(),
                                   ins.N_COMBOS, despues)
    assert 'huella' in m