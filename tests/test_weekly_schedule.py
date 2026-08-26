import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from module.config.weekly_schedule import WeeklySchedule


class WeeklyScheduleTest(unittest.TestCase):
    def setUp(self):
        self._old_cwd = Path.cwd()
        self._temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self._temp_dir.name)
        Path('config').mkdir()

    def tearDown(self):
        os.chdir(self._old_cwd)
        self._temp_dir.cleanup()

    def test_next_run_uses_nearest_weekly_slot(self):
        schedule = WeeklySchedule('oas1')
        schedule.save(True, [
            {'task': 'AreaBoss', 'weekday': 1, 'time': '09:00'},
            {'task': 'AreaBoss', 'weekday': 5, 'time': '18:30'},
        ])

        self.assertEqual(
            schedule.next_run('AreaBoss', datetime(2026, 8, 26, 12)),
            datetime(2026, 8, 28, 18, 30),
        )
        self.assertEqual(
            schedule.next_run('AreaBoss', datetime(2026, 8, 28, 18, 30)),
            datetime(2026, 8, 31, 9),
        )

    def test_disabled_schedule_does_not_override_tasks(self):
        schedule = WeeklySchedule('oas1')
        schedule.save(False, [
            {'task': 'AreaBoss', 'weekday': 1, 'time': '09:00'},
        ])

        self.assertIsNone(
            schedule.next_run('AreaBoss', datetime(2026, 8, 26, 12)),
        )


if __name__ == '__main__':
    unittest.main()
