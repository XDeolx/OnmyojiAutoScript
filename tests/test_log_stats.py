import unittest

from module.server.log_stats import LogStatsParser


class LogStatsParserTest(unittest.TestCase):
    def test_scheduler_end_closes_task_before_idle_wait(self):
        lines = [
            '2026-08-27 00:13:03.187 | INFO | [Task] KekkaiUtilize (Enable, 2, 2026-08-27 00:13:00)',
            '════════════════════════════════',
            '────────── KEKKAI UTILIZE ──────────',
            '════════════════════════════════',
            '2026-08-27 00:13:03.640 | INFO | Task work started',
            '2026-08-27 00:13:43.136 | INFO | Scheduler: End task `KekkaiUtilize`',
            '2026-08-27 01:33:04.999 | INFO | [Task] RichMan (Enable, 5, 2026-08-27 01:33:00)',
            '════════════════════════════════',
            '────────── RICH MAN ──────────',
            '════════════════════════════════',
            '2026-08-27 01:33:05.267 | INFO | Task work started',
            '2026-08-27 01:33:10.267 | INFO | Scheduler: End task `RichMan`',
        ]

        payload = LogStatsParser.parse_lines(lines, script_name='test')
        run = payload['tasks']['KekkaiUtilize']['runs'][0]

        self.assertEqual(run['start_time'], '2026-08-27 00:13:03.640')
        self.assertEqual(run['end_time'], '2026-08-27 00:13:43.136')
        self.assertEqual(run['duration_seconds'], 39.496)

    def test_scheduler_end_only_closes_matching_task(self):
        parser = LogStatsParser()
        parser.consume_lines([
            '2026-08-27 00:13:03.187 | INFO | [Task] KekkaiUtilize (Enable, 2, 2026-08-27 00:13:00)',
            '════════════════════════════════',
            '────────── KEKKAI UTILIZE ──────────',
            '════════════════════════════════',
            '2026-08-27 00:13:03.640 | INFO | Task work started',
            '2026-08-27 00:13:20.000 | INFO | Scheduler: End task `RichMan`',
            '2026-08-27 00:13:43.136 | INFO | Scheduler: End task `KekkaiUtilize`',
        ])

        run = parser.snapshot()['tasks']['KekkaiUtilize']['runs'][0]
        self.assertEqual(run['end_time'], '2026-08-27 00:13:43.136')


if __name__ == '__main__':
    unittest.main()
