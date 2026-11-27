import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
import cv2
import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / 'tasks/BondlingFairyland/script_task.py'


class StoneStockTest(unittest.TestCase):
    def read(self, values, visible=True):
        node = next(n for n in ast.walk(ast.parse(SOURCE.read_text(encoding='utf-8')))
                    if isinstance(n, ast.FunctionDef) and n.name == '_read_stone_stock')
        env = dict(copy=copy, cv2=cv2, sleep=lambda _: None,
                   GameStuckError=RuntimeError, GamePageUnknownError=ValueError)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), env)
        results = iter(values)
        rule = SimpleNamespace(roi=(0, 0, 78, 32), crop=lambda *a: np.zeros((32, 78, 3), np.uint8),
                               ocr=lambda _: next(results))
        fake = SimpleNamespace(O_B_STONE_NUMBER=rule, screenshot=lambda: None,
                               appear=lambda _: visible, I_STONE_SURE='dialog',
                               device=SimpleNamespace(image=None))
        return env['_read_stone_stock'](fake)

    def test_invalid_then_stock(self):
        self.assertEqual(self.read([(0, 0, 0), (7, 23, 30), (7, 23, 30)]), 7)

    def test_zero_requires_two_valid_frames(self):
        self.assertEqual(self.read([(0, 30, 30), (0, 0, 0), (7, 23, 30), (7, 23, 30)]), 7)
        self.assertEqual(self.read([(0, 30, 30)] * 2), 0)

    def test_unreadable_does_not_mean_empty(self):
        with self.assertRaises(RuntimeError):
            self.read([(0, 0, 0)] * 5)

    def test_changed_or_invalid_counts_rejected(self):
        with self.assertRaises(RuntimeError):
            self.read([(7, 23, 30), (1, 29, 30), (7, 23, 30), (31, -1, 30), (0, 0, 0)])

    def test_missing_dialog(self):
        with self.assertRaises(ValueError):
            self.read([], visible=False)


if __name__ == '__main__':
    unittest.main()
