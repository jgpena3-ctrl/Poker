import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading, queue, os, json
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
sys.path.insert(0, os.path.dirname(__file__))


class RecorderGUI:
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
        self.root.title('Poker Hand Recorder')
        self.root.geometry('740x640')
        self.root.resizable(True, True)

        self.stop_event = threading.Event()
        self.log_queue = queue.Queue()
        self.worker = None
        self.running = False
        self.manual_recorder = None
        self.reader_ready = False
        self._cards_dirty = False

        self._build_ui()
        self._preload_names()
        self._poll_queue()

    # ---------- UI ----------

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # -- Player names + cards --
        pf = ttk.LabelFrame(main, text='Players', padding=10)
        pf.pack(fill=tk.X, pady=(0, 10))

        self.name_vars = {}
        self.card_vars = {}
        self.inactive_vars = {}
        self.pos_vars = {}
        ttk.Label(pf, text='Inact', font=('', 9, 'bold')).grid(row=0, column=0, padx=(0, 2))
        ttk.Label(pf, text='Name', font=('', 9, 'bold')).grid(row=0, column=1, columnspan=2, padx=(2, 5), sticky=tk.W)
        ttk.Label(pf, text='Pos', font=('', 9, 'bold')).grid(row=0, column=3, padx=(5, 5))
        ttk.Label(pf, text='Cards', font=('', 9, 'bold')).grid(row=0, column=4, padx=(10, 5))
        for i, (key, label) in enumerate(self.PLAYER_LABELS):
            row = i + 1
            # Inactive checkbox
            inact_var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(pf, variable=inact_var)
            cb.grid(row=row, column=0, padx=(0, 2))
            self.inactive_vars[key] = inact_var
            # Name label
            ttk.Label(pf, text=f'{label}:', width=6, anchor=tk.E).grid(row=row, column=1, padx=(2, 2), sticky=tk.E)
            var = tk.StringVar(value='')
            entry = ttk.Entry(pf, textvariable=var, width=16)
            entry.grid(row=row, column=2, pady=2, sticky=tk.W)
            self.name_vars[key] = var

            # Position entry (auto-filled, editable)
            pos_var = tk.StringVar(value='')
            pos_entry = ttk.Entry(pf, textvariable=pos_var, width=6)
            pos_entry.grid(row=row, column=3, pady=2, padx=(5, 5), sticky=tk.W)
            self.pos_vars[key] = pos_var

            card_var = tk.StringVar(value='')
            card_entry = ttk.Entry(pf, textvariable=card_var, width=14)
            card_entry.grid(row=row, column=4, pady=2, padx=(5, 0), sticky=tk.W)
            self.card_vars[key] = card_var

        pos_hint = ttk.Label(pf, text='(Positions auto-filled from button, editable)  |  Cards: e.g. AhKd or leave empty', foreground='gray')
        pos_hint.grid(row=len(self.PLAYER_LABELS) + 1, column=0, columnspan=5, pady=(5, 0))

        # -- Output file --
        of = ttk.Frame(main)
        of.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(of, text='Output:').pack(side=tk.LEFT, padx=(0, 5))
        self.output_var = tk.StringVar(value='hands_db.jsonl')
        ttk.Entry(of, textvariable=self.output_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(of, text='Browse', command=self._browse, width=8).pack(side=tk.LEFT)

        # -- Mode selector --
        mf = ttk.Frame(main)
        mf.pack(fill=tk.X, pady=(0, 5))

        self.mode_var = tk.StringVar(value='auto')
        ttk.Radiobutton(mf, text='▶ Play (auto)', variable=self.mode_var, value='auto', command=self._on_mode_change).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(mf, text='✋ Manual', variable=self.mode_var, value='manual', command=self._on_mode_change).pack(side=tk.LEFT)

        # -- Winner override --
        wf = ttk.Frame(main)
        wf.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(wf, text='Winner(s):', width=10).pack(side=tk.LEFT)
        self.winner_var = tk.StringVar(value='')
        ttk.Entry(wf, textvariable=self.winner_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Label(wf, text='comma-separated pids, e.g. p2 or p2,p3', foreground='gray').pack(side=tk.LEFT)

        # -- Buttons --
        bf = ttk.Frame(main)
        bf.pack(fill=tk.X, pady=(0, 10))

        # Auto mode buttons
        self.btn_frame = ttk.Frame(bf)
        self.btn_frame.pack(side=tk.LEFT)

        self.start_btn = ttk.Button(self.btn_frame, text='▶  Start', command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.stop_btn = ttk.Button(self.btn_frame, text='■  Stop', command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)

        # Manual mode buttons (hidden initially)
        self.manual_frame = ttk.Frame(bf)
        self.init_btn = ttk.Button(self.manual_frame, text='⚙ Init Reader', command=self._manual_init, width=14)
        self.init_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.capture_btn = ttk.Button(self.manual_frame, text='📷 Capture', command=self._manual_capture, width=14, state=tk.DISABLED)
        self.capture_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.end_hand_btn = ttk.Button(self.manual_frame, text='💾 Save & New Hand', command=self._manual_end_hand, width=20, state=tk.DISABLED)
        self.end_hand_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.cancel_hand_btn = ttk.Button(self.manual_frame, text='✕ Cancel Hand', command=self._manual_cancel_hand, width=16, state=tk.DISABLED)
        self.cancel_hand_btn.pack(side=tk.LEFT)

        self.status_canvas = tk.Canvas(bf, width=16, height=16, highlightthickness=0)
        self.status_canvas.pack(side=tk.RIGHT, padx=(0, 5))
        self.status_dot = self.status_canvas.create_oval(2, 2, 14, 14, fill='gray', outline='')
        self.status_label = ttk.Label(bf, text='Ready', foreground='gray')
        self.status_label.pack(side=tk.RIGHT)

        # -- Log --
        lf = ttk.LabelFrame(main, text='Log')
        lf.pack(fill=tk.BOTH, expand=True)

        self.log = scrolledtext.ScrolledText(lf, height=18, font=('Consolas', 9), wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)

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
            filetypes=[('JSONL files', '*.jsonl'), ('All files', '*.*')]
        )
        if path:
            self.output_var.set(path)

    # ---------- log / status ----------

    def _log(self, msg):
        self.log_queue.put(str(msg))

    def _set_status(self, text, color):
        self.status_label.config(text=text, foreground=color)
        self.status_canvas.itemconfig(self.status_dot, fill=color)

    # ---------- precarga de nombres ----------

    def _preload_names(self):
        """Precarga los nombres de los jugadores de la última mano guardada."""
        out = self.output_var.get().strip()
        candidates = []
        if out:
            candidates.append(out if os.path.isabs(out) else os.path.join(os.getcwd(), out))
        candidates.append(os.path.join(os.path.dirname(__file__), '..', 'data', 'hands_db.jsonl'))
        path = next((p for p in candidates if os.path.exists(p)), None)
        if path is None:
            self._log('No hay hands_db previo para precargar nombres')
            return
        try:
            with open(path, encoding='utf-8') as f:
                lines = [l for l in f.read().splitlines() if l.strip()]
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
                self._log(f'Nombres precargados de la última mano ({loaded} jugadores)')
            else:
                self._log(f'La última mano de {path} no tiene nombres')
        except Exception as e:
            self._log(f'No se pudieron precargar nombres: {e}')

    # ---------- auto mode ----------

    def _start(self):
        names = {}
        for key, _ in self.PLAYER_LABELS:
            v = self.name_vars[key].get().strip()
            names[key] = v if v else key.upper()

        output_path = self.output_var.get().strip()
        if not output_path:
            self._log('ERROR: Output path is empty')
            return

        import recorder_live as rl_mod
        rl_mod.PLAYER_NAMES.clear()
        rl_mod.PLAYER_NAMES.update(names)
        rl_mod.OUTPUT_PATH = output_path
        rl_mod.MANUAL_CARDS.clear()
        for key, _ in self.PLAYER_LABELS:
            cv = self.card_vars[key].get().strip()
            if cv:
                rl_mod.MANUAL_CARDS[key] = cv
        # Manual inactive flags
        rl_mod.MANUAL_INACTIVE.clear()
        for key, _ in self.PLAYER_LABELS:
            if self.inactive_vars[key].get():
                rl_mod.MANUAL_INACTIVE.add(key)
        # Manual positions
        rl_mod.MANUAL_POSITIONS.clear()
        for key, _ in self.PLAYER_LABELS:
            pv = self.pos_vars[key].get().strip().upper()
            if pv:
                rl_mod.MANUAL_POSITIONS[key] = pv
        w = self.winner_var.get().strip()
        rl_mod.MANUAL_WINNER = [x.strip() for x in w.split(',') if x.strip()] if w else None

        self.stop_event.clear()
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._set_status('Recording...', 'green')
        self.log.delete('1.0', tk.END)
        self._log('Recorder started (Ctrl+C in terminal also works)')
        for key, name in names.items():
            self._log(f'  {key}: {name}')
        self._log(f'  Output: {output_path}')
        if rl_mod.MANUAL_WINNER:
            self._log(f'  winner override: {rl_mod.MANUAL_WINNER}')
        self._log('')

        self.worker = threading.Thread(
            target=self._run_recorder,
            args=(names, output_path),
            daemon=True
        )
        self.worker.start()

    def _stop(self):
        self.stop_event.set()
        self._set_status('Stopping...', 'orange')
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.running = False

    def _run_recorder(self, names, output_path):
        import recorder_live as rl_mod
        rl_mod.PLAYER_NAMES.clear()
        rl_mod.PLAYER_NAMES.update(names)
        rl_mod.OUTPUT_PATH = output_path

        def log_func(msg):
            self._log(str(msg))

        self.root.after(0, lambda: self._set_status('Training reader...', 'orange'))
        log_func('Training reader...')
        from capture_live import init_reader
        init_reader()
        log_func('Readers ready.')
        self.root.after(0, lambda: self._set_status('Waiting for hand...', 'green'))

        lr = rl_mod.LiveRecorder()
        lr.on_hand_saved = self._mark_cards_dirty
        lr.run(stop_event=self.stop_event, log_func=log_func)
        self.root.after(0, self._on_stopped)

    def _on_stopped(self):
        self._set_status('Stopped', 'gray')
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.running = False
        self._log('')
        self._log('Recorder stopped. Output saved to: ' + self.output_var.get())

    # ---------- manual mode ----------

    def _manual_init(self):
        def task():
            self._log('Training reader...')
            self.root.after(0, lambda: self._set_status('Training...', 'orange'))
            from capture_live import init_reader
            init_reader()
            self.reader_ready = True
            self.root.after(0, lambda: self._set_status('Reader ready', 'green'))
            self.root.after(0, lambda: self.init_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.capture_btn.config(state=tk.NORMAL))
            self._log('Readers ready.')
            self._log('Click "Capture" to capture one frame at a time.')
            # Crear recorder en el hilo principal
            self.root.after(0, self._create_recorder)
        threading.Thread(target=task, daemon=True).start()

    def _create_recorder(self):
        import recorder_live as rl_mod
        names = {}
        for key, _ in self.PLAYER_LABELS:
            v = self.name_vars[key].get().strip()
            names[key] = v if v else key.upper()
        rl_mod.PLAYER_NAMES.clear()
        rl_mod.PLAYER_NAMES.update(names)
        rl_mod.OUTPUT_PATH = self.output_var.get().strip() or 'hands_db.jsonl'
        rl_mod.MANUAL_CARDS.clear()  # start fresh — auto-detect only
        # Manual inactive flags
        rl_mod.MANUAL_INACTIVE.clear()
        for key, _ in self.PLAYER_LABELS:
            if self.inactive_vars[key].get():
                rl_mod.MANUAL_INACTIVE.add(key)
        # Manual positions
        rl_mod.MANUAL_POSITIONS.clear()
        for key, _ in self.PLAYER_LABELS:
            pv = self.pos_vars[key].get().strip().upper()
            if pv:
                rl_mod.MANUAL_POSITIONS[key] = pv
        rl_mod.MANUAL_WINNER = None
        self.manual_recorder = rl_mod.LiveRecorder()
        self.manual_recorder.on_hand_saved = self._mark_cards_dirty
        self.end_hand_btn.config(state=tk.DISABLED)
        self.cancel_hand_btn.config(state=tk.DISABLED)
        self._log('Recorder ready. Capture when a hand is visible.')

    def _show_hand(self, label=''):
        h = self.manual_recorder.hand
        if h is None:
            self._log(f'{label}: (no hand)')
            return
        self._log(f'{label}: {h["hand_id"]}')
        for p in h['players']:
            self._log(f'  {p["name"]:>12} pos={p["pos"]:>3} stack={p["stack"]} cards={p["cards"]}')
        for sname in ['preflop', 'flop', 'turn', 'river']:
            s = h['streets'].get(sname)
            if s and s['actions']:
                board = ' '.join(s['board']) if s['board'] else ''
                self._log(f'  {sname:>8} [{board}]')
                for a in s['actions']:
                    amt_s = f'{a["amount"]:.1f}' if isinstance(a['amount'], float) else str(a['amount'])
                    self._log(f'           {a["pos"]:>3} {a["action"]} {amt_s}')
        com = h.get('comunitarias', {})
        for st in ['flop', 'turn', 'river']:
            if com.get(st):
                self._log(f'  {st:>8} cards: {" ".join(com[st])}')
        fp = h.get('final_pot')
        sw = h.get('showdown', {})
        if fp is not None:
            self._log(f'  final_pot={fp}')
        if sw:
            self._log(f'  showdown={sw}')

    def _manual_capture(self):
        if self.manual_recorder is None:
            self._log('ERROR: Click "Init Reader" first')
            return
        self._log('')
        self._log('--- Capturing ---')
        # Sync GUI vars to module vars for real-time inactive/position/name overrides
        import recorder_live as rl_mod
        rl_mod.MANUAL_INACTIVE.clear()
        for key, _ in self.PLAYER_LABELS:
            if self.inactive_vars[key].get():
                rl_mod.MANUAL_INACTIVE.add(key)
        rl_mod.MANUAL_POSITIONS.clear()
        for key, _ in self.PLAYER_LABELS:
            pv = self.pos_vars[key].get().strip().upper()
            if pv:
                rl_mod.MANUAL_POSITIONS[key] = pv
        # Sync names for new hands
        for key, _ in self.PLAYER_LABELS:
            nv = self.name_vars[key].get().strip()
            if nv:
                rl_mod.PLAYER_NAMES[key] = nv
        # Sync cards → hace que _start_hand guarde las cartas manuales
        rl_mod.MANUAL_CARDS.clear()
        for key, _ in self.PLAYER_LABELS:
            cv = self.card_vars[key].get().strip()
            if cv:
                rl_mod.MANUAL_CARDS[key] = cv
        from capture_live import capture
        state, img_arr, pil = capture()
        pot = state.get('pot') or state.get('pot_wide')
        self._log(f'  pot={pot}  btn={state.get("btn")}  coms={self.manual_recorder._visible_coms(state)}')
        for p in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
            sk = state.get(f'{p}_stake')
            bt = state.get(f'{p}_bet')
            st = state.get(f'{p}_state')
            sk_s = f'{sk:.1f}' if sk is not None else '-'
            bt_s = f'{bt:.1f}' if bt is not None else '-'
            st_s = st or '-'
            self._log(f'  {p:>6} stake={sk_s:>6} bet={bt_s:>6} state={st_s}')
        before_id = self.manual_recorder.hand_id if self.manual_recorder.hand else None
        self.manual_recorder.process_frame(state, img_arr, log=self._log)
        if self.manual_recorder.hand:
            # Auto-fill card fields from detected cards (sin pisar las manuales)
            for p in self.manual_recorder.hand['players']:
                pid = p.get('_id', '')
                if (pid in self.card_vars and p.get('cards')
                        and not self.card_vars[pid].get().strip()):
                    self.card_vars[pid].set(p['cards'])
            new_id = self.manual_recorder.hand_id
            # Fill position fields from hand positions (overwrites with final value used)
            hand_positions = self.manual_recorder._hand_positions or {}
            for pid in self.pos_vars:
                pos = hand_positions.get(pid, '')
                if pos:
                    self.pos_vars[pid].set(pos)
            # Auto-fill winner field (non-folded players)
            non_folded = [p for p in self.manual_recorder.hand['players']
                          if p['active'] and
                          state.get(f'{p["_id"]}_stake') is not None and
                          state.get(f'{p["_id"]}_state') not in (None, 'retirarse', 'ausente', 'inactivo')]
            if non_folded:
                self.winner_var.set(','.join(p['_id'] for p in non_folded))
            self.end_hand_btn.config(state=tk.NORMAL)
            self.cancel_hand_btn.config(state=tk.NORMAL)
            if before_id != new_id:
                self._log('')
                self._log('=== HAND STATE (new) ===')
            else:
                self._log('')
                self._log('=== HAND STATE (updated) ===')
            self._show_hand('')
        elif before_id is not None:
            # Hand ended but no new hand started yet — clear positions
            for pid in self.pos_vars:
                self.pos_vars[pid].set('')
            # Log hand ended
            self._log('')
            self._log('=== HAND ENDED ===')

    def _manual_end_hand(self):
        if self.manual_recorder is None or self.manual_recorder.hand is None:
            self._log('No active hand to save.')
            return
        import recorder_live as rl_mod
        # Inject manually entered cards
        for p in self.manual_recorder.hand['players']:
            pid = p.get('_id', '')
            if pid in self.card_vars:
                val = self.card_vars[pid].get().strip()
                if val:
                    p['cards'] = val
        # Inject winner override
        w = self.winner_var.get().strip()
        if w:
            rl_mod.MANUAL_WINNER = [x.strip() for x in w.split(',') if x.strip()]
            self._log(f'  winner override: {rl_mod.MANUAL_WINNER}')
        else:
            rl_mod.MANUAL_WINNER = None
        self._log('')
        self._log('--- Saving hand ---')
        self.manual_recorder.finalize_hand(self.manual_recorder.last_state)
        self._log('Hand saved.')
        self.end_hand_btn.config(state=tk.DISABLED)
        self.cancel_hand_btn.config(state=tk.DISABLED)
        self.winner_var.set('')
        # Clear position fields for new hand
        for key in self.pos_vars:
            self.pos_vars[key].set('')
        self._create_recorder()

    def _manual_cancel_hand(self):
        if self.manual_recorder is None or self.manual_recorder.hand is None:
            return
        hid = self.manual_recorder.hand.get('hand_id', '???')
        self._log('')
        self._log(f'--- Cancelling {hid} ---')
        self.manual_recorder.hand = None
        self.manual_recorder.street_has_bet = False
        self.manual_recorder.hand_id -= 1  # next hand reuses same ID
        self.end_hand_btn.config(state=tk.DISABLED)
        self.cancel_hand_btn.config(state=tk.DISABLED)
        self.winner_var.set('')
        for key in self.pos_vars:
            self.pos_vars[key].set('')
        self._clear_card_fields()
        self._log('Hand discarded. Ready for next.')
        self._create_recorder()

    # ---------- queue polling ----------

    def _mark_cards_dirty(self):
        self._cards_dirty = True

    def _clear_card_fields(self):
        for key in self.card_vars:
            self.card_vars[key].set('')

    def _poll_queue(self):
        if self._cards_dirty:
            self._cards_dirty = False
            self._clear_card_fields()
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log.insert(tk.END, msg + '\n')
                self.log.see(tk.END)
        except queue.Empty:
            pass
        # Mantener las cartas del GUI sincronizadas mientras se graba,
        # para que _start_hand guarde las cartas manuales también en auto.
        try:
            import recorder_live as rl_mod
            if self.running or self.manual_recorder is not None:
                rl_mod.MANUAL_CARDS.clear()
                for key, _ in self.PLAYER_LABELS:
                    cv = self.card_vars[key].get().strip()
                    if cv:
                        rl_mod.MANUAL_CARDS[key] = cv
        except Exception:
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
    app = RecorderGUI()
    app.run()
