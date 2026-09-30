"""Regression coverage for FrogBoss/LBS registration and pending queues."""
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from module.config.config import Config
from module.config.config_model import ConfigModel
from module.config.config_manual import ConfigManual
from tasks.FrogBoss.config import FrogBoss, Strategy
from tasks.Script.config_optimization import ScheduleRule


class FrogSchedulerTests(unittest.TestCase):
    def queue(self, rule=ScheduleRule.FILTER, enabled=True, future=False, running=''):
        when = datetime.now() + timedelta(days=1 if future else -1)
        frog = FrogBoss(scheduler=dict(enable=enabled, next_run=when),
                        frog_boss_config=dict(strategy_frog=Strategy.Oas))
        data = {
            'frog_boss': frog.dict(),
            'lbs': {'scheduler': dict(enable=True, next_run=when, priority=5)},
            'restart': {'scheduler': dict(enable=True, next_run=when, priority=5)},
        }
        model = SimpleNamespace(dict=lambda: data, running_task=running,
                                script=SimpleNamespace(optimization=SimpleNamespace(schedule_rule=rule)))
        config = SimpleNamespace(model=model, apply_weekly_schedule_today=lambda: None)
        # Use the actual queue-building code, but never load/save personal configs.
        Config.update_scheduler(config)
        return [x.command for x in config.pending_task], [x.command for x in config.waiting_task]

    def test_registration(self):
        self.assertEqual(ConfigModel.type('frog_boss'), 'FrogBoss')
        self.assertEqual(ConfigModel.type('lbs'), 'LBS')
        names = [x.strip() for x in ConfigManual.SCHEDULER_PRIORITY.split('>')]
        self.assertEqual(names.count('FrogBoss'), 1)
        self.assertEqual(names.count('LBS'), 1)

    def test_fixed_order_oas_and_lbs(self):
        self.assertEqual(self.queue(), (['Restart', 'FrogBoss', 'LBS'], []))

    def test_other_rules_keep_frog(self):
        for rule in (ScheduleRule.FIFO, ScheduleRule.PRIORITY):
            with self.subTest(rule=rule):
                pending, waiting = self.queue(rule=rule)
                self.assertEqual(set(pending), {'Restart', 'FrogBoss', 'LBS'})
                self.assertEqual(pending[0], 'Restart')
                self.assertEqual(waiting, [])

    def test_disabled_not_enqueued(self):
        pending, waiting = self.queue(enabled=False)
        self.assertNotIn('FrogBoss', pending + waiting)

    def test_future_is_waiting(self):
        pending, waiting = self.queue(future=True)
        self.assertEqual(pending, [])
        self.assertIn('FrogBoss', waiting)

    def test_running_task_preserved(self):
        pending, _ = self.queue(running='FrogBoss')
        self.assertEqual(pending[0], 'FrogBoss')


if __name__ == '__main__':
    unittest.main()
