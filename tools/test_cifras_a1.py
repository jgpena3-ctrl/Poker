# -*- coding: utf-8 -*-
"""LAS CIFRAS DE A1, Y POR QUE NO SE PINAN.

Y el problema, MEDIDO: **A1 ha seguido resolviendo manos** ✓, y el numero de
resueltas se ha movido ✓. Y tres tests de A2 fallaron por eso ✓ —no por un
defecto, sino por un numero de A1 que cambio debajo— ✓.

Y la regla que sale, y que este fichero vigila ✓:

> **Una cifra de A1 en un test o en un documento de A2 CADUCA SOLA** ✓, y un
> test que falla por un dato que no es un defecto es un test que ENSUCIA ✓.
> Y lo que se fija es la RELACION ✓, no el numero ✓.

## Y QUE NUMEROS SE PUEDEN PINAR

Y hay una lista corta de numeros que SI son estables ✓, y son los de la base
CANONICA, que esta congelada ✓:

  · 1258 — las lineas de la base canonica ✓;
  · 877  — la ventana fiable de la base de HOY ✓;
  · 921  — el control de regresion de la base de HOY ✓.

Y lo que NO se puede es el **conteo de manos resueltas por A1** ✓, que es de
A1 ✓ y se mueve ✓. Y la comprobacion es dinamica ✓: se mide el conteo en el
momento ✓ y se busca en los tests ✓, de modo que el dia que A1 resuelva mas ✓,
el numero viejo queda marcado ✓.
"""
import ast
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

# Y los numeros de la base CANONICA, que estan congelados ✓ y se pueden
# nombrar ✓.
ESTABLES = (1258, 877, 921)


def _conteo_de_resueltas():
    """Cuantas manos ha resuelto la herramienta, MEDIDO ahora.

    Y se mide en el momento ✓, y no se guarda ✓: porque ese numero es
    justamente el que se mueve ✓, y un numero guardado en un test es
    exactamente lo que hay que evitar ✓.
    """
    detalle = os.path.join(ROOT, 'trabajo', 'botes_aritmetica.jsonl')
    if not os.path.exists(detalle):
        return None
    n = 0
    with io.open(detalle, encoding='utf-8') as f:
        for l in f:
            if not l.strip():
                continue
            if json.loads(l).get('resuelto'):
                n += 1
    return n


def _ficheros_de_test():
    for carpeta in ('motor', 'tools', 'recorder'):
        base = os.path.join(ROOT, carpeta)
        for nombre in sorted(os.listdir(base)):
            if nombre.startswith('test_') and nombre.endswith('.py'):
                yield os.path.join(carpeta, nombre)


def test_ningun_test_pina_el_conteo_de_resueltas_de_a1():
    """Y que el conteo de A1 no aparezca como literal en ningun test.

    Y el motivo de que la busqueda sea por el ARBOL y no por el texto ✓: en
    un TEXTO un `1258` puede ser el de la base canonica ✓ —que es estable— ✓
    o el de la copia ✓ —que es de A1— ✓, y el numero no los distingue ✓.
    Y en un ARBOL lo que se mira es el VALOR y el CONTEXTO ✓.

    Y la lista de estables ✓ es la de la base canonica ✓, que esta congelada ✓.
    """
    n = _conteo_de_resueltas()
    if n is None:
        return          # sin el detalle de A1, no hay nada que comprobar
    assert n not in ESTABLES, (
        'el conteo de resueltas ha coincidido con un numero estable (%d), y '
        'entonces esta comprobacion no distinguiria nada' % n)

    culpables = []
    for ruta in _ficheros_de_test():
        if os.path.abspath(ruta) == os.path.abspath(__file__):
            continue
        with io.open(ruta, encoding='utf-8') as f:
            arbol = ast.parse(f.read())
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Constant)
                    and isinstance(nodo.value, int)
                    and nodo.value == n):
                culpables.append('%s:%d' % (os.path.relpath(ruta, ROOT),
                                              nodo.lineno))
    assert not culpables, (
        'el conteo de manos resueltas por A1 (%d) aparece como literal en %d '
        'sitio(s):\n   %s\n\nY ese numero es de A1 y SE MUEVE ✓, y un test '
        'que falla por un dato que no es un defecto es un test que ensucia ✓. '
        'Lo que se fija es la RELACION ✓.'
        % (n, len(culpables), '\n   '.join(culpables)))


def test_el_registro_no_tiene_la_cifra_de_a1():
    """Y que el registro nombre la TAREA y no su numero.

    Y el motivo: un registro es lo que se lee para saber que queda ✓, y si
    su numero esta viejo ✓, lo que dice esta viejo ✓, y lo que esta viejo no
    se lee ✓.

    Y la comprobacion es sobre el TEXTO ✓, y no sobre el arbol ✓, porque aqui
    lo que se busca es una MENCION ✓, que esta en el texto ✓.
    """
    reg = os.path.join(ROOT, 'DOCS', 'ESTADO_DEL_TRABAJO.md')
    with io.open(reg, encoding='utf-8') as f:
        texto = f.read()
    n = _conteo_de_resueltas()
    if n is not None:
        assert str(n) not in texto, (
            'el registro menciona el conteo de manos resueltas por A1 (%d), y '
            'ese numero se mueve ✓. Y lo que se escribe es LA TAREA ✓.'
            % n)
    # y el texto que si tiene que estar
    assert 'las manos sin resolver' in texto, (
        'el registro tiene que nombrar la TAREA de A1, y no su numero')
    assert 'se mueve' in texto, (
        'y tiene que decir que el numero se mueve, que es el motivo ✓')
