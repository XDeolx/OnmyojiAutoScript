import unittest
from unittest.mock import Mock, call

from tasks.Component.Login.service import LoginService


class LoginCompatibilityTest(unittest.TestCase):
    def _make_service(self):
        service = LoginService.__new__(LoginService)
        service.O_LOGIN_ENTER_GAME = Mock(name="legacy_enter_game")
        service.O_LOGIN_ENTER_GAME.name = "login_enter_game"
        service.O_LOGIN_ENTER_GAME_VERTICAL = Mock(name="vertical_enter_game")
        service.O_LOGIN_ENTER_GAME_VERTICAL.name = "login_enter_game_vertical"
        service.ocr_appear_click = Mock()
        return service

    def test_legacy_enter_game_rule_remains_first_choice(self):
        service = self._make_service()
        service.ocr_appear_click.return_value = True

        self.assertTrue(service._click_enter_game())

        service.ocr_appear_click.assert_called_once_with(
            service.O_LOGIN_ENTER_GAME,
            interval=3,
        )

    def test_vertical_enter_game_rule_is_used_as_fallback(self):
        service = self._make_service()
        service.ocr_appear_click.side_effect = [False, True]

        self.assertTrue(service._click_enter_game())

        self.assertEqual(
            service.ocr_appear_click.call_args_list,
            [
                call(service.O_LOGIN_ENTER_GAME, interval=3),
                call(service.O_LOGIN_ENTER_GAME_VERTICAL, interval=3),
            ],
        )

    def test_enter_game_returns_false_when_neither_layout_matches(self):
        service = self._make_service()
        service.ocr_appear_click.return_value = False

        self.assertFalse(service._click_enter_game())

        self.assertEqual(service.ocr_appear_click.call_count, 2)


if __name__ == "__main__":
    unittest.main()
