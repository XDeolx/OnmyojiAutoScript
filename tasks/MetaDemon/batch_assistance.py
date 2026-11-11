"""Keep the assistant attached to the parent CustomTask across account switches."""

import time

from module.exception import ScriptError
from module.logger import logger
from tasks.MetaDemon.config import AssistanceRole


BATCH_CHANNEL = 'MetaDemonAssistanceBatch'


class BatchAssistance:
    def __init__(self, task, runtime, peer):
        self.runtime = runtime
        self.peer = peer
        self.offering = task.conf.assistance_config.role == AssistanceRole.OFFERING
        self.session = getattr(task.config, 'metademon_batch_session', None) if self.offering else None
        if not peer or peer == runtime.name:
            raise ScriptError('整批鬼王协同需要填写另一实例的配置名')
        if self.offering and not self.session:
            raise ScriptError('整批鬼王上供必须在自定义任务中运行')

    def wait_for_peer(self):
        logger.info(f'等待整批鬼王协同：{self.peer}')
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.offering:
                if self.assistant_ready():
                    return True
            elif self.runtime.runner_task(self.peer) == 'CustomTask':
                state = self.runtime.peer_battle_state(BATCH_CHANNEL, self.peer)
                if state and state['payload'].get('status') == 'active':
                    self.session = state['session']
                    self._publish('ready')
                    return True
            time.sleep(0.5)
        logger.warning(f'整批鬼王协同等待超时：{self.peer}')
        return False

    def _publish(self, status):
        self.runtime.publish_battle_state(BATCH_CHANNEL, self.peer, self.session, {'status': status})

    def _peer_status(self):
        state = self.runtime.peer_battle_state(BATCH_CHANNEL, self.peer)
        if state and state['session'] == self.session:
            return state['payload'].get('status')
        return None

    def assistant_ready(self):
        return (self._peer_status() == 'ready'
                and self.runtime.runner_task(self.peer) in ('MetaDemon', 'CustomTask'))

    def offering_status(self):
        status = self._peer_status()
        if status == 'active' and self.runtime.runner_task(self.peer) == 'CustomTask':
            return status
        return status if status in ('complete', 'failed') else 'lost'

    def close(self):
        if not self.offering and self.session:
            self._publish('left')
