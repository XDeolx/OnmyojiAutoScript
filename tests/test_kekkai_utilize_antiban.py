import unittest
from datetime import datetime, timedelta

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
        )
        self.assertEqual(result, datetime(2026, 8, 29, 14, 30))

    def test_rest_interval_is_added_to_full_card_duration(self):
        now = datetime(2026, 8, 29, 12, 0)
        result = ScriptTask._next_utilize_run_time(
            timedelta(hours=6),
            timedelta(hours=2),
            now,
        )
        self.assertEqual(result, datetime(2026, 8, 29, 20, 0))


if __name__ == '__main__':
    unittest.main()
