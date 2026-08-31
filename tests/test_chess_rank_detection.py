import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from tasks.Chess.config import ChessConfig
from tasks.Chess.script_task import ScriptTask


class ChessRankDetectionTest(unittest.TestCase):
    def _task(self):
        task = ScriptTask.__new__(ScriptTask)
        task.device = SimpleNamespace(image=object())
        return task

    def test_result_rank_ocr_is_preserved(self):
        task = self._task()
        task.O_RANK = Mock()
        task.O_RANK.ocr.return_value = '第4名'

        self.assertEqual(task._read_game_rank(), (4, '第4名'))

    def test_alive_player_ocr_returns_highest_visible_slot(self):
        task = self._task()
        for index in range(1, 9):
            rule = Mock()
            rule.ocr.return_value = '100' if index <= 5 else ''
            setattr(task, f'O_HEALTH_{index}', rule)

        self.assertEqual(task._read_alive_players(), 5)

    def test_legacy_early_exit_fields_remain_optional(self):
        config = ChessConfig()

        self.assertFalse(config.early_exit)
        self.assertEqual(config.remaining_players, 0)

    def test_startup_recovery_navigation_contract_is_available(self):
        task = self._task()
        task.screenshot = Mock()
        task.appear = Mock(return_value=False)

        self.assertTrue(callable(task.chess_result_flow_visible))
        self.assertTrue(callable(task.return_to_chess_lobby))
        self.assertTrue(callable(task.exit_chess_battle))
        self.assertFalse(task._recover_interrupted_chess_game())


if __name__ == '__main__':
    unittest.main()
