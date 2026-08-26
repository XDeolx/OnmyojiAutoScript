import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from module.config.config import Config
from module.config.weekly_schedule import WeeklySchedule


class WeeklyScheduleConfigTest(unittest.TestCase):
    def setUp(self):
        self._old_cwd = Path.cwd()
        self._temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self._temp_dir.name)
        Path('config').mkdir()

    def tearDown(self):
        os.chdir(self._old_cwd)
        self._temp_dir.cleanup()

    def _config(self):
        config = Config.__new__(Config)
        config.config_name = 'oas1'
        config.model = SimpleNamespace(
            area_boss=SimpleNamespace(
                scheduler=SimpleNamespace(
                    enable=True,
                    next_run=datetime(2026, 8, 27, 17, 0),
                ),
            ),
            restart=SimpleNamespace(
                scheduler=SimpleNamespace(
                    enable=False,
                    next_run=datetime(2026, 8, 27, 9, 0),
                ),
            ),
        )
        config.save = Mock()
        return config

    def test_daily_sync_skips_past_entries_by_default(self):
        WeeklySchedule('oas1').save(True, [
            {'task': 'Restart', 'weekday': 3, 'time': '09:05'},
            {'task': 'AreaBoss', 'weekday': 3, 'time': '17:49'},
        ], catch_up_missed=False)
        config = self._config()

        result = config.apply_weekly_schedule_today(datetime(2026, 8, 26, 12))

        self.assertEqual(result['skipped'], ['Restart'])
        self.assertEqual(result['applied'], ['AreaBoss'])
        self.assertEqual(
            config.model.area_boss.scheduler.next_run,
            datetime(2026, 8, 26, 17, 49),
        )
        self.assertFalse(config.model.restart.scheduler.enable)
        config.save.assert_called_once()

    def test_daily_sync_catches_up_past_entries_when_enabled(self):
        WeeklySchedule('oas1').save(True, [
            {'task': 'Restart', 'weekday': 3, 'time': '09:05'},
        ], catch_up_missed=True)
        config = self._config()

        result = config.apply_weekly_schedule_today(datetime(2026, 8, 26, 12))

        self.assertEqual(result['skipped'], [])
        self.assertEqual(result['applied'], ['Restart'])
        self.assertTrue(config.model.restart.scheduler.enable)
        self.assertEqual(
            config.model.restart.scheduler.next_run,
            datetime(2026, 8, 26, 9, 5),
        )
        config.save.assert_called_once()

    def test_daily_sync_only_runs_once_without_force(self):
        WeeklySchedule('oas1').save(True, [
            {'task': 'AreaBoss', 'weekday': 3, 'time': '17:49'},
        ])
        config = self._config()

        first = config.apply_weekly_schedule_today(datetime(2026, 8, 26, 12))
        second = config.apply_weekly_schedule_today(datetime(2026, 8, 26, 13))

        self.assertEqual(first['applied'], ['AreaBoss'])
        self.assertEqual(second, {'applied': [], 'skipped': []})
        config.save.assert_called_once()


if __name__ == '__main__':
    unittest.main()
