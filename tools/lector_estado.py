"""
Lector de Estado Completo v2.1
Entrena con golden.json como ground truth.
Lee: cartas héroe, community cards, stacks, pot, state buttons (fondo de color según estado), dealer button, bets (felt text).
"""
import os, json
import numpy as np
from PIL import Image
from digit_ocr import DigitOCR

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURAS_DIR = os.path.join(REPO_DIR, 'capturas')
CALIB_PATH = os.path.join(REPO_DIR, 'data', 'calib_1365.json')
GOLDEN_PATH = os.path.join(REPO_DIR, 'data', 'golden.json')
TEMPLATE_DIR = os.path.join(REPO_DIR, 'templates')

with open(CALIB_PATH) as f:
    calib = json.load(f)

with open(GOLDEN_PATH) as f:
    GOLDEN = json.load(f)

# ============================================================
# DIGIT READER — OCR for numeric values via connected-component
# digit matching. Handles arbitrary unseen numbers.
# ============================================================
class DigitReader:
    MIN_IOU = 0.35

    def __init__(self, text_threshold=80):
        self.text_threshold = text_threshold
        self.digit_templates = {}  # ch -> list of binary masks

    def train(self, gray_crops, known_values):
        samples = {c: [] for c in '0123456789.'}
        for gray, val in zip(gray_crops, known_values):
            if val is None:
                continue
            if gray.max() < 110:
                continue
            binary = gray >= self.text_threshold
            chars = self._segment_and_label(binary)
            val_str = f'{float(val):.1f}'
            # Match segments to val_str characters right-to-left
            if not chars or len(chars) < len(val_str.replace('.', '')):
                continue
            clean_val = val_str.replace('.', '')
            if len(chars) == len(clean_val) + 1 and '.' in val_str:
                # segments include dot as separate char
                for i, (x, seg) in enumerate(chars):
                    if seg.shape[1] <= 3:
                        samples.setdefault('.', []).append(seg)
                    else:
                        di = sum(1 for j, (_, s) in enumerate(chars) if j < i and s.shape[1] > 3)
                        ch = clean_val[di] if di < len(clean_val) else '?'
                        samples.setdefault(ch, []).append(seg)
            elif len(chars) == len(clean_val):
                for i, (x, seg) in enumerate(chars):
                    ch = clean_val[i] if i < len(clean_val) else '?'
                    samples.setdefault(ch, []).append(seg)
        for ch, masks in samples.items():
            if masks:
                h = max(m.shape[0] for m in masks)
                w = max(m.shape[1] for m in masks)
                padded = np.zeros((len(masks), h, w), dtype=bool)
                for i, m in enumerate(masks):
                    padded[i, :m.shape[0], :m.shape[1]] = m
                self.digit_templates[ch] = [padded.mean(axis=0) > 0.3]

    @staticmethod
    def _segment_and_label(binary):
        col = binary.sum(axis=0)
        chars = []
        in_c = False
        start = 0
        for x in range(binary.shape[1]):
            if col[x] > 0 and not in_c:
                in_c = True
                start = x
            elif col[x] == 0 and in_c:
                in_c = False
                seg = binary[:, start:x]
                if seg.max():
                    chars.append((start, seg))
        if in_c:
            seg = binary[:, start:binary.shape[1]]
            if seg.max():
                chars.append((start, seg))
        # Second pass: split segments at decimal points (thin columns)
        result = []
        for gx, seg in chars:
            seg_col = seg.sum(axis=0)
            if seg.shape[1] < 6:
                result.append((gx, seg))
                continue
            # Group consecutive thin columns into dot regions
            dot_regions = []
            i = 0
            while i < seg.shape[1]:
                if seg_col[i] <= 2:
                    j = i
                    while j < seg.shape[1] and seg_col[j] <= 2:
                        j += 1
                    if j - i <= 3:
                        has_left = i > 0 and seg_col[i-1] >= 4
                        has_right = j < seg.shape[1] and seg_col[j] >= 4
                        if has_left or has_right:
                            dot_regions.append((i, j))
                    i = j + 1
                else:
                    i += 1
            if not dot_regions:
                result.append((gx, seg))
                continue
            prev = 0
            for dr_start, dr_end in dot_regions:
                if dr_start > prev:
                    sub = seg[:, prev:dr_start]
                    if sub.max():
                        result.append((gx + prev, sub))
                dp = seg[:, dr_start:dr_end]
                if dp.max():
                    result.append((gx + dr_start, dp))
                prev = dr_end
            if prev < seg.shape[1]:
                rem = seg[:, prev:]
                if rem.max():
                    result.append((gx + prev, rem))
        return result

    def read_number(self, gray_crop):
        if gray_crop.max() < 110 and (gray_crop >= 80).sum() > 100:
            return None
        binary = gray_crop >= self.text_threshold
        if binary.mean() < 0.003:
            return None
        chars = self._segment_and_label(binary)
        if not chars:
            return None
        recognized = []
        for x, seg in chars:
            ch, score = self._best_match(seg)
            if ch and score > self.MIN_IOU:
                recognized.append((x, ch, score))
        if not recognized:
            return None
        recognized.sort(key=lambda c: c[0])
        val_str = ''.join(c[1] for c in recognized)
        try:
            return float(val_str)
        except ValueError:
            return None

    def _best_match(self, seg):
        best_ch, best_score = None, -1
        if not self.digit_templates:
            return None, 0
        for ch, templates in self.digit_templates.items():
            for t in templates:
                score = self._iou(seg, t)
                if score > best_score:
                    best_score = score
                    best_ch = ch
        return best_ch, best_score

    @staticmethod
    def _iou(a, b):
        ha, wa = a.shape
        hb, wb = b.shape
        h = min(ha, hb)
        w = min(wa, wb)
        ac = a[:h, :w]
        bc = b[:h, :w]
        o = (ac & bc).sum()
        u = ac.sum() + bc.sum() - o
        return o / max(u, 1)


