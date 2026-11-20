"""GUI experimental HU independiente (Fase 10).

Ventana compacta (367x719 por defecto, dentro de los 368 disponibles) anclada
al borde derecho de la pantalla: no tapa las zonas de interes que lee el
capturador. Muestra solo lo necesario (estado leido, recomendacion y preguntas
al operador) y conserva el detalle tecnico en una pestana secundaria.

No importa ``motor.asistente_live_gui`` ni ejecuta acciones de poker.
"""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Mapping, Optional


from .assistant import EXPERIMENTAL_VERSION, HUExperimentalAssistant
from .config import ExperimentalConfig


TITLE = 'HU Experimental (NO validado)'
WARNING = (
    'MODO EXPERIMENTAL. Recomendacion no validada y sin acciones de poker. '
    'La ventana se ancla al borde derecho para no tapar la mesa.'
)

WINDOW_WIDTH = 367
WINDOW_HEIGHT = 719
PAD = 6
FONT_SMALL = ('', 8)
FONT_TINY = ('', 7)
FONT_RECO = ('', 14, 'bold')

FOLD_LABELS = ('fold', 'check', 'call', 'raise', 'all-in', 'unknown')


# ---------------------------------------------------------------------------
# Texto para el operador
# ---------------------------------------------------------------------------
_HINTS = {
    'active_player_count_uncertain': (
        'No puedo confirmar exactamente 2 jugadores activos (HU).'),
    'hero_cards_ocr_vs_recorded': (
        'Tus cartas leidas no coinciden con las registradas.'),
    'hero_cards_not_observed': 'No veo tus cartas.',
    'board_ocr_vs_recorded': 'El board leido no coincide con el registrado.',
    'board_missing_in_ocr_but_recorded': (
        'No veo el board aunque el recorder lo tiene.'),
    'board_not_observed': 'No veo el board.',
    'invalid_board_count': 'El board tiene un numero de cartas invalido.',
    'button_not_in_active': 'El boton esta en un asiento inactivo.',
    'hu_positions_not_observable': (
        'No puedo determinar quien es SB y quien BB.'),
    'position_not_observed': 'No puedo determinar las posiciones.',
    'to_call_explicit_vs_derived': 'La cantidad a igualar no cuadra.',
    'to_call_bets_vs_contributions': 'Las apuestas no cuadran con el bote.',
    'to_call_not_observed': 'No veo cuanto hay que igualar.',
    'economic_state_incomplete': 'Falta el bote o algun stack.',
    'pot_not_observed': 'No veo el bote.',
    'duplicate_cards': 'Hay cartas duplicadas.',
    'recorder_error': 'El recorder fallo al procesar la mano.',
    'invalid_numeric': 'Hay un numero leido invalido.',
    'frame_not_processed': 'La captura aun se esta procesando.',
    'recorder_snapshot_unavailable': 'El recorder no devolvio estado.',
    'invalid_state': 'El estado leido no es interpretable.',
    'hero_not_active': 'No estas en la mano.',
    'not_heads_up': (
        'Aun hay mas de 2 jugadores activos en la mano; esperando que queden 2.'),
    'awaiting_preflop_after_midhand_start': (
        'Paridad iniciada con la mano en curso; espero una mano nueva desde '
        'preflop para reconstruir el bote.'),
    'pot_read_vs_calculated': (
        'El bote leido no cuadra con el ledger. Sin recomendacion hasta '
        'reconciliar; si empezaste a mitad de mano, espera la proxima.'),
    'position_mode_live_6max_situation_hu': (
        'Modo 6-max: recomiendo en la situacion HU (2 activos) usando las '
        'posiciones y el orden de la mesa.'),
    'position_mode_hu_correction_not_exact_live_parity': (
        'Modo HU: corrige SB/BB y el orden postflop; no es paridad exacta '
        'con la mesa live.'),
    'position_mapping_live_btn_vs_hu_sb': (
        'La mesa 6-max tiene al hero en BTN; la situacion HU lo mapea a SB. '
        'La recomendacion usa la posicion live (BTN).'),
    'no_hu_decision_pending': 'Esperando tu turno.',
    'hand_finalized_during_capture_cycle': (
        'Mano terminada; esperando la siguiente.'),
    'hero_identity_mismatch': (
        'El asiento del heroe no coincide con el del motor.'),
    'postflop_position_order_unverified': (
        'Aun no puedo verificar el orden postflop.'),
    'live_engine_no_recommendation': (
        'El motor no produjo recomendacion en esta captura.'),
    'live_engine_error': 'El motor fallo al calcular.',
}

