# -*- coding: utf-8 -*-
"""Clasifica `data/`: fuente, derivado regenerable o debris de runtime.

Por qué existe: un `git add -A` metió `data/shadow_hierarchy.jsonl` en el repo.
La pregunta correcta no es "¿lo escribe el código?" ( Casi todo lo escribe
`reconstruir_derivados.py`) sino:

  - ¿se LEE como entrada?  -> fuente o derivado, se versiona.
  - ¿solo se ESCRIBE al usar el sistema? -> runtime, NO se versiona.

MEDIDO, no estimado. Salida usada en DOCS/DATA_FUENTE_VS_RUNTIME.md.

Uso:  python tools/clasifica_data.py
"""
import io
import os
import re
import subprocess

ROOT = os.getcwd()


def git(*a):
    return subprocess.check_output(['git'] + list(a), cwd=ROOT,
                                   stderr=subprocess.DEVNULL).decode().strip()


# --- quien escribe cada fichero de data/ ---------------------------------
#
# MEDIDO: antes esto vivia a nivel de modulo, asi que el `os.walk`
# corria al IMPORTAR el script. Quien quisiera reutilizar una funcion
# pagaba un recorrido completo del repo sin pedirlo. Ahora es una
# funcion, y la llama `main()`.
def construir_escriben():
    # --- quien escribe cada fichero de data/ ---------------------------------
    #
    # MEDIDO que buscar solo el literal `data/...` es INSUFICIENTE: los modulos
    # del motor construyen sus rutas con `os.path.join(REPO_DIR, 'data', 'x.json')`
    # y con `Path(DATA_DIR) / 'x.json'`. Con la busqueda literal, `clasifica_data`
    # decia "nadie lo escribe" de ficheros que si se escriben, lo que es un falso
    # positivo de runtime y por tanto peligroso: invita a borrar algo vivo.
    #
    # Se buscan las TRES formas. La de nombre base es ambigua en principio (un
    # `x.json` podria estar en otra carpeta), asi que se marca como tal en la
    # columna, en vez de presentarla como certera.
    # Rutas por literal `data/...`: certeza alta, se reporta tal cual.
    RX_LITERAL = re.compile(r"['\"](data/[^'\"{}]+)['\"]")

    # Nombres de fichero citados en cualquier parte. Para cada uno se mira la
    # VENTANA de 400 caracteres anteriores buscando como se construyo la ruta.
    #
    # POR QUE UNA VENTANA y no un regex: `os.path.join(` admite parentesis
    # anidados antes del nombre
    #     os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'x.json')
    # y cualquier patron con `[^)]*` se para en el primer `)`. MEDIDO: asi
    # fallaban `observations.json`, `player_stats.json` y `profiles.json`.
    #
    # LIMITACION, y es real: la ventana es heuristica. Puede atribuir un fichero a
    # un modulo que lo cita cerca sin construirlo. Para eso cada coincidencia se
    # etiqueta con la forma detectada, para que se pueda revisar a ojo.
    VENTANA = 400
    RX_NOMBRE = re.compile(r"['\"]([\w.\-]+\.jsonl?)['\"]")
    RX_PREFIJO = re.compile(r"os\.path\.join\($|/\s*$|os\.path\.join\([^)]*\)$")


    def _forma(ruta_texto):
        """Como se construyo la ruta que termina en este nombre: etiqueta o None."""
        ventana = ruta_texto[-VENTANA:]
        if 'os.path.join' in ventana:
            return 'join'
        if re.search(r"/\s*['\"]?$", ventana.rstrip()):
            return 'div'
        return None

    ESCRIBEN = {}
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in {'.git', '__pycache__', '.venv'}]
        for fn in fns:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, ROOT).replace('\\', '/')
            src = io.open(p, encoding='utf-8').read()
            # 1) literales `data/...`
            for m in RX_LITERAL.finditer(src):
                ESCRIBEN.setdefault(m.group(1), set()).add(rel)

            # 2) nombres sueltos, con la ventana que reconstruye como se llega
            for m in RX_NOMBRE.finditer(src):
                base = m.group(1)
                if base in ('__init__.py',):
                    continue
                etiqueta = _forma(src[:m.start()])
                if etiqueta is None:
                    continue          # citado, no construido: no es escritor
                ESCRIBEN.setdefault('data/' + base, set()).add(
                    '%s [%s]' % (rel, etiqueta))
    return ESCRIBEN


def main():
    ESCRIBEN = construir_escriben()

    print('=' * 78)
    print('CLASIFICACION DE data/  (versionados)')
    print('=' * 78)
    print('%-34s %-8s %s' % ('fichero', 'escrito', 'por quien'))
    print('-' * 78)

    for f in sorted(git('ls-files', 'data').splitlines()):
        autores = sorted(ESCRIBEN.get(f, ()))
        marca = 'SI' if autores else '-'
        print('%-34s %-8s %s' % (f, marca, ', '.join(a[:34] for a in autores) or '-'))

    print()
    print('=' * 78)
    print('SOSPECHOSOS: nombre de test/salida y NADIE lo escribe')
    print('=' * 78)
    sospechosos = []
    for f in sorted(git('ls-files', 'data').splitlines()):
        base = os.path.basename(f)
        if re.search(r'(test|trace|output|dump|tmp|debug)', base, re.I) \
                and f not in ESCRIBEN:
            sospechosos.append(f)
            print('   %s   (%d bytes)'
                  % (f, os.path.getsize(f) if os.path.exists(f) else -1))
    if not sospechosos:
        print('   ninguno')

    print()
    print('=' * 78)
    print('¿los sospechosos se referencian desde algun sitio?')
    print('=' * 78)
    for f in sospechosos:
        base = os.path.basename(f)
        usos = []
        for dp, dn, fns in os.walk(ROOT):
            dn[:] = [d for d in dn if d not in {'.git', '__pycache__', '.venv'}]
            for fn in fns:
                if not (fn.endswith('.py') or fn.endswith('.md')):
                    continue
                p = os.path.join(dp, fn)
                if base in io.open(p, encoding='utf-8', errors='ignore').read():
                    usos.append(os.path.relpath(p, ROOT).replace('\\', '/'))
        print('   %-34s referenciado en: %s'
              % (f, ', '.join(sorted(set(usos))) or 'NADA'))



if __name__ == '__main__':
    main()