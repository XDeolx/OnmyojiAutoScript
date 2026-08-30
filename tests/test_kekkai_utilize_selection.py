import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tasks.KekkaiUtilize.config import SelectFriendList, UtilizeRule
from tasks.KekkaiUtilize.page import (
    page_guild_realm_growth,
    page_guild_realm_utilize,
)
from tasks.KekkaiUtilize.script_task import ScriptTask
from tasks.Utils.config_enum import ShikigamiClass


class KekkaiUtilizeSelectionTest(unittest.TestCase):
    def _task(self, rule=UtilizeRule.DEFAULT):
        task = ScriptTask.__new__(ScriptTask)
        task.config = SimpleNamespace(
            kekkai_utilize=SimpleNamespace(
                utilize_config=SimpleNamespace(utilize_rule=rule)
            )
        )
        return task

    def test_duplicate_template_hits_keep_highest_confidence(self):
        task = self._task()
        area = (100, 200, 80, 40)
        cards = [
            (task.I_U_FISH_4, 0.84, area),
            (task.I_U_FISH_5, 0.93, area),
            (task.I_U_TAIKO_6, 0.88, (500, 200, 80, 40)),
        ]

        result = task._deduplicate_card_matches(cards)

        self.assertEqual(len(result), 2)
        self.assertIs(result[0][0], task.I_U_FISH_5)
        self.assertEqual(result[0][1], 0.93)
        self.assertEqual(len(result[0][3]), 2)

    def test_default_rule_relocates_best_recorded_card(self):
        task = self._task()

        def scan():
            task.ap_max_num = 118
            task.jade_max_num = 60
            return False

        task._current_select_best = Mock(side_effect=scan)
        task._reset_utilize_friend_list = Mock()
        task._locate_recorded_resource_card = Mock(return_value=True)

        with patch('tasks.KekkaiUtilize.script_task.logger'):
            self.assertTrue(
                task._select_optimal_resource_card(
                    SelectFriendList.SAME_SERVER
                )
            )
        task._reset_utilize_friend_list.assert_called_once_with(
            SelectFriendList.SAME_SERVER
        )
        task._locate_recorded_resource_card.assert_called_once_with('斗鱼', 118)

    def test_strategy_maximum_respects_selected_rule(self):
        task = self._task(UtilizeRule.TAIKO)
        self.assertTrue(task._is_strategy_maximum_reward('太鼓', 76))
        self.assertFalse(task._is_strategy_maximum_reward('斗鱼', 151))
        self.assertFalse(task._is_strategy_maximum_reward('太鼓', 75))

    def test_reward_value_overrides_incorrect_star_template(self):
        self.assertIsNone(ScriptTask._resource_reward_star('斗鱼', 84))
        self.assertEqual(ScriptTask._resource_reward_star('斗鱼', 118), 4)
        self.assertEqual(ScriptTask._resource_reward_star('斗鱼', 134), 5)
        self.assertEqual(ScriptTask._resource_reward_star('斗鱼', 151), 6)
        self.assertEqual(ScriptTask._resource_reward_star('太鼓', 59), 4)
        self.assertEqual(ScriptTask._resource_reward_star('太鼓', 67), 5)
        self.assertEqual(ScriptTask._resource_reward_star('太鼓', 76), 6)

    def test_relocation_uses_ocr_even_when_template_type_is_wrong(self):
        task = self._task()
        area = (100, 200, 80, 40)
        task.screenshot = Mock()
        task.device = SimpleNamespace(image=object(), image_frame_id=1)
        task.order_targets = SimpleNamespace(find_everyone=Mock())
        task._deduplicate_card_matches = Mock(
            return_value=[(task.I_U_TAIKO_6, 0.95, area, ())]
        )
        task.click = Mock()
        task.check_card_num = Mock(return_value=('斗鱼', 143))
        task.appear = Mock(return_value=False)
        task.perform_swipe_action = Mock()

        with patch('tasks.KekkaiUtilize.script_task.time.sleep'):
            self.assertTrue(task._locate_recorded_resource_card('斗鱼', 143))

        task.click.assert_called_once()

    def test_scan_does_not_skip_better_card_after_false_six_star_match(self):
        task = self._task(UtilizeRule.FISH)
        areas = [(100, 200, 80, 40), (100, 320, 80, 40)]
        task.ap_max_num = 0
        task.jade_max_num = 0
        task.utilize_found_eligible_card = False
        task.utilize_current_group_has_eligible_card = False
        task.utilize_current_group_scan_completed = False
        task.screenshot = Mock()
        task.device = SimpleNamespace(image=object(), image_frame_id=1)
        task.order_targets = SimpleNamespace(find_everyone=Mock())
        task._deduplicate_card_matches = Mock(
            return_value=[
                (task.I_U_FISH_6, 0.95, areas[0], ()),
                (task.I_U_FISH_6, 0.94, areas[1], ()),
            ]
        )
        task.click = Mock()
        task.check_card_num = Mock(
            side_effect=[('斗鱼', 118), ('斗鱼', 151)]
        )

        with patch('tasks.KekkaiUtilize.script_task.time.sleep'):
            self.assertTrue(task._current_select_best())

        self.assertEqual(task.check_card_num.call_count, 2)
        self.assertEqual(task.ap_max_num, 151)

    def test_entered_realm_failure_uses_separate_two_try_limit(self):
        task = self._task()
        task.utilize_failed_count = 1
        task.utilize_entered_failed_count = 0
        task.utilize_terminal_failure = False
        task.push_notify = Mock()
        task.set_next_run = Mock()

        with patch('tasks.KekkaiUtilize.script_task.logger'):
            self.assertFalse(
                task._record_utilize_failure('no slot', entered_realm=True)
            )
        self.assertFalse(task.utilize_terminal_failure)
        self.assertEqual(task.utilize_failed_count, 1)

        with patch(
            'tasks.KekkaiUtilize.script_task.datetime',
            wraps=datetime,
        ), patch('tasks.KekkaiUtilize.script_task.logger'):
            self.assertFalse(
                task._record_utilize_failure('no slot', entered_realm=True)
            )
        self.assertTrue(task.utilize_terminal_failure)
        task.set_next_run.assert_called_once()

    def test_terminal_failure_returns_to_growth_page_before_exit(self):
        task = self._task()
        task.config.kekkai_utilize.utilize_config.select_friend_list = (
            SelectFriendList.SAME_SERVER
        )
        task.config.kekkai_utilize.utilize_config.shikigami_class = (
            ShikigamiClass.N
        )
        task.config.kekkai_utilize.utilize_config.shikigami_order = 7
        task.utilize_add_count = 0
        task.utilize_found_eligible_card = True
        task.utilize_terminal_failure = False
        task.goto_page = Mock(return_value=True)
        task.screenshot = Mock()
        task.appear = Mock(return_value=True)

        def run_utilize(*_args):
            task.utilize_terminal_failure = True

        task.run_utilize = Mock(side_effect=run_utilize)

        with patch('tasks.KekkaiUtilize.script_task.time.sleep'):
            self.assertFalse(task.check_utilize_add())

        self.assertEqual(
            task.goto_page.call_args_list[-1].args[0],
            page_guild_realm_growth,
        )
        self.assertIn(
            page_guild_realm_utilize,
            [call.args[0] for call in task.goto_page.call_args_list],
        )


if __name__ == '__main__':
    unittest.main()
