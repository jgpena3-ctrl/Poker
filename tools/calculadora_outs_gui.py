"""calculadora_outs_gui.py — mini UI para decidir calls con draws.

Introduces tus outs, la apuesta a igualar y el bote total (bets vivos
incluidos); la ventana recalcula en vivo la equity del draw, las pot odds
necesarias, si el call es rentable de forma directa y, si no lo es, cuanto
dinero extra tendrias que sacarle al rival en calles posteriores para
recuperar el call (implied odds).

Uso:  python tools/calculadora_outs_gui.py
"""
import os
import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from motor.implied_odds import analizar_call  # noqa: E402

CALLE_OPCIONES = {
    'Flop (2 cartas por venir)': 2,
    'Turn (1 carta por venir)': 1,
}

VERDE = '#1a7f37'
ROJO = '#c62828'
INFINITO = float('inf')


def _fmt(valor):
    return 'infinito' if valor == INFINITO else f'{valor:.2f}'


class CalculadoraOutsGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Outs · Pot odds · Implied odds')
        self.root.resizable(False, False)
        self._topmost = tk.BooleanVar(value=True)
        self._apply_topmost()

        self.outs_var = tk.StringVar(value='8')
        self.calle_var = tk.StringVar(value='Turn (1 carta por venir)')
        self.call_var = tk.StringVar(value='100')
        self.bote_var = tk.StringVar(value='200')

        self._build_ui()
        for var in (self.outs_var, self.call_var, self.bote_var,
                    self.calle_var):
            var.trace_add('write', lambda *_: self._calcular())
        self._calcular()

    # ---------- UI ----------

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        datos = ttk.LabelFrame(main, text='Tu situacion', padding=10)
        datos.pack(fill=tk.X)

        ttk.Label(datos, text='Outs').grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Spinbox(datos, from_=0, to=46, textvariable=self.outs_var,
                    width=8).grid(row=0, column=1, padx=(8, 0), sticky=tk.W)

        ttk.Label(datos, text='Calle').grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Combobox(datos, textvariable=self.calle_var, width=26,
                     values=list(CALLE_OPCIONES),
                     state='readonly').grid(row=1, column=1, padx=(8, 0),
                                            sticky=tk.W)

        ttk.Label(datos, text='Apuesta a igualar').grid(
            row=2, column=0, sticky=tk.W, pady=3)
        ttk.Entry(datos, textvariable=self.call_var,
                  width=10).grid(row=2, column=1, padx=(8, 0), sticky=tk.W)

        ttk.Label(datos, text='Bote total (bets incluidos)').grid(
            row=3, column=0, sticky=tk.W, pady=3)
        ttk.Entry(datos, textvariable=self.bote_var,
                  width=10).grid(row=3, column=1, padx=(8, 0), sticky=tk.W)

        ttk.Checkbutton(main, text='Siempre encima de otras ventanas',
                        variable=self._topmost,
                        command=self._apply_topmost).pack(anchor=tk.W,
                                                          pady=(8, 4))

        res = ttk.LabelFrame(main, text='Resultado', padding=10)
        res.pack(fill=tk.BOTH, expand=True)

        self.lbl_equity = self._fila(res, 0, 'Equity del draw')
        self.lbl_potodds = self._fila(res, 1, 'Equity que necesitas')
        self.lbl_ev = self._fila(res, 2, 'Call directo')
        self.lbl_extra = self._fila(res, 3, 'Extra a sacarle al completar')
        self.lbl_total = self._fila(res, 4, 'Cobro minimo si completas')

        self.lbl_error = ttk.Label(main, text='', foreground=ROJO)
        self.lbl_error.pack(anchor=tk.W, pady=(4, 0))

    @staticmethod
    def _fila(parent, row, titulo):
        ttk.Label(parent, text=titulo).grid(row=row, column=0, sticky=tk.W,
                                            pady=2)
        lbl = ttk.Label(parent, text='-',
                        font=('Segoe UI', 10, 'bold'), anchor=tk.W)
        lbl.grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=(14, 0))
        return lbl

    def _apply_topmost(self):
        self.root.attributes('-topmost', bool(self._topmost.get()))

    # ---------- logica ----------

    @staticmethod
    def _num(var):
        texto = var.get().strip().replace(',', '.')
        if not texto:
            raise ValueError('Rellena todos los campos')
        try:
            valor = float(texto)
        except ValueError:
            raise ValueError('Introduce numeros validos')
        if valor < 0:
            raise ValueError('Los valores no pueden ser negativos')
        return valor

    def _calcular(self):
        self.lbl_error.config(text='')
        try:
            outs_texto = self.outs_var.get().strip()
            if outs_texto:
                outs = int(float(outs_texto))
            else:
                raise ValueError('Rellena todos los campos')
            call = self._num(self.call_var)
            bote = self._num(self.bote_var)
        except ValueError as exc:
            self.lbl_error.config(text=str(exc))
            return
        if outs < 0 or outs > 46:
            self.lbl_error.config(text='Los outs deben estar entre 0 y 46')
            return

        cartas = CALLE_OPCIONES[self.calle_var.get()]
        a = analizar_call(outs, cartas, call, bote)
        regla = '4' if cartas >= 2 else '2'

        self.lbl_equity.config(
            text=f'{a.equity * 100:.1f}%  '
                 f'(regla del {regla}: {a.equity_regla_42 * 100:.0f}%)')
        self.lbl_potodds.config(
            text=f'{a.pot_odds * 100:.1f}%  = call / (bote + call)')

        if a.rentable_directo:
            self.lbl_ev.config(
                text=f'RENTABLE  (EV {a.ev_directo:+.2f})', foreground=VERDE)
            self.lbl_extra.config(
                text='0 — el bote ya paga el call', foreground=VERDE)
        else:
            self.lbl_ev.config(
                text=f'NO rentable  (EV {a.ev_directo:+.2f})', foreground=ROJO)
            if a.extra_necesario == INFINITO:
                extra = 'infinito más del rival en siguientes calles'
            else:
                extra = (f'{a.extra_necesario:.2f} '
                         f'más del rival en siguientes calles '
                         f'(= {a.extra_pct_bote_call * 100:.1f}% del bote + call)')
            self.lbl_extra.config(text=extra, foreground=ROJO)
        self.lbl_total.config(
            text=f'{_fmt(a.cobro_minimo_al_completar)}'
                 f"{'' if a.rentable_directo else '  (bote + call + extra)'}")

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    CalculadoraOutsGUI().run()
