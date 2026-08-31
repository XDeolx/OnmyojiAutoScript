import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from tasks.KekkaiUtilize.config import UtilizeConfig
from tasks.KekkaiUtilize.script_task import ScriptTask


class KekkaiUtilizeAntiBanTest(unittest.TestCase):
    def test_minimum_interval_defaults_to_disabled(self):
        self.assertEqual(UtilizeConfig().min_run_interval, timedelta(0))

    def test_rest_interval_starts_after_card_expires(self):
        now = datetime(2026, 8, 29, 12, 0)
        result = ScriptTask._next_utilize_run_time(
            timedelta(minutes=30),
            timedelta(hours=2),
            now,
            interval_factor=0.6,
        )
        self.assertEqual(result, datetime(2026, 8, 29, 13, 42))

    def test_rest_interval_is_added_to_full_card_duration(self):
        now = datetime(2026, 8, 29, 12, 0)
        result = ScriptTask._next_utilize_run_time(
            timedelta(hours=6),
            timedelta(hours=2),
            now,
            interval_factor=0.9,
        )
        self.assertEqual(result, datetime(2026, 8, 29, 19, 48))

    def test_rest_interval_samples_factor_once_per_schedule(self):
        with patch(
            'tasks.KekkaiUtilize.script_task.random.uniform',
            return_value=0.75,
        ) as uniform:
            interval, factor = ScriptTask._sample_rest_interval(
                timedelta(minutes=20),
            )

        self.assertEqual(interval, timedelta(minutes=15))
        self.assertEqual(factor, 0.75)
        uniform.assert_called_once_with(0.6, 0.9)

    def test_randomized_interval_is_rounded_to_whole_seconds(self):
        interval, factor = ScriptTask._sample_rest_interval(
            timedelta(seconds=7),
            factor=0.75,
        )

        self.assertEqual(interval, timedelta(seconds=5))
        self.assertEqual(factor, 0.75)

    def test_disabled_rest_interval_does_not_sample_random_factor(self):
        with patch(
            'tasks.KekkaiUtilize.script_task.random.uniform',
        ) as uniform:
            interval, factor = ScriptTask._sample_rest_interval(timedelta(0))

        self.assertEqual(interval, timedelta(0))
        self.assertEqual(factor, 0.0)
        uniform.assert_not_called()


if __name__ == '__main__':
    unittest.main()
