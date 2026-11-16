"""Punto de entrada de la GUI experimental HU (Fase 10)."""
from .hu_experimental.gui import (  # noqa: F401
    HUExperimentalGUI,
    TITLE,
    WARNING,
    main,
)

__all__ = ['HUExperimentalGUI', 'TITLE', 'WARNING', 'main']


if __name__ == '__main__':
    raise SystemExit(main())
