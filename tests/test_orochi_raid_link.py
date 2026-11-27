from datetime import datetime, timedelta
from types import SimpleNamespace as NS
import sys
import unittest
from unittest.mock import patch

from module.exception import TaskEnd, ScriptError, GamePageUnknownError
from tasks.Orochi.realm_raid_link import RealmRaidLink


class LinkTest(unittest.TestCase):
    def owner(self, resume=True, role='alone'):
        owner = RealmRaidLink()
        link = NS(enable=True, interval_count=20, interval_minutes=10, ticket_threshold=25,
                  resume_after_raid=resume)
        owner.config = NS(orochi=NS(orochi_config=NS(user_status=role), realm_raid_link=link),
                          realm_raid=NS(raid_config=NS(number_base=0),
                                        switch_soul_config=NS(enable=False, enable_switch_by_name=False)))
        owner.current_count, owner.limit_count = 20, 100
        owner.start_time, owner.limit_time = datetime.now(), timedelta(hours=1)
        owner._raid_last_count, owner._raid_last_time = 0, 0
        owner._raid_link_stopped = False
        owner._raid_link_active = True
        owner.events = []
        owner._restore_orochi_page = lambda: owner.events.append('restore')
        owner.switch_orochi_souls = lambda: owner.events.append('souls')
        owner._set_link_soul_buff = lambda b: owner.events.append(('buff', b))
        owner._read_raid_tickets = lambda _: 30
        runner = NS(completed=False, succeeded=False, goto_page=lambda _: None)
        def run():
            runner.completed = runner.succeeded = True
            raise TaskEnd
        runner.run = run
        owner._make_raid_runner = lambda: runner
        return owner, runner

    def call(self, owner, final=False):
        with patch.dict(sys.modules, {'tasks.GameUi.page': NS(page_main='main', page_realm_raid='raid')}):
            return owner._run_linked_realm_raid(final)

    def test_resume_retains_counter_and_restores_setup(self):
        owner, _ = self.owner()
        self.assertFalse(self.call(owner))
        self.assertEqual(owner.current_count, 20)
        self.assertEqual(owner.limit_count, 100)
        self.assertEqual(owner.events, [('buff', False), 'souls', ('buff', True), 'restore'])
        self.assertEqual(owner._raid_last_count, 20)

    def test_switch_off_stops_remaining_run(self):
        owner, _ = self.owner(resume=False)
        self.assertTrue(self.call(owner))
        self.assertTrue(owner._raid_link_stopped)
        self.assertNotIn('souls', owner.events)

    def test_multiplayer_never_enters_link(self):
        for role in ['leader', 'member', 'wild']:
            owner, _ = self.owner(role=role)
            self.assertFalse(owner._raid_check_due())
            self.assertFalse(self.call(owner, final=True))
            self.assertEqual(owner.events, [])

    def test_reused_solo_loop_does_not_enable_link(self):
        owner, _ = self.owner()
        owner._raid_link_active = False
        self.assertFalse(owner._raid_check_due())
        self.assertFalse(self.call(owner, final=True))

    def test_final_uses_remaining_tickets_without_restart(self):
        owner, _ = self.owner()
        owner.current_count = 100
        owner._read_raid_tickets = lambda _: 3
        self.assertTrue(self.call(owner, final=True))
        self.assertNotIn('souls', owner.events)

    def test_below_threshold_returns_to_original_page(self):
        owner, runner = self.owner()
        owner._read_raid_tickets = lambda _: 12
        self.assertFalse(self.call(owner))
        self.assertFalse(runner.completed)
        self.assertEqual(owner.events, ['restore'])

    def test_failed_raid_does_not_resume(self):
        owner, runner = self.owner()
        def fail():
            runner.completed = True
            raise TaskEnd
        runner.run = fail
        with self.assertRaises(ScriptError):
            self.call(owner)
        self.assertNotIn('souls', owner.events)

    def test_resume_requires_soul_restoration_when_raid_switches(self):
        owner, _ = self.owner()
        owner.config.realm_raid.switch_soul_config.enable = True
        owner.config.orochi.switch_soul = NS(auto_switch_soul=False, enable=False, enable_switch_by_name=False)
        with self.assertRaises(ScriptError):
            self.call(owner)
        self.assertEqual(owner.events, [])

    def test_due_by_count_or_time_and_can_disable_both(self):
        owner, _ = self.owner()
        with patch('tasks.Orochi.realm_raid_link.time.monotonic', return_value=0):
            self.assertTrue(owner._raid_check_due())
            owner.current_count = 1
            self.assertFalse(owner._raid_check_due())
        with patch('tasks.Orochi.realm_raid_link.time.monotonic', return_value=600):
            self.assertTrue(owner._raid_check_due())
            owner.config.orochi.realm_raid_link.interval_count = 0
            owner.config.orochi.realm_raid_link.interval_minutes = 0
            self.assertFalse(owner._raid_check_due())

    def test_unreadable_tickets_do_not_trigger_raid(self):
        owner, _ = self.owner()
        owner.device = NS(image=None)
        runner = NS(screenshot=lambda: None, O_NUMBER=NS(ocr=lambda _: (0, 0, 0)))
        with patch('tasks.Orochi.realm_raid_link.time.sleep'):
            with self.assertRaises(GamePageUnknownError):
                RealmRaidLink._read_raid_tickets(owner, runner)


if __name__ == '__main__':
    unittest.main()
