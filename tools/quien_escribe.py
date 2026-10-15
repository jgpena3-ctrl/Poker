# -*- coding: utf-8 -*-
"""¿Que modulos ESCRIBEN en hands_db.jsonl? Instrumento, no busqueda.

TRES formas de escribir que un `open()` se pierde, y las tres estan en este
repo:

  1. rutas en cadena:  DB_NAME = 'hands_db.jsonl'
                       DB_PATH = os.path.join(ROOT, 'data', DB_NAME)
     -> hace falta cierre transitivo de nombres.
  2. escritura indirecta:  shutil.copy2(backup, DB_PATH)
     -> el que ESCRIBE es el SEGUNDO argumento, y no hay ningun open().
  3. atributos:  self.output_path, con el valor puesto en otro sitio.

VERIFICADO CONTRA SI MISMO antes de usarse. Si el instrumento no encuentra lo
que se le da buscado, no puede usarse para decir que no hay nada: eso es
`RESUMEN_SECCION.md` §8.
"""
import ast
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OBJETIVO = 'hands_db.jsonl'
MODOS_ESCRITURA = {'w', 'a', 'x', 'r+', 'w+', 'a+', 'x+', 'wb', 'ab', 'xb',
                   'w+b', 'a+b', 'r+b', 'wb+', 'ab+', 'rb+', 'wb+', 'w+b'}
COPIAS = ('copy2', 'copy', 'copyfile', 'move', 'replace', 'rename')


def _constante_menciona(nodo):
    return any(isinstance(s, ast.Constant) and isinstance(s.value, str)
               and OBJETIVO in s.value for s in ast.walk(nodo))


def _nodos_de_ambito(arbol):
    """Los nodos que pertenecen a ESTE ambito y no a uno interior.

    De nivel superior se walks las sentencias que no sean def/class. Dentro de
    una funcion se walks todo su cuerpo.

    Sin esto, `motor/learn.py` sigue saliendo como escritor: `load_hands()`
    tiene `path = path or DB_PATH` —alias legitimo— y ese `path` contaminaba
    las rutas de modulo, con las que `main()`aba`preflop_stats.json`.
    """
    if isinstance(arbol, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return list(ast.walk(arbol))
    nodos = []
    for st in arbol.body:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef,
                           ast.ClassDef)):
            continue
        nodos.extend(ast.walk(st))
    return nodos


def _rutas(arbol, semilla=frozenset()):
    """Cierre transitivo dentro de UN ambito.

    `semilla` son las rutas que ya se conocen de fuera del ambito (las de
    modulo). Sin ella, una funcion que hace `db = tmp_path / DB_NAME` no
    resolvia el alias: `DB_NAME` es de modulo y `_rutas` de la funcion sola no
    lo ve.
    """
    conocidas, changed = set(semilla), True
    nodos = _nodos_de_ambito(arbol)
    nombres = {n.id for n in nodos if isinstance(n, ast.Name)}
    atributos = {a.attr for a in nodos if isinstance(a, ast.Attribute)}
    while changed:
        changed = False
        for nodo in nodos:
            if not isinstance(nodo, ast.Assign):
                continue
            valor_usa = any(
                isinstance(s, ast.Name) and s.id in conocidas
                for s in ast.walk(nodo.value))
            if not (_constante_menciona(nodo.value) or valor_usa):
                continue
            for t in nodo.targets:
                nuevos = []
                if isinstance(t, ast.Name):
                    nuevos = [t.id]
                elif isinstance(t, ast.Attribute) and (t.attr in nombres
                                                      or t.attr in atributos):
                    nuevos = [t.attr]
                for x in nuevos:
                    if x not in conocidas:
                        conocidas.add(x)
                        changed = True
    return conocidas


