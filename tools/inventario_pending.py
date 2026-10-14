# -*- coding: utf-8 -*-
"""F6.1.a — Inventario de `pending` (NO modifica nada).

revision_2 pide, antes de tocar nada: "identifica todos los productores,
consumidores y puntos de limpieza de pending... deja documentado qué significa
cada estado y quién es responsable de resolverlo".

Lo que este script busca, en orden de importancia:

  1. Quién CALCULA el conjunto de pendientes. Si hay mas de una
     implementacion, hay mas de una fuente de verdad y pueden divergir.
  2. Quién lo CONSUME.
  3. Si el parametro de entrada y la clave de salida son el mismo dato
     recalculado (que es lo que sospechamos).
  4. Si el vocabulario de roles (`PENDING`, `AGGRESSOR`...) esta vivo o muerto.

Uso:  python tools/inventario_pending.py
"""
import ast
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUIDOS = {'.git', '__pycache__', '.venv', '_snapshot_pre_rebuild_1b14c18',
             '_backup_aplicar_correcciones', 'data'}
ROLES = ('AGGRESSOR', 'CHECKER', 'CALLER', 'PENDING')


def ficheros():
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in EXCLUIDOS]
        for fn in fns:
            if fn.endswith('.py'):
                yield os.path.join(dp, fn)


def rel(p):
    return os.path.relpath(p, ROOT).replace('\\', '/')


# ---------------------------------------------------------------------------
# 1. quien CALCULA pendientes
# ---------------------------------------------------------------------------
# Una "fuente" de pending se detecta por construir una lista de posiciones a
# partir de alguna de estas señales:
#   - `not in acted` / `not in ya_actuaron`  (no ha actuado en la calle)
#   - `.get('active')` / `_state') == 'activo'`  (sigue en la mano)
#   - `actions[i+1:]`                          (posiciones posteriores en la lista)
PATRONES_PEND = {
    'no_ha_actuado_en_la_calle': re.compile(
        r"not in\s+(acted|ya_actuaron|actuaron)\b"),
    'sigue_activo_en_la_mano': re.compile(
        r"\.get\('active'\)|_state'\)\s*(!=|==)\s*'activo'"),
    'posiciones_posteriores_en_la_lista': re.compile(
        r"\w+\[\s*\w+\s*\+\s*1\s*:\s*\]"),
}

# este propio script contiene los patrones como texto, asi que se excluye
YO = 'tools/inventario_pending.py'


