"""Sello de procedencia para los ficheros derivados.

Motivo (revision_1/revision_2): sin procedencia, comparar dos
`profile_ranges.json` es imposible. Ya ocurrio: un fichero tenia 450
decisiones y otro 1157, con el MISMO `meta` (`{alpha, origen}`), y no habia
forma de saber por que.

Reglas:
  - `hands_input` son las manos RECIBIDAS por `from_hands()`.
  - `hands_used` son las que APORTARON al menos una observacion. Son
    distintas: una mano sin cartas conocidas cuenta en `hands_input` y no
    aporta nada al estimador. Confundirlas seria volver a mentir.
  - `hands_window` distingue la ventana fiable de una ventana a medida.
  - `code_commit` identifica el commit, y `arbol_sucio` avisa si hay cambios
    sin commitear: `git rev-parse HEAD` solo no basta para reproducir.
"""
import datetime
import os
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ficheros cuyo estado sin commitear cambia como se construye un derivado.
RUTAS_RELEVANTES = ('motor/', 'recorder/', 'tools/', 'data/hands_db.jsonl')


def _git(*args):
    try:
        return subprocess.check_output(
            ['git'] + list(args), cwd=REPO_DIR,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def code_commit():
    """Commit actual, o 'desconocido' si git no esta disponible."""
    return _git('rev-parse', '--short', 'HEAD') or 'desconocido'


def arbol_sucio(paths=RUTAS_RELEVANTES):
    """Hay cambios sin commitear que afectan a la construccion?

    paths : acota la comprobacion. Sin el, `git status --porcelain` da falsos
            positivos: un `tools/*.py` recien creado no cambia como se
            construyo un derivado, pero git lo reporta igual.

    Devuelve True / False, o **None si no se pudo consultar git**: presentar
    un fallo de git como "arbol limpio" seria peor que no saber.
    """
    args = ['status', '--porcelain']
    if paths:
        args += ['--'] + list(paths)
    out = _git(*args)
    if out is None:
        return None
    return bool(out)


def procedencia(hands_input=None, hands_used=None, reliable_hands=None,
               paths=RUTAS_RELEVANTES):
    """Devuelve el dict de `meta` con la procedencia de esta construccion.

    hands_input : nº de manos recibidas por `from_hands()`.
    hands_used  : nº de manos que aportaron al menos una observacion. Si no
                  se distingue, se asume igual a `hands_input`.
    paths       : rutas cuyo estado sin commitear invalida la reproduccion.

    LIMITACION CONOCIDA: `hands_window` se deduce comparando `hands_used`
    con `RELIABLE_HANDS`. Si alguien construye con 900 manos de otra fuente,
    el sello dira `reliable_only` sin serlo. Se acepta: para distinguirlo
    haria falta que `from_hands` recibiera la ventana como parametro.
    """
    if reliable_hands is None:
        from .learn import RELIABLE_HANDS as reliable_hands
    if hands_used is None:
        hands_used = hands_input
    # La ventana se clasifica por las manos RECIBIDAS, no por las que
    # aportaron observacion: con 900 de entrada pero 874 con cartas, la
    # ventana sigue siendo la fiable. `hands_used` mide la muestra
    # efectiva, que es otra cosa.
    if hands_input is None:
        ventana = 'desconocida'
    elif hands_input == reliable_hands:
        ventana = 'reliable_only'
    else:
        ventana = 'custom'
    return {
        'hands_window': ventana,
        'hands_input': hands_input,
        'hands_used': hands_used,
        'code_commit': code_commit(),
        'arbol_sucio': arbol_sucio(paths),
        'built_at': datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec='seconds'),
    }