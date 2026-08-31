import unittest
from unittest.mock import Mock, patch

from tasks.Chess.script_task import ScriptTask


class ChessClickProgressTest(unittest.TestCase):
    def _task(self):
        task = ScriptTask.__new__(ScriptTask)
        task.device = Mock()
        task.screenshot = Mock()
        task.close_shikigami_specifics_if_open = Mock(return_value=False)
        task._shikigami_display_name = lambda name: name
        task.get_lineup_strategy = Mock(
            return_value={
                'key': 'test',
                'shikigami': {'kaoru': {'position': 1}},
            }
        )
        return task

    @patch('tasks.Chess.runtime.hand_operations.time.sleep')
    def test_confirmed_lineup_sale_clears_click_history(self, _sleep):
        task = self._task()
        task._hand_card_detections = Mock(return_value=[{'roi': (10, 20, 30, 40)}])
        task.classify_hand_card = Mock(
            return_value={
                'type': 'shikigami',
                'name': 'kaoru',
                'position': (20, 30),
            },
        )
        task._hand_card_identity_count = Mock(side_effect=[2, 1])
        task.sell_hand_card = Mock()

        result = task.sell_one_lineup_hand_card()

        self.assertIsNotNone(result)
        task.device.click_record_clear.assert_called_once_with()

    @patch('tasks.Chess.runtime.hand_operations.time.sleep')
    def test_unconfirmed_lineup_sale_keeps_click_history(self, _sleep):
        task = self._task()
        task._hand_card_detections = Mock(return_value=[{'roi': (10, 20, 30, 40)}])
        task.classify_hand_card = Mock(
            return_value={
                'type': 'shikigami',
                'name': 'kaoru',
                'position': (20, 30),
            },
        )
        task._hand_card_identity_count = Mock(side_effect=[2, 2])
        task.sell_hand_card = Mock()

        result = task.sell_one_lineup_hand_card()

        self.assertIsNone(result)
        task.device.click_record_clear.assert_not_called()

    @patch('tasks.Chess.runtime.economy.time.sleep')
    def test_confirmed_shop_purchase_clears_click_history(self, _sleep):
        task = self._task()
        task._recognize_shop_slot = Mock(
            side_effect=[{'score': 0.9, 'source': 'template'}, None],
        )
        task._is_purchase_allowed = Mock(return_value=True)
        task._can_afford_shop_shikigami = Mock(return_value=True)
        task.click = Mock()

        result = task._buy_shop_slot(3, Mock(), 'kaoru')

        self.assertTrue(result)
        task.device.click_record_clear.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
