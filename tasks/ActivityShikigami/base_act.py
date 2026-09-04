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
from tasks.ActivityShikigami.settlement_behavior import ClimbSettlementPlanner, SettlementDecision
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
            if self.climb_type == 'pass':
                mode = self.current_pass_mode or 'easy'
                return self.pass_action_count[mode]
            return self.count_map[self.climb_type]

        def get_limit() -> int:
            if self.climb_type == 'pass':
                mode = self.current_pass_mode or 'easy'
                return self.conf.general_climb.pass_limit_for(mode)
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
        if self._settlement_region_enabled():
            return self._handle_climb_reward(context)
        return super()._handle_reward(context, config)

    def _reset_round_context(self, context: BattleContext, config: GeneralBattleConfig, *, continuous_count: int) -> None:
        super()._reset_round_context(context, config, continuous_count=continuous_count)
        for attribute in (
            'fatigue_settlement_delay_timer',
            'fatigue_settlement_delay',
            'fatigue_settlement_delay_logged',
            'climb_settlement_decision',
            'climb_settlement_special_done',
        ):
            if hasattr(context, attribute):
                delattr(context, attribute)

    def before_run(self):
        self._fatigue_battle_count = 0
        self._climb_mode_review_pending = False
        self._initialize_settlement_behavior()
        self.switch_souled = {}
        self.current_pass_mode = None
        self.pass_action_count = {'easy': 0, 'hard': 0}
        self.penta_pass_active = False
        self.climb_consumable_count = {}
        self.climb_pending_consumption = {}
        pages.page_battle_result = self.navigator.resolve_page(pages.page_battle_result)
        pages.page_battle_result.recognizer = pages.any_of(self.I_UI_BACK_RED, pages.page_battle_result.recognizer)

    def _settlement_region_enabled(self) -> bool:
        return bool(getattr(self.conf.general_climb, 'settlement_region_enable', False))

    def _initialize_settlement_behavior(self) -> None:
        self._settlement_planner = None
        if not self._settlement_region_enabled():
            return

        config = self.conf.general_climb
        self._settlement_planner = ClimbSettlementPlanner(
            detail_enabled=config.settlement_detail_enable,
            detail_interval_min=config.settlement_detail_interval_min,
            detail_interval_max=config.settlement_detail_interval_max,
            detail_delay_min=config.settlement_detail_delay_min,
            detail_delay_max=config.settlement_detail_delay_max,
            burst_percent=config.settlement_burst_percent,
        )
        planner = self._settlement_planner
        logger.info(f'Climb settlement template: {planner.template_summary}')
        if planner.detail_enabled:
            logger.info(
                'Climb settlement detail cycle: '
                f'initial_progress={planner.detail_progress}/{planner.detail_target}, '
                f'next_in={planner.detail_target - planner.detail_progress}'
            )

    def _get_settlement_planner(self) -> ClimbSettlementPlanner:
        planner = getattr(self, '_settlement_planner', None)
        if planner is None:
            self._initialize_settlement_behavior()
            planner = self._settlement_planner
        return planner

    def _begin_climb_settlement(self, context: BattleContext) -> SettlementDecision:
        decision = getattr(context, 'climb_settlement_decision', None)
        if decision is not None:
            return decision

        planner = self._get_settlement_planner()
        decision = planner.begin_settlement()
        context.climb_settlement_decision = decision
        logger.info(
            'Climb settlement behavior: '
            f'battle={decision.battle_number}, kind={decision.kind}, '
            f'detail={decision.detail_progress}/{decision.detail_target}'
        )
        if decision.kind == 'detail':
            logger.info(
                'Climb settlement detail cycle reset: '
                f'next_target={planner.detail_target}'
            )
        return decision

    def _execute_climb_burst(self, *, reason: str, battle_number: int) -> bool:
        self._climb_mode_review_pending = True
        points = self._get_settlement_planner().burst_points()
        logger.info(
            'Climb settlement burst: '
            f'battle={battle_number}, reason={reason}, clicks={len(points)}, anchor_region=R7'
        )
        completed = 0
        for index, (x, y) in enumerate(points):
            if index:
                interval = round(random.uniform(0.08, 0.18), 3)
                logger.info(
                    '爬塔快速结算随机等待: '
                    f'battle={battle_number}, reason={reason}, '
                    f'click={index + 1}/{len(points)}, delay={interval:.3f}s'
                )
                time.sleep(interval)
            self.device.click(
                x,
                y,
                control_name=f'CLIMB_SETTLEMENT_BURST_E_{reason.upper()}',
            )
            completed += 1
        return False

    def _restore_climb_mode_after_burst(self) -> None:
        """Restore the configured climb type if settlement taps changed the mode."""
        if not getattr(self, '_climb_mode_review_pending', False):
            return

        self._climb_mode_review_pending = False
        expected_type = self.climb_type
        mode_pages = {
            'pass': pages.page_act_pass,
            'ap': pages.page_act_ap,
            'ap100': pages.page_act_ap100,
            'boss': pages.page_act_boss,
        }
        expected_page = mode_pages.get(expected_type)
        if expected_page is None:
            logger.warning(
                'Climb settlement mode review skipped: '
                f'expected={expected_type}, reason=unsupported_type'
            )
            return

        current_page = None
        for _attempt in range(5):
            self.screenshot()
            current_page = GameUi.detect_page_in(
                self,
                *mode_pages.values(),
                include_global=False,
            )
            if current_page is not None:
                break
            time.sleep(0.25)

        expected_key = getattr(expected_page, 'key', None)
        current_key = getattr(current_page, 'key', None)
        actual_type = next(
            (
                climb_type
                for climb_type, page in mode_pages.items()
                if getattr(page, 'key', None) == current_key
            ),
            'unknown',
        )
        if current_page is not None and current_key == expected_key:
            logger.info(
                'Climb settlement mode review: '
                f'expected={expected_type}, actual={actual_type}, result=confirmed'
            )
            return

        logger.warning(
            'Climb settlement mode review: '
            f'expected={expected_type}, actual={actual_type}, result=restore'
        )
        self.goto_page(expected_page)
        self.screenshot()
        restored_page = GameUi.detect_page_in(self, expected_page, include_global=False)
        restored = getattr(restored_page, 'key', None) == expected_key
        log = logger.info if restored else logger.warning
        log(
            'Climb settlement mode restore: '
            f'expected={expected_type}, result={"success" if restored else "failed"}'
        )

    def _execute_climb_detail(self, decision: SettlementDecision) -> None:
        planner = self._get_settlement_planner()
        region_name, (x, y) = planner.detail_point(self.climb_type)
        delay = planner.detail_delay()
        logger.info(
            'Climb settlement detail: '
            f'battle={decision.battle_number}, region={region_name}, point=({x},{y})'
        )
        self.device.click(x, y, control_name=f'CLIMB_SETTLEMENT_{region_name.upper()}')
        logger.info(
            '爬塔查看详情随机等待: '
            f'battle={decision.battle_number}, delay={delay:.2f}s'
        )
        time.sleep(delay)
        self._execute_climb_burst(reason='detail', battle_number=decision.battle_number)

    def _weighted_climb_settlement_click(self, context: BattleContext, battle_number: int) -> bool:
        timer = context.settlement_click_timer
        if timer.started() and not timer.reached():
            return False

        category, region_name, (x, y) = self._get_settlement_planner().weighted_point()
        logger.info(
            'Climb settlement weighted click: '
            f'battle={battle_number}, category={category}, region={region_name}, point=({x},{y})'
        )
        self.device.click(x, y, control_name=f'CLIMB_SETTLEMENT_{category}_{region_name}')
        timer.limit = self._next_settlement_click_interval()
        timer.reset()
        return True

    def _handle_climb_reward(self, context: BattleContext) -> BattleAction:
        """Handle climb rewards with the task-level settlement behavior template."""
        context.reward_no_battle_ts = None
        context.is_win = True
        self.appear_then_click(self.I_OVER_GHOST, interval=0.8)
        self.appear_then_click(self.I_GB_SKIN_CONFIRM, interval=0.8)
        if context.last_page != pages.page_reward:
            self.device.click_record_clear()

        decision = self._begin_climb_settlement(context)
        special_done = getattr(context, 'climb_settlement_special_done', False)
        if decision.kind == 'detail' and not special_done:
            self._execute_climb_detail(decision)
            context.climb_settlement_special_done = True
            return BattleAction.CONTINUE
        if decision.kind == 'burst' and not special_done:
            self._execute_climb_burst(reason='random', battle_number=decision.battle_number)
            context.climb_settlement_special_done = True
            return BattleAction.CONTINUE

        self._weighted_climb_settlement_click(context, decision.battle_number)
        return BattleAction.CONTINUE

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

    def _climb_penta_enabled(self) -> bool:
        return self.climb_type == 'ap' and self.penta_pass_active

    def _climb_resource_consumption(self) -> int:
        if self.climb_type == 'ap':
            return 30 if self._climb_penta_enabled() else 6
        if self.climb_type == 'pass' and self.current_pass_mode == 'hard':
            return 5
        return 1

    def _climb_ap_pass_consumption(self) -> int:
        return 5 if self._climb_penta_enabled() else 1

    def _update_climb_consumable_count(self, name: str, raw_count: int) -> int:
        """按上一场已确认的消耗修正爬塔资源 OCR 的异常下降。"""
        previous_count = self.climb_consumable_count.get(name, -1)
        expected_consumption = self.climb_pending_consumption.pop(name, 0)
        remain = max(raw_count, 0)
        if previous_count >= 0 and expected_consumption > 0:
            expected_count = max(previous_count - expected_consumption, 0)
            if remain < expected_count:
                logger.warning(
                    f'Climb {name} OCR decreased beyond expected consumption: '
                    f'previous={previous_count}, raw={raw_count}, '
                    f'expected={expected_consumption}, corrected={expected_count}'
                )
                remain = expected_count
        self.climb_consumable_count[name] = remain
        logger.info(
            f'Climb {name} remain: raw={raw_count}, normalized={remain}, '
            f'expected_consumption={expected_consumption}'
        )
        return remain

    def _record_climb_consumption(self):
        """战斗成功进入后，记录本场的资源消耗，用于下一次 OCR 校正。"""
        consumption = self._climb_resource_consumption()
        self.climb_pending_consumption[self.climb_type] = consumption
        if self.climb_type == 'ap':
            self.climb_pending_consumption['ap_pass'] = self._climb_ap_pass_consumption()
            self.climb_pending_consumption['penta_pass'] = 1 if self._climb_penta_enabled() else 0
        logger.info(
            f'Climb consumption snapshot: type={self.climb_type}, resource={consumption}, '
            f'ap_pass={self.climb_pending_consumption.get("ap_pass", "-")}, '
            f'penta_pass={self.climb_pending_consumption.get("penta_pass", 0)}'
        )

    def _sync_climb_penta_pass(self):
        """仅在体力爬塔中同步五倍券开关，并在耗尽时自动关闭。"""
        if self.climb_type != 'ap':
            return

        configured = self.conf.general_climb.use_penta_pass
        remain = None
        if configured or self.climb_pending_consumption.get('penta_pass', 0) > 0:
            raw_remain = self.O_REMAIN_PENTA_PASS.ocr_digit(self.device.image)
            remain = self._update_climb_consumable_count('penta_pass', raw_remain)
        desired_enabled = configured and (remain is None or remain > 0)
        enabled_rule = self.I_FIGHT_PENTA_USE
        disabled_rule = self.I_FIGHT_PENTA_DISUSE
        target_rule = enabled_rule if desired_enabled else disabled_rule
        click_rule = disabled_rule if desired_enabled else enabled_rule

        for attempt in range(1, 4):
            self.screenshot()
            if self.appear(target_rule):
                self.penta_pass_active = desired_enabled
                logger.info(
                    f'Climb penta mode ready: enabled={desired_enabled}, remain={remain}'
                )
                return
            if not self.appear(click_rule):
                self.penta_pass_active = self.appear(enabled_rule)
                logger.warning(
                    f'Cannot identify climb penta toggle state: '
                    f'enabled={desired_enabled}, remain={remain}'
                )
                return
            self.click(click_rule, interval=0)
            time.sleep(0.5)
            logger.info(
                f'Toggle climb penta mode: enabled={desired_enabled}, attempt={attempt}/3'
            )

        self.screenshot()
        self.penta_pass_active = self.appear(enabled_rule)
        logger.warning(
            f'Failed to synchronize climb penta mode: enabled={desired_enabled}, remain={remain}'
        )

    def _sync_pass_difficulty(self):
        """切换门票简单/困难模式，并在三次未确认后仅结束当前模式。"""
        mode = self.current_pass_mode or 'easy'
        if mode == 'hard':
            target_rule = self.I_CHECK_CLIMB_HARD
            click_rule = self.C_CL_SELECT_HARD
        else:
            target_rule = self.I_CHECK_CLIMB_EASY
            click_rule = self.C_CL_SELECT_EASY

        for attempt in range(1, 4):
            self.screenshot()
            if self.appear(target_rule):
                logger.info(f'Pass mode ready: {mode}')
                return
            self.click(click_rule, interval=0)
            if self.wait_until_appear(target_rule, wait_time=3):
                self.device.click_record_clear()
                logger.info(f'Pass mode selected: {mode}, attempt={attempt}/3')
                return
            logger.warning(f'Pass mode selection timeout: {mode}, attempt={attempt}/3')

        raise TicketsNotEnough(f'Cannot select pass mode: {mode}')

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
        while self.run_idx < len(self.conf.general_climb.run_sequence_v):
            if self.climb_type == 'pass':
                # 困难门票收益优先；旧配置中的单个次数仍只会运行简单模式。
                for mode in ('hard', 'easy'):
                    if self.conf.general_climb.pass_limit_for(mode) <= 0:
                        logger.info(f'Skip pass mode {mode}: limit is 0')
                        continue
                    self.current_pass_mode = mode
                    self._run_current_climb_type()
            else:
                self.current_pass_mode = None
                self._run_current_climb_type()
            self.current_pass_mode = None
            self.switch_next()
        self.goto_page(pages.page_main)
        if self.conf.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def _run_current_climb_type(self):
        logger.hr(
            f'Start run {self.climb_type}'
            + (f'/{self.current_pass_mode}' if self.current_pass_mode else ''),
            1,
        )
        dest_page: Optional[pages.Page] = getattr(pages, f'page_act_{self.climb_type}', None)
        if not dest_page:
            logger.warning(f'{self.climb_type} page is not supported')
            return
        self.goto_page(dest_page)
        if self.climb_type == 'pass':
            self._sync_pass_difficulty()
        cur_battle_conf = getattr(self.conf, f'{self.climb_type}_battle_conf')
        if cur_battle_conf is None:
            logger.warning(f'{self.climb_type} battle config is not supported')
            return
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
                    if self.climb_type == 'pass':
                        self._sync_pass_difficulty()
                    continue
                handle()
        except (LimitCountOut, LimitTimeOut, TicketsNotEnough) as error:
            logger.info(
                f'Finish climb type {self.climb_type}'
                + (f'/{self.current_pass_mode}' if self.current_pass_mode else '')
                + f': {error}'
            )

    def _run_pass(self):
        self._run_common()

    def _run_ap(self):
        self._run_common()

    def _run_ap100(self):
        self._run_common()

    def _run_boss(self):
        self._run_common()

    def _run_common(self):
        if self.climb_type == 'ap':
            self._sync_climb_penta_pass()
        if not self.check_tickets_enough():
            logger.warning(f'No tickets left, wait for next time')
            raise TicketsNotEnough
        self._apply_fatigue_rest()
        soul_type = 'ap100' if (
            self.climb_type == 'pass' and self.current_pass_mode == 'hard'
        ) else self.climb_type
        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS, soul_type=soul_type)
        if self.climb_type == 'pass':
            self._sync_pass_difficulty()
        if self._fatigue_rest_enabled():
            self._apply_fatigue_battle_delay()
        elif self.conf.general_climb.random_sleep:
            random_sleep(probability=0.2)
        if self.enter_battle():
            self._record_climb_consumption()
            if self.climb_type == 'pass':
                mode = self.current_pass_mode or 'easy'
                self.pass_action_count[mode] += 1
                logger.info(
                    f'Pass mode {mode} action count: '
                    f'{self.pass_action_count[mode]}/{self.conf.general_climb.pass_limit_for(mode)}'
                )
            else:
                self.count_map[self.climb_type] += 1
            self.run_general_battle(getattr(self.conf, f'{self.climb_type}_battle_conf'),
                                    battle_key=f'act_{self.climb_type}')
            self._restore_climb_mode_after_burst()
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

    def switch_soul(self, enter_button: RuleImage, soul_type: str = None):
        soul_type = soul_type or self.climb_type
        if self.switch_souled.get(soul_type, False):
            return
        self.switch_souled[soul_type] = True
        conf = self.conf.switch_soul_config
        enable_switch = getattr(conf, f"enable_switch_{soul_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{soul_type}_by_name", False)
        if not enable_switch and not enable_by_name:
            return
        logger.hr('Start switch soul', 2)
        conf.validate_switch_soul()
        self.ui_click(enter_button, stop=self.I_CHECK_RECORDS, interval=1)
        if enable_by_name:
            group, team = getattr(conf, f"{soul_type}_group_team_name").split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{soul_type}_group_team")
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
        ap_pass_remain = None
        if self.climb_type == 'pass':
            remain_times = self.O_REMAIN_PASS.ocr_digit(self.device.image)
        if self.climb_type == 'ap':
            remain_times = self.O_REMAIN_AP.ocr_digit(self.device.image)
            ap_pass_remain = self.O_REMAIN_AP_PASS.ocr_digit(self.device.image)
        if self.climb_type == 'boss':
            cur, remain_times, total = self.O_REMAIN_BOSS.ocr_digit_counter(self.device.image)
        if self.climb_type == 'ap100':
            remain_times = self.O_REMAIN_AP100.ocr_digit(self.device.image)
        remain_times = self._update_climb_consumable_count(self.climb_type, remain_times)
        required = self._climb_resource_consumption()
        if self.climb_type == 'ap' and ap_pass_remain is not None:
            ap_pass_remain = self._update_climb_consumable_count('ap_pass', ap_pass_remain)
            ap_pass_required = self._climb_ap_pass_consumption()
            if ap_pass_remain < ap_pass_required:
                logger.info(
                    f'Climb ap pass is insufficient: '
                    f'remain={ap_pass_remain}, required={ap_pass_required}'
                )
                return False
        if remain_times < required:
            logger.info(
                f'Climb {self.climb_type} resource is insufficient: '
                f'remain={remain_times}, required={required}, mode={self.current_pass_mode}'
            )
            return False
        return True
