"""range_lab_gui.py — laboratorio experimental del creador/actualizador de rangos.

Revisa de forma experimental el pipeline rival:

  creador    : OR poblacional (preflop.py) o perfilado (player_ranges.py)
  actualizador: RangeState.update con P(A|H) postflop (postflop_ranges.py)
  equity     : situation.equity_vs_range tras cada paso
  tiempos    : perf_counter por etapa (creación, cada update, cada equity)

Uso:
  python tools/range_lab_gui.py                 (UI tkinter)
  python tools/range_lab_gui.py --test          (headless: demo + timings en consola)
"""
import os
import sys
import time
import tkinter as tk
from tkinter import ttk, scrolledtext

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import numpy as np

from motor import postflop_ranges as pf_mod
from motor import player_ranges as pr_mod
from motor.cards import card_id
from motor.hand_evaluator import evaluate_hand
from motor.preflop import opening_range
from motor.ranges import N_COMBOS, RangeState, uniform_range
from motor.situation import equity_vs_range

POSICIONES = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']
SPOTS = ['no_raise', 'facing_open', 'facing_3bet']
ACCIONES_PRE = ['open', 'limp', 'rol', 'call_limp', 'bb_check', 'call_open',
                '3bet', 'squeeze', '4bet', 'call_3bet', 'fold', 'fold_vs_open',
                'fold_vs_3bet']
STREETS = ['flop', 'turn', 'river']
FACINGS = ['none', 'bet', 'cbet', 'barrel', 'raise']
ACCIONES_POST = ['x', 'b', 'c', 'f', 'r']
ACCION_NOMBRE = {'x': 'check', 'b': 'bet', 'c': 'call', 'f': 'fold', 'r': 'raise'}


# ---------------------------------------------------------------------------
# Núcleo experimental (UI-agnóstico, para poder medir sin tkinter)
# ---------------------------------------------------------------------------

def load_models():
    """Carga ProfileRangeModel + PostflopRangeModel (json si existe, si no DB)."""
    t = {}
    t0 = time.perf_counter()
    try:
        pre = pr_mod.ProfileRangeModel.load()
        t['preflop_load'] = (time.perf_counter() - t0) * 1000
    except (FileNotFoundError, ValueError, KeyError):
        from motor.learn import load_hands
        hands = load_hands()
        t0 = time.perf_counter()
        pre = pr_mod.ProfileRangeModel.from_hands(hands)
        t['preflop_load'] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    try:
        post = pf_mod.PostflopRangeModel.load()
        t['postflop_load'] = (time.perf_counter() - t0) * 1000
    except (FileNotFoundError, ValueError, KeyError):
        from motor.learn import load_hands
        hands = load_hands()
        t0 = time.perf_counter()
        post = pf_mod.PostflopRangeModel.from_hands(hands)
        t['postflop_load'] = (time.perf_counter() - t0) * 1000
    # reinyectar Oracle si el load lo perdió (load no restaura _oracle)
    if getattr(post, '_oracle', None) is None:
        try:
            from motor.behavior import Oracle, build
            from motor.learn import load_hands
            hands = load_hands()
            post._oracle = Oracle(build(hands, labels=dict(post.labels)))
            t['oracle_rebuild'] = True
        except Exception:
            t['oracle_rebuild'] = False
    # warmup del evaluador (tabla C(52,5) ~10 MB, build una sola vez): se mide
    # aparte para no contaminar la equity del paso 0 en frío
    t0 = time.perf_counter()
    try:
        from motor.hand_evaluator import _five_table
        _five_table()
    except Exception:
        pass
    t['evaluator_warmup'] = (time.perf_counter() - t0) * 1000
    return pre, post, t


def build_base_range(pre_model, perfil, spot, accion, pos, modo='perfilado'):
    """Creador rival. Devuelve (reach_vec, tiempos, detalle).

    modo 'perfilado': ProfileRangeModel.prob_vec (perfil) — ignora jugador.
    modo 'poblacional': OR preflop de la posición (sin perfil).
    """
    t = {}
    if modo == 'poblacional' or not perfil or perfil == '(OR poblacional)':
        t0 = time.perf_counter()
        vec = opening_range(pos).astype(np.float32)
        t['creador'] = (time.perf_counter() - t0) * 1000
        return vec, t, f'OR_{pos} poblacional'
    t0 = time.perf_counter()
    vec = pre_model.prob_vec(perfil, spot, accion, pos).astype(np.float32)
    t['creador'] = (time.perf_counter() - t0) * 1000
    opp = pre_model.opp.get((perfil, spot))
    n = int(opp.sum()) if opp is not None else 0
    return vec, t, f'{perfil} {spot}/{accion} pos={pos} (n_opp={n})'


