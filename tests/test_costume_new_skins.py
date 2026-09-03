import unittest
from pathlib import Path
from types import SimpleNamespace

from tasks.Component.Costume.assets import CostumeAssets
from tasks.Component.Costume.config import MainType, ShikigamiType, ThemeType
from tasks.Component.Costume.costume_base import (
    CostumeBase,
    main_costume_model,
    shikigami_costume_model,
    theme_costume_model,
)
from tasks.Component.CostumeShikigami.assets import CostumeShikigamiAssets


class CostumeNewSkinsTest(unittest.TestCase):
    def test_fox_perch_courtyard_has_complete_navigation_assets(self):
        mapping = main_costume_model[MainType.COSTUME_MAIN_17]
        assets = CostumeAssets()

        self.assertEqual(
            set(mapping),
            {
                'I_CHECK_MAIN',
                'I_MAIN_GOTO_EXPLORATION',
                'I_MAIN_GOTO_SUMMON',
                'I_MAIN_GOTO_TOWN',
                'I_PET_HOUSE',
                'I_WQ_DONE',
                'I_HARVEST_SIGN',
                'I_HARVEST_JADE',
                'I_HARVEST_MAIL',
                'I_HARVEST_SOUL',
                'I_HARVEST_GUILD_REWARD',
            },
        )
        for asset_name in mapping.values():
            if asset_name.startswith(('I_WQ_', 'I_HARVEST_')):
                continue
            self.assertTrue(hasattr(assets, asset_name), asset_name)
            self.assertTrue(Path(getattr(assets, asset_name).file).is_file())

    def test_window_intermission_has_complete_shikigami_assets(self):
        mapping = shikigami_costume_model[ShikigamiType.COSTUME_SHIKIGAMI_12]
        assets = CostumeShikigamiAssets()

        self.assertEqual(len(mapping), 20)
        for asset_name in mapping.values():
            self.assertTrue(hasattr(assets, asset_name), asset_name)
            self.assertTrue(Path(getattr(assets, asset_name).file).is_file())

    def test_new_language_evening_theme_has_complete_bottom_bar_assets(self):
        mapping = theme_costume_model[ThemeType.COSTUME_THEME_1]
        assets = CostumeAssets()
        expected_keys = {
            'I_MAIN_SCROLL_CLOSE',
            'I_MAIN_GOTO_SHIKIGAMI_RECORDS',
            'I_MAIN_GOTO_ONMYODO',
            'I_MAIN_GOTO_FRIENDS',
            'I_MAIN_GOTO_DAILY',
            'I_MAIN_GOTO_MALL',
            'I_MAIN_GOTO_GUILD',
            'I_MAIN_GOTO_TEAM',
            'I_MAIN_GOTO_COLLECTION',
            'I_MAIN_GOTO_TRAVEL',
        }

        self.assertEqual(set(mapping), expected_keys)
        self.assertNotIn('I_CHECK_MAIN', mapping)
        self.assertNotIn('I_MAIN_GOTO_EXPLORATION', mapping)
        for asset_name in mapping.values():
            self.assertTrue(hasattr(assets, asset_name), asset_name)
            self.assertTrue(Path(getattr(assets, asset_name).file).is_file())

    def test_new_language_evening_theme_replaces_only_bottom_bar_assets(self):
        task = CostumeBase()
        mapping = theme_costume_model[ThemeType.COSTUME_THEME_1]
        for target_name in mapping:
            setattr(task, target_name, SimpleNamespace(file=None))

        task.check_costume_theme(ThemeType.COSTUME_THEME_1)

        assets = CostumeAssets()
        for target_name, asset_name in mapping.items():
            self.assertEqual(getattr(task, target_name).file, getattr(assets, asset_name).file)


if __name__ == '__main__':
    unittest.main()