# Codigos que solo indican "espera", no una pregunta al operador.
_WAIT_CODES = {
    'no_hu_decision_pending',
    'hand_finalized_during_capture_cycle',
    'frame_not_processed',
    'hero_not_active',
}


def _hint(code: Any) -> str:
    text = str(code or '').strip()
    if not text:
        return ''
    if text.startswith('contradiction:'):
        text = text.split(':', 1)[1]
    base = text.split(':', 1)[0]
    if base in _HINTS:
        return _HINTS[base]
    if text.startswith('not_heads_up'):
        return _HINTS['not_heads_up']
    return text


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _flag(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in ('0', 'false', 'no', 'off')


def _fmt(value: Any) -> str:
    if value is None:
        return '—'
    if isinstance(value, bool):
        return 'si' if value else 'no'
    if isinstance(value, float):
        text = ('%.2f' % value).rstrip('0').rstrip('.')
        return text or '0'
    return str(value)


def _fmt_cards(cards: Any) -> str:
    if not cards:
        return '—'
    return ' '.join(str(card) for card in cards)


def _fmt_pair(hero: Any, villain: Any) -> str:
    return '%s / %s' % (_fmt(hero), _fmt(villain))


class HUExperimentalGUI:
    """Interfaz compacta de observacion y registro manual."""

    window_title = TITLE
    window_warning = WARNING

    def __init__(self, root: Optional[tk.Misc] = None,
                 assistant: Optional[HUExperimentalAssistant] = None,
                 config: Optional[ExperimentalConfig] = None):
        self.root = root or tk.Tk()
        self.config = config or ExperimentalConfig.default()
        self.assistant = assistant or HUExperimentalAssistant(self.config)
        self.last_analysis = None
        self.last_registration = None
        self.last_frame = None
        self._pending_ids: list = []
        self._pending_labels: dict = {}
        self._outcome_choices: dict = {}
        self._quick_buttons: list = []

        self.root.title(self.window_title)
        self._apply_geometry()
        self._build_ui()
        self._refresh_registry_status()

    # ------------------------------------------------------------------
    # Geometria: ventana fija en el borde derecho, fuera de la mesa
    # ------------------------------------------------------------------
    def _apply_geometry(self) -> None:
        width = _env_int('HU_GUI_WIDTH', WINDOW_WIDTH)
        height = _env_int('HU_GUI_HEIGHT', WINDOW_HEIGHT)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = _env_int('HU_GUI_X', max(0, screen_w - width))
        y = _env_int('HU_GUI_Y', 0)
        # Sin bordes: los 368 px del borde derecho son espacio util real. Con
        # decoraciones de Windows el area cliente se saldria de la pantalla.
        if _flag('HU_GUI_BORDERLESS', True):
            try:
                self.root.overrideredirect(True)
            except tk.TclError:
                pass
        self.root.geometry('%dx%d+%d+%d' % (width, height, x, y))
        self.root.resizable(False, False)
        if _flag('HU_GUI_TOPMOST', True):
            try:
                self.root.attributes('-topmost', True)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------
    # Construccion de la interfaz
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=PAD)
        main.pack(fill=tk.BOTH, expand=True)
        self._build_header(main)
        self._build_live_panel(main)
        self._build_recommendation(main)
        self._build_question_panel(main)
        self._build_notebook(main)

    def _build_header(self, parent) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(0, 4))

        title_row = ttk.Frame(frame)
        title_row.pack(fill=tk.X)
        title = ttk.Label(title_row, text=self.window_title,
                          font=('', 9, 'bold'),
                          wraplength=WINDOW_WIDTH - 2 * PAD - 40,
                          justify=tk.LEFT)
        title.pack(side=tk.LEFT, anchor=tk.W)
        ttk.Button(title_row, text='✕', width=2,
                   command=self.destroy).pack(side=tk.RIGHT)
        self._drag_offset = None
        title.bind('<ButtonPress-1>', self._begin_drag)
        title.bind('<B1-Motion>', self._on_drag)

        ttk.Label(frame, text=self.window_warning, foreground='#8a1c1c',
                  font=FONT_TINY, wraplength=WINDOW_WIDTH - 2 * PAD - 8,
                  justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 3))

        self.auto_status_var = tk.StringVar(value='detenido')
        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)
        self._build_primary_buttons(buttons)

        ttk.Label(frame, textvariable=self.auto_status_var,
                  foreground='#123c7a', font=FONT_TINY,
                  wraplength=WINDOW_WIDTH - 2 * PAD - 8,
                  justify=tk.LEFT).pack(anchor=tk.W, pady=(3, 0))

    def _begin_drag(self, event) -> None:
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y())

    def _on_drag(self, event) -> None:
        if self._drag_offset is None:
            return
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        try:
            self.root.geometry('+%d+%d' % (x, y))
        except tk.TclError:
            pass

    def _build_primary_buttons(self, parent) -> None:
        ttk.Button(parent, text='Preparar lectores',
                   command=self.prepare_readers).pack(side=tk.LEFT)
        ttk.Button(parent, text='Capturar',
                   command=self.capture_state).pack(side=tk.LEFT, padx=(4, 0))

    def _build_live_panel(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text='Mesa (lectura en vivo)',
                               padding=4)
        frame.pack(fill=tk.X, pady=(0, 4))
        self.live_vars: dict = {}
        rows = (
            ('calle', 'Calle'),
            ('mano', 'Mano'),
            ('pos', 'Posiciones'),
            ('cartas', 'Tus cartas'),
            ('board', 'Board'),
            ('bote', 'Bote'),
            ('to_call', 'Igualar'),
            ('stacks', 'Stacks tu/rival'),
            ('bets', 'Apuestas tu/rival'),
        )
        for row, (key, label) in enumerate(rows):
            ttk.Label(frame, text=label + ':', width=15, anchor=tk.W,
                      font=FONT_TINY).grid(row=row, column=0, sticky=tk.W)
            variable = tk.StringVar(value='—')
            self.live_vars[key] = variable
            ttk.Label(frame, textvariable=variable, anchor=tk.W,
                      font=FONT_SMALL,
                      wraplength=WINDOW_WIDTH - 2 * PAD - 120,
                      justify=tk.LEFT).grid(row=row, column=1, sticky=tk.W)

    def _build_recommendation(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text='Recomendacion (no vinculante)',
                               padding=4)
        frame.pack(fill=tk.X, pady=(0, 4))
        self.reco_var = tk.StringVar(value='—')
        ttk.Label(frame, textvariable=self.reco_var, font=FONT_RECO,
                  foreground='#123c7a',
                  wraplength=WINDOW_WIDTH - 2 * PAD - 16,
                  justify=tk.LEFT).pack(anchor=tk.W)
        self.reco_detail_var = tk.StringVar(value='')
        ttk.Label(frame, textvariable=self.reco_detail_var, font=FONT_TINY,
                  wraplength=WINDOW_WIDTH - 2 * PAD - 16,
                  justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 0))

    def _build_question_panel(self, parent) -> None:
        frame = ttk.LabelFrame(parent, text='Necesito de ti', padding=4)
        frame.pack(fill=tk.X, pady=(0, 4))
        self.question_var = tk.StringVar(value='Sin preguntas pendientes.')
        ttk.Label(frame, textvariable=self.question_var, font=FONT_SMALL,
                  wraplength=WINDOW_WIDTH - 2 * PAD - 16,
                  justify=tk.LEFT).pack(anchor=tk.W)

        self.outcome_prediction_var = tk.StringVar()
        self.outcome_action_var = tk.StringVar()
        self.outcome_exclusion_var = tk.StringVar()

        ttk.Label(frame, text='Resultado observado del rival:', font=FONT_TINY,
                  foreground='#555555').pack(anchor=tk.W, pady=(3, 0))
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=(1, 0))
        self._outcome_box = ttk.Combobox(
            row, textvariable=self.outcome_prediction_var, values=(),
            state='disabled', width=24, font=FONT_TINY)
        self._outcome_box.pack(side=tk.LEFT)
        self._outcome_action_box = ttk.Combobox(
            row, textvariable=self.outcome_action_var, values=FOLD_LABELS,
            state='disabled', width=7, font=FONT_TINY)
        self._outcome_action_box.pack(side=tk.LEFT, padx=(3, 0))
        self._register_outcome_button = ttk.Button(
            row, text='Registrar', command=self.register_outcome,
            state='disabled')
        self._register_outcome_button.pack(side=tk.LEFT, padx=(3, 0))

        quick = ttk.Frame(frame)
        quick.pack(fill=tk.X, pady=(3, 0))
        self._quick_buttons = []
        for action in FOLD_LABELS[:-1]:
            button = ttk.Button(
                quick, text=action, width=5, state='disabled',
                command=lambda value=action: self._quick_outcome(value))
            button.pack(side=tk.LEFT, padx=(0, 2))
            self._quick_buttons.append(button)

    def _build_notebook(self, parent) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        detail = ttk.Frame(notebook, padding=2)
        notebook.add(detail, text='Detalle')
        self.detail_text = tk.Text(detail, width=1, height=4, wrap=tk.WORD,
                                   state=tk.DISABLED, font=('Consolas', 7))
        scroll = ttk.Scrollbar(detail, command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=scroll.set)
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.tag_configure('observed', foreground='#1b5e20')
        self.detail_text.tag_configure('inferred', foreground='#6a4c00')
        self.detail_text.tag_configure('unknown', foreground='#8a1c1c')
        self.detail_text.tag_configure('prediction', foreground='#123c7a',
                                       font=('Consolas', 7, 'bold'))
        self.detail_text.tag_configure('posterior', foreground='#4a148c')

        advanced = ttk.Frame(notebook)
        notebook.add(advanced, text='Avanzado')
        self._build_advanced(advanced)

    def _build_advanced(self, parent) -> None:
        canvas = tk.Canvas(parent, width=1, height=1, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient='vertical',
                               command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        frame = ttk.Frame(canvas, padding=2)
        window = canvas.create_window((0, 0), window=frame, anchor='nw')
        frame.bind('<Configure>',
                   lambda event: canvas.configure(
                       scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',
                    lambda event: canvas.itemconfigure(window,
                                                       width=event.width))

        ttk.Label(frame, text='Registro aislado',
                  font=('', 8, 'bold')).pack(anchor=tk.W)
        self.registry_var = tk.StringVar(value=str(self.assistant.registry_path))
        ttk.Entry(frame, textvariable=self.registry_var, state='readonly',
                  width=36, font=FONT_TINY).pack(fill=tk.X, pady=(1, 1))
        self.registry_status_var = tk.StringVar(value='sin verificar')
        ttk.Label(frame, textvariable=self.registry_status_var,
                  foreground='#555555', font=FONT_TINY,
                  wraplength=WINDOW_WIDTH - 2 * PAD - 40,
                  justify=tk.LEFT).pack(anchor=tk.W)

        ttk.Separator(frame).pack(fill=tk.X, pady=4)
        ttk.Label(frame, text='Control manual (alternativa al automatico)',
                  font=('', 8, 'bold')).pack(anchor=tk.W)
        manual = ttk.Frame(frame)
        manual.pack(fill=tk.X, pady=(2, 0))
        ttk.Button(manual, text='Preparar',
                   command=self.prepare_readers).pack(side=tk.LEFT)
        ttk.Button(manual, text='Capturar',
                   command=self.capture_state).pack(side=tk.LEFT, padx=(3, 0))
        ttk.Button(manual, text='Analizar',
                   command=self.analyze_current).pack(side=tk.LEFT, padx=(3, 0))
        ttk.Button(manual, text='Registrar',
                   command=self.register_prediction).pack(side=tk.LEFT,
                                                          padx=(3, 0))

        ttk.Separator(frame).pack(fill=tk.X, pady=4)
        self.capture_status_var = tk.StringVar(value='sin captura')
        self.ocr_status_var = tk.StringVar(value='sin OCR')
        self.decision_status_var = tk.StringVar(value='sin decision')
        self.equity_status_var = tk.StringVar(value='sin equity')
        self.action_status_var = tk.StringVar(value='sin accion')
        self.persist_status_var = tk.StringVar(
            value='sin prediccion persistida')
        for label, variable in (
                ('Captura', self.capture_status_var),
                ('OCR', self.ocr_status_var),
                ('Decision', self.decision_status_var),
                ('Equity', self.equity_status_var),
                ('Accion', self.action_status_var),
                ('Registro', self.persist_status_var)):
            ttk.Label(frame, text=label + ':', font=FONT_TINY,
                      foreground='#555555').pack(anchor=tk.W)
            ttk.Label(frame, textvariable=variable, font=FONT_TINY,
                      wraplength=WINDOW_WIDTH - 2 * PAD - 40,
                      justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 2))

        ttk.Separator(frame).pack(fill=tk.X, pady=4)
        ttk.Label(frame, text='Exclusion (opcional)',
                  font=FONT_TINY).pack(anchor=tk.W)
        ttk.Entry(frame, textvariable=self.outcome_exclusion_var, width=36,
                  font=FONT_TINY).pack(fill=tk.X, pady=(1, 3))

        tools = ttk.Frame(frame)
        tools.pack(fill=tk.X)
        ttk.Button(tools, text='Verificar integridad',
                   command=self.verify_registry).pack(side=tk.LEFT)
        ttk.Button(tools, text='Crear backup',
                   command=self.create_backup).pack(side=tk.LEFT, padx=(3, 0))

        ttk.Separator(frame).pack(fill=tk.X, pady=4)
        ttk.Label(
            frame,
            text=('modo=%s | poll=%.2fs | hands=%s'
                  % (self.config.parity_position_mode,
                     self.config.auto_poll_s,
                     self.config.parity_hands_path)),
            foreground='#555555', font=FONT_TINY,
            wraplength=WINDOW_WIDTH - 2 * PAD - 40,
            justify=tk.LEFT).pack(anchor=tk.W)
        ttk.Label(frame, text=EXPERIMENTAL_VERSION,
                  foreground='#777777', font=FONT_TINY).pack(anchor=tk.W)

    # ------------------------------------------------------------------
    # Presentacion del estado observado
    # ------------------------------------------------------------------
    def _update_live_panel(self, analysis) -> None:
        state = analysis.state
        snapshot = getattr(analysis, 'snapshot', None) or {}
        recorder = getattr(analysis, 'recorder_snapshot', None)
        hand_id = state.hand_id or snapshot.get('hand_id')
        if hand_id is None and recorder is not None:
            try:
                hand_id = recorder.raw_state.get('hand_id')
            except AttributeError:
                hand_id = None

        self.live_vars['calle'].set(str(state.street or '—'))
        self.live_vars['mano'].set(_fmt(hand_id))
        self.live_vars['pos'].set('%s / %s' % (
            state.hero_position or '—', state.villain_position or '—'))
        self.live_vars['cartas'].set(_fmt_cards(state.hero_cards))
        self.live_vars['board'].set(_fmt_cards(state.board))
        self.live_vars['bote'].set(_fmt(state.pot))
        self.live_vars['to_call'].set(_fmt(state.to_call))
        self.live_vars['stacks'].set(
            _fmt_pair(state.hero_stack, state.villain_stack))
        self.live_vars['bets'].set(
            _fmt_pair(state.hero_bet, state.villain_bet))

    def _set_recommendation(self, analysis) -> None:
        recommendation = (
            analysis.selected_action
            or analysis.provisional_selected_action
            or getattr(analysis, 'live_recommendation', None))
        if recommendation:
            self.reco_var.set(str(recommendation))
        else:
            self.reco_var.set('Sin recomendacion')

        pieces = []
        if analysis.equity is None:
            if analysis.equity_uncertainty:
                pieces.append('equity: no calculada (%s)'
                              % analysis.equity_uncertainty)
            else:
                pieces.append('equity: no calculada')
        else:
            pieces.append('equity %.4f' % analysis.equity)
        ev = analysis.ev_result
        if ev is not None and getattr(ev, 'best_action', None):
            pieces.append('mejor EV: %s' % ev.best_action)
        pieces.append('estado: %s' % analysis.canonical_status)
        if not recommendation:
            reason = (getattr(analysis, 'canonical_reason', None)
                      or getattr(analysis.state, 'reason', None))
            if reason:
                pieces.append('bloqueo: %s' % _hint(reason))
        block = getattr(analysis, 'recorder_snapshot', None)
        if block is not None and block.contradictions:
            pieces.append('contradicciones: %d' % len(block.contradictions))
        self.reco_detail_var.set(' | '.join(pieces))

    def _blockers(self, analysis) -> list:
        items = []
        state = analysis.state
        if state.status != 'ready' and state.reason:
            items.append(state.reason)
        recorder = getattr(analysis, 'recorder_snapshot', None)
        if recorder is not None:
            items.extend(recorder.contradictions)
            items.extend(str(item.get('code') or 'ambiguity')
                         for item in recorder.ambiguities)
        else:
            items.extend(getattr(state, 'contradictions', ()) or ())
        if not state.hero_cards:
            items.append('hero_cards_not_observed')
        if state.pot is None:
            items.append('pot_not_observed')

        questions = []
        seen = set()
        for item in items:
            text = _hint(item)
            if text and text not in seen:
                seen.add(text)
                questions.append(text)
        return questions

    def _update_question_panel(self, analysis=None) -> None:
        lines = []
        if analysis is not None:
            questions = self._blockers(analysis)
            if questions:
                lines.append('Para poder decidir necesito:')
                for question in questions[:3]:
                    lines.append('• ' + question)
                if len(questions) > 3:
                    lines.append('• (+%d mas, ver Detalle)'
                                 % (len(questions) - 3))
        if self._pending_ids:
            if lines:
                lines.append('')
            lines.append(
                ('1 prediccion sin resultado. Marca la accion del rival.'
                 if len(self._pending_ids) == 1 else
                 '%d predicciones sin resultado. Marca la accion del rival.'
                 % len(self._pending_ids)))
            latest = self._pending_ids[-1]
            label = self._pending_labels.get(latest)
            if label:
                lines.append('  ' + label)
        if not lines:
            lines.append('Sin preguntas pendientes.')
        self.question_var.set('\n'.join(lines))

        pending = bool(self._pending_ids)
        self._outcome_box.configure(state='readonly' if pending else 'disabled')
        self._outcome_action_box.configure(
            state='readonly' if pending else 'disabled')
        self._register_outcome_button.configure(
            state='normal' if pending else 'disabled')
        for button in self._quick_buttons:
            button.configure(state='normal' if pending else 'disabled')

    def _present_analysis(self, analysis) -> None:
        self.last_analysis = analysis
        self._update_live_panel(analysis)
        self._set_recommendation(analysis)
        self._update_question_panel(analysis)
        self._set_detail(analysis)
        self._present_status(analysis)

    def _present_status(self, analysis) -> None:
        """Resume el analisis en las etiquetas de estado (sin widgets)."""
        state = analysis.state
        self.decision_status_var.set(
            '%s | HU=%s | calle=%s'
            % (analysis.canonical_status, state.status, state.street))
        if analysis.equity is None:
            self.equity_status_var.set(
                'unknown | %s'
                % (analysis.equity_uncertainty or 'sin equity calculable'))
        else:
            self.equity_status_var.set(
                '%.4f | %s | %s'
                % (analysis.equity, analysis.equity_method,
                   analysis.equity_uncertainty
                   or 'sin incertidumbre declarada'))
        if analysis.selected_action:
            self.action_status_var.set('demostrada: %s'
                                       % analysis.selected_action)
        elif analysis.provisional_selected_action:
            self.action_status_var.set('provisional NO demostrada: %s'
                                       % analysis.provisional_selected_action)
        else:
            self.action_status_var.set('sin recomendacion')

    def _set_detail(self, analysis) -> None:
        text = self.detail_text
        position = text.yview()[0]
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
        snapshot = getattr(analysis, 'recorder_snapshot', None)
        if snapshot is not None:
            view = snapshot.decision_view
            raw = snapshot.raw_state
            text.insert(tk.END, '\nESTADO BRUTO CAPTURADO\n', 'observed')
            text.insert(tk.END, '  btn=%s | estados=%s\n'
                        % (raw.get('btn'), {
                            seat: raw.get('%s_state' % seat)
                            for seat in ('hero', 'p1', 'p2', 'p3', 'p4', 'p5')
                        }))
            text.insert(tk.END, '  pot=%s | stacks=%s | bets=%s\n'
                        % (raw.get('pot'), {
                            seat: raw.get('%s_stake' % seat)
                            for seat in ('hero', 'p1', 'p2', 'p3', 'p4', 'p5')
                        }, {
                            seat: raw.get('%s_bet' % seat)
                            for seat in ('hero', 'p1', 'p2', 'p3', 'p4', 'p5')
                        }))
            text.insert(tk.END, '  hero_cards=%s | community=%s\n'
                        % (raw.get('hero_cards'), raw.get('community')))
            text.insert(tk.END, '\nSNAPSHOT RECORDER (una ejecucion)\n',
                        'observed')
            text.insert(tk.END, '  seq=%s procesado=%s fingerprint=%s...\n'
                        % (snapshot.sequence, snapshot.processed,
                           snapshot.fingerprint[:16]))
            text.insert(tk.END, '  Cartas OCR/recorder: %s / %s\n'
                        % (snapshot.cards_read.get('hero'),
                           snapshot.cards_recorded.get('hero')))
            text.insert(tk.END, '  Pot leido/calculado: %s / %s | to_call: %s (%s)\n'
                        % (snapshot.pot_read, snapshot.pot_live_calculated,
                           snapshot.to_call, snapshot.to_call_source))
            text.insert(tk.END, '  Posiciones recorder/HU: %s / %s\n'
                        % (dict(snapshot.positions), dict(view.hu_positions)))
            text.insert(tk.END, '  Boton OCR/recorder: %s / %s\n'
                        % (snapshot.button_read, snapshot.button_recorded))
            text.insert(tk.END, '  Contribuciones: %s\n'
                        % dict(snapshot.contributions))
            text.insert(tk.END, '  Contradicciones: %s\n'
                        % (list(snapshot.contradictions) or 'ninguna'))
            text.insert(tk.END, '  Ambiguedades: %s\n'
                        % ([item.get('code') for item in snapshot.ambiguities]
                           or 'ninguna'))
        text.insert(tk.END, '\nINFERIDO\n', 'inferred')
        text.insert(tk.END, '  Rango: %s (%s)\n'
                    % (analysis.range_kind, analysis.range_source))
        text.insert(tk.END, '  Cobertura: %s | secuencia: %s\n'
                    % (analysis.coverage_state, analysis.sequence_status))
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
        try:
            text.yview_moveto(position)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
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

    def prepare_readers(self) -> None:
        """Inicializa los lectores originales fuera del hilo de la interfaz."""
        prepare = getattr(self.assistant, 'prepare', None)
        if prepare is None:
            self.capture_status_var.set('este asistente no expone prepare()')
            return
        self.capture_status_var.set(
            'inicializando lectores y motor original (puede tardar varios s)...')

        def worker():
            try:
                setup_ms = prepare()
                prepare_engine = getattr(
                    self.assistant, 'prepare_engine', None)
                if prepare_engine is not None:
                    prepare_engine()
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda e=exc: self.capture_status_var.set(
                    'ERROR preparando lectores/motor: %s' % e))
                return
            self.root.after(0, lambda ms=setup_ms: self.capture_status_var.set(
                'lectores + motor listos; setup=%.1f ms '
                '(no imputado a captura)' % ms))

        threading.Thread(target=worker, daemon=True).start()

    def capture_state(self) -> None:
        try:
            frame = self.assistant.capture()
        except Exception as exc:  # noqa: BLE001
            self.capture_status_var.set('ERROR: %s' % exc)
            self.ocr_status_var.set('captura fallida')
            self.auto_status_var.set('ERROR captura: %s' % exc)
            return
        self.last_frame = frame
        # Un frame nuevo invalida el analisis anterior: registrar una
        # prediccion nunca debe reutilizar el estado de otra captura.
        self.last_analysis = None
        setup = ('; setup %.1f ms' % frame.setup_ms
                 if frame.setup_ms is not None else '')
        self.capture_status_var.set('%s; captura %.1f ms%s' % (
            frame.source, frame.capture_ms or 0.0, setup))
        ocr = ('OCR incluido en captura' if frame.ocr_ms is None
               else 'OCR=%.1f ms' % frame.ocr_ms)
        self.ocr_status_var.set('warnings=%s; %s' % (
            ', '.join(frame.warnings) or 'ninguno', ocr))
        self.auto_status_var.set('captura manual completada')
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
        self._present_analysis(analysis)

    def _quick_outcome(self, action: str) -> None:
        self.outcome_action_var.set(action)
        if self._pending_ids:
            self.question_var.set(
                'Accion marcada: %s. Pulsa Registrar para guardarla.'
                % action)

    def _display_for(self, prediction_id: str) -> str:
        label = (self._pending_labels.get(prediction_id) or '').strip()
        short = prediction_id[:8]
        return ('%s · %s' % (label, short)) if label else short

    def _sync_outcome_choices(self) -> None:
        choices = {}
        values = []
        for prediction_id in self._pending_ids:
            display = self._display_for(prediction_id)
            unique = display
            counter = 2
            while unique in choices and choices[unique] != prediction_id:
                unique = '%s (%d)' % (display, counter)
                counter += 1
            choices[unique] = prediction_id
            values.append(unique)
        self._outcome_choices = choices
        self._outcome_box.configure(values=tuple(values))

    def _add_pending_prediction(self, prediction_id: str,
                                label: Optional[str] = None) -> None:
        if not prediction_id:
            return
        if prediction_id not in self._pending_ids:
            self._pending_ids.append(prediction_id)
        if label:
            self._pending_labels[prediction_id] = str(label)
        self._sync_outcome_choices()
        self.outcome_prediction_var.set(self._display_for(prediction_id))
        self._update_question_panel(self.last_analysis)

    def register_prediction(self) -> None:
        if self.last_frame is None:
            messagebox.showinfo('Sin captura', 'Captura un estado primero.')
            return
        if self.last_analysis is None:
            self.analyze_current()
        if self.last_analysis is None:
            messagebox.showerror(
                'Sin analisis', 'El estado no produjo un analisis registrable.')
            return
        try:
            # Congela exactamente la prediccion mostrada. No se vuelve a
            # analizar: un cambio de estado entre pantalla y registro haria que
            # el evento persistido no coincidiera con lo que vio el operador.
            registration = self.assistant.register_analysis(
                self.last_analysis)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Fallo de persistencia', str(exc))
            self.persist_status_var.set('ERROR: %s' % exc)
            return
        self.last_registration = registration
        self.persist_status_var.set('persistida: %s'
                                    % registration.prediction_id)
        state = registration.analysis.state
        label = '%s · %s · %s' % (
            state.hand_id or '?', state.street or '?',
            registration.analysis.provisional_selected_action or '?')
        self._add_pending_prediction(registration.prediction_id,
                                     label=label)
        self._refresh_registry_status()
        self._set_detail(registration.analysis)

    def register_outcome(self) -> None:
        raw_prediction = self.outcome_prediction_var.get().strip()
        prediction_id = self._outcome_choices.get(raw_prediction,
                                                  raw_prediction)
        if not prediction_id:
            messagebox.showinfo('Falta prediction ID',
                                'Indica la prediccion a la que corresponde.')
            return
        action = self.outcome_action_var.get().strip() or None
        exclusion = self.outcome_exclusion_var.get().strip() or None
        if not action and not exclusion:
            messagebox.showinfo(
                'Falta resultado',
                'Marca la accion observada del rival (o elige unknown), o '
                'indica una exclusion en la pestana Avanzado.')
            return
        try:
            self.assistant.record_outcome(
                prediction_id, observed_action=action,
                exclusion_reason=exclusion)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Fallo de registro', str(exc))
            return
        self.persist_status_var.set('resultado registrado para %s'
                                    % prediction_id)
        self._pending_labels.pop(prediction_id, None)
        self._pending_ids = [item for item in self._pending_ids
                             if item != prediction_id]
        self._sync_outcome_choices()
        self.outcome_prediction_var.set(
            self._display_for(self._pending_ids[-1])
            if self._pending_ids else '')
        self.outcome_action_var.set('')
        self._update_question_panel(self.last_analysis)
        self._refresh_registry_status()
        self._after_outcome_registered()

    def _after_outcome_registered(self) -> None:
        """Gancho para que la GUI automatica reanude tras reconciliar."""

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
