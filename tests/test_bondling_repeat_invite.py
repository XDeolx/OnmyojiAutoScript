import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tasks/BondlingFairyland/script_task.py'

class RepeatInviteTest(unittest.TestCase):
    def run_dialog(self, checkbox='unchecked', stuck=False, present=True):
        clock = [0]
        class Timer:
            def __init__(self, seconds): self.seconds, self.start_at = seconds, clock[0]
            def start(self): return self
            def reached(self): return clock[0] - self.start_at >= self.seconds
        class Fake:
            I_GI_SURE = 'confirm'
            I_I_DEFAULT = 'checked'
            I_I_NO_DEFAULT = 'unchecked'
            visible = present
            state = checkbox
            clicks = []
            def screenshot(self): clock[0] += 0.5
            def appear(self, rule):
                return self.visible and (rule == 'confirm' or rule == self.state)
            def appear_then_click(self, rule, **kw):
                if not self.appear(rule): return False
                self.clicks.append(rule)
                if rule == 'unchecked': self.state = 'checked'
                elif rule == 'confirm' and not stuck: self.visible = False
                return True
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'check_and_invite')
        env = dict(Timer=Timer, GameStuckError=RuntimeError, logger=SimpleNamespace(warning=lambda _: None))
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), env)
        fake = Fake()
        result = env['check_and_invite'](fake)
        return result, fake.clicks

    def test_checkbox_then_confirmation(self):
        self.assertEqual(self.run_dialog(), (True, ['unchecked', 'confirm']))

    def test_checked_checkbox_not_toggled_off(self):
        self.assertEqual(self.run_dialog('checked'), (True, ['confirm']))

    def test_missing_checkbox_still_confirms_current_invite(self):
        self.assertEqual(self.run_dialog('missing'), (True, ['confirm']))

    def test_no_dialog_no_click(self):
        self.assertEqual(self.run_dialog(present=False), (False, []))

    def test_stuck_confirmation_is_bounded(self):
        with self.assertRaises(RuntimeError): self.run_dialog(stuck=True)

if __name__ == '__main__': unittest.main()