def sources():
    out = []
    for path in ficheros():
        r = rel(path)
        if r == YO:
            continue
        try:
            src = io.open(path, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        # solo los que de verdad participan: tocan `pending` o `clasify_villains`
        if 'pending' not in src and 'clasify_villains' not in src:
            continue
        if r.startswith('motor/test_'):
            continue                      # los tests no son fuentes
        lineas = src.split('\n')
        for etiqueta, patron in PATRONES_PEND.items():
            for k, linea in enumerate(lineas, 1):
                if linea.strip().startswith('#'):
                    continue
                if patron.search(linea):
                    out.append((r, k, etiqueta, linea.strip()[:76]))
    return out


# ---------------------------------------------------------------------------
# 2. productores y consumidores de la clave 'pending'
# ---------------------------------------------------------------------------
def consumidores():
    lecturas, escrituras = [], []
    for path in ficheros():
        r = rel(path)
        try:
            src = io.open(path, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        lineas = src.split('\n')
        for k, linea in enumerate(lineas, 1):
            s = linea.strip()
            if s.startswith('#'):
                continue
            if re.search(r"['\"]pending['\"]\s*:", s):
                escrituras.append((r, k, s[:76]))
            elif re.search(r"\.get\(\s*['\"]pending['\"]|\[\s*['\"]pending['\"]\s*\]", s):
                lecturas.append((r, k, s[:76]))
    return escrituras, lecturas


# ---------------------------------------------------------------------------
# 3. el parametro de entrada
# ---------------------------------------------------------------------------
def parametro_entrada():
    hits = []
    for path in ficheros():
        r = rel(path)
        try:
            src = io.open(path, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        for k, linea in enumerate(src.split('\n'), 1):
            if 'pending_positions' in linea and not linea.strip().startswith('#'):
                hits.append((r, k, linea.strip()[:76]))
    return hits


# ---------------------------------------------------------------------------
# 4. vocabulario de roles
# ---------------------------------------------------------------------------
def roles():
    definidos, usados = {}, []
    for path in ficheros():
        r = rel(path)
        if r == YO:
            continue
        try:
            src = io.open(path, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        for k, linea in enumerate(src.split('\n'), 1):
            m = re.match(r"^(%s)\s*=\s*'([a-z_]+)'" % '|'.join(ROLES), linea)
            if m:
                definidos[m.group(1)] = (r, k, m.group(2))
    for path in ficheros():
        r = rel(path)
        if r == YO:
            continue
        try:
            src = io.open(path, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        for k, linea in enumerate(src.split('\n'), 1):
            s = linea.strip()
            if s.startswith('#') or re.match(r"^%s\s*=" % '|'.join(ROLES), s):
                continue
            for rol in ROLES:
                if re.search(r"\b%s\b" % rol, s):
                    usados.append((r, k, rol, s[:70]))
    return definidos, usados


def main():
    print('=' * 78)
    print('F6.1.a  INVENTARIO DE `pending`   (solo lectura, no modifica nada)')
    print('=' * 78)

    # ---------------------------------------------------------------- 1
    srcs = sources()
    print()
    print('1) QUIEN CALCULA EL CONJUNTO DE PENDIENTES')
    print('-' * 78)
    implementaciones = {}
    for r, k, etiqueta, txt in srcs:
        implementaciones.setdefault(r, set()).add(etiqueta)
    for r in sorted(implementaciones):
        print('   %s' % r)
        for e in sorted(implementaciones[r]):
            for r2, k2, _e, txt in srcs:
                if r2 == r and _e == e:
                    print('        L%-5d %-36s %s' % (k2, e, txt))
                    break
    print()
    distintos = len(implementaciones)
    print('   IMPLEMENTACIONES DISTINTAS: %d' % distintos)

    # ---------------------------------------------------------------- 2
    esc, lec = consumidores()
    print()
    print('2) QUIEN ESCRIBE LA CLAVE "pending"')
    print('-' * 78)
    for r, k, s in esc:
        print('   %-30s L%-5d %s' % (r, k, s))
    if not esc:
        print('   (ninguno por literales; se construye en un dict)')

    print()
    print('3) QUIEN LEE LA CLAVE "pending"')
    print('-' * 78)
    for r, k, s in lec:
        print('   %-30s L%-5d %s' % (r, k, s))
    if not lec:
        print('   ninguno')

    # ---------------------------------------------------------------- 4
    print()
    print('4) PARAMETRO DE ENTRADA `pending_positions`')
    print('-' * 78)
    for r, k, s in parametro_entrada():
        marca = '' if not r.startswith('motor/test_') else '   [test]'
        print('   %-30s L%-5d %s%s' % (r, k, s, marca))

    # ---------------------------------------------------------------- 5
    print()
    print('5) VOCABULARIO DE ROLES (PENDING, AGGRESSOR, CHECKER, CALLER)')
    print('-' * 78)
    defs, usos = roles()
    for rol in ROLES:
        if rol not in defs:
            print('   %-10s (no definido)' % rol)
            continue
        r, k, valor = defs[rol]
        reales = [u for u in usos if u[2] == rol]
        prod = [u for u in reales if not u[0].startswith('motor/test_')]
        estado = 'MUERTO (solo lo usa un test)' if not prod else \
                 ('usado en %d sitio(s) de produccion' % len(prod))
        print('   %-10s = %-10s definido en %s:%d   -> %s'
              % (rol, valor, r, k, estado))
        for u in prod[:3]:
            print('               %s:%d  %s' % (u[0], u[1], u[3]))

    print()
    print('=' * 78)
    print('VEREDICTO PRELIMINAR')
    print('=' * 78)
    print("""
   `classify_villains` devuelve 'pending' (salida) y recibe
   `pending_positions` (entrada). El llamador calcula el conjunto y la funcion
   lo vuelve a filtrar. Eso ya son dos codigos para el mismo dato.

   Encima hay un vocabulario de roles (`PENDING`, `AGGRESSOR`, `CHECKER`,
   `CALLER`) que `classify_villains` NUNCA emite: la funcion devuelve claves
   separadas, no etiquetas de rol. El vocabulario solo lo importa un test.
   Son dos vocabularios coexistiendo, y solo uno describe lo que el codigo
   hace de verdad.

   Este script no propone el contrato canonico: solo deja constancia de como
   esta hoy. Ese contrato es F6.1.b.
""")
    return 0


if __name__ == '__main__':
    sys.exit(main())
