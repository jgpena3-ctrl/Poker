import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json, os

DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'hands_db.jsonl')

class HandEditor:
    def __init__(self, root):
        self.root = root
        self.root.title('Poker Hand DB Editor')
        self.root.geometry('1100x700')
        self.root.minsize(750, 450)
        self.hands = []
        self.hand_idx = {}
        self.cur = -1
        self.search_res = []
        self._nav_text = tk.StringVar(value='0 / 0')
        self._load()
        self._ui()
        if self.hands:
            self._go(0)

    def _load(self):
        self.hands = []
        if os.path.exists(DATA_PATH):
            with open(DATA_PATH, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try: self.hands.append(json.loads(line))
                        except: pass
        self.hands.sort(key=lambda h: h.get('hand_id',''))
        self.hand_idx = {h['hand_id']: i for i, h in enumerate(self.hands)}

    def _ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.nb = ttk.Notebook(main)
        self.nb.pack(fill=tk.BOTH, expand=True)
        # Search tab
        self.search_tab = ttk.Frame(self.nb)
        self.nb.add(self.search_tab, text='Buscar/Navegar')
        self._search_ui(self.search_tab)
        # Edit tab
        self.edit_tab = ttk.Frame(self.nb)
        self.nb.add(self.edit_tab, text='Editar')
        self._edit_ui(self.edit_tab)

    # ===== SEARCH TAB =====
    def _search_ui(self, p):
        sb = ttk.Frame(p)
        sb.pack(fill=tk.X, pady=(0,3))
        ttk.Label(sb, text='Buscar:', font=('',8,'bold')).pack(side=tk.LEFT, padx=(0,2))
        self.svar = tk.StringVar(value='id')
        for t, m in [('ID','id'),('Board','board'),('Hand+Board','hb'),('Jugador','filter')]:
            ttk.Radiobutton(sb, text=t, variable=self.svar, value=m).pack(side=tk.LEFT, padx=(0,3))
        self.sentry = ttk.Entry(sb, width=20)
        self.sentry.pack(side=tk.LEFT, padx=(0,3))
        self.sentry.bind('<Return>', lambda e: self._dosearch())
        ttk.Button(sb, text='Buscar', command=self._dosearch).pack(side=tk.LEFT, padx=(0,2))
        ttk.Button(sb, text='Todos', command=self._showall).pack(side=tk.LEFT, padx=(0,3))
        ttk.Button(sb, text='ID manual', command=self._jumpid).pack(side=tk.LEFT, padx=(0,3))
        nav = ttk.Frame(sb)
        nav.pack(side=tk.RIGHT)
        ttk.Button(nav, text='◀◀', width=3, command=lambda: self._nav(-10)).pack(side=tk.LEFT)
        ttk.Button(nav, text='◀', width=3, command=lambda: self._nav(-1)).pack(side=tk.LEFT, padx=(0,1))
        ttk.Label(nav, textvariable=self._nav_text, width=9).pack(side=tk.LEFT, padx=3)
        ttk.Button(nav, text='▶', width=3, command=lambda: self._nav(1)).pack(side=tk.LEFT, padx=(1,0))
        ttk.Button(nav, text='▶▶', width=3, command=lambda: self._nav(10)).pack(side=tk.LEFT)

        lf = ttk.LabelFrame(p, text='Manos', padding=2)
        lf.pack(fill=tk.BOTH, expand=True)
        self.lb = tk.Listbox(lf, font=('Consolas',9), height=18)
        self.lb.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.lb.bind('<<ListboxSelect>>', lambda e: self._onlist())
        sbar = ttk.Scrollbar(lf, command=self.lb.yview)
        sbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.lb.config(yscrollcommand=sbar.set)

        ib = ttk.LabelFrame(p, text='Info', padding=1)
        ib.pack(fill=tk.X, pady=(3,0))
        ig = ttk.Frame(ib)
        ig.pack(fill=tk.X)
        lbls = [('Hand ID:','hid'),('Fecha:','fecha'),('Btn:','btn'),('Pot:','pot'),('Winner:','winner')]
        for i,(l,v) in enumerate(lbls):
            ttk.Label(ig, text=l, font=('',7,'bold')).grid(row=0,column=i*2,padx=(0,3),sticky=tk.W)
            setattr(self, v, tk.StringVar())
            w = 12 if v!='fecha' else 24
            wgt = ttk.Label(ig, textvariable=getattr(self,v), width=w, font=('',7), anchor='w')
            wgt.grid(row=0,column=i*2+1,sticky=tk.W,padx=(0,4))
            if v=='fecha': wgt.config(foreground='darkblue')
        ttk.Label(ig, text='Ganador:', font=('',7,'bold')).grid(row=0,column=10,padx=(2,1),sticky=tk.W)
        self.winner_entry = ttk.Entry(ig, width=16, font=('',7))
        self.winner_entry.grid(row=0,column=11,sticky=tk.W)
        self.winner_entry.bind('<FocusOut>', lambda e: self._mod())

    # ===== EDIT TAB =====
    def _edit_ui(self, p):
        top = ttk.Frame(p)
        top.pack(fill=tk.X, pady=(0,2))
        ttk.Label(top, text='ID:', font=('',8,'bold')).pack(side=tk.LEFT)
        self.jvar = tk.StringVar()
        ttk.Entry(top, textvariable=self.jvar, width=8).pack(side=tk.LEFT, padx=(2,2))
        ttk.Button(top, text='Ir', command=self._jumphand).pack(side=tk.LEFT, padx=(0,3))
        ttk.Label(top, text='←').pack(side=tk.LEFT, padx=(0,2))
        self.jstatus = ttk.Label(top, text='')
        self.jstatus.pack(side=tk.LEFT)

        ib = ttk.LabelFrame(p, text='Info', padding=1)
        ib.pack(fill=tk.X, pady=(0,2))
        ig = ttk.Frame(ib)
        ig.pack(fill=tk.X)
        lbls = [('Hand ID:','hid'),('Fecha:','fecha'),('Btn:','btn'),('Pot:','pot'),('Winner:','winner')]
        for i,(l,v) in enumerate(lbls):
            ttk.Label(ig, text=l, font=('',7,'bold')).grid(row=0,column=i*2,padx=(0,3),sticky=tk.W)
            setattr(self, v, tk.StringVar())
            w = 12 if v!='fecha' else 24
            wgt = ttk.Label(ig, textvariable=getattr(self,v), width=w, font=('',7), anchor='w')
            wgt.grid(row=0,column=i*2+1,sticky=tk.W,padx=(0,4))
            if v=='fecha': wgt.config(foreground='darkblue')
        ttk.Label(ig, text='Ganador:', font=('',7,'bold')).grid(row=0,column=10,padx=(2,1),sticky=tk.W)
        self.winner_entry = ttk.Entry(ig, width=16, font=('',7))
        self.winner_entry.grid(row=0,column=11,sticky=tk.W)
        self.winner_entry.bind('<FocusOut>', lambda e: self._mod())
        ttk.Button(ig, text='Apl', width=4, command=self._setwinner).grid(row=0,column=12,padx=(2,0),sticky=tk.W)

        nav = ttk.Frame(p)
        nav.pack(fill=tk.X, pady=(1,0))
        ttk.Button(nav, text='◀◀', width=3, command=lambda: self._nav(-10)).pack(side=tk.LEFT)
        ttk.Button(nav, text='◀', width=3, command=lambda: self._nav(-1)).pack(side=tk.LEFT, padx=(0,1))
        ttk.Label(nav, textvariable=self._nav_text, width=9).pack(side=tk.LEFT, padx=3)
        ttk.Button(nav, text='▶', width=3, command=lambda: self._nav(1)).pack(side=tk.LEFT, padx=(1,0))
        ttk.Button(nav, text='▶▶', width=3, command=lambda: self._nav(10)).pack(side=tk.LEFT)
        ttk.Label(nav, text='(o pestaña Buscar)', font=('',6), foreground='gray').pack(side=tk.LEFT, padx=(8,0))

        lc = ttk.Frame(p)
        lc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,2))

        pf = ttk.LabelFrame(lc, text='Jugadores', padding=2)
        pf.pack(fill=tk.X, pady=(0,2))
        cols = ('pos','name','stack','cards','act')
        self.pt = ttk.Treeview(pf, columns=cols, show='headings', height=5)
        for c,w in zip(cols,[40,90,45,55,35]):
            self.pt.heading(c, text={'pos':'Pos','name':'Nombre','stack':'Stack','cards':'Cards','act':'Act'}[c], command=lambda _c=c: self._sortc(_c))
            self.pt.column(c, width=w)
        pbar = ttk.Scrollbar(pf, orient=tk.VERTICAL, command=self.pt.yview)
        self.pt.configure(yscrollcommand=pbar.set)
        self.pt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pbar.pack(side=tk.RIGHT, fill=tk.Y)

        pe = ttk.LabelFrame(lc, text='Editar (clic fila)', padding=2)
        pe.pack(fill=tk.X, pady=(2,0))

        ne = ttk.Frame(pe)
        ne.pack(fill=tk.X)
        ttk.Label(ne, text='Nom:').pack(side=tk.LEFT)
        self.enm = tk.StringVar()
        ttk.Entry(ne, textvariable=self.enm, width=10).pack(side=tk.LEFT, padx=(2,2))
        ttk.Button(ne, text='Apl', command=self._setnm).pack(side=tk.LEFT, padx=(0,3))

        pe2 = ttk.Frame(pe)
        pe2.pack(fill=tk.X)
        ttk.Label(pe2, text='Pos:').pack(side=tk.LEFT)
        self.epos = tk.StringVar()
        ttk.Entry(pe2, textvariable=self.epos, width=4).pack(side=tk.LEFT, padx=(2,2))
        ttk.Button(pe2, text='Apl', command=self._setpos).pack(side=tk.LEFT, padx=(0,3))

        pe3 = ttk.Frame(pe)
        pe3.pack(fill=tk.X)
        ttk.Label(pe3, text='Cards:').pack(side=tk.LEFT)
        self.ecards = tk.StringVar()
        ttk.Entry(pe3, textvariable=self.ecards, width=6).pack(side=tk.LEFT, padx=(2,2))
        ttk.Button(pe3, text='Apl', command=self._setcards).pack(side=tk.LEFT, padx=(0,3))

        pe4 = ttk.Frame(pe)
        pe4.pack(fill=tk.X)
        self.eact = tk.BooleanVar(value=True)
        ttk.Checkbutton(pe4, text='Activo', variable=self.eact).pack(side=tk.LEFT, padx=(2,2))
        ttk.Button(pe4, text='Apl', command=self._setact).pack(side=tk.LEFT, padx=(2,0))

        ttk.Label(pe, text='Clic fila → editar → Apl', foreground='gray', font=('',6)).pack(fill=tk.X, pady=(1,0))

        rc = ttk.Frame(p)
        rc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sf = ttk.LabelFrame(rc, text='Calles y Acciones', padding=2)
        sf.pack(fill=tk.BOTH, expand=True)
        self.sn = ttk.Notebook(sf)
        self.sn.pack(fill=tk.BOTH, expand=True)
        self.at = {}

        for st in ['preflop','flop','turn','river']:
            frm = ttk.Frame(self.sn)
            self.sn.add(frm, text=st.upper())
            bf = ttk.Frame(frm)
            bf.pack(fill=tk.X, pady=(0,1))
            ttk.Label(bf, text='Board:', font=('',8,'bold')).pack(side=tk.LEFT)
            bv = tk.StringVar(); setattr(self, f'bd_{st}', bv)
            be = ttk.Entry(bf, textvariable=bv, width=14, font=('Consolas',8))
            be.pack(side=tk.LEFT, padx=(2,2))
            setattr(self, f'bd_entry_{st}', be)
            ttk.Button(bf, text='Apl', command=lambda s=st: self._setboard(s)).pack(side=tk.LEFT, padx=(0,2))
            ttk.Button(bf, text='🗑', width=2, command=lambda s=st: self._clrboard(s)).pack(side=tk.LEFT)
            tree = ttk.Treeview(frm, columns=('pos','action','amount'), show='headings', height=5)
            tree.heading('pos', text='Pos'); tree.heading('action', text='Accion'); tree.heading('amount', text='Monto')
            tree.column('pos', width=55); tree.column('action', width=55); tree.column('amount', width=65)
            tree.pack(fill=tk.BOTH, expand=True)
            tree.bind('<Double-1>', lambda e, s=st: self._modact(s))
            self.at[st] = tree
            af = ttk.Frame(frm)
            af.pack(fill=tk.X, pady=(1,0))
            ttk.Label(af, text='Agregar:').pack(side=tk.LEFT)
            pv = tk.StringVar(); setattr(self, f'ap_{st}', pv)
            ttk.Entry(af, textvariable=pv, width=4).pack(side=tk.LEFT, padx=(2,1))
            av = tk.StringVar(); setattr(self, f'aa_{st}', av)
            ttk.Combobox(af, textvariable=av, values=['b','c','r','f','x'], width=3).pack(side=tk.LEFT, padx=(0,1))
            amv = tk.StringVar(); setattr(self, f'amt_{st}', amv)
            ttk.Entry(af, textvariable=amv, width=4).pack(side=tk.LEFT, padx=(0,1))
            ttk.Button(af, text='+', width=2, command=lambda s=st: self._addact(s)).pack(side=tk.LEFT, padx=(0,1))
            ttk.Button(af, text='🗑', width=2, command=lambda s=st: self._delact(s)).pack(side=tk.LEFT, padx=(0,1))
            ttk.Button(af, text='⬆', width=2, command=lambda s=st: self._mvact(s,-1)).pack(side=tk.LEFT, padx=(0,1))
            ttk.Button(af, text='⬇', width=2, command=lambda s=st: self._mvact(s,1)).pack(side=tk.LEFT, padx=(0,1))
            ttk.Button(af, text='🔄', width=2, command=lambda s=st: self._modact(s)).pack(side=tk.LEFT, padx=(0,1))
            ttk.Button(af, text='Limpiar', command=lambda s=st: self._clearact(s)).pack(side=tk.LEFT)

        bs = ttk.Frame(rc)
        bs.pack(fill=tk.X, pady=(2,0))
        ttk.Label(bs, text='Pot:', font=('',8,'bold')).pack(side=tk.LEFT)
        self.pot_entry = ttk.Entry(bs, width=7, font=('',7))
        self.pot_entry.pack(side=tk.LEFT, padx=(2,4))
        self.pot_entry.bind('<FocusOut>', lambda e: self._mod())
        ttk.Label(bs, text='Showdown:', font=('',8,'bold')).pack(side=tk.LEFT)
        self.sw_entry = ttk.Entry(bs, width=25, font=('',7))
        self.sw_entry.pack(side=tk.LEFT, padx=(2,4))
        self.sw_entry.bind('<FocusOut>', lambda e: self._mod())

        bf = ttk.Frame(rc)
        bf.pack(fill=tk.X, pady=(2,0))
        ttk.Button(bf, text='💾 Guardar', command=self._save).pack(side=tk.LEFT, padx=(0,2))
        ttk.Button(bf, text='Guardar+Btn', command=self._savenext).pack(side=tk.LEFT, padx=(0,2))
        ttk.Button(bf, text='JSON', command=self._savejson).pack(side=tk.LEFT, padx=(0,2))
        ttk.Button(bf, text='Recargar', command=self._reload).pack(side=tk.LEFT)
        self.sstatus = ttk.Label(bf, text='')
        self.sstatus.pack(side=tk.RIGHT, padx=4)

    # ===== LOGIC =====

    def _showall(self):
        self.search_res = list(range(len(self.hands)))
        self._updatelb()
        if self.hands: self._go(0)

    def _dosearch(self):
        q = self.sentry.get().strip().lower()
        m = self.svar.get()
        if not q: self._showall(); return
        res = []
        for i,h in enumerate(self.hands):
            if m=='id':
                if q in h.get('hand_id','').lower(): res.append(i)
            elif m=='board':
                bs=' '.join(h.get('comunitarias',{}).get('flop',[])+h.get('comunitarias',{}).get('turn',[])+h.get('comunitarias',{}).get('river',[]))
                if q in bs.lower(): res.append(i)
            elif m=='hb':
                hs=h.get('hand_id','').lower()
                bs=' '.join(h.get('comunitarias',{}).get('flop',[])+h.get('comunitarias',{}).get('turn',[])+h.get('comunitarias',{}).get('river',[]))
                if q in hs or q in bs.lower(): res.append(i)
            elif m=='filter':
                if any(q in p.get('name','').lower() or q in p.get('pos','').lower() for p in h.get('players',[])): res.append(i)
        self.search_res = res
        self._updatelb()
        if res: self._go(res[0])
        else: self.sstatus.config(text='Sin resultados', foreground='orange')

    def _updatelb(self):
        self.lb.delete(0, tk.END)
        idx = self.search_res if self.search_res else list(range(len(self.hands)))
        for i in idx:
            h = self.hands[i]
            bs=' '.join(h.get('comunitarias',{}).get('flop',[])+h.get('comunitarias',{}).get('turn',[])+h.get('comunitarias',{}).get('river',[]))
            w = h.get('winner',[''])[0] if h.get('winner') else ''
            self.lb.insert(tk.END, f"{h.get('hand_id','')} | {h.get('date','')[:10]} | {bs:24s} | P:{h.get('final_pot',0):>5} | W:{w}")
        self._nav_text.set(f'{self.cur+1} / {len(self.hands)}')

    def _onlist(self):
        sel = self.lb.curselection()
        if sel and self.search_res:
            self.cur = self.search_res[sel[0]]
            self._disp()

    def _nav(self, d):
        if not self.hands: return
        if not self.search_res: self.search_res = list(range(len(self.hands)))
        try: ii = self.search_res.index(self.cur)
        except ValueError: ii = 0
        ni = max(0, min(ii+d, len(self.search_res)-1))
        self.cur = self.search_res[ni]
        self._disp()
        self._updatelb()
        self.lb.selection_clear(0, tk.END)
        self.lb.selection_set(ni)
        self.lb.see(ni)

    def _go(self, idx):
        if not self.hands: return
        if isinstance(idx, str): idx = self.hand_idx.get(idx, 0)
        self.cur = max(0, min(idx, len(self.hands)-1))
        self._disp()
        self._updatelb()
        if self.search_res and self.cur in self.search_res:
            li = self.search_res.index(self.cur)
            self.lb.selection_set(li); self.lb.see(li)
        self._nav_text.set(f'{self.cur+1} / {len(self.hands)}')

    def _jumpid(self):
        d = tk.Toplevel(self.root)
        d.title('Ir a mano'); d.geometry('280x90'); d.transient(self.root); d.grab_set()
        ttk.Label(d, text='Hand ID (ej: H_0042):').pack(pady=(8,2))
        e = ttk.Entry(d, width=14); e.pack(); e.focus()
        def go():
            hid = e.get().strip().upper()
            if hid in self.hand_idx:
                d.destroy(); self._go(self.hand_idx[hid])
            else:
                messagebox.showwarning('No encontrado', f'{hid} no existe')
        ttk.Button(d, text='Ir', command=go).pack(pady=(4,4))
        e.bind('<Return>', lambda ev: go())

    def _jumphand(self):
        hid = self.jvar.get().strip().upper()
        if not hid: return
        if hid in self.hand_idx:
            self._go(self.hand_idx[hid])
            self.jstatus.config(text=f'→ {hid} ✓', foreground='green')
        else:
            self.jstatus.config(text=f'{hid} no existe', foreground='red')

    def _fmt_date(self, s):
        """'2024-05-13T14:32:07.123456' → '2024-05-13 14:32'"""
        if not s:
            return ''
        # Reemplaza la 'T' por espacio y corta a 16 chars (fecha + hora + minuto)
        s = s.replace('T', ' ')
        return s[:16]
    
    def _disp(self):
        h = self._cur()
        if not h: return
        self._mod(False)
        self.hid.set(h.get('hand_id',''))
        self.fecha.set(self._fmt_date(h.get('date','')))
        self.btn.set(f"{h.get('btn_player','')}(idx={h.get('btn_idx','')})")
        self.pot.set(str(h.get('final_pot',0)))
        self.pot_entry.delete(0,tk.END); self.pot_entry.insert(0,str(h.get('final_pot',0)))
        self.winner.set(', '.join(h.get('winner',[])))
        self.winner_entry.delete(0,tk.END); self.winner_entry.insert(0,', '.join(h.get('winner',[])))
        sw = h.get('showdown',{})
        self.sw_entry.delete(0,tk.END); self.sw_entry.insert(0, json.dumps(sw, ensure_ascii=False) if sw else '')
        self.pt.delete(*self.pt.get_children())
        for p in h.get('players',[]):
            self.pt.insert('', tk.END, values=(p.get('pos',''), p.get('name',''), p.get('stack',''), p.get('cards',''), 'Sí' if p.get('active') else 'No'))
        for st in ['preflop','flop','turn','river']:
            sd = h.get('streets',{}).get(st,{})
            getattr(self, f'bd_{st}').set(' '.join(sd.get('board',[])) if sd.get('board') else '')
            t = self.at[st]
            t.delete(*t.get_children())
            for a in sd.get('actions',[]):
                t.insert('', tk.END, values=(a.get('pos',''), a.get('action',''), a.get('amount','')))

    def _mod(self, m=True):
        if m: self.sstatus.config(text='★ Modificado', foreground='red')
        else: self.sstatus.config(text='')

    def _cplayer_idx(self):
        sel = self.pt.selection()
        if not sel: return None
        return self.pt.index(sel[0])

    def _cur(self):
        if 0 <= self.cur < len(self.hands): return self.hands[self.cur]
        return None

    def _setnm(self):
        h = self._cur()
        if not h: return
        i = self._cplayer_idx()
        if i is None or i >= len(h['players']):
            messagebox.showinfo('Info','Clic una fila primero'); return
        n = self.enm.get().strip()
        if not n: return
        h['players'][i]['name'] = n
        self._mod(); self._disp()

    def _setpos(self):
        h = self._cur()
        if not h: return
        i = self._cplayer_idx()
        if i is None or i >= len(h['players']):
            messagebox.showinfo('Info','Clic una fila primero'); return
        np = self.epos.get().strip().upper()
        h['players'][i]['pos'] = np
        self._mod(); self._disp()

    def _setcards(self):
        h = self._cur()
        if not h: return
        i = self._cplayer_idx()
        if i is None or i >= len(h['players']):
            messagebox.showinfo('Info','Clic una fila primero'); return
        c = self._normalize_cards(self.ecards.get().strip())
        h['players'][i]['cards'] = c
        self._mod(); self._disp()

    def _setwinner(self):
        h = self._cur()
        if not h: return
        w = self.winner_entry.get().strip()
        h['winner'] = [x.strip() for x in w.split(',') if x.strip()] if w else []
        self.winner.set(', '.join(h['winner']))
        self._mod(); self._disp()

    def _normalize_cards(self, raw):
        """Convierte 'as kd' o 'ASK D' o 'AsKd' → 'AsKd' (rank mayúscula, palo minúscula)."""
        raw = raw.replace(' ', '').replace(',', '')
        if not raw:
            return ''
        # Agrupar en pares rank+suit
        if len(raw) % 2 != 0:
            # entrada parcheada: solo intenta normalizar sin romper
            pairs = [raw[i:i+2] for i in range(0, len(raw), 2)]
        else:
            pairs = [raw[i:i+2] for i in range(0, len(raw), 2)]
        out = []
        for pair in pairs:
            if len(pair) == 2:
                out.append(pair[0].upper() + pair[1].lower())
            else:
                out.append(pair.upper())
        return ''.join(out)

    def _setact(self):
        h = self._cur()
        if not h: return
        i = self._cplayer_idx()
        if i is None or i >= len(h['players']): return
        h['players'][i]['active'] = self.eact.get()
        self._mod(); self._disp()

    def _setboard(self, st):
        h = self._cur()
        if not h: return
        raw = getattr(self, f'bd_{st}').get().strip()
        cards = self._parse_board(raw)
        h.setdefault('streets',{}).setdefault(st,{})['board'] = cards
        self._mod(); self._disp()

    def _clrboard(self, st):
        h = self._cur()
        if not h: return
        h.setdefault('streets',{}).setdefault(st,{})['board'] = []
        self._mod(); self._disp()

    def _parse_board(self, raw):
        """'As Kd 7h' o 'AsKd7h' → ['As','Kd','7h']"""
        raw = raw.replace(',', ' ').strip()
        if not raw:
            return []
        # Si vienen con espacios, separar directo
        if ' ' in raw:
            tokens = raw.split()
            # Si algún token tiene más de 2 chars, lo partimos igual
            out = []
            for t in tokens:
                out.extend(self._split_cards(t))
            return [self._norm_card(c) for c in out if c]
        else:
            # Pegado: AsKd7h
            return [self._norm_card(c) for c in self._split_cards(raw) if c]

    def _split_cards(self, s):
        return [s[i:i+2] for i in range(0, len(s), 2) if len(s[i:i+2]) == 2]

    def _norm_card(self, c):
        """'AS' → 'As', 'as' → 'As', '7h' → '7h', 'TH' → 'Th'"""
        if len(c) != 2: return c
        return c[0].upper() + c[1].lower()

    def _addact(self, st):
        h = self._cur()
        if not h: return
        pos = getattr(self, f'ap_{st}').get().strip().upper()
        act = getattr(self, f'aa_{st}').get().strip().lower()
        amt_str = getattr(self, f'amt_{st}').get().strip()
        if not pos or not act: messagebox.showwarning('Error','Pos y acción req'); return
        try: amt = float(amt_str) if amt_str else 0.0
        except ValueError: amt = 0.0
        h.setdefault('streets',{}).setdefault(st,{}).setdefault('actions',[]).append({'pos':pos,'action':act,'amount':amt})
        getattr(self, f'ap_{st}').set('')
        getattr(self, f'aa_{st}').set('')
        getattr(self, f'amt_{st}').set('')
        self._mod(); self._disp()

    def _delact(self, st):
        h = self._cur()
        if not h: return
        t = self.at[st]
        sel = t.selection()
        if not sel: messagebox.showwarning('Error','Selec una acción'); return
        i = t.index(sel[0])
        a = h.get('streets',{}).get(st,{}).get('actions',[])
        if 0<=i<len(a): a.pop(i); self._mod(); self._disp()

    def _clearact(self, st):
        h = self._cur()
        if not h: return
        if messagebox.askyesno('Confirmar', f'Limpiar {st}?'):
            h.get('streets',{}).get(st,{}).setdefault('actions',[]).clear()
            self._mod(); self._disp()

    def _mvact(self, st, d):
        h = self._cur()
        if not h: return
        t = self.at[st]
        sel = t.selection()
        if not sel: messagebox.showwarning('Error','Selec una acción'); return
        i = t.index(sel[0])
        a = h.get('streets',{}).get(st,{}).get('actions',[])
        ni = i+d
        if a and 0<=ni<len(a):
            a[i],a[ni] = a[ni],a[i]; self._mod(); self._disp()

    def _modact(self, st):
        h = self._cur()
        if not h: return
        t = self.at[st]
        sel = t.selection()
        if not sel: messagebox.showwarning('Error','Selec una acción'); return
        i = t.index(sel[0])
        a = h.get('streets',{}).get(st,{}).get('actions',[])
        if 0<=i<len(a):
            cur = a[i]
            cyc = {'b':'c','c':'r','r':'f','f':'x','x':'b'}
            cur['action'] = cyc.get(cur['action'], cur['action'])
            self._mod(); self._disp()

    def _sortc(self, col):
        data = [(self.pt.set(c,col), c) for c in self.pt.get_children('')]
        rv = col in ('name','stack')
        try:
            data.sort(key=lambda x: float(x[0]) if x[0] and x[0].replace('.','').replace('-','').isdigit() else x[0], reverse=rv)
        except: pass
        for i,(_,c) in enumerate(data): self.pt.move(c,'',i)

    def _save(self):
        h = self._cur()
        if not h: return
        try: h['final_pot'] = float(self.pot_entry.get())
        except: pass
        w = self.winner_entry.get().strip()
        h['winner'] = [x.strip() for x in w.split(',') if x.strip()] if w else []
        sw = self.sw_entry.get().strip()
        if sw:
            try: h['showdown'] = json.loads(sw)
            except: h['showdown'] = {'winner1': sw}
        else: h['showdown'] = {}
        self._write()
        self._mod(False)
        self.sstatus.config(text='Guardado ✓', foreground='green')

    def _savenext(self):
        self._save(); self._nav(1)

    def _savejson(self):
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON','*.json')])
        if path:
            h = self._cur()
            if h:
                with open(path,'w',encoding='utf-8') as f: json.dump(h,f,indent=2,ensure_ascii=False)
                messagebox.showinfo('OK', f'Guardado: {path}')

    def _reload(self):
        self._load()
        self._disp(); self._updatelb()
        self._mod(False); self.sstatus.config(text='Recargado')

    def _write(self):
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        with open(DATA_PATH,'w',encoding='utf-8') as f:
            for h in self.hands: f.write(json.dumps(h, ensure_ascii=False) + '\n')

if __name__ == '__main__':
    root = tk.Tk()
    app = HandEditor(root)
    root.mainloop()
