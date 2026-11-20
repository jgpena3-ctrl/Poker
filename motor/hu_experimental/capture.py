"""Adaptador de captura aislado para el asistente HU experimental.

Delega en ``tools/capture_live.py``, el mismo pipeline que usa
``asistente_live`` (screenshot, StateReader y CardReader). El adaptador no
escribe archivos: solo devuelve estado e imagen. La inicializacion pesada de los
lectores se hace en ``prepare()`` y no se imputa al frame capturado.
"""
from __future__ import annotations

import sys
import threading
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
    setup_ms: Optional[float] = None
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
        self._prepared = False
        self._last_setup_ms: Optional[float] = None
        self._prepare_lock = threading.Lock()

    def prepare(self) -> float:
        """Inicializa los lectores originales fuera del presupuesto de captura.

        ``capture_live.init_reader()`` entrena plantillas OCR y tarda varios
        segundos en el primer uso. Ese coste de arranque no debe contarse como
        latencia de un frame: la captura empieza despues.
        """
        if self._capture_fn is not None or self._prepared:
            return 0.0
        with self._prepare_lock:
            if self._prepared:
                return 0.0
            tools = str(_tools_root())
            if tools not in sys.path:
                sys.path.insert(0, tools)
            try:
                import capture_live
            except Exception as exc:  # pragma: no cover - depende del entorno
                raise CaptureError('lectores no disponibles: %s' % exc) from exc
            started = time.perf_counter()
            try:
                capture_live.init_reader()
            except Exception as exc:  # pragma: no cover - entorno real
                raise CaptureError(
                    'no se pudieron inicializar los lectores: %s' % exc) from exc
            self._prepared = True
            self._last_setup_ms = (time.perf_counter() - started) * 1000.0
            return self._last_setup_ms

    def capture(self) -> CapturedFrame:
        if self._capture_fn is not None:
            started = time.perf_counter()
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
                setup_ms=frame.setup_ms,
                metadata=frame.metadata,
                pil=frame.pil,
            )

        self.prepare()
        started = time.perf_counter()
        state, image, pil, captured_at = self._default_capture()
        return CapturedFrame(
            state=state,
            # La edad se mide desde el screenshot, no desde el final del OCR.
            captured_at=captured_at,
            image=image,
            source='screen',
            warnings=self._capture_warnings(state),
            capture_ms=(time.perf_counter() - started) * 1000.0,
            # capture_live no separa screenshot de OCR. El total posterior al
            # screenshot se conserva en capture_ms; no se inventa un OCR_ms.
            ocr_ms=None,
            setup_ms=self._last_setup_ms,
            metadata={
                'reader': 'capture_live.StateReader+CardReader',
                'capture_backend': 'tools.capture_live.capture',
                'reader_setup_ms': self._last_setup_ms,
            },
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
            setup_ms = state.pop('_setup_ms', None)
            return CapturedFrame(state=state, captured_at=captured_at,
                                 image=image, source='injected',
                                 warnings=warnings, setup_ms=setup_ms, pil=pil)
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

    def _default_capture(self) -> Tuple[dict, Any, Any, str]:
        """Delega en el pipeline original ``tools/capture_live.py``.

        No se reimplementa la lectura: se usa exactamente la misma funcion que
        ``asistente_live``. El timestamp se toma inmediatamente antes de la
        llamada (screenshot) y no despues del OCR.
        """
        tools = str(_tools_root())
        if tools not in sys.path:
            sys.path.insert(0, tools)
        try:
            import capture_live
        except Exception as exc:  # pragma: no cover - depende del entorno
            raise CaptureError('lectores no disponibles: %s' % exc) from exc

        captured_at = self._clock()
        try:
            state, image, pil = capture_live.capture()
        except Exception as exc:  # pragma: no cover - entorno real
            raise CaptureError('fallo de captura/OCR original: %s' % exc) from exc
        if not isinstance(state, Mapping):
            raise CaptureError('capture_live devolvio un estado no interpretable')
        return dict(state), image, pil, captured_at

    @staticmethod
    def _capture_warnings(state: Mapping[str, Any]) -> Tuple[str, ...]:
        warnings = []
        if not state:
            warnings.append('state_empty')
        if not state.get('hero_cards'):
            warnings.append('hero_cards_not_observed')
        if not any('%s_state' % seat in state
                   for seat in ('hero', 'p1', 'p2', 'p3', 'p4', 'p5')):
            warnings.append('state_keys_missing')
        for seat in ('hero', 'p1', 'p2', 'p3', 'p4', 'p5'):
            if state.get(f'{seat}_state') is None:
                warnings.append('%s_state_unknown' % seat)
        if state.get('pot') is None:
            warnings.append('pot_not_observed')
        return tuple(warnings)
