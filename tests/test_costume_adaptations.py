import json
import unittest
from pathlib import Path

from tasks.Component.Costume.config import ShikigamiType
from tasks.Component.Costume.costume_base import shikigami_costume_model
from tasks.Component.CostumeShikigami.assets import CostumeShikigamiAssets


class CostumeAdaptationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_hanafuda_stage_is_registered_with_all_required_assets(self):
        costume = ShikigamiType.COSTUME_SHIKIGAMI_11
        model = shikigami_costume_model[costume]

        self.assertEqual(costume.value, 'costume_shikigami_11')
        self.assertEqual(len(model), 20)
        for asset_name in model.values():
            self.assertTrue(
                hasattr(CostumeShikigamiAssets, asset_name),
                asset_name,
            )

    def test_hanafuda_rule_images_exist(self):
        folder = self.root / 'tasks/Component/CostumeShikigami/sk11'
        with (folder / 'image.json').open(encoding='utf-8') as stream:
            rules = json.load(stream)

        self.assertEqual(len(rules), 20)
        for rule in rules:
            image = folder / rule['imageName']
            self.assertTrue(image.is_file(), image.name)
            self.assertGreater(image.stat().st_size, 0, image.name)

    def test_qiguang_records_detection_area(self):
        self.assertEqual(
            tuple(CostumeShikigamiAssets.I_CHECK_RECORDS_5.roi_front),
            (313, 75, 44, 43),
        )
        self.assertEqual(
            tuple(CostumeShikigamiAssets.I_CHECK_RECORDS_5.roi_back),
            (308, 70, 54, 53),
        )


if __name__ == '__main__':
    unittest.main()
