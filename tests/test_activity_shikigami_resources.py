import unittest
from pathlib import Path

from tasks.ActivityShikigami.assets import ActivityShikigamiAssets


class ActivityShikigamiResourcesTest(unittest.TestCase):
    def test_activity_entry_and_overlay_resources_use_current_page_group(self):
        asset_names = (
            'I_MAIN_GOTO_ACT',
            'I_SKIP_BUTTON',
            'I_CHECK_BATTLE_MAIN',
            'I_CONFIRM_SKIP',
            'I_ACTIVITY_AWARD',
            'I_ACTIVITY_SIGNIN_CLOSE',
        )

        for asset_name in asset_names:
            asset = getattr(ActivityShikigamiAssets, asset_name)
            self.assertIn('/as/page/', asset.file.replace('\\', '/'))
            self.assertTrue(Path(asset.file).is_file(), asset_name)

        self.assertEqual(ActivityShikigamiAssets.I_MAIN_GOTO_ACT.roi_front, [1188, 304, 35, 28])

    def test_climb_resource_inventory_includes_all_current_mode_assets(self):
        asset_names = (
            'I_FIGHT_PENTA_USE',
            'I_FIGHT_PENTA_DISUSE',
            'I_CHECK_CLIMB_HARD',
            'I_CHECK_CLIMB_EASY',
        )
        for asset_name in asset_names:
            asset = getattr(ActivityShikigamiAssets, asset_name)
            self.assertIn('/as/climb/', asset.file.replace('\\', '/'))
            self.assertTrue(Path(asset.file).is_file(), asset_name)

        self.assertEqual(tuple(ActivityShikigamiAssets.C_CL_SELECT_EASY.roi_front), (1166, 171, 71, 63))
        self.assertEqual(tuple(ActivityShikigamiAssets.C_CL_SELECT_HARD.roi_front), (1121, 340, 71, 63))
        self.assertEqual(tuple(ActivityShikigamiAssets.O_REMAIN_PENTA_PASS.roi), (948, 13, 93, 34))
        self.assertEqual(tuple(ActivityShikigamiAssets.O_REMAIN_AP_PASS.roi), (567, 14, 93, 34))


if __name__ == '__main__':
    unittest.main()
