# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig as BaseSwitchSoulConfig
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.GeneralInvite.config_invite import InviteConfig
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig


class UserStatus(str, Enum):
    LEADER = 'leader'
    MEMBER = 'member'
    ALONE = 'alone'
    WILD = 'wild'  # 还不打算实现

class Layer(str, Enum):
    ONE = '壹层'
    TWO = '贰层'
    THREE = '叁层'
    FOUR = '肆层'
    FIVE = '伍层'
    SIX = '陆层'
    SEVEN = '柒层'
    EIGHT = '捌层'
    NINE = '玖层'
    TEN = '拾层'
    ELEVEN = '悲鸣'
    TWELVE = '神罚'
    THIRTEEN = '虚无'


class OrochiConfig(ConfigBase):
    # 身份
    user_status: UserStatus = Field(default=UserStatus.LEADER, description='user_status_help')
    # 层数
    layer: Layer = Field(default=Layer.ELEVEN, description='layer_help')
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 限制次数
    limit_count: int = Field(default=30, description='limit_count_help')
    # 是否开启御魂加成
    soul_buff_enable: bool = Field(default=False, description='soul_buff_enable_help')
    # 是否御魂结束检测是否出现真蛇
    check_true_orochi_enable: bool = Field(default=False, description='check_true_orochi_enable_help')

class SwitchSoulConfig(BaseSwitchSoulConfig):
    enable: bool = Field(default=False)
    switch_group_team: str = Field(default='-1,-1', description='switch_group_team_help')
    enable_switch_by_name: bool = Field(default=False, description='enable_switch_by_name_help')
    group_name: str = Field(default='')
    team_name: str = Field(default='')
    auto_switch_soul: bool = Field(default=False, description='auto_switch_soul_orochi_help')
    # 十层 config
    ten_switch: str = Field(default='-1,-1', description='ten_switch_help')
    # 悲鸣 config
    eleven_switch: str = Field(default='-1,-1', description='eleven_switch_help')
    # 神罚 config
    twelve_switch: str = Field(default='-1,-1', description='twelve_switch_help')
    # 虚无 config
    thirteen_switch: str = Field(default='-1,-1', description='thirteen_switch_help')


class RealmRaidLinkConfig(ConfigBase):
    team_finish_enable: bool = Field(default=False, title='组队任务结束后执行个人突破', description='队长、队员或野队模式达到本次局数或时间上限并正常结束后，调度一次个人突破任务，沿用其全部配置。中途不检查，突破后不续刷；邀请失败、队伍解散或等待超时提前退出不触发。独立于单人联动开关。')
    enable: bool = Field(default=False, title='检查突破票并调用个人突破', description='仅支持单人模式。中途达到票数门槛时执行个人突破；刷蛇正常结束后，只要票数满足个人突破的保留票数设置也会执行一次。')
    interval_count: int = Field(default=20, ge=0, title='每完成多少局检查', description='0 表示关闭按局数检查。')
    interval_minutes: int = Field(default=10, ge=0, title='检查间隔（分钟）', description='0 表示关闭按时间检查；到时在当前战斗结算后检查。两项都为 0 时仅结束后检查。')
    ticket_threshold: int = Field(default=25, ge=1, le=30, title='中途触发突破票数')
    resume_after_raid: bool = Field(default=False, title='突破后继续之前的八岐大蛇任务', description='仅支持单人模式。突破正常结束后继续本次剩余局数与刷蛇时间；不重新计算整轮次数。关闭则突破后结束本次刷蛇。')


class Orochi(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    orochi_config: OrochiConfig = Field(default_factory=OrochiConfig)
    invite_config: InviteConfig = Field(default_factory=InviteConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    realm_raid_link: RealmRaidLinkConfig = Field(default_factory=RealmRaidLinkConfig)

