import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.RealmRaid.script_task import ScriptTask as RealmRaidTask
from tasks.RyouToppa.script_task import TOPPA_FIRE_DELAY_RANGE
from tasks.RyouToppa.script_task import ScriptTask as RyouToppaTask
from tasks.RyouToppa.script_task import random_delay as ryou_toppa_random_delay
from tasks.base_task import BaseTask


class BreakthroughHumanizationTest(unittest.TestCase):
    def test_breakthrough_tasks_declare_humanized_ranges(self):
        for task_class in (RyouToppaTask, RealmRaidTask):
            self.assertEqual(task_class.CLICK_REACTION_DELAY, (0.18, 0.22))
            self.assertEqual(task_class.PREPARE_CLICK_DELAY_RANGE, (2.5, 3.5))
            self.assertEqual(
                task_class.SETTLEMENT_CLICK_INTERVAL_RANGE,
                (0.65, 0.95),
            )

    def test_interval_sampling_normalizes_reversed_range(self):
        with patch(
            'tasks.Component.GeneralBattle.general_battle.random.uniform',
            return_value=0.8,
        ) as uniform:
            self.assertEqual(GeneralBattle._sample_interval((0.95, 0.65)), 0.8)
        uniform.assert_called_once_with(0.65, 0.95)

    def test_ryou_toppa_attack_delay_uses_two_to_ten_seconds(self):
        with patch(
            'tasks.RyouToppa.script_task.random.uniform',
            return_value=6.4,
        ) as uniform:
            self.assertEqual(ryou_toppa_random_delay(), 6.4)
        uniform.assert_called_once_with(2.0, 10.0)

    def test_ryou_toppa_fire_delay_uses_two_to_five_seconds(self):
        with patch(
            'tasks.RyouToppa.script_task.random.uniform',
            return_value=3.6,
        ) as uniform:
            self.assertEqual(
                ryou_toppa_random_delay(*TOPPA_FIRE_DELAY_RANGE),
                3.6,
            )
        uniform.assert_called_once_with(2.0, 5.0)

    def test_ryou_toppa_waits_after_target_selection_before_fire(self):
        task = RyouToppaTask.__new__(RyouToppaTask)
        task.config = SimpleNamespace(
            ryou_toppa=SimpleNamespace(
                raid_config=SimpleNamespace(random_delay=False),
                general_battle_config=Mock(),
            ),
        )
        task.device = SimpleNamespace(click_record_clear=Mock())
        task.check_area = Mock(return_value=True)
        task.screenshot = Mock()
        task.is_in_battle = Mock(side_effect=[False, False, True])
        task.appear = Mock(return_value=True)
        task.appear_then_click = Mock(return_value=True)
        task.run_general_battle = Mock(return_value=True)
        timer = Mock()
        timer.start.return_value = timer
        timer.reached.return_value = True

        with patch(
            'tasks.RyouToppa.script_task.random_delay',
            return_value=3.6,
        ) as delay, patch(
            'tasks.RyouToppa.script_task.Timer',
            return_value=timer,
        ) as timer_class:
            self.assertTrue(task.attack_area(0))

        delay.assert_called_once_with(*TOPPA_FIRE_DELAY_RANGE)
        timer_class.assert_any_call(3.6)
        task.appear_then_click.assert_called_once()

    def test_appear_then_click_rechecks_target_after_reaction_delay(self):
        task = BaseTask.__new__(BaseTask)
        task.CLICK_REACTION_DELAY = (0.18, 0.22)
        task.appear = Mock(side_effect=[True, False])
        task.device = SimpleNamespace(screenshot=Mock(), click=Mock())
        target = Mock()
        target.name = 'TARGET'

        with patch('tasks.base_task.sleep'):
            self.assertFalse(task.appear_then_click(target))

        task.device.screenshot.assert_called_once_with()
        task.device.click.assert_not_called()

    def test_ryou_refresh_uses_selected_device_swipe_method(self):
        task = RyouToppaTask.__new__(RyouToppaTask)
        task.device = SimpleNamespace(swipe=Mock())

        with patch(
            'tasks.RyouToppa.script_task.random.randint',
            side_effect=[1, 600, 400],
        ), patch('tasks.RyouToppa.script_task.time.sleep'):
            task.flush_area_cache()

        task.device.swipe.assert_called_once_with(
            (600, 400),
            (600, 299),
            duration=0.352,
            control_name='RYOU_TOPPA_REFRESH',
        )


if __name__ == '__main__':
    unittest.main()
