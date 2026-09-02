import unittest
from pathlib import Path
from unittest.mock import Mock, call

from tasks.GameUi.page import page_entertainment
from tasks.RichMan.config import ItachiCoinShop as ItachiCoinShopConfig
from tasks.RichMan.itachi_shop import ItachiCoinShop
from tasks.RichMan.page import page_itachi_shop


class ItachiCoinShopTest(unittest.TestCase):
    def test_purchase_defaults_to_disabled(self):
        config = ItachiCoinShopConfig()

        self.assertFalse(config.itachi_coin_buy_jade)
        field = config.model_fields['itachi_coin_buy_jade']
        self.assertEqual(field.title, '购买勾玉礼盒')
        self.assertIn('默认关闭', field.description)

    def test_disabled_purchase_does_not_navigate(self):
        task = ItachiCoinShop.__new__(ItachiCoinShop)
        task.goto_page = Mock()

        task.execute_itachi_coin_shop(ItachiCoinShopConfig())

        task.goto_page.assert_not_called()

    def test_enabled_purchase_processes_at_most_three_gifts(self):
        task = ItachiCoinShop.__new__(ItachiCoinShop)
        task.goto_page = Mock()
        task._wait_entertainment_overlay_closed = Mock(return_value=True)
        task._open_front_gift_once = Mock(return_value=task.GIFT_OPENED)
        task._buy_opened_gift = Mock(return_value=task.GIFT_PURCHASED)

        task.execute_itachi_coin_shop(
            ItachiCoinShopConfig(itachi_coin_buy_jade=True)
        )

        self.assertEqual(task._open_front_gift_once.call_count, 3)
        self.assertEqual(task._buy_opened_gift.call_count, 3)
        self.assertEqual(
            task.goto_page.call_args_list,
            [
                call(page_entertainment),
                call(page_itachi_shop),
                call(page_entertainment),
            ],
        )

    def test_coin_counter_uses_current_and_total_values(self):
        task = ItachiCoinShop.__new__(ItachiCoinShop)
        task.device = Mock(image=object())
        task.O_ITACHI_COIN = Mock()
        task.O_ITACHI_COIN.ocr.return_value = (400, 200, 600)

        self.assertEqual(task._read_itachi_coin(), (400, 600))

    def test_purchase_limit_popup_is_closed_before_stopping(self):
        task = ItachiCoinShop.__new__(ItachiCoinShop)
        task.screenshot = Mock()
        task._read_itachi_coin = Mock(return_value=None)
        task._read_buy_cost = Mock(return_value=None)
        task._read_purchase_status = Mock(return_value=None)
        task.click = Mock()
        task.appear = Mock(return_value=True)
        task.ui_click_until_disappear = Mock()

        self.assertEqual(task._buy_opened_gift(), task.GIFT_STOP)
        task.ui_click_until_disappear.assert_called_once_with(
            task.I_UI_CONFIRM_SAMLL,
            interval=1,
        )

    def test_unopenable_front_gift_stops_following_attempts(self):
        task = ItachiCoinShop.__new__(ItachiCoinShop)
        task.goto_page = Mock()
        task._wait_entertainment_overlay_closed = Mock(return_value=True)
        task._open_front_gift_once = Mock(return_value=task.GIFT_STOP)
        task._buy_opened_gift = Mock()

        task.execute_itachi_coin_shop(
            ItachiCoinShopConfig(itachi_coin_buy_jade=True)
        )

        task._open_front_gift_once.assert_called_once()
        task._buy_opened_gift.assert_not_called()

    def test_insufficient_coin_stops_all_gift_attempts(self):
        task = ItachiCoinShop.__new__(ItachiCoinShop)
        task.goto_page = Mock()
        task._wait_entertainment_overlay_closed = Mock(return_value=True)
        task._open_front_gift_once = Mock(return_value=task.GIFT_OPENED)
        task._buy_opened_gift = Mock(return_value=task.GIFT_STOP)

        task.execute_itachi_coin_shop(
            ItachiCoinShopConfig(itachi_coin_buy_jade=True)
        )

        task._open_front_gift_once.assert_called_once()
        task._buy_opened_gift.assert_called_once()

    def test_coin_cost_mismatch_stops_following_purchases(self):
        task = ItachiCoinShop.__new__(ItachiCoinShop)
        task.screenshot = Mock()
        task._read_itachi_coin = Mock(return_value=(350, 600))

        self.assertFalse(task._verify_coin_cost((400, 600), 100))

    def test_itachi_shop_templates_are_present(self):
        asset_dir = Path('tasks/RichMan/itachi_shop')

        self.assertTrue(
            (asset_dir / 'itachi_shop_itachi_shop_entry.png').is_file()
        )
        self.assertTrue(
            (asset_dir / 'itachi_shop_itachi_shop_check.png').is_file()
        )


if __name__ == '__main__':
    unittest.main()
