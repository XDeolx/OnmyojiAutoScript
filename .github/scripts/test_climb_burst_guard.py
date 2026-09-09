"""Run with toolkit/python.exe -B .github/scripts/test_climb_burst_guard.py."""
import importlib.util
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


SOURCE_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = Path(os.environ.get('OAS_TEST_RUNTIME_ROOT', SOURCE_ROOT))
sys.path.insert(0, str(RUNTIME_ROOT))


def load_source(name, relative):
    spec = importlib.util.spec_from_file_location(name, SOURCE_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


planner_module = load_source(
    'tasks.ActivityShikigami.settlement_behavior',
    'tasks/ActivityShikigami/settlement_behavior.py',
)
base_module = load_source(
    'tasks.ActivityShikigami.base_act', 'tasks/ActivityShikigami/base_act.py',
)
BaseAct = base_module.BaseAct
BattleAction = base_module.BattleAction
GeneralBattle = base_module.GeneralBattle


def make_planner():
    return planner_module.ClimbSettlementPlanner(
        detail_enabled=False, detail_interval_min=20, detail_interval_max=40,
        detail_delay_min=1, detail_delay_max=1.5, burst_percent=5,
    )


def make_task(mode='ap', penta=False):
    task = object.__new__(BaseAct)
    task.__dict__['conf'] = SimpleNamespace(
        general_climb=SimpleNamespace(
            run_sequence_v=[mode], fatigue_rest_enable=True,
            fatigue_rest_battle_count=60, pass_limit_for=lambda mode: 100,
        ),
        ap_battle_conf=object(), pass_battle_conf=object(),
    )
    task.run_idx = 0
    task.current_pass_mode = 'hard' if mode == 'pass' else None
    task.pass_action_count = {'easy': 0, 'hard': 0}
    task.penta_pass_active = penta
    task.climb_pending_consumption = {}
    task.climb_consumable_count = {}
    task._fatigue_battle_count = 0
    task._climb_burst_pending = False
    task._climb_burst_next_battle = False
    task.device = MagicMock()
    task.screenshot = MagicMock()
    task.is_in_real_battle = MagicMock(return_value=False)
    task.is_in_prepare = MagicMock(return_value=False)
    task._get_settlement_planner = MagicMock(return_value=make_planner())
    task._restore_climb_mode_after_burst = MagicMock()
    return task


class BurstGuardTests(unittest.TestCase):
    def setUp(self):
        self.log_patch = patch.object(base_module, 'logger')
        self.log_patch.start()
        self.addCleanup(self.log_patch.stop)

    def test_points_cover_full_diamond_and_each_burst_stays_clustered(self):
        random.seed(20260909)
        planner = make_planner()
        region = planner_module.BURST_CHALLENGE_REGION
        points = []
        for _ in range(2000):
            burst = planner.burst_points()
            self.assertIn(len(burst), (3, 4))
            self.assertTrue(all(region.contains(p) for p in burst))
            # Actual switch icon from assets.py, not its oversized search/exclusion ROI.
            for other_button in ((1233, 547, 1262, 573), (1015, 560, 1054, 602)):
                self.assertTrue(all(not planner_module.point_in_bounds(p, other_button) for p in burst))
            self.assertLessEqual(max(x for x, y in burst) - min(x for x, y in burst), 14)
            self.assertLessEqual(max(y for x, y in burst) - min(y for x, y in burst), 12)
            points.extend(burst)
        # Verify all four tips are reachable; the old center inset fails this.
        self.assertLess(min(x for x, y in points), 1115)
        self.assertGreater(max(x for x, y in points), 1237)
        self.assertLess(min(y for x, y in points), 566)
        self.assertGreater(max(y for x, y in points), 688)
        self.assertFalse(region.contains((1105, 556)))
        self.assertFalse(region.contains((1247, 698)))

    def test_edge_anchor_jitter_never_leaves_button(self):
        planner = make_planner()
        region = planner_module.BURST_CHALLENGE_REGION
        for tip in ((1105, 627), (1247, 627), (1176, 556), (1176, 698)):
            with patch.object(planner_module.DiamondRegion, 'sample', return_value=tip):
                self.assertTrue(all(region.contains(p) for p in planner.burst_points()))

    def test_burst_keeps_fast_group_then_checks_for_new_battle(self):
        task = make_task()
        task.is_in_real_battle.return_value = True
        points = [(1170, 620), (1173, 624), (1171, 626)]
        task._get_settlement_planner.return_value.burst_points = lambda: points
        with patch.object(base_module.time, 'sleep') as sleep:
            self.assertTrue(task._execute_climb_burst(reason='random', battle_number=1))
        self.assertEqual(task.device.click.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        task.screenshot.assert_called_once()
        self.assertTrue(task._climb_burst_next_battle)

    def test_old_reward_is_not_a_new_battle(self):
        task = make_task()
        task._climb_burst_pending = True
        task.is_in_battle = MagicMock(return_value=True)
        self.assertFalse(task._capture_climb_burst_next_battle())
        task.is_in_battle.assert_not_called()

    def test_preparation_and_direct_combat_both_finish_previous_round(self):
        for method, indicator in (('_handle_prepare', 'is_in_prepare'),
                                  ('_handle_in_battle', 'is_in_real_battle')):
            task = make_task()
            task._climb_burst_pending = True
            getattr(task, indicator).return_value = True
            with patch.object(GeneralBattle, method) as parent:
                self.assertEqual(getattr(task, method)(object(), object()), BattleAction.EXIT_WIN)
                parent.assert_not_called()
            self.assertTrue(task._climb_burst_next_battle)

    def test_regular_combat_uses_existing_handler(self):
        task = make_task()
        task.is_in_real_battle.return_value = True
        with patch.object(GeneralBattle, '_handle_in_battle', return_value=BattleAction.CONTINUE) as parent:
            self.assertEqual(task._handle_in_battle(object(), object()), BattleAction.CONTINUE)
            parent.assert_called_once()

    def test_delayed_entry_after_last_tap_is_detected(self):
        task = make_task()
        task._climb_burst_pending = True
        task.is_in_real_battle.side_effect = [False, False, True]
        with patch.object(base_module.time, 'monotonic', side_effect=[0, 0, 1, 2]), \
                patch.object(base_module.time, 'sleep'):
            self.assertTrue(task._confirm_climb_burst_next_battle())
        self.assertFalse(task._climb_burst_pending)
        self.assertFalse(task._climb_burst_next_battle)
        self.assertFalse(task._climb_mode_review_pending)

    def test_no_entry_has_bounded_wait(self):
        task = make_task()
        task._climb_burst_pending = True
        with patch.object(base_module.time, 'monotonic', side_effect=[0, 0, 1, 5]), \
                patch.object(base_module.time, 'sleep'):
            self.assertFalse(task._confirm_climb_burst_next_battle())
        self.assertEqual(task.screenshot.call_count, 2)
        self.assertFalse(task._climb_burst_pending)

    def test_confirmed_entry_is_consumed_once(self):
        task = make_task()
        task._climb_burst_pending = True
        task._climb_burst_next_battle = True
        self.assertTrue(task._confirm_climb_burst_next_battle())
        self.assertFalse(task._confirm_climb_burst_next_battle())
        task.screenshot.assert_not_called()

    def test_takeover_counts_each_round_and_accumulates_resources(self):
        for mode, penta, expected in (
            ('ap', False, {'ap': 12, 'ap_pass': 2, 'penta_pass': 0}),
            ('ap', True, {'ap': 60, 'ap_pass': 10, 'penta_pass': 2}),
            ('pass', False, {'pass': 10}),
        ):
            task = make_task(mode, penta)
            calls = []

            def battle(config, **kwargs):
                calls.append(config)
                if len(calls) == 1:
                    task._climb_burst_pending = True
                    task._climb_burst_next_battle = True

            task.run_general_battle = battle
            task.enter_battle = MagicMock()
            task.check_tickets_enough = MagicMock()
            task._run_entered_climb_battles()
            self.assertEqual(len(calls), 2)
            self.assertEqual(task._fatigue_battle_count, 2)
            self.assertEqual(task.climb_pending_consumption, expected)
            if mode == 'pass':
                self.assertEqual(task.pass_action_count, {'easy': 0, 'hard': 2})
            else:
                self.assertEqual(task.count_map['ap'], 2)
            task.enter_battle.assert_not_called()
            task.check_tickets_enough.assert_not_called()
            task._restore_climb_mode_after_burst.assert_called_once()

    def test_both_detail_and_random_burst_propagate_immediate_entry(self):
        for kind in ('detail', 'burst'):
            task = make_task()
            task.appear_then_click = MagicMock(return_value=False)
            task._begin_climb_settlement = MagicMock(return_value=SimpleNamespace(kind=kind, battle_number=1))
            task._execute_climb_detail = MagicMock(return_value=True)
            task._execute_climb_burst = MagicMock(return_value=True)
            context = SimpleNamespace(last_page=None)
            self.assertEqual(task._handle_climb_reward(context), BattleAction.EXIT_WIN)
            self.assertTrue(context.climb_settlement_special_done)

    def test_real_battle_loop_rebuilds_context_for_burst_takeover(self):
        task = make_task()
        task.current_count = 0
        task._custom_pages_registered = True
        task.conf.ap_battle_conf = SimpleNamespace(continuous_battle=False)
        frames = iter(['battle', 'reward', 'prepare', 'battle', 'reward', 'main'])
        task.screenshot = lambda: setattr(task, 'frame', next(frames))
        task.is_in_real_battle = lambda _: task.frame == 'battle'
        task.is_in_prepare = lambda _: task.frame == 'prepare'
        for name in ('_tick_long_battle', '_tick_timeout', '_sync_prepare_click_timer',
                     '_ensure_battle_stuck_guard'):
            setattr(task, name, MagicMock())
        contexts = []

        def build_context(*args):
            context = SimpleNamespace(last_page=None, quick_exit=False, is_win=False,
                                      reward_no_battle_ts=None)
            contexts.append(context)
            return context

        task._build_context = build_context
        task._evaluate_exit_matcher = lambda _: task.frame == 'main'

        def reward(context, config):
            context.is_win = True
            if len(contexts) == 1:
                if task._execute_climb_burst(reason='random', battle_number=1):
                    return BattleAction.EXIT_WIN
            return BattleAction.CONTINUE

        task._handle_reward = reward
        frame_pages = {'battle': base_module.pages.page_battle,
                       'prepare': base_module.pages.page_battle_prepare,
                       'reward': base_module.pages.page_reward, 'main': None}
        with patch.object(base_module.GameUi, 'detect_page_in', side_effect=lambda *a, **k: frame_pages[task.frame]), \
                patch.object(GeneralBattle, '_handle_in_battle', return_value=BattleAction.CONTINUE), \
                patch.object(base_module.time, 'sleep'):
            task._run_entered_climb_battles()
        self.assertEqual(task.current_count, 2)
        self.assertEqual(task.count_map['ap'], 2)
        self.assertEqual(task._fatigue_battle_count, 2)
        self.assertEqual(task.climb_pending_consumption['ap'], 12)
        self.assertEqual(len(contexts), 2)
        self.assertIsNot(contexts[0], contexts[1])
        self.assertIsNone(task._battle_context)


if __name__ == '__main__':
    unittest.main(verbosity=2)