def _atributos_de_ruta(arbol, globales):
    """Atributos (`self.output_path`) asignados desde la base, en CUALQUIER
    ambito.

    Un atributo de instancia es cross-scope por naturaleza: se asigna en
    `__init__` y se usa en `save()`. Si solo se mirara el ambito del uso, los
    tres recorder —los que de verdad escriben la base mientras se juega—
    desaparecerian de la lista.

    Y el valor suele ser un alias: los tres hacen
    `self.output_path = OUTPUT_PATH`, y es `OUTPUT_PATH` —constante de
    modulo— la que menciona `hands_db.jsonl`. Por eso aqui tambien hace
    falta mirar si el valor USA una ruta ya conocida.
    """
    atributos = {a.attr for a in ast.walk(arbol) if isinstance(a, ast.Attribute)}
    salida = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        usa_una = any(isinstance(s, ast.Name) and s.id in globales
                      for s in ast.walk(nodo.value))
        if not (_constante_menciona(nodo.value) or usa_una):
            continue
        for t in nodo.targets:
            if isinstance(t, ast.Attribute) and t.attr in atributos:
                salida.add(t.attr)
    return salida


def _nombres_de_ruta(arbol):
    """Rutas de modulo + rutas locales de cada funcion, por ambito.

    Tres conjuntos, y la separacion es lo que hace que el instrumento no
    invente ni esconda:
      - las de MODULO, que NO bajan dentro de las funciones
      - las LOCALES de cada funcion
      - los ATRIBUTOS, que si son cross-scope (ver arriba)
    """
    globales = _rutas(arbol)
    atributos = _atributos_de_ruta(arbol, globales)
    por_ambito = {id(arbol): set(globales) | atributos}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            por_ambito[id(nodo)] = (set(globales) | atributos
                                    | _rutas(nodo, globales))
    return por_ambito


def _es_ruta(nodo, rutas):
    return any(isinstance(s, ast.Name) and s.id in rutas
               or isinstance(s, ast.Attribute) and s.attr in rutas
               for s in ast.walk(nodo))


def _funciones_que_escriben_por_parametro(arbol):
    """`nombre -> indice_del_parametro_que_escribe`.

    Sin esto, el inventario se queda viejo en cuanto alguien envuelve la
    escritura en un helper —que es lo que acabo de hacer con
    `hand_editor._guardar_base()`— y un inventario viejo es peor que ninguno:
    da por cerrado un canal que se ha vuelto a abrir.

    El criterio: dentro de la funcion, una escritura cuyo DESTINO (el segundo
    argumento de `copy2`, el de `os.replace`, el path de `open`) es uno de sus
    parametros. Esa funcion escribe lo que le pasen.
    """
    res = {}
    for f in ast.walk(arbol):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = f.args
        params = ([a.arg for a in args.posonlyargs] + [a.arg for a in args.args]
                  + [a.arg for a in args.kwonlyargs])
        if not params:
            continue
        for nodo in ast.walk(f):
            if not isinstance(nodo, ast.Call):
                continue
            fn = nodo.func
            nombre = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else None)
            destino = None
            if nombre in COPIAS and len(nodo.args) >= 2:
                destino = nodo.args[1]
            elif nombre == 'open' and nodo.args:
                modo = nodo.args[1] if len(nodo.args) > 1 else None
                if getattr(modo, 'value', None) in MODOS_ESCRITURA:
                    destino = nodo.args[0]
            if destino is None:
                continue
            for sub in ast.walk(destino):
                if isinstance(sub, ast.Name) and sub.id in params:
                    res.setdefault(f.name, params.index(sub.id))
    return res


