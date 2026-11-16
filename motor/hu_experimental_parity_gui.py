"""Punto de entrada de la GUI experimental de paridad HU (Fase 10.1)."""
from .hu_parity.gui_parity import (  # noqa: F401
    HUParityGUI,
    PARITY_TITLE,
    PARITY_WARNING,
    main,
)

__all__ = ['HUParityGUI', 'PARITY_TITLE', 'PARITY_WARNING', 'main']


if __name__ == '__main__':
    raise SystemExit(main())
