from tasks.GameUi.page import Page, page_main, page_reward, page_battle, page_battle_result, page_shikigami_records, random_click, reward_random_click
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.MetaDemon.assets import MetaDemonAssets
from tasks.MetaDemon.navigation_assets import NavigationAssets as A


def clear_activity_overlay(task):
    for rule in (A.I_ACTIVITY_SKIP_ENSURE, A.I_ACTIVITY_SKIP, A.I_ACTIVITY_GENERAL_CLOSE_RED):
        if task.appear_then_click(rule, interval=1):
            return True
    return False


def enter_meta_demon_boss(task):
    return (task.appear_then_click(A.I_METADEMON_ENTRY_LABEL, interval=0.8)
            or task.appear_then_click(A.I_PAGE_METADEMON_MD_CHECK_MAIN_PAGE, interval=0.8)
            or task.appear_then_click(A.I_PAGE_METADEMON_MD_CHECK_MAIN_PAGE_BACKUP, interval=0.8))


page_activity = Page(A.I_PAGE_CHECK_ACTIVITY)
page_main.connect(page_activity, A.I_MAIN_GOTO_ACTIVITY, key='page_main->page_activity')
page_activity.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key='page_activity->page_main')
page_activity.add_enter_failure_hooks(clear_activity_overlay)
page_activity.add_enter_success_hooks(clear_activity_overlay)
page_meta_demon_boss = Page(A.I_PAGE_METADEMON_CHECK_BOSS_PAGE)
page_meta_demon_boss.add_enter_success_hooks(MetaDemonAssets.I_MD_CLOSE_POPUP)
page_meta_demon_boss.add_enter_success_hooks(lambda task: getattr(task, "handle_borrow_confirmation", lambda: False)())
page_meta_demon_boss.connect(page_activity, GlobalGameAssets.I_UI_BACK_YELLOW, key='page_meta_demon_boss->page_activity')
page_activity.connect(page_meta_demon_boss, enter_meta_demon_boss, key='page_activity->page_meta_demon_boss')
page_reward.connect(page_meta_demon_boss, reward_random_click, key='page_reward->page_meta_demon_boss')
page_battle_result.connect(page_meta_demon_boss, random_click(), key='page_battle_result->page_meta_demon_boss')