def run_pipeline(hero, board, base_vec, post_model, perfil, pasos):
    """Ejecuta creador + N updates + equity tras cada paso, todo cronometrado.

    pasos: lista de dicts {street, facing, action, hero_pos, villain_pos}.
    La posición postflop se REGISTRA por paso pero el modelo actual solo
    condiciona por (perfil, street, facing, bucket): se muestra para evidenciar
    que hoy no mueve la equity (futuro split por posición).

    Devuelve (filas, resumen) donde cada fila es un dict con equity, masa, ms.
    """
    filas = []
    tiempos = {}

    t0 = time.perf_counter()
    rs = RangeState(reach=base_vec)
    rs.set_known_cards(list(hero) + list(board))
    tiempos['blockers'] = (time.perf_counter() - t0) * 1000

    def _equity(rs_):
        t1 = time.perf_counter()
        eq, w, ti, l = equity_vs_range(list(hero), list(board),
                                       villain_reach=rs_)
        ms = (time.perf_counter() - t1) * 1000
        return eq, w, ti, l, ms

    eq, w, ti, l, ms_eq = _equity(rs)
    filas.append({'paso': 0, 'desc': 'base (creador + blockers)',
                  'street': '-', 'facing': '-', 'action': '-',
                  'hero_pos': '-', 'vil_pos': '-',
                  'equity': eq, 'wins': w, 'ties': ti, 'losses': l,
                  'masa': float(rs.reach.sum()),
                  'ms_update': 0.0, 'ms_equity': ms_eq, 'n_cell': '',
                  'prior': ''})

    for i, p in enumerate(pasos, 1):
        st, fa, ac = p['street'], p['facing'], p['action']
        t1 = time.perf_counter()
        vec = post_model.prob_vec(perfil, st, fa, list(board), ac)
        ms_vec = (time.perf_counter() - t1) * 1000
        vec_mean = float(vec.mean())
        t1 = time.perf_counter()
        rs.update(vec)
        ms_upd = (time.perf_counter() - t1) * 1000
        eq, w, ti, l, ms_eq = _equity(rs)
        # contexto de evidencia: n del facing + prior Oracle
        n_cell = sum(v for k, v in post_model.opp.items()
                     if k[0] == perfil and k[1] == st and k[2] == fa)
        prior = post_model._prior(perfil, st, fa) or {}
        prior_s = (f"{prior.get(ac, 0.0):.2f}" if prior else '?')
        filas.append({
            'paso': i,
            'desc': f"{st} {fa} -> {ac} ({ACCION_NOMBRE.get(ac, ac)})",
            'street': st, 'facing': fa, 'action': ac,
            'hero_pos': p.get('hero_pos', '-'), 'vil_pos': p.get('villain_pos', '-'),
            'equity': eq, 'wins': w, 'ties': ti, 'losses': l,
            'masa': float(rs.reach.sum()),
            'ms_update': ms_vec + ms_upd, 'ms_equity': ms_eq,
            'n_cell': str(n_cell),
            'prior': prior_s,
            'vec_mean': vec_mean,
        })
        tiempos[f'paso{i}'] = ms_vec + ms_upd + ms_eq
    return filas, tiempos, rs


def top_combos(rs, k=8):
    return rs.top_hands(k=k)


