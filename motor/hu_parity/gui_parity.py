"""GUI experimental de paridad HU (Fase 10.1).

Version compacta de la GUI de paridad. La ventana se ancla al borde derecho y
ocupa 367x719 px (dentro de los 368 disponibles) para no tapar la mesa. El
flujo principal es un unico boton: prepara lectores/motor, arranca el polling
automatico y muestra la lectura, la recomendacion y las preguntas que necesiten
intervencion humana (por ejemplo, la accion observada del rival).

Sigue siendo una ventana independiente: no importa ``asistente_live_gui``, no
ejecuta acciones y no escribe en ``data/``. El registro prospectivo aislado y
el resultado posterior son responsabilidad explicita del operador.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

from ..hu_experimental.config import ExperimentalConfig
from ..hu_experimental.gui import _flag, HUExperimentalGUI
from .automation import HUPollingController, PollEvent
from .concurrency import CaptureSessionGuard, ConcurrencyError
from .parity import LiveParityAssistant


PARITY_TITLE = 'HU Paridad live (NO validado)'
PARITY_WARNING = (
    'MODO PARIDAD EXPERIMENTAL. Usa el motor original y NO ejecuta acciones. '
    'No hay botones para ejecutar acciones de poker. El polling captura y '
    'registra predicciones aisladas. No usar a la vez que asistente_live.'
)


class HUParityGUI(HUExperimentalGUI):
    window_title = PARITY_TITLE
    window_warning = PARITY_WARNING

    def __init__(self, root: Optional[tk.Misc] = None,
                 assistant: Optional[LiveParityAssistant] = None,
                 config: Optional[ExperimentalConfig] = None):
        self.config = config or ExperimentalConfig.default()
        self.assistant = assistant or LiveParityAssistant(self.config)
        self._capture_guard = CaptureSessionGuard(
            self.config.runtime_dir / 'capture_session.lock')
        if hasattr(self.assistant, 'set_capture_guard'):
            self.assistant.set_capture_guard(self._capture_guard)
        self._event_queue: queue.Queue = queue.Queue()
        self._ui_queue: queue.Queue = queue.Queue()
        self._controller = HUPollingController(
            self.assistant, interval_s=self.config.auto_poll_s,
            on_event=self._enqueue_event)
        self._starting = False
        self._start_blocked_by_pending = False
        self._cancel_start = False

        super().__init__(root=root, assistant=self.assistant,
                         config=self.config)

        self._load_pending_from_assistant()
        self.root.after(100, self._drain_events)
        if _flag('HU_GUI_AUTOSTART', True):
            self.root.after(900, self._autostart)

    # ------------------------------------------------------------------
    # Controles principales
    # ------------------------------------------------------------------
    def _build_primary_buttons(self, parent) -> None:
        ttk.Button(parent, text='Iniciar',
                   command=self.start_auto).pack(side=tk.LEFT)
        ttk.Button(parent, text='Detener',
                   command=self.stop_auto).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(parent, text='Capturar ahora',
                   command=self.capture_now).pack(side=tk.LEFT, padx=(4, 0))

    def capture_now(self) -> None:
        """Captura y analiza una sola vez sin arrancar el polling."""
        if self._controller.is_alive:
            self.auto_status_var.set(
                'captura automatica activa; detenla para capturar manualmente')
            return
        if self._assistant_pending_ids():
            self._load_pending_from_assistant()
            self._start_blocked_by_pending = True
            return
        self.capture_state()

    # ------------------------------------------------------------------
    # Reconciliacion de predicciones previas
    # ------------------------------------------------------------------
    def _assistant_pending_ids(self) -> tuple:
        assistant = getattr(self, 'assistant', None)
        getter = getattr(assistant, 'pending_outcome_ids', None)
        if getter is None:
            return ()
        try:
            return tuple(getter() or ())
        except Exception:  # noqa: BLE001 - la GUI no debe caerse por esto
            return ()

    def _assistant_pending_entries(self) -> tuple:
        assistant = getattr(self, 'assistant', None)
        getter = getattr(assistant, 'pending_outcomes', None)
        if getter is None:
            return tuple({'prediction_id': prediction_id}
                         for prediction_id in self._assistant_pending_ids())
        try:
            entries = tuple(getter() or ())
        except Exception:  # noqa: BLE001
            entries = ()
        if entries:
            return entries
        return tuple({'prediction_id': prediction_id}
                     for prediction_id in self._assistant_pending_ids())

    def _assistant_startup_error(self):
        assistant = getattr(self, 'assistant', None)
        getter = getattr(assistant, 'startup_registry_error', None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:  # noqa: BLE001 - la GUI no debe caerse por esto
            return None

    @staticmethod
    def _pending_label(entry) -> str:
        hand = entry.get('hand_id')
        street = entry.get('street')
        action = entry.get('action')
        if not any((hand, street, action)):
            return ''
        parts = [str(hand or '?'), str(street or '?')]
        if entry.get('hu_position'):
            parts.append(str(entry['hu_position']))
        parts.append(str(action or '?'))
        return ' · '.join(parts)

    def _load_pending_from_assistant(self) -> None:
        entries = self._assistant_pending_entries()
        if entries:
            for entry in entries:
                prediction_id = entry.get('prediction_id')
                if not prediction_id:
                    continue
                self._add_pending_prediction(
                    prediction_id, label=self._pending_label(entry))
            self._start_blocked_by_pending = True
            self._update_question_panel(self.last_analysis)
            count = len(entries)
            self.auto_status_var.set(
                ('detenido: 1 prediccion anterior sin resultado; '
                 'marca la accion observada y pulsa Registrar.'
                 if count == 1 else
                 'detenido: %d predicciones anteriores sin resultado; '
                 'marca la accion observada y pulsa Registrar.' % count))
            self.decision_status_var.set(
                'reconciliacion pendiente antes de capturar')
            return
        error = self._assistant_startup_error()
        if error:
            self.auto_status_var.set(
                'ERROR: registro prospectivo no verificable: %s' % error)
            self.decision_status_var.set('ERROR registro: %s' % error)

    def _after_outcome_registered(self) -> None:
        if (self._start_blocked_by_pending and not self._pending_ids
                and not self._controller.is_alive and not self._starting):
            self._start_blocked_by_pending = False
            self.auto_status_var.set(
                'reconciliado; iniciando captura automatica...')
            self.root.after(300, self.start_auto)

    # ------------------------------------------------------------------
    # Arranque automatico
    # ------------------------------------------------------------------
    def _autostart(self) -> None:
        if not _flag('HU_GUI_AUTOSTART', True):
            return
        if self._controller.is_alive or self._starting:
            return
        self.start_auto()

    def start_auto(self) -> None:
        if getattr(self, '_starting', False):
            return
        if getattr(self._controller, 'is_alive', False):
            self.auto_status_var.set(
                'esperando a que termine el ciclo anterior...')
            return
        # El asistente bloquea el reinicio si quedaron predicciones sin
        # outcome. Se pregunta por ellas antes de capturar: capturar ahora
        # asociaria el resultado a otra mano.
        if self._assistant_pending_ids():
            self._start_blocked_by_pending = True
            self._load_pending_from_assistant()
            return
        registry_error = self._assistant_startup_error()
        if registry_error:
            self.auto_status_var.set(
                'ERROR: registro prospectivo no verificable: %s'
                % registry_error)
            self.decision_status_var.set(
                'ERROR registro: %s' % registry_error)
            return
        try:
            warning = self._capture_guard.acquire()
        except ConcurrencyError as exc:
            self.auto_status_var.set('ERROR: %s' % exc)
            self.decision_status_var.set('ERROR captura: %s' % exc)
            return
        self._starting = True
        self._cancel_start = False
        if warning:
            self.auto_status_var.set('preparando lectores... (%s)' % warning)
        else:
            self.auto_status_var.set(
                'preparando lectores y motor (puede tardar varios s)...')

        def worker():
            try:
                self.assistant.prepare()
                prepare_engine = getattr(
                    self.assistant, 'prepare_engine', None)
                if prepare_engine is not None:
                    prepare_engine()
            except Exception as exc:  # noqa: BLE001 - se muestra al operador
                self._ui(lambda e=exc: self._start_failed(e))
                return
            self._ui(lambda: self._start_polling(warning))

        threading.Thread(target=worker, daemon=True,
                         name='hu-gui-prepare').start()

    def _ui(self, callback) -> None:
        """Encola una llamada para el hilo de Tk (``after`` no es thread-safe)."""
        self._ui_queue.put(callback)

    def _start_failed(self, exc: Exception) -> None:
        self._starting = False
        self._capture_guard.release()
        self.auto_status_var.set('ERROR preparando: %s' % exc)

    def _start_polling(self, warning: Optional[str]) -> None:
        self._starting = False
        if (self._cancel_start
                or not getattr(self._capture_guard, 'held', False)):
            self.auto_status_var.set('detenido')
            return
        try:
            self._controller.start()
        except Exception as exc:  # noqa: BLE001
            self._capture_guard.release()
            self.auto_status_var.set('ERROR polling: %s' % exc)
            self.decision_status_var.set('ERROR polling: %s' % exc)
            return
        if warning:
            self.auto_status_var.set('activo; %s' % warning)
        else:
            self.auto_status_var.set('activo; esperando primer ciclo...')

    def stop_auto(self) -> None:
        self._starting = False
        self._cancel_start = True
        stopped = self._controller.stop()
        if stopped:
            self._capture_guard.release()
            self.auto_status_var.set('detenido')
            return
        self.auto_status_var.set(
            'parada solicitada; esperando al ciclo en curso...')
        worker = getattr(self._controller, '_thread', None)
        if worker is not None:
            threading.Thread(
                target=self._release_guard_after_worker, args=(worker,),
                name='hu-gui-lock-release', daemon=True).start()

    # ------------------------------------------------------------------
    # Eventos del polling
    # ------------------------------------------------------------------
    def _enqueue_event(self, event: PollEvent) -> None:
        self._event_queue.put(event)

    def _drain_events(self) -> None:
        try:
            while True:
                callback = self._ui_queue.get_nowait()
                try:
                    callback()
                except Exception as exc:  # noqa: BLE001 - se informa en la GUI
                    self.auto_status_var.set('ERROR: %s' % exc)
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            while True:
                event = self._event_queue.get_nowait()
                try:
                    self._handle_event(event)
                except Exception as exc:  # noqa: BLE001 - no matar el drenaje
                    self.auto_status_var.set(
                        'ERROR presentando evento: %s' % exc)
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
            if ('reinicio bloqueado' in event.error or
                    'predicciones previas sin outcome' in event.error):
                self._load_pending_from_assistant()
                self._start_blocked_by_pending = True
                try:
                    self._controller.stop()
                finally:
                    self._capture_guard.release()
                return
            fatal = ('recurso de captura ocupado' in event.error or
                     'no se pudo verificar si asistente_live' in event.error or
                     'registro prospectivo no verificable' in event.error)
            if fatal:
                self._controller.stop()
                self._capture_guard.release()
            timing = (' | ciclo %.1f ms' % event.elapsed_ms
                      if event.elapsed_ms is not None else '')
            self.auto_status_var.set('ERROR: %s%s' % (event.error, timing))
            self.decision_status_var.set('ERROR auto: %s' % event.error)
            return

        analysis = event.analysis
        if analysis is not None:
            self.last_analysis = analysis
            self.last_frame = getattr(self.assistant, '_last_frame', None)
            self._present_analysis(analysis)

        if event.registration is not None:
            self.last_registration = event.registration
            self.persist_status_var.set(
                'auto-persistida: %s' % event.registration.prediction_id)
            label = None
            registered = getattr(event.registration, 'analysis', None)
            if registered is not None:
                state = registered.state
                label = '%s · %s · %s' % (
                    state.hand_id or '?', state.street or '?',
                    registered.provisional_selected_action or '?')
            self._add_pending_prediction(
                event.registration.prediction_id, label=label)
            self._refresh_registry_status()

        if analysis is not None:
            timing = (' | ciclo %.1f ms' % event.elapsed_ms
                      if event.elapsed_ms is not None else '')
            snapshot = getattr(analysis, 'snapshot', None) or {}
            hand = analysis.state.hand_id or snapshot.get('hand_id') or '—'
            self.auto_status_var.set(
                'activo; mano %s | calle %s%s'
                % (hand, analysis.state.street, timing))

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------
    def destroy(self) -> None:
        stopped = False
        try:
            stopped = self._controller.stop()
        finally:
            try:
                # No liberar exclusividad si la captura/polling no termino.
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
