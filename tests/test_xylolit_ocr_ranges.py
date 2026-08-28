import json
import unittest
from pathlib import Path


class XylolitOcrRangeTest(unittest.TestCase):
    def _load(self, path):
        root = Path(__file__).resolve().parents[1]
        with (root / path).open(encoding='utf-8') as stream:
            return {item['itemName']: item for item in json.load(stream)}

    def test_bondling_ranges(self):
        rules = self._load('tasks/BondlingFairyland/bf/ocr.json')
        self.assertEqual(rules['b_bondling_class']['roiBack'], '266,271,79,112')
        self.assertEqual(rules['b_low_number']['roiFront'], '540,12,107,40')
        self.assertEqual(rules['b_medium_number']['roiFront'], '728,15,113,35')
        self.assertEqual(rules['b_high_number']['roiFront'], '922,9,102,41')

    def test_sougenbi_ranges(self):
        rules = self._load('tasks/Sougenbi/s/ocr.json')
        self.assertEqual(rules['s_greed']['roiFront'], '590,20,84,34')
        self.assertEqual(rules['s_anger']['roiFront'], '770,18,84,36')
        self.assertEqual(rules['s_foolery']['roiFront'], '944,18,86,34')


if __name__ == '__main__':
    unittest.main()
