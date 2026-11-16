"""Adaptador de captura aislado para el asistente HU experimental.

Reutiliza los lectores existentes sin pasar por ``asistente_live`` ni por el
recorder. El adaptador no escribe archivos: solo devuelve estado e imagen.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Tuple


class CaptureError(RuntimeError):
    """La captura o la lectura OCR no pudo completarse."""


@dataclass(frozen=True)
class CapturedFrame:
    state: Mapping[str, Any]
    captured_at: str
    image: Any = None
    source: str = 'screen'
    warnings: Tuple[str, ...] = ()
    capture_ms: Optional[float] = None
    ocr_ms: Optional[float] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # La imagen PIL se conserva para que el motor live pueda reutilizar su
    # deteccion de turno (StateMatcher). No se serializa ni se persiste.
    pil: Any = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tools_root() -> Path:
    return Path(__file__).resolve().parents[2] / 'tools'


class HUCaptureAdapter:
    """Captura de pantalla con inyeccion de dependencias para pruebas.

    ``capture_fn`` es la unica fuente de imagen/estado. No hay captura
    automatica en segundo plano: cada llamada a ``capture()`` es explicita.
    """

    def __init__(self, capture_fn: Optional[Callable[[], Any]] = None,
                 clock: Optional[Callable[[], str]] = None):
        self._capture_fn = capture_fn
        self._clock = clock or _now_iso
        self._reader = None
        self._card_reader = None

    def capture(self) -> CapturedFrame:
        started = time.perf_counter()
        if self._capture_fn is not None:
            try:
                raw = self._capture_fn()
            except Exception as exc:  # noqa: BLE001 - se expone como error de captura
                raise CaptureError('fallo de captura: %s' % exc) from exc
            frame = self._coerce_frame(raw)
            return CapturedFrame(
                state=frame.state,
                captured_at=frame.captured_at or self._clock(),
                image=frame.image,
                source=frame.source,
                warnings=frame.warnings,
                capture_ms=(time.perf_counter() - started) * 1000.0,
                ocr_ms=frame.ocr_ms,
                metadata=frame.metadata,
                pil=frame.pil,
            )

        state, image, pil, ocr_ms, captured_at = self._default_capture()
        return CapturedFrame(
            state=state,
            # La edad se mide desde el screenshot, no desde el final del OCR.
            captured_at=captured_at,
            image=image,
            source='screen',
            warnings=self._capture_warnings(state),
            capture_ms=(time.perf_counter() - started) * 1000.0,
            ocr_ms=ocr_ms,
            metadata={'reader': 'lector_estado+lector_unificado'},
            pil=pil,
        )

    def _coerce_frame(self, raw: Any) -> CapturedFrame:
        if isinstance(raw, CapturedFrame):
            return raw
        if isinstance(raw, Mapping):
            state = dict(raw)
            image = state.pop('_image', None)
            pil = state.pop('_pil', None)
            captured_at = state.pop('_captured_at', None) or self._clock()
            warnings = tuple(state.pop('_warnings', ()) or ())
            return CapturedFrame(state=state, captured_at=captured_at,
                                 image=image, source='injected',
                                 warnings=warnings, pil=pil)
        if isinstance(raw, (tuple, list)):
            if len(raw) < 1:
                raise CaptureError('captura inyectada vacia')
            state = raw[0]
            image = raw[1] if len(raw) > 1 else None
            pil = None
            ocr_ms = None
            if len(raw) > 2:
                # Compatibilidad con capture_live.capture(): (state, img, pil).
                # Si el tercer valor es numerico se interpreta como ocr_ms.
                if isinstance(raw[2], (int, float)) and not isinstance(raw[2], bool):
                    ocr_ms = float(raw[2])
                else:
                    pil = raw[2]
            if not isinstance(state, Mapping):
                raise CaptureError('estado inyectado no es mapping')
            return CapturedFrame(state=dict(state), captured_at=self._clock(),
                                 image=image, source='injected',
                                 warnings=self._capture_warnings(state),
                                 pil=pil, ocr_ms=ocr_ms)
        raise CaptureError('captura inyectada con formato no soportado')

    def _default_capture(self) -> Tuple[dict, Any, Any, float, str]:
        try:
            tools = str(_tools_root())
            for path in (tools,):
                if path not in sys.path:
                    sys.path.insert(0, path)
            import numpy as np
            from PIL import ImageGrab
            from lector_estado import StateReader
            from lector_unificado import CardReader
        except Exception as exc:  # pragma: no cover - depende del entorno
            raise CaptureError('lectores no disponibles: %s' % exc) from exc

        if self._reader is None:
            try:
                self._reader = StateReader()
            except Exception as exc:  # pragma: no cover - entorno real
                raise CaptureError('StateReader no inicializado: %s' % exc) from exc
        if self._card_reader is None:
            try:
                self._card_reader = CardReader()
            except Exception as exc:  # pragma: no cover - entorno real
                raise CaptureError('CardReader no inicializado: %s' % exc) from exc

        try:
            pil = ImageGrab.grab()
            captured_at = self._clock()
            img_arr = np.array(pil.convert('RGB'))
        except Exception as exc:  # pragma: no cover - entorno real
            raise CaptureError('pantalla no disponible: %s' % exc) from exc

        started = time.perf_counter()
        try:
            state = dict(self._reader.read_all(pil))
            cards = self._card_reader.read_all(img_arr)
        except Exception as exc:  # pragma: no cover - entorno real
            raise CaptureError('fallo de OCR/interpretacion: %s' % exc) from exc
        ocr_ms = (time.perf_counter() - started) * 1000.0

        hero = cards.get('hero') if isinstance(cards, Mapping) else None
        if hero:
            state['hero_cards'] = hero
        community = cards.get('community') if isinstance(cards, Mapping) else None
        if community is not None:
            state['community'] = community
        state['_capture_source'] = 'screen'
        return state, img_arr, pil, ocr_ms, captured_at

    @staticmethod
    def _capture_warnings(state: Mapping[str, Any]) -> Tuple[str, ...]:
        warnings = []
        if not state.get('hero_cards'):
            warnings.append('hero_cards_not_observed')
        for seat in ('hero', 'p1', 'p2', 'p3', 'p4', 'p5'):
            if state.get(f'{seat}_state') is None:
                warnings.append('%s_state_unknown' % seat)
        if state.get('pot') is None:
            warnings.append('pot_not_observed')
        return tuple(warnings)
