# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta, time
from module.logger import logger

from pydantic import BaseModel, Field, validator

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time, dynamic_hide
from typing import Optional


class GeneralClimb(ConfigBase):
    limit_time: Time = Field(default=Time(hour=1, minute=30), description='总限制时间')
    pass_limit: str = Field(default='50', description='pass_limit_help')
    ap_limit: int = Field(default=300)
    boss_limit: int = Field(default=20)
    ap100_limit: int = Field(default=20)
    run_sequence: str = Field(default='pass,ap,ap100,boss',
                              description='pass:门票,ap100:100体,boss:boss战,ap:体力\n'
                                          '逗号分隔,从左到右依次运行\n'
                                          '例:pass,ap100,boss,ap=门票->100体->boss战->体力')
    # # 门票爬塔buff
    # pass_buff: str = Field(default='buff_4,buff_5', description='门票爬塔加成,buff1-5,加成页从左往右顺序,清空则不切换加成')
    # # 体力爬塔buff
    # ap_buff: str = Field(default='buff_4,buff_5', description='体力爬塔加成,buff1-5,加成页从左往右顺序,清空则不切换加成')
    # # boss爬塔buff
    # boss_buff: str = Field(default='buff_1,buff_3', description='boss战爬塔加成,buff1-5,加成页从左往右顺序,清空则不切换加成')
    # 结束后激活 御魂清理
    active_souls_clean: bool = Field(default=False, description='是否运行结束后清理御魂')
    # 点击战斗随机休息
    random_sleep: bool = Field(default=False, description='是否启用在点击战斗前随机休息')
    use_penta_pass: bool = Field(default=False, description='use_penta_pass_help')
    fatigue_rest_enable: bool = Field(default=False, description='fatigue_rest_enable_help')
    fatigue_rest_battle_count: int = Field(default=60, ge=10, le=500,
                                            description='fatigue_rest_battle_count_help')
    fatigue_rest_delay_min: float = Field(default=1.0, ge=0.0, le=30.0,
                                           description='fatigue_rest_delay_min_help')
    fatigue_rest_delay_max: float = Field(default=5.0, ge=0.1, le=30.0,
                                           description='fatigue_rest_delay_max_help')
    fatigue_rest_minutes_min: int = Field(default=5, ge=1, le=60,
                                          description='fatigue_rest_minutes_min_help')
    fatigue_rest_minutes_max: int = Field(default=10, ge=1, le=60,
                                          description='fatigue_rest_minutes_max_help')
    fatigue_rest_settlement_delay_min: float = Field(default=1.0, ge=0.0, le=30.0,
                                                      description='fatigue_rest_settlement_delay_min_help')
    fatigue_rest_settlement_delay_max: float = Field(default=3.0, ge=0.1, le=30.0,
                                                      description='fatigue_rest_settlement_delay_max_help')
    settlement_region_enable: bool = Field(default=False, description='settlement_region_enable_help')
    settlement_detail_enable: bool = Field(default=True, description='settlement_detail_enable_help')
    settlement_detail_interval_min: int = Field(default=20, ge=1, le=500,
                                                 description='settlement_detail_interval_min_help')
    settlement_detail_interval_max: int = Field(default=40, ge=1, le=500,
                                                 description='settlement_detail_interval_max_help')
    settlement_detail_delay_min: float = Field(default=1.0, ge=0.0, le=10.0,
                                                description='settlement_detail_delay_min_help')
    settlement_detail_delay_max: float = Field(default=1.5, ge=0.0, le=10.0,
                                                description='settlement_detail_delay_max_help')
    settlement_burst_percent: int = Field(default=5, ge=0, le=100,
                                          description='settlement_burst_percent_help')

    @validator('fatigue_rest_delay_max')
    def validate_fatigue_delay_range(cls, value, values):
        if value < values.get('fatigue_rest_delay_min', value):
            raise ValueError('疲劳点击延迟下限不能大于上限')
        return value

    @validator('fatigue_rest_minutes_max')
    def validate_fatigue_rest_range(cls, value, values):
        if value < values.get('fatigue_rest_minutes_min', value):
            raise ValueError('疲劳休息时长下限不能大于上限')
        return value

    @validator('fatigue_rest_settlement_delay_max')
    def validate_fatigue_settlement_delay_range(cls, value, values):
        if value < values.get('fatigue_rest_settlement_delay_min', value):
            raise ValueError('疲劳结算点击延迟下限不能大于上限')
        return value

    @validator('settlement_detail_interval_max')
    def validate_settlement_detail_interval(cls, value, values):
        if value < values.get('settlement_detail_interval_min', value):
            raise ValueError('模拟查看详情的最小战斗间隔不能大于最大间隔')
        return value

    @validator('settlement_detail_delay_max')
    def validate_settlement_detail_delay(cls, value, values):
        if value < values.get('settlement_detail_delay_min', value):
            raise ValueError('模拟查看详情的最小等待不能大于最大等待')
        return value

    @property
    def limit_time_v(self) -> timedelta:
        if isinstance(self.limit_time, time):
            return timedelta(hours=self.limit_time.hour, minutes=self.limit_time.minute,
                             seconds=self.limit_time.second)
        return self.limit_time

    @property
    def run_sequence_v(self) -> list[str]:
        """得到limit>0且配置好的运行顺序序列"""
        self.valid_run_sequence()
        str_list = [climb_type.strip() for climb_type in self.run_sequence.split(',')]
        return [climb_type for climb_type in str_list if self.limit_for(climb_type) > 0]

    @property
    def pass_limits_v(self) -> tuple[int, int]:
        """返回门票简单、困难模式的次数限制。"""
        easy_limit, *hard_limit = (int(part) for part in self.pass_limit.split(','))
        return easy_limit, hard_limit[0] if hard_limit else 0

    def pass_limit_for(self, mode: str) -> int:
        easy_limit, hard_limit = self.pass_limits_v
        if mode == 'easy':
            return easy_limit
        if mode == 'hard':
            return hard_limit
        raise ValueError(f'Unsupported pass mode: {mode}')

    def limit_for(self, climb_type: str) -> int:
        if climb_type == 'pass':
            return sum(self.pass_limits_v)
        return getattr(self, f'{climb_type}_limit', 0)

    @validator('pass_limit', pre=True, always=True)
    def parse_pass_limit(cls, value):
        """兼容旧的单个次数和“简单次数,困难次数”写法。"""
        raw_value = '0' if value is None else str(value).strip()
        parts = [part.strip() for part in raw_value.split(',')]
        if len(parts) not in (1, 2) or any(not part for part in parts):
            raise ValueError('门票爬塔次数必须填写数字或“简单次数,困难次数”')
        if any(not part.isdigit() for part in parts):
            raise ValueError('门票爬塔次数只能填写非负整数')
        return ','.join(str(int(part)) for part in parts)

    # @model_validator(mode='after')
    def valid_run_sequence(self):
        if not self.run_sequence or not self.run_sequence.strip():
            raise ValueError('run sequence cannot be empty')
        sequence_list = [climb_type.strip() for climb_type in self.run_sequence.split(',')]
        if not sequence_list or len(sequence_list) < 1:
            raise ValueError('run sequence cannot be empty')
        label_set = {field.replace('_limit', '') for field in self.model_fields if field.endswith('_limit')}
        for climb_type in sequence_list:
            if climb_type not in label_set:
                raise ValueError(f'run sequence can only be one of {", ".join(label_set)}, now is {climb_type}')
        return self

    @validator('limit_time', pre=True, always=True)
    def parse_limit_time(cls, value):
        if isinstance(value, str):
            if value.isdigit():
                try:
                    value = int(value)
                except ValueError:
                    logger.warning('Invalid limit_time value. Expected format: seconds')
                    return time(hour=0, minute=30, second=0)
                delta = timedelta(seconds=value)
                return time(hour=delta.seconds // 3600, minute=delta.seconds // 60 % 60, second=delta.seconds % 60)
            else:
                try:
                    return time.fromisoformat(value)
                except ValueError:
                    logger.warning('Invalid limit_time value. Expected format: HH:MM:SS')
                    return time(hour=0, minute=30, second=0)
        return value


def check_soul_by_number(enable_switch: bool, group_team: str, label: str):
    if not enable_switch:
        return
    if not group_team or group_team == "-1,-1":
        raise ValueError(f"[{label}]Switch Soul configuration is enabled, but there is no setting")
    if ',' not in group_team:
        raise ValueError(f"[{label}]The switch soul configuration must be in English ','")
    parts = group_team.split(',')
    if len(parts) != 2:
        raise ValueError(f"[{label}]The length of the switch soul configuration must be equal to 2")
    if not all(p.strip().isdigit() for p in parts):
        raise ValueError(f"[{label}]Switching soul configurations must be numeric")


def check_soul_by_ocr(enable_switch: bool, group_team: str, label: str):
    if not enable_switch:
        return
    if not group_team:
        raise ValueError(f"[{label}]Switch Soul configuration is enabled, but there is no setting")
    if ',' not in group_team:
        raise ValueError(f"[{label}]The switch soul configuration must be in English ','")
    parts = group_team.split(',')
    if len(parts) != 2:
        raise ValueError(f"[{label}]The length of the switch soul configuration must be equal to 2")


class SwitchSoulConfig(BaseModel):
    enable_switch_pass: bool = Field(default=False)
    pass_group_team: str = Field(default='-1,-1', description='pass_group_team_help')
    enable_switch_pass_by_name: bool = Field(default=False)
    pass_group_team_name: str = Field(default='')

    enable_switch_ap: bool = Field(default=False)
    ap_group_team: str = Field(default='-1,-1')
    enable_switch_ap_by_name: bool = Field(default=False)
    ap_group_team_name: str = Field(default='')

    enable_switch_boss: bool = Field(default=False)
    boss_group_team: str = Field(default='-1,-1')
    enable_switch_boss_by_name: bool = Field(default=False)
    boss_group_team_name: str = Field(default='')

    enable_switch_ap100: bool = Field(default=False)
    ap100_group_team: str = Field(default='-1,-1')
    enable_switch_ap100_by_name: bool = Field(default=False)
    ap100_group_team_name: str = Field(default='')

    # @model_validator(mode='after')
    def validate_switch_soul(self):
        label_set = self.get_label_set()
        for label in label_set:
            enable_num = getattr(self, f"enable_switch_{label}", False)
            team = getattr(self, f"{label}_group_team", None)
            check_soul_by_number(enable_num, team, label=label.upper())

            enable_ocr = getattr(self, f"enable_switch_{label}_by_name", False)
            team_name = getattr(self, f"{label}_group_team_name", None)
            check_soul_by_ocr(enable_ocr, team_name, label=label.upper())
        return self

    def get_label_set(self):
        return {field.replace("enable_switch_", "") for field in self.model_fields if
                field.startswith("enable_switch_") and not field.endswith("by_name")}


class RichManConfig(ConfigBase):
    buy_ap: bool = Field(default=False, description='是否购买体力')
    buy_reward: bool = Field(default=False, description='是否购买奖励积分')
    buy_ticket: bool = Field(default=False, description='是否购买定向骰子')


class ActivityShikigami(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    general_climb: GeneralClimb = Field(default_factory=GeneralClimb)
    rich_man: RichManConfig = Field(default_factory=RichManConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)

    pass_battle_conf: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    ap_battle_conf: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    boss_battle_conf: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    ap100_battle_conf: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)

    hide_fields = dynamic_hide('rich_man')