def _clasifica(arbol):
    """[(linea, 'escribe'|'lee'|'indeterminado'|'tmp', detalle)] por ambito."""
    por_ambito = _nombres_de_ruta(arbol)
    helpers = _funciones_que_escriben_por_parametro(arbol)
    eventos = []

    def _ambitos_de(nodo):
        """El ambito de un nodo: la funcion mas cercana que lo contiene."""
        return None

    # Recorrer por funcion, no por todo el arbol: `ast.walk` mezclaria los
    # `path` de dos funciones distintas.
    funciones = [n for n in ast.walk(arbol)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    PARTE = [(arbol, por_ambito.get(id(arbol), set()), True)]
    for f in funciones:
        PARTE.append((f, por_ambito.get(id(f), set()), False))

    for cuerpo, rutas, es_modulo in PARTE:
        nodos = _nodos_de_ambito(cuerpo)
        for nodo in nodos:
            if not isinstance(nodo, ast.Call):
                continue
            eventos.extend(_eventos_de(nodo, rutas, cuerpo))
            eventos.extend(_eventos_helper(nodo, rutas, helpers, cuerpo))
    return eventos


def _eventos_helper(nodo, rutas, helpers, cuerpo):
    """La escritura a traves de un helper: `_guardar_base(manos, DATA_PATH)`.

    Si `helpers` dice que ese helper escribe su parametro `n`, y el argumento
    `n` es una ruta, entonces la llamada ES una escritura de la base.
    """
    f = nodo.func
    nombre = f.attr if isinstance(f, ast.Attribute) else (
        f.id if isinstance(f, ast.Name) else None)
    if nombre not in helpers:
        return []
    indice = helpers[nombre]
    if len(nodo.args) <= indice:
        return []
    arg = nodo.args[indice]
    if not _es_ruta(arg, rutas):
        return []
    tipo = 'tmp' if _es_tmp(arg, cuerpo) else 'escribe'
    return [(nodo.lineno, tipo, '%s(..., <LA BASE>)' % nombre)]


def _es_tmp(nodo, cuerpo=None):
    """¿La ruta sale de `tmp_path`? Entonces es una COPIA MUTADA de test.

    `motor/test_cm004.py:370` hace `db = tmp_path / 'hands_db.jsonl'` y luego
    `V.DB_PATH = str(db)`. Escribe un fichero que se llama como la base y no
    es la base: es un mutante para probar el verificador. Sin esta categoria
    salia como "escritor de la base", que es exactamente el falso positivo en
    la direccion peligrosa que este instrumento tiene que evitar.

    Mirar solo el uso no basta: en el `open(db, 'w')` no aparece `tmp_path`.
    Hay que mirar la ASIGNACION de `db` dentro del mismo ambito.
    """
    def _menciona_tmp(x):
        return any(isinstance(s, ast.Name) and 'tmp' in s.id.lower()
                   for s in ast.walk(x))
    if _menciona_tmp(nodo):
        return True
    if cuerpo is None:
        return False
    for sub in ast.walk(nodo):
        if isinstance(sub, ast.Name):
            for st in ast.walk(cuerpo):
                if isinstance(st, ast.Assign) and _menciona_tmp(st.value):
                    if any(isinstance(t, ast.Name) and t.id == sub.id
                           for t in st.targets):
                        return True
    return False


def _eventos_de(nodo, rutas, cuerpo=None):
    f = nodo.func
    nombre = f.attr if isinstance(f, ast.Attribute) else (
        f.id if isinstance(f, ast.Name) else None)
    if nombre is None:
        return []

    def _destino(idx):
        return nodo.args[idx] if len(nodo.args) > idx else None

    if nombre in COPIAS and len(nodo.args) >= 2 and _es_ruta(nodo.args[1], rutas):
        tipo = 'tmp' if _es_tmp(nodo.args[1], cuerpo) else 'escribe'
        return [(nodo.lineno, tipo, '%s(..., <LA BASE>)' % nombre)]
    if nombre in COPIAS and len(nodo.args) >= 1 and _es_ruta(nodo.args[0], rutas):
        return [(nodo.lineno, 'indeterminado', '%s(<LA BASE>, ...)' % nombre)]
    if nombre in ('write_text', 'write_bytes'):
        if nodo.args and _es_ruta(nodo.args[0], rutas):
            return [(nodo.lineno, 'escribe', nombre + '(<LA BASE>)')]
        return []
    if nombre != 'open' or not nodo.args:
        return []
    if not _es_ruta(nodo.args[0], rutas):
        return []

    modo = nodo.args[1] if len(nodo.args) > 1 else next(
        (k.value for k in nodo.keywords if k.arg == 'mode'), None)
    valor = getattr(modo, 'value', None)
    if valor is None:
        # `open(P)` sin modo ni kwargs es modo texto por defecto, que es 'r'.
        # `open(P, encoding='utf-8')` tampoco puede ser escritura: `encoding`
        # solo existe en modo texto.
        return [(nodo.lineno, 'lee', 'open(<LA BASE>) modo texto por defecto')]
    if valor in MODOS_ESCRITURA:
        tipo = 'tmp' if _es_tmp(nodo.args[0], cuerpo) else 'escribe'
        return [(nodo.lineno, tipo, "open(<LA BASE>, %r)" % valor)]
    return [(nodo.lineno, 'lee', "open(<LA BASE>, %r)" % valor)]


def _autoverificacion():
    casos = [
        ('cadena', "N='hands_db.jsonl'\nP=os.path.join('data',N)\nopen(P,'a')\n",
         'escribe'),
        ('indirecta', "P='hands_db.jsonl'\nshutil.copy2('bak', P)\n", 'escribe'),
        ('atributo', "def f(s):\n    open(s.output_path,'a')\ns.output_path='hands_db.jsonl'\n",
         'escribe'),
        ('solo lectura', "P='hands_db.jsonl'\nopen(P, encoding='utf-8')\n", 'lee'),
        ('a otro fichero', "open('otra_cosa.json','w')\n", None),
        ('copia mutada en tmp', "P='hands_db.jsonl'\n"
                                "def f(tmp_path):\n"
                                "    db = tmp_path / P\n"
                                "    open(db, 'w')\n", 'tmp'),
        ('helper', "P='hands_db.jsonl'\n"
                   "def guardar(manos, ruta=P):\n"
                   "    tmp = ruta + '.tmp'\n"
                   "    open(tmp, 'w')\n"
                   "    os.replace(tmp, ruta)\n"
                   "def usar():\n"
                   "    guardar([], P)\n", 'escribe'),
    ]
    fallos = []
    for nombre, codigo, esperado in casos:
        e = _clasifica(ast.parse(codigo))
        real = [x[1] for x in e]
        ok = (real == [esperado]) if esperado else (not real)
        print('  %-14s %-6s esperado=%-10s obtenido=%s'
              % (nombre, 'OK' if ok else 'ROTO', esperado, real))
        if not ok:
            fallos.append(nombre)
    return not fallos


print('AUTOCOMPROBACION del instrumento')
if not _autoverificacion():
    print('\nEl instrumento falla en un caso que sabe la respuesta. Se para.')
    raise SystemExit(1)
print('  -> el instrumento ve las 7 formas. Se puede usar.\n')

base = os.getcwd()
ESCRITORES, LECTORES, INDIET, TMP = {}, {}, {}, {}
DESTINO = {'escribe': ESCRITORES, 'lee': LECTORES,
           'indeterminado': INDIET, 'tmp': TMP}
for carpeta in ('tools', 'recorder', 'motor', 'tests'):
    d = os.path.join(base, carpeta)
    if not os.path.isdir(d):
        continue
    for nombre in sorted(os.listdir(d)):
        if not nombre.endswith('.py'):
            continue
        rel = '%s/%s' % (carpeta, nombre)
        try:
            arbol = ast.parse(io.open(os.path.join(d, nombre),
                                      encoding='utf-8').read())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for ln, tipo, det in _clasifica(arbol):
            DESTINO.get(tipo, {}).setdefault(rel, []).append(
                'L%d %s' % (ln, det))
for nombre in sorted(os.listdir(base)):
    if not nombre.endswith('.py'):
        continue
    try:
        arbol = ast.parse(io.open(os.path.join(base, nombre),
                                  encoding='utf-8').read())
    except (SyntaxError, UnicodeDecodeError):
        continue
    for ln, tipo, det in _clasifica(arbol):
        DESTINO.get(tipo, {}).setdefault(nombre, []).append(
            'L%d %s' % (ln, det))

for titulo, d in (('ESCRIBEN en hands_db.jsonl', ESCRITORES),
                  ('COPIAS MUTADAS en tmp_path (NO son la base)', TMP),
                  ('INDETERMINADO — a revisar a mano', INDIET),
                  ('SOLO LEEN', LECTORES)):
    print('=== %s ===' % titulo)
    if not d:
        print('   (ninguno)')
    for r in sorted(d):
        print('  %-34s %s' % (r, '; '.join(
            sorted(set(d[r]), key=lambda x: int(x.split()[0][1:])))))
    print()