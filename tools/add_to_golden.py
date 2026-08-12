import os, sys, json
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lector_estado import CAPTURAS_DIR, GOLDEN, GOLDEN_PATH, calib
from digit_ocr import DigitOCR


def predict_all(ocr, gray, calib):
    fields = {
        'pot': (tuple(calib['pot']), 'digits'),
        'hero_stake': (tuple(calib['player_stacks']['hero']), 'stacks'),
        'p1_stake': (tuple(calib['player_stacks']['p1']), 'stacks'),
        'p2_stake': (tuple(calib['player_stacks']['p2']), 'stacks'),
        'p3_stake': (tuple(calib['player_stacks']['p3']), 'stacks'),
        'p4_stake': (tuple(calib['player_stacks']['p4']), 'stacks'),
        'p5_stake': (tuple(calib['player_stacks']['p5']), 'stacks'),
    }
    results = {}
    for name, ((x1, y1, x2, y2), pool) in fields.items():
        crop = gray[y1:y2, x1:x2]
        pred = ocr.read(crop, pool=pool)
        if pred is not None:
            results[name] = round(pred, 2)
        else:
            results[name] = None
    return results


def main():
    if len(sys.argv) < 2:
        print("Uso: python add_to_golden.py <captura_o_numero>")
        print("Ej:  python add_to_golden.py 63")
        print("     python add_to_golden.py \"Captura de pantalla (63).png\"")
        sys.exit(1)

    raw = sys.argv[1]
    if raw.endswith('.png'):
        fname = raw
    else:
        fname = f'Captura de pantalla ({raw}).png'

    path = os.path.join(CAPTURAS_DIR, fname)
    if not os.path.exists(path):
        print(f"Error: no existe {path}")
        sys.exit(1)

    print(f"Leyendo {fname} ...")
    gray = np.array(Image.open(path).convert('L'))

    print("Cargando OCR ...")
    ocr = DigitOCR(load_templates=True)
    if not ocr._trained:
        print("OCRL: no hay templates entrenados. Ejecutá train_cyclic() primero.")
        sys.exit(1)

    results = predict_all(ocr, gray, calib)

    print("\nPredicciones:")
    for name, val in results.items():
        print(f"  {name:15s} = {val}")

    # Update golden.json
    if fname not in GOLDEN:
        GOLDEN[fname] = {}
        print(f"\n  -> Nueva entrada en golden.json")

    entry = GOLDEN[fname]
    for name, val in results.items():
        entry[name] = val

    # Preserve existing non-numeric fields
    with open(GOLDEN_PATH, 'w') as f:
        json.dump(GOLDEN, f, indent=2)
    print(f"\n  golden.json actualizado.")


if __name__ == '__main__':
    main()
