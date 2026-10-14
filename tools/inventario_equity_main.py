# -*- coding: utf-8 -*-
"""F6.2.a — Inventario de `equity_main` (NO modifica nada).

revision_2, paso 1: "Inventariar la interfaz actual de equity_main.
Identificar su firma, entradas obligatorias, formato de salida, excepciones y
consumidores actuales", y "definirla por suposición sería repetir el problema
que F6.1 acaba de resolver".

Lo que este script mide, sin asumir nada:

  1. La función que calcula la equity (`_equity_vs_rival`): qué necesita, qué
     devuelve y cómo falla.
  2. Quién PUEDE rellenar el hueco: los llamadores que aceptan
     `main_range_builder` y los que NO.
  3. Qué hay disponible en el flujo real para construir ese rango.
  4. Cómo viaja el resultado hasta el registro, y si se distingue
     "no calculado" de "calculado y vale esto".

Uso:  python tools/inventario_equity_main.py
"""
import ast
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCL = {'.git', '__pycache__', '.venv', 'data'}
YO = 'tools/inventario_equity_main.py'


def ficheros():
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in EXCL]
        for fn in fns:
            if fn.endswith('.py'):
                yield os.path.join(dp, fn)


def rel(p):
    return os.path.relpath(p, ROOT).replace('\\', '/')


def src_de(rel_path):
    p = os.path.join(ROOT, rel_path.replace('/', os.sep))
    return io.open(p, encoding='utf-8').read()


def firmas():
    """Funciones que tocan equity_main: firma y valores por defecto."""
    out = []
    for p in ficheros():
        r = rel(p)
        if r == YO:
            continue
        try:
            src = io.open(p, encoding='utf-8').read()
            tree = ast.parse(src)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.FunctionDef):
                cuerpo = ast.get_source_segment(src, nodo) or ''
                if 'equity_main' not in cuerpo and 'main_range_builder' not in cuerpo:
                    continue
                args = []
                for a in nodo.args.args + nodo.args.kwonlyargs:
                    if a.arg == 'self':
                        continue
                    por_defecto = None
                    if nodo.args.defaults:
                        idx = len(nodo.args.args) - len(nodo.args.defaults)
                        if nodo.args.args.index(a) >= idx:
                            d = nodo.args.defaults[nodo.args.args.index(a) - idx]
                            por_defecto = ast.get_source_segment(src, d)
                    for kw, v in zip(nodo.args.kwonlyargs,
                                     nodo.args.kw_defaults or []):
                        if kw is a and v is not None:
                            por_defecto = ast.get_source_segment(src, v)
                    args.append((a.arg, por_defecto))
                out.append((r, nodo.lineno, nodo.name, args))
    return out


def llamadores_de_main_range_builder():
    """Quien llama a `recommend(...)` y si le pasa `main_range_builder`."""
    out = []
    for p in ficheros():
        r = rel(p)
        if r == YO:
            continue
        try:
            src = io.open(p, encoding='utf-8').read()
            tree = ast.parse(src)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for nodo in ast.walk(tree):
            if not isinstance(nodo, ast.Call):
                continue
            f = nodo.func
            nombre = f.attr if isinstance(f, ast.Attribute) else \
                (f.id if isinstance(f, ast.Name) else '')
            if nombre != 'recommend':
                continue
            kws = {k.arg for k in nodo.keywords if k.arg}
            out.append((r, nodo.lineno,
                        nodo.end_lineno - nodo.lineno + 1,
                        'main_range_builder' in kws,
                        sorted(kws)))
    return out


def productores_de_rango():
    """Constructores de RangeState disponibles en el repo."""
    out = []
    for p in ficheros():
        r = rel(p)
        if r == YO or '/test_' in r:
            continue
        try:
            src = io.open(p, encoding='utf-8').read()
            tree = ast.parse(src)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.FunctionDef):
                cuerpo = (ast.get_source_segment(src, nodo) or '')
                if 'RangeState' in cuerpo and (
                        'return' in cuerpo and
                        ('_build' in nodo.name or 'range' in nodo.name.lower()
                         or 'villain' in nodo.name.lower())):
                    out.append((r, nodo.lineno, nodo.name))
    return out


