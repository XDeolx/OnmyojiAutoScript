import unittest

from module.config.config_menu import ConfigMenu
from module.exception import TaskEnd
from tasks.MartialTournament.script_task import ScriptTask


class MartialTournamentRetiredTest(unittest.TestCase):
    def test_martial_tournament_is_hidden_from_activity_menu(self):
        self.assertNotIn('MartialTournament', ConfigMenu().menu['Activity Task'])

    def test_legacy_schedule_ends_without_loading_event_resources(self):
        task = object.__new__(ScriptTask)
        next_runs = []
        task.set_next_run = lambda **kwargs: next_runs.append(kwargs)

        with self.assertRaises(TaskEnd):
            task.run()

        self.assertEqual(next_runs, [{'task': 'MartialTournament', 'success': True}])


if __name__ == '__main__':
    unittest.main()
