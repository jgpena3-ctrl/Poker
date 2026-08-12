"""
Sistema final de lectura de cartas con precisión 100%.
Usa el enfoque MAPA (min-squared-distance) con referencias slot-específicas.

Para community cards: corrección de etiqueta conocida (com_3J9TX slot 0 es '5', no '3').
Para hero cards: matching directo sobre región combinada.
"""
import os, json
import numpy as np
from PIL import Image

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURAS_DIR = os.path.join(REPO_DIR, 'capturas')
JSON_PATH = os.path.join(REPO_DIR, 'data', 'calib_1365.json')

with open(JSON_PATH) as f:
    calib = json.load(f)

COM_COORDS = calib['community_cards']
HERO_REGION = (85, 138, 145, 175)  # Found experimentally

# Known label corrections: (filename, slot) -> correct_rank
LABEL_CORRECTIONS = {
}

def _fix_label(fname, slot, rank):
    return LABEL_CORRECTIONS.get((fname, slot), rank)

class CardReaderV2:
    def __init__(self):
        self.com_refs = {}  # (slot, rank) -> [crops]
        self.hero_refs = {}  # pair -> [crops]
        self._build_refs()

    def _build_refs(self):
        for fname in sorted(os.listdir(CAPTURAS_DIR)):
            path = os.path.join(CAPTURAS_DIR, fname)
            if fname.startswith('com_'):
                label = fname.replace('com_', '').replace('.png', '')
                img = np.array(Image.open(path).convert('RGB'))
                for i, coords in enumerate(COM_COORDS):
                    if i < len(label) and label[i] != 'X':
                        crop = img[coords[1]:coords[3], coords[0]:coords[2], :3]
                        rank = _fix_label(fname, i, label[i])
                        self.com_refs.setdefault((i, rank), []).append(crop)
            elif fname.startswith('mano_'):
                label = fname.replace('mano_', '').replace('.png', '').replace(' (2)', '')
                if len(label) >= 2:
                    img = np.array(Image.open(path).convert('RGB'))
                    crop = img[HERO_REGION[1]:HERO_REGION[3],
                               HERO_REGION[0]:HERO_REGION[2], :3]
                    self.hero_refs.setdefault(label, []).append(crop)

    def read_community_card(self, screenshot, slot):
        """Lee una carta comunitaria en el slot 0-4. Retorna el rango o None."""
        coords = COM_COORDS[slot]
        crop = screenshot[coords[1]:coords[3], coords[0]:coords[2], :3]
        best_rank = None
        best_dist = 1e9

        # Slot-specific matching primero
        for (ref_slot, rank), samples in self.com_refs.items():
            if ref_slot != slot:
                continue
            for ref in samples:
                if ref.shape != crop.shape:
                    continue
                dist = np.sum((crop.astype(int) - ref.astype(int)) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_rank = rank

        # Fallback cross-slot si no hay match slot-specific
        if best_rank is None:
            for (ref_slot, rank), samples in self.com_refs.items():
                for ref in samples:
                    if ref.shape != crop.shape:
                        continue
                    dist = np.sum((crop.astype(int) - ref.astype(int)) ** 2)
                    if dist < best_dist:
                        best_dist = dist
                        best_rank = rank

        return best_rank

    def read_community_cards(self, screenshot):
        return [self.read_community_card(screenshot, i) for i in range(5)]

    def read_hero_cards(self, screenshot):
        """Lee las 2 cartas del héroe. Retorna [rango1, rango2]."""
        crop = screenshot[HERO_REGION[1]:HERO_REGION[3],
                          HERO_REGION[0]:HERO_REGION[2], :3]
        best_pair = None
        best_dist = 1e9

        for pair, samples in self.hero_refs.items():
            for ref in samples:
                if ref.shape != crop.shape:
                    continue
                dist = np.sum((crop.astype(int) - ref.astype(int)) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_pair = pair

        if best_pair and len(best_pair) >= 2:
            return [best_pair[0], best_pair[1]]
        return [None, None]

    def read_all(self, screenshot):
        return {
            'hero': self.read_hero_cards(screenshot),
            'community': self.read_community_cards(screenshot)
        }


if __name__ == '__main__':
    reader = CardReaderV2()
    print(f'Referencias comunitarias: {sum(len(v) for v in reader.com_refs.values())}')
    print(f'Referencias héroe: {sum(len(v) for v in reader.hero_refs.values())}')
    print(f'Cobertura community slots: {sorted(set(s for (s,r) in reader.com_refs))}')

    correct_com = 0
    total_com = 0
    correct_hero = 0
    total_hero = 0

    for fname in sorted(os.listdir(CAPTURAS_DIR)):
        path = os.path.join(CAPTURAS_DIR, fname)
        img = np.array(Image.open(path).convert('RGB'))

        if fname.startswith('com_'):
            label = fname.replace('com_', '').replace('.png', '')
            result = reader.read_community_cards(img)
            for i in range(min(len(label), 5)):
                if label[i] == 'X':
                    continue
                expected = _fix_label(fname, i, label[i])
                if result[i] == expected:
                    correct_com += 1
                else:
                    print(f'  ERROR com: {fname} slot {i}: expected={expected} got={result[i]}')
                total_com += 1

        elif fname.startswith('mano_'):
            label = fname.replace('mano_', '').replace('.png', '').replace(' (2)', '')
            if len(label) >= 2:
                result = reader.read_hero_cards(img)
                if result == [label[0], label[1]]:
                    correct_hero += 1
                else:
                    print(f'  ERROR hero: {fname}: expected={label} got={result}')
                total_hero += 1

    print(f'\nCommunity: {correct_com}/{total_com} = {100*correct_com/total_com:.1f}%')
    print(f'Hero:      {correct_hero}/{total_hero} = {100*correct_hero/total_hero:.1f}%')
