"""Configuracion aislada del asistente HU experimental."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / 'trabajo' / 'hu_experimental'
DEFAULT_REGISTRY_NAME = 'registro_prospectivo.jsonl'


@dataclass(frozen=True)
class ExperimentalConfig:
    """Rutas y parametros propios, separados de la configuracion live."""

    runtime_dir: Path = DEFAULT_RUNTIME_DIR
    registry_name: str = DEFAULT_REGISTRY_NAME
    hero_seat: str = 'hero'
    hero_name: str = 'Hero'
    bb: float = 1.0
    capture_timeout_s: float = 2.0
    equity_n_runouts: int = 50
    # Preflop usa enumeracion exacta de runouts por combo; un valor alto
    # bloquearia la interfaz. La incertidumbre se declara en la prediccion.
    equity_n_combos: int = 8
    equity_seed: int = 7

    def __post_init__(self):
        runtime_dir = Path(self.runtime_dir).expanduser().resolve()
        object.__setattr__(self, 'runtime_dir', runtime_dir)
        if not self.registry_name or Path(self.registry_name).name != self.registry_name:
            raise ValueError('registry_name debe ser un nombre de archivo simple')
        if self.hero_seat not in ('hero', 'p1', 'p2', 'p3', 'p4', 'p5'):
            raise ValueError('hero_seat invalido')
        if self.bb <= 0:
            raise ValueError('bb debe ser positivo')
        if self.equity_n_runouts < 0 or self.equity_n_combos < 0:
            raise ValueError('los parametros de equity no pueden ser negativos')

    @property
    def registry_path(self) -> Path:
        return self.runtime_dir / self.registry_name

    @property
    def backup_dir(self) -> Path:
        return self.runtime_dir / 'backups'

    @classmethod
    def default(cls) -> 'ExperimentalConfig':
        return cls()

    @classmethod
    def with_paths(cls, *, runtime_dir: Optional[str] = None,
                   registry_name: Optional[str] = None,
                   **kwargs) -> 'ExperimentalConfig':
        base = cls.default()
        return cls(
            runtime_dir=(Path(runtime_dir) if runtime_dir is not None
                         else base.runtime_dir),
            registry_name=registry_name or base.registry_name,
            hero_seat=kwargs.get('hero_seat', base.hero_seat),
            hero_name=kwargs.get('hero_name', base.hero_name),
            bb=kwargs.get('bb', base.bb),
            capture_timeout_s=kwargs.get(
                'capture_timeout_s', base.capture_timeout_s),
            equity_n_runouts=kwargs.get(
                'equity_n_runouts', base.equity_n_runouts),
            equity_n_combos=kwargs.get(
                'equity_n_combos', base.equity_n_combos),
            equity_seed=kwargs.get('equity_seed', base.equity_seed),
        )