# ============================================================
# SLIDING WINDOW NUMBER READER
# Slides whole-number templates across a slightly wider crop
# to find the best alignment, handling ROI misalignment.
# ============================================================
class SlidingNumberReader:
    def __init__(self, text_threshold=80, min_text_ratio=0.003, iou_thresholds=None):
        self.text_threshold = text_threshold
        self.min_text_ratio = min_text_ratio
        self.refs = {}
        self.iou_thresholds = iou_thresholds or {}

    def train_region(self, region_key, gray_crops, known_values):
        entries = []
        for gray, val in zip(gray_crops, known_values):
            if val is None:
                continue
            if gray.max() < 110 and (gray >= 80).sum() > 100:
                continue
            binary = (gray >= self.text_threshold)
            if binary.mean() < self.min_text_ratio:
                continue
            entries.append((val, binary.ravel(), binary.shape[0], binary.shape[1]))
        if entries:
            self.refs[region_key] = entries

    def read_number(self, gray_crop, region_key):
        if region_key not in self.refs:
            return None
        # Noise rejection: feltro has many mid-bright pixels vs dim text has few
        if gray_crop.max() < 110:
            bright_at_80 = (gray_crop >= 80).sum()
            if bright_at_80 > 100:
                return None
        # Add 4px padding on each side for sliding
        padded = np.pad(gray_crop, ((4, 4), (4, 4)), mode='constant', constant_values=0)
        query = (padded >= self.text_threshold)
        if query.mean() < self.min_text_ratio:
            return None
        qh, qw = query.shape
        best_val = None
        best_score = -1
        for val, t_vec, th, tw in self.refs[region_key]:
            if th > qh or tw > qw:
                continue
            t_sum = t_vec.sum()
            for dy in range(qh - th + 1):
                for dx in range(qw - tw + 1):
                    window = query[dy:dy+th, dx:dx+tw]
                    w_vec = window.ravel()
                    overlap = (w_vec & t_vec).sum()
                    union = w_vec.sum() + t_sum - overlap
                    if union < 1:
                        continue
                    score = overlap / union
                    if score > best_score:
                        best_score = score
                        best_val = val
        iou_th = self.iou_thresholds.get(region_key, 0.50)
        return best_val if best_score > iou_th else None

