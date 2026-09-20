"""asistente_live_gui.py — interfaz gráfica del asistente en vivo.

Inspirada en recorder/poker_recorder_gui.py pero integra el asistente:
  - Nombres de jugador por asiento (para el registro y la etiqueta del rival).
  - Modo Automático (polling continuo ~0.5 s: registra cada mano en
    data/hands_db.jsonl y recomienda cuando toca a hero).
  - Modo Manual (tú decides cuándo capturar: botón 'Capturar', y guardas la
    mano con 'Guardar mano').
  - Botón 'Siempre al frente' (ventana siempre superpuesta).

El asistente solo recomienda (mejor acción por EV); el humano decide.

Uso:  python -m motor.asistente_live_gui
"""
import os
import sys
import threading
import queue
import json
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'tools'))
sys.path.insert(0, os.path.join(_ROOT, 'recorder'))

from motor.asistente_live import Asistente  # noqa: E402

DEFAULT_HANDS_DB = os.path.join(_ROOT, 'data', 'hands_db.jsonl')


class AsistenteLiveGUI:
    PLAYER_LABELS = [
        ('hero', 'Hero'),
        ('p5', 'P5'),
        ('p4', 'P4'),
        ('p3', 'P3'),
        ('p2', 'P2'),
        ('p1', 'P1'),
    ]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Asistente Poker en Vivo (PEZ/TIBURON)')
        self.root.geometry('880x760')
        self.root.resizable(True, True)

        self.stop_event = threading.Event()
        self.log_queue = queue.Queue()
        self.worker = None
        self.running = False
        self.asis = None            # Asistente (creado en el hilo que lo usa)
        self.reader_ready = False
        self._cards_dirty = False

        self._build_ui()
        self._preload_names()
        self._poll_queue()

    # ---------- UI ----------

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # -- Siempre al frente --
        top = ttk.Frame(main)
        top.pack(fill=tk.X, pady=(0, 5))
        self.topmost_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text='Ventana siempre al frente',
                        variable=self.topmost_var,
                        command=self._toggle_topmost).pack(side=tk.LEFT)
        self.root.attributes('-topmost', True)

        # -- Players (nombres, posición, cartas manuales) --
        pf = ttk.LabelFrame(main, text='Players', padding=10)
        pf.pack(fill=tk.X, pady=(0, 8))

        self.name_vars = {}
        self.card_vars = {}
        self.inactive_vars = {}
        self.pos_vars = {}
        ttk.Label(pf, text='Inact', font=('', 9, 'bold')).grid(
            row=0, column=0, padx=(0, 2))
        ttk.Label(pf, text='Name', font=('', 9, 'bold')).grid(
            row=0, column=1, columnspan=2, padx=(2, 5), sticky=tk.W)
        ttk.Label(pf, text='Pos', font=('', 9, 'bold')).grid(
            row=0, column=3, padx=(5, 5))
        ttk.Label(pf, text='Cards', font=('', 9, 'bold')).grid(
            row=0, column=4, padx=(10, 5))
        for i, (key, label) in enumerate(self.PLAYER_LABELS):
            row = i + 1
            inact_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(pf, variable=inact_var).grid(
                row=row, column=0, padx=(0, 2))
            self.inactive_vars[key] = inact_var
            ttk.Label(pf, text=f'{label}:', width=6, anchor=tk.E).grid(
                row=row, column=1, padx=(2, 2), sticky=tk.E)
            var = tk.StringVar(value='')
            ttk.Entry(pf, textvariable=var, width=16).grid(
                row=row, column=2, pady=2, sticky=tk.W)
            self.name_vars[key] = var
            pos_var = tk.StringVar(value='')
            ttk.Entry(pf, textvariable=pos_var, width=6).grid(
                row=row, column=3, pady=2, padx=(5, 5), sticky=tk.W)
            self.pos_vars[key] = pos_var
            card_var = tk.StringVar(value='')
            ttk.Entry(pf, textvariable=card_var, width=14).grid(
                row=row, column=4, pady=2, padx=(5, 0), sticky=tk.W)
            self.card_vars[key] = card_var
        ttk.Label(pf, text='(Nombres para el registro y etiqueta del rival. '
                           'El perfil PEZ/TIBURON se calcula por STACK: '
                           '<50 BB).', foreground='gray').grid(
            row=len(self.PLAYER_LABELS) + 1, column=0, columnspan=5,
            pady=(4, 0))

        # -- Output --
        of = ttk.Frame(main)
        of.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(of, text='Output:').pack(side=tk.LEFT, padx=(0, 5))
        self.output_var = tk.StringVar(value=DEFAULT_HANDS_DB)
        ttk.Entry(of, textvariable=self.output_var, width=44).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(of, text='Browse', command=self._browse, width=8).pack(
            side=tk.LEFT)

        # -- Modo --
        mf = ttk.Frame(main)
        mf.pack(fill=tk.X, pady=(0, 5))
        self.mode_var = tk.StringVar(value='auto')
        ttk.Radiobutton(mf, text='Automático', variable=self.mode_var,
                        value='auto', command=self._on_mode_change).pack(
            side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(mf, text='Manual', variable=self.mode_var,
                        value='manual', command=self._on_mode_change).pack(
            side=tk.LEFT)

        # -- Winner override (manual) --
        wf = ttk.Frame(main)
        wf.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(wf, text='Winner(s):', width=10).pack(side=tk.LEFT)
        self.winner_var = tk.StringVar(value='')
        ttk.Entry(wf, textvariable=self.winner_var, width=30).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Label(wf, text='pids separados por coma: p2 o p2,p3',
                  foreground='gray').pack(side=tk.LEFT)

        # -- Botones --
        bf = ttk.Frame(main)
        bf.pack(fill=tk.X, pady=(0, 8))
        self.btn_frame = ttk.Frame(bf)
        self.btn_frame.pack(side=tk.LEFT)
        self.start_btn = ttk.Button(self.btn_frame, text='▶  Iniciar',
                                    command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.stop_btn = ttk.Button(self.btn_frame, text='■  Detener',
                                   command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)

        self.manual_frame = ttk.Frame(bf)
        self.init_btn = ttk.Button(self.manual_frame, text='⚙ Inicializar '
                                   'lector + modelos', command=self._manual_init)
        self.init_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.capture_btn = ttk.Button(self.manual_frame, text='Capturar',
                                      command=self._manual_capture, width=14,
                                      state=tk.DISABLED)
        self.capture_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.end_hand_btn = ttk.Button(self.manual_frame,
                                       text='Guardar mano', width=14,
                                       command=self._manual_end_hand,
                                       state=tk.DISABLED)
        self.end_hand_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.cancel_hand_btn = ttk.Button(self.manual_frame,
                                          text='Cancelar mano', width=14,
                                          command=self._manual_cancel_hand,
                                          state=tk.DISABLED)
        self.cancel_hand_btn.pack(side=tk.LEFT)

        self.status_canvas = tk.Canvas(bf, width=16, height=16,
                                       highlightthickness=0)
        self.status_canvas.pack(side=tk.RIGHT, padx=(0, 5))
        self.status_dot = self.status_canvas.create_oval(2, 2, 14, 14,
                                                         fill='gray',
                                                         outline='')
        self.status_label = ttk.Label(bf, text='Listo', foreground='gray')
        self.status_label.pack(side=tk.RIGHT)

        # -- Recomendación (destacada) --
        rf = ttk.LabelFrame(main, text='Recomendación', padding=6)
        rf.pack(fill=tk.X, pady=(0, 8))
        self.reco_label = ttk.Label(rf, text='—', font=('', 12, 'bold'),
                                    foreground='#0a5')
        self.reco_label.pack(anchor=tk.W)
        self.reco_detail = scrolledtext.ScrolledText(rf, height=9,
                                                     font=('Consolas', 9),
                                                     wrap=tk.WORD)
        self.reco_detail.pack(fill=tk.BOTH, expand=True)

        # -- Log --
        lf = ttk.LabelFrame(main, text='Log / estado de la mano')
        lf.pack(fill=tk.BOTH, expand=True)
        self.log = scrolledtext.ScrolledText(lf, height=12,
                                             font=('Consolas', 9))
        self.log.pack(fill=tk.BOTH, expand=True)

    # ---------- helpers UI ----------

    def _toggle_topmost(self):
        self.root.attributes('-topmost', bool(self.topmost_var.get()))

    def _on_mode_change(self):
        if self.mode_var.get() == 'auto':
            self.btn_frame.pack(side=tk.LEFT)
            self.manual_frame.pack_forget()
        else:
            self.btn_frame.pack_forget()
            self.manual_frame.pack(side=tk.LEFT)

    def _browse(self):
        path = filedialog.asksaveasfilename(
            defaultextension='.jsonl',
            filetypes=[('JSONL files', '*.jsonl'), ('All files', '*.*')])
        if path:
            self.output_var.set(path)

    def _log(self, msg):
        self.log_queue.put(('log', str(msg)))

    def _set_status(self, text, color):
        def _apply():
            self.status_label.config(text=text, foreground=color)
            self.status_canvas.itemconfig(self.status_dot, fill=color)
        self.root.after(0, _apply)

    def _preload_names(self):
        out = self.output_var.get().strip()
        candidates = []
        if out:
            candidates.append(out if os.path.isabs(out)
                              else os.path.join(os.getcwd(), out))
        candidates.append(DEFAULT_HANDS_DB)
        path = next((p for p in candidates if os.path.exists(p)), None)
        if path is None:
            self._log('No hay hands_db previo para precargar nombres')
            return
        try:
            lines = [l for l in open(path, encoding='utf-8').read()
                     .splitlines() if l.strip()]
            hand = None
            for line in reversed(lines):
                try:
                    hand = json.loads(line)
                    break
                except ValueError:
                    continue
            if hand is None:
                self._log(f'No se pudo leer la última mano de {path}')
                return
            ids = ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']
            loaded = 0
            for pid, pl in zip(ids, hand.get('players', [])):
                name = (pl.get('name') or '').strip()
                if name and pid in self.name_vars:
                    self.name_vars[pid].set(name)
                    loaded += 1
            if loaded:
                self._log(f'Nombres precargados de la última mano '
                          f'({loaded} jugadores)')
            else:
                self._log(f'La última mano de {path} no tiene nombres')
        except Exception as e:
            self._log(f'No se pudieron precargar nombres: {e}')

    # ---------- sync de nombres/overrides al módulo recorder ----------

    def _sync_to_recorder(self):
        import recorder_live as rl_mod
        rl_mod.PLAYER_NAMES.clear()
        for key, _ in self.PLAYER_LABELS:
            v = self.name_vars[key].get().strip()
            rl_mod.PLAYER_NAMES[key] = v if v else key.upper()
        rl_mod.OUTPUT_PATH = self.output_var.get().strip() or DEFAULT_HANDS_DB
        rl_mod.MANUAL_INACTIVE.clear()
        for key, _ in self.PLAYER_LABELS:
            if self.inactive_vars[key].get():
                rl_mod.MANUAL_INACTIVE.add(key)
        rl_mod.MANUAL_POSITIONS.clear()
        for key, _ in self.PLAYER_LABELS:
            pv = self.pos_vars[key].get().strip().upper()
            if pv:
                rl_mod.MANUAL_POSITIONS[key] = pv
        rl_mod.MANUAL_CARDS.clear()
        for key, _ in self.PLAYER_LABELS:
            cv = self.card_vars[key].get().strip()
            if cv:
                rl_mod.MANUAL_CARDS[key] = cv
        w = self.winner_var.get().strip()
        rl_mod.MANUAL_WINNER = ([x.strip() for x in w.split(',')
                                 if x.strip()] if w else None)

    # ---------- modo automático ----------

    def _start(self):
        self._sync_to_recorder()
        self.stop_event.clear()
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._set_status('Grabando...', 'green')
        self.log.delete('1.0', tk.END)

        self.worker = threading.Thread(target=self._run_auto, daemon=True)
        self.worker.start()

    def _stop(self):
        self.stop_event.set()
        self._set_status('Deteniendo...', 'orange')
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.running = False

    def _run_auto(self):
        def log_func(msg):
            self._log(str(msg))

        self.root.after(0, lambda: self._set_status('Lector...', 'orange'))
        log_func('Inicializando lector...')
        import capture_live
        capture_live.init_reader()
        self._log('')
        log_func('Construyendo modelos PEZ/TIBURON...')
        from motor.asistente_live import build_models
        models = build_models(verbose=True)
        hero_name = self.name_vars['hero'].get().strip() or 'Jarduan'
        self.asis = Asistente(models=models, hero_name=hero_name,
                              verbose=False)
        log_func('Asistente listo. Esperando turno del hero...')
        self.root.after(0, lambda: self._set_status('Esperando turno...',
                                                    'green'))

        def on_reco(text, evs, sit, label):
            best = evs.best()
            if getattr(evs, 'preflop', False):
                choice = getattr(evs, 'chosen', best[0])
                summary = (f'MEJOR: {choice} · '
                           f'{evs.ev.get(choice, best[1]):.0%} '
                           f'(matriz preflop)  ·  vs {label}')
            else:
                choice = getattr(evs, 'chosen', best[0])
                spot = getattr(evs, 'spot', 'postflop')
                summary = (f'MEJOR: {choice} {evs.ev.get(choice, best[1]):+.2f} BB'
                           f'  ·  {spot}  ·  vs {label}')
            self.log_queue.put(('reco', summary, text))
            self.log_queue.put(('log', ''))

        while not self.stop_event.is_set():
            self._sync_to_recorder()
            try:
                prev_hand = self.asis.rec.hand
                state, img_arr, pil = capture_live.capture()
                self.asis.step(state, img_arr, pil, log=log_func,
                               on_reco=on_reco)
                if prev_hand is not None and self.asis.rec.hand is None:
                    self.log_queue.put(('reco', 'Mano terminada', ''))
            except Exception as e:
                log_func(f'[error] {e}')
            import time
            time.sleep(self.asis.poll)

        if self.asis.rec.hand is not None:
            try:
                self.asis.rec.finalize_hand(self.asis.last_state)
                log_func('Mano en curso guardada.')
            except Exception:
                pass
        self.log_queue.put(('reco', 'Mano terminada', ''))
        self.root.after(0, self._on_stopped)

    def _on_stopped(self):
        self._set_status('Detenido', 'gray')
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.running = False
        self._log('')
        self._log('Asistente detenido. Manos guardadas en: '
                  + self.output_var.get())

    # ---------- modo manual ----------

    def _manual_init(self):
        def task():
            self._log('Inicializando lector...')
            self.root.after(0, lambda: self._set_status('Lector...',
                                                        'orange'))
            import capture_live
            capture_live.init_reader()
            self._log('Construyendo modelos PEZ/TIBURON...')
            from motor.asistente_live import build_models
            models = build_models(verbose=False)
            hero_name = self.name_vars['hero'].get().strip() or 'Jarduan'
            self.asis = Asistente(models=models, hero_name=hero_name,
                                  verbose=False)
            self.reader_ready = True
            self._log('Lector + modelos listos.')
            self.root.after(0, lambda: self._set_status('Listo', 'green'))
            self.root.after(0, lambda: self.init_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.capture_btn.config(state=tk.NORMAL))
            self._log('Pulsa "Capturar" cuando quieras una captura.')
        threading.Thread(target=task, daemon=True).start()

    def _manual_capture(self):
        if self.asis is None:
            self._log('ERROR: pulsa "Inicializar lector + modelos" primero')
            return
        self._sync_to_recorder()
        self._log('')
        self._log('--- Capturando ---')
        from capture_live import capture
        state, img_arr, pil = capture()
        pot = state.get('pot') or state.get('pot_wide')
        self._log(f'  pot={pot}  btn={state.get("btn")}  '
                  f'coms={self.asis.rec._visible_coms(state)}')
        for p in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
            sk = state.get(f'{p}_stake')
            bt = state.get(f'{p}_bet')
            st = state.get(f'{p}_state')
            sk_s = f'{sk:.1f}' if sk is not None else '-'
            bt_s = f'{bt:.1f}' if bt is not None else '-'
            self._log(f'  {p:>6} stake={sk_s:>6} bet={bt_s:>6} state={st or "-"}')

        def on_reco(text, evs, sit, label):
            best = evs.best()
            if getattr(evs, 'preflop', False):
                choice = getattr(evs, 'chosen', best[0])
                summary = (f'MEJOR: {choice} · '
                           f'{evs.ev.get(choice, best[1]):.0%} '
                           f'(matriz preflop)  ·  vs {label}')
            else:
                choice = getattr(evs, 'chosen', best[0])
                spot = getattr(evs, 'spot', 'postflop')
                summary = (f'MEJOR: {choice} {evs.ev.get(choice, best[1]):+.2f} BB'
                           f'  ·  {spot}  ·  vs {label}')
            self.log_queue.put(('reco', summary, text))

        before_id = self.asis.rec.hand_id if self.asis.rec.hand else None
        res = self.asis.step(state, img_arr, pil, log=self._log,
                             on_reco=on_reco, require_turn=False,
                             force_reco=True)
        if res is None:
            self._log('  (sin recomendación: faltan cartas del hero o rival '
                      'activo)')
        rec = self.asis.rec
        if rec.hand:
            if before_id != rec.hand_id:
                # Mano auto-finalizada → nueva mano: limpiar campos viejos
                # antes de rellenar con los detectados de la nueva mano.
                self._clear_card_fields()
                self.winner_var.set('')
            for p in rec.hand['players']:
                pid = p.get('_id', '')
                if (pid in self.card_vars and p.get('cards')
                        and not self.card_vars[pid].get().strip()):
                    self.card_vars[pid].set(p['cards'])
            hand_positions = rec._hand_positions or {}
            for pid in self.pos_vars:
                pos = hand_positions.get(pid, '')
                if pos:
                    self.pos_vars[pid].set(pos)
            non_folded = [p for p in rec.hand['players']
                          if p['active'] and
                          state.get(f'{p["_id"]}_stake') is not None and
                          state.get(f'{p["_id"]}_state')
                          not in ('retirarse', 'ausente', 'inactivo')]
            if non_folded:
                self.winner_var.set(','.join(p['_id']
                                             for p in non_folded))
            self.end_hand_btn.config(state=tk.NORMAL)
            self.cancel_hand_btn.config(state=tk.NORMAL)
            self._log('')
            self._log('=== MANO NUEVA ===' if before_id != rec.hand_id
                      else '=== MANO ACTUALIZADA ===')
            self._show_hand()
        elif before_id is not None:
            # La mano auto-finalizó (por fold, new hand, o fin de juego).
            for pid in self.pos_vars:
                self.pos_vars[pid].set('')
            self._clear_card_fields()
            self.winner_var.set('')
            self._clear_reco()
            self.end_hand_btn.config(state=tk.DISABLED)
            self.cancel_hand_btn.config(state=tk.DISABLED)
            self._log('')
            self._log('=== MANO TERMINADA ===')

    def _show_hand(self):
        h = self.asis.rec.hand
        if h is None:
            self._log('  (no hand)')
            return
        self._log(f'  {h["hand_id"]}')
        for p in h['players']:
            self._log(f'  {p["name"]:>12} pos={p["pos"]:>3} '
                      f'stack={p["stack"]} cards={p["cards"]}')
        for sname in ['preflop', 'flop', 'turn', 'river']:
            s = h['streets'].get(sname)
            if s and s['actions']:
                board = ' '.join(s['board']) if s['board'] else ''
                self._log(f'  {sname:>8} [{board}]')
                for a in s['actions']:
                    amt_s = (f'{a["amount"]:.1f}'
                             if isinstance(a['amount'], float)
                             else str(a['amount']))
                    self._log(f'           {a["pos"]:>3} {a["action"]} '
                              f'{amt_s}')
        com = h.get('comunitarias', {})
        for st in ['flop', 'turn', 'river']:
            if com.get(st):
                self._log(f'  {st:>8} cartas: {" ".join(com[st])}')
        fp = h.get('final_pot')
        sw = h.get('showdown', {})
        if fp is not None:
            self._log(f'  final_pot={fp}')
        if sw:
            self._log(f'  showdown={sw}')

    def _manual_end_hand(self):
        rec = self.asis.rec if self.asis else None
        if rec is None or rec.hand is None:
            self._log('No hay mano activa para guardar.')
            return
        import recorder_live as rl_mod
        for p in rec.hand['players']:
            pid = p.get('_id', '')
            if pid in self.card_vars:
                val = self.card_vars[pid].get().strip()
                if val:
                    p['cards'] = val
        w = self.winner_var.get().strip()
        if w:
            rl_mod.MANUAL_WINNER = [x.strip() for x in w.split(',')
                                    if x.strip()]
            self._log(f'  winner override: {rl_mod.MANUAL_WINNER}')
        else:
            rl_mod.MANUAL_WINNER = None
        self._log('')
        self._log('--- Guardando mano ---')
        rec.finalize_hand(rec.last_state)
        self._log('Mano guardada.')
        self.end_hand_btn.config(state=tk.DISABLED)
        self.cancel_hand_btn.config(state=tk.DISABLED)
        self.winner_var.set('')
        for key in self.pos_vars:
            self.pos_vars[key].set('')
        self._clear_card_fields()
        self._clear_reco()
        self._create_recorder()

    def _create_recorder(self):
        import recorder_live as rl_mod
        self._sync_to_recorder()
        if self.asis is not None:
            self.asis.rec = rl_mod.LiveRecorder()
        self.end_hand_btn.config(state=tk.DISABLED)
        self.cancel_hand_btn.config(state=tk.DISABLED)

    def _manual_cancel_hand(self):
        rec = self.asis.rec if self.asis else None
        if rec is None or rec.hand is None:
            return
        hid = rec.hand.get('hand_id', '???')
        self._log('')
        self._log(f'--- Cancelando {hid} ---')
        rec.hand = None
        rec.street_has_bet = False
        rec.hand_id -= 1
        self.end_hand_btn.config(state=tk.DISABLED)
        self.cancel_hand_btn.config(state=tk.DISABLED)
        self.winner_var.set('')
        for key in self.pos_vars:
            self.pos_vars[key].set('')
        self._clear_card_fields()
        self._clear_reco()
        self._log('Mano descartada. Listo para la siguiente.')
        self._create_recorder()

    # ---------- cola de eventos / UI ----------

    def _mark_cards_dirty(self):
        self._cards_dirty = True

    def _clear_card_fields(self):
        for key in self.card_vars:
            self.card_vars[key].set('')

    def _clear_reco(self):
        """Borra el panel de recomendación (mano terminada o cancelada)."""
        self.reco_label.config(text='')
        self.reco_detail.delete('1.0', tk.END)

    def _poll_queue(self):
        if self._cards_dirty:
            self._cards_dirty = False
            self._clear_card_fields()
        try:
            while True:
                msg = self.log_queue.get_nowait()
                kind = msg[0]
                if kind == 'reco':
                    summary, detail = msg[1], msg[2]
                    self.reco_label.config(text=summary)
                    self.reco_detail.delete('1.0', tk.END)
                    self.reco_detail.insert(tk.END, detail)
                else:
                    self.log.insert(tk.END, msg[1] + '\n')
                    self.log.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def run(self):
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self.root.mainloop()

    def _on_close(self):
        if self.running:
            self.stop_event.set()
        self.root.destroy()


if __name__ == '__main__':
    app = AsistenteLiveGUI()
    app.run()