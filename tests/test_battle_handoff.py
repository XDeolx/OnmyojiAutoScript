import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tasks/Component/GeneralBattle/general_battle.py'

class BattleHandoffTest(unittest.TestCase):
    def setup_task(self, page):
        clock = [100.0]
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        names = {'_inherit_current_battle_frame', '_mark_battle_started', '_battle_age',
                 '_can_record_current_battle_result', '_guard_unconfirmed_settlement'}
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GeneralBattle')
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
        env = {'BattleContext': object, 'page_battle': 'battle', 'MIN_BATTLE_RESULT_DELAY': 1.0,
               'time': SimpleNamespace(time=lambda: clock[0]), 'GameStuckError': RuntimeError,
               'logger': SimpleNamespace(info=lambda _: None),
               'GameUi': SimpleNamespace(detect_page_in=lambda *a, **kw: page)}
        node = ast.ClassDef(name='Task', bases=[], keywords=[], body=methods, decorator_list=[])
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(SOURCE), 'exec'), env)
        context = SimpleNamespace(battle_started_at=None, last_page=None, outcome_ready=False,
                                  is_win=False, reward_no_battle_ts=None, unconfirmed_settlement_ts=None)
        return env['Task'](), context, clock

    def test_battle_frame_then_fast_reward_can_record(self):
        task, ctx, clock = self.setup_task('battle')
        task._inherit_current_battle_frame(ctx)
        clock[0] += 3
        self.assertTrue(task._can_record_current_battle_result(ctx))

    def test_reward_without_battle_is_not_a_win(self):
        task, ctx, clock = self.setup_task('reward')
        task._inherit_current_battle_frame(ctx)
        clock[0] += 3
        self.assertFalse(task._can_record_current_battle_result(ctx))
        self.assertFalse(ctx.outcome_ready)

    def test_unconfirmed_reward_wait_is_bounded(self):
        task, ctx, clock = self.setup_task('reward')
        task._guard_unconfirmed_settlement(ctx)
        clock[0] += 15
        with self.assertRaises(RuntimeError): task._guard_unconfirmed_settlement(ctx)

    def test_confirmed_caller_survives_reward_as_first_frame(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'run_general_battle')
        ctx = SimpleNamespace(reward_no_battle_ts=None, quick_exit=False, last_page=None)
        events = []
        class Fake:
            _custom_pages_registered = True
            current_count = 0
            device = SimpleNamespace(stuck_record_add=lambda _: None, click_record_clear=lambda: None,
                                     screenshot_interval_set=lambda *a: None)
            def _build_context(self, *a): return ctx
            def _exit_matcher(self): return None
            def _mark_battle_started(self, context): events.append('confirmed')
            def _inherit_current_battle_frame(self, context): raise AssertionError('must not re-detect caller evidence')
            def screenshot(self): events.append('reward_frame')
            def _tick_long_battle(self, context): pass
            def _tick_timeout(self, context): pass
            def _sync_prepare_click_timer(self, *a): pass
            def _ensure_battle_stuck_guard(self, *a): pass
            gb_page_handle_dict = {'reward': lambda *a: 'done'}
            def _resolve_action(self, action, context): return True
        env = dict(GeneralBattleConfig=object, Union=__import__('typing').Union, BuffClass=object,
                   ExitMatcher=object, GameUi=SimpleNamespace(detect_page_in=lambda *a, **kw: 'reward'),
                   logger=SimpleNamespace(info=lambda _: None, hr=lambda *a: None),
                   page_battle_prepare='prepare', page_battle='battle', page_battle_result='result', page_reward='reward')
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), env)
        self.assertTrue(env['run_general_battle'](Fake(), battle_confirmed=True))
        self.assertEqual(events, ['confirmed', 'reward_frame'])

if __name__ == '__main__': unittest.main()