# ============================================================
# 1-NN BINARY MATCHER
# ============================================================
class BinaryMatcher:
    STD_WIDTH = 64  # center-align all masks to this width

    def __init__(self, text_threshold=100, min_text_ratio=0.005):
        self.text_threshold = text_threshold
        self.min_text_ratio = min_text_ratio
        self.refs = {}

    @staticmethod
    def _center_align(mask, target_w):
        h, w = mask.shape
        if w == target_w:
            return mask
        if w > target_w:
            # Center-crop
            left = (w - target_w) // 2
            return mask[:, left:left + target_w]
        # Center-pad
        pad = target_w - w
        left = pad // 2
        right = pad - left
        return np.pad(mask, ((0, 0), (left, right)), mode='constant', constant_values=0)

    def train_region(self, region_key, samples_by_value):
        entries = []
        for val, binaries in samples_by_value.items():
            for b in binaries:
                aligned = self._center_align(b, self.STD_WIDTH)
                entries.append((val, aligned.ravel(), aligned.shape[0], aligned.shape[1]))
        if entries:
            self.refs[region_key] = entries

    def read_region(self, gray_crop, region_key, ocr=None, is_stack=False):
        if region_key not in self.refs:
            return None
        # Reject feltro texture: many mid-bright pixels but no truly bright text
        if gray_crop.max() < 110 and (gray_crop >= 80).sum() > 100:
            return None
        binary = (gray_crop >= self.text_threshold)
        if binary.mean() < self.min_text_ratio:
            return None
        # Center-align query to standard width
        h, w = binary.shape
        q_aligned = self._center_align(binary, self.STD_WIDTH)
        q_vec = q_aligned.ravel()
        h_aligned, w_aligned = q_aligned.shape
        best_val = None
        best_score = -1
        for val, t_vec, th, tw in self.refs[region_key]:
            if th == h_aligned and tw == w_aligned:
                vec = t_vec
                q = q_vec
            elif th >= h_aligned and tw >= w_aligned:
                t_mat = t_vec.reshape(th, tw)[:h_aligned, :w_aligned]
                vec = t_mat.ravel()
                q = q_vec
            else:
                t_mat = t_vec.reshape(th, tw)
                q_pad = self._center_align(q_aligned, tw)
                vec = t_vec
                q = q_pad.ravel()
            iou = (q & vec).sum() / max((q | vec).sum(), 1)
            score = iou
            if score > best_score:
                best_score = score
                best_val = val
        if best_score > 0.40:
            # If match is not exact, try DigitOCR for unseen values
            if best_score < 1.0 and ocr is not None:
                ocr_val = ocr.read(gray_crop, is_stack=is_stack)
                if ocr_val is not None:
                    return ocr_val
            return best_val
        return None


