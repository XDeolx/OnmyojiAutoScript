# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
import time
from cached_property import cached_property
from datetime import timedelta, datetime

from module.base.timer import Timer
from module.atom.image_grid import ImageGrid
from module.logger import logger
from module.exception import TaskEnd, GamePageUnknownError, GameStuckError

from tasks.GameUi.game_ui import GameUi
from tasks.KekkaiUtilize.page import page_guild_realm, page_guild_realm_utilize, page_guild_realm_growth, \
    page_friend_utilize, page_gr_ap_box, page_gr_exp_jug
from tasks.Utils.config_enum import ShikigamiClass
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets
from tasks.KekkaiUtilize.config import UtilizeRule, SelectFriendList
from tasks.KekkaiUtilize.utils import CardClass, target_to_card_class
from tasks.Component.ReplaceShikigami.replace_shikigami import ReplaceShikigami
from tasks.GameUi.page import page_main, page_guild
from module.base.utils import point2str
import random

""" 结界蹭卡 """


class ScriptTask(GameUi, ReplaceShikigami, KekkaiUtilizeAssets):
    last_best_index = 99
    utilize_add_count = 0
    utilize_failed_count = 0
    utilize_entered_failed_count = 0
    utilize_terminal_failure = False
    utilize_found_eligible_card = False
    utilize_current_group_has_eligible_card = False
    utilize_current_group_scan_completed = False
    utilize_lazy_mode_active = False
    ap_max_num = 0
    jade_max_num = 0

    # 同类型、同星级结界卡的最高奖励。达到最高值后，本轮不再打开同档卡片。
    CARD_TIER_INFO = {
        CardClass.TAIKO4: ('太鼓', 4, 59),
        CardClass.TAIKO5: ('太鼓', 5, 67),
        CardClass.TAIKO6: ('太鼓', 6, 76),
        CardClass.FISH4: ('斗鱼', 4, 118),
        CardClass.FISH5: ('斗鱼', 5, 134),
        CardClass.FISH6: ('斗鱼', 6, 151),
    }
    STRATEGY_MAX_REWARDS = {
        '太鼓': 76,
        '斗鱼': 151,
    }
    GUILD_REWARD_WAIT_RANGE = (2.0, 4.0)
    REST_INTERVAL_FACTOR_RANGE = (0.6, 0.9)

    @classmethod
    def _sample_rest_interval(
        cls,
        configured_interval: timedelta,
        factor: float | None = None,
    ) -> tuple[timedelta, float]:
        if not configured_interval or configured_interval.total_seconds() <= 0:
            return timedelta(0), 0.0
        if factor is None:
            factor = random.uniform(*cls.REST_INTERVAL_FACTOR_RANGE)
        randomized_seconds = round(
            configured_interval.total_seconds() * factor
        )
        return timedelta(seconds=randomized_seconds), factor

    @classmethod
    def _next_utilize_run_time(
        cls,
        remaining_time: timedelta,
        min_run_interval: timedelta,
        now: datetime | None = None,
        interval_factor: float | None = None,
    ) -> datetime:
        now = now or datetime.now()
        rest_interval, _ = cls._sample_rest_interval(
            min_run_interval,
            factor=interval_factor,
        )
        return now + remaining_time + rest_interval

    def run(self):
        con = self.config.kekkai_utilize.utilize_config
        self.utilize_add_count = 0
        self.utilize_failed_count = 0
        self.utilize_entered_failed_count = 0
        self.utilize_terminal_failure = False
        self.utilize_found_eligible_card = False
        self.utilize_current_group_has_eligible_card = False
        self.utilize_current_group_scan_completed = False
        self.utilize_lazy_mode_active = False
        self.ap_max_num = 0
        self.jade_max_num = 0
        if con.utilize_enable and con.lazy_mode:
            lazy_roll = random.random()
            self.utilize_lazy_mode_active = (
                lazy_roll < con.lazy_mode_weight
            )
            logger.info(
                '怠惰模式随机判定: '
                f'roll={lazy_roll:.4f}, '
                f'weight={con.lazy_mode_weight:.4f}, '
                f'active={self.utilize_lazy_mode_active}'
            )
        # 进入寮结界
        self.goto_page(page_guild_realm)
        # 育成界面去蹭卡
        if con.utilize_enable:
            if not self.check_utilize_add():
                # 正常返回而非抛出 TaskEnd，使调度器把本轮记为失败；
                # 下次运行时间已由失败处理设置为 10 分钟后。
                return

        # 查看育成满级
        self.check_max_lv(con.shikigami_class, con.auto_fill)
        # 检查是否有蹭卡收获 是否收取
        if con.utilize_harvest:
            self.check_utilize_harvest()
        # 收体力盒子或者是经验盒子
        self.check_box_ap_or_exp(con.box_ap_enable, con.box_exp_enable, con.box_exp_waste)

        # 返回庭院本来就会经过寮主页，只顺手处理当前可见的寮奖励。
        self.receive_guild_assets(
            guild_lottery_enable=con.guild_lottery_enable,
            random_wait_enable=con.guild_reward_random_wait,
        )
        if not con.utilize_enable:
            self.set_next_run(task='KekkaiUtilize', finish=True, success=True)
        self.goto_page(page_main)
        raise TaskEnd

    def receive_guild_assets(
        self,
        guild_lottery_enable: bool = False,
        random_wait_enable: bool = False,
    ) -> bool:
        """退出结界时经过寮主页，单次顺手处理可见奖励。"""
        self.goto_page(page_guild)
        collected = self.collect_visible_guild_assets(
            guild_lottery_enable=guild_lottery_enable,
            random_wait_enable=random_wait_enable,
        )
        logger.info(
            '寮主页收尾完成: '
            f'handled={collected}, lottery_enabled={guild_lottery_enable}'
        )
        return collected

    def _guild_reward_random_wait(
        self,
        enabled: bool,
        stage: str,
    ) -> float:
        if not enabled:
            return 0.0
        delay = random.uniform(*self.GUILD_REWARD_WAIT_RANGE)
        logger.info(f'寮奖励随机等待: stage={stage}, delay={delay:.2f}s')
        time.sleep(delay)
        return delay

    def _settle_guild_reward(self, allow_assets_confirm: bool = False) -> None:
        """仅在已经点击奖励后处理确认框和奖励弹窗。"""
        timeout = Timer(4).start()
        while not timeout.reached():
            self.screenshot()
            if allow_assets_confirm and self.appear_then_click(
                self.I_GUILD_ASSETS_RECEIVE,
                interval=0.5,
            ):
                allow_assets_confirm = False
                continue
            if self.ui_reward_appear_click():
                return

    def collect_visible_guild_assets(
        self,
        guild_lottery_enable: bool = False,
        random_wait_enable: bool = False,
    ) -> bool:
        """固定收取当前可见奖励，并按配置选择是否进行寮抽奖。"""
        reward_collected = self.collect_visible_guild_rewards(
            random_wait_enable=random_wait_enable,
        )
        lottery_drew = False
        if guild_lottery_enable:
            lottery_drew = self.collect_visible_guild_lottery(
                random_wait_enable=random_wait_enable,
            )
        logger.info(
            '寮抽奖: '
            f'enabled={guild_lottery_enable}, drew={lottery_drew}'
        )
        return reward_collected or lottery_drew

    def collect_visible_guild_rewards(
        self,
        random_wait_enable: bool = False,
    ) -> bool:
        """顺手收取寮主页当前可见的资金和体力，不受抽奖开关影响。"""
        collected = False
        empty_scans = 0
        max_scans = 4
        self.screenshot()
        if self.appear_then_click(self.I_GUILD_EXPAND):
            # 展开动画期间奖励图标尚未稳定，立即识别会漏掉仅有的寮资金。
            time.sleep(0.8)
            self.screenshot()

        for scan_index in range(1, max_scans + 1):
            self.screenshot()
            handled_this_scan = False

            if self.appear_then_click(
                self.I_GUILD_ASSETS,
                interval=0.5,
                threshold=0.6,
            ):
                collected = True
                handled_this_scan = True
                self._settle_guild_reward(allow_assets_confirm=True)
                self._guild_reward_random_wait(random_wait_enable, '寮资金完成')
                self.screenshot()

            if self.appear_then_click(self.I_GUILD_AP, interval=0.5):
                collected = True
                handled_this_scan = True
                self._settle_guild_reward()
                self.device.click_record_clear()
                self._guild_reward_random_wait(random_wait_enable, '寮体力完成')
                self.screenshot()

            if handled_this_scan:
                empty_scans = 0
                continue

            empty_scans += 1
            if empty_scans >= 2:
                break
            logger.info(
                f'寮奖励暂未识别，短暂等待后复查: scan={scan_index}/{max_scans}'
            )
            time.sleep(0.5)

        logger.info(
            '顺手收取寮资金/体力: '
            f'collected={collected}, scans={scan_index}'
        )
        return collected

    def collect_visible_guild_lottery(
        self,
        random_wait_enable: bool = False,
    ) -> bool:
        """仅在抽奖开关开启时处理当前可见的寮抽奖。"""
        self.screenshot()
        if not self.appear(self.I_GUILD_LOTTERY, interval=0.5):
            return False
        self._guild_reward_random_wait(random_wait_enable, '寮抽奖前')
        drew = self.guild_lottery(random_wait_enable=random_wait_enable)
        if drew:
            self._guild_reward_random_wait(random_wait_enable, '寮抽奖完成')
        return drew

    def guild_lottery(self, random_wait_enable: bool = False) -> bool:
        """执行当前可见的寮抽奖，并在完成后返回寮主页。"""
        entered = self.ui_click_until_appear_or_timeout(
            self.I_GUILD_LOTTERY,
            self.I_CHECK_GUILD_LOTTERY,
            interval=1.5,
            timeout=7,
        )
        if not entered:
            logger.warning('进入寮抽奖页面失败')
            return False

        drew = False
        idle_timer = Timer(4).start()
        hard_timeout = Timer(30).start()
        while not idle_timer.reached() and not hard_timeout.reached():
            self.screenshot()
            if self.ui_reward_appear_click():
                drew = True
                idle_timer.reset()
                continue
            if self.appear(self.I_GUILD_LOTTERY_SPECIAL_REWARD, interval=1):
                self.click(self.C_UI_REWARD)
                drew = True
                idle_timer.reset()
                continue
            if self.appear(self.I_KU_CHECK_CAN_LOTTERY, interval=1):
                self._guild_reward_random_wait(
                    random_wait_enable,
                    '寮抽奖操作前',
                )
                self.swipe(self.S_GUILD_LOTTERY)
                drew = True
                idle_timer.reset()
                continue

        self.appear_then_click(self.I_UI_BACK_YELLOW)
        self.device.click_record_clear()
        logger.info(f'寮抽奖结束: drew={drew}')
        return drew

    def check_utilize_add(self):
        con = self.config.kekkai_utilize.utilize_config
        while 1:
            self.utilize_add_count += 1
            if self.utilize_add_count >= 5:
                if not self.utilize_found_eligible_card:
                    target_name = {
                        UtilizeRule.TAIKO: '太鼓',
                        UtilizeRule.FISH: '斗鱼',
                        UtilizeRule.DEFAULT: '太鼓或斗鱼',
                    }.get(con.utilize_rule, '目标结界卡')
                    message = f'未检测到四星及以上{target_name}, 5分钟后再次执行蹭卡'
                    logger.warning(message)
                    self.push_notify(content=message)
                else:
                    logger.warning('已检测到四星及以上结界卡，但未能完成选择，5分钟后重试')
                self.set_next_run(task='KekkaiUtilize', target=datetime.now() + timedelta(minutes=5))
                return True

            # 无论收不收到菜，都会进入看看至少看一眼时间还剩多少
            time.sleep(0.5)
            # 进入育成界面
            self.goto_page(page_guild_realm_growth)
            self.screenshot()
            if not self.appear(self.I_UTILIZE_ADD):
                remaining_time = self.O_UTILIZE_RES_TIME.ocr(self.device.image)
                if not isinstance(remaining_time, timedelta):
                    logger.warning('Ocr remaining time error')
                logger.info(f'Utilize remaining time: {remaining_time}')
                # 已经蹭上卡了，设置下次蹭卡时间  # 减少30秒
                # remaining_time = remaining_time - timedelta(seconds=30)
                rest_interval, interval_factor = (
                    self._sample_rest_interval(con.min_run_interval)
                )
                next_time = datetime.now() + remaining_time + rest_interval
                logger.info(
                    'Utilize randomized rest interval: '
                    f'configured={con.min_run_interval}, '
                    f'factor={interval_factor:.3f}, '
                    f'effective={rest_interval}'
                )
                self.set_next_run(task='KekkaiUtilize', target=next_time)
                return True
            if not self.goto_page(page_guild_realm_utilize):
                logger.info('Utilize failed, exit')
            # 开始执行寄养
            self.run_utilize(con.select_friend_list, con.shikigami_class, con.shikigami_order)
            # 不论本轮成功、可重试失败还是终止失败，都先回到
            # 结界育成页，避免下一轮从好友结界内部开始。
            self.goto_page(page_guild_realm_growth)
            if self.utilize_terminal_failure:
                return False

    def check_max_lv(self, shikigami_class: ShikigamiClass = ShikigamiClass.N, auto_fill: bool = False):
        """
        在结界界面，进入式神育成，检查是否有满级的，如果有就换下一个
        退出的时候还是结界界面
        :return:
        """
        self.goto_page(page_guild_realm_growth)
        if auto_fill:
            self.ui_click(self.I_AUTO_FILL, self.I_REMOVE_ALL, interval=1.5)
            self.goto_page(page_guild_realm)
            return
        if self.appear(self.I_RS_LEVEL_MAX):
            # 存在满级的式神
            logger.info('Exist max level shikigami and replace it')
            self.unset_shikigami_max_lv()
            self.switch_shikigami_class(shikigami_class)
            self.set_shikigami(shikigami_order=7, stop_image=self.I_RS_NO_ADD)
        else:
            logger.info('No max level shikigami')
        if self.detect_no_shikigami():
            logger.warning('There are no any shikigami grow room')
            self.switch_shikigami_class(shikigami_class)
            self.set_shikigami(shikigami_order=7, stop_image=self.I_RS_NO_ADD)

        # 回到结界界面
        self.goto_page(page_guild_realm)

    def check_box_ap_or_exp(self, ap_enable: bool = True, exp_enable: bool = True, exp_waste: bool = True) -> bool:
        """
        顺路检查盒子
        :param exp_waste:
        :param ap_enable:
        :param exp_enable:
        :return:
        """

        def _harvest_ap_box():
            """收取体力"""
            timer_ap = Timer(6)
            timer_ap.start()
            while True:
                if timer_ap.reached():
                    logger.warning('Extract ap box done')
                    break
                self.screenshot()
                if self.appear(self.I_UI_REWARD):
                    self.ui_click_until_smt_disappear(self.C_UI_REWARD, self.I_UI_REWARD, interval=1)
                    logger.info('Reward box')
                    break
                if self.appear_then_click(self.I_AP_EXTRACT, interval=2):
                    continue
            return True

        def _harvest_exp_jug():
            time_exp = Timer(12)
            time_exp.start()
            max_tries = random.randint(2, 3)
            while True:
                if time_exp.reached():
                    logger.warning('Extract exp jug done')
                    break
                if max_tries <= 0:
                    logger.info('Exp maybe already full, ocr failed, exit')
                    break
                self.screenshot()
                # 如果出现结界皮肤， 表示收取好了
                current_page = self.detect_page_in(
                    page_guild_realm,
                    page_gr_exp_jug,
                    include_global=False,
                )
                if current_page == page_guild_realm:
                    break
                # 如果出现收取确认，表明进入到了有满级的
                if self.appear(self.I_UI_CONFIRM) and self.appear(self.I_UI_CANCEL):
                    target_button = self.I_UI_CONFIRM if exp_waste else self.I_UI_CANCEL
                    self.ui_click_until_disappear(target_button)
                    break
                if self.appear(self.I_EXP_EXTRACT, interval=1):
                    # 如果达到今日领取的最大，就不领取了
                    cur, res, total = self.O_BOX_EXP.ocr(self.device.image)
                    if total <= 0:
                        logger.warning('Exp box OCR no data, retry')
                        continue
                    if cur == total:
                        logger.info('Exp box reach max do not collect')
                        break
                    self.click(self.I_EXP_EXTRACT)
                    max_tries -= 1
            return True

        self.screenshot()
        if ap_enable and self.appear(self.I_BOX_AP):
            self.goto_page(page_gr_ap_box)
            _harvest_ap_box()
            self.goto_page(page_guild_realm)
        if exp_enable and (self.appear(self.I_BOX_EXP) or self.appear(self.I_BOX_EXP_MAX)):
            self.goto_page(page_gr_exp_jug)
            _harvest_exp_jug()
            self.goto_page(page_guild_realm)
        return True

    def check_utilize_harvest(self) -> bool:
        """
        在寮结界界面检查是否有寄养收获
        :return: 如果没有返回False, 如果有就收菜返回True
        """
        self.screenshot()
        appear = self.appear(self.I_UTILIZE_EXP)
        if not appear:
            logger.info('No utilize harvest')
            return False

        # 收获
        self.ui_get_reward(self.I_UTILIZE_EXP)
        return True

    def switch_friend_list(self, friend: SelectFriendList = SelectFriendList.SAME_SERVER) -> bool:
        """
        切换不同的服务区
        :param friend:
        :return:
        """
        logger.info('Switch friend list to %s', friend)
        if friend == SelectFriendList.SAME_SERVER:
            check_image = self.I_UTILIZE_FRIEND_GROUP
        else:
            check_image = self.I_UTILIZE_ZONES_GROUP

        timer_click = Timer(1)
        timer_click.start()
        while 1:
            self.screenshot()
            if self.appear(check_image):
                break
            if timer_click.reached():
                timer_click.reset()
                x, y = check_image.coord()
                self.device.click(x=x, y=y, control_name=check_image.name)
        if friend == SelectFriendList.DIFFERENT_SERVER:
            time.sleep(1)
        time.sleep(0.5)

    @cached_property
    def order_targets(self) -> ImageGrid:
        rule = self.config.kekkai_utilize.utilize_config.utilize_rule
        if rule == UtilizeRule.DEFAULT:
            return ImageGrid([
                self.I_U_FISH_6, self.I_U_TAIKO_6,
                self.I_U_FISH_5, self.I_U_TAIKO_5,
                self.I_U_FISH_4, self.I_U_TAIKO_4,
            ])
        elif rule == UtilizeRule.FISH:
            return ImageGrid([self.I_U_FISH_6, self.I_U_FISH_5, self.I_U_FISH_4])
        elif rule == UtilizeRule.TAIKO:
            return ImageGrid([self.I_U_TAIKO_6, self.I_U_TAIKO_5, self.I_U_TAIKO_4])
        else:
            logger.error('Unknown utilize rule')
            raise ValueError('Unknown utilize rule')

    @cached_property
    def lazy_scan_targets(self) -> ImageGrid:
        """怠惰模式扫描四星以上卡；四星仅用于排除星级冲突。"""
        return ImageGrid([
            self.I_U_FISH_6, self.I_U_TAIKO_6,
            self.I_U_FISH_5, self.I_U_TAIKO_5,
            self.I_U_FISH_4, self.I_U_TAIKO_4,
        ])

    @staticmethod
    def _same_card_match(area_a: tuple, area_b: tuple) -> bool:
        """判断两个模板结果是否来自好友列表中的同一张结界卡。"""
        ax, ay, aw, ah = area_a
        bx, by, bw, bh = area_b
        center_ax, center_ay = ax + aw / 2, ay + ah / 2
        center_bx, center_by = bx + bw / 2, by + bh / 2
        return (
            abs(center_ax - center_bx) <= 35
            and abs(center_ay - center_by) <= 25
        )

    def _deduplicate_card_matches(self, cards: list | None) -> list:
        """合并同一位置的多星级模板结果，保留最高置信度结果。"""
        if not cards:
            return []

        groups: list[list] = []
        for match in sorted(cards, key=lambda item: item[2][1]):
            for group in groups:
                if self._same_card_match(match[2], group[0][2]):
                    group.append(match)
                    break
            else:
                groups.append([match])

        result = []
        for group in groups:
            selected = max(group, key=lambda item: item[1])
            detected_classes = tuple({
                target_to_card_class(target)
                for target, _, _ in group
            })
            if len(detected_classes) > 1:
                detail = ', '.join(
                    f'{target_to_card_class(target).value}@{score:.3f}'
                    for target, score, _ in sorted(
                        group,
                        key=lambda item: item[1],
                        reverse=True,
                    )
                )
                logger.warning(
                    f'同一结界卡命中多个模板，保留最高置信度结果: {detail}'
                )
            result.append((*selected, detected_classes))
        return result

    @cached_property
    def order_cards(self) -> list[CardClass]:
        rule = self.config.kekkai_utilize.utilize_config.utilize_rule
        result = []
        if rule == UtilizeRule.DEFAULT:
            result = [CardClass.FISH6, CardClass.TAIKO6, CardClass.FISH5, CardClass.TAIKO5,
                      CardClass.TAIKO4, CardClass.FISH4, CardClass.TAIKO3, CardClass.FISH3]
        elif rule == UtilizeRule.FISH:
            result = [CardClass.FISH6, CardClass.FISH5,
                      CardClass.TAIKO6, CardClass.TAIKO5, CardClass.FISH4, CardClass.TAIKO4, CardClass.FISH3,
                      CardClass.TAIKO3]
        elif rule == UtilizeRule.TAIKO:
            result = [CardClass.TAIKO6, CardClass.TAIKO5,
                      CardClass.FISH6, CardClass.FISH5, CardClass.TAIKO4, CardClass.FISH4, CardClass.TAIKO3,
                      CardClass.FISH3]
        else:
            logger.error('Unknown utilize rule')
            raise ValueError('Unknown utilize rule')
        return result

    def _reset_utilize_friend_list(self, friend: SelectFriendList) -> None:
        """刷新好友列表并回到所选分组的顶部。"""
        if friend == SelectFriendList.SAME_SERVER:
            self.switch_friend_list(SelectFriendList.SAME_SERVER)
            self.swipe(self.S_U_END, interval=3)
            self.switch_friend_list(SelectFriendList.DIFFERENT_SERVER)
            self.switch_friend_list(SelectFriendList.SAME_SERVER)
        else:  # 跨区必须切换两次，否则结界卡不会刷新到顶部
            self.switch_friend_list(SelectFriendList.DIFFERENT_SERVER)
            self.swipe(self.S_U_END, interval=3)
            self.switch_friend_list(SelectFriendList.SAME_SERVER)
            self.switch_friend_list(SelectFriendList.DIFFERENT_SERVER)

    def _record_utilize_failure(
        self,
        reason: str,
        *,
        entered_realm: bool = False,
    ) -> bool:
        """记录蹭卡失败，区分入场前失败与进入目标结界后失败。"""
        if entered_realm:
            self.utilize_entered_failed_count += 1
            logger.warning(
                '进入目标结界后的蹭卡流程失败: '
                f'{reason} ({self.utilize_entered_failed_count}/2)'
            )
            if self.utilize_entered_failed_count < 2:
                return False

            message = '目标结界已被占用'
            logger.error(message)
            logger.info('蹭卡任务推迟10分钟')
            self.push_notify(content=message)
            self.set_next_run(
                task='KekkaiUtilize',
                finish=True,
                server=False,
                target=datetime.now() + timedelta(minutes=10),
            )
            self.utilize_terminal_failure = True
            return False

        self.utilize_failed_count += 1
        logger.warning(
            f'蹭卡失败: {reason} ({self.utilize_failed_count}/3)'
        )
        if self.utilize_failed_count < 3:
            return False

        message = '连续3次蹭卡失败，目标结界视为已经被蹭，任务失败，10分钟后重试'
        logger.error(message)
        self.push_notify(content=message)
        self.set_next_run(
            task='KekkaiUtilize',
            finish=True,
            server=False,
            target=datetime.now() + timedelta(minutes=10),
        )
        self.utilize_terminal_failure = True
        return False

    def _finish_low_value_utilize(self) -> bool:
        """已扫描范围没有四星以上策略卡时，失败并延迟任务。"""
        rule = self.config.kekkai_utilize.utilize_config.utilize_rule
        scan_scope = (
            '当前优先分组'
            if self.utilize_lazy_mode_active
            else '同区和跨区'
        )
        target_name = {
            UtilizeRule.TAIKO: '太鼓',
            UtilizeRule.FISH: '斗鱼',
            UtilizeRule.DEFAULT: '太鼓或斗鱼',
        }.get(rule, '目标结界卡')
        message = (
            f'{scan_scope}全是当前策略低价值卡，未检测到四星及以上{target_name}，'
            '任务失败，20分钟后重试'
        )
        logger.error(message)
        self.push_notify(content=message)
        self.set_next_run(
            task='KekkaiUtilize',
            finish=True,
            server=False,
            target=datetime.now() + timedelta(minutes=20),
        )
        self.utilize_terminal_failure = True
        return False

    def run_utilize(self, friend: SelectFriendList = SelectFriendList.SAME_SERVER,
                    shikigami_class: ShikigamiClass = ShikigamiClass.N,
                    shikigami_order: int = 7):
        """
        执行寄养
        :param shikigami_order:
        :param shikigami_class:
        :param friend:
        :param rule:
        :return:
        """
        logger.hr('Start utilize')
        fallback_friend = (
            SelectFriendList.DIFFERENT_SERVER
            if friend == SelectFriendList.SAME_SERVER
            else SelectFriendList.SAME_SERVER
        )
        selected_friend = None

        # 普通模式会在优先分组无可用卡时扫描备选分组；
        # 怠惰模式只处理当前配置的优先分组。
        friend_groups = (
            (friend,)
            if self.utilize_lazy_mode_active
            else (friend, fallback_friend)
        )
        for index, target_friend in enumerate(friend_groups, start=1):
            priority_text = '优先' if index == 1 else '备选'
            logger.hr(f'{priority_text}好友分组: {target_friend.value}', 2)
            self._reset_utilize_friend_list(target_friend)
            if self.utilize_lazy_mode_active:
                select_result = self._select_lazy_resource_card(target_friend)
            else:
                select_result = self._select_optimal_resource_card(target_friend)
            if select_result is True:
                selected_friend = target_friend
                logger.info(
                    f'已在{priority_text}分组[{target_friend.value}]选中蹭卡目标，'
                    '不再检查其他分组'
                )
                break
            if select_result is False:
                logger.warning(
                    f'分组[{target_friend.value}]存在可用卡，但最优卡定位失败，'
                    '本轮不切换分组'
                )
                return False
            logger.info(
                f'分组[{target_friend.value}]没有当前策略可用的四星以上结界卡'
            )

        if selected_friend is None:
            return self._finish_low_value_utilize()

        # 找到卡,重置次数
        self.utilize_add_count = 0
        logger.info('开始执行进入结界蹭卡流程')
        self.screenshot()
        # 进入结界
        if not self.appear(self.I_U_ENTER_REALM):
            logger.warning('Cannot find enter realm button')
            # 可能是滑动的时候出错
            logger.warning('The best reason is that the swipe is wrong')
            return self._record_utilize_failure('未识别到进入结界按钮')
        try:
            self.goto_page(page_friend_utilize)
        except (GamePageUnknownError, GameStuckError) as error:
            logger.warning('Appear friend realm failed')
            return self._record_utilize_failure(
                f'进入好友结界失败: {type(error).__name__}'
            )
        # 判断好友的有两个位置还是一个坑位
        stop_image = None
        self.screenshot()
        if self.appear(self.I_U_ADD_1):  # 右侧第一个有（无论左侧有没有）
            logger.info('Right side has one')
            stop_image = self.I_U_ADD_1
        elif self.appear(self.I_U_ADD_2) and not self.appear(self.I_U_ADD_1):  # 右侧第二个有 但是最左边的没有，这表示只留有一个坑位
            logger.info('Right side has two')
            stop_image = self.I_U_ADD_2
        if not stop_image:
            # 没有坑位可能是其他人的手速太快了抢占了
            self.save_image(content='没有坑位了', wait_time=0, push_flag=False, image_type='png')
            logger.warning('没有坑位可能是其他人的手速太快了抢占了')
            return self._record_utilize_failure(
                '目标结界已经没有可用坑位',
                entered_realm=True,
            )
        try:
            # 切换式神的类型
            self.switch_shikigami_class(shikigami_class)
            # 上式神
            self.set_shikigami(shikigami_order, stop_image)
        except (GamePageUnknownError, GameStuckError) as error:
            return self._record_utilize_failure(
                f'式神寄养失败: {type(error).__name__}',
                entered_realm=True,
            )
        self.utilize_failed_count = 0
        self.utilize_entered_failed_count = 0
        return True

    def _resource_type_matches_rule(self, card_type: str) -> bool:
        """以详情页 OCR 得到的资源类型判断是否符合当前策略。"""
        rule = self.config.kekkai_utilize.utilize_config.utilize_rule
        if rule == UtilizeRule.TAIKO:
            return card_type == '太鼓'
        if rule == UtilizeRule.FISH:
            return card_type == '斗鱼'
        if rule == UtilizeRule.DEFAULT:
            return card_type in ('太鼓', '斗鱼')
        logger.error('Unknown utilize rule')
        raise ValueError('Unknown utilize rule')

    @staticmethod
    def _resource_reward_star(card_type: str, card_value: int) -> int | None:
        """按实际奖励范围推断星级，避免把模板误判当作真实星级。"""
        ranges = {
            '太鼓': ((4, 50, 59), (5, 59, 67), (6, 67, 76)),
            '斗鱼': ((4, 101, 118), (5, 118, 134), (6, 134, 151)),
        }
        for star, minimum, maximum in ranges.get(card_type, ()):
            if minimum <= card_value <= maximum:
                return star
        return None

    def _select_lazy_resource_card(
        self,
        friend: SelectFriendList,
    ) -> bool | None:
        """怠惰模式：先找五星；确认没有后复位并选当前分组首张四星。"""
        max_swipes = 20
        consecutive_miss_limit = 3
        timeout = Timer(120).start()
        miss_count = 0
        four_star_candidate: tuple[str, int] | None = None
        self.utilize_current_group_has_eligible_card = False
        self.utilize_current_group_scan_completed = False

        logger.hr('怠惰模式快速选择结界卡', 2)
        for swipe_count in range(max_swipes + 1):
            if timeout.reached():
                logger.warning('怠惰模式扫描超时，不能确认当前分组无可用卡')
                return False

            self.screenshot()
            raw_cards = self.lazy_scan_targets.find_everyone(
                self.device.image,
                frame_id=self.device.image_frame_id,
            )
            cards = self._deduplicate_card_matches(raw_cards)
            if cards:
                for _, _, area, _ in cards:
                    self.C_SELECT_CARD.roi_front = area
                    self.click(self.C_SELECT_CARD)
                    time.sleep(2)
                    card_type, card_value = self.check_card_num()
                    star = self._resource_reward_star(card_type, card_value)
                    logger.info(
                        '怠惰模式 OCR 候选: '
                        f'{card_type}@{card_value}, star={star}, area={area}'
                    )
                    if (
                        star is None
                        or not self._resource_type_matches_rule(card_type)
                    ):
                        continue

                    self.utilize_found_eligible_card = True
                    self.utilize_current_group_has_eligible_card = True
                    if star >= 5:
                        logger.info(
                            f'怠惰模式已选择首个 OCR 确认的'
                            f'{star}星{card_type}@{card_value}'
                        )
                        return True
                    if four_star_candidate is None:
                        four_star_candidate = (card_type, card_value)

            # 当前屏即使只有四星卡或另一策略资源卡，也说明仍位于
            # 有效卡区域，需要继续向下寻找，不能计入连续空屏。
            miss_count = 0 if cards else miss_count + 1
            logger.info(
                f'怠惰模式第{swipe_count}屏未发现当前策略五星以上结界卡'
            )
            if self.appear(self.I_U_EMPTY_CARD):
                logger.info('怠惰模式已到达好友列表空卡区域')
                self.utilize_current_group_scan_completed = True
                break
            if miss_count > consecutive_miss_limit:
                logger.info(
                    f'怠惰模式连续{miss_count}屏没有四星以上资源卡候选，'
                    '结束当前分组扫描'
                )
                self.utilize_current_group_scan_completed = True
                break
            self.perform_swipe_action()
        else:
            self.utilize_current_group_scan_completed = True
            logger.info(
                f'怠惰模式已按最大滑动次数{max_swipes}完成当前分组扫描'
            )

        if four_star_candidate is None:
            logger.info('当前优先分组没有符合策略的五星或四星结界卡')
            return None

        logger.info(
            '当前优先分组已确认没有五星以上目标，'
            '复位列表并回退选择四星卡'
        )
        self._reset_utilize_friend_list(friend)
        if self._locate_recorded_resource_card(*four_star_candidate):
            return True
        logger.warning('已发现四星目标，但复位后重新定位失败')
        return False

    def _select_optimal_resource_card(
        self,
        friend: SelectFriendList,
    ) -> bool | None:
        """浏览当前分组，计算最高收益并确保最终重新选中该卡。"""
        self.ap_max_num, self.jade_max_num = 0, 0
        self.utilize_current_group_has_eligible_card = False
        self.utilize_current_group_scan_completed = False
        try:
            logger.hr('浏览列表并选择最优结界卡', 2)
            reached_strategy_maximum = self._current_select_best()
            if reached_strategy_maximum:
                logger.info('🏁 已命中当前策略最高收益，停止下划并直接进入结界')
                return True
            logger.info(
                f'📝 列表浏览完成 | '
                f'斗鱼:{self.ap_max_num} 太鼓:{self.jade_max_num}'
            )

            rule = self.config.kekkai_utilize.utilize_config.utilize_rule
            if rule == UtilizeRule.TAIKO and self.jade_max_num > 0:
                card_type, card_value = '太鼓', self.jade_max_num
            elif rule == UtilizeRule.FISH and self.ap_max_num > 0:
                card_type, card_value = '斗鱼', self.ap_max_num
            elif rule == UtilizeRule.DEFAULT and (
                self.ap_max_num > 0 or self.jade_max_num > 0
            ):
                ap_as_jade = self.ap_max_num / 1.8
                logger.info(
                    f'⚖️ 默认换算 | 斗鱼:{self.ap_max_num}体力 ÷ 1.8 '
                    f'= {ap_as_jade:.2f} | 太鼓:{self.jade_max_num}勾玉'
                )
                if ap_as_jade >= self.jade_max_num:
                    card_type, card_value = '斗鱼', self.ap_max_num
                else:
                    card_type, card_value = '太鼓', self.jade_max_num
            else:
                if self.utilize_current_group_has_eligible_card:
                    logger.warning('🔄 检测到四星以上目标，但奖励数值识别失败')
                    return False
                if not self.utilize_current_group_scan_completed:
                    logger.warning('当前好友分组未能完整扫描，不能判定为全是低价值卡')
                    return False
                logger.info('当前分组全是当前策略低价值结界卡')
                return None

            logger.info(f'🎯 最优决策: {card_type}@{card_value}')
            self._reset_utilize_friend_list(friend)
            if self._locate_recorded_resource_card(card_type, card_value):
                logger.info(f'✅ 已重新选中最优结界卡: {card_type}@{card_value}')
                return True
            logger.warning(f'❌ 无法重新定位最优结界卡: {card_type}@{card_value}')
            return False
        finally:
            self.ap_max_num, self.jade_max_num = 0, 0

    def _locate_recorded_resource_card(
        self,
        best_card_type: str,
        best_card_value: int,
    ) -> bool:
        """从列表顶部重新找到并保留浏览阶段记录的最优卡。"""
        max_swipes = 20
        consecutive_miss_limit = 3
        timeout = Timer(120).start()
        miss_count = 0

        logger.info(
            f'开始重新定位最优结界卡: {best_card_type}@{best_card_value}'
        )
        for swipe_count in range(max_swipes + 1):
            if timeout.reached():
                logger.warning('重新定位最优结界卡超时')
                return False

            self.screenshot()
            raw_cards = self.order_targets.find_everyone(
                self.device.image,
                frame_id=self.device.image_frame_id,
            )
            cards = self._deduplicate_card_matches(raw_cards)
            if not cards:
                miss_count += 1
                if (
                    miss_count > consecutive_miss_limit
                    or self.appear(self.I_U_EMPTY_CARD)
                ):
                    return False
                self.perform_swipe_action()
                continue

            miss_count = 0
            for _, _, area, _ in cards:
                self.C_SELECT_CARD.roi_front = area
                self.click(self.C_SELECT_CARD)
                time.sleep(2)
                card_type, card_value = self.check_card_num()
                logger.info(
                    '重新定位候选: '
                    f'{card_type}@{card_value}, '
                    f'target={best_card_type}@{best_card_value}'
                )
                if (
                    card_type == best_card_type
                    and card_value == best_card_value
                ):
                    return True

            if self.appear(self.I_U_EMPTY_CARD):
                return False
            self.perform_swipe_action()

        logger.warning(f'重新定位达到最大滑动次数{max_swipes}')
        return False

    def _is_strategy_maximum_reward(
        self,
        card_type: str,
        card_value: int,
    ) -> bool:
        """判断当前卡是否已经达到所选策略的全局最高收益。"""
        maximum = self.STRATEGY_MAX_REWARDS.get(card_type)
        if maximum is None or card_value < maximum:
            return False

        rule = self.config.kekkai_utilize.utilize_config.utilize_rule
        if rule == UtilizeRule.TAIKO:
            return card_type == '太鼓'
        if rule == UtilizeRule.FISH:
            return card_type == '斗鱼'
        if rule == UtilizeRule.DEFAULT:
            return card_type in ('太鼓', '斗鱼')
        logger.error('Unknown utilize rule')
        raise ValueError('Unknown utilize rule')

    def _current_select_best(self) -> bool:
        """浏览好友列表、记录奖励，并保留当前选中的最佳结界卡。"""
        # ============== 配置常量 ==============#
        RESOURCE_CONFIG = {
            '斗鱼': {'record_attr': 'ap_max_num'},
            '太鼓': {'record_attr': 'jade_max_num'}
        }
        MAX_SWIPES = 20  # 最大滑动次数
        CONSEC_MISS = 3  # 允许连续无卡次数
        TIMEOUT = 120  # 操作超时(秒)

        # ============== 初始化阶段 ==============#
        logger.info('启动结界卡浏览选择')
        timer = Timer(TIMEOUT).start()
        miss_count = 0  # 连续无卡计数器
        # ============== 主滑动循环 ==============#
        for swipe_count in range(MAX_SWIPES + 1):
            # 超时检测
            if timer.reached():
                logger.warning('⏰ 操作超时，终止流程')
                return False

            # ------ 步骤1: 截图识别结界卡 ------#
            self.screenshot()
            raw_cards = self.order_targets.find_everyone(
                self.device.image,
                frame_id=self.device.image_frame_id,
            )
            cards = self._deduplicate_card_matches(raw_cards)

            # 处理无卡情况
            if not cards:
                miss_count += 1
                logger.info(f'第{swipe_count}次滑动 | 未检测到结界卡' if swipe_count > 0 else '初始界面 | 未检测到结界卡')
                # 游戏会优先排列有结界卡的好友，连续未命中或出现空卡时
                # 即可视为当前分组已扫描完成。
                if miss_count > CONSEC_MISS or self.appear(self.I_U_EMPTY_CARD):
                    logger.warning(
                        f'⚠️ 连续{miss_count}次未检测到目标结界卡，终止当前分组扫描'
                    )
                    self.utilize_current_group_scan_completed = True
                    return False
                # 执行滑动操作
                self.perform_swipe_action()
                continue

            miss_count = 0  # 重置无卡计数器

            # ------ 步骤2: 处理识别到的结界卡 ------
            cards_list = [target for target, _, _, _ in cards]
            logger.info((f'第{swipe_count}次滑动' if swipe_count > 0 else '初始界面') + f' | 检测到结界卡：{cards_list}')

            # 遍历所有结界卡（已按位置排序）
            for _, _, area, _ in cards:
                # 设置点击区域并获取结界卡详情
                self.C_SELECT_CARD.roi_front = area
                self.click(self.C_SELECT_CARD)
                time.sleep(2)  # 等待结界卡详情加载

                # 解析结界卡类型和数值
                card_type, card_value = self.check_card_num()

                # 跳过无效结界卡（类型未知或数值异常）
                star = self._resource_reward_star(card_type, card_value)
                if (
                    star is None
                    or card_type not in RESOURCE_CONFIG
                    or not self._resource_type_matches_rule(card_type)
                ):
                    logger.info(f'⏭️ 跳过无效卡: {card_type}@{card_value}')
                    continue

                self.utilize_found_eligible_card = True
                self.utilize_current_group_has_eligible_card = True
                logger.info(
                    f'✅ OCR 确认{star}星{card_type}奖励: {card_value}'
                )

                # ====== 模式分支处理 ======#
                record_attr = RESOURCE_CONFIG[card_type]['record_attr']
                current_record = getattr(self, record_attr, 0)
                logger.info(f'🔍 识别卡片: {card_type} | 当前值: {card_value}, 最优值: {current_record}')

                # 更新最佳记录
                if card_value > current_record:
                    logger.info(f'📈 更新记录: {card_type} | {current_record} → {card_value}')
                    setattr(self, record_attr, card_value)

                if self._is_strategy_maximum_reward(card_type, card_value):
                    logger.info(
                        f'✅ 当前策略最高收益已确认: '
                        f'{card_type}@{card_value}，保留当前选项并停止浏览'
                    )
                    return True

            if self.appear(self.I_U_EMPTY_CARD):
                logger.info('Empty card already appeared, exit explore')
                self.utilize_current_group_scan_completed = True
                return False
            # ------ 步骤3: 滑动到下一屏 ------#
            self.perform_swipe_action()

        # ============== 终止处理 ==============#
        self.utilize_current_group_scan_completed = True
        logger.info(
            f'已按最大滑动次数{MAX_SWIPES}完成当前分组的有界全量扫描'
        )
        return False

    def perform_swipe_action(self):
        """统一滑动操作"""
        duration = 2
        safe_pos_x = random.randint(340, 600)
        safe_pos_y = random.randint(500, 565)
        p1 = (safe_pos_x, safe_pos_y)
        p2 = (safe_pos_x, safe_pos_y - 416)
        logger.info('Swipe %s -> %s, %sS ' % (point2str(*p1), point2str(*p2), duration))
        self.device.swipe_adb(p1, p2, duration=duration)

        # self.swipe(self.S_U_UP, duration=1, wait_up_time=1)
        self.device.click_record_clear()
        time.sleep(2)

    def check_card_num(self) -> tuple[str, int]:
        """优化版数值提取方法，返回结界卡类型及对应数值"""
        self.screenshot()
        # OCR识别
        raw_text = self.O_CARD_NUM.ocr(self.device.image)
        # logger.info(f'OCR原始结果: {raw_text}')

        # 判断结界卡类型
        if any(c in raw_text for c in ['体', 'カ', '力']):
            card_type = '斗鱼'
        elif any(c in raw_text for c in ['勾', '玉']):
            card_type = '太鼓'
        else:
            logger.warning(f'结界卡类型识别失败，原始内容: {raw_text}')
            # self.push_notify(content=f'结界卡类型识别失败: {raw_text}')
            return 'unknown', 0  # 未知类型返回0

        # 提取纯数字部分（兼容带+号的情况，如+100）
        cleaned = re.sub(r'[^\d+]', '', raw_text)  # 保留数字和加号
        match = re.search(r'\d+', cleaned)  # 匹配连续数字

        try:
            value = int(match.group()) if match else 0
        except ValueError:
            logger.warning(f'数值转换异常，清理后文本: {cleaned}')
            value = 0

        if value <= 0:
            self.push_notify(content=f'数值异常: {raw_text} -> 解析值: {value}')
            return card_type, 0

        # logger.info(f'识别成功: 卡类型: {card_type}, 数值: {value}')
        return card_type, value


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config('日常1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run_utilize(SelectFriendList.DIFFERENT_SERVER)
    # t.check_utilize_add()
    # t.check_card_num('勾玉', 67)
    # t.screenshot()
    # print(t.appear(t.I_BOX_EXP, threshold=0.6))
    # print(t.appear(t.I_BOX_EXP_MAX, threshold=0.6))