def bucket_dist(post_model, board, rs):
    """Reparto de masa por bucket de fuerza sobre el board actual."""
    try:
        bids = np.asarray([card_id(c) for c in board], dtype=np.intp)
        _, buckets = post_model._board_buckets(bids)
    except (ValueError, IndexError):
        return []
    w = rs.weights
    out = []
    for b in range(post_model.n_buckets):
        out.append(float(w[buckets == b].sum()))
    return out


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class RangeLabGUI:
    def __init__(self, pre_model, post_model, load_ms):
        self.pre = pre_model
        self.post = post_model
        self.load_ms = load_ms
        self.perfiles = sorted({p for (p, _s) in self.pre.opp} |
                               set(self.post.labels.values()))
        self.root = tk.Tk()
        self.root.title('Lab rangos rival — creador / actualizador / equity / tiempos')
        self.root.geometry('1020x820')

        # ---- vars ----
        self.hero_var = tk.StringVar(value='Jd Jh')
        self.board_var = tk.StringVar(value='Qh 7s 2c')
        self.perfil_var = tk.StringVar(
            value=self.perfiles[0] if self.perfiles else '(OR poblacional)')
        self.modo_var = tk.StringVar(value='perfilado')
        self.vilpos_var = tk.StringVar(value='UTG')
        self.spot_var = tk.StringVar(value='no_raise')
        self.accpre_var = tk.StringVar(value='open')
        # nuevo paso postflop
        self.st_var = tk.StringVar(value='flop')
        self.fa_var = tk.StringVar(value='bet')
        self.ac_var = tk.StringVar(value='c')
        self.hpos_var = tk.StringVar(value='BB')
        self.vpos_var = tk.StringVar(value='BTN')
        self.pasos = [
            {'street': 'flop', 'facing': 'bet', 'action': 'c',
             'hero_pos': 'BB', 'villain_pos': 'BTN'},
        ]
        self._build_ui()
        self.recalcular()

    # ---------- construcción ----------
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # entrada
        f0 = ttk.LabelFrame(main, text='Hero / board / creador rival (preflop)', padding=8)
        f0.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f0, text='Hero:').grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(f0, textvariable=self.hero_var, width=14).grid(row=0, column=1, padx=4)
        ttk.Label(f0, text='Board:').grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(f0, textvariable=self.board_var, width=22).grid(row=0, column=3, padx=4)
        ttk.Label(f0, text='(cartas separadas por espacio: Qh 7s 2c)').grid(
            row=0, column=4, sticky=tk.W)

        ttk.Label(f0, text='Modo:').grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(f0, textvariable=self.modo_var, width=12, state='readonly',
                     values=['perfilado', 'poblacional']).grid(row=1, column=1, padx=4)
        ttk.Label(f0, text='Perfil:').grid(row=1, column=2, sticky=tk.W)
        ttk.Combobox(f0, textvariable=self.perfil_var, width=16, state='readonly',
                     values=self.perfiles + ['(OR poblacional)']).grid(row=1, column=3, padx=4)
        ttk.Label(f0, text='Pos vil:').grid(row=1, column=4, sticky=tk.W)
        ttk.Combobox(f0, textvariable=self.vilpos_var, width=7, state='readonly',
                     values=POSICIONES).grid(row=1, column=5, padx=4)

        ttk.Label(f0, text='Spot:').grid(row=2, column=0, sticky=tk.W)
        ttk.Combobox(f0, textvariable=self.spot_var, width=12, state='readonly',
                     values=SPOTS).grid(row=2, column=1, padx=4)
        ttk.Label(f0, text='Acción pre:').grid(row=2, column=2, sticky=tk.W)
        ttk.Combobox(f0, textvariable=self.accpre_var, width=12, state='readonly',
                     values=ACCIONES_PRE).grid(row=2, column=3, padx=4)
        ttk.Button(f0, text='⟳ Recalcular todo', command=self.recalcular).grid(
            row=2, column=4, columnspan=2, padx=8)

        # nuevo paso postflop
        f1 = ttk.LabelFrame(main, text='Añadir acción postflop (+ posición, experimental)',
                            padding=8)
        f1.pack(fill=tk.X, pady=(0, 6))
        for i, (lbl, var, vals, w) in enumerate([
                ('Street', self.st_var, STREETS, 8),
                ('Facing', self.fa_var, FACINGS, 8),
                ('Acción', self.ac_var, ACCIONES_POST, 6),
                ('Hero pos', self.hpos_var, POSICIONES, 7),
                ('Vil pos', self.vpos_var, POSICIONES, 7)]):
            ttk.Label(f1, text=lbl + ':').grid(row=0, column=i * 2, sticky=tk.W)
            ttk.Combobox(f1, textvariable=var, width=w, state='readonly',
                         values=vals).grid(row=0, column=i * 2 + 1, padx=4)
        ttk.Button(f1, text='+ Añadir y actualizar', command=self.anadir_paso).grid(
            row=0, column=10, padx=8)
        ttk.Button(f1, text='− Quitar último', command=self.quitar_paso).grid(
            row=0, column=11, padx=2)
        ttk.Button(f1, text='Limpiar', command=self.limpiar_pasos).grid(
            row=0, column=12, padx=2)
        ttk.Label(f1, text='NOTA: el modelo postflop condiciona por (perfil×street×facing×bucket); '
                           'la posición se registra por paso pero HOY no mueve P(A|H) — '
                           'sirve para comparar y preparar el split por posición.',
                  foreground='gray', wraplength=960, justify=tk.LEFT).grid(
            row=1, column=0, columnspan=13, sticky=tk.W, pady=(4, 0))

        # tabla de pasos
        f2 = ttk.LabelFrame(main, text='Equity vs rango + tiempos por paso', padding=8)
        f2.pack(fill=tk.X, pady=(0, 6))
        cols = ('paso', 'descripcion', 'equity', 'delta', 'masa', 'ms_upd', 'ms_eq', 'n', 'prior', 'pmedia')
        self.tree = ttk.Treeview(f2, columns=cols, show='headings', height=7)
        heads = {'paso': 'paso', 'descripcion': 'descripción', 'equity': 'equity',
                 'delta': 'Δ eq', 'masa': 'masa reach', 'ms_upd': 'ms update',
                 'ms_eq': 'ms equity', 'n': 'n facing', 'prior': 'prior P(A|C)',
                 'pmedia': 'P(A|H) media'}
        widths = {'paso': 45, 'descripcion': 230, 'equity': 70, 'delta': 70,
                  'masa': 90, 'ms_upd': 80, 'ms_eq': 80, 'n': 70, 'prior': 90,
                  'pmedia': 90}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor=tk.CENTER if c != 'descripcion' else tk.W)
        self.tree.pack(fill=tk.X)

        # detalle
        f3 = ttk.LabelFrame(main, text='Detalle / top combos / buckets / tiempos', padding=8)
        f3.pack(fill=tk.BOTH, expand=True)
        self.detail = scrolledtext.ScrolledText(f3, height=18, font=('Consolas', 9))
        self.detail.pack(fill=tk.BOTH, expand=True)

    # ---------- parse ----------
    @staticmethod
    def _parse_cards(txt, n_min, n_max):
        toks = [t.strip() for t in txt.replace(',', ' ').split() if t.strip()]
        if not (n_min <= len(toks) <= n_max):
            raise ValueError(f'se esperaban {n_min}..{n_max} cartas, hay {len(toks)}: {txt!r}')
        for t in toks:
            card_id(t)  # valida
        if len(set(toks)) != len(toks):
            raise ValueError(f'cartas duplicadas: {txt!r}')
        inter = set(toks[:2]) if len(toks) >= 2 else set()
        return toks

    # ---------- acciones ----------
    def anadir_paso(self):
        self.pasos.append({'street': self.st_var.get(), 'facing': self.fa_var.get(),
                           'action': self.ac_var.get(), 'hero_pos': self.hpos_var.get(),
                           'villain_pos': self.vpos_var.get()})
        self.recalcular()

    def quitar_paso(self):
        if self.pasos:
            self.pasos.pop()
        self.recalcular()

    def limpiar_pasos(self):
        self.pasos = []
        self.recalcular()

    def recalcular(self):
        try:
            toks_h = self._parse_cards(self.hero_var.get(), 2, 2)
            toks_b = self._parse_cards(self.board_var.get(), 3, 5)
        except ValueError as e:
            self.detail.delete('1.0', tk.END)
            self.detail.insert(tk.END, f'ERROR en cartas: {e}')
            return
        perfil = self.perfil_var.get()
        t_total0 = time.perf_counter()
        try:
            base_vec, t_crea, base_desc = build_base_range(
                self.pre, perfil, self.spot_var.get(), self.accpre_var.get(),
                self.vilpos_var.get(), modo=self.modo_var.get())
        except Exception as e:
            self.detail.delete('1.0', tk.END)
            self.detail.insert(tk.END, f'ERROR creador: {e}')
            return
        try:
            hero_score = evaluate_hand(toks_h, toks_b)
            from motor.hand_evaluator import category_name
            hero_cat = category_name(hero_score)
        except Exception:
            hero_cat = '?'
        try:
            filas, t_pasos, rs = run_pipeline(toks_h, toks_b, base_vec, self.post,
                                              perfil, self.pasos)
        except Exception as e:
            import traceback
            self.detail.delete('1.0', tk.END)
            self.detail.insert(tk.END, f'ERROR actualizador/equity: {e}\n{traceback.format_exc()}')
            return
        total_ms = (time.perf_counter() - t_total0) * 1000

        # tabla
        for r in self.tree.get_children():
            self.tree.delete(r)
        prev_eq = None
        for f in filas:
            d = '' if prev_eq is None else f"{f['equity'] - prev_eq:+.3f}"
            prev_eq = f['equity']
            self.tree.insert('', tk.END, values=(
                f["paso"], f["desc"], f"{f['equity']:.3f}", d,
                f"{f['masa']:.1f}", f"{f['ms_update']:.1f}", f"{f['ms_equity']:.1f}",
                f["n_cell"], f["prior"], f"{f.get('vec_mean', 0):.3f}" if f['paso'] else '-'))

        # detalle
        tops = top_combos(rs, k=8)
        buckets = bucket_dist(self.post, toks_b, rs)
        lines = []
        lines.append(f'Hero {toks_h}  Board {toks_b}  ({hero_cat})   vs {base_desc}')
        lines.append(f'Cargas: preflop {self.load_ms.get("preflop_load", 0):.1f} ms · '
                     f'postflop {self.load_ms.get("postflop_load", 0):.1f} ms · '
                     f'warmup evaluador {self.load_ms.get("evaluator_warmup", 0):.0f} ms')
        lines.append(f'Creador: {t_crea.get("creador", 0):.2f} ms · '
                     f'TOTAL pipeline: {total_ms:.1f} ms '
                     f'(updates Σ {sum(f["ms_update"] for f in filas):.1f} ms · '
                     f'equitys Σ {sum(f["ms_equity"] for f in filas):.1f} ms)')
        if filas:
            e0, e1 = filas[0]['equity'], filas[-1]['equity']
            lines.append(f'Equity: {e0:.3f} (base) → {e1:.3f} (final)   Δ {e1 - e0:+.3f}')
        lines.append('')
        lines.append('Top combos del rango rival final (etiqueta, peso):')
        for lab, w in tops:
            lines.append(f'  {lab:<6} {w:.4f}')
        if buckets:
            lines.append('')
            lines.append('Masa por bucket de fuerza (0=aire … 4=nuts):')
            lines.append('  ' + '  '.join(f'b{b}:{m:.2f}' for b, m in enumerate(buckets)))
        lines.append('')
        lines.append('Pasos postflop registrados (posición experimental, no usada por P(A|H)):')
        if not self.pasos:
            lines.append('  (sin pasos: solo rango base)')
        for i, p in enumerate(self.pasos, 1):
            lines.append(f"  {i}. {p['street']} facing={p['facing']} act={p['action']} "
                         f"hero_pos={p.get('hero_pos')} vil_pos={p.get('villain_pos')}")
        if any(f['masa'] <= 0 for f in filas[1:]):
            lines.append('')
            lines.append('AVISO: masa 0 → acción inconsistente con el facing '
                         '(p. ej. x frente a bet, b frente a raise). P(A|H)≈0 '
                         'colapsa el rango. Combinaciones válidas: facing none → x/b; '
                         'facing bet/cbet/barrel/raise → c/f/r.')
        self.detail.delete('1.0', tk.END)
        self.detail.insert(tk.END, '\n'.join(lines))

    def run(self):
        self.root.mainloop()