# ============================================================
# STATE MATCHER (1-NN on button-background masks)
# Detects any bright/saturated pixels above feltro level,
# regardless of button color (green=subir, blue=igualar, gray=retirarse, orange=mostrar).
# ============================================================
class StateMatcher:
    def __init__(self, min_bright_px=10):
        self.min_bright_px = min_bright_px
        self.refs = {}
        self.rois = {}
        self.color_sig = {}

    @staticmethod
    def _bright_mask(crop_rgb):
        return np.max(crop_rgb, axis=2) > 120

    @staticmethod
    def _button_color(crop_rgb):
        """Color medio del fondo del botón (píxeles brillantes junto al texto oscuro).
        Distingue botones verdes (subir/apostar) de azules (pasar/igualar) y
        amarillos (SB/BB/Mostrar cartas)."""
        bright = np.max(crop_rgb, axis=2) > 120
        dark = np.max(crop_rgb, axis=2) < 60
        from scipy.ndimage import binary_dilation
        text_near = binary_dilation(dark, np.ones((5, 5))) & bright
        if text_near.sum() < 20:
            return None
        return crop_rgb[text_near].mean(axis=0)

    @staticmethod
    def _is_button(crop_rgb):
        """Check that bright pixels form a centered dense region (button) not scattered (avatar/card)."""
        bright = np.max(crop_rgb, axis=2) > 120
        if bright.sum() < 10:
            return False
        # Card background: near-white (hero cards) - bright pixels at max>120 level
        bg_px = crop_rgb[bright]
        if len(bg_px) > 0 and bg_px[:, 0].mean() > 200 and bg_px[:, 1].mean() > 200 and bg_px[:, 2].mean() > 200:
            return False
        # Fill ratio: bounding-box occupancy
        ys, xs = np.where(bright)
        if len(ys) < 5:
            return False
        box_w = xs.max() - xs.min() + 1
        box_h = ys.max() - ys.min() + 1
        fill = bright.sum() / (box_w * box_h)
        if fill < 0.4:
            return False
        # At least 50 truly bright pixels (button vs scattered avatar highlights)
        if bright.sum() < 50:
            return False
        # Button text is centered in the ROI. If the largest text component
        # is at the extreme right edge (player name/avatar overflow), reject.
        dt2 = np.max(crop_rgb, axis=2) < 40
        from scipy.ndimage import binary_dilation, label
        bn2 = binary_dilation(bright, np.ones((3, 3)))
        tm2 = dt2 & bn2
        td2 = binary_dilation(tm2, np.ones((2, 2)))
        lbl, nl = label(td2, np.ones((3, 3), dtype=int))
        if nl > 0:
            sz2 = [(lbl == i).sum() for i in range(1, nl + 1)]
            bgst = np.argmax(sz2) + 1
            _ys, _xs = np.where(lbl == bgst)
            _cx = _xs.mean()
            if _cx > crop_rgb.shape[1] * 0.75:
                return False
        # Centered check: bright mass center should be near ROI center
        cx = xs.mean()
        roi_cx = bright.shape[1] / 2
        if abs(cx - roi_cx) > roi_cx * 0.35:
            return False
        cy = ys.mean()
        roi_cy = bright.shape[0] / 2
        if abs(cy - roi_cy) > roi_cy * 0.35:
            return False
        # Text presence: dark pixels (text) must exist on the bright background
        dark_text = np.max(crop_rgb, axis=2) < 40
        from scipy.ndimage import binary_dilation, label
        bg_near = binary_dilation(bright, np.ones((3, 3)))
        text_mask = dark_text & bg_near
        if text_mask.sum() < 3:
            return False
        # At least some dark pixels must be truly black (max < 20), not just gray decoration
        txt_px = crop_rgb[text_mask]
        if len(txt_px) > 0 and (np.max(txt_px, axis=1) < 20).sum() < 2:
            return False
        # Text must form connected components (letters), not scattered noise
        text_dil = binary_dilation(text_mask, np.ones((2, 2)))
        labeled, n = label(text_dil, np.ones((3, 3), dtype=int))
        if n < 1:
            return False
        sizes = [(labeled == i).sum() for i in range(1, n + 1)]
        big = [s for s in sizes if s >= 5]
        if len(big) < 1 or len(big) > 15:
            return False
        if max(big) < 8:
            return False
        # Real state text (SB, BB, pasar, igualar, ...) always forms components
        # >= 37 px; avatar/photo crops only have small stray dark pixels (<= ~18).
        if max(big) < 30:
            return False
        return True

    def train(self, player, roi, samples_by_state, colors_by_state=None):
        entries = []
        for state_val, masks in samples_by_state.items():
            for m in masks:
                entries.append((state_val, m.ravel(), m.shape[0], m.shape[1]))
        if entries:
            self.refs[player] = entries
            self.rois[player] = roi
        if colors_by_state:
            self.color_sig.update(colors_by_state)

    def read(self, pil_img, player):
        if player not in self.refs:
            return None
        roi = self.rois[player]
        img_rgb = np.array(pil_img.convert('RGB'))
        h_img, w_img = img_rgb.shape[:2]
        h_roi = max(roi[3] - roi[1], 1)
        w_roi = max(roi[2] - roi[0], 1)
        offsets = [(0, 0)]
        if h_img > h_roi:
            offsets.append((0, -1))
        if h_img > h_roi + 1:
            offsets.append((0, 1))
        if w_img > w_roi:
            offsets.append((-1, 0))
        if w_img > w_roi + 1:
            offsets.append((1, 0))
        best_val = None
        best_score = -1
        for dx, dy in offsets:
            x0 = max(0, min(roi[0] + dx, w_img - w_roi))
            y0 = max(0, min(roi[1] + dy, h_img - h_roi))
            x1 = min(x0 + w_roi, w_img)
            y1 = min(y0 + h_roi, h_img)
            crop = img_rgb[y0:y1, x0:x1]
            if not self._is_button(crop):
                continue
            bm = self._bright_mask(crop)
            cc = self._button_color(crop)
            h, w = bm.shape
            for val, t_vec, th, tw in self.refs[player]:
                if th == h and tw == w:
                    vec = t_vec
                    q = bm.ravel()
                elif th >= h and tw >= w:
                    t_mat = t_vec.reshape(th, tw)[:h, :w]
                    vec = t_mat.ravel()
                    q = bm.ravel()
                else:
                    q_pad = np.zeros((th, tw), dtype=bool)
                    kh, kw = min(h, th), min(w, tw)
                    q_pad[:kh, :kw] = bm[:kh, :kw]
                    vec = t_vec
                    q = q_pad.ravel()
                score = (q == vec).mean()
                # Refuerzo por color del botón: estados azules (pasar/igualar)
                # vs verdes (subir/apostar) comparten forma de máscara de brillo.
                if cc is not None:
                    sig = self.color_sig.get(val)
                    if sig is not None:
                        dist = (abs(cc[0] - sig[0]) + abs(cc[1] - sig[1])
                                + abs(cc[2] - sig[2])) / 765.0
                        score = score * 0.6 + max(0.0, 1.0 - dist) * 0.4
                if score > best_score:
                    best_score = score
                    best_val = val
        # Estados reales puntuan >= 0.875 (medido sobre golden); el avatar de
        # fondo alcanza ~0.60-0.72 y daba falsos 'BB'. Umbral 0.85.
        return best_val if best_score > 0.85 else None


# ============================================================
# FULL STATE READER
# ============================================================
class StateReader:
    # Bet text ROIs on the table felt (from user confirmation)
    BET_ROIS = {
        'hero': (685, 496, 749, 514),  # left-aligned at 685, 64×18
        'p1':   (441, 462, 505, 480),  # center 473, 64×18
        'p2':   (441, 390, 505, 408),  # center 473, 64×18
        'p3':   (685, 306, 749, 324),  # left-aligned at 685, 64×18
        'p4':   (860, 390, 924, 408),  # center 892, 64×18
        'p5':   (859, 462, 923, 480),  # center 891, 64×18
    }

    def __init__(self):
        self.bm = BinaryMatcher(text_threshold=80, min_text_ratio=0.005)
        iou_th = {tuple(calib['player_stacks']['p2']): 0.90}
        self.sr = SlidingNumberReader(text_threshold=80, min_text_ratio=0.003, iou_thresholds=iou_th)
        self.ocr = DigitOCR()
        self.dr = DigitReader(text_threshold=80)
        self.dr_trained = False
        self.sm = StateMatcher(min_bright_px=10)
        self._train()

    @staticmethod
    def _is_full_screenshot(fname):
        return fname.startswith('Captura')

    @staticmethod
    def _strip_left_label(gray_crop):
        binary = gray_crop >= 80
        col_sums = binary.sum(axis=0)
        for col in range(len(col_sums)):
            if col_sums[col] == 0:
                run = col
                while run < len(col_sums) and col_sums[run] == 0:
                    run += 1
                if run - col >= 2:
                    return gray_crop[:, run:]
        return gray_crop

    def _train(self):
        # ---- Numeric ROIs from calib ----
        numeric_regions = {}
        if 'pot' in calib:
            numeric_regions['pot'] = tuple(calib['pot'])
        for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
            coords = calib.get('player_stacks', {}).get(player)
            if coords:
                numeric_regions[f'{player}_stack'] = tuple(coords)

        region_data = {k: {} for k in numeric_regions}
        for fname, data in GOLDEN.items():
            if not self._is_full_screenshot(fname):
                continue
            for rname in numeric_regions:
                if rname == 'pot':
                    val = data.get('pot')
                elif rname.endswith('_stack'):
                    p = rname.replace('_stack', '')
                    val = data.get(f'{p}_stake')
                else:
                    continue
                if val is not None and isinstance(val, (int, float)):
                    v = float(val)
                    if v not in region_data[rname]:
                        region_data[rname][v] = []
                    region_data[rname][v].append(fname)

        for rname, rkey in numeric_regions.items():
            samples_by_val = {}
            all_crops, all_vals = [], []
            for val, fnames in region_data[rname].items():
                binaries = []
                for fn in fnames:
                    gray = np.array(Image.open(os.path.join(CAPTURAS_DIR, fn)).crop(rkey).convert('L'))
                    if rname == 'pot':
                        gray = self._strip_left_label(gray)
                    # Reject feltro texture: many mid-bright pixels but no truly bright text
                    if gray.max() < 110 and (gray >= 80).sum() > 100:
                        continue
                    binaries.append(gray >= self.bm.text_threshold)
                    all_crops.append(gray)
                    all_vals.append(val)
                if binaries:
                    samples_by_val[val] = binaries
            self.bm.train_region(rkey, samples_by_val)
            self.sr.train_region(rkey, all_crops, all_vals)
            if all_crops:
                self.dr.train(all_crops, all_vals)

        if not self.ocr._trained:
            self.ocr.train_cyclic()

        # ---- State ROIs (button background) ----
        state_rois = {
            'hero': (652, 577, 714, 594),
            'p1':   (390, 535, 452, 552),
            'p2':   (392, 297, 454, 314),
            'p3':   (652, 226, 714, 243),
            'p4':   (911, 297, 973, 314),
            'p5':   (914, 535, 976, 552),
        }

        state_data = {p: {} for p in state_rois}
        state_colors = {p: {} for p in state_rois}
        for fname, data in GOLDEN.items():
            if not fname.lower().endswith('.png'):
                continue
            img = np.array(Image.open(os.path.join(CAPTURAS_DIR, fname)).convert('RGB'))
            h_img, w_img = img.shape[:2]
            for player, roi in state_rois.items():
                state_val = data.get(f'{player}_state')
                if state_val is None:
                    continue
                h_roi = max(roi[3] - roi[1], 1)
                w_roi = max(roi[2] - roi[0], 1)
                offsets = [(0, 0)]
                if h_img > h_roi:
                    offsets.append((0, -1))
                if h_img > h_roi + 1:
                    offsets.append((0, 1))
                if w_img > w_roi:
                    offsets.append((-1, 0))
                if w_img > w_roi + 1:
                    offsets.append((1, 0))
                best_bm = None
                best_sum = 0
                for dx, dy in offsets:
                    x0 = max(0, min(roi[0] + dx, w_img - w_roi))
                    y0 = max(0, min(roi[1] + dy, h_img - h_roi))
                    x1 = min(x0 + w_roi, w_img)
                    y1 = min(y0 + h_roi, h_img)
                    crop = img[y0:y1, x0:x1]
                    bm = StateMatcher._bright_mask(crop)
                    s = bm.sum()
                    if s > best_sum:
                        best_sum = s
                        best_bm = bm
                        best_crop = crop
                if best_sum < 50:
                    continue
                state_data[player].setdefault(state_val, []).append(best_bm)
                bc = StateMatcher._button_color(best_crop)
                if bc is not None:
                    state_colors[player].setdefault(state_val, []).append(bc)
            del img

        # Pool state templates across ALL players (same ROI size 62x17)
        pooled_states = {}
        pooled_colors = {}
        for player, samples_dict in state_data.items():
            for val, masks in samples_dict.items():
                pooled_states.setdefault(val, []).extend(masks)
        for player, samples_dict in state_colors.items():
            for val, cs in samples_dict.items():
                arr = np.array(cs)
                pooled_colors[val] = tuple(np.median(arr, axis=0))
        for player, samples_dict in state_data.items():
            if not samples_dict:
                continue
            self.sm.train(player, state_rois[player], pooled_states, pooled_colors)

        # ---- Bet ROIs (table felt text) ----
        # Unified bet templates (all center-aligned to 52px to match max width)
        bet_pooled = {}
        for fname, data in GOLDEN.items():
            if not self._is_full_screenshot(fname):
                continue
            img = np.array(Image.open(os.path.join(CAPTURAS_DIR, fname)).convert('L'))
            for player, roi in self.BET_ROIS.items():
                bet_val = data.get(f'{player}_bet')
                if bet_val is not None and isinstance(bet_val, (int, float)):
                    crop = img[roi[1]:roi[3], roi[0]:roi[2]]
                    binary = crop >= self.bm.text_threshold
                    if binary.mean() >= 0.005:
                        bet_pooled.setdefault(float(bet_val), []).append(binary)
            del img
        if bet_pooled:
            self.bm.train_region(('bet',), bet_pooled)

        # Bet templates are now handled inside DigitOCR.train_cyclic()

    # ----------------------------------------------------------
    # Dealer button
    # ----------------------------------------------------------
    def detect_button(self, pil_img):
        arr = np.array(pil_img.convert('RGB'))
        candidates = []
        for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
            coords = calib['dealer_button'].get(player)
            if not coords:
                continue
            crop = arr[coords[1]:coords[3], coords[0]:coords[2]]
            mb = crop.mean()
            if mb > 80:
                candidates.append((mb, player))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_mb, best_player = candidates[0]
        # Protección p3: al mostrar las manos, el texto de la mano ganadora
        # aparece en el espacio del botón y con su mismo color → falso positivo
        # de botón únicamente en p3. p3 recibe el botón solo si ninguna otra
        # posición supera el umbral; si hay otra detectada, se prefiere esa.
        if best_player == 'p3' and len(candidates) > 1:
            for mb, player in candidates[1:]:
                if player != 'p3':
                    return player
        return best_player if best_mb > 80 else None

    # ----------------------------------------------------------
    # Unified read
    # ----------------------------------------------------------
    def read_all(self, pil_img):
        gray_img = np.array(pil_img.convert('L'))
        rgb_img = np.array(pil_img.convert('RGB'))
        result = {}

        # Pot (DigitOCR only — strip left label text)
        pc = calib.get('pot')
        if pc:
            gc = gray_img[pc[1]:pc[3], pc[0]:pc[2]]
            gc = self._strip_left_label(gc)
            result['pot'] = self.ocr.read(gc, pool='digits')

        # Stacks (DigitOCR first, then SlidingNumberReader, then BinaryMatcher)
        for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
            coords = calib.get('player_stacks', {}).get(player)
            if coords:
                gc = gray_img[coords[1]:coords[3], coords[0]:coords[2]]
                result[f'{player}_stake'] = self.ocr.read(gc, pool='stacks')

        # Button
        result['btn'] = self.detect_button(pil_img)

        # States (all detected labels: actions, BB, SB, BTN, inactive, etc.)
        for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
            state = self.sm.read(pil_img, player)
            # If no state detected, check if the player is inactive (no bright content in ROI)
            if state is None:
                roi = self.sm.rois.get(player)
                if roi:
                    crop = rgb_img[roi[1]:roi[3], roi[0]:roi[2], :]
                    bm = StateMatcher._bright_mask(crop)
                    if bm.sum() < 100:
                        state = 'inactivo'
            result[f'{player}_state'] = state

        # Bets: BinaryMatcher primary for p3 (unique ROI with button artifact
        # that confuses DigitOCR's character segmentation), DigitOCR primary
        # for other players, cross-fallback for all.
        for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
            roi = self.BET_ROIS.get(player)
            if roi:
                gc = gray_img[roi[1]:roi[3], roi[0]:roi[2]]
                if player == 'p3':
                    # BM primary (more robust to button frame remnants)
                    result[f'{player}_bet'] = self.bm.read_region(gc, ('bet',),
                        ocr=self.ocr)
                    if result[f'{player}_bet'] is None:
                        result[f'{player}_bet'] = self.ocr.read(gc, pool='digits')
                else:
                    result[f'{player}_bet'] = self.ocr.read(gc, pool='digits')
                    if result[f'{player}_bet'] is None:
                        result[f'{player}_bet'] = self.bm.read_region(gc, ('bet',),
                            ocr=self.ocr)
            else:
                result[f'{player}_bet'] = None



        # Players who are folded/inactive have no visible bet.
        # (No anular el stake: el golden registra stakes para jugadores
        # 'ausente'/'retirarse' — el stack sigue visible en la mesa.)
        null_states = {'retirarse', 'ausente', 'inactivo', 'sin jugador', 'fuera'}
        for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
            if result.get(f'{player}_state') in null_states:
                result[f'{player}_bet'] = None

        return result


# ============================================================
if __name__ == '__main__':
    import time as _time

    print('=== StateReader: training on golden.json ===')
    t0 = _time.perf_counter()
    sr = StateReader()
    dt = _time.perf_counter() - t0
    print(f'  Training: {dt*1000:.0f}ms')
    print(f'  Numeric regions: {len(sr.bm.refs)}')
    print(f'  State players: {list(sr.sm.refs.keys())}')

    # Verify only on full screenshots
    print('\n=== Verificación (solo Capturas) ===')
    total = 0
    correct = 0
    fp = 0
    fn = 0
    errors = []
    act_ok = act_total = 0

    t0 = _time.perf_counter()
    for fname, expected in sorted(GOLDEN.items()):
        if not fname.lower().endswith('.png'):
            continue
        path = os.path.join(CAPTURAS_DIR, fname)
        if not os.path.exists(path):
            continue
        pil = Image.open(path)
        result = sr.read_all(pil)

        # Check numeric fields — only relevant for Captura* screenshots
        for field in ['pot', 'pot_wide', 'btn',
                      'hero_stake', 'p1_stake', 'p2_stake', 'p3_stake', 'p4_stake', 'p5_stake',
                      'hero_bet', 'p1_bet', 'p2_bet', 'p3_bet', 'p4_bet', 'p5_bet']:
            exp = expected.get(field)
            got = result.get(field)
            # Skip numeric stack/bet/pot checks for com_*/mano_* files (no valid ground truth)
            if not fname.startswith('Captura') and field != 'btn':
                continue
            # Skip non-numeric strings for money fields (e.g. "$", "apostar to...")
            if isinstance(exp, str) and field != 'btn':
                continue
            if exp is None and got is None:
                correct += 1
            elif exp is not None and got is not None:
                if isinstance(exp, str) and exp == got:
                    correct += 1
                elif isinstance(exp, (int, float)) and isinstance(got, (int, float)) and abs(float(exp) - float(got)) < 0.01:
                    correct += 1
                else:
                    errors.append(f'{fname[:35]:35s} {field:20s} esp={exp!r:10s} obt={got!r:10s}')
            elif exp is not None and got is None:
                fn += 1
                errors.append(f'{fname[:35]:35s} {field:20s} esp={exp!r:10s} obt=None     [FN]')
            elif exp is None and got is not None:
                fp += 1
                errors.append(f'{fname[:35]:35s} {field:20s} esp=None     obt={got!r:10s} [FP]')
            total += 1

        # Check state fields — separate action states from labels
        ACTION_STATES = {'retirarse','ausente','igualar','subir','apostar','pasar','apostar todo'}
        for player in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']:
            field = f'{player}_state'
            exp = expected.get(field)
            got = result.get(field)
            if exp is None and got is None:
                pass
            elif isinstance(exp, str) and isinstance(got, str):
                if exp.lower() == got.lower():
                    if exp in ACTION_STATES:
                        act_ok += 1; act_total += 1
                else:
                    if exp in ACTION_STATES or got in ACTION_STATES:
                        errors.append(f'{fname[:35]:35s} {field:20s} esp={exp!r:10s} obt={got!r:10s}')
                    if exp in ACTION_STATES:
                        act_total += 1
            elif isinstance(exp, str) and got is None:
                if exp in ACTION_STATES:
                    act_total += 1
                    errors.append(f'{fname[:35]:35s} {field:20s} esp={exp!r:10s} obt=None     [FN]')
            elif isinstance(got, str) and exp is None:
                if got in ACTION_STATES:
                    act_total += 1
                    errors.append(f'{fname[:35]:35s} {field:20s} esp=None     obt={got!r:10s} [FP]')

    dt2 = _time.perf_counter() - t0
    print(f'  Verification: {dt2*1000:.0f}ms')
    print(f'\n  Resultados numéricos: {correct}/{total} = {100*correct/max(total,1):.1f}%')
    if act_total:
        print(f'  Estados acción: {act_ok}/{act_total} = {100*act_ok/max(act_total,1):.1f}%')
    else:
        print(f'  Estados acción: 0/0')
    if errors:
        print(f'\n  Errores relevantes ({len(errors)}):')
        for e in errors[:30]:
            print(f'    {e}')
