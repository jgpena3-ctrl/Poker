"""Sello de procedencia para los ficheros derivados.

Motivo (revision_1/revision_2): sin procedencia, comparar dos
`profile_ranges.json` es imposible. Ya ocurrio: un fichero tenia 450
decisiones y otro 1157, con el MISMO `meta` (`{alpha, origen}`), y no habia
forma de saber por que.

Reglas:
  - `hands_used` es el numero REAL de manos que entro en la construccion,
    no la constante nominal `RELIABLE_HANDS`. Si no lo es, `meta` miente,
    que es justo lo que este modulo existe para evitar.
  - `hands_window` distingue la ventana fiable de una ventana a medida.
  - `code_commit` identifica el commit. Si el arbol esta sucio se marca,
    porque `git rev-parse HEAD` solo no basta para reproducir el resultado.
"""
import datetime
import os
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def arbol_sucio():
    """True si hay cambios sin commitear: el commit no basta para reproducir."""
    try:
        return bool(_git('status', '--porcelain'))
    except Exception:
        return False


def procedencia(hands_used=None, reliable_hands=None):
    """Devuelve el dict de `meta` con la procedencia de esta construcción.

    hands_used      : nº real de manos usadas. None = desconocido.
    reliable_hands  : constante de la ventana fiable, para clasificar la
                      ventana como 'reliable_only' o 'custom'.
    """
    if reliable_hands is None:
        from .learn import RELIABLE_HANDS as reliable_hands
    if hands_used is None:
        ventana = 'desconocida'
    elif hands_used == reliable_hands:
        ventana = 'reliable_only'
    else:
        ventana = 'custom'
    meta = {
        'hands_window': ventana,
        'hands_used': hands_used,
        'code_commit': code_commit(),
        'arbol_sucio': arbol_sucio(),
        'built_at': datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec='seconds'),
    }
    return meta