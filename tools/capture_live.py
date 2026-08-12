"""
capture_live.py — Módulo de captura único.

Inicializa los lectores una sola vez y expone capture()
que toma un pantallazo, ejecuta ambos readers y devuelve
el dict de estado completo.

Uso:
  from capture_live import capture
  state = capture()
"""
import os, sys, time
import numpy as np
from PIL import ImageGrab

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lector_estado import StateReader
from lector_unificado import CardReader

_reader = None
_card_reader = None
_init_ms = 0

def get_readers():
    """Devuelve (StateReader, CardReader) — los singletons ya inicializados."""
    _ensure_loaded()
    return _reader, _card_reader

def _ensure_loaded():
    global _reader, _card_reader, _init_ms
    if _reader is not None:
        return
    t0 = time.perf_counter()
    _reader = StateReader()
    _card_reader = CardReader()
    _init_ms = (time.perf_counter() - t0) * 1000

def capture():
    _ensure_loaded()
    pil = ImageGrab.grab()
    img_arr = np.array(pil.convert('RGB'))
    state = _reader.read_all(pil)
    cards = _card_reader.read_all(img_arr)
    for seat in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
        if seat in cards and cards[seat]:
            state[f'{seat}_cards'] = cards[seat]
    state['community'] = cards.get('community', [])
    return state, img_arr, pil

def init_reader():
    """Inicializa los lectores sin capturar pantalla."""
    _ensure_loaded()

def init_ms():
    _ensure_loaded()
    return _init_ms
