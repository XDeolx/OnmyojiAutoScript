from module.atom.image import RuleImage

class NavigationAssets:
    I_MAIN_GOTO_ACTIVITY = RuleImage(roi_front=(1188, 304, 35, 28), roi_back=(1164, 134, 83, 393), threshold=0.7, method='Template matching', file='./tasks/MetaDemon/md/page_main_goto_activity.png')
    I_ACTIVITY_SKIP = RuleImage(roi_front=(1159, 37, 51, 22), roi_back=(1141, 27, 86, 43), threshold=0.8, method='Template matching', file='./tasks/MetaDemon/md/page_activity_skip.png')
    I_ACTIVITY_GENERAL_CLOSE_RED = RuleImage(roi_front=(1149, 169, 40, 32), roi_back=(1008, 0, 272, 274), threshold=0.8, method='Template matching', file='./tasks/MetaDemon/md/page_activity_general_close_red.png')
    I_ACTIVITY_SKIP_ENSURE = RuleImage(roi_front=(719, 446, 120, 30), roi_back=(679, 417, 192, 85), threshold=0.8, method='Template matching', file='./tasks/MetaDemon/md/page_activity_skip_ensure.png')
    I_PAGE_CHECK_ACTIVITY = RuleImage(roi_front=(151, 18, 140, 41), roi_back=(141, 0, 192, 69), threshold=0.8, method='Template matching', file='./tasks/MetaDemon/md/page_check_activity.png')
    I_PAGE_METADEMON_CHECK_BOSS_PAGE = RuleImage(roi_front=(1064, 19, 43, 40), roi_back=(1054, 7, 62, 63), threshold=0.8, method='Template matching', file='./tasks/MetaDemon/md/page_check_metademon_check_boss_page.png')
    I_PAGE_METADEMON_MD_CHECK_MAIN_PAGE = RuleImage(roi_front=(907, 60, 76, 208), roi_back=(869, 14, 171, 288), threshold=0.8, method='Template matching', file='./tasks/MetaDemon/md/page_check_metademon_md_check_main_page.png')
    I_PAGE_METADEMON_MD_CHECK_MAIN_PAGE_BACKUP = RuleImage(roi_front=(907, 60, 76, 208), roi_back=(869, 14, 171, 288), threshold=0.8, method='Template matching', file='./tasks/MetaDemon/md/page_checks_page_metademon_md_check_main_page_backup.png')
    I_METADEMON_ENTRY_LABEL = RuleImage(roi_front=(994, 182, 22, 74), roi_back=(970, 150, 70, 140), threshold=0.8, method='Template matching', file='./tasks/MetaDemon/md/page_metademon_entry_label.png')
