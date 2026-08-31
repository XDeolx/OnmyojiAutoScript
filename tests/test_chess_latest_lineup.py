import unittest
from unittest.mock import patch

from tasks.Chess.strategy.grigri import lineup_bond_context
from tasks.Chess.strategy.lineup_strategy import ARAKAWA_CONFIG
from tasks.Chess.strategy.shikigami_catalog import SHIKIGAMI_BONDS_BY_ROMAJI


class ChessLatestLineupTest(unittest.TestCase):
    def test_arakawa_uses_latest_xylolit_lineup(self):
        self.assertEqual(
            list(ARAKAWA_CONFIG['shikigami_positions']),
            [
                '古笼火',
                '凤凰火',
                '思金神',
                '座敷童子',
                '椒图',
                '河童',
                '海坊主',
                '金鱼姬',
                '荒川之主',
            ],
        )
        self.assertEqual(
            ARAKAWA_CONFIG['shikigami_positions']['思金神'],
            (1, 3, ('招财猫', '魍魉之匣', '狰')),
        )
        self.assertEqual(
            ARAKAWA_CONFIG['shikigami_positions']['荒川之主'][:2],
            (2, 10),
        )

    def test_only_one_secondary_bond_is_selected(self):
        bonds = {
            'test_a': ('主羁绊', '次羁绊甲', '次羁绊乙'),
            'test_b': ('主羁绊', '次羁绊甲', '次羁绊乙'),
            'test_c': ('主羁绊', '次羁绊甲', '次羁绊乙'),
            'test_d': ('主羁绊',),
        }
        strategy = {
            'display_name': '主羁绊',
            'shikigami': {name: {} for name in bonds},
        }

        with patch.dict(SHIKIGAMI_BONDS_BY_ROMAJI, bonds, clear=False):
            context = lineup_bond_context(strategy)

        self.assertEqual(context['secondary'], frozenset({'次羁绊甲'}))


if __name__ == '__main__':
    unittest.main()
