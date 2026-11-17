import importlib.util
from pathlib import Path
import unittest

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ticket_stars", ROOT / "tasks/MetaDemon/ticket_stars.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
recognize = module.recognize_ticket_stars


class PortraitStarsTest(unittest.TestCase):
    def test_four_star_gold_background(self):
        data = np.fromfile(str(ROOT / "tests/fixtures/metademon_four_star_portrait.png"), np.uint8)
        image = cv2.cvtColor(cv2.imdecode(data, 1), cv2.COLOR_BGR2RGB)
        self.assertEqual(recognize(image, (0, 0, 80, 82), portrait=True), 4)

    def card(self, stars, hue=20):
        hsv = np.zeros((72, 72, 3), dtype=np.uint8)
        for index, center in enumerate((11, 21, 31, 41, 51, 61)):
            hsv[55:70, center - 3:center + 3] = (hue, 220, 220) if index < stars else (0, 0, 120)
        return hsv

    def recognize_hsv(self, hsv):
        return recognize(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB), (0, 0, 72, 72), portrait=True)

    def test_orange_and_awakened_stars(self):
        for hue in (20, 145):
            for stars in range(1, 7):
                with self.subTest(hue=hue, stars=stars):
                    self.assertEqual(self.recognize_hsv(self.card(stars, hue)), stars)

    def test_ambiguity_without_grey_stays_unknown(self):
        hsv = self.card(4)
        hsv[55:70, 48:54] = (80, 220, 220)
        hsv[55:59, 48:54] = (20, 220, 220)
        self.assertIsNone(self.recognize_hsv(hsv))

    def test_noncontiguous_and_empty_stay_unknown(self):
        hsv = self.card(4)
        hsv[55:70, 18:24] = (0, 0, 120)
        self.assertIsNone(self.recognize_hsv(hsv))
        self.assertIsNone(self.recognize_hsv(self.card(0)))


if __name__ == "__main__":
    unittest.main()
