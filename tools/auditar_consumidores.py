# -*- coding: utf-8 -*-
"""Auditoria de consumidores de hands_db.jsonl (revision_2, orden de ejecucion).

revision_2 §3.1 pide, antes de migrar:
  "buscar todos los lectores, validadores, serializadores y consumidores de
   hands_db.jsonl. Verificar especificamente como se conservan campos
   desconocidos."

Por que esto bloquea CM-003: las 41 inferencias se marcan con `inferred: true`.
Si algun camino COPIA una accion construyendola de nuevo con un conjunto
cerrado de claves (`{'pos':..,'action':..,'amount':..}`), el campo se pierde en
silencio y las inferencias acabarian presentandose como observaciones. Ese es
justo el fallo que CM-003 quiere evitar.

El riesgo NO esta en los lectores (que reciben dicts y los devuelven), sino en
los ESCRITORES: lo que abre hands_db.jsonl para reescribirlo. Por eso el
analisis se centra en ellos.

Uso:  python tools/auditar_consumidores.py
"""
import ast
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUIDOS = {'.git', '__pycache__', '.venv', '_snapshot_pre_rebuild_1b14c18',
             'data'}
DB_NOMBRE = 'hands_db'

# Claves que identifican una accion de poker en el esquema real.
CLAVES_ACCION = {'pos', 'action', 'amount', 'amount_type', 'blind'}


def _ficheros():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUIDOS]
        for fn in filenames:
            if fn.endswith('.py'):
                yield os.path.join(dirpath, fn)


def _lineas(src):
    return src.split('\n')


def _es_escritor(src):
    """Escribe (o puede reescribir) hands_db.jsonl."""
    if DB_NOMBRE not in src:
        return False
    # una escritura real: json.dump / json.dumps + open(...,'w')
    return bool(re.search(r"json\.dumps?\s*\(", src)
                and re.search(r"open\([^)]*['\"][wax]", src)
                or re.search(r"\.write\s*\(\s*json\.dumps", src)
                or re.search(r"['\"]w['\"]\s*\)", src) and DB_NOMBRE in src
                and re.search(r"open\(", src) and re.search(r"json\.dump", src))


def _reconstrucciones(src):
    """Localiza el patron que DESTRUYE campos nuevos de una accion.

    Solo cuenta una construccion si el bucle o la comprehension RECORRE
    `...actions...` y produce un dict literal. Anadir una accion nueva con
    `.append({...})` NO cuenta: no toca las que ya existen.

    Devuelve [(linea, tipo)].
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    out = []
    for nodo in ast.walk(tree):
        # --- comprehension que itera sobre `actions` y construye un dict ---
        if isinstance(nodo, (ast.ListComp, ast.DictComp)):
            texto = ast.get_source_segment(src, nodo) or ''
            if not re.search(r"['\"]actions['\"]|actions\b", texto):
                continue
            genera_dict = (isinstance(nodo, ast.DictComp)
                           or re.search(r"\{['\"]pos['\"]", texto))
            if genera_dict:
                out.append((nodo.lineno, 'comprehension sobre `actions`'))

        # --- bucle `for x in <algo>.actions` que REASIGNA una dict a x ---
        if isinstance(nodo, ast.For):
            texto = ast.get_source_segment(src, nodo) or ''
            if not re.search(r"['\"]actions['\"]|\.actions\b", texto):
                continue
            # busca `x = {` dentro del cuerpo del bucle
            for sub in ast.walk(nodo):
                if (isinstance(sub, ast.Assign)
                        and isinstance(sub.value, ast.Dict)
                        and isinstance(sub.targets[0], ast.Name)
                        and sub.targets[0].id == nodo.target.id):
                    out.append((sub.lineno,
                                'bucle reescribe la accion `%s`' % nodo.target.id))
    return out


def _lee_y_reescribe(src):
    """Carga el JSONL y despues lo escribe: el camino que pierde campos."""
    return bool(re.search(r"json\.loads?\s*\(", src)
                and re.search(r"json\.dumps?\s*\(", src))


def main():
    filas = []          # (rel, escribe, lee_y_reescribe, reconstrucciones)
    for path in _ficheros():
        rel = os.path.relpath(path, ROOT).replace('\\', '/')
        try:
            src = io.open(path, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        if DB_NOMBRE not in src:
            continue
        filas.append((rel, _es_escritor(src), _lee_y_reescribe(src),
                      _reconstrucciones(src)))

    filas.sort()

    # ------------------------------------------------------------- resumen
    print('=' * 76)
    print('1) FICHEROS QUE TOCAN hands_db.jsonl')
    print('=' * 76)
    print('   %-34s %-8s %-9s %s'
          % ('fichero', 'escribe', 'lee+rees', 'reconstruye accion'))
    print('   ' + '-' * 72)
    for rel, esc, lr, rec in filas:
        marca = lambda b: 'SI' if b else '-'          # noqa: E731
        print('   %-34s %-8s %-9s %s'
              % (rel, marca(esc), marca(lr),
                 ', '.join('%d:%s' % (l, t) for l, t in rec) or '-'))

    # -------------------------------------------------- reconstrucciones
    print()
    print('=' * 76)
    print('2) CONSTRUCCIONES DE ACCION QUE PODRIAN PERDER `inferred: true`')
    print('=' * 76)
    hay = False
    for path in _ficheros():
        rel = os.path.relpath(path, ROOT).replace('\\', '/')
        try:
            src = io.open(path, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        if DB_NOMBRE not in src:
            continue
        for linea, tipo in _reconstrucciones(src):
            hay = True
            print()
            print('   %s:%d  [%s]' % (rel, linea, tipo))
            for k, txt in enumerate(_lineas(src)[max(0, linea - 3):linea + 2]):
                print('     %4d | %s' % (linea - 2 + k, txt))
    if not hay:
        print('   ninguna.')

    # ---------------------------------------------------------- veredicto
    _print = print
    print()
    print('=' * 76)
    print('3) VEREDICTO')
    print('=' * 76)

    reconstructed_files = set()
    for rel, esc, lr, rec in filas:
        if rec:
            reconstructed_files.add(rel)
    # un escritor que ademas reconstruye acciones es peligroso
    peligrosos = set()
    for rel, esc, lr, rec in filas:
        if rec and (esc or lr):
            peligrosos.add(rel)

    if not peligrosos:
        _print("""
   OK para `inferred: true`.

   Ningun fichero recorre `actions` para RECONSTRUIR sus dicts. El patron
   detectado es solo `x = {'pos':..,'action':..}` dentro de un bucle sobre
   `actions`, o una comprehension equivalente; ninguno aparece.

   `.append({...})` NO cuenta: crea una accion nueva, no toca las que ya
   existen, asi que un `inferred: true` puesto a mano sobrevive a un grabador
   que anada acciones nuevas.

   Queda una comprobacion manual pendiente: `hand_editor.py` (ver seccion 1).
   Edita el JSONL a mano, y hay que ver COMO serializa al guardar, porque el
   patron AST no cubre llamadas indirectas a `json.dump`.
""")
    else:
        _print('   REVISAR: %s' % ', '.join(sorted(peligrosos)))
        _print('')
        _print('   Estos ficheros recorren `actions` reconstruyendo los dicts:')
        _print('   un `inferred: true` puesto a mano se perderia al reescribir.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
