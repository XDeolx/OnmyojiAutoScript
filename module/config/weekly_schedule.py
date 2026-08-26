# This Python file uses the following encoding: utf-8
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from module.config.utils import convert_to_underscore, read_file, write_file


class WeeklySchedule:
    """Persistent weekly task schedule for one script config."""

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
            'entries': clean_entries,
            'last_applied_date': str(raw.get('last_applied_date', '')),
            'last_applied_at': str(raw.get('last_applied_at', '')),
        }

    def save(self, enabled: bool, entries: list[dict], catch_up_missed: bool | None = None) -> dict:
        previous = self.load()
        was_enabled = previous['enabled']
        data = {
            'enabled': bool(enabled),
            'catch_up_missed': (
                previous['catch_up_missed']
                if catch_up_missed is None
                else bool(catch_up_missed)
            ),
            'entries': self.normalize_entries(entries),
            'last_applied_date': previous['last_applied_date'],
            'last_applied_at': previous['last_applied_at'],
        }
        if enabled and not was_enabled:
            data['last_applied_date'] = ''
            data['last_applied_at'] = ''
        write_file(str(self.path), data)
        return data

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
                parsed_time = datetime.strptime(run_time, '%H:%M').time()
            except ValueError as e:
                raise ValueError(f'Invalid time for {task}: {run_time}') from e
            item = {
                'task': task,
                'weekday': weekday,
                'time': parsed_time.strftime('%H:%M'),
            }
            key = (convert_to_underscore(task), weekday, item['time'])
            if key in seen:
                continue
            seen.add(key)
            normalized.append(item)
        return sorted(normalized, key=lambda item: (item['weekday'], item['time'], item['task']))

    def entries_for(self, task: str) -> list[dict]:
        task_key = convert_to_underscore(task)
        data = self.load()
        if not data['enabled']:
            return []
        return [
            entry
            for entry in data['entries']
            if convert_to_underscore(entry.get('task', '')) == task_key
        ]

    def next_run(self, task: str, after: datetime | None = None) -> datetime | None:
        entries = self.entries_for(task)
        if not entries:
            return None
        after = (after or datetime.now()).replace(microsecond=0)
        candidates = []
        for entry in entries:
            run_time = datetime.strptime(entry['time'], '%H:%M').time()
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
        run_time = datetime.strptime(entry['time'], '%H:%M').time()
        return datetime.combine(run_date, run_time)

    def targets_for_date(self, target_date: date) -> dict[str, datetime]:
        data = self.load()
        if not data['enabled']:
            return {}
        targets = {}
        for entry in data['entries']:
            if entry['weekday'] != target_date.isoweekday():
                continue
            task_key = convert_to_underscore(entry['task'])
            run_time = datetime.strptime(entry['time'], '%H:%M').time()
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
