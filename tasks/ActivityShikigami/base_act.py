import time

from datetime import datetime, timedelta
import random
from tasks.Component.GeneralBattle.general_battle import GeneralBattle, ExitMatcher, BattleContext, BattleAction
from cached_property import cached_property

from module.atom.image import RuleImage
from module.base.protect import random_sleep
from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger

from tasks.base_task import BaseTask
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import GeneralBattleConfig, ActivityShikigami
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
import tasks.ActivityShikigami.page as pages
from typing import Optional, Callable


class LimitTimeOut(Exception):
    pass


class LimitCountOut(Exception):
    pass


class TicketsNotEnough(Exception):
    pass


class StateMachine(BaseTask):
    run_idx: int = 0  # 当前爬塔类型
    _count_map = None
    _pre_tickets_map = None
    switch_souled: dict[str, bool] = {}

    @cached_property
    def conf(self) -> ActivityShikigami:
        return self.config.model.activity_shikigami

    @property
    def climb_type(self) -> str:
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            return self.conf.general_climb.run_sequence_v[-1]
        return self.conf.general_climb.run_sequence_v[self.run_idx]

    @property
    def count_map(self) -> dict[str, int]:
        """
        :return: key: climb type, value: run count
        """
        if not getattr(self, "_count_map", None):
            self._count_map = {climb_type: 0 for climb_type in self.conf.general_climb.run_sequence_v}
        return self._count_map

    @property
    def pre_tickets_map(self) -> dict[str, int]:
        """
        :return: key: climb type, value: pre tickets num
        """
        if not getattr(self, "_pre_tickets_map", None):
            self._pre_tickets_map = {climb_type: -1 for climb_type in self.conf.general_climb.run_sequence_v}
        return self._pre_tickets_map

    def update_status(self):
        """
        更新全局状态
        """

        def get_count() -> int:
            return self.count_map[self.climb_type]

        def get_limit() -> int:
            limit = getattr(self.conf.general_climb, f'{self.climb_type}_limit', 0)
            return 0 if not limit else limit

        # 超过运行时间
        if datetime.now() - self.start_time >= self.conf.general_climb.limit_time_v:
            logger.info(f"Climb type {self.climb_type} time out")
            raise LimitTimeOut
        # 次数达到限制
        if get_count() >= get_limit():
            logger.info(f"Climb type {self.climb_type} count limit reached")
            raise LimitCountOut

    def switch_next(self):
        """
        切换下一种爬塔类型
        :return: True 切换成功 or False
        """
        self.run_idx += 1
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            logger.info('All climbing activities have been completed')
            return False
        # 切换爬塔类型了, 恢复所有状态
        self.current_count = 0
        logger.hr(f'Climb switch to {self.climb_type}', 2)
        return True