def main(argv=None):
    args = list(argv) if argv is not None else sys.argv[1:]
    if '--test' in args:
        pre, post, lms = load_models()
        print(f'load: preflop {lms.get("preflop_load", 0):.1f} ms · '
              f'postflop {lms.get("postflop_load", 0):.1f} ms')
        perfil = sorted({p for (p, _s) in pre.opp})[0]
        base_vec, t_crea, desc = build_base_range(pre, perfil, 'no_raise', 'open', 'UTG')
        print(f'creador ({desc}): {t_crea["creador"]:.2f} ms')
        pasos = [
            {'street': 'flop', 'facing': 'bet', 'action': 'c',
             'hero_pos': 'BB', 'villain_pos': 'BTN'},
            {'street': 'turn', 'facing': 'none', 'action': 'x',
             'hero_pos': 'BB', 'villain_pos': 'BTN'},
        ]
        t0 = time.perf_counter()
        filas, _tp, rs = run_pipeline(['Jd', 'Jh'], ['Qh', '7s', '2c'],
                                      base_vec, post, perfil, pasos)
        total = (time.perf_counter() - t0) * 1000
        for f in filas:
            print(f"  paso {f['paso']}: {f['desc']:<28} eq={f['equity']:.3f} "
                  f"masa={f['masa']:.1f} upd={f['ms_update']:.1f}ms eq={f['ms_equity']:.1f}ms")
        print(f'TOTAL: {total:.1f} ms · top: {rs.top_hands(3)}')
        return
    pre, post, lms = load_models()
    RangeLabGUI(pre, post, lms).run()


if __name__ == '__main__':
    main()
