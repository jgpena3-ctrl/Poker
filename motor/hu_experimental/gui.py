"""GUI experimental HU independiente (Fase 10).

No importa ``motor.asistente_live_gui`` ni ejecuta acciones de poker. Muestra
estado observado, incertidumbre y prediccion experimental, y permite persistir
la prediccion en el registro prospectivo aislado.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Optional

from .assistant import EXPERIMENTAL_VERSION, HUExperimentalAssistant
from .config import ExperimentalConfig


TITLE = 'HU Experimental — solo observacion (no validado)'
WARNING = (
    'MODO EXPERIMENTAL. Las predicciones NO estan validadas estrategicamente '
    'y NO deben usarse como verdad para jugar dinero real. Esta ventana no '
    'ejecuta acciones de poker.'
)


class HUExperimentalGUI:
    """Interfaz independiente de observacion y registro manual."""

    def __init__(self, root: Optional[tk.Misc] = None,
                 assistant: Optional[HUExperimentalAssistant] = None,
                 config: Optional[ExperimentalConfig] = None):
        self.root = root or tk.Tk()
        self.config = config or ExperimentalConfig.default()
        self.assistant = assistant or HUExperimentalAssistant(self.config)
        self.last_analysis = None
        self.last_registration = None
        self.last_frame = None

        self.root.title(TITLE)
        self.root.geometry('980x820')
        self.root.minsize(760, 640)
        self._build_ui()
        self._refresh_registry_status()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        warning = ttk.Label(main, text=WARNING, foreground='#8a1c1c',
                            wraplength=920, justify=tk.LEFT,
                            font=('', 10, 'bold'))
        warning.pack(fill=tk.X, pady=(0, 8))

        path_frame = ttk.LabelFrame(main, text='Registro aislado', padding=8)
        path_frame.pack(fill=tk.X, pady=(0, 8))
        self.registry_var = tk.StringVar(value=str(self.assistant.registry_path))
        ttk.Label(path_frame, text='Ruta:').pack(side=tk.LEFT)
        ttk.Entry(path_frame, textvariable=self.registry_var, width=72,
                  state='readonly').pack(side=tk.LEFT, padx=(5, 8),
                                         fill=tk.X, expand=True)
        self.registry_status_var = tk.StringVar(value='sin verificar')
        ttk.Label(path_frame, textvariable=self.registry_status_var,
                  foreground='#555555').pack(side=tk.LEFT)

        controls = ttk.Frame(main)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(controls, text='Capturar estado',
                   command=self.capture_state).pack(side=tk.LEFT)
        ttk.Button(controls, text='Analizar',
                   command=self.analyze_current).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(controls, text='Registrar prediccion',
                   command=self.register_prediction).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(controls, text='Verificar integridad',
                   command=self.verify_registry).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(controls, text='Crear backup',
                   command=self.create_backup).pack(side=tk.LEFT, padx=(6, 0))

        status_frame = ttk.LabelFrame(main, text='Estado de captura e interpretacion',
                                      padding=8)
        status_frame.pack(fill=tk.X, pady=(0, 8))
        self.capture_status_var = tk.StringVar(value='sin captura')
        self.ocr_status_var = tk.StringVar(value='sin OCR')
        self.decision_status_var = tk.StringVar(value='sin decision')
        self.equity_status_var = tk.StringVar(value='sin equity')
        self.action_status_var = tk.StringVar(value='sin accion')
        self.persist_status_var = tk.StringVar(value='sin prediccion persistida')
        for label, var in (
                ('Captura', self.capture_status_var),
                ('OCR', self.ocr_status_var),
                ('Decision', self.decision_status_var),
                ('Equity', self.equity_status_var),
                ('Accion', self.action_status_var),
                ('Registro', self.persist_status_var)):
            row = ttk.Frame(status_frame)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=label + ':', width=9, anchor=tk.W).pack(side=tk.LEFT)
            ttk.Label(row, textvariable=var, wraplength=820,
                      justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)

        detail_frame = ttk.LabelFrame(main, text='Detalle observable / inferido / prediccion',
                                      padding=8)
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.detail_text = tk.Text(detail_frame, height=18, wrap=tk.WORD,
                                   state=tk.DISABLED)
        scroll = ttk.Scrollbar(detail_frame, command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=scroll.set)
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.tag_configure('observed', foreground='#1b5e20')
        self.detail_text.tag_configure('inferred', foreground='#6a4c00')
        self.detail_text.tag_configure('unknown', foreground='#8a1c1c')
        self.detail_text.tag_configure('prediction', foreground='#123c7a',
                                       font=('', 10, 'bold'))
        self.detail_text.tag_configure('posterior', foreground='#4a148c')

        outcome_frame = ttk.LabelFrame(main, text='Resultado posterior (evento separado)',
                                       padding=8)
        outcome_frame.pack(fill=tk.X)
        self.outcome_prediction_var = tk.StringVar(value='')
        self.outcome_action_var = tk.StringVar(value='')
        self.outcome_exclusion_var = tk.StringVar(value='')
        ttk.Label(outcome_frame, text='Prediction ID:').grid(
            row=0, column=0, sticky=tk.W)
        ttk.Entry(outcome_frame, textvariable=self.outcome_prediction_var,
                  width=36).grid(row=0, column=1, sticky=tk.W, padx=(4, 10))
        ttk.Label(outcome_frame, text='Accion observada:').grid(
            row=0, column=2, sticky=tk.W)
        ttk.Entry(outcome_frame, textvariable=self.outcome_action_var,
                  width=18).grid(row=0, column=3, sticky=tk.W, padx=(4, 10))
        ttk.Label(outcome_frame, text='Exclusion:').grid(
            row=0, column=4, sticky=tk.W)
        ttk.Entry(outcome_frame, textvariable=self.outcome_exclusion_var,
                  width=24).grid(row=0, column=5, sticky=tk.W, padx=(4, 10))
        ttk.Button(outcome_frame, text='Registrar resultado',
                   command=self.register_outcome).grid(row=0, column=6)

        ttk.Label(main, text='No hay botones de fold/call/raise/all-in. '
                             'La captura es manual y no hay polling automatico.',
                  foreground='#555555').pack(fill=tk.X, pady=(6, 0))

    def _set_detail(self, analysis) -> None:
        text = self.detail_text
        text.configure(state=tk.NORMAL)
        text.delete('1.0', tk.END)
        state = analysis.state
        text.insert(tk.END, 'OBSERVADO\n', 'observed')
        text.insert(tk.END, '  Asientos activos: %s\n' % (state.active_seats,))
        text.insert(tk.END, '  Hero: %s | rival: %s | posiciones: %s/%s\n'
                    % (state.hero_seat, state.villain_seat,
                       state.hero_position, state.villain_position))
        text.insert(tk.END, '  Cartas hero: %s | board: %s | calle: %s\n'
                    % (state.hero_cards, state.board, state.street))
        text.insert(tk.END, '  Pot: %s | to_call: %s | stacks: %s/%s | bets: %s/%s\n'
                    % (state.pot, state.to_call, state.hero_stack,
                       state.villain_stack, state.hero_bet, state.villain_bet))
        text.insert(tk.END, '  Campos observados: %s\n'
                    % ', '.join(state.observed_fields))
        text.insert(tk.END, '\nINFERIDO\n', 'inferred')
        text.insert(tk.END, '  Rango: %s (%s)\n'
                    % (analysis.range_kind, analysis.range_source))
        text.insert(tk.END, '  Cobertura: %s | secuencia: %s\n'
                    % (analysis.coverage_state, analysis.sequence_status))
        text.insert(tk.END, '  Nota: el prior es plano; no describe al rival.\n')
        text.insert(tk.END, '\nDESCONOCIDO / LIMITACIONES\n', 'unknown')
        for reason in analysis.uncertainty_reasons or ('sin motivos',):
            text.insert(tk.END, '  - %s\n' % reason)
        for warning in analysis.warnings:
            text.insert(tk.END, '  - captura: %s\n' % warning)
        text.insert(tk.END, '\nPREDICCION EXPERIMENTAL\n', 'prediction')
        text.insert(tk.END, '  Estado canonico: %s (%s)\n'
                    % (analysis.canonical_status, analysis.canonical_reason))
        text.insert(tk.END, '  Equity: %s | metodo: %s | incertidumbre: %s\n'
                    % (analysis.equity, analysis.equity_method,
                       analysis.equity_uncertainty))
        if analysis.ev_result is not None:
            text.insert(tk.END, '  EV status: %s | mejor EV: %s\n'
                        % (analysis.ev_result.status,
                           analysis.ev_result.best_action))
            for action in analysis.ev_result.actions:
                text.insert(tk.END, '    %s: ev=%s status=%s reason=%s\n'
                            % (action.action, action.ev, action.status,
                               action.reason))
        if analysis.selected_action:
            text.insert(tk.END, '  Accion demostrada: %s\n'
                        % analysis.selected_action)
        elif analysis.provisional_selected_action:
            text.insert(tk.END, '  Accion provisional (NO demostrada): %s\n'
                        % analysis.provisional_selected_action)
        else:
            text.insert(tk.END, '  Sin accion recomendada: datos insuficientes.\n')
        text.insert(tk.END, '\nSUPUESTOS\n', 'posterior')
        for assumption in analysis.assumptions:
            text.insert(tk.END, '  - %s\n' % assumption)
        text.configure(state=tk.DISABLED)

    def _refresh_registry_status(self) -> None:
        try:
            result = self.assistant.verify()
            if result.ok:
                self.registry_status_var.set('integridad OK (%d eventos)'
                                             % result.event_count)
            else:
                self.registry_status_var.set('ERROR: %s'
                                             % '; '.join(result.issues))
        except Exception as exc:  # noqa: BLE001 - se muestra al operador
            self.registry_status_var.set('ERROR: %s' % exc)

    def capture_state(self) -> None:
        try:
            frame = self.assistant.capture()
        except Exception as exc:  # noqa: BLE001
            self.capture_status_var.set('ERROR: %s' % exc)
            self.ocr_status_var.set('captura fallida')
            return
        self.last_frame = frame
        self.capture_status_var.set('%s; %.1f ms' % (
            frame.source, frame.capture_ms or 0.0))
        self.ocr_status_var.set(
            'warnings=%s; OCR=%.1f ms' % (
                ', '.join(frame.warnings) or 'ninguno', frame.ocr_ms or 0.0))
        self.analyze_current()

    def analyze_current(self) -> None:
        source = self.last_frame
        if source is None:
            self.decision_status_var.set('capture primero')
            return
        try:
            analysis = self.assistant.analyze(source)
        except Exception as exc:  # noqa: BLE001
            self.decision_status_var.set('ERROR: %s' % exc)
            return
        self.last_analysis = analysis
        state = analysis.state
        self.decision_status_var.set(
            '%s | HU=%s | calle=%s' % (analysis.canonical_status,
                                       state.status, state.street))
        if analysis.equity is None:
            self.equity_status_var.set(
                'unknown | %s' % (analysis.equity_uncertainty or
                                  'sin equity calculable'))
        else:
            self.equity_status_var.set(
                '%.4f | %s | %s' % (analysis.equity, analysis.equity_method,
                                    analysis.equity_uncertainty or
                                    'sin incertidumbre declarada'))
        if analysis.selected_action:
            self.action_status_var.set('demostrada: %s'
                                       % analysis.selected_action)
        elif analysis.provisional_selected_action:
            self.action_status_var.set('provisional NO demostrada: %s'
                                       % analysis.provisional_selected_action)
        else:
            self.action_status_var.set('sin recomendacion')
        self._set_detail(analysis)

    def register_prediction(self) -> None:
        if self.last_frame is None:
            messagebox.showinfo('Sin captura', 'Captura un estado primero.')
            return
        try:
            registration = self.assistant.predict_and_register(self.last_frame)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Fallo de persistencia', str(exc))
            self.persist_status_var.set('ERROR: %s' % exc)
            return
        self.last_registration = registration
        self.persist_status_var.set('persistida: %s'
                                    % registration.prediction_id)
        self.outcome_prediction_var.set(registration.prediction_id)
        self._refresh_registry_status()
        self._set_detail(registration.analysis)

    def register_outcome(self) -> None:
        prediction_id = self.outcome_prediction_var.get().strip()
        if not prediction_id:
            messagebox.showinfo('Falta prediction ID',
                                'Indica la prediccion a la que corresponde.')
            return
        action = self.outcome_action_var.get().strip() or None
        exclusion = self.outcome_exclusion_var.get().strip() or None
        try:
            self.assistant.record_outcome(
                prediction_id, observed_action=action,
                exclusion_reason=exclusion)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Fallo de registro', str(exc))
            return
        self.persist_status_var.set('resultado registrado para %s'
                                    % prediction_id)
        self._refresh_registry_status()

    def verify_registry(self) -> None:
        try:
            result = self.assistant.verify()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Verificacion fallida', str(exc))
            return
        self._refresh_registry_status()
        if result.ok:
            messagebox.showinfo('Integridad', 'Registro integro: %d eventos.'
                                % result.event_count)
        else:
            messagebox.showerror('Integridad', '\n'.join(result.issues))

    def create_backup(self) -> None:
        try:
            result = self.assistant.create_backup()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Backup fallido', str(exc))
            return
        messagebox.showinfo(
            'Backup creado',
            '%s\nSHA-256: %s\nEventos: %d'
            % (result.backup_path, result.sha256, result.event_count))

    def run(self) -> None:
        self.root.mainloop()

    def destroy(self) -> None:
        self.root.destroy()


def main(argv: Optional[list] = None) -> int:
    del argv
    gui = HUExperimentalGUI()
    gui.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
