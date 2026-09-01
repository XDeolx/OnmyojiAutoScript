import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.default_pages import reward_random_click


class RewardClickDistributionTest(unittest.TestCase):
    def test_reward_click_uses_expected_region_weights(self):
        expected = GeneralBattleAssets.C_RANDOM_RIGHT
        with patch(
            "tasks.GameUi.default_pages.random.choices",
            return_value=[expected],
        ) as choices:
            self.assertIs(reward_random_click(), expected)

        areas = choices.call_args.args[0]
        self.assertEqual(
            areas,
            (
                GeneralBattleAssets.C_RANDOM_LEFT,
                GeneralBattleAssets.C_RANDOM_TOP,
                GeneralBattleAssets.C_RANDOM_RIGHT,
                GeneralBattleAssets.C_RANDOM_BOTTOM,
            ),
        )
        self.assertEqual(choices.call_args.kwargs["weights"], (5, 10, 45, 40))
        self.assertEqual(choices.call_args.kwargs["k"], 1)

    def test_settlement_waits_before_sampling_click_region(self):
        task = GeneralBattle.__new__(GeneralBattle)
        task.click = Mock()
        click_factory = Mock()
        timer = Mock()
        timer.started.return_value = True
        timer.reached.return_value = False
        context = SimpleNamespace(settlement_click_timer=timer)

        self.assertFalse(task._settlement_click(context, click_factory))

        click_factory.assert_not_called()
        task.click.assert_not_called()
        timer.reset.assert_not_called()

    def test_settlement_samples_region_when_timer_is_ready(self):
        task = GeneralBattle.__new__(GeneralBattle)
        click = Mock()
        task.click = Mock()
        task._next_settlement_click_interval = Mock(return_value=0.82)
        click_factory = Mock(return_value=click)
        timer = Mock()
        timer.started.return_value = True
        timer.reached.return_value = True
        context = SimpleNamespace(settlement_click_timer=timer)

        self.assertTrue(task._settlement_click(context, click_factory))

        click_factory.assert_called_once_with()
        task.click.assert_called_once_with(click)
        self.assertEqual(timer.limit, 0.82)
        timer.reset.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
