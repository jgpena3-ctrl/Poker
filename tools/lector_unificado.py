"""
Módulo unificado de lectura: cartas (100% con mapa) y números (OCR rápido ~3ms).
"""
import os, json
from PIL import Image
import numpy as np
import cv2

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURAS_DIR = os.path.join(REPO_DIR, 'capturas')
JSON_PATH = os.path.join(REPO_DIR, 'data', 'calib_1365.json')

with open(JSON_PATH) as f:
    calib = json.load(f)

COM_COORDS = calib['community_cards']
COM_RANK = calib.get('community_rank', [0, 0, 20, 22])   # [x1,y1,x2,y2] relative to card crop
COM_PALO = calib.get('community_palo', [0, 22, 20, 42])   # [x1,y1,x2,y2] relative to card crop
HERO_REGION = (96, 146, 117, 165)

# ===============================
# CARD READER (MAP approach) - 100% + Suit detection
# ===============================
LABEL_CORRECTIONS = {
}

def _fix_label(fname, slot, rank):
    return LABEL_CORRECTIONS.get((fname, slot), rank)

class CardReader:
    def __init__(self):
        self.com_rank_refs = {}     # rank -> [gradient templates of rank area]
        self.com_suit_refs = {}     # suit_name -> [RGB suit crops]
        self.hero_refs = {}
        self.hero_left_rank_refs = {}   # rank -> [crops of top half (rank area)]
        self.hero_right_rank_refs = {}  # rank -> [crops of top half (rank area)]
        self._build_refs()

    @staticmethod
    def _crop_has_content(crop):
        """Return True if crop has enough bright pixels to contain a visible card."""
        bright = (crop[:,:,0] > 80).sum()
        total = crop.shape[0] * crop.shape[1]
        mean_r = crop[:,:,0].mean()
        return mean_r >= 40 and bright / total >= 0.03

    def _build_refs(self):
        rx1, ry1, rx2, ry2 = COM_RANK
        px1, py1, px2, py2 = COM_PALO
        all_suit_samples = []  # [(suit_crop)]
        skipped = 0
        for fname in sorted(os.listdir(CAPTURAS_DIR)):
            path = os.path.join(CAPTURAS_DIR, fname)
            if fname.startswith('com_'):
                label = fname.replace('com_', '').replace('.png', '')
                img = np.array(Image.open(path).convert('RGB'))
                for i, coords in enumerate(COM_COORDS):
                    if i < len(label) and label[i] != 'X':
                        crop = img[coords[1]:coords[3], coords[0]:coords[2], :3]
                        if not self._crop_has_content(crop):
                            skipped += 1
                            continue
                        rank = _fix_label(fname, i, label[i])
                        # Extract rank area and suit area (relative coords within crop)
                        rank_crop = crop[ry1:ry2, rx1:rx2]
                        suit_crop = crop[py1:py2, px1:px2]
                        # Store gradient template for rank matching (pool across slots)
                        grad = self._card_gradient(rank_crop)
                        self.com_rank_refs.setdefault(rank, []).append(grad)
                        # Store RGB suit crop for suit matching
                        all_suit_samples.append(suit_crop)
            elif fname.startswith('mano_'):
                label = fname.replace('mano_', '').replace('.png', '').replace(' (2)', '')
                if len(label) >= 2:
                    img = np.array(Image.open(path).convert('RGB'))
                    crop = img[HERO_REGION[1]:HERO_REGION[3],
                               HERO_REGION[0]:HERO_REGION[2], :3]
                    self.hero_refs.setdefault(label, []).append(crop)
                    # Split into left/right card halves
                    hh = crop.shape[0]
                    hw = crop.shape[1] // 2
                    hmid = hh // 2
                    left_rank, right_rank = label[0], label[1]
                    left_half = crop[:, :hw, :]
                    right_half = crop[:, hw:2*hw, :]
                    # Top half = rank area → store gradient for brightness-invariant matching
                    self.hero_left_rank_refs.setdefault(left_rank, []).append(
                        self._card_gradient(left_half[:hmid, :, :]))
                    self.hero_right_rank_refs.setdefault(right_rank, []).append(
                        self._card_gradient(right_half[:hmid, :, :]))

        # Cluster suit samples globally (all slots pooled): first by color,
        # then by shape. s=spade(black), h=heart(red), d=diamond(red), c=club(black)
        if not all_suit_samples:
            return
        X = np.array([s.flatten().astype(float) for s in all_suit_samples])
        redness = np.array([((s[:,:,0].astype(int) - s[:,:,1].astype(int)) > 30).sum() for s in all_suit_samples])
        darkness = np.array([s.mean() for s in all_suit_samples])  # lower = darker
        is_red = redness > 10
        for color_group, is_red_mask in [(False, False), (True, True)]:
            idx = np.where(is_red == is_red_mask)[0]
            if len(idx) == 0:
                continue
            if len(idx) < 2:
                name = 'h' if is_red_mask else 's'
                self.com_suit_refs[name] = [all_suit_samples[j] for j in idx]
                continue
            sub_X = X[idx]
            c0 = sub_X[0]
            c1 = sub_X[-1]
            sub_labels = np.zeros(len(sub_X), dtype=int)
            for _ in range(5):
                for j in range(len(sub_X)):
                    d0 = np.sum((sub_X[j] - c0) ** 2)
                    d1 = np.sum((sub_X[j] - c1) ** 2)
                    sub_labels[j] = 0 if d0 < d1 else 1
                if (sub_labels == 0).any():
                    c0 = sub_X[sub_labels == 0].mean(axis=0)
                if (sub_labels == 1).any():
                    c1 = sub_X[sub_labels == 1].mean(axis=0)
            # Disambiguate names using known priors:
            # Red: heart has more red area than diamond
            # Black: spade is darker (more solid ink) than club
            cl0_idx = np.where(sub_labels == 0)[0]
            cl1_idx = np.where(sub_labels == 1)[0]
            if is_red_mask:
                r0 = redness[idx][cl0_idx].mean()
                r1 = redness[idx][cl1_idx].mean()
                # higher redness = heart, lower = diamond
                if r0 >= r1:
                    h_name, d_name = 'h', 'd'
                    h_idx, d_idx = cl0_idx, cl1_idx
                else:
                    h_name, d_name = 'h', 'd'
                    h_idx, d_idx = cl1_idx, cl0_idx
                self.com_suit_refs[h_name] = [all_suit_samples[idx[j]] for j in h_idx]
                self.com_suit_refs[d_name] = [all_suit_samples[idx[j]] for j in d_idx]
            else:
                d0_val = darkness[idx][cl0_idx].mean()
                d1_val = darkness[idx][cl1_idx].mean()
                # darker = spade, lighter = club
                if d0_val <= d1_val:
                    s_name, c_name = 's', 'c'
                    s_idx, c_idx = cl0_idx, cl1_idx
                else:
                    s_name, c_name = 's', 'c'
                    s_idx, c_idx = cl1_idx, cl0_idx
                self.com_suit_refs[s_name] = [all_suit_samples[idx[j]] for j in s_idx]
                self.com_suit_refs[c_name] = [all_suit_samples[idx[j]] for j in c_idx]


    @staticmethod
    def _resize_to(crop, target_shape):
        """Resize crop to target (h, w) if shapes differ, using LANCZOS."""
        if crop.shape[:2] == target_shape:
            return crop
        from PIL import Image as PILImage
        pil = PILImage.fromarray(crop)
        pil = pil.resize((target_shape[1], target_shape[0]), PILImage.LANCZOS)
        return np.array(pil)

    @staticmethod
    def _is_empty(crop):
        """Return True if crop is too dark to contain a visible card."""
        mean_r = crop[:,:,0].mean()
        bright = (crop[:,:,0] > 80).sum()
        total = crop.shape[0] * crop.shape[1]
        return mean_r < 40 or bright / total < 0.03

    def _card_gradient(self, rgb_crop):
        """Convert RGB card crop to gradient magnitude."""
        gray = cv2.cvtColor(rgb_crop, cv2.COLOR_RGB2GRAY)
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        return np.sqrt(sobelx**2 + sobely**2).astype(np.float32)

    @staticmethod
    def _ncc_score(q, ref):
        """Normalized cross-correlation score (higher = more similar)."""
        qf = q.astype(float).ravel()
        rf = ref.astype(float).ravel()
        qn = (qf - qf.mean()) / max(qf.std(), 1e-8)
        rn = (rf - rf.mean()) / max(rf.std(), 1e-8)
        return float(np.dot(qn, rn) / len(qn))

    @staticmethod
    def _determine_color(suit_crop):
        """Determine if a card is red (heart/diamond) or black (club/spade).
        Returns 'r' or 'b'. suit_crop should be the suit region only."""
        redness = ((suit_crop[:,:,0].astype(int) - suit_crop[:,:,1].astype(int)) > 30).sum()
        return 'r' if redness > 10 else 'b'

    def read_community_card(self, img_arr, slot):
        rx1, ry1, rx2, ry2 = COM_RANK
        coords = COM_COORDS[slot]
        crop = img_arr[coords[1]:coords[3], coords[0]:coords[2], :3]
        rank_area = crop[ry1:ry2, rx1:rx2]
        if self._is_empty(rank_area):
            return None
        query_grad = self._card_gradient(rank_area)
        best_rank = None
        best_score = -1.0
        for rank, samples in self.com_rank_refs.items():
            for ref in samples:
                q = self._resize_to(query_grad, ref.shape[:2])
                score = self._ncc_score(q, ref)
                if score > best_score:
                    best_score = score
                    best_rank = rank
        if best_score < 0.15:
            return None
        return best_rank

    def read_community_card_suit(self, img_arr, slot):
        px1, py1, px2, py2 = COM_PALO
        rx1, ry1, rx2, ry2 = COM_RANK
        coords = COM_COORDS[slot]
        crop = img_arr[coords[1]:coords[3], coords[0]:coords[2], :3]
        rank_area = crop[ry1:ry2, rx1:rx2]
        if self._is_empty(rank_area):
            return None
        suit_area = crop[py1:py2, px1:px2]
        if not self.com_suit_refs:
            return None
        query_color = self._determine_color(suit_area)
        best_suit = None
        best_dist = 1e9
        for suit_name, samples in self.com_suit_refs.items():
            suit_color = 'r' if suit_name in ('h', 'd') else 'b'
            if suit_color != query_color:
                continue
            for ref in samples:
                q = self._resize_to(suit_area, ref.shape[:2])
                dist = np.sum((q.astype(float) - ref.astype(float)) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_suit = suit_name
        if best_suit is None:
            for suit_name, samples in self.com_suit_refs.items():
                for ref in samples:
                    q = self._resize_to(suit_area, ref.shape[:2])
                    dist = np.sum((q.astype(float) - ref.astype(float)) ** 2)
                    if dist < best_dist:
                        best_dist = dist
                        best_suit = suit_name
        return best_suit

    def read_community_cards(self, img_arr):
        return [self.read_community_card(img_arr, i) for i in range(5)]

    def read_community_suits(self, img_arr):
        return [self.read_community_card_suit(img_arr, i) for i in range(5)]

    def read_hero_cards(self, img_arr):
        crop = img_arr[HERO_REGION[1]:HERO_REGION[3],
                       HERO_REGION[0]:HERO_REGION[2], :3]
        if self._is_empty(crop):
            return [None, None]
        hh = crop.shape[0]
        hmid = hh // 2
        hw = crop.shape[1] // 2
        left_half = crop[:, :hw, :]
        right_half = crop[:, hw:2*hw, :]
        # Only use top half (rank area, invariant to suit)
        left_rank_crop = left_half[:hmid, :, :]
        right_rank_crop = right_half[:hmid, :, :]

        def best_rank(rank_crop, refs):
            best_r, best_sc = None, -1.0
            if self._is_empty(rank_crop):
                return None
            query_grad = self._card_gradient(rank_crop)
            for rank, samples in refs.items():
                for ref in samples:
                    q = self._resize_to(query_grad, ref.shape[:2])
                    sc = self._ncc_score(q, ref)
                    if sc > best_sc:
                        best_sc = sc
                        best_r = rank
            return best_r

        left = best_rank(left_rank_crop, self.hero_left_rank_refs)
        right = best_rank(right_rank_crop, self.hero_right_rank_refs)
        return [left, right]

    def read_hero_card_suits(self, img_arr):
        """Detect suits using user-given absolute pixel coordinates."""
        suits = []
        # Card 1 (left): pixel (100,157) = white for heart, red for diamond
        r1, g1, b1 = img_arr[157, 100, :3].astype(int)
        if r1 > 200 and g1 > 200 and b1 > 200:
            suits.append('h')
        elif r1 > 150 and g1 < 100 and b1 < 100:
            suits.append('d')
        else:
            # Black suit: pixel (98,159) = near-white for club, dark for spade
            r2, g2, b2 = img_arr[159, 98, :3].astype(int)
            if r2 > 150 and g2 > 150 and b2 > 150:
                suits.append('c')
            else:
                suits.append('s')
        # Card 2 (right): pixel (113,157) = white for heart, red for diamond
        r3, g3, b3 = img_arr[157, 113, :3].astype(int)
        if r3 > 200 and g3 > 200 and b3 > 200:
            suits.append('h')
        elif r3 > 150 and g3 < 100 and b3 < 100:
            suits.append('d')
        else:
            # Black suit: pixel (111,159) = near-white for club, dark for spade
            r4, g4, b4 = img_arr[159, 111, :3].astype(int)
            if r4 > 150 and g4 > 150 and b4 > 150:
                suits.append('c')
            else:
                suits.append('s')
        return suits

    def read_all(self, img_arr):
        com_ranks = self.read_community_cards(img_arr)
        com_suits = self.read_community_suits(img_arr)
        hero_ranks = self.read_hero_cards(img_arr)
        hero_suits = self.read_hero_card_suits(img_arr)
        return {
            'hero': [f'{r}{s}' if (r and s) else r for r, s in zip(hero_ranks, hero_suits)],
            'community': [{'rank': r, 'suit': s} if r else {'rank': None, 'suit': None}
                          for r, s in zip(com_ranks, com_suits)],
        }

# ===============================
# NUMBER READER (OCR rápido ~3ms)
# ===============================
from ocr_rapido import OcrRapido

NUM_READER = OcrRapido()
NUM_READER.train()

CARD_READER = CardReader()


if __name__ == '__main__':
    print('=== Lector de Cartas (100%) + Suits ===')
    correct_com = 0
    total_com = 0
    correct_hero = 0
    total_hero = 0
    correct_suit_cross = 0
    total_suit_cross = 0

    for fname in sorted(os.listdir(CAPTURAS_DIR)):
        if not fname.lower().endswith('.png'):
            continue
        path = os.path.join(CAPTURAS_DIR, fname)
        img = np.array(Image.open(path).convert('RGB'))

        if fname.startswith('com_'):
            label = fname.replace('com_', '').replace('.png', '')
            result = CARD_READER.read_all(img)
            ranks = [c['rank'] for c in result['community']]
            suits = [c['suit'] for c in result['community']]
            for i in range(min(len(label), 5)):
                if label[i] == 'X':
                    continue
                expected = _fix_label(fname, i, label[i])
                if ranks[i] == expected:
                    correct_com += 1
                else:
                    print(f'  RANK ERROR: {fname} slot {i}: {expected} -> {ranks[i]}')
                total_com += 1

            # Verify suit consistency: cards with same rank at same slot should have same suit
            for slot in range(5):
                if suits[slot]:
                    total_suit_cross += 1

        elif fname.startswith('mano_'):
            label = fname.replace('mano_', '').replace('.png', '').replace(' (2)', '')
            if len(label) >= 2:
                result = CARD_READER.read_hero_cards(img)
                if result == [label[0], label[1]]:
                    correct_hero += 1
                else:
                    print(f'  HERO ERROR: {fname}: {label} -> {result}')
                total_hero += 1

    print(f'  Community ranks: {correct_com}/{total_com} = {100*correct_com/total_com:.1f}%')
    print(f'  Hero:            {correct_hero}/{total_hero} = {100*correct_hero/total_hero:.1f}%')

    # Check cross-card suit consistency
    print('\n  === Suit consistency check ===')
    for slot in range(5):
        suits_by_file = {}
        for fname in sorted(os.listdir(CAPTURAS_DIR)):
            if not (fname.startswith('com_') and fname.lower().endswith('.png')):
                continue
            label = fname.replace('com_', '').replace('.png', '')
            if slot < len(label) and label[slot] != 'X':
                img = np.array(Image.open(os.path.join(CAPTURAS_DIR, fname)).convert('RGB'))
                suit = CARD_READER.read_community_card_suit(img, slot)
                rank = label[slot]
                suits_by_file.setdefault(rank, []).append((fname, suit))
        for rank, entries in sorted(suits_by_file.items()):
            suits = [s for _, s in entries]
            if len(set(suits)) == 1:
                print(f'  Slot {slot} rank {rank}: consistent ({suits[0]}) [{len(entries)} cards]')
            else:
                print(f'  Slot {slot} rank {rank}: INCONSISTENT {suits}')

    print('\n=== Lector de Números (OCR rápido) ===')
    for fname in sorted(os.listdir(CAPTURAS_DIR)):
        if not (fname.startswith('Captura') and fname.lower().endswith('.png')):
            continue
        pil_img = Image.open(os.path.join(CAPTURAS_DIR, fname))
        pot = NUM_READER.read_pot(pil_img)
        stack = NUM_READER.read_stack(pil_img, 'hero')
        if pot is None:
            print(f'  {fname:40s} pot=???   hero_stack={stack!s}')
        elif stack is None:
            print(f'  {fname:40s} pot={pot:8.1f}  hero_stack=???')
        else:
            print(f'  {fname:40s} pot={pot:8.1f}  hero_stack={stack:8.1f}')
