import os
import json
import subprocess
import re
from PIL import Image
import numpy as np

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_DIR, 'data', 'calib_1365.json')

with open(JSON_PATH) as f:
    calib = json.load(f)

TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class NumberReader:
    def __init__(self):
        self.pot_coords = calib['pot']
        self.player_stacks = calib['player_stacks']
        self.buttons = calib['buttons']
        self.screen_seats = calib['screen_seats']
        self.seat_order = calib['seat_order']

    def _ocr_region(self, crop, whitelist='0123456789Kk.'):
        """Run tesseract on a cropped PIL image region."""
        crop_rgb = Image.new('RGB', crop.size)
        crop_rgb.paste(crop)
        temp_path = os.path.join(os.environ.get('TEMP', INFO_DIR), '_ocr_temp.png')
        crop_rgb.save(temp_path)

        result = subprocess.run([
            TESSERACT_PATH, temp_path, 'stdout',
            '--psm', '7',
            '-c', f'tessedit_char_whitelist={whitelist}',
        ], capture_output=True, text=True, timeout=10)

        try:
            os.remove(temp_path)
        except:
            pass

        return result.stdout.strip()

    def _parse_number(self, text):
        """Parse OCR text into a float, handling K suffix."""
        text = text.strip()
        if not text:
            return None
        # Remove non-numeric except . and K/k
        text = re.sub(r'[^0-9.Kk]', '', text)
        if not text:
            return None
        # Handle K suffix (thousands)
        if text.upper().endswith('K'):
            try:
                val = float(text[:-1].rstrip('.'))
                return val * 1000
            except ValueError:
                pass
        try:
            return float(text)
        except ValueError:
            return None

    def read_pot(self, screenshot):
        """Read the pot amount."""
        crop = screenshot.crop(tuple(self.pot_coords))
        text = self._ocr_region(crop)
        return self._parse_number(text)

    def read_player_stack(self, screenshot, player):
        """Read a player's stack by name (hero, p1-p5)."""
        if player not in self.player_stacks:
            return None
        crop = screenshot.crop(tuple(self.player_stacks[player]))
        text = self._ocr_region(crop)
        return self._parse_number(text)

    def read_all_stacks(self, screenshot):
        """Read all player stacks. Returns dict of name -> amount."""
        stacks = {}
        for name, coords in self.player_stacks.items():
            crop = screenshot.crop(tuple(coords))
            text = self._ocr_region(crop)
            val = self._parse_number(text)
            stacks[name] = val
        return stacks

    def read_raise_input(self, screenshot):
        """Read the raise value input box."""
        coords = self.buttons.get('value_input')
        if not coords:
            return None
        crop = screenshot.crop(tuple(coords))
        text = self._ocr_region(crop)
        return self._parse_number(text)

    def read_button_states(self, screenshot):
        """Detect which action buttons are available based on mean pixel color."""
        states = {}
        for name, coords in self.buttons.items():
            if name == 'value_input':
                continue
            crop = np.array(screenshot.crop(tuple(coords)).convert('RGB'))
            # Check if button is active by looking for non-background pixels
            mean = crop.mean()
            # Active buttons tend to have colored text/icons (mean != background)
            states[name] = mean < 200
        return states

    def read_all(self, screenshot):
        """Read all numbers and states from the screenshot."""
        return {
            'pot': self.read_pot(screenshot),
            'stacks': self.read_all_stacks(screenshot),
            'raise_input': self.read_raise_input(screenshot),
            'button_states': self.read_button_states(screenshot),
        }


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore
    reader = NumberReader()
    cap_dir = os.path.join(INFO_DIR, 'capturas')

    print('=== Number reader test ===')
    for fname in sorted(os.listdir(cap_dir)):
        if fname.endswith('.png') and fname.startswith('Captura'):
            img = Image.open(os.path.join(cap_dir, fname))
            pot = reader.read_pot(img)
            stack = reader.read_player_stack(img, 'hero')
            print(f'  {fname:40s} pot={pot!s:>10s}  hero_stack={stack!s:>10s}')
