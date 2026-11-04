"""Fuente canónica de la versión del motor registrada en el decision log.

La versión no puede depender de que el operador se acuerde de exportar una
variable de entorno: una decisión sin versión no es auditable. El orden de
resolución es:

1. ``POKER_MOTOR_VERSION`` (override explícito, útil en pruebas/replays).
2. El commit de git del repositorio, con sufijo ``-dirty`` si el código del
   motor tiene cambios sin commitear.
3. ``unversioned`` si no hay git disponible. Nunca ``None``.

El sufijo ``-dirty`` es deliberado: un commit limpio identifica el código
exacto; un árbol modificado no puede afirmar que es ese commit sin más.
"""
from __future__ import annotations

import os
import subprocess

ENV_VAR = 'POKER_MOTOR_VERSION'
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args):
    try:
        result = subprocess.run(
            ('git',) + args, cwd=_ROOT, capture_output=True, text=True,
            timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _commit():
    commit = _git('rev-parse', 'HEAD')
    return commit or None


def _motor_dirty():
    """True si hay cambios sin commitear que afectan al paquete ``motor``.

    Incluye ficheros nuevos: un módulo sin commitear también forma parte del
    código que se está ejecutando y no puede quedar disfrazado de commit.
    """
    status = _git('status', '--porcelain', '--untracked-files=normal', '--',
                  'motor')
    return bool(status)


def motor_version():
    """Devuelve siempre una cadena no vacía que identifica el código."""
    override = (os.environ.get(ENV_VAR) or '').strip()
    if override:
        return override
    commit = _commit()
    if not commit:
        return 'unversioned'
    return f'{commit}-dirty' if _motor_dirty() else commit
