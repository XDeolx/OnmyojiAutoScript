from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from tasks.ActivityShikigami.base_act import BaseAct
from tasks.ActivityShikigami.config import GeneralClimb
from tasks.ActivityShikigami.settlement_behavior import (
    CATEGORY_COUNTS,
    CATEGORY_POOLS,
    DETAIL_REGIONS,
    MODE_SWITCH_EXCLUSION,
    SETTLEMENT_REGIONS,
    ClimbSettlementPlanner,
    point_in_bounds,
)
from tasks.Component.GeneralBattle.general_battle import BattleAction


class ActivityShikigamiSettlementPlannerTest(unittest.TestCase):
    @staticmethod
    def create_planner(**overrides):
        values = {
            'detail_enabled': True,
            'detail_interval_min': 20,
            'detail_interval_max': 40,
            'detail_delay_min': 1.0,
            'detail_delay_max': 1.5,
            'burst_percent': 5,
        }
        values.update(overrides)
        return ClimbSettlementPlanner(**values)

    def test_task_template_selects_the_requested_region_counts(self):
        planner = self.create_planner()

        for category, indexes in planner.template.items():
            self.assertEqual(len(indexes), CATEGORY_COUNTS[category])
            self.assertEqual(len(indexes), len(set(indexes)))
            self.assertTrue(set(indexes).issubset(CATEGORY_POOLS[category]))
        self.assertEqual(planner.template['E'], (7,))

    def test_first_detail_trigger_uses_a_random_initial_phase(self):
        with patch(
            'tasks.ActivityShikigami.settlement_behavior.random.randint',
            side_effect=[30, 29, 25],
        ):
            planner = self.create_planner()
            decision = planner.begin_settlement()

        self.assertEqual(decision.kind, 'detail')
        self.assertEqual(decision.battle_number, 1)
        self.assertEqual(decision.detail_target, 30)
        self.assertEqual(planner.detail_progress, 0)
        self.assertEqual(planner.detail_target, 25)

    def test_random_burst_is_separate_from_the_detail_cycle(self):
        with patch(
            'tasks.ActivityShikigami.settlement_behavior.random.randint',
            side_effect=[20, 0],
        ):
            planner = self.create_planner(burst_percent=5)

        with patch('tasks.ActivityShikigami.settlement_behavior.random.random', return_value=0.01):
            decision = planner.begin_settlement()

        self.assertEqual(decision.kind, 'burst')
        self.assertEqual(decision.detail_progress, 1)
        self.assertEqual(decision.detail_target, 20)

    def test_weighted_click_stays_inside_the_selected_ellipse(self):
        planner = self.create_planner(detail_enabled=False)
        planner.template['A'] = (10, 11)

        with patch(
            'tasks.ActivityShikigami.settlement_behavior.random.choices',
            return_value=['A'],
        ) as choices, patch(
            'tasks.ActivityShikigami.settlement_behavior.random.choice',
            return_value=10,
        ):
            category, region_name, point = planner.weighted_point()

        self.assertEqual(category, 'A')
        self.assertEqual(region_name, 'R10')
        self.assertTrue(SETTLEMENT_REGIONS[10].contains(point, scale=0.82))
        self.assertEqual(choices.call_args.kwargs['weights'], (5, 5, 25, 20, 45))

    def test_burst_uses_three_or_four_low_offset_points_inside_r7(self):
        planner = self.create_planner(detail_enabled=False)

        points = planner.burst_points()

        self.assertIn(len(points), (3, 4))
        self.assertTrue(all(SETTLEMENT_REGIONS[7].contains(point, scale=0.82) for point in points))
        self.assertTrue(all(not point_in_bounds(point, MODE_SWITCH_EXCLUSION) for point in points))
        self.assertLessEqual(max(x for x, _ in points) - min(x for x, _ in points), 14)
        self.assertLessEqual(max(y for _, y in points) - min(y for _, y in points), 12)

    def test_detail_four_is_directly_above_detail_three(self):
        detail_three = DETAIL_REGIONS[3]
        detail_four = DETAIL_REGIONS[4]

        self.assertEqual(detail_four.bounds[0], detail_three.bounds[0])
        self.assertEqual(detail_four.bounds[2], detail_three.bounds[2])
        self.assertEqual(detail_four.bounds[3] - detail_four.bounds[1],
                         detail_three.bounds[3] - detail_three.bounds[1])
        self.assertLess(detail_four.bounds[3], detail_three.bounds[1])

    def test_detail_five_and_six_are_above_detail_one_and_two(self):
        for upper_id, lower_id in ((5, 1), (6, 2)):
            upper = DETAIL_REGIONS[upper_id]
            lower = DETAIL_REGIONS[lower_id]
            self.assertEqual(upper.bounds[0], lower.bounds[0])
            self.assertEqual(upper.bounds[2], lower.bounds[2])
            self.assertEqual(upper.bounds[3] - upper.bounds[1],
                             lower.bounds[3] - lower.bounds[1])
            self.assertLess(upper.bounds[3], lower.bounds[1])

    def test_pass_detail_uses_all_six_regions(self):
        planner = self.create_planner()

        with patch(
            'tasks.ActivityShikigami.settlement_behavior.random.choice',
            return_value=1,
        ) as choice:
            region_name, _point = planner.detail_point('pass')

        self.assertEqual(region_name, 'Detail1')
        self.assertEqual(choice.call_args.args[0], (1, 2, 3, 4, 5, 6))

    def test_non_pass_detail_uses_only_the_upper_row(self):
        planner = self.create_planner()

        with patch(
            'tasks.ActivityShikigami.settlement_behavior.random.choice',
            return_value=4,
        ) as choice:
            region_name, _point = planner.detail_point('ap')

        self.assertEqual(region_name, 'Detail4')
        self.assertEqual(choice.call_args.args[0], (4, 5, 6))

    def test_weighted_r7_never_uses_the_mode_switch_exclusion(self):
        planner = self.create_planner(detail_enabled=False)
        planner.template['E'] = (7,)

        with patch(
            'tasks.ActivityShikigami.settlement_behavior.random.choices',
            return_value=['E'],
        ):
            points = [planner.weighted_point()[2] for _ in range(500)]

        self.assertTrue(all(not point_in_bounds(point, MODE_SWITCH_EXCLUSION) for point in points))

    @patch('tasks.ActivityShikigami.base_act.GameUi.detect_page_in')
    def test_burst_mode_review_restores_the_expected_climb_type(self, detect_page):
        task = BaseAct.__new__(BaseAct)
        task.conf = SimpleNamespace(
            general_climb=SimpleNamespace(run_sequence_v=['pass']),
        )
        task.run_idx = 0
        task._climb_mode_review_pending = True
        task.screenshot = MagicMock()
        task.goto_page = MagicMock()
        detect_page.side_effect = [
            __import__('tasks.ActivityShikigami.page', fromlist=['page_act_ap']).page_act_ap,
            __import__('tasks.ActivityShikigami.page', fromlist=['page_act_pass']).page_act_pass,
        ]

        BaseAct._restore_climb_mode_after_burst(task)

        page_module = __import__('tasks.ActivityShikigami.page', fromlist=['page_act_pass'])
        task.goto_page.assert_called_once_with(page_module.page_act_pass)
        self.assertFalse(task._climb_mode_review_pending)

    def test_fatigue_guard_runs_before_the_custom_reward_handler(self):
        task = BaseAct.__new__(BaseAct)
        task.conf = SimpleNamespace(
            general_climb=SimpleNamespace(settlement_region_enable=True),
        )
        task._fatigue_settlement_click_ready = MagicMock(return_value=False)
        task._handle_climb_reward = MagicMock(return_value=BattleAction.CONTINUE)

        action = BaseAct._handle_reward(task, SimpleNamespace(), SimpleNamespace())

        self.assertEqual(action, BattleAction.CONTINUE)
        task._handle_climb_reward.assert_not_called()

        task._fatigue_settlement_click_ready.return_value = True
        action = BaseAct._handle_reward(task, SimpleNamespace(), SimpleNamespace())

        self.assertEqual(action, BattleAction.CONTINUE)
        task._handle_climb_reward.assert_called_once()

    def test_config_rejects_reversed_detail_ranges(self):
        with self.assertRaises(ValidationError):
            GeneralClimb(
                settlement_detail_interval_min=40,
                settlement_detail_interval_max=20,
            )
        with self.assertRaises(ValidationError):
            GeneralClimb(
                settlement_detail_delay_min=1.5,
                settlement_detail_delay_max=1.0,
            )


if __name__ == '__main__':
    unittest.main()
