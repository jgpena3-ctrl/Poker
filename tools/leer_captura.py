"""
Uso: python leer_captura.py <numero>
Ej:  python leer_captura.py 108

Carga Captura de pantalla (<numero>).png y muestra todo lo que detectan los lectores,
incluyendo qué tecnología usó cada campo.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image
from lector_estado import StateReader, calib
from lector_unificado import CardReader, CARD_READER
from ocr_rapido import OcrRapido

CAPTURAS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'capturas')

def main():
    if len(sys.argv) < 2:
        print('Uso: python leer_captura.py <numero>')
        sys.exit(1)

    num = sys.argv[1]
    path = os.path.join(CAPTURAS_DIR, f'Captura de pantalla ({num}).png')
    if not os.path.exists(path):
        print(f'Archivo no encontrado: {path}')
        sys.exit(1)

    pil = Image.open(path)
    img = np.array(pil.convert('RGB'))
    gray_img = np.array(pil.convert('L'))

    print(f'=== Lectura de {os.path.basename(path)} ===')

    # 1. StateReader con detalle de tecnología
    print(f'\n--- StateReader ---')
    sr = StateReader()
    state = sr.read_all(pil)

    # Re-leer cada campo con la tecnología específica para mostrar diagnóstico
    print(f'\n  == Pot ==')
    print(f'  pot (DigitOCR):      {state.get("pot")}')

    print(f'\n  == Button ==')
    print(f'  btn (ChkRegion):     {state.get("btn")}')

    print(f'\n  == Stacks (DigitOCR pool=stacks) ==')
    for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
        coords = calib.get('player_stacks', {}).get(player)
        if coords:
            gc = gray_img[coords[1]:coords[3], coords[0]:coords[2]]
            ocr_val = sr.ocr.read(gc, pool='stacks')
            bm_val = sr.bm.read_region(gc, (f'{player}_stack',), is_stack=True)
            sr_val = sr.sr.read_number(gc, tuple(coords))
            final = state.get(f'{player}_stake')
            tech = 'DigitOCR'
            if final is None and ocr_val is not None:
                tech = 'DigitOCR→None, luego BM→None'
            elif final != ocr_val and ocr_val is not None:
                tech = 'DigitOCR→SlidingNR'
            elif final is None and bm_val is not None:
                tech = 'BinaryMatcher'
            print(f'  {player}_stake: {final}  [DigitOCR={ocr_val}  BM={bm_val}  SlidingNR={sr_val}]')

    print(f'\n  == States (StateMatcher) ==')
    for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
        st = sr.sm.read(pil, player)
        print(f'  {player}_state: {state.get(f"{player}_state")}  [SM={st}]')

    print(f'\n  == Bets (DigitOCR pool=digits, fallback BinaryMatcher) ==')
    for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
        roi = sr.BET_ROIS.get(player)
        if roi:
            gc = gray_img[roi[1]:roi[3], roi[0]:roi[2]]
            ocr_val = sr.ocr.read(gc, pool='digits')
            bm_val = sr.bm.read_region(gc, ('bet',), ocr=sr.ocr)
            final = state.get(f'{player}_bet')
            # Determine which tech produced the final value
            if player == 'p3' and final is not None:
                if bm_val is not None and abs(float(final) - bm_val) < 0.01:
                    tech = 'BinaryMatcher (primary)'
                elif ocr_val is not None and abs(float(final) - ocr_val) < 0.01:
                    tech = 'DigitOCR (fallback on masked crop)'
                else:
                    tech = 'BinaryMatcher'
            elif ocr_val is not None:
                tech = 'DigitOCR'
            elif bm_val is not None and bm_val != ocr_val:
                tech = 'BinaryMatcher (OCR fallback)'
            else:
                tech = 'BinaryMatcher'
            print(f'  {player}_bet: {final}  [DigitOCR={ocr_val}  BM={bm_val}]  ROI_SIZE={roi[2]-roi[0]}x{roi[3]-roi[1]}  tech={tech}')

    # 1b. Resumen compacto
    print(f'\n  == Resumen ==')
    for k, v in sorted(state.items()):
        if k.endswith('_state') or k.endswith('_stake') or k.endswith('_bet') or k in ('pot', 'btn'):
            print(f'  {k}: {v}')

    # 2. Card reader
    print(f'\n--- CardReader ---')
    cards = CARD_READER.read_all(img)
    print(f'  hero: {cards.get("hero")}')
    com = cards.get('community', [])
    for i, c in enumerate(com):
        r = c.get('rank') if isinstance(c, dict) else None
        s = c.get('suit') if isinstance(c, dict) else None
        print(f'  community[{i}]: rank={r} suit={s}')

    # 3. Number reader (OCR)
    print(f'\n--- OcrRapido ---')
    nr = OcrRapido()
    nr.train()
    pot = nr.read_pot(pil)
    print(f'  pot: {pot}')
    for p in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
        stack = nr.read_stack(pil, p)
        if stack is not None:
            print(f'  stack_{p}: {stack}')

if __name__ == '__main__':
    main()
