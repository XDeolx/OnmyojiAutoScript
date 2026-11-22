import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load_method(file, name, env):
    tree = ast.parse((ROOT / file).read_text(encoding='utf-8'))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), env)
    return env[name]

HAND = 'tasks/Chess/runtime/hand_operations.py'
NAV = 'tasks/GameUi/chess_battle.py'

class ChessGuardsTest(unittest.TestCase):
    def sale(self, counts):
        cleared = []
        current = [10]
        def wait(condition):
            for value in counts:
                current[0] = value
                if condition(): return True
            return False
        fake = SimpleNamespace(
            close_shikigami_specifics_if_open=lambda: False,
            _wait_chess_action_state=wait,
            device=SimpleNamespace(click_record_remove=cleared.append))
        result = load_method(HAND, '_wait_hand_card_removed', {})(fake, 10, lambda: current[0])
        return result, cleared

    def test_success_clears_only_sale_guard(self):
        self.assertEqual(self.sale([9, 9, 9]), (True, ['CHESS_SELL_UNKNOWN_HAND_CARD']))

    def test_fluctuating_recognition_does_not_confirm_sale(self):
        self.assertEqual(self.sale([9, 10, 9, 10, 9]), (False, []))

    def test_full_notice_overrides_incomplete_visual_count(self):
        fake = SimpleNamespace(I_HAND_FULL_NOTICE='full', appear=lambda _: True)
        logger = SimpleNamespace(info=lambda _: None)
        self.assertEqual(load_method(HAND, '_hand_capacity_count', {'logger': logger})(fake), 10)

    def test_rank_up_reward_rank_lobby_recovery(self):
        clock = [0.0]
        pages = ['rank_up', 'reward', 'rank', 'lobby']
        clicks = []
        class Fake:
            CHESS_EXIT_TIMEOUT = 60
            CHESS_EXIT_SCREENSHOT_INTERVAL = 0.35
            def __getattr__(self, name): return name
            def screenshot(self): pass
            def appear(self, rule):
                return rule == {'rank_up': 'I_CHESS_RANK_UP', 'reward': 'I_UI_REWARD_NEW',
                                'rank': 'I_CHESS_RANK_GOTO_LOBBY', 'lobby': 'I_CHECK_CHESS'}[pages[0]]
            def click(self, rule):
                clicks.append(rule)
                pages.pop(0)
        env = {'time': SimpleNamespace(monotonic=lambda: clock[0],
                   sleep=lambda duration: clock.__setitem__(0, clock[0]+duration)),
               'GeneralBattleAssets': SimpleNamespace(C_RANDOM_LEFT='safe'), 'GameStuckError': RuntimeError}
        result = load_method(NAV, '_return_to_chess_lobby_strict', env)(Fake())
        self.assertTrue(result)
        self.assertEqual(clicks, ['safe', 'safe', 'I_CHESS_RANK_GOTO_LOBBY'])

    def test_full_hand_cleanup_equips_before_selling(self):
        actions = []
        fake = SimpleNamespace(
            _read_chess_mode=lambda: '备', _ensure_shop_closed=lambda **kw: True,
            screenshot=lambda: None, _soul_hand_cards=lambda: [1],
            _board_lineup_names={'unit'}, shikigami_deploy_positions={'unit': 1},
            equip_souls_from_hand=lambda names: actions.append('equip') or [1],
            cleanup_non_lineup_hand_cards=lambda **kw: actions.append('sell') or [2])
        logger = SimpleNamespace(info=lambda _: None, warning=lambda _: None)
        result = load_method(HAND, 'emergency_cleanup_hand', {'logger': logger})(fake)
        self.assertEqual(actions, ['equip', 'sell'])
        self.assertEqual(result['sold_non_lineup'], [2])

    def test_failed_purchase_with_full_notice_cleans_then_retries(self):
        actions = []
        class Fake:
            SHOP_BUY_TIMEOUT = 30
            _current_round_no = 1
            full = False
            device = SimpleNamespace(click_record_remove=lambda _: None)
            def _recognize_shop_slot(self, *a, **kw): return {'source': 'frame', 'score': 1}
            def _is_purchase_allowed(self): return True
            def _can_afford_shop_shikigami(self, *a, **kw): return True
            def _hand_capacity_count(self): return 10 if self.full else 9
            def _shikigami_display_name(self, name): return name
            def ui_click_until_disappear(self, *a, **kw):
                actions.append('buy')
                self.full = len(actions) == 1
                return not self.full
            def _free_one_hand_slot_for_purchase(self, **kw):
                actions.append('cleanup')
                self.full = False
                return {'type': 'emergency_cleanup'}
        logger = SimpleNamespace(info=lambda _: None, warning=lambda _: None, debug=lambda _: None)
        env = {'RuleClick': object, 'time': SimpleNamespace(monotonic=lambda: 0),
               'SHIKIGAMI_BY_ROMAJI': {'unit': SimpleNamespace(cost=1)}, 'logger': logger}
        buy = load_method('tasks/Chess/runtime/economy.py', '_buy_shop_slot', env)
        self.assertTrue(buy(Fake(), 1, object(), 'unit'))
        self.assertEqual(actions, ['buy', 'cleanup', 'buy'])

if __name__ == '__main__': unittest.main()
