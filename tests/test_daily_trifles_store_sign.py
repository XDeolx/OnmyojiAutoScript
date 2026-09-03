import unittest
from unittest.mock import Mock, patch

from tasks.DailyTrifles.script_task import ScriptTask


def started_timer(*reached_values):
    timer = Mock()
    timer.start.return_value = timer
    timer.reached.side_effect = reached_values
    return timer


class DailyTriflesStoreSignTest(unittest.TestCase):
    def create_task(self):
        task = ScriptTask.__new__(ScriptTask)
        task.I_DAILY_LOGIN_GIFT_PANEL = object()
        task.I_UI_BACK_YELLOW = object()
        task.I_UI_REWARD = object()
        task.screenshot = Mock()
        task.appear = Mock()
        task.appear_then_click = Mock()
        task.ui_reward_appear_click = Mock()
        return task

    def test_new_login_gift_panel_is_closed_before_returning(self):
        task = self.create_task()
        task.appear.side_effect = [True, True, False]
        task.appear_then_click.return_value = True
        outer_timer = started_timer(False)
        close_timer = started_timer(False, False)

        with patch(
            'tasks.DailyTrifles.script_task.Timer',
            side_effect=[outer_timer, close_timer],
        ), patch('tasks.DailyTrifles.script_task.sleep'):
            self.assertTrue(task._wait_store_sign_result())

        task.appear_then_click.assert_called_once_with(
            task.I_UI_BACK_YELLOW,
            interval=0.8,
        )

    def test_legacy_reward_page_remains_supported(self):
        task = self.create_task()
        task.appear.side_effect = [False, False]
        task.ui_reward_appear_click.return_value = True
        outer_timer = started_timer(False)
        reward_timer = started_timer(False)

        with patch(
            'tasks.DailyTrifles.script_task.Timer',
            side_effect=[outer_timer, reward_timer],
        ), patch('tasks.DailyTrifles.script_task.sleep'):
            self.assertTrue(task._wait_store_sign_result())

        task.ui_reward_appear_click.assert_called_once()

    def test_unclosed_login_gift_panel_reports_failure(self):
        task = self.create_task()
        task.appear.return_value = True
        task.appear_then_click.return_value = False
        close_timer = started_timer(False, True)

        with patch(
            'tasks.DailyTrifles.script_task.Timer',
            return_value=close_timer,
        ), patch('tasks.DailyTrifles.script_task.sleep'):
            self.assertFalse(task._close_daily_login_gift_panel())


if __name__ == '__main__':
    unittest.main()
