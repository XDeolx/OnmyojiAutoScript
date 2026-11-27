import unittest
from unittest.mock import patch

from module.exception import GameStuckError
from tasks.SixRealms.page import handle_sr_confirm_tip, handle_sr_confirm, SixRealmsAssets, GlobalGameAssets


class FakeTask:
    def __init__(self, checked=False, stuck=False):
        self.confirm = True
        self.unchecked = not checked
        self.stuck = stuck
        self.clicks = []

    def screenshot(self):
        pass

    def appear(self, rule):
        return ((rule is SixRealmsAssets.I_SR_SELECT_ENSURE_SHORT and self.confirm)
                or (rule is SixRealmsAssets.I_SR_NOT_TIP and self.unchecked))

    def appear_then_click(self, rule, **kwargs):
        if not self.appear(rule):
            return False
        self.clicks.append(rule)
        if not self.stuck:
            if rule is SixRealmsAssets.I_SR_NOT_TIP:
                self.unchecked = False
            else:
                self.confirm = False
        return True


class ConfirmTest(unittest.TestCase):
    def test_checkbox_before_confirm(self):
        task = FakeTask()
        self.assertTrue(handle_sr_confirm_tip(task))
        self.assertEqual(task.clicks, [SixRealmsAssets.I_SR_NOT_TIP, SixRealmsAssets.I_SR_SELECT_ENSURE_SHORT])

    def test_already_checked_still_confirms(self):
        task = FakeTask(checked=True)
        self.assertTrue(handle_sr_confirm_tip(task))
        self.assertEqual(task.clicks, [SixRealmsAssets.I_SR_SELECT_ENSURE_SHORT])

    def test_unknown_page_never_clicked(self):
        task = FakeTask()
        task.confirm = False
        self.assertFalse(handle_sr_confirm_tip(task))
        self.assertEqual(task.clicks, [])

    def test_stuck_checkbox_does_not_confirm(self):
        class Timer:
            def __init__(self, *a): self.checks = 0
            def start(self): return self
            def reached(self):
                self.checks += 1
                return self.checks > 8
        task = FakeTask(stuck=True)
        with patch('module.base.timer.Timer', Timer):
            with self.assertRaises(GameStuckError):
                handle_sr_confirm_tip(task)
        self.assertEqual(task.clicks, [SixRealmsAssets.I_SR_NOT_TIP] * 3)

    def test_backup_requires_cancel(self):
        task = FakeTask()
        task.appear = lambda r: False
        task.appear_then_click = lambda *a, **k: self.fail('No confirmation should be clicked')
        self.assertFalse(handle_sr_confirm(task))


if __name__ == '__main__':
    unittest.main()
