"""GUI experimental de paridad HU (Fase 10.1).

Reutiliza la GUI de Fase 10 y anade polling automatico. Sigue siendo una
ventana independiente: no importa ``asistente_live_gui``, no ejecuta acciones y
no escribe en ``data/`` salvo que la configuracion lo autorice explicitamente.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

from ..hu_experimental.config import ExperimentalConfig
from ..hu_experimental.gui import HUExperimentalGUI
from .automation import HUPollingController, PollEvent
from .concurrency import CaptureSessionGuard, ConcurrencyError
from .parity import LiveParityAssistant


PARITY_TITLE = 'HU Paridad live — observacion automatica (NO validado)'
PARITY_WARNING = (
    'MODO PARIDAD EXPERIMENTAL. Usa el motor asistente_live original. '
    'La recomendacion NO es una decision demostrada ni una validacion '
    'estrategica. No hay botones para ejecutar acciones de poker. '
    'El polling automatico captura y persiste predicciones en el registro '
    'aislado; el piloto real sigue sin autorizar. No ejecute simultaneamente '
    'asistente_live: si no puede verificarse el proceso original, la exclusion '
    'de captura es responsabilidad del operador.'
)


class HUParityGUI(HUExperimentalGUI):
    def __init__(self, root: Optional[tk.Misc] = None,
                 assistant: Optional[LiveParityAssistant] = None,
                 config: Optional[ExperimentalConfig] = None):
        self.config = config or ExperimentalConfig.default()
        self.assistant = assistant or LiveParityAssistant(self.config)
        self._capture_guard = CaptureSessionGuard(
            self.config.runtime_dir / 'capture_session.lock')
        if hasattr(self.assistant, 'set_capture_guard'):
            self.assistant.set_capture_guard(self._capture_guard)
        super().__init__(root=root, assistant=self.assistant,
                         config=self.config)
        self.root.title(PARITY_TITLE)
        self._event_queue: queue.Queue = queue.Queue()
        self._controller = HUPollingController(
            self.assistant, interval_s=self.config.auto_poll_s,
            on_event=self._enqueue_event)
        self._build_parity_controls()
        self.root.after(100, self._drain_events)

    def _build_parity_controls(self) -> None:
        main = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        main.pack(fill=tk.X)
        warning = ttk.Label(main, text=PARITY_WARNING, foreground='#8a1c1c',
                            wraplength=920, justify=tk.LEFT,
                            font=('', 10, 'bold'))
        warning.pack(fill=tk.X, pady=(0, 6))

        frame = ttk.LabelFrame(main, text='Polling automatico de paridad',
                               padding=8)
        frame.pack(fill=tk.X)
        self.auto_status_var = tk.StringVar(value='detenido; captura exclusiva pendiente')
        ttk.Button(frame, text='Iniciar auto',
                   command=self.start_auto).pack(side=tk.LEFT)
        ttk.Button(frame, text='Detener auto',
                   command=self.stop_auto).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(frame, text='Estado:').pack(side=tk.LEFT, padx=(16, 2))
        ttk.Label(frame, textvariable=self.auto_status_var,
                  foreground='#123c7a').pack(side=tk.LEFT)
        ttk.Label(
            frame,
            text=(' | posicion=%s | hands=%s | poll=%.2fs'
                  % (self.config.parity_position_mode,
                     self.config.parity_hands_path,
                     self.config.auto_poll_s)),
            foreground='#555555').pack(side=tk.LEFT, padx=(16, 0))

    def _enqueue_event(self, event: PollEvent) -> None:
        self._event_queue.put(event)

    def _drain_events(self) -> None:
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            self.root.after(100, self._drain_events)
        except tk.TclError:
            pass

    def _handle_event(self, event: PollEvent) -> None:
        if event.error:
            if ('recurso de captura ocupado' in event.error or
                    'no se pudo verificar si asistente_live' in event.error):
                self._controller.stop()
            timing = (' | ciclo %.1f ms' % event.elapsed_ms
                      if event.elapsed_ms is not None else '')
            self.auto_status_var.set('ERROR: %s%s' % (event.error, timing))
            self.decision_status_var.set('ERROR auto: %s' % event.error)
            return
        analysis = event.analysis
        if analysis is not None:
            self.last_analysis = analysis
            self.last_frame = getattr(self.assistant, '_last_frame', None)
            state = analysis.state
            self.decision_status_var.set(
                '%s | HU=%s | calle=%s'
                % (analysis.canonical_status, state.status, state.street))
            if analysis.equity is None:
                self.equity_status_var.set(
                    'unknown | %s' % (analysis.equity_uncertainty or
                                      'sin equity calculable'))
            else:
                self.equity_status_var.set(
                    '%.4f | %s | %s'
                    % (analysis.equity, analysis.equity_method,
                       analysis.equity_uncertainty or
                       'sin incertidumbre declarada'))
            if analysis.provisional_selected_action:
                self.action_status_var.set(
                    'live provisional NO demostrada: %s'
                    % analysis.provisional_selected_action)
            else:
                self.action_status_var.set('sin recomendacion')
            self._set_detail(analysis)
        if event.registration is not None:
            self.last_registration = event.registration
            self.persist_status_var.set(
                'auto-persistida: %s' % event.registration.prediction_id)
            self.outcome_prediction_var.set(
                event.registration.prediction_id)
            self._refresh_registry_status()
        if analysis is not None and not event.error:
            timing = (' | ciclo %.1f ms' % event.elapsed_ms
                      if event.elapsed_ms is not None else '')
            self.auto_status_var.set('activo; ultimo=%s%s'
                                     % (analysis.captured_at, timing))

    def start_auto(self) -> None:
        try:
            warning = self._capture_guard.acquire()
        except ConcurrencyError as exc:
            self.auto_status_var.set('ERROR: %s' % exc)
            self.decision_status_var.set('ERROR captura: %s' % exc)
            return
        try:
            self._controller.start()
        except Exception as exc:  # noqa: BLE001 - se muestra al operador
            self.auto_status_var.set('ERROR polling: %s' % exc)
            self.decision_status_var.set('ERROR polling: %s' % exc)
            if not self._controller.is_alive:
                self._capture_guard.release()
            return
        self.auto_status_var.set(
            'activo; exclusividad no verificada' if warning else
            'activo (esperando primer ciclo)')

    def stop_auto(self) -> None:
        stopped = self._controller.stop()
        self.auto_status_var.set(
            'detenido' if stopped else
            'parada solicitada; el ciclo sigue activo y conserva el lock')

    def destroy(self) -> None:
        stopped = False
        try:
            stopped = self._controller.stop()
        finally:
            try:
                # No liberar exclusividad si la captura/polling no terminó.
                # Un watcher libera el lock cuando el worker realmente termina.
                if stopped:
                    self._capture_guard.release()
                else:
                    worker = getattr(self._controller, '_thread', None)
                    if worker is not None:
                        threading.Thread(
                            target=self._release_guard_after_worker,
                            args=(worker,), name='hu-capture-lock-release',
                            daemon=True).start()
            finally:
                super().destroy()

    def _release_guard_after_worker(self, worker) -> None:
        worker.join()
        self._capture_guard.release()


def main(argv: Optional[list] = None) -> int:
    del argv
    gui = HUParityGUI()
    gui.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
