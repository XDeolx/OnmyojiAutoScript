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

    def test_schedule_accepts_legacy_minutes_and_preserves_seconds(self):
        schedule = WeeklySchedule('oas1')
        saved = schedule.save(True, [
            {'task': 'AreaBoss', 'weekday': 1, 'time': '09:00'},
            {'task': 'Restart', 'weekday': 2, 'time': '10:15:37'},
        ])

        self.assertEqual(saved['entries'][0]['time'], '09:00:00')
        self.assertEqual(saved['entries'][1]['time'], '10:15:37')
        self.assertEqual(
            schedule.next_run('Restart', datetime(2026, 8, 31, 12)),
            datetime(2026, 9, 1, 10, 15, 37),
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

    def test_week_refresh_defaults_to_disabled_with_wednesday_freeze(self):
        refresh = WeeklySchedule('oas1').load()['week_refresh']

        self.assertFalse(refresh['enabled'])
        self.assertEqual(refresh['min_offset_seconds'], 600)
        self.assertEqual(refresh['max_offset_seconds'], 1200)
        self.assertEqual(refresh['freeze_windows'], [{
            'weekday': 3,
            'start': '04:00:00',
            'end': '10:00:00',
        }])

    def test_week_refresh_respects_boundaries_exclusions_and_freeze(self):
        entries = [
            {'task': 'AreaBoss', 'weekday': 1, 'time': '08:00:00'},
            {'task': 'Restart', 'weekday': 1, 'time': '09:00:00'},
            {'task': 'Frozen', 'weekday': 3, 'time': '05:00:00'},
            {'task': 'AfterFreeze', 'weekday': 3, 'time': '10:05:00'},
        ]
        refresh = {
            'enabled': True,
            'min_offset_seconds': 600,
            'max_offset_seconds': 1200,
            'excluded_tasks': ['Restart'],
            'freeze_windows': [
                {'weekday': 3, 'start': '04:00:00', 'end': '10:00:00'},
            ],
            'boundaries': [
                {
                    'task': 'AreaBoss',
                    'weekday': 1,
                    'start': '08:10:00',
                    'end': '08:15:00',
                },
            ],
        }

        generated, issues = WeeklySchedule.generate_week_refresh_entries(
            entries, refresh, chooser=lambda values: values[0]
        )
        by_task = {entry['task']: entry['time'] for entry in generated}

        self.assertEqual(by_task['AreaBoss'], '08:10:00')
        self.assertEqual(by_task['Restart'], '09:00:00')
        self.assertNotIn('Frozen', by_task)
        self.assertEqual(by_task['AfterFreeze'], '10:15:00')
        self.assertEqual(issues, [{
            'task': 'Frozen',
            'weekday': 3,
            'base_time': '05:00:00',
            'reason': 'base_time_in_freeze',
        }])

    def test_week_refresh_moves_a_frozen_base_time_outside_freeze(self):
        generated, issues = WeeklySchedule.generate_week_refresh_entries(
            [{'task': 'NearFreezeEnd', 'weekday': 3, 'time': '09:55:00'}],
            {
                'enabled': True,
                'min_offset_seconds': 600,
                'max_offset_seconds': 600,
                'excluded_tasks': [],
                'freeze_windows': [
                    {'weekday': 3, 'start': '04:00:00', 'end': '10:00:00'},
                ],
                'boundaries': [],
            },
            chooser=lambda values: values[0],
        )

        self.assertEqual(generated, [{
            'task': 'NearFreezeEnd',
            'weekday': 3,
            'time': '10:05:00',
        }])
        self.assertEqual(issues, [])

    def test_week_refresh_keeps_base_time_when_boundary_has_no_candidate(self):
        generated, issues = WeeklySchedule.generate_week_refresh_entries(
            [{'task': 'AreaBoss', 'weekday': 1, 'time': '08:00:00'}],
            {
                'enabled': True,
                'min_offset_seconds': 600,
                'max_offset_seconds': 1200,
                'excluded_tasks': [],
                'freeze_windows': [],
                'boundaries': [{
                    'task': 'AreaBoss',
                    'weekday': 1,
                    'start': '07:59:00',
                    'end': '08:01:00',
                }],
            },
        )

        self.assertEqual(generated[0]['time'], '08:00:00')
        self.assertEqual(issues[0]['reason'], 'no_time_within_boundary')

    def test_week_refresh_allows_tasks_to_exchange_order(self):
        calls = 0

        def choose(values):
            nonlocal calls
            calls += 1
            return values[-1] if calls == 1 else values[0]

        generated, _ = WeeklySchedule.generate_week_refresh_entries(
            [
                {'task': 'First', 'weekday': 1, 'time': '08:00:00'},
                {'task': 'Second', 'weekday': 1, 'time': '08:05:00'},
            ],
            {
                'enabled': True,
                'min_offset_seconds': 600,
                'max_offset_seconds': 1200,
                'excluded_tasks': [],
                'freeze_windows': [],
                'boundaries': [],
            },
            chooser=choose,
        )
        by_task = {entry['task']: entry['time'] for entry in generated}

        self.assertEqual(by_task['First'], '08:20:00')
        self.assertEqual(by_task['Second'], '07:45:00')

    def test_week_refresh_generates_once_per_iso_week(self):
        schedule = WeeklySchedule('oas1')
        schedule.save(
            True,
            [{'task': 'AreaBoss', 'weekday': 1, 'time': '08:00:00'}],
            week_refresh={
                'enabled': True,
                'min_offset_seconds': 600,
                'max_offset_seconds': 1200,
                'excluded_tasks': [],
                'freeze_windows': [],
                'boundaries': [],
            },
        )

        first = schedule.ensure_week_refresh(
            datetime(2026, 8, 31), chooser=lambda values: values[0]
        )
        repeated = schedule.ensure_week_refresh(
            datetime(2026, 9, 2), chooser=lambda values: values[-1]
        )
        next_week = schedule.ensure_week_refresh(
            datetime(2026, 9, 7), chooser=lambda values: values[-1]
        )

        self.assertEqual(first['generated_week'], '2026-W36')
        self.assertEqual(
            repeated['generated_entries'], first['generated_entries']
        )
        self.assertEqual(next_week['generated_week'], '2026-W37')
        self.assertNotEqual(
            next_week['generated_entries'], first['generated_entries']
        )

    def test_daily_targets_use_current_week_refresh_snapshot(self):
        schedule = WeeklySchedule('oas1')
        schedule.save(
            True,
            [{'task': 'AreaBoss', 'weekday': 1, 'time': '08:00:00'}],
            week_refresh={
                'enabled': True,
                'min_offset_seconds': 600,
                'max_offset_seconds': 1200,
                'excluded_tasks': [],
                'freeze_windows': [],
                'boundaries': [],
            },
        )
        schedule.ensure_week_refresh(
            datetime(2026, 8, 31), chooser=lambda values: values[-1]
        )

        self.assertEqual(
            schedule.targets_for_date(datetime(2026, 8, 31).date()),
            {'area_boss': datetime(2026, 8, 31, 8, 20)},
        )

    def test_saving_unchanged_refresh_rules_keeps_week_snapshot(self):
        schedule = WeeklySchedule('oas1')
        rules = {
            'enabled': True,
            'min_offset_seconds': 600,
            'max_offset_seconds': 1200,
            'excluded_tasks': [],
            'freeze_windows': [],
            'boundaries': [],
        }
        entries = [{'task': 'AreaBoss', 'weekday': 1, 'time': '08:00:00'}]
        schedule.save(True, entries, week_refresh=rules)
        generated = schedule.ensure_week_refresh(
            datetime(2026, 8, 31), chooser=lambda values: values[-1]
        )

        saved = schedule.save(True, entries, week_refresh=rules)

        self.assertEqual(
            saved['week_refresh']['generated_week'],
            generated['generated_week'],
        )
        self.assertEqual(
            saved['week_refresh']['generated_entries'],
            generated['generated_entries'],
        )


if __name__ == '__main__':
    unittest.main()
