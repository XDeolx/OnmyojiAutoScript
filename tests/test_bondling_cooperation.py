import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from module.cooperation import Cooperation
from module.exception import ScriptError, TaskEnd
from tasks.BondlingFairyland.cooperation import prepare_handoff, TASK


class HandoffWakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'config').mkdir()
        self.write('alpha', 'handoff1', 'beta')
        self.write('beta', 'handoff2', '')
        self.a = Cooperation('alpha', self.root)
        self.b = Cooperation('beta', self.root)
        self.a.publish(TASK)
        self.b.publish('')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, role, peer):
        data = {'bondling_fairyland': {'scheduler': {'enable': True},
            'bondling_config': {'user_status': role, 'bondling_mode': '只刷契灵(低级式盘)',
                                'bondling_stone_class': '测试契灵'},
            'invite_config': {'cooperation_script': peer}}}
        (self.root / 'config' / f'{name}.json').write_text(json.dumps(data), encoding='utf-8')

    def config(self, peer=''):
        calls = []
        item = NS(scheduler=NS(enable=True), invite_config=NS(cooperation_script=peer,
                   wait_time=NS(hour=0, minute=0, second=2)))
        return NS(model=NS(bondling_fairyland=item), bondling_fairyland=item,
                  reload=lambda: None, task_call=lambda *a, **k: calls.append(a),
                  task_delay=lambda **k: calls.append(k), calls=calls)

    def test_idle_peer_wakes(self):
        self.assertTrue(self.a.prepare(self.config('beta'), TASK, 'beta', defer=False))
        config = self.config()
        self.assertEqual(self.b.wake_next(config), TASK)
        self.assertEqual(config.calls, [(TASK,)])
        self.assertEqual(self.b.accepted_peer(TASK), 'alpha')

    def test_busy_peer_is_queued_without_interrupt(self):
        self.b.publish('OtherTask')
        self.assertFalse(self.a.prepare(self.config('beta'), TASK, 'beta', defer=False))
        self.assertEqual(self.b.runner_task('beta'), 'OtherTask')
        self.b.publish('')
        self.assertEqual(self.b.wake_next(self.config()), TASK)

    def test_stale_request_discarded(self):
        self.a.prepare(self.config('beta'), TASK, 'beta', defer=False)
        self.a.publish('')
        self.assertIsNone(self.b.wake_next(self.config()))
        self.assertEqual(self.b.requested(), [])

    def test_same_roles_rejected(self):
        self.write('beta', 'handoff1', '')
        with self.assertRaises(ScriptError):
            self.a.validate(TASK, 'beta')

    def test_disabled_peer_rejected(self):
        path = self.root / 'config/beta.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['bondling_fairyland']['scheduler']['enable'] = False
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ScriptError):
            self.a.validate(TASK, 'beta')

    def test_timeout_clears_pending_wake(self):
        config = self.config('beta')
        self.b.publish('OtherTask')
        with patch('tasks.BondlingFairyland.cooperation.time.monotonic', side_effect=[0, 3]):
            with self.assertRaises(TaskEnd):
                prepare_handoff(NS(config=config, cooperation_runtime=self.a))
        self.assertEqual(self.b.requested(), [])
        self.assertFalse(config.calls[0]['success'])

    def test_reverse_start_discovers_one_sided_pair(self):
        self.b.publish(TASK)
        config = self.config()
        prepare_handoff(NS(config=config, cooperation_runtime=self.b))
        self.assertEqual(config.calls, [])
        self.assertEqual(self.b.peers[TASK], 'alpha')

    def test_offline_peer_defers_without_wake(self):
        self.b.close()
        config = self.config('beta')
        with self.assertRaises(TaskEnd):
            prepare_handoff(NS(config=config, cooperation_runtime=self.a))
        self.assertFalse(config.calls[0]['success'])
        self.assertEqual(self.b.requested(), [])

    def test_waits_for_idle_peer_to_start(self):
        config = self.config('beta')
        def start(_):
            self.b.wake_next(self.config())
            self.b.publish(TASK)
        with patch('tasks.BondlingFairyland.cooperation.time.sleep', side_effect=start):
            prepare_handoff(NS(config=config, cooperation_runtime=self.a))
        self.assertEqual(config.calls, [])


if __name__ == '__main__':
    unittest.main()
