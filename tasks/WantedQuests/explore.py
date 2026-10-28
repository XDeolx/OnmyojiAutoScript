from module.atom.gif import RuleGif
from module.atom.image import RuleImage
from module.logger import logger
from tasks.Exploration import page as pages
from tasks.Exploration.base import BaseExploration
from tasks.Exploration.config import UpType, UserStatus
from tasks.Exploration.script_task import ScriptTask as ExplorationScriptTask
from tasks.Exploration.version import HighLight
from typing import Optional


class ExploreWantedBoss(Exception):
    # 出现一种情况，要求的怪是仅仅最后的Boss，其他小怪不是
    pass


class WQExplore(ExplorationScriptTask, HighLight):
    _explor_cnt: int = 0  # 探索次数
    _max_cnt: int = 0  # 探索最大次数
    _unlock_boss: bool = False

    def _default_detect_categories(self) -> set[str]:
        categories = super()._default_detect_categories()
        categories.add("exploration")
        return categories

    def search_up_fight(self, up_type: UpType = None) -> Optional[RuleImage | RuleGif]:
        if self.appear(self.TEMPLATE_GIF):
            self.fire_monster_type = 'wq_normal'
            return self.TEMPLATE_GIF
        if self._unlock_boss and self.appear(self.I_NORMAL_BATTLE_BUTTON):
            self.fire_monster_type = 'wq_unlock'
            return self.I_NORMAL_BATTLE_BUTTON
        return None

    def check_exit(self, current_page: pages.Page | None) -> bool:
        need_exit = self._explor_cnt >= self._max_cnt
        return need_exit

    def arrive_end(self) -> bool:
        arrived_end = BaseExploration.arrive_end(self)
        if arrived_end:
            if not self._unlock_boss and self.fire_monster_type == '':
                logger.info('No wanted minion found; re-enter chapter and defeat minions to unlock boss')
                self._unlock_boss = True
            elif self._unlock_boss:
                # Do not loop through empty chapters forever if the boss fails to appear.
                raise ExploreWantedBoss
            else:
                self._explor_cnt += 1
        return arrived_end

    def run_on_battle(self):
        super().run_on_battle()
        # Count the chapter only after returning from battle, not on entry.
        if self.fire_monster_type == 'boss':
            self._explor_cnt += 1

    def explore(self, goto: RuleImage, num: int):
        logger.info(f'Start exploring with number: {num}')
        self._max_cnt = num
        self._explor_cnt = 0
        self._unlock_boss = False
        self.fire_monster_type = ''
        while True:
            self.screenshot()
            if pages.page_exp_entrance == self.get_current_page():
                break
            if self.appear_then_click(goto, interval=2):
                continue
        self.user_status = UserStatus.ALONE
        self.exec_exp_page()

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from tasks.WantedQuests.assets import WantedQuestsAssets

    config = Config('oas1')
    device = Device(config)
    t = WQExplore(config, device)
    t.explore(goto=WantedQuestsAssets.I_GOTO_1, num=2)
