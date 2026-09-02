# This Python file uses the following encoding: utf-8
from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta
from pathlib import Path

from module.config.utils import convert_to_underscore, read_file, write_file
from module.logger import logger


def _parse_schedule_time(value: str) -> time:
    for pattern in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(value, pattern).time()
        except ValueError:
            continue
    raise ValueError(f'Invalid weekly schedule time: {value}')


class WeeklySchedule:
    """Persistent weekly task schedule for one script config."""

    DEFAULT_FREE_CYCLE_TASKS = ('KekkaiActivation', 'KekkaiUtilize')
    DEFAULT_WEEK_REFRESH = {
        'enabled': False,
        'min_offset_seconds': 10 * 60,
        'max_offset_seconds': 20 * 60,
        'excluded_tasks': [],
        'freeze_windows': [
            {'weekday': 3, 'start': '04:00:00', 'end': '10:00:00'},
        ],
        'boundaries': [],
        'generated_week': '',
        'generated_at': '',
        'generated_entries': [],
        'issues': [],
    }

    def __init__(self, config_name: str):
        self.config_name = config_name

    @property
    def path(self) -> Path:
        return Path.cwd() / 'config' / 'weekly_schedule' / f'{self.config_name}.json'

    def load(self) -> dict:
        raw = read_file(str(self.path))
        if not isinstance(raw, dict):
            raw = {}
        entries = raw.get('entries', [])
        if not isinstance(entries, list):
            entries = []
        clean_entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                clean_entries.extend(self.normalize_entries([entry]))
            except (TypeError, ValueError):
                continue
        return {
            'enabled': bool(raw.get('enabled', True)),
            'catch_up_missed': bool(raw.get('catch_up_missed', False)),
            'turtle_mode': bool(raw.get('turtle_mode', False)),
            'turtle_keep_tasks': self.normalize_tasks(raw.get('turtle_keep_tasks', [])),
            'turtle_restore_pending': bool(raw.get('turtle_restore_pending', False)),
            'free_cycle_tasks': self.normalize_tasks(
                raw.get('free_cycle_tasks', self.DEFAULT_FREE_CYCLE_TASKS)
            ),
            'entries': clean_entries,
            'week_refresh': self.normalize_week_refresh(raw.get('week_refresh')),
            'last_applied_date': str(raw.get('last_applied_date', '')),
            'last_applied_at': str(raw.get('last_applied_at', '')),
        }

    def save(
        self,
        enabled: bool,
        entries: list[dict],
        catch_up_missed: bool | None = None,
        turtle_mode: bool | None = None,
        turtle_keep_tasks: list[str] | None = None,
        free_cycle_tasks: list[str] | None = None,
        week_refresh: dict | None = None,
    ) -> dict:
        previous = self.load()
        was_enabled = previous['enabled']
        next_turtle_mode = (
            previous['turtle_mode'] if turtle_mode is None else bool(turtle_mode)
        )
        next_turtle_tasks = (
            previous['turtle_keep_tasks']
            if turtle_keep_tasks is None
            else self.normalize_tasks(turtle_keep_tasks)
        )
        next_free_cycle_tasks = (
            previous['free_cycle_tasks']
            if free_cycle_tasks is None
            else self.normalize_tasks(free_cycle_tasks)
        )
        next_week_refresh = (
            previous['week_refresh']
            if week_refresh is None
            else self.normalize_week_refresh(week_refresh)
        )
        next_entries = self.normalize_entries(entries)
        previous_refresh_rules = self.week_refresh_rules(previous['week_refresh'])
        next_refresh_rules = self.week_refresh_rules(next_week_refresh)
        if (
            previous['entries'] != next_entries
            or previous_refresh_rules != next_refresh_rules
        ):
            next_week_refresh = {
                **next_week_refresh,
                'generated_week': '',
                'generated_at': '',
                'generated_entries': [],
                'issues': [],
            }
        else:
            next_week_refresh = {
                **next_week_refresh,
                'generated_week': previous['week_refresh']['generated_week'],
                'generated_at': previous['week_refresh']['generated_at'],
                'generated_entries': previous['week_refresh']['generated_entries'],
                'issues': previous['week_refresh']['issues'],
            }
        restore_pending = previous['turtle_restore_pending']
        if next_turtle_mode:
            restore_pending = False
        elif previous['turtle_mode']:
            restore_pending = True
        data = {
            'enabled': bool(enabled),
            'catch_up_missed': (
                previous['catch_up_missed']
                if catch_up_missed is None
                else bool(catch_up_missed)
            ),
            'turtle_mode': next_turtle_mode,
            'turtle_keep_tasks': next_turtle_tasks,
            'turtle_restore_pending': restore_pending,
            'free_cycle_tasks': next_free_cycle_tasks,
            'entries': next_entries,
            'week_refresh': next_week_refresh,
            'last_applied_date': previous['last_applied_date'],
            'last_applied_at': previous['last_applied_at'],
        }
        if enabled and not was_enabled:
            data['last_applied_date'] = ''
            data['last_applied_at'] = ''
        write_file(str(self.path), data)
        return data

    @staticmethod
    def normalize_tasks(tasks) -> list[str]:
        if not isinstance(tasks, (list, tuple, set)):
            return []
        normalized = []
        seen = set()
        for task in tasks:
            name = str(task).strip()
            key = convert_to_underscore(name)
            if not name or key in seen:
                continue
            seen.add(key)
            normalized.append(name)
        return normalized

    @classmethod
    def normalize_week_refresh(cls, value) -> dict:
        raw = value if isinstance(value, dict) else {}
        defaults = cls.DEFAULT_WEEK_REFRESH
        try:
            first_offset = int(raw.get(
                'min_offset_seconds', defaults['min_offset_seconds']
            ))
            second_offset = int(raw.get(
                'max_offset_seconds', defaults['max_offset_seconds']
            ))
        except (TypeError, ValueError):
            first_offset = defaults['min_offset_seconds']
            second_offset = defaults['max_offset_seconds']
        first_offset = max(0, min(first_offset, 24 * 60 * 60 - 1))
        second_offset = max(0, min(second_offset, 24 * 60 * 60 - 1))

        freeze_source = raw.get('freeze_windows', defaults['freeze_windows'])
        freeze_windows = []
        if isinstance(freeze_source, list):
            for item in freeze_source:
                if not isinstance(item, dict):
                    continue
                weekday = int(item.get('weekday', 0))
                start = _parse_schedule_time(str(item.get('start', '')))
                end = _parse_schedule_time(str(item.get('end', '')))
                if weekday < 1 or weekday > 7 or start >= end:
                    raise ValueError('Invalid weekly refresh freeze window')
                freeze_windows.append({
                    'weekday': weekday,
                    'start': start.strftime('%H:%M:%S'),
                    'end': end.strftime('%H:%M:%S'),
                })

        boundaries = []
        boundary_source = raw.get('boundaries', defaults['boundaries'])
        seen_boundaries = set()
        if isinstance(boundary_source, list):
            for item in boundary_source:
                if not isinstance(item, dict):
                    continue
                task = str(item.get('task', '')).strip()
                weekday = int(item.get('weekday', 0))
                start = _parse_schedule_time(str(item.get('start', '')))
                end = _parse_schedule_time(str(item.get('end', '')))
                if not task or weekday < 1 or weekday > 7 or start > end:
                    raise ValueError('Invalid weekly refresh task boundary')
                key = (convert_to_underscore(task), weekday)
                if key in seen_boundaries:
                    continue
                seen_boundaries.add(key)
                boundaries.append({
                    'task': task,
                    'weekday': weekday,
                    'start': start.strftime('%H:%M:%S'),
                    'end': end.strftime('%H:%M:%S'),
                })

        generated_entries = []
        generated_source = raw.get('generated_entries', [])
        if isinstance(generated_source, list):
            for entry in generated_source:
                if not isinstance(entry, dict):
                    continue
                try:
                    generated_entries.extend(cls.normalize_entries([entry]))
                except (TypeError, ValueError):
                    continue

        issues = []
        issue_source = raw.get('issues', [])
        if isinstance(issue_source, list):
            for issue in issue_source:
                if not isinstance(issue, dict):
                    continue
                issues.append({
                    'task': str(issue.get('task', '')),
                    'weekday': int(issue.get('weekday', 0)),
                    'base_time': str(issue.get('base_time', '')),
                    'reason': str(issue.get('reason', '')),
                })

        return {
            'enabled': bool(raw.get('enabled', defaults['enabled'])),
            'min_offset_seconds': min(first_offset, second_offset),
            'max_offset_seconds': max(first_offset, second_offset),
            'excluded_tasks': cls.normalize_tasks(raw.get(
                'excluded_tasks', defaults['excluded_tasks']
            )),
            'freeze_windows': freeze_windows,
            'boundaries': boundaries,
            'generated_week': str(raw.get('generated_week', '')),
            'generated_at': str(raw.get('generated_at', '')),
            'generated_entries': generated_entries,
            'issues': issues,
        }

    @staticmethod
    def week_refresh_rules(value: dict) -> dict:
        return {
            key: value[key]
            for key in (
                'enabled',
                'min_offset_seconds',
                'max_offset_seconds',
                'excluded_tasks',
                'freeze_windows',
                'boundaries',
            )
        }

    @staticmethod
    def week_key(reference: date | datetime) -> str:
        if isinstance(reference, datetime):
            reference = reference.date()
        iso_year, iso_week, _ = reference.isocalendar()
        return f'{iso_year}-W{iso_week:02d}'

    @classmethod
    def generate_week_refresh_entries(
        cls,
        entries: list[dict],
        week_refresh: dict,
        chooser=None,
    ) -> tuple[list[dict], list[dict]]:
        """Generate independent second-level offsets within hard boundaries."""
        entries = cls.normalize_entries(entries)
        refresh = cls.normalize_week_refresh(week_refresh)
        choose = chooser or secrets.choice
        excluded = {
            convert_to_underscore(task)
            for task in refresh['excluded_tasks']
        }
        freezes = {}
        for item in refresh['freeze_windows']:
            freezes.setdefault(item['weekday'], []).append((
                cls._clock_seconds(item['start']),
                cls._clock_seconds(item['end']),
            ))
        boundaries = {
            (convert_to_underscore(item['task']), item['weekday']): (
                cls._clock_seconds(item['start']),
                cls._clock_seconds(item['end']),
            )
            for item in refresh['boundaries']
        }
        occupied = set()
        generated = []
        issues = []

        for entry in entries:
            task_key = convert_to_underscore(entry['task'])
            weekday = entry['weekday']
            base_seconds = cls._clock_seconds(entry['time'])
            freeze_windows = freezes.get(weekday, [])
            base_is_frozen = any(
                start <= base_seconds < end
                for start, end in freeze_windows
            )
            if task_key in excluded:
                if base_is_frozen:
                    issues.append({
                        'task': entry['task'],
                        'weekday': weekday,
                        'base_time': entry['time'],
                        'reason': 'base_time_in_freeze',
                    })
                    continue
                target_seconds = base_seconds
            else:
                boundary_start, boundary_end = boundaries.get(
                    (task_key, weekday),
                    (0, 24 * 60 * 60 - 1),
                )
                candidates = set()
                for offset in range(
                    refresh['min_offset_seconds'],
                    refresh['max_offset_seconds'] + 1,
                ):
                    signed_offsets = (0,) if offset == 0 else (-offset, offset)
                    for signed_offset in signed_offsets:
                        candidate = base_seconds + signed_offset
                        if candidate < boundary_start or candidate > boundary_end:
                            continue
                        if candidate < 0 or candidate >= 24 * 60 * 60:
                            continue
                        if any(
                            start <= candidate < end
                            for start, end in freeze_windows
                        ):
                            continue
                        candidates.add(candidate)
                available = sorted(
                    candidate
                    for candidate in candidates
                    if (weekday, candidate) not in occupied
                )
                if not available:
                    available = sorted(candidates)
                if available:
                    target_seconds = choose(available)
                else:
                    issues.append({
                        'task': entry['task'],
                        'weekday': weekday,
                        'base_time': entry['time'],
                        'reason': (
                            'base_time_in_freeze'
                            if base_is_frozen
                            else 'no_time_within_boundary'
                        ),
                    })
                    if base_is_frozen:
                        continue
                    target_seconds = base_seconds
            occupied.add((weekday, target_seconds))
            generated.append({
                'task': entry['task'],
                'weekday': weekday,
                'time': cls._format_clock_seconds(target_seconds),
            })
        return cls.normalize_entries(generated), issues

    def ensure_week_refresh(
        self,
        reference: datetime | None = None,
        force: bool = False,
        chooser=None,
    ) -> dict:
        reference = (reference or datetime.now()).replace(microsecond=0)
        data = self.load()
        refresh = data['week_refresh']
        if not data['enabled'] or not refresh['enabled']:
            return refresh
        week_key = self.week_key(reference)
        if not force and refresh['generated_week'] == week_key:
            return refresh
        generated_entries, issues = self.generate_week_refresh_entries(
            data['entries'], refresh, chooser=chooser
        )
        refresh = {
            **refresh,
            'generated_week': week_key,
            'generated_at': str(reference),
            'generated_entries': generated_entries,
            'issues': issues,
        }
        data['week_refresh'] = refresh
        write_file(str(self.path), data)
        logger.info(
            f"Weekly refresh generated: week={week_key}, "
            f"entries={len(generated_entries)}, issues={issues}"
        )
        return refresh

    def effective_entries(self, reference: date | datetime) -> list[dict]:
        data = self.load()
        refresh = data['week_refresh']
        if (
            refresh['enabled']
            and refresh['generated_week'] == self.week_key(reference)
        ):
            return refresh['generated_entries']
        return data['entries']

    @staticmethod
    def _clock_seconds(value: str) -> int:
        parsed = _parse_schedule_time(value)
        return parsed.hour * 3600 + parsed.minute * 60 + parsed.second

    @staticmethod
    def _format_clock_seconds(value: int) -> str:
        hour = value // 3600
        minute = value % 3600 // 60
        second = value % 60
        return f'{hour:02d}:{minute:02d}:{second:02d}'

    @staticmethod
    def normalize_entries(entries: list[dict]) -> list[dict]:
        normalized = []
        seen = set()
        for entry in entries:
            task = str(entry.get('task', '')).strip()
            weekday = int(entry.get('weekday', 0))
            run_time = str(entry.get('time', '')).strip()
            if not task:
                raise ValueError('Task is required')
            if weekday < 1 or weekday > 7:
                raise ValueError(f'Invalid weekday for {task}: {weekday}')
            try:
                parsed_time = _parse_schedule_time(run_time)
            except ValueError as e:
                raise ValueError(f'Invalid time for {task}: {run_time}') from e
            item = {
                'task': task,
                'weekday': weekday,
                'time': parsed_time.strftime('%H:%M:%S'),
            }
            key = (convert_to_underscore(task), weekday, item['time'])
            if key in seen:
                continue
            seen.add(key)
            normalized.append(item)
        return sorted(normalized, key=lambda item: (item['weekday'], item['time'], item['task']))

    def entries_for(self, task: str, include_disabled: bool = False) -> list[dict]:
        task_key = convert_to_underscore(task)
        data = self.load()
        if not data['enabled'] and not include_disabled:
            return []
        return [
            entry
            for entry in data['entries']
            if convert_to_underscore(entry.get('task', '')) == task_key
        ]

    def next_run(
        self,
        task: str,
        after: datetime | None = None,
        include_disabled: bool = False,
    ) -> datetime | None:
        entries = self.entries_for(task, include_disabled=include_disabled)
        if not entries:
            return None
        after = (after or datetime.now()).replace(microsecond=0)
        candidates = []
        for entry in entries:
            run_time = _parse_schedule_time(entry['time'])
            days_ahead = (entry['weekday'] - after.isoweekday()) % 7
            candidate = datetime.combine(after.date() + timedelta(days=days_ahead), run_time)
            if candidate <= after:
                candidate += timedelta(days=7)
            candidates.append(candidate)
        return min(candidates).replace(microsecond=0)

    @staticmethod
    def current_week_datetime(entry: dict, reference: datetime | None = None) -> datetime:
        reference = (reference or datetime.now()).replace(microsecond=0)
        week_start = reference.date() - timedelta(days=reference.isoweekday() - 1)
        run_date = week_start + timedelta(days=int(entry['weekday']) - 1)
        run_time = _parse_schedule_time(entry['time'])
        return datetime.combine(run_date, run_time)

    def targets_for_date(self, target_date: date) -> dict[str, datetime]:
        data = self.load()
        if not data['enabled']:
            return {}
        targets = {}
        for entry in self.effective_entries(target_date):
            if entry['weekday'] != target_date.isoweekday():
                continue
            task_key = convert_to_underscore(entry['task'])
            run_time = _parse_schedule_time(entry['time'])
            target = datetime.combine(target_date, run_time)
            current = targets.get(task_key)
            if current is None or target < current:
                targets[task_key] = target
        return targets

    def needs_daily_apply(self, target_date: date) -> bool:
        data = self.load()
        return data['enabled'] and data['last_applied_date'] != target_date.isoformat()

    def mark_applied(self, applied_at: datetime | None = None) -> None:
        applied_at = (applied_at or datetime.now()).replace(microsecond=0)
        data = self.load()
        data['last_applied_date'] = applied_at.date().isoformat()
        data['last_applied_at'] = str(applied_at)
        data['turtle_restore_pending'] = False
        write_file(str(self.path), data)

    def clear_turtle_restore_pending(self) -> None:
        data = self.load()
        if not data['turtle_restore_pending']:
            return
        data['turtle_restore_pending'] = False
        write_file(str(self.path), data)

    def next_daily_refresh(self, after: datetime | None = None) -> datetime | None:
        if not self.load()['enabled']:
            return None
        after = (after or datetime.now()).replace(microsecond=0)
        return datetime.combine(after.date() + timedelta(days=1), time.min)

    def planned_tasks(self) -> set[str]:
        data = self.load()
        if not data['enabled']:
            return set()
        return {convert_to_underscore(entry.get('task', '')) for entry in data['entries']}

    @staticmethod
    def copy(source_name: str, target_name: str) -> None:
        source = WeeklySchedule(source_name)
        if source.path.exists():
            data = source.load()
            WeeklySchedule(target_name).save(
                data['enabled'],
                data['entries'],
                data['catch_up_missed'],
                data['turtle_mode'],
                data['turtle_keep_tasks'],
                data['free_cycle_tasks'],
                data['week_refresh'],
            )

    @staticmethod
    def rename(old_name: str, new_name: str) -> None:
        old_path = WeeklySchedule(old_name).path
        new_path = WeeklySchedule(new_name).path
        if old_path.exists():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.replace(new_path)

    @staticmethod
    def delete(config_name: str) -> None:
        path = WeeklySchedule(config_name).path
        if path.exists():
            path.unlink()
