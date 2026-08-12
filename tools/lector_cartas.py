import os
import json
import numpy as np
from PIL import Image
import cv2

INFO_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURAS_DIR = os.path.join(INFO_DIR, 'capturas')
JSON_PATH = os.path.join(INFO_DIR, 'calib_1365.json')

with open(JSON_PATH) as f:
    calib = json.load(f)

class CardReader:
    def __init__(self):
        self.community_coords = calib['community_cards']
        self.hero_coords = calib['hero_cards']

        self.community_templates = {}  # (slot, rank) -> gradient mag template
        self.hero_pair_templates = {}  # pair_label -> hero region template
        self.rank_templates_list = []  # [(rank, template), ...] for fallback
        self.hero_region = (85, 138, 145, 175)

        self._build_templates()

    def _build_templates(self):
        # Build community card templates (gradient magnitude per slot)
        com_data = {}
        for fname in os.listdir(CAPTURAS_DIR):
            if fname.startswith('com_'):
                label = fname.replace('com_', '').replace('.png', '')
                img = np.array(Image.open(os.path.join(CAPTURAS_DIR, fname)))
                for i, coords in enumerate(self.community_coords):
                    if i < len(label) and label[i] != 'X':
                        crop = img[coords[1]:coords[3], coords[0]:coords[2], :3]
                        com_data.setdefault((i, label[i]), []).append(crop)

        for (slot, rank), samples in com_data.items():
            grad_samples = []
            for s in samples:
                gray = cv2.cvtColor(s, cv2.COLOR_RGB2GRAY)
                sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
                sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
                mag = np.sqrt(sobelx**2 + sobely**2).astype(np.uint8)
                grad_samples.append(mag)
            template = np.mean(grad_samples, axis=0).astype(np.uint8)
            self.community_templates[(slot, rank)] = template

        # Build hero pair templates
        hero_data = {}
        for fname in os.listdir(CAPTURAS_DIR):
            if fname.startswith('mano_'):
                label = fname.replace('mano_', '').replace('.png', '').replace(' (2)', '')
                if len(label) >= 2:
                    img = np.array(Image.open(os.path.join(CAPTURAS_DIR, fname)))
                    crop = img[self.hero_region[1]:self.hero_region[3],
                               self.hero_region[0]:self.hero_region[2], :3]
                    hero_data.setdefault(label, []).append(crop)

        for pair, samples in hero_data.items():
            self.hero_pair_templates[pair] = np.mean(samples, axis=0).astype(np.uint8)

        # Build generic rank templates list (for fallback)
        seen = set()
        for (slot, rank), template in self.community_templates.items():
            if rank not in seen:
                self.rank_templates_list.append((rank, template))
                seen.add(rank)

    def read_community_cards(self, screenshot):
        cards = []
        for i, coords in enumerate(self.community_coords):
            crop = screenshot[coords[1]:coords[3], coords[0]:coords[2], :3]
            gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            query = np.sqrt(sobelx**2 + sobely**2).astype(np.uint8)

            best_rank = None
            best_score = -1

            # Try per-slot templates
            for (slot, rank), template in self.community_templates.items():
                if slot == i and query.shape == template.shape:
                    result = cv2.matchTemplate(query, template, cv2.TM_CCOEFF_NORMED)
                    score = result[0, 0]
                    if score > best_score and score > 0.5:
                        best_score = score
                        best_rank = rank

            # Fallback: try generic templates from other slots
            if best_rank is None:
                for rank, template in self.rank_templates_list:
                    if query.shape == template.shape:
                        result = cv2.matchTemplate(query, template, cv2.TM_CCOEFF_NORMED)
                        score = result[0, 0]
                        if score > best_score and score > 0.35:
                            best_score = score
                            best_rank = rank

            cards.append(best_rank)
        return cards

    def read_hero_cards(self, screenshot):
        crop = screenshot[self.hero_region[1]:self.hero_region[3],
                          self.hero_region[0]:self.hero_region[2], :3]

        # Pair matching - find best match across all templates
        best_pair = None
        best_score = -1
        for pair, template in self.hero_pair_templates.items():
            th, tw = template.shape[:2]
            ch, cw = crop.shape[:2]
            if th <= ch and tw <= cw:
                result = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                if max_val > best_score:
                    best_score = max_val
                    best_pair = pair
        if best_pair and best_score > 0.6 and len(best_pair) >= 2:
            return [best_pair[0], best_pair[1]]

        # Fallback: match individual ranks
        found = [None, None]
        for rank, template in self.rank_templates_list:
            th, tw = template.shape[:2]
            ch, cw = crop.shape[:2]
            if th > ch or tw > cw:
                continue
            result = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > 0.4:
                mid_x = cw // 2
                slot = 0 if max_loc[0] + tw // 2 < mid_x else 1
                if found[slot] is None or max_val > found[slot][1]:
                    found[slot] = (rank, max_val)
        return [f[0] if f else None for f in found]

    def read_all(self, screenshot):
        return {
            'hero': self.read_hero_cards(screenshot),
            'community': self.read_community_cards(screenshot)
        }

if __name__ == '__main__':
    reader = CardReader()
    print("CardReader initialized successfully")
    print(f"  Community templates: {len(reader.community_templates)}")
    print(f"  Hero pair templates: {len(reader.hero_pair_templates)}")
    print(f"  Generic rank templates: {len(reader.rank_templates_list)}")

    for fname in sorted(os.listdir(CAPTURAS_DIR)):
        if fname.startswith('com_') or fname.startswith('mano_'):
            label = fname.replace('com_', '').replace('mano_', '').replace('.png', '').replace(' (2)', '')
            img = np.array(Image.open(os.path.join(CAPTURAS_DIR, fname)))
            result = reader.read_all(img)
            if fname.startswith('mano_'):
                status = 'OK' if result['hero'] == [label[0], label[1]] else 'XX'
                print(f"  [{status}] {fname:25s} hero={result['hero']} (expected={label})")
            else:
                correct = sum(1 for a, b in zip(result['community'], label) if a == b and b != 'X')
                total = sum(1 for c in label if c != 'X')
                status = f'{correct}/{total}'
                print(f"  [{status}] {fname:20s} community={result['community']} (expected={label})")
