# -*- coding: utf-8 -*-
"""Abre el editor de manos sobre la COPIA, no sobre la base canonica.

    python trabajo/ABRIR_EDITOR_COPIA.py

Que hace, y por que existe
-------------------------
`hand_editor.py` escribe en la ruta que le diga `POKER_DB_PATH`. Este
arranque la fija a `trabajo/hands_db_edicion.jsonl`, que es una COPIA de la
base canonica, y comprueba **ANTES** de abrir la ventana que la copia existe y
que la base canonica esta intacta.

Si alguien lanza `hand_editor.py` sin este script, sigue editando
`data/hands_db.jsonl`. Por eso el script no cambia el default: lo cambia solo
en su propia ejecucion.
"""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

COPIA = os.path.join(ROOT, 'trabajo', 'hands_db_edicion.jsonl')
CANONICA = os.path.join(ROOT, 'data', 'hands_db.jsonl')

# Lo que la canonica DEBE tener mientras se trabaja sobre la copia.
# Se lee de `motor/learn.py`, que es la unica declaracion vigente: si la base
# cambia de forma legitima, el commit que la cambia actualiza ese valor y este
# arranque lo hereda. Clavarlo aqui ya fallo una vez: el commit `12c7bed`
# (H_1196) subio la base a `5ae2abd7...` y este script seguia esperando
# `357279...`, anterior a ese commit.
from motor.learn import HANDS_DB_SHA256 as SHA_ESPERADO


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _lineas(p):
    with open(p, encoding='utf-8') as f:
        return sum(1 for l in f if l.strip())


def main():
    if not os.path.exists(COPIA):
        import shutil
        os.makedirs(os.path.dirname(COPIA), exist_ok=True)
        shutil.copy2(CANONICA, COPIA)
        print('copia creada: %s' % COPIA)

    sha_c = sha256(CANONICA)
    if sha_c != SHA_ESPERADO:
        print('PARADA: la base canonica NO tiene el hash esperado.')
        print('  esperado : %s' % SHA_ESPERADO)
        print('  ahora    : %s' % sha_c)
        print('Alguien la toco. NO se abre el editor: primero hay que')
        print('saber que cambio y decidir si se conserva.')
        return 1

    n = _lineas(COPIA)
    print('canonica : %s  (%d registros)' % (sha_c[:16], _lineas(CANONICA)))
    print('copia    : %s  (%d registros)' % (sha256(COPIA)[:16], n))
    print()
    print('EDITANDO LA COPIA. La canonica no se toca al guardar.')
    print()

    os.environ['POKER_DB_PATH'] = COPIA
    import hand_editor
    hand_editor.DATA_PATH = COPIA
    hand_editor.ES_COPIA = True

    import tkinter as tk
    root = tk.Tk()
    app = hand_editor.HandEditor(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())