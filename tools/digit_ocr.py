"""
DigitOCR — per‑digit OCR.

Training (cyclic):  CCL → dot split → width‑organized templates.
Inference:          CCL → dot split → DP merge → exact‑width template matching.
"""
import os, json, hashlib
import numpy as np
from PIL import Image
from scipy.ndimage import label

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURAS_DIR = os.path.join(REPO_DIR, 'capturas')
CALIB_PATH = os.path.join(REPO_DIR, 'data', 'calib_1365.json')
GOLDEN_PATH = os.path.join(REPO_DIR, 'data', 'golden.json')
TEMPLATE_DIR = os.path.join(REPO_DIR, 'templates')
DIGIT_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, 'digits')
STACK_TEMPLATE_DIR = os.path.join(TEMPLATE_DIR, 'digits_stack')
UNKNOWN_DIR = os.path.join(DIGIT_TEMPLATE_DIR, 'unknown')

# Bet ROIs (same as StateReader.BET_ROIS)
BET_ROIS = {
    'hero': (685, 496, 749, 514),  # left-aligned at 685, 64×18
    'p1':   (441, 462, 505, 480),  # center 473, 64×18
    'p2':   (441, 390, 505, 408),  # center 473, 64×18
    'p3':   (685, 306, 749, 324),  # left-aligned at 685, 64×18
    'p4':   (860, 390, 924, 408),  # center 892, 64×18
    'p5':   (859, 462, 923, 480),  # center 891, 64×18
}


class DigitOCR:
    MIN_IOU = 0.25

    def __init__(self, text_threshold=80, load_templates=True):
        self.text_threshold = text_threshold
        self.digit_templates = {}   # {ch: {width: [mask, ...]}}  — pot / bets
        self.stack_templates = {}   # {ch: {width: [mask, ...]}}  — stacks
        self._trained = False
        self._thresh_offset = 14

        if load_templates:
            self._load_templates()

    def _binarize(self, gray_crop):
        thresh = max(gray_crop.mean() + self._thresh_offset, 60)
        return gray_crop >= thresh

    # ================================================================
    # CYCLIC TRAINING
    # ================================================================
    def train_cyclic(self, capturas_dir=None, golden=None):
        """Iterative per‑capture training with width‑organized templates.

        1. Process captures one by one, reading each with current templates.
        2. If result mismatches golden, extract the correct digit masks and
           add them as new templates (exact‑width buckets).
        3. After each capture, re‑verify ALL previously processed captures.
        4. Repeat the full pass until no new templates are added (converged).
        """
        if capturas_dir is None:
            capturas_dir = CAPTURAS_DIR
        if golden is None:
            with open(GOLDEN_PATH) as f:
                golden = json.load(f)
        if not os.path.exists(CALIB_PATH):
            return self
        with open(CALIB_PATH) as f:
            calib = json.load(f)

        captures = sorted(f for f in golden if f.startswith('Captura'))

        self._trained = True
        prev_total = -1
        for iteration in range(1, 6):
            for fname in captures:
                path = os.path.join(capturas_dir, fname)
                if not os.path.exists(path):
                    continue
                gray = np.array(Image.open(path).convert('L'))
                data = golden[fname]

                for pool, regions in [('digits', [
                    ('pot', tuple(calib['pot']), True),
                    *[(f'{p}_bet', BET_ROIS[p], False) for p in ['hero','p1','p2','p3','p4','p5']]
                ]), ('stacks', [
                    (f'{p}_stake', tuple(calib['player_stacks'][p]), True)
                    for p in ['hero','p1','p2','p3','p4','p5']
                ])]:
                    if pool == 'digits':
                        templates = self.digit_templates
                    else:
                        templates = self.stack_templates
                    for field, roi, has_bb in regions:
                        val = data.get(field)
                        if not isinstance(val, (int, float)):
                            continue
                        pred = self._read_region(gray, roi, pool=pool)
                        if pred is not None and abs(float(val) - pred) < 0.01:
                            continue
                        val_str = str(int(val)) if val == int(val) else str(val)
                        self._extract_and_add(gray, roi, val_str, has_bb, pool)

            curr_total = self._total_templates()
            added = curr_total - prev_total
            if added == 0:
                break
            prev_total = curr_total

        self.save_templates()
        return self

    # keep alias for backward compat
    train = train_cyclic

    def _read_region(self, gray, roi, pool='digits'):
        """Read a numeric value from a single ROI using the specified pool."""
        crop = gray[roi[1]:roi[3], roi[0]:roi[2]]
        return self.read(crop, pool=pool)

    @staticmethod
    def _split_wide_at_junction(sub, col_sums=None):
        """Split a wide binary mask at the best vertical-projection junction.
        Returns [left_mask, right_mask] or empty list if no good split found."""
        w = sub.shape[1]
        if col_sums is None:
            col_sums = sub.sum(axis=0)
        thin = [x for x in range(3, w - 3) if col_sums[x] <= max(col_sums) * 0.6]
        # Prioritize splits that produce balanced halves
        best = None
        best_ratio = float('inf')
        for x in thin:
            lw, rw = x, w - x
            if lw < 4 or rw < 4:
                continue
            left, right = sub[:, :x], sub[:, x:]
            if left.sum() < 10 or right.sum() < 10:
                continue
            ratio = lw / rw if lw > rw else rw / lw
            if ratio < best_ratio:
                best_ratio = ratio
                best = x
        if best is None:
            return []
        return [sub[:, :best], sub[:, best:]]

    def _extract_and_add(self, gray, roi, val_str, has_bb, pool):
        """Extract digit masks from a region and add them to the appropriate pool."""
        crop = gray[roi[1]:roi[3], roi[0]:roi[2]]
        if crop.size == 0:
            return
        binary = self._binarize(crop)
        if binary.sum() < 5:
            return

        # Find and trim BB suffix via column projection gap detection
        gap_trimmed = False
        col_sums = binary.sum(axis=0)
        nonzeros = np.where(col_sums > 0)[0]
        if len(nonzeros) > 0:
            last = int(nonzeros[-1])
            i = last
            while i > 0:
                if col_sums[i] == 0:
                    gap_end = i
                    while i > 0 and col_sums[i] == 0:
                        i -= 1
                    if gap_end - i > 3 and col_sums[i] > 0:
                        binary = binary[:, :gap_end]
                        gap_trimmed = True
                        break
                else:
                    i -= 1

        comps = self._ccl_components(binary)
        if not comps:
            return

        # Component-based BB removal below is only needed when gap detection
        # did NOT find a clear separation between value and BB.
        if not gap_trimmed:
            # Trim BB suffix (2 trailing digit-shaped components)
            if has_bb and len(comps) >= 2:
                c0, c1 = comps[-2], comps[-1]
                if (6 <= c0['w'] <= 10 and 6 <= c1['w'] <= 10) or \
                   (6 <= c0['w'] <= 10 and 2 <= c1['w'] <= 5 and c1['pixels'] >= 10):
                    comps = comps[:-2]
            if not comps:
                return

            # Remove trailing BB artifacts at the right edge of the crop
            while comps and comps[-1]['x2'] >= binary.shape[1] - 14:
                ch, sc = self._best_match(comps[-1]['mask'], pool=pool)
                if ch is not None and sc >= 0.85:
                    break
                comps.pop()
            if not comps:
                return

        # Split out dots that are merged inside CCL components
        comps = self._split_dot_components(binary, comps)

        # Classify tiny components as dots
        for c in comps:
            if c['w'] <= 4 and c['pixels'] <= 8 and c['h'] <= c['w']:
                c['dot'] = True

        # Merge adjacent split components (e.g. a '3' whose strokes are detached)
        comps = self._merge_split_components(binary, comps, pool)

        dot_comps = [c for c in comps if c['dot']]
        dig_comps = [c for c in comps if not c['dot'] and c['pixels'] >= 15]

        clean_val = val_str.replace('.', '')
        n_exp = len(clean_val)

        # Split merged wide components when component count is insufficient
        if len(dig_comps) < n_exp:
            expanded = []
            for c in dig_comps:
                if c['w'] >= 12 and len(expanded) + len(dig_comps) - dig_comps.index(c) - 1 < n_exp:
                    sub = binary[:, c['x1']:c['x2'] + 1]
                    parts = self._split_wide_at_junction(sub)
                    if len(parts) == 2:
                        for p in parts:
                            expanded.append({
                                'x1': 0, 'x2': p.shape[1] - 1,
                                'w': p.shape[1], 'h': 1,
                                'mask': p, 'pixels': p.sum(),
                                'dot': False
                            })
                        continue
                expanded.append(c)
            dig_comps = expanded

        templates = self.stack_templates if pool == 'stacks' else self.digit_templates

        if len(dig_comps) == n_exp:
            for c, ch in zip(dig_comps, clean_val):
                if c['mask'].sum() >= 3:
                    self._add_to_pool(templates, ch, c['mask'])
        elif len(dig_comps) > n_exp:
            pass

        for c in dot_comps:
            if not c.get('junction_dot'):
                self._add_to_pool(templates, '.', c['mask'])

    def _try_merge_pair(self, binary, comps, i, pool='digits'):
        """Try merging comps[i] and comps[i+1]; return merged or None."""
        c0, c1 = comps[i], comps[i+1]
        gap = c1['x1'] - c0['x2']
        cw = c1['x2'] - c0['x1'] + 1
        if not (1 <= gap <= 2 and cw <= 14):
            return None
        # Only merge if both individual components look incomplete
        _, sc0 = self._best_match(c0['mask'], pool=pool)
        _, sc1 = self._best_match(c1['mask'], pool=pool)
        if sc0 >= 0.85 or sc1 >= 0.85:
            return None
        merged_mask = binary[:, c0['x1']:c1['x2']+1]
        _, sc_m = self._best_match(merged_mask, pool=pool)
        if sc_m < 0.5:
            return None
        return {
            'x1': c0['x1'], 'x2': c1['x2'],
            'w': cw, 'h': binary.shape[0],
            'mask': merged_mask, 'pixels': merged_mask.sum(),
            'dot': False
        }

    def _merge_split_components(self, binary, comps, pool='digits'):
        """Merge adjacent non-dot components with small gap that likely
        belong to the same digit (e.g. a '3' whose left stroke is detached
        from its curves)."""
        if len(comps) < 2:
            return comps
        result = []
        i = 0
        while i < len(comps):
            if i + 1 < len(comps) and not comps[i].get('dot') and not comps[i+1].get('dot'):
                merged = self._try_merge_pair(binary, comps, i, pool)
                if merged:
                    result.append(merged)
                    i += 2
                    continue
            result.append(comps[i])
            i += 1
        return result

    # ================================================================
    # LEGACY SINGLE-PASS TRAINING (kept for reference)
    # ================================================================
    def train_legacy(self, capturas_dir=None, golden=None):
        """Original single‑pass training, reworked for width‑organized storage."""
        if capturas_dir is None:
            capturas_dir = CAPTURAS_DIR
        if golden is None:
            with open(GOLDEN_PATH) as f:
                golden = json.load(f)
        if not os.path.exists(CALIB_PATH):
            return self
        with open(CALIB_PATH) as f:
            calib = json.load(f)

        raw = {c: [] for c in '0123456789.'}

        for fname, data in golden.items():
            if not fname.startswith('Captura'):
                continue
            path = os.path.join(capturas_dir, fname)
            if not os.path.exists(path):
                continue
            gray = np.array(Image.open(path).convert('L'))

            for region_key, field, has_bb in [
                ('pot', 'pot', False),
            ] + [(f'{p}_stack', f'{p}_stake', True) for p in
                 ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']]:
                val = data.get(field)
                if not isinstance(val, (int, float)):
                    continue
                if region_key == 'pot':
                    roi = tuple(calib['pot'])
                else:
                    p = region_key.replace('_stack', '')
                    roi = tuple(calib['player_stacks'][p])
                val_str = str(int(val)) if val == int(val) else str(val)
                self._extract_train(gray, roi, val_str, raw, has_bb)

        max_widths = {'1': 10, '.': 4}
        for ch, masks in raw.items():
            if ch == '.':
                kept = [m for m in masks if m.sum() <= 8 and m.shape[1] <= 4]
            else:
                mw = max_widths.get(ch, 25)
                kept = [m for m in masks if m.sum() >= 15 and m.shape[1] <= mw]
            if kept:
                by_width = {}
                for m in kept:
                    w = m.shape[1]
                    by_width.setdefault(w, []).append(m)
                self.digit_templates[ch] = by_width

        self._trained = True
        self.save_templates()
        return self

    def _extract_train(self, gray, roi, val_str, raw, has_bb):
        """Extract masks and append to raw dict (helper for train_legacy)."""
        crop = gray[roi[1]:roi[3], roi[0]:roi[2]]
        if crop.size == 0:
            return
        binary = self._binarize(crop)
        if binary.sum() < 5:
            return

        comps = self._ccl_components(binary)
        if not comps:
            return

        if has_bb and len(comps) >= 2:
            if all(6 <= c['w'] <= 10 for c in comps[-2:]):
                comps = comps[:-2]
        if not comps:
            return

        comps = self._split_dot_components(binary, comps)

        for c in comps:
            if c['w'] <= 4 and c['pixels'] <= 8 and c['h'] <= c['w']:
                c['dot'] = True

        dot_comps = [c for c in comps if c['dot']]
        dig_comps = [c for c in comps if not c['dot'] and c['pixels'] >= 15]

        clean_val = val_str.replace('.', '')
        n_exp = len(clean_val)

        if len(dig_comps) == n_exp:
            for c, ch in zip(dig_comps, clean_val):
                if c['mask'].sum() >= 3:
                    raw.setdefault(ch, []).append(c['mask'])
        elif len(dig_comps) > n_exp:
            pass

        for c in dot_comps:
            raw.setdefault('.', []).append(c['mask'])

    # ================================================================
    # CCL + component splitting (shared by training & inference)
    # ================================================================
    def _split_wide_component(self, binary, comp, pool='digits'):
        """Split a wide CCL component (w >= 14) by trying every split column
        and picking the one where both halves match templates with high score."""
        sub = binary[:, comp['x1']:comp['x2'] + 1]
        w = sub.shape[1]
        col_sums = sub.sum(axis=0)
        thin_candidates = [c for c in range(3, w - 3) if col_sums[c] < max(col_sums) * 0.55]
        best_total, best_split = 0, None
        for split_at in thin_candidates:
            left = sub[:, :split_at]
            right = sub[:, split_at:]
            if left.sum() < 15 or right.sum() < 15:
                continue
            lw, rw = left.shape[1], right.shape[1]
            if lw > rw * 2 or rw > lw * 2:
                continue
            ch_l, sc_l = self._best_match(left, pool=pool)
            ch_r, sc_r = self._best_match(right, pool=pool)
            if ch_l is None or ch_r is None:
                continue
            total = sc_l + sc_r
            if total > best_total:
                best_total = total
                best_split = split_at
        if best_split is None:
            # Fusion de TRES cifras (p.ej. '172'): intenta dos cortes a la vez.
            best3 = None
            cands = thin_candidates
            for a in range(len(cands)):
                for b in range(a + 1, len(cands)):
                    j1, j2 = cands[a], cands[b]
                    p1 = sub[:, :j1]
                    p2 = sub[:, j1:j2]
                    p3 = sub[:, j2:]
                    if p1.sum() < 15 or p2.sum() < 15 or p3.sum() < 15:
                        continue
                    w1, w2, w3 = p1.shape[1], p2.shape[1], p3.shape[1]
                    if w1 < 3 or w2 < 3 or w3 < 3:
                        continue
                    c1, s1 = self._best_match(p1, pool=pool)
                    c2, s2 = self._best_match(p2, pool=pool)
                    c3, s3 = self._best_match(p3, pool=pool)
                    if c1 is None or c2 is None or c3 is None:
                        continue
                    total = s1 + s2 + s3
                    if best3 is None or total > best3[0]:
                        best3 = (total, j1, j2)
            if best3 is None:
                return [comp]
            _, j1, j2 = best3
            result = []
            for start, end in [(0, j1), (j1, j2), (j2, w)]:
                mask = sub[:, start:end]
                result.append({'x1': comp['x1'] + start,
                               'x2': comp['x1'] + end - 1,
                               'w': end - start, 'h': comp['h'],
                               'mask': mask, 'pixels': mask.sum(),
                               'dot': False})
            return result
        left_mask = sub[:, :best_split]
        right_mask = sub[:, best_split:]
        result = []
        gx = comp['x1']
        result.append({'x1': gx, 'x2': gx + best_split - 1,
                       'w': best_split, 'h': comp['h'],
                       'mask': left_mask, 'pixels': left_mask.sum(),
                       'dot': False})
        result.append({'x1': gx + best_split, 'x2': comp['x2'],
                       'w': w - best_split, 'h': comp['h'],
                       'mask': right_mask, 'pixels': right_mask.sum(),
                       'dot': False})
        return result

    @staticmethod
    def _split_dot_components(binary, comps):
        """Within each wide CCL component, detect and split out merged dots."""
        h = binary.shape[0]
        result = []
        for idx, c in enumerate(comps):
            w = c['x2'] - c['x1'] + 1
            if w < 6:
                result.append(c)
                continue
            sub = binary[:, c['x1']:c['x2'] + 1]
            col = sub.sum(axis=0)
            next_x1 = comps[idx + 1]['x1'] if idx + 1 < len(comps) else None
            splits = []
            i = 0
            while i < len(col):
                if col[i] <= 3:
                    j = i
                    while j < len(col) and col[j] <= 3:
                        j += 1
                    rw = j - i
                    if 2 <= rw <= 5:
                        # Un punto adherido al borde derecho de su glifo solo es
                        # plausible si el glifo siguiente está pegado a 1-2 píxeles
                        # (p.ej. '2.'+ '5'); si hay hueco mayor, el trozo es parte
                        # del propio trazo de la cifra (p.ej. el serif del '4').
                        edge_tight = j == w and next_x1 is not None and \
                            c['x1'] + j - 1 >= next_x1 - 3
                        if j < w or edge_tight:
                            run_seg = sub[:, i:j]
                            if run_seg.sum() >= 3:
                                ys = np.where(run_seg)[0]
                                if len(ys) > 0:
                                    # Punto refundido con el trazo de la cifra: se
                                    # acepta si arranca en la mitad inferior o la
                                    # mayoría de sus píxeles están en la mitad
                                    # inferior (p.ej. '12.1' con el punto pegado
                                    # a la cola del '2').
                                    lo = int((ys >= h * 0.5).sum())
                                    spread = int(ys.max() - ys.min())
                                    if ys.min() >= h * 0.5 or (
                                            (edge_tight or spread <= 2) and
                                            lo >= max(2, ys.size * 0.6)):
                                        splits.append((i, j))
                    i = j + 1
                else:
                    i += 1
            if not splits:
                result.append(c)
                continue

            prev = 0
            pieces = []
            for sp, ep in splits:
                if sp > prev:
                    submask = sub[:, prev:sp]
                    if submask.max():
                        gx1 = c['x1'] + prev
                        gx2 = c['x1'] + sp - 1
                        pieces.append({
                            'x1': gx1, 'x2': gx2,
                            'w': gx2 - gx1 + 1,
                            'h': c['h'],
                            'mask': submask,
                            'pixels': submask.sum(),
                            'dot': False
                        })
                dmask = sub[:, sp:ep]
                if dmask.max():
                    gx1 = c['x1'] + sp
                    gx2 = c['x1'] + ep - 1
                    pieces.append({
                        'x1': gx1, 'x2': gx2,
                        'w': gx2 - gx1 + 1,
                        'h': c['h'],
                        'mask': dmask,
                        'pixels': dmask.sum(),
                        'dot': True
                    })
                prev = ep
            if prev < len(col):
                rem = sub[:, prev:]
                if rem.max():
                    gx1 = c['x1'] + prev
                    gx2 = c['x1'] + len(col) - 1
                    pieces.append({
                        'x1': gx1, 'x2': gx2,
                        'w': gx2 - gx1 + 1,
                        'h': c['h'],
                        'mask': rem,
                        'pixels': rem.sum(),
                        'dot': False
                    })
            # Un punto interior a un compuesto (con piezas a ambos lados) es el
            # hueco de UNION de dos cifras fusionadas ('46', '12.1'...), no un
            # punto decimal real: los puntos reales solo se adhieren a un solo
            # glifo (p.ej. '2.') y nunca quedan interiores.
            next_c = comps[idx + 1] if idx + 1 < len(comps) else None
            for k, piece in enumerate(pieces):
                if piece['dot']:
                    if k < len(pieces) - 1:
                        piece['junction_dot'] = True
                    elif next_c is not None and next_c['x1'] - piece['x2'] <= 0:
                        # Punto final que SOLAPA con el glifo siguiente: es un
                        # fragmento de union (p.ej. el serif del '4' pegado al
                        # '7'), no un punto decimal real.
                        piece['junction_dot'] = True
            result.extend(pieces)
        result.sort(key=lambda x: x['x1'])
        return result

    @staticmethod
    def _ccl_components(binary):
        labeled, n = label(binary, np.ones((3, 3), dtype=int))
        comps = []
        for i in range(1, n + 1):
            ys, xs = np.where(labeled == i)
            if len(ys) < 1:
                continue
            x1, x2 = xs.min(), xs.max()
            y1, y2 = ys.min(), ys.max()
            mask = labeled[y1:y2 + 1, x1:x2 + 1] == i
            comps.append({
                'x1': x1, 'x2': x2, 'w': x2 - x1 + 1,
                'h': y2 - y1 + 1, 'mask': mask, 'pixels': mask.sum(),
                'dot': False
            })
        comps.sort(key=lambda c: c['x1'])
        return comps

    @staticmethod
    def _merge_comps(comps, target_n, binary):
        groups = [[i] for i in range(len(comps))]
        while len(groups) > target_n:
            best_pair, best_gap = None, float('inf')
            for i in range(len(groups) - 1):
                g = comps[groups[i][-1]]['x2']
                h = comps[groups[i + 1][0]]['x1']
                gap = h - g
                if gap < best_gap:
                    best_gap = gap
                    best_pair = i
            if best_pair is None or best_gap > 10:
                break
            groups[best_pair] = groups[best_pair] + groups[best_pair + 1]
            groups.pop(best_pair + 1)
        result = []
        for g in groups:
            x1 = comps[g[0]]['x1']
            x2 = comps[g[-1]]['x2']
            result.append(binary[:, x1:x2 + 1])
        return result

    # ================================================================
    # INFERENCE
    # ================================================================
    def read(self, gray_crop, is_stack=False, pool=None):
        if not self._trained:
            return None
        if pool is None:
            pool = 'stacks' if is_stack else 'digits'
        else:
            is_stack = (pool == 'stacks')
        templates = self.stack_templates if pool == 'stacks' else self.digit_templates
        if not templates:
            return None

        binary = self._binarize(gray_crop)
        if binary.mean() < 0.003:
            return None

        # Find and trim BB suffix via column projection gap detection.
        # BB text is always separated from the numeric value by a gap of 4+ px
        # (gaps between digits/dots are 1-3px). Scan right-to-left for the first
        # gap > 3px; everything after that is BB. The gap must have content on
        # its left side (a leading margin of the crop is not a BB gap).
        gap_trimmed = False
        col_sums = binary.sum(axis=0)
        nonzeros = np.where(col_sums > 0)[0]
        if len(nonzeros) > 0:
            last = int(nonzeros[-1])
            i = last
            while i > 0:
                if col_sums[i] == 0:
                    gap_end = i
                    while i > 0 and col_sums[i] == 0:
                        i -= 1
                    if gap_end - i > 3 and col_sums[i] > 0:
                        binary = binary[:, :gap_end]
                        gap_trimmed = True
                        break
                else:
                    i -= 1

        comps = self._ccl_components(binary)
        if not comps:
            return None

        # Trim a leading '$'-like symbol: grupo pegado al borde izquierdo del
        # crop, seguido de un hueco de 4+ px antes del texto (los huecos entre
        # cifras/puntos son de 1-3 px). El grupo debe terminar antes de x=12
        # (una cifra real partida, p.ej. el '4' de '4.5', queda excluida).
        if comps and comps[0]['x1'] == 0 and len(comps) >= 2:
            for i in range(len(comps) - 1):
                if comps[i + 1]['x1'] - comps[i]['x2'] - 1 >= 4:
                    if comps[i]['x2'] < 12:
                        del comps[:i + 1]
                    break

        # The component-based BB trims below are only needed when gap detection
        # did NOT find a clear separation (unusual layout or dense text).
        if not gap_trimmed:
            # Trim trailing artifacts (2 trailing digit-shaped components)
            if len(comps) >= 2:
                c0, c1 = comps[-2], comps[-1]
                if (6 <= c0['w'] <= 10 and 6 <= c1['w'] <= 10) or \
                   (6 <= c0['w'] <= 10 and 2 <= c1['w'] <= 5 and c1['pixels'] >= 10):
                    comps = comps[:-2]
            if not comps:
                return None

            # Remove trailing BB artifacts at the right edge of the TEXT
            # (the '$'-bundle usually ends well before the crop boundary)
            if len(nonzeros) > 0:
                last_nz_col = int(nonzeros[-1])
            else:
                last_nz_col = binary.shape[1]
            while comps and comps[-1]['x2'] >= last_nz_col - 14:
                ch, sc = self._best_match(comps[-1]['mask'], pool=pool)
                if ch is not None and sc >= 0.85:
                    break
                comps.pop()
            if not comps:
                return None

        comps = self._split_dot_components(binary, comps)

        for c in comps:
            if c['w'] <= 4 and c['pixels'] <= 8 and c['h'] <= 4:
                c['dot'] = True

        # Split wide digit components at optimal junction
        expanded = []
        templates = self.stack_templates if pool == 'stacks' else self.digit_templates
        for c in comps:
            if c['dot'] or c['w'] < 12:
                expanded.append(c)
            else:
                parts = self._split_wide_component(binary, c, pool=pool)
                if len(parts) >= 2:
                    all_ok = True
                    for part in parts:
                        pch, _ = self._best_match(part['mask'], pool=pool)
                        if pch is None or not any(abs(part['w'] - tw) <= 1
                                                  for tw in templates.get(pch, {})):
                            all_ok = False
                            break
                    if all_ok:
                        expanded.extend(parts)
                        continue
                expanded.append(c)
        comps = expanded

        # Merge adjacent split components
        comps = self._merge_split_components(binary, comps, pool)

        dot_items = [c for c in comps if c['dot'] and not c.get('junction_dot')]
        dig_items = [c for c in comps if not c['dot'] and c['pixels'] >= 15]

        # Filter junction pixels
        valid_dots = []
        for d in dot_items:
            if d['pixels'] >= 3:
                valid_dots.append(d)
                continue
            touches_left = any(0 <= d['x1'] - dig['x2'] <= 1 for dig in dig_items)
            touches_right = any(0 <= dig['x1'] - d['x2'] <= 1 for dig in dig_items)
            if not (touches_left and touches_right):
                valid_dots.append(d)
        dot_items = valid_dots

        def _score(mask):
            ch, sc = self._best_match(mask, save_unknown=True, pool=pool)
            return (ch, sc) if sc >= self.MIN_IOU else (None, 0.0)

        m = len(dig_items)
        if m == 0:
            return None

        dp = [(0.0, []) for _ in range(m + 1)]
        dp[0] = (0.0, [])

        for i in range(m):
            cur_score = dp[i][0]
            if i > 0 and cur_score == 0.0:
                continue
            x0 = dig_items[i]['x1']
            for j in range(i, min(i + 3, m)):
                if j > i:
                    gap = dig_items[j]['x1'] - dig_items[j - 1]['x2']
                    if gap > 6:
                        break
                xj = dig_items[j]['x2']
                merged = binary[:, x0:xj + 1]
                if merged.shape[1] > 30:
                    break
                if j == i:
                    ch, sc = _score(dig_items[i]['mask'])
                else:
                    ch, sc = _score(merged)
                if ch is None:
                    if j > i:
                        # Fragmented glyphs (e.g. a '0' whose strokes detach at
                        # the binarize threshold) make the merged range match no
                        # single template. Try splitting it into two valid
                        # digits at the thinnest junction before giving up.
                        pseudo = {'x1': x0, 'x2': xj, 'h': merged.shape[0]}
                        parts = self._split_wide_component(binary, pseudo,
                                                           pool=pool)
                        if len(parts) == 2:
                            ch0, sc0 = self._best_match(parts[0]['mask'],
                                                        pool=pool)
                            ch1, sc1 = self._best_match(parts[1]['mask'],
                                                        pool=pool)
                            if ch0 is not None and ch1 is not None:
                                abs_split = parts[0]['x2'] + 1
                                segs_l = sum(1 for k in range(i, j + 1)
                                             if dig_items[k]['x2'] < abs_split)
                                segs_r = (j - i + 1) - segs_l
                            if segs_l >= 1 and segs_r >= 1:
                                total = cur_score + sc0 + sc1
                                if total > dp[j + 1][0]:
                                    dp[j + 1] = (total, dp[i][1] +
                                                 [(ch0, segs_l, sc0),
                                                  (ch1, segs_r, sc1)])
                    continue
                total = cur_score + sc
                if total > dp[j + 1][0]:
                    dp[j + 1] = (total, dp[i][1] + [(ch, j - i + 1, sc)])

        best = max(range(1, m + 1), key=lambda i: dp[i][0])
        if dp[best][0] == 0.0:
            return None

        chars_info = dp[best][1]

        # Reject glyphs that are NOT real digits: the "apostar todo" all-in
        # badge text sits inside the stack ROI and force-matches digit
        # templates with much lower IOU than real numbers (medido: reales
        # >= 0.61, badge <= 0.42). Stacks also never have 7 integer digits.
        if any(sc < 0.50 for _ch, _n, sc in chars_info):
            return None
        if is_stack:
            n_digits = sum(n for _ch, n, _sc in chars_info)
            if n_digits > 6:
                return None

        # Reject crops with significant unconsumed glyphs: text like
        # 'Apostar to...' has letters left unmatched after the digit path,
        # while real numbers consume all components.
        consumed = 0
        for _ch, n_segs, _sc in chars_info:
            consumed += n_segs
        if consumed < len(dig_items):
            leftover = sum(int(binary[:, c['x1']:c['x2'] + 1].sum())
                           for c in dig_items[consumed:])
            total_px = int(binary.sum())
            if total_px and leftover / total_px > 0.15:
                return None

        dig_x1 = dig_items[0]['x1'] if dig_items else 0
        dig_x2 = dig_items[-1]['x2'] if dig_items else 0
        all_items = [(c['x1'], '.') for c in dot_items
                     if dig_x1 <= c['x1'] <= dig_x2]
        consumed = 0
        for ch, n_segs, _sc in chars_info:
            if consumed < len(dig_items):
                all_items.append((dig_items[consumed]['x1'], ch))
                consumed += n_segs
        all_items.sort(key=lambda x: x[0])

        val_str = ''.join(item[1] for item in all_items)
        if not val_str:
            return None
        cleaned = []
        prev_dot = False
        for ch in val_str:
            if ch == '.':
                if prev_dot:
                    continue
                prev_dot = True
            else:
                prev_dot = False
            cleaned.append(ch)
        val_str = ''.join(cleaned).strip('.')
        if not val_str:
            return None
        try:
            return float(val_str)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Template matching — exact width match
    # ------------------------------------------------------------------
    def _best_match(self, seg_mask, save_unknown=False, pool='digits'):
        best_ch, best_score = None, -1
        seg_px = seg_mask.sum()
        seg_w = seg_mask.shape[1]

        templates = self.stack_templates if pool == 'stacks' else self.digit_templates

        for ch, widths in templates.items():
            for w, masks in widths.items():
                if abs(seg_w - w) > 2:
                    continue
                for t in masks:
                    if ch == '.' and seg_px > 12:
                        continue
                    if ch != '.' and seg_px < 2:
                        continue
                    score = self._iou(seg_mask, t)
                    if score > best_score:
                        best_score = score
                        best_ch = ch
        if best_ch is None and save_unknown:
            self._save_unknown(seg_mask)
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

    # ----------------------------------------------------------
    # Template file I/O — width‑organized PNGs
    # ----------------------------------------------------------
    def save_templates(self):
        self._save_pool(self.digit_templates, DIGIT_TEMPLATE_DIR)
        self._save_pool(self.stack_templates, STACK_TEMPLATE_DIR)

    @staticmethod
    def _save_pool(templates, base_dir):
        if not templates:
            return
        MAX_PER_WIDTH = 25  # cap de máscaras por (carácter, ancho) para evitar
                            # acumulación ilimitada de archivos en cada reentreno
        for ch, widths in templates.items():
            if not ch:
                continue
            ch_name = 'dot' if ch == '.' else ch
            for w, masks in widths.items():
                ch_dir = os.path.join(base_dir, ch_name, f'w{w}')
                os.makedirs(ch_dir, exist_ok=True)
                keep = masks[:MAX_PER_WIDTH]
                for i, mask in enumerate(keep):
                    img = (mask.astype(np.uint8)) * 255
                    Image.fromarray(img).save(os.path.join(ch_dir, f'{i:02d}.png'))
                # Podar archivos sobrantes de reentrenos anteriores
                for fname in os.listdir(ch_dir):
                    if not fname.endswith('.png'):
                        continue
                    try:
                        idx = int(fname[:2])
                    except ValueError:
                        idx = MAX_PER_WIDTH
                    if idx >= len(keep):
                        try:
                            os.remove(os.path.join(ch_dir, fname))
                        except OSError:
                            pass

    def _load_templates(self):
        self._load_pool(self.digit_templates, DIGIT_TEMPLATE_DIR)
        self._load_pool(self.stack_templates, STACK_TEMPLATE_DIR)
        if self.digit_templates or self.stack_templates:
            self._trained = True
        return self

    @staticmethod
    def _load_pool(dest, base_dir):
        if not os.path.isdir(base_dir):
            return
        for ch in sorted(os.listdir(base_dir)):
            ch_dir = os.path.join(base_dir, ch)
            if not os.path.isdir(ch_dir):
                continue
            if ch == 'unknown':
                continue
            key = '.' if ch == 'dot' else ch

            # Detect old format: PNGs directly in char dir (no width subdirs)
            pngs = sorted(f for f in os.listdir(ch_dir) if f.endswith('.png'))
            if pngs:
                by_width = {}
                for fname in pngs:
                    path = os.path.join(ch_dir, fname)
                    m = np.array(Image.open(path).convert('L')) > 128
                    w = m.shape[1]
                    by_width.setdefault(w, []).append(m)
                for w, wmasks in by_width.items():
                    dest.setdefault(key, {}).setdefault(w, []).extend(wmasks)
                continue

            # New format: width subdirectories (w{width})
            for wdir in sorted(os.listdir(ch_dir)):
                wdir_path = os.path.join(ch_dir, wdir)
                if not os.path.isdir(wdir_path) or not wdir.startswith('w'):
                    continue
                w = int(wdir[1:])
                masks = []
                for fname in sorted(os.listdir(wdir_path)):
                    if not fname.endswith('.png'):
                        continue
                    path = os.path.join(wdir_path, fname)
                    img = np.array(Image.open(path).convert('L'))
                    masks.append(img > 128)
                if masks:
                    dest.setdefault(key, {}).setdefault(w, []).extend(masks)

    @staticmethod
    def _add_to_pool(templates, ch, mask):
        """Add mask to template pool if not already present (by content hash)."""
        w = mask.shape[1]
        existing = templates.get(ch, {}).get(w, [])
        for t in existing:
            if t.shape == mask.shape and (t == mask).all():
                return
        templates.setdefault(ch, {}).setdefault(w, []).append(mask)

    def _save_unknown(self, mask, context=''):
        """Save an unrecognized component for manual labeling."""
        os.makedirs(UNKNOWN_DIR, exist_ok=True)
        # Nombre derivado del contenido: el mismo glifo regenerado en otra
        # sesión sobrescribe su archivo en vez de acumular duplicados
        # (evita los miles de copias idénticas que llenaban la carpeta).
        key = mask.astype(np.uint8).tobytes()
        digest = hashlib.md5(key).hexdigest()[:8]
        tag = f'un_{digest}'
        if context:
            tag += f'_{context}'
        path = os.path.join(UNKNOWN_DIR, f'{tag}.png')
        img = (mask.astype(np.uint8)) * 255
        Image.fromarray(img).save(path)

    def list_unknowns(self):
        """Return list of unknown component paths for review."""
        if not os.path.isdir(UNKNOWN_DIR):
            return []
        return sorted([
            os.path.join(UNKNOWN_DIR, f)
            for f in os.listdir(UNKNOWN_DIR) if f.endswith('.png')
        ])

    def _total_templates(self):
        """Count total templates across both pools."""
        total = 0
        for t in (self.digit_templates, self.stack_templates):
            for widths in t.values():
                for masks in widths.values():
                    total += len(masks)
        return total

    def print_summary(self):
        """Print a summary of templates per character and width."""
        for pool_name, t in [('digits', self.digit_templates), ('stacks', self.stack_templates)]:
            print(f'\n  [{pool_name}]')
            for ch in sorted(t.keys()):
                for w in sorted(t[ch].keys()):
                    n = len(t[ch][w])
                    print(f'    {ch!r} w={w}: {n} templates')


# ------------------------------------------------------------------
if __name__ == '__main__':
    import time
    print('=== DigitOCR Cyclic Training ===')
    t0 = time.perf_counter()
    ocr = DigitOCR(load_templates=False)
    ocr.train_cyclic()
    dt = time.perf_counter() - t0
    print(f'  Hecho en {dt*1000:.0f}ms')
    ocr.print_summary()
    total = ocr._total_templates()
    print(f'\n  Total templates: {total}')

    from lector_estado import GOLDEN, calib

    fields = ['pot'] + [f'{p}_stake' for p in ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']]
    PLAYERS = ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']

    total = correct = 0
    errors = []

    t0 = time.perf_counter()
    for fname, data in sorted(GOLDEN.items()):
        if not fname.startswith('Captura'):
            continue
        path = os.path.join(CAPTURAS_DIR, fname)
        if not os.path.exists(path):
            continue
        gray = np.array(Image.open(path).convert('L'))
        for field in fields:
            val = data.get(field)
            if val is None or not isinstance(val, (int, float)):
                continue
            if field == 'pot':
                roi = tuple(calib['pot'])
                pred = ocr.read(gray[roi[1]:roi[3], roi[0]:roi[2]], pool='digits')
            else:
                p = field.replace('_stake', '')
                roi = tuple(calib['player_stacks'][p])
                pred = ocr.read(gray[roi[1]:roi[3], roi[0]:roi[2]], pool='stacks')
            total += 1
            if pred is not None and abs(float(val) - pred) < 0.01:
                correct += 1
            elif pred is not None:
                errors.append(f'{fname[:35]:35s} {field:20s} true={val!r:10s} pred={pred!r:10s}')
            else:
                errors.append(f'{fname[:35]:35s} {field:20s} true={val!r:10s} pred=None')

    dt = time.perf_counter() - t0
    print(f'\n=== Verification ===')
    print(f'  {dt*1000:.0f}ms')
    if total:
        print(f'  {correct}/{total} = {100*correct/total:.1f}%')
    if errors:
        print(f'  Errors ({len(errors)}):')
        for e in errors[:30]:
            print(f'    {e}')
