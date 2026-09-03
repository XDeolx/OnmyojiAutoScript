from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.action import conditional_action
from tasks.GameUi.default_pages import reward_random_click
from tasks.GameUi.page import (Page, page_main, sequence, page_battle, page_battle_prepare, page_reward,
                               page_battle_result, all_of, any_of)
from tasks.GlobalGame.assets import GlobalGameAssets

# 爬塔活动主界面
page_act = Page(ActivityShikigamiAssets.I_TO_BATTLE_MAIN)
page_act.add_enter_failure_hooks(RightActivityAssets.I_TOGGLE_BUTTON,
                                 conditional_action(GlobalGameAssets.I_UI_REWARD, reward_random_click),
                                 GlobalGameAssets.I_UI_BACK_RED, ActivityShikigamiAssets.I_SKIP_BUTTON)
page_act.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act->page_main")
page_main.connect(page_act, ActivityShikigamiAssets.I_MAIN_GOTO_ACT, key="page_main->page_act")
# 爬塔选择页面
page_climb_main = Page(ActivityShikigamiAssets.I_CHECK_CLIMB_MAIN)
page_climb_main.connect(page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_climb_main->page_act")
# 体力爬塔页面
page_act_ap = Page(all_of(ActivityShikigamiAssets.I_CHECK_BATTLE_PASS,
                          ActivityShikigamiAssets.I_CLIMB_MODE_AP))
page_act_ap.connect(page_climb_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_ap->page_climb_main")
# 门票爬塔页面
page_act_pass = Page(all_of(ActivityShikigamiAssets.I_CHECK_BATTLE_PASS,
                            ActivityShikigamiAssets.I_CLIMB_MODE_PASS))
page_act_pass.connect(page_climb_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_pass->page_climb_main")
# 100体爬塔页面
page_act_ap100 = Page(ActivityShikigamiAssets.I_CLIMB_MODE_AP100)
page_act_ap100.add_enter_failure_hooks(GlobalGameAssets.I_UI_BACK_RED)
page_act_ap100.connect(page_climb_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_ap100->page_climb_main")
# BOSS爬塔页面
page_act_boss = Page(ActivityShikigamiAssets.I_AS_BOSS_FIRE)
page_act_boss.connect(page_climb_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_boss->page_climb_main")
