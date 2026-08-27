import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from tasks.KekkaiUtilize.page import page_guild
from tasks.KekkaiUtilize.script_task import ScriptTask


class KekkaiUtilizeGuildAssetsTest(unittest.TestCase):
    def _task(self):
        task = ScriptTask.__new__(ScriptTask)
        task.goto_page = Mock()
        task.screenshot = Mock()
        task._settle_guild_reward = Mock()
        task.device = SimpleNamespace(click_record_clear=Mock())
        return task

    def test_receive_guild_assets_visits_guild_once(self):
        task = self._task()
        task.collect_visible_guild_assets = Mock(return_value=True)

        self.assertTrue(task.receive_guild_assets())

        task.goto_page.assert_called_once_with(page_guild)
        task.collect_visible_guild_assets.assert_called_once_with()

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


if __name__ == '__main__':
    unittest.main()
