# -*- coding: utf-8 -*-
"""Inventario de la API publica de rules.py y sus consumidores (F5, paso 1).

revision_2 pide inventariar las funciones publicas de `rules.py` y sus
consumidores antes de definir contratos. Este script:

  1. lista el API publico (no `_`-privado) con firma y linea;
  2. lista los DATOS que consume (clases y constantes);
  3. localiza cada consumidor en el repo;
  4. marca los simbolos sin consumidor y los consumidores sin test.

No modifica nada: es un inventario reproducible.
"""
import ast
import collections
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _api(path):
    tree = ast.parse(io.open(path, encoding='utf-8').read())
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name.startswith('_'):
                continue
            out.append((node.name, node.lineno, type(node).__name__))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith('_'):
                    if t.id.isupper():
                        out.append((t.id, node.lineno, 'CONST'))
    return out


def main():
    rules = os.path.join(ROOT, 'motor', 'rules.py')
    api = _api(rules)

    print('=' * 74)
    print('API PUBLICO DE rules.py  (%d simbolos)' % len(api))
    print('=' * 74)
    for name, line, kind in api:
        print('  %-22s L%-4d %s' % (name, line, kind))

    # ---- consumidores -------------------------------------------------
    print()
    print('=' * 74)
    print('CONSUMIDORES')
    print('=' * 74)
    uso = collections.defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in ('.git', '__pycache__', '.venv',
                                    '_snapshot_pre_rebuild_1b14c18')]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT)
            if rel == 'motor\\rules.py' or rel == 'motor/rules.py':
                continue
            try:
                txt = io.open(p, encoding='utf-8').read()
            except (OSError, UnicodeDecodeError):
                continue
            for name, _l, _k in api:
                if re.search(r'\b%s\b' % re.escape(name), txt):
                    uso[name].append(rel)

    sin_consumidor = []
    for name, line, kind in api:
        users = [u for u in uso.get(name, [])]
        if not users:
            sin_consumidor.append(name)
            marca = '  <-- SIN CONSUMIDOR'
        else:
            tests = [u for u in users if 'test' in u]
            prod = [u for u in users if 'test' not in u]
            marca = '  prod=%d test=%d' % (len(prod), len(tests))
            if not tests:
                marca += '  <-- SIN TEST DIRECTO'
        print('  %-22s %s' % (name, marca))
        for u in sorted(set(uso.get(name, []))):
            print('        %s' % u)

    print()
    print('=' * 74)
    print('PARA F5')
    print('=' * 74)
    print('  simbolos sin consumidor : %d  %s'
          % (len(sin_consumidor), sin_consumidor))
    print()
    print('  Candidatos a contrato (superficie publica con consumidores):')
    for name, line, kind in api:
        if uso.get(name):
            print('    %s' % name)
    return 0


if __name__ == '__main__':
    sys.exit(main())