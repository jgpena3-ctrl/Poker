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
    # --- Fase 10.1: modo paridad con el motor live ---
    # 'hu_sb_bb': modo operativo; fuerza SB/BB en HU mediante
    # MANUAL_POSITIONS y adapta el orden postflop del recorder por instancia.
    # 'live_default' solo sirve como referencia diagnóstica y no es paridad HU.
    parity_position_mode: str = 'hu_sb_bb'
    # Ruta donde el recorder de paridad escribe las manos. Por defecto queda
    # aislada en trabajo/hu_experimental; para el piloto autorizado se puede
    # apuntar a data/hands_db.jsonl con parity_allow_historical_hand_db=True.
    parity_hands_path: Optional[Path] = None
    parity_allow_historical_hand_db: bool = False
    parity_enable_live_decision_log: bool = False
    parity_enable_shadow_logs: bool = False
    auto_poll_s: float = 0.5
    max_frame_age_s: float = 5.0
    max_capture_ms: float = 5000.0
    max_ocr_ms: float = 3000.0

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
        if self.parity_position_mode not in ('live_default', 'hu_sb_bb'):
            raise ValueError('parity_position_mode invalido')
        if self.parity_enable_shadow_logs:
            raise ValueError(
                'parity_enable_shadow_logs esta prohibido en Fase 10.2')
        if self.auto_poll_s <= 0:
            raise ValueError('auto_poll_s debe ser positivo')
        if self.max_frame_age_s <= 0 or self.max_capture_ms <= 0 \
                or self.max_ocr_ms <= 0:
            raise ValueError('los limites temporales deben ser positivos')
        hands_path = (Path(self.parity_hands_path).expanduser()
                      if self.parity_hands_path is not None
                      else runtime_dir / 'hands_parity.jsonl')
        hands_path = hands_path.resolve()
        historical = (PROJECT_ROOT / 'data' / 'hands_db.jsonl').resolve()
        if hands_path == historical:
            raise ValueError(
                'parity_hands_path no puede apuntar a data/hands_db.jsonl '
                'en Fase 10.2')
        try:
            hands_path.relative_to(runtime_dir)
        except ValueError as exc:
            raise ValueError(
                'parity_hands_path debe permanecer dentro de runtime_dir') from exc
        object.__setattr__(self, 'parity_hands_path', hands_path)

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
            parity_position_mode=kwargs.get(
                'parity_position_mode', base.parity_position_mode),
            parity_hands_path=kwargs.get('parity_hands_path'),
            parity_allow_historical_hand_db=kwargs.get(
                'parity_allow_historical_hand_db',
                base.parity_allow_historical_hand_db),
            parity_enable_live_decision_log=kwargs.get(
                'parity_enable_live_decision_log',
                base.parity_enable_live_decision_log),
            parity_enable_shadow_logs=kwargs.get(
                'parity_enable_shadow_logs',
                base.parity_enable_shadow_logs),
            auto_poll_s=kwargs.get('auto_poll_s', base.auto_poll_s),
            max_frame_age_s=kwargs.get(
                'max_frame_age_s', base.max_frame_age_s),
            max_capture_ms=kwargs.get(
                'max_capture_ms', base.max_capture_ms),
            max_ocr_ms=kwargs.get('max_ocr_ms', base.max_ocr_ms),
        )
