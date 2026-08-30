import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tasks.KekkaiUtilize.config import UtilizeConfig
from tasks.KekkaiUtilize.page import page_guild
from tasks.KekkaiUtilize.script_task import ScriptTask


class KekkaiUtilizeGuildAssetsTest(unittest.TestCase):
    def _task(self):
        task = ScriptTask.__new__(ScriptTask)
        task.goto_page = Mock()
        task.screenshot = Mock()
        task._settle_guild_reward = Mock()
        task.appear = Mock(return_value=False)
        task.device = SimpleNamespace(click_record_clear=Mock())
        return task

    def test_receive_guild_assets_visits_guild_once(self):
        task = self._task()
        task.collect_visible_guild_assets = Mock(return_value=True)

        self.assertTrue(task.receive_guild_assets())

        task.goto_page.assert_called_once_with(page_guild)
        task.collect_visible_guild_assets.assert_called_once_with(
            guild_lottery_enable=False,
            random_wait_enable=False,
        )

    def test_visible_collection_skips_guild_lottery(self):
        task = self._task()

        def click_visible(target, **kwargs):
            return target is task.I_GUILD_ASSETS or target is task.I_GUILD_AP

        task.appear_then_click = Mock(side_effect=click_visible)

        self.assertTrue(task.collect_visible_guild_assets())

        clicked_targets = [call.args[0] for call in task.appear_then_click.call_args_list]
        self.assertFalse(any(target is task.I_GUILD_LOTTERY for target in clicked_targets))
        self.assertEqual(task._settle_guild_reward.call_count, 2)
        task.device.click_record_clear.assert_called_once_with()

    def test_guild_lottery_is_optional_and_defaults_to_disabled(self):
        self.assertFalse(UtilizeConfig().guild_lottery_enable)
        task = self._task()
        task.appear_then_click = Mock(return_value=False)
        task.appear = Mock(
            side_effect=lambda target, **_: target is task.I_GUILD_LOTTERY
        )
        task.guild_lottery = Mock(return_value=True)

        self.assertTrue(
            task.collect_visible_guild_assets(guild_lottery_enable=True)
        )
        task.guild_lottery.assert_called_once_with(random_wait_enable=False)

    def test_random_wait_uses_two_to_four_second_range(self):
        self.assertFalse(UtilizeConfig().guild_reward_random_wait)
        task = self._task()

        with patch(
            'tasks.KekkaiUtilize.script_task.random.uniform',
            return_value=3.25,
        ) as uniform, patch(
            'tasks.KekkaiUtilize.script_task.time.sleep'
        ) as sleep:
            self.assertEqual(
                task._guild_reward_random_wait(True, '寮体力完成'),
                3.25,
            )

        uniform.assert_called_once_with(2.0, 4.0)
        sleep.assert_called_once_with(3.25)

    def test_guild_lottery_entry_failure_is_not_counted_as_draw(self):
        task = self._task()
        task.ui_click_until_appear_or_timeout = Mock(return_value=False)

        self.assertFalse(task.guild_lottery(random_wait_enable=True))

        task.ui_click_until_appear_or_timeout.assert_called_once()


if __name__ == '__main__':
    unittest.main()