class BaseAct(StateMachine, GameUi, GeneralBattle, SwitchSoul, ActivityShikigamiAssets):
    """爬塔活动基类"""

    def _exit_matcher(self) -> ExitMatcher | None:
        return self.I_ACT_FIRE

    def _handle_result(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        if not self._fatigue_settlement_click_ready(context):
            return BattleAction.CONTINUE
        if self.climb_type == 'boss':
            self.appear_then_click(self.I_UI_BACK_RED, interval=1.5)
        return super()._handle_result(context, config)

    def _handle_reward(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        if not self._fatigue_settlement_click_ready(context):
            return BattleAction.CONTINUE
        return super()._handle_reward(context, config)

    def _reset_round_context(self, context: BattleContext, config: GeneralBattleConfig, *, continuous_count: int) -> None:
        super()._reset_round_context(context, config, continuous_count=continuous_count)
        for attribute in (
            'fatigue_settlement_delay_timer',
            'fatigue_settlement_delay',
            'fatigue_settlement_delay_logged',
        ):
            if hasattr(context, attribute):
                delattr(context, attribute)

    def before_run(self):
        self._fatigue_battle_count = 0
        pages.page_battle_result = self.navigator.resolve_page(pages.page_battle_result)
        pages.page_battle_result.recognizer = pages.any_of(self.I_UI_BACK_RED, pages.page_battle_result.recognizer)

    def _fatigue_rest_enabled(self) -> bool:
        return self.conf.general_climb.fatigue_rest_enable

    def _apply_fatigue_rest(self):
        """在下一场挑战前，处理已经完成的疲劳周期。"""
        if not self._fatigue_rest_enabled():
            return

        config = self.conf.general_climb
        completed = self._fatigue_battle_count
        if completed < config.fatigue_rest_battle_count:
            return

        rest_minutes = round(random.uniform(
            config.fatigue_rest_minutes_min,
            config.fatigue_rest_minutes_max,
        ), 2)
        rest_seconds = rest_minutes * 60
        logger.info(
            'Climb fatigue rest: '
            f'completed={completed}/{config.fatigue_rest_battle_count}, '
            f'duration={rest_minutes:.2f}m'
        )
        rest_started_at = datetime.now()
        time.sleep(rest_seconds)
        actual_rest = datetime.now() - rest_started_at
        # 疲劳休息不占用活动的有效运行时长。
        self.start_time += actual_rest
        self._fatigue_battle_count = 0
        logger.info(
            'Climb fatigue rest finished: '
            f'actual_duration={actual_rest.total_seconds() / 60:.2f}m, cycle reset'
        )

    def _apply_fatigue_battle_delay(self):
        """按当前疲劳进度，为下一场挑战生成渐进且带浮动的点击等待。"""
        if not self._fatigue_rest_enabled():
            return 0.0

        config = self.conf.general_climb
        cycle_count = config.fatigue_rest_battle_count
        progress = min(self._fatigue_battle_count, cycle_count - 1) / max(cycle_count - 1, 1)
        center = config.fatigue_rest_delay_min + (
            config.fatigue_rest_delay_max - config.fatigue_rest_delay_min
        ) * progress
        spread = min(0.8, max(0.1, (config.fatigue_rest_delay_max - config.fatigue_rest_delay_min) * 0.2))
        lower = max(config.fatigue_rest_delay_min, center - spread)
        upper = min(config.fatigue_rest_delay_max, center + spread)
        delay = round(random.triangular(lower, upper, center), 2)
        logger.info(
            'Climb fatigue delay: '
            f'progress={self._fatigue_battle_count + 1}/{cycle_count}, '
            f'delay={delay:.2f}s, range={lower:.2f}-{upper:.2f}s'
        )
        time.sleep(delay)
        return delay

    def _fatigue_settlement_click_ready(self, context: BattleContext) -> bool:
        """在每轮结算第一次退出点击前应用疲劳模式的随机等待。"""
        if not self._fatigue_rest_enabled():
            return True

        timer = getattr(context, 'fatigue_settlement_delay_timer', None)
        if timer is None:
            config = self.conf.general_climb
            delay = round(random.uniform(
                config.fatigue_rest_settlement_delay_min,
                config.fatigue_rest_settlement_delay_max,
            ), 2)
            context.fatigue_settlement_delay = delay
            context.fatigue_settlement_delay_timer = Timer(delay).start()
            logger.info(f'Climb fatigue settlement delay: delay={delay:.2f}s')
            return False

        if not timer.reached():
            return False

        if not getattr(context, 'fatigue_settlement_delay_logged', False):
            logger.info(
                'Climb fatigue settlement delay finished: '
                f'delay={context.fatigue_settlement_delay:.2f}s'
            )
            context.fatigue_settlement_delay_logged = True
        return True

    def _record_fatigue_battle(self):
        if not self._fatigue_rest_enabled():
            return
        self._fatigue_battle_count += 1
        logger.info(
            'Climb fatigue progress: '
            f'completed={self._fatigue_battle_count}/{self.conf.general_climb.fatigue_rest_battle_count}'
        )

    @property
    def act_page_handle_dict(self) -> dict[pages.Page, Callable]:
        """活动页面和处理器的映射"""
        return {
            pages.page_act_pass: self._run_pass,
            pages.page_act_ap: self._run_ap,
            pages.page_act_ap100: self._run_ap100,
            pages.page_act_boss: self._run_boss,
            pages.page_battle_prepare: lambda: self.run_general_battle(getattr(self.conf, f'{self.climb_type}_battle_conf'),
                                                                       battle_key=f'act_{self.climb_type}'),
            pages.page_battle: lambda: self.run_general_battle(getattr(self.conf, f'{self.climb_type}_battle_conf'),
                                                                       battle_key=f'act_{self.climb_type}'),
            pages.page_reward: lambda: self.click(pages.reward_random_click(), interval=1.5),
        }

    def run(self):
        self.before_run()
        for climb_type in self.conf.general_climb.run_sequence_v:
            logger.hr(f'Start run {self.climb_type}', 1)
            dest_page: Optional[pages.Page] = getattr(pages, f'page_act_{climb_type}', None)
            if not dest_page:
                logger.warning(f'{climb_type} page is not supported')
                continue
            self.goto_page(dest_page)
            cur_battle_conf = getattr(self.conf, f'{climb_type}_battle_conf')
            if cur_battle_conf is None:
                logger.warning(f'{climb_type} battle config is not supported')
                continue
            self.lock_team(cur_battle_conf)
            try:
                while True:
                    self.screenshot()
                    self.update_status()
                    current_page = self.get_current_page()
                    if current_page is None:
                        time.sleep(0.5)
                        continue
                    handle = self.act_page_handle_dict.get(current_page, None)
                    if handle is None:
                        self.goto_page(dest_page)
                        continue
                    handle()
            except (LimitCountOut, LimitTimeOut, TicketsNotEnough):
                pass
            finally:
                self.switch_next()  # 切换下一个爬塔类型
        self.goto_page(pages.page_main)
        if self.conf.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def _run_pass(self):
        self._run_common()

    def _run_ap(self):
        self._run_common()

    def _run_ap100(self):
        self._run_common()

    def _run_boss(self):
        self._run_common()

    def _run_common(self):
        if not self.check_tickets_enough():
            logger.warning(f'No tickets left, wait for next time')
            raise TicketsNotEnough
        self._apply_fatigue_rest()
        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS)
        if self._fatigue_rest_enabled():
            self._apply_fatigue_battle_delay()
        elif self.conf.general_climb.random_sleep:
            random_sleep(probability=0.2)
        if self.enter_battle():
            self.count_map[self.climb_type] += 1
            self.run_general_battle(getattr(self.conf, f'{self.climb_type}_battle_conf'),
                                    battle_key=f'act_{self.climb_type}')
            self._record_fatigue_battle()

    def enter_battle(self):
        click_times, max_times = 0, random.randint(3, 5)
        while True:
            self.screenshot()
            if self.is_in_battle(False):
                return True
            if click_times >= max_times:
                logger.warning(f'{self.climb_type} cannot enter battle, click reach max times')
                raise TicketsNotEnough
            if self.appear(self.I_UI_BACK_RED, interval=1):
                logger.warning(
                    f'{self.climb_type} cannot enter battle, appear red close button, maybe not enough tickets')
                raise TicketsNotEnough
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1) or \
                    self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.ocr_appear_click(self.O_FIRE, interval=1.5):
                self.device.click_record_clear()
                click_times += 1
                logger.info(f'Try click fire, remain times[{max_times - click_times}]')
                continue

    def switch_soul(self, enter_button: RuleImage):
        if self.switch_souled.get(self.climb_type, False):
            return
        self.switch_souled[self.climb_type] = True
        conf = self.conf.switch_soul_config
        enable_switch = getattr(conf, f"enable_switch_{self.climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{self.climb_type}_by_name", False)
        if not enable_switch and not enable_by_name:
            return
        logger.hr('Start switch soul', 2)
        conf.validate_switch_soul()
        self.ui_click(enter_button, stop=self.I_CHECK_RECORDS, interval=1)
        if enable_by_name:
            group, team = getattr(conf, f"{self.climb_type}_group_team_name").split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{self.climb_type}_group_team")
            self.run_switch_soul(group_team)
        self.goto_page(getattr(pages, f"page_act_{self.climb_type}"))

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """
        根据配置判断当前爬塔类型是否锁定阵容, 并执行锁定或解锁
        """
        enable = battle_conf.lock_team_enable
        if enable:
            logger.info(f'Lock {self.climb_type} team')
            match self.climb_type:
                case 'ap' | 'boss':
                    self.ui_click(self.I_AP_UNLOCK, stop=self.I_AP_LOCK, interval=1.5)
                case _:
                    self.ui_click(self.I_UNLOCK, stop=self.I_LOCK, interval=1.5)
            return
        logger.info(f'Unlock {self.climb_type} team')
        match self.climb_type:
            case 'ap' | 'boss':
                self.ui_click(self.I_AP_LOCK, stop=self.I_AP_UNLOCK, interval=1.5)
            case _:
                self.ui_click(self.I_LOCK, stop=self.I_UNLOCK, interval=1.5)

    def check_tickets_enough(self) -> bool:
        """
        判断当前爬塔门票是否足够
        :return: True 可以运行 or False
        """
        logger.hr(f'Check {self.climb_type} tickets')
        self.screenshot()
        remain_times = 0
        if self.climb_type == 'pass':
            remain_times = self.O_REMAIN_PASS.ocr_digit(self.device.image)
        if self.climb_type == 'ap':
            remain_times = self.O_REMAIN_AP.ocr_digit(self.device.image)
        if self.climb_type == 'boss':
            cur, remain_times, total = self.O_REMAIN_BOSS.ocr_digit_counter(self.device.image)
        if self.climb_type == 'ap100':
            remain_times = self.O_REMAIN_AP100.ocr_digit(self.device.image)
        # 上一次识别的票的数量和这一次识别的数量差距大于1, 则认为票数量有误, 允许继续挑战
        if self.pre_tickets_map[self.climb_type] - remain_times > 1:
            self.pre_tickets_map[self.climb_type] -= 1
            return True
        self.pre_tickets_map[self.climb_type] = remain_times
        return remain_times > 0
