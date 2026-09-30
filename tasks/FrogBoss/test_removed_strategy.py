import unittest
from tasks.FrogBoss.config import FrogBoss, FrogBossConfig, Strategy


class RemovedStrategyTests(unittest.TestCase):
    def test_removed_from_choices(self):
        self.assertNotIn('frog_bilibili', [s.value for s in Strategy])
        for mode in ('validation', 'serialization'):
            schema = FrogBossConfig.model_json_schema(mode=mode)
            choices = schema['$defs']['Strategy']['enum']
            self.assertEqual(len(choices), 6)
            self.assertNotIn('需要重新选择策略', choices)

    def test_legacy_disabled_without_mutating_input(self):
        data = {'scheduler': {'enable': True}, 'frog_boss_config': {'strategy_frog': 'frog_bilibili'}}
        result = FrogBoss(**data)
        self.assertFalse(result.scheduler.enable)
        self.assertTrue(result.frog_boss_config.needs_strategy_selection)
        self.assertTrue(data['scheduler']['enable'])
        self.assertEqual(data['frog_boss_config']['strategy_frog'], 'frog_bilibili')
        self.assertFalse(FrogBoss(**result.model_dump()).scheduler.enable)

    def test_standalone_legacy_config(self):
        self.assertTrue(FrogBossConfig(strategy_frog='frog_bilibili').needs_strategy_selection)

    def test_previous_placeholder_stays_disabled(self):
        result = FrogBoss(scheduler={'enable': True},
                          frog_boss_config={'strategy_frog': '需要重新选择策略'})
        self.assertFalse(result.scheduler.enable)
        restored = FrogBoss.model_validate_json(result.model_dump_json())
        self.assertTrue(restored.frog_boss_config.needs_strategy_selection)
        self.assertFalse(restored.scheduler.enable)

    def test_select_valid_strategy_clears_guard(self):
        data = FrogBoss(frog_boss_config={'strategy_frog': 'frog_bilibili'}).model_dump()
        data['frog_boss_config']['strategy_frog'] = 'frog_oas'
        data['scheduler']['enable'] = True
        result = FrogBoss(**data)
        self.assertTrue(result.scheduler.enable)
        self.assertFalse(result.frog_boss_config.needs_strategy_selection)

    def test_other_strategies_unchanged(self):
        for strategy in Strategy:
            result = FrogBoss(scheduler={'enable': True}, frog_boss_config={'strategy_frog': strategy})
            self.assertTrue(result.scheduler.enable)
            self.assertEqual(result.frog_boss_config.strategy_frog, strategy)

    def test_default_unchanged(self):
        self.assertEqual(FrogBoss().frog_boss_config.strategy_frog, Strategy.Majority)


if __name__ == '__main__':
    unittest.main()
