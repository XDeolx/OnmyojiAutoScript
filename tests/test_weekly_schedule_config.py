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
            kekkai_utilize=SimpleNamespace(
                scheduler=SimpleNamespace(
                    enable=False,
                    next_run=datetime(2026, 8, 27, 18, 0),
                ),
            ),
            kekkai_activation=SimpleNamespace(
                scheduler=SimpleNamespace(
                    enable=False,
                    next_run=datetime(2026, 8, 27, 19, 0),
                ),
            ),
        )
        config.model.dict = lambda: {
            'area_boss': {},
            'restart': {},
            'kekkai_utilize': {},
            'kekkai_activation': {},
        }
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

    def test_daily_sync_preserves_second_precision(self):
        WeeklySchedule('oas1').save(True, [
            {'task': 'AreaBoss', 'weekday': 3, 'time': '17:49:37'},
        ])
        config = self._config()

        result = config.apply_weekly_schedule_today(
            datetime(2026, 8, 26, 12),
        )

        self.assertEqual(result['applied'], ['AreaBoss'])
        self.assertEqual(
            config.model.area_boss.scheduler.next_run,
            datetime(2026, 8, 26, 17, 49, 37),
        )

    def test_daily_sync_only_runs_once_without_force(self):
        WeeklySchedule('oas1').save(True, [
            {'task': 'AreaBoss', 'weekday': 3, 'time': '17:49'},
        ])
        config = self._config()

        first = config.apply_weekly_schedule_today(datetime(2026, 8, 26, 12))
        second = config.apply_weekly_schedule_today(datetime(2026, 8, 26, 13))

        self.assertEqual(first['applied'], ['AreaBoss'])
        self.assertEqual(second, {
            'applied': [],
            'skipped': [],
            'disabled': [],
            'restored': [],
            'preserved': [],
        })
        config.save.assert_called_once()

    def test_daily_sync_disables_planned_task_on_off_day(self):
        WeeklySchedule('oas1').save(True, [
            {'task': 'Restart', 'weekday': 4, 'time': '19:30'},
        ])
        config = self._config()
        config.model.restart.scheduler.enable = True
        restart_time = config.model.restart.scheduler.next_run

        result = config.apply_weekly_schedule_today(datetime(2026, 8, 28, 0, 1))

        self.assertEqual(result['disabled'], ['Restart'])
        self.assertFalse(config.model.restart.scheduler.enable)
        self.assertEqual(config.model.restart.scheduler.next_run, restart_time)
        self.assertTrue(config.model.area_boss.scheduler.enable)

    def test_daily_sync_reenables_task_on_next_planned_day(self):
        WeeklySchedule('oas1').save(True, [
            {'task': 'Restart', 'weekday': 1, 'time': '19:30'},
        ])
        config = self._config()
        config.model.restart.scheduler.enable = False

        result = config.apply_weekly_schedule_today(datetime(2026, 8, 31, 0, 1))

        self.assertEqual(result['applied'], ['Restart'])
        self.assertTrue(config.model.restart.scheduler.enable)
        self.assertEqual(
            config.model.restart.scheduler.next_run,
            datetime(2026, 8, 31, 19, 30),
        )

    def test_off_day_disables_free_cycle_task_instead_of_preserving_it(self):
        WeeklySchedule('oas1').save(True, [
            {'task': 'KekkaiUtilize', 'weekday': 4, 'time': '08:10'},
        ])
        config = self._config()
        config.model.kekkai_utilize.scheduler.enable = True

        result = config.apply_weekly_schedule_today(datetime(2026, 8, 28, 0, 1))

        self.assertEqual(result['disabled'], ['KekkaiUtilize'])
        self.assertEqual(result['preserved'], [])
        self.assertFalse(config.model.kekkai_utilize.scheduler.enable)

    def test_daily_sync_preserves_default_free_cycle_task_times(self):
        schedule = WeeklySchedule('oas1')
        schedule.save(True, [
            {'task': 'KekkaiUtilize', 'weekday': 4, 'time': '08:10'},
            {'task': 'KekkaiActivation', 'weekday': 4, 'time': '09:05'},
            {'task': 'AreaBoss', 'weekday': 4, 'time': '17:49'},
        ])
        config = self._config()
        config.model.kekkai_utilize.scheduler.enable = True
        config.model.kekkai_activation.scheduler.enable = True
        utilize_time = config.model.kekkai_utilize.scheduler.next_run
        activation_time = config.model.kekkai_activation.scheduler.next_run

        result = config.apply_weekly_schedule_today(datetime(2026, 8, 27, 0, 1))

        self.assertEqual(
            set(result['preserved']),
            {'KekkaiUtilize', 'KekkaiActivation'},
        )
        self.assertEqual(config.model.kekkai_utilize.scheduler.next_run, utilize_time)
        self.assertEqual(
            config.model.kekkai_activation.scheduler.next_run,
            activation_time,
        )
        self.assertEqual(
            config.model.area_boss.scheduler.next_run,
            datetime(2026, 8, 27, 17, 49),
        )

    def test_manual_sync_still_resets_free_cycle_task_time(self):
        WeeklySchedule('oas1').save(True, [
            {'task': 'KekkaiUtilize', 'weekday': 4, 'time': '08:10'},
        ])
        config = self._config()
        config.model.kekkai_utilize.scheduler.enable = True

        result = config.apply_weekly_schedule_today(
            datetime(2026, 8, 27, 0, 1),
            force=True,
        )

        self.assertEqual(result['preserved'], [])
        self.assertEqual(result['applied'], ['KekkaiUtilize'])
        self.assertEqual(
            config.model.kekkai_utilize.scheduler.next_run,
            datetime(2026, 8, 27, 8, 10),
        )

    def test_turtle_mode_disables_every_task_except_retained_tasks(self):
        WeeklySchedule('oas1').save(
            True,
            [
                {'task': 'AreaBoss', 'weekday': 3, 'time': '17:49'},
                {'task': 'Restart', 'weekday': 3, 'time': '18:30'},
            ],
            turtle_mode=True,
            turtle_keep_tasks=['AreaBoss'],
        )
        config = self._config()
        config.model.area_boss.scheduler.enable = False
        config.model.restart.scheduler.enable = True

        result = config.apply_weekly_schedule_today(datetime(2026, 8, 26, 12))

        self.assertEqual(result['applied'], ['AreaBoss'])
        self.assertEqual(result['disabled'], ['Restart'])
        self.assertTrue(config.model.area_boss.scheduler.enable)
        self.assertFalse(config.model.restart.scheduler.enable)

    def test_turtle_mode_does_not_keep_planned_task_enabled_on_off_day(self):
        WeeklySchedule('oas1').save(
            True,
            [{'task': 'Restart', 'weekday': 4, 'time': '19:30'}],
            turtle_mode=True,
            turtle_keep_tasks=['Restart'],
        )
        config = self._config()
        config.model.area_boss.scheduler.enable = False
        config.model.restart.scheduler.enable = True

        result = config.apply_weekly_schedule_today(datetime(2026, 8, 28, 0, 1))

        self.assertEqual(result['disabled'], ['Restart'])
        self.assertFalse(config.model.restart.scheduler.enable)

    def test_enabling_turtle_mode_preserves_retained_task_time(self):
        schedule = WeeklySchedule('oas1')
        entries = [
            {'task': 'AreaBoss', 'weekday': 3, 'time': '17:49'},
            {'task': 'Restart', 'weekday': 3, 'time': '18:30'},
        ]
        schedule.save(True, entries)
        schedule.mark_applied(datetime(2026, 8, 26, 0, 0, 5))
        schedule.save(
            True,
            entries,
            turtle_mode=True,
            turtle_keep_tasks=['AreaBoss'],
        )
        config = self._config()
        retained_time = datetime(2026, 8, 26, 18, 0)
        config.model.area_boss.scheduler.next_run = retained_time
        config.model.restart.scheduler.enable = True

        result = config.apply_weekly_schedule_today(
            datetime(2026, 8, 26, 12),
            force=True,
            preserve_existing_times=True,
        )

        self.assertEqual(config.model.area_boss.scheduler.next_run, retained_time)
        self.assertTrue(config.model.area_boss.scheduler.enable)
        self.assertFalse(config.model.restart.scheduler.enable)
        self.assertEqual(result['applied'], [])
        self.assertEqual(schedule.load()['last_applied_date'], '2026-08-26')

    def test_disabling_turtle_mode_restores_only_today_weekly_tasks(self):
        schedule = WeeklySchedule('oas1')
        entries = [
            {'task': 'AreaBoss', 'weekday': 3, 'time': '17:49'},
            {'task': 'Restart', 'weekday': 4, 'time': '09:05'},
        ]
        schedule.save(
            True,
            entries,
            turtle_mode=True,
            turtle_keep_tasks=['AreaBoss'],
        )
        schedule.save(
            True,
            entries,
            turtle_mode=False,
            turtle_keep_tasks=['AreaBoss'],
        )
        config = self._config()
        config.model.area_boss.scheduler.enable = False
        config.model.restart.scheduler.enable = False

        area_boss_time = config.model.area_boss.scheduler.next_run
        restart_time = config.model.restart.scheduler.next_run
        result = config.apply_weekly_schedule_today(datetime(2026, 8, 26, 12))

        self.assertEqual(result['restored'], ['AreaBoss'])
        self.assertEqual(result['disabled'], [])
        self.assertTrue(config.model.area_boss.scheduler.enable)
        self.assertFalse(config.model.restart.scheduler.enable)
        self.assertEqual(config.model.area_boss.scheduler.next_run, area_boss_time)
        self.assertEqual(config.model.restart.scheduler.next_run, restart_time)
        self.assertFalse(schedule.load()['turtle_restore_pending'])


if __name__ == '__main__':
    unittest.main()
