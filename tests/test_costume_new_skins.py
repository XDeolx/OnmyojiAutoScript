import unittest
from pathlib import Path

from tasks.Component.Costume.assets import CostumeAssets
from tasks.Component.Costume.config import MainType, ShikigamiType
from tasks.Component.Costume.costume_base import (
    main_costume_model,
    shikigami_costume_model,
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


if __name__ == '__main__':
    unittest.main()
