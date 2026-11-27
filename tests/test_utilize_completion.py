import ast
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(path, name, env):
    node = next(n for n in ast.walk(ast.parse((ROOT / path).read_text(encoding='utf-8')))
                if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), env)
    return env[name]

class CompletionTest(unittest.TestCase):
    def checker(self, frames):
        iterator = iter(frames)
        return load('tasks/KekkaiUtilize/script_task.py', '_utilize_completion_check', {})(
            NS(_utilize_countdowns=lambda: next(iterator)))

    def test_new_timer_in_either_slot_requires_two_frames(self):
        for values in ([21590, 0], [0, 21590]):
            check = self.checker([[0, 0], values, values])
            self.assertFalse(check())
            self.assertTrue(check())

    def test_existing_guest_and_invalid_timer_are_not_completion(self):
        check = self.checker([[21000, 0], [20999, 0], [20998, 0]])
        self.assertFalse(check())
        self.assertFalse(check())
        check = self.checker([[0, 0], [90000, 0], [90000, 0]])
        self.assertFalse(check())
        self.assertFalse(check())

    def test_confirmation_stops_roster_clicks_even_if_empty_marker_remains(self):
        class Timer:
            def __init__(self, *a): pass
            def start(self): return self
            def reached_and_reset(self): return True
        calls = []
        checks = iter([False, True])
        fake = NS(**{'C_SHIKIGAMI_LEFT_' + str(i): i for i in range(1, 8)})
        fake.I_U_CONFIRM_SMALL = 'confirm'
        fake.screenshot = lambda: None
        fake.appear_then_click = lambda *a, **kw: calls.append('confirm') or True
        fake.appear = lambda *a: True
        fake.click = lambda *a, **kw: self.fail('clicked roster after confirmation')
        fn = load('tasks/Component/ReplaceShikigami/replace_shikigami.py', 'set_shikigami',
                  {'RuleImage': object, 'Timer': Timer, 'time': NS(time=lambda: 0),
                   'GameStuckError': RuntimeError, 'logger': NS(info=lambda *a: None, error=lambda *a: None)})
        fn(fake, 4, object(), completion_check=lambda: next(checks))
        self.assertEqual(calls, ['confirm'])

if __name__ == '__main__': unittest.main()
