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

    def test_current_week_datetime_uses_each_entry_weekday(self):
        reference = datetime(2026, 8, 26, 15)

        self.assertEqual(
            WeeklySchedule.current_week_datetime(
                {'task': 'AreaBoss', 'weekday': 1, 'time': '08:10'},
                reference,
            ),
            datetime(2026, 8, 24, 8, 10),
        )
        self.assertEqual(
            WeeklySchedule.current_week_datetime(
                {'task': 'AreaBoss', 'weekday': 2, 'time': '08:10'},
                reference,
            ),
            datetime(2026, 8, 25, 8, 10),
        )

    def test_daily_targets_only_include_selected_date(self):
        schedule = WeeklySchedule('oas1')
        schedule.save(True, [
            {'task': 'AreaBoss', 'weekday': 2, 'time': '08:10'},
            {'task': 'AreaBoss', 'weekday': 3, 'time': '17:49'},
            {'task': 'Restart', 'weekday': 3, 'time': '09:05'},
        ], catch_up_missed=True)

        self.assertEqual(
            schedule.targets_for_date(datetime(2026, 8, 26).date()),
            {
                'area_boss': datetime(2026, 8, 26, 17, 49),
                'restart': datetime(2026, 8, 26, 9, 5),
            },
        )
        self.assertTrue(schedule.needs_daily_apply(datetime(2026, 8, 26).date()))
        schedule.mark_applied(datetime(2026, 8, 26, 0, 0, 5))
        self.assertFalse(schedule.needs_daily_apply(datetime(2026, 8, 26).date()))
        self.assertTrue(schedule.needs_daily_apply(datetime(2026, 8, 27).date()))
        self.assertTrue(schedule.load()['catch_up_missed'])

    def test_turtle_mode_persists_tasks_and_marks_restore(self):
        schedule = WeeklySchedule('oas1')
        schedule.save(
            True,
            [{'task': 'AreaBoss', 'weekday': 3, 'time': '17:49'}],
            turtle_mode=True,
            turtle_keep_tasks=['AreaBoss', 'area_boss', 'KekkaiUtilize'],
        )

        active = schedule.load()
        self.assertTrue(active['turtle_mode'])
        self.assertEqual(
            active['turtle_keep_tasks'],
            ['AreaBoss', 'KekkaiUtilize'],
        )
        self.assertFalse(active['turtle_restore_pending'])

        schedule.save(
            True,
            active['entries'],
            turtle_mode=False,
            turtle_keep_tasks=active['turtle_keep_tasks'],
        )
        self.assertTrue(schedule.load()['turtle_restore_pending'])
        schedule.mark_applied(datetime(2026, 8, 26, 12))
        self.assertFalse(schedule.load()['turtle_restore_pending'])

    def test_free_cycle_defaults_can_be_cleared_and_are_copied(self):
        source = WeeklySchedule('oas1')
        self.assertEqual(
            source.load()['free_cycle_tasks'],
            ['KekkaiActivation', 'KekkaiUtilize'],
        )
        source.save(
            True,
            [{'task': 'AreaBoss', 'weekday': 3, 'time': '17:49'}],
            free_cycle_tasks=[],
        )
        WeeklySchedule.copy('oas1', 'oas2')

        self.assertEqual(source.load()['free_cycle_tasks'], [])
        self.assertEqual(WeeklySchedule('oas2').load()['free_cycle_tasks'], [])


if __name__ == '__main__':
    unittest.main()
