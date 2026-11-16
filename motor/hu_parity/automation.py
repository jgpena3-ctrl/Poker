"""Polling automatico para el asistente experimental HU.

El controlador no conoce tkinter ni el motor live: solo llama a
``assistant.poll_once()`` y entrega eventos al consumidor. La GUI de paridad lo
usa en un hilo daemon y drena la cola con ``root.after``; los tests pueden
llamar a ``run_once()`` de forma determinista.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional


@dataclass(frozen=True)
class PollEvent:
    analysis: Any = None
    registration: Any = None
    error: Optional[str] = None
    elapsed_ms: Optional[float] = None
    phase_times_ms: Optional[Mapping[str, float]] = None


class HUPollingController:
    """Bucle de observacion periodica con parada cooperativa."""

    def __init__(self, assistant: Any, *, interval_s: float = 0.5,
                 on_event: Optional[Callable[[PollEvent], None]] = None,
                 waiter: Optional[Callable[[float], Any]] = None):
        if interval_s <= 0:
            raise ValueError('interval_s debe ser positivo')
        self.assistant = assistant
        self.interval_s = float(interval_s)
        self.on_event = on_event
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._waiter = waiter or self._stop.wait

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive()
                    and not self._stop.is_set())

    @property
    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def run_once(self) -> PollEvent:
        try:
            event = self.assistant.poll_once()
            if not isinstance(event, PollEvent):
                event = PollEvent(analysis=event)
        except Exception as exc:  # noqa: BLE001 - se informa al operador
            event = PollEvent(error=str(exc))
        if self.on_event is not None:
            try:
                self.on_event(event)
            except Exception:
                # Un fallo de la GUI no debe tumbar el polling.
                pass
        return event

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            if self.is_running:
                return
            raise RuntimeError('el polling anterior aun esta terminando')
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name='hu-parity-poller', daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> bool:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                # El llamador no debe liberar recursos exclusivos mientras el
                # ciclo siga capturando/procesando en segundo plano.
                return False
        self._thread = None
        return True

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.run_once()
            # wait() permite despertar inmediatamente al detener.
            self._waiter(self.interval_s)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False
