import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.RealmRaid.script_task import ScriptTask as RealmRaidTask
from tasks.RyouToppa.script_task import ScriptTask as RyouToppaTask
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
