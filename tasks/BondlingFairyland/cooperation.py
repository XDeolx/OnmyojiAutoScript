"""Wake a paired, running scheduler without interrupting its current task."""
import time
import uuid

from module.exception import ScriptError, TaskEnd
from module.logger import logger

TASK = 'BondlingFairyland'


def prepare_handoff(owner):
    settings = owner.config.bondling_fairyland
    runtime = getattr(owner, 'cooperation_runtime', None)
    peer = settings.invite_config.cooperation_script.strip()
    if runtime is None:
        if peer:
            raise ScriptError('契灵协同需要从已启动的脚本调度器运行')
        return
    if not peer:
        # One-sided pairing still works when the receiving side starts first.
        candidates = []
        for path in (runtime.root / 'config').glob('*.json'):
            if path.stem == runtime.name:
                continue
            other = runtime.read(path.stem).get('bondling_fairyland', {})
            if (other.get('scheduler', {}).get('enable')
                    and other.get('invite_config', {}).get('cooperation_script', '').strip() == runtime.name):
                candidates.append(path.stem)
        if len(candidates) > 1:
            raise ScriptError('有多个契灵协同脚本指向当前实例，请明确配对')
        peer = next(iter(candidates), '')
    if not peer:
        return
    runtime.validate(TASK, peer)
    owner._handoff_session = uuid.uuid4().hex
    owner._handoff_peer = peer
    runtime.publish_battle_state(TASK, peer, owner._handoff_session, {"stage": "starting"})
    wait = settings.invite_config.wait_time
    seconds = wait.hour * 3600 + wait.minute * 60 + wait.second
    if seconds <= 0:
        raise ScriptError('契灵协同等待时间必须大于零')
    runtime.peers[TASK] = peer
    # prepare() queues busy partners; only scheduler boundaries consume the request.
    if runtime.runner_task(peer) is not None:
        runtime.prepare(owner.config, TASK, peer, defer=False)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            active = runtime.runner_task(peer)
            if active == TASK:
                runtime.ack(TASK)
                logger.info('契灵协同任务已启动，继续准备')
                return
            if active is None:
                break
            time.sleep(0.5)
    runtime.skip_without_wake(TASK, peer, 'handoff_start_unavailable')
    logger.warning('契灵协同对端未运行或等待超时，本次推迟，不进入单边战斗')
    owner.config.task_delay(task=TASK, success=False, server=False)
    raise TaskEnd


def publish_phase(owner, stage):
    runtime = getattr(owner, 'cooperation_runtime', None)
    peer = getattr(owner, '_handoff_peer', None)
    if not runtime or not peer:
        return
    other = runtime.peer_battle_state(TASK, peer)
    if stage == 'leader' and other and other['payload'].get('stage') == 'leader':
        logger.warning('契灵对端仍处于队长阶段，推迟本次任务以避免双队长')
        owner.config.task_delay(task=TASK, success=False, server=False)
        raise TaskEnd
    runtime.publish_battle_state(TASK, peer, owner._handoff_session,
                                {'stage': stage, 'target_session': other['session'] if other else None})


def peer_finished(owner):
    runtime = getattr(owner, 'cooperation_runtime', None)
    peer = getattr(owner, '_handoff_peer', None)
    if not runtime or not peer:
        return False
    other = runtime.peer_battle_state(TASK, peer)
    return bool(other and other['payload'].get('stage') == 'leader_done'
                and other['payload'].get('target_session') == owner._handoff_session)


def require_handoff(owner):
    if not peer_finished(owner):
        logger.warning('契灵队员未收到本轮交接确认，推迟任务，不自行切换队长')
        owner.config.task_delay(task=TASK, success=False, server=False)
        raise TaskEnd
