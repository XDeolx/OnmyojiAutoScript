import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tasks/DemonEncounter/script_task.py'

class Timer:
    def __init__(self, seconds): self.seconds, self.ticks = seconds, 0
    def start(self): return self
    def reset(self): self.ticks = 0
    def reached(self):
        self.ticks += 1
        return self.seconds < 10 and self.ticks >= 2

def method(name, nested=None):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ScriptTask')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    if nested:
        node = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == nested)
    logger = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, hr=lambda *a: None)
    env = dict(Timer=Timer, logger=logger, time=SimpleNamespace(sleep=lambda _: None),
               Answer=lambda: SimpleNamespace(answer_one=lambda **_: 1))
    return node, env

class TransitionsTest(unittest.TestCase):
    def test_new_reward_must_clear_before_next_question(self):
        node, env = method('_mail')
        class Fake:
            state = 'question'
            question = 1
            reward_clicks = 0
            frames = 0
            answered = 0
            device = SimpleNamespace(image=None)
            def __getattr__(self, name):
                if name.startswith('O_'):
                    return SimpleNamespace(detect_text=self.ocr)
                return name
            def ocr(self, image):
                assert self.state == 'question', 'OCR read a reward overlay'
                return 'question'
            def screenshot(self):
                self.frames += 1
                assert self.frames < 100, 'did not finish'
            def appear(self, item, **kwargs):
                return item == 'I_LETTER_CLOSE' and self.state == 'question'
            def click(self, item, **kwargs):
                assert self.state == 'question'
                self.answered += 1
                self.state = 'reward'
                self.reward_clicks = 0
                return True
            def ui_reward_appear_click(self):
                if self.state != 'reward': return False
                self.reward_clicks += 1
                if self.reward_clicks == 3:
                    self.question += 1
                    self.state = 'question' if self.question <= 3 else 'map'
                return True
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), env)
        fake = Fake()
        env['_mail'](fake, 'lantern')
        self.assertEqual(fake.answered, 3)
        self.assertEqual(fake.state, 'map')

    def test_boss_retries_swallowed_map_click(self):
        node, env = method('execute_boss', 'find_boss')
        class Fake:
            best_demon_enable = False
            clicks = 0
            frames = 0
            device = SimpleNamespace(click_record_remove=lambda _: None)
            def __getattr__(self, name): return name
            def screenshot(self):
                self.frames += 1
                assert self.frames < 10, 'boss was never retried'
            def appear(self, item):
                return ((item == 'I_BOSS_FIRE' and self.clicks == 2)
                        or item in ('I_DE_LOCATION', 'I_DE_BOSS'))
            def click(self, item, **kwargs):
                if item == 'C_DM_BOSS_CLICK': self.clicks += 1
                return True
        fake = Fake()
        env['self'] = fake
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), env)
        self.assertTrue(env['find_boss']())
        self.assertEqual(fake.clicks, 2)

if __name__ == '__main__': unittest.main()
