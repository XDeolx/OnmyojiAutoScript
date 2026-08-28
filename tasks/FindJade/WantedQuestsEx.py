from tasks.WantedQuests.config import CooperationType, WantedQuestsConfig


def need_invite_vip(self):
    return True


def get_invite_vip_name(self, ctype: CooperationType):
    if not self.fade_conf:
        return ""
    return self.fade_conf.get_invite_name(ctype)


def next_run(self):
    pass


def invite_success_callback(self, ctype: CooperationType, name: str):
    if not self.fade_conf:
        return
    self.fade_conf.update_invite_history(ctype, name)
    self.config.save()


def get_config(self):
    # FindJade 复用 WantedQuests 的执行逻辑，保留用户在 WQ 中配置的
    # battle_priority 等任务参数，仅覆盖 FindJade 专用的协作设置。
    wq_config = self.config.wanted_quests.wanted_quests_config
    # 通过序列化重新构造，避免复制 cached_property 中可能过期的排序结果。
    config = WantedQuestsConfig.model_validate(wq_config.model_dump())
    config.invite_friend_name="default"
    config.cooperation_only=True
    config.cooperation_type=self.fade_conf.get_cooperation_type_mask()
    return config