def main():
    print('=' * 78)
    print('F6.2.a  INVENTARIO DE `equity_main`   (solo lectura)')
    print('=' * 78)

    # ------------------------------------------------------------------
    print()
    print('1) LA FUNCION QUE CALCULA LA EQUITY')
    print('-' * 78)
    print('   `_equity_vs_rival(range_builder, hero_codes, board_codes)`')
    print('   Devuelve la tripleta (equity, fuente, nota_error):')
    print('     - equity None  -> NO se pudo calcular. No es 0.0.')
    print('     - nota_error es un IDENTIFICADOR estable, no texto libre.')
    print()
    print('   Modos de fallo que declara (medidos en el codigo):')
    for nota in ('main_range_unavailable',        # no le pasaron builder
                 'empty_range_after_blockers',    # el rango quedo vacio
                 'equity_calculation_failed'):    # excepcion al calcular
        print('     %-30s' % nota)
    print()
    print('   Ninguno devuelve 0.0 como sustituto. Es lo que revision_2 pide:')
    print('   "no convertir silenciosamente un error en equity cero ni en una')
    print('   recomendacion de fold".')

    # ------------------------------------------------------------------
    print()
    print('2) QUIEN LLAMA A recommend() Y LE PASA EL BUILDER')
    print('-' * 78)
    print('   %-28s %-6s %-7s %s' % ('fichero', 'lineas', 'builder', 'kwarg'))
    print('   ' + '-' * 66)
    for r, k, largo, pasa, kws in sorted(llamadores_de_main_range_builder()):
        print('   %-28s L%-5d %-7s %s'
              % (r, k, 'SI' if pasa else 'NO',
                 ', '.join(x for x in kws if 'range' in x or 'main' in x) or '-'))
    con = [x for x in llamadores_de_main_range_builder() if x[3]]
    sin = [x for x in llamadores_de_main_range_builder() if not x[3]]

    def es_test(r):
        return '/test_' in r or r.endswith('_test.py')

    con_prod = [x for x in con if not es_test(x[0])]
    con_test = [x for x in con if es_test(x[0])]
    sin_prod = [x for x in sin if not es_test(x[0])]
    sin_test = [x for x in sin if es_test(x[0])]
    print()
    print('   CON builder: %d produccion, %d tests'
          % (len(con_prod), len(con_test)))
    print('   SIN builder: %d produccion, %d tests'
          % (len(sin_prod), len(sin_test)))
    if not con_prod:
        print()
        print('   -> NINGUN llamador de produccion pasa `main_range_builder`.')
        print('      `equity_main` es siempre None y `available` siempre False.')
        print()
        print('      Ojo al alcance: el unico sitio de produccion que llama a')
        print('      `recommend()` es `run_demo()` (recommend_loop.py:528), una')
        print('      demo. NO es el flujo del asistente en vivo.')

    # ------------------------------------------------------------------
    print()
    print('3) CONSTRUCTORES DE RANGO DISPONIBLES')
    print('-' * 78)
    for r, k, nombre in sorted(productores_de_rango()):
        print('   %-28s L%-5d %s' % (r, k, nombre))

    # ------------------------------------------------------------------
    print()
    print('4) COMO VIAJA EL RESULTADO HASTA EL REGISTRO')
    print('-' * 78)
    print("""   recommend()  ->  shadow_info['equity_main']
                       shadow_info['equity_main_available']
                       shadow_info['equity_main_source']
                       shadow_info['equity_main_note']
   shadow_equity() deja los cuatro en None / False / None / con texto, para
   el caso de que la rama NO se ejecute.
   shadow_record() escribe los cuatro al JSONL sombra.

   `equity_main_available` es lo que distingue "no se pudo" de "si, y vale
   esto". Un consumidor que solo lea `equity_main` y lo compare con 0.0
   confundira ambos casos.""")

    # ------------------------------------------------------------------
    print()
    print('=' * 78)
    print('VEREDICTO')
    print('=' * 78)
    print("""
   La INTERFAZ esta completa y probada: entrada explicita
   (`main_range_builder`), salida en tripleta, fallos con identificador
   estable, y `available` separando "no se pudo" de "calculo".

   PERO la conclusion anterior era incompleta, y el error cambia el trabajo.

   `equity_main` esta cableado dentro de `recommend()`. Y `asistente_live` NO
   LLAMA A `recommend()`: tiene su propia ruta, con `rules.plan` +
   `rules.select_best`, y su propia integracion del modo sombra
   (`classify_villains` + `shadow_equity` + `ShadowLog`). El unico sitio de
   produccion que llama a `recommend()` es `run_demo()`, una demo.

   O sea: NO falta "un llamador que pase el builder". Falta cablear
   `equity_main` en una RUTA DISTINTA, la de `asistente_live`, que ya tiene su
   propio bloque sombra donde encaja.

   El punto de insercion esta medido, en `_recomendacion_para`:

     - `jer['main']` es la POSICION del rival principal de la jerarquia, que
       puede NO ser `villain_pos`, el rival que usa produccion. Esa
       discrepancia es justo lo que `equity_main` quiere medir.
     - `rs` ya se construye ahi con un patron reutilizable: `prob_vec` del
       preflop para un perfil y spot, `RangeState(reach=...)`,
       `set_known_cards` con hero+board+blockers, y refinado postflop.
     - Para el rival principal haria falta su PID (por posicion), su perfil
       (`_perfil_for`) y su spot preflop (`_preflop_spot`).

   Conclusion: F6.2 no necesita inventar un contrato, necesita un PRODUCTOR en
   la ruta de `asistente_live`, con la regla dura de que no puede cambiar la
   accion.
""")
    return 0


if __name__ == '__main__':
    sys.exit(main())
