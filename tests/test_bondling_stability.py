import ast
from datetime import time as Time
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tasks/BondlingFairyland/script_task.py'

def load(name, extra=None):
    node = next(n for n in ast.walk(ast.parse(SOURCE.read_text(encoding='utf-8')))
                if isinstance(n, ast.FunctionDef) and n.name == name)
    env = dict(GamePageUnknownError=RuntimeError, GameStuckError=RuntimeError, ScriptError=RuntimeError,
               logger=SimpleNamespace(info=lambda *a: None, warning=lambda *a: None), time=Time)
    env.update(extra or {})
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), env)
    return env[name]

class Timer:
    def __init__(self, seconds): self.seconds, self.calls = seconds, 0
    def start(self): return self
    def reached(self):
        self.calls += 1
        return self.calls > 10

class StabilityTest(unittest.TestCase):
    def test_private_must_be_confirmed_before_create(self):
        fake = SimpleNamespace(ensure_private=lambda: False,
                               create_ensure=lambda **kw: self.fail('created public room'))
        with self.assertRaises(RuntimeError): load('_create_private_bond_team')(fake)

    def test_private_creation_uses_bondling_button(self):
        seen = []
        fake = SimpleNamespace(ensure_private=lambda: True, I_CREATE_TEAM='bondling_create',
                               create_ensure=lambda **kw: seen.append(kw) or True)
        self.assertTrue(load('_create_private_bond_team')(fake))
        self.assertEqual(seen, [{'ensure_rules': ['bondling_create']}])

    def test_settings_disable_marker_clears_before_return(self):
        state = {'disabled': True, 'clicks': 0}
        def click(*a, **kw): state.update(disabled=False, clicks=state['clicks']+1)
        fake = SimpleNamespace(screenshot=lambda: None, I_CAPTION_ENSURE='dialog',
            appear=lambda rule: rule == 'dialog' or state['disabled'], appear_then_click=click)
        load('_enable_capture_option', {'Timer': Timer})(fake, 'disabled')
        self.assertEqual(state['clicks'], 1)

    def test_settings_closed_is_not_success(self):
        fake = SimpleNamespace(screenshot=lambda: None, I_CAPTION_ENSURE='dialog', appear=lambda _: False)
        with self.assertRaises(RuntimeError):
            load('_enable_capture_option', {'Timer': Timer})(fake, 'disabled')

    def test_late_invitation_waits_instead_of_leaving(self):
        class Fake:
            def __getattr__(self, name): return name
            def screenshot(self): pass
            def appear(self, rule): return rule == 'I_CHECK_BONDLING_FAIRYLAND'
            def is_in_room(self, *a): return False
            def exit_room(self): raise AssertionError('must wait for next invite')
        fake = Fake()
        self.assertIsNone(load('wait_battle', {'Timer': Timer})(fake, Time(1, 2, 3)))
        self.assertEqual(fake.timer_wait.seconds, 3723)

    def test_abandon_skipped_on_success(self):
        fake = SimpleNamespace(I_CAP_SUCCESS='success', I_BATTLE_SUCCESS='win', appear=lambda _: True)
        self.assertFalse(load('_handle_battle_fail_abandon', {'Timer': Timer})(fake))

    def test_locked_room_does_not_click_prepare(self):
        fake = SimpleNamespace(_room_locked=True)
        fn = load('_prepare_click_ready', {'BattleContext': object, 'GeneralBattleConfig': object})
        self.assertFalse(fn(fake, object(), object()))

    def test_private_create_failure_does_not_silently_loop(self):
        fake = SimpleNamespace(ensure_private=lambda: True, I_CREATE_TEAM='create',
                               create_ensure=lambda **kw: False)
        with self.assertRaises(RuntimeError): load('_create_private_bond_team')(fake)

    def test_stale_capture_page_returns_to_search(self):
        state = {'capture': True, 'back': 0}
        def click(*a, **kw):
            state.update(capture=False, back=state['back']+1)
            return True
        fake = SimpleNamespace(goto_page=lambda _: None, screenshot=lambda: None,
            in_catch_ui=lambda: state['capture'], I_BALL_HELP='help', I_UI_BACK_YELLOW='back',
            I_BF_STORE='store', appear=lambda rule: rule == 'store' and not state['capture'],
            appear_then_click=click)
        load('goto_bondling_search', {'Timer': Timer, 'page_bondling_fairyland': 'bondling'})(fake)
        self.assertEqual(state['back'], 1)

    def test_transient_courtyard_does_not_end_wait(self):
        class Fake:
            frame = 0
            def __getattr__(self, name): return name
            def screenshot(self): self.frame += 1
            def appear(self, rule):
                return ((self.frame == 1 and rule == 'I_CHECK_MAIN')
                        or (self.frame >= 3 and rule == 'I_EXIT'))
            def is_in_room(self, *a): return False
            def exit_room(self): raise AssertionError('transient page must not destroy room')
        self.assertTrue(load('wait_battle', {'Timer': Timer})(Fake(), Time(0, 1)))

if __name__ == '__main__': unittest.main()
