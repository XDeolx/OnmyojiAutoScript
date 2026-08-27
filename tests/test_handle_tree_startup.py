import unittest
from unittest.mock import patch

from module.device.handle import EmulatorFamily, Handle, WindowNode
from module.exception import EmulatorNotRunningError


class HandleTreeStartupTest(unittest.TestCase):
    def test_mumu_screenshot_handle_rejects_empty_child_tree(self):
        handle = Handle.__new__(Handle)
        handle.root_node = WindowNode(name='MuMu模拟器12-1', num=123)
        handle.__dict__['emulator_family'] = EmulatorFamily.FAMILY_MUMU

        with self.assertRaises(EmulatorNotRunningError):
            _ = handle.screenshot_handle_num

    def test_handle_tree_can_be_rebuilt_when_child_appears(self):
        handle = Handle.__new__(Handle)
        handle.root_handle_title = 'MuMu模拟器12-1'
        handle.root_handle_num = 123
        calls = 0

        def build_tree(_hwnd, root_node):
            nonlocal calls
            calls += 1
            if calls == 3:
                WindowNode(name='MuMuPlayer', num=456, parent=root_node)

        with patch.object(Handle, 'handle_tree', side_effect=build_tree), \
                patch('module.device.handle.sleep', return_value=None):
            ready = handle._build_handle_tree_with_retry()

        self.assertTrue(ready)
        self.assertEqual(calls, 3)
        self.assertEqual(handle.root_node.children[0].name, 'MuMuPlayer')


if __name__ == '__main__':
    unittest.main()
