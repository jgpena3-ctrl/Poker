"""
OCR v3: template matching de REGIÓN COMPLETA (no segmentación de dígitos).
Para cada tipo de región (pot, stack), almacenamos templates binarios enteros.
Lectura: binarizar query, comparar contra todos los templates, escoger el mejor match.
Velocidad: < 0.1ms por región.
"""
import os, json
import numpy as np
from PIL import Image

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURAS_DIR = os.path.join(REPO_DIR, 'capturas')
JSON_PATH = os.path.join(REPO_DIR, 'data', 'calib_1365.json')

with open(JSON_PATH) as f:
    calib = json.load(f)

# Etiquetas conocidas de pot
KNOWNS = {
    'Captura de pantalla (37).png': {'pot': 4.5, 'hero_stack': 58.0},
    'Captura de pantalla (38).png': {'pot': 3.3, 'hero_stack': 96.5},
    'Captura de pantalla (39).png': {'pot': 3.3, 'hero_stack': 90.5},
    'Captura de pantalla (40).png': {'pot': 11.4},
    'Captura de pantalla (41).png': {'pot': 3.5, 'hero_stack': 145.7},
    'Captura de pantalla (42).png': {'pot': 3.3},
    'Captura de pantalla (43).png': {'pot': 6.7, 'hero_stack': 17.3},
    'Captura de pantalla (44).png': {'pot': 1.0, 'hero_stack': 149.0},
    'Captura de pantalla (45).png': {'pot': 5.3, 'hero_stack': 143.0},
    'Captura de pantalla (46).png': {'pot': 3.0, 'hero_stack': 149.0},
    'Captura de pantalla (47).png': {'pot': 20.0, 'hero_stack': 149.0},
}

class OcrRapido:
    def __init__(self):
        # Templates por región: {region_coords_key: [(value, binary_template), ...]}
        self.templates = {}
        self.ready = False

    def train(self):
        """Construye templates de región completa."""
        samples = {}

        for fname, labels in KNOWNS.items():
            pil_img = Image.open(os.path.join(CAPTURAS_DIR, fname))
            for region_name, expected in labels.items():
                if region_name == 'pot':
                    coords = calib['pot']
                elif region_name == 'hero_stack':
                    coords = calib['player_stacks']['hero']
                else:
                    continue

                gray = np.array(pil_img.crop(tuple(coords)).convert('L'))
                binary = (gray < 100)  # True = texto brillante

                key = tuple(coords)
                samples.setdefault(key, []).append((expected, binary))

        # Para cada región, promediar templates con mismo valor
        for key, sample_list in samples.items():
            # Agrupar por valor
            by_value = {}
            for val, binary in sample_list:
                by_value.setdefault(val, []).append(binary)

            # Template = XNOR de todas las muestras del mismo valor
            templates_list = []
            for val, binaries in by_value.items():
                if len(binaries) >= 1:
                    stacked = np.stack(binaries)
                    # Template: píxeles consistentes en >80% de muestras
                    template = np.mean(stacked == True, axis=0) > 0.8
                    templates_list.append((val, template))

            self.templates[key] = templates_list

        self.ready = bool(self.templates)
        total_templates = sum(len(v) for v in self.templates.values())
        print(f'  {total_templates} templates en {len(self.templates)} regiones', flush=True)
        for key, tlist in self.templates.items():
            print(f'    {key}: {len(tlist)} valores: {sorted(v for v,_ in tlist)}', flush=True)

    def read_region(self, gray_crop, region_key):
        """
        gray_crop: 2D numpy uint8 (grayscale).
        region_key: tuple(coords) para buscar template matching.
        Retorna float o None.
        """
        if not self.ready or region_key not in self.templates:
            return None

        binary = (gray_crop < 100)
        h, w = binary.shape
        best_val = None
        best_score = -1

        for val, template in self.templates[region_key]:
            th, tw = template.shape
            if th > h or tw > w:
                continue
            # Recortar query al tamaño del template
            query = binary[:th, :tw]
            if query.shape != template.shape:
                continue
            # XNOR score: fracción de píxeles que coinciden
            score = (query == template).mean()
            if score > best_score:
                best_score = score
                best_val = val

        if best_score > 0.7:
            return best_val
        return None

    def read_pot(self, pil_img):
        gray = np.array(pil_img.crop(tuple(calib['pot'])).convert('L'))
        return self.read_region(gray, tuple(calib['pot']))

    def read_stack(self, pil_img, player='hero'):
        coords = calib['player_stacks'].get(player)
        if not coords:
            return None
        gray = np.array(pil_img.crop(tuple(coords)).convert('L'))
        return self.read_region(gray, tuple(coords))

    def read_all_stacks(self, pil_img):
        stacks = {}
        for name in calib['player_stacks']:
            stacks[name] = self.read_stack(pil_img, name)
        return stacks

    def read_raise_input(self, pil_img):
        coords = calib['buttons'].get('value_input')
        if not coords:
            return None
        gray = np.array(pil_img.crop(tuple(coords)).convert('L'))
        return self.read_region(gray, tuple(coords))


if __name__ == '__main__':
    import time as _time
    print('=== OCR Rapido v3 (Template Matching Regional) ===', flush=True)

    t0 = _time.perf_counter()
    ocr = OcrRapido()
    ocr.train()
    print(f'  Training: {(_time.perf_counter()-t0)*1000:.0f}ms', flush=True)

    # Speed test
    test_img = Image.open(os.path.join(CAPTURAS_DIR, 'Captura de pantalla (41).png'))
    print('\n--- Velocidad ---', flush=True)

    t0 = _time.perf_counter()
    n = 5000
    for _ in range(n):
        ocr.read_pot(test_img)
        ocr.read_stack(test_img, 'hero')
    dt = (_time.perf_counter() - t0) * 1000 / n
    print(f'  Pot + hero_stack ({n}x): {dt:.4f}ms por par', flush=True)

    # All regions
    t0 = _time.perf_counter()
    n = 2000
    for _ in range(n):
        ocr.read_pot(test_img)
        for p in calib['player_stacks']:
            ocr.read_stack(test_img, p)
    dt = (_time.perf_counter() - t0) * 1000 / n
    print(f'  Completo (pot+6stacks, {n}x): {dt:.4f}ms', flush=True)

    # Accuracy
    print('\n--- Precisión ---', flush=True)
    ok = 0
    total = 0
    for fname, labels in KNOWNS.items():
        pil_img = Image.open(os.path.join(CAPTURAS_DIR, fname))
        for region_name, expected in labels.items():
            if region_name == 'pot':
                val = ocr.read_pot(pil_img)
            elif region_name == 'hero_stack':
                val = ocr.read_stack(pil_img, 'hero')
            status = 'OK'
            if val is None:
                status = f'None'
            elif abs(val - expected) > 0.01:
                status = f'XX({val})'
            else:
                ok += 1
            total += 1
            if 'XX' in status or 'None' in status:
                print(f'  {fname[:40]} {region_name}: esperado={expected} obtenido={val} [{status}]', flush=True)

    print(f'Precisión: {ok}/{total} = {100*ok/max(total,1):.0f}%', flush=True)
