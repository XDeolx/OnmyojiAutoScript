# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from enum import Enum
from pydantic import Field, field_validator, field_serializer, model_validator

from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.config_scheduler import Scheduler


class Strategy(str, Enum):
    Majority = 'frog_majority'
    Minority = 'frog_minority'
    Dashen = 'frog_dashen'
    Oas = 'frog_oas'
    AlwaysRed = 'frog_always_red'
    AlwaysBlue = 'frog_always_blue'

class FrogBossConfig(ConfigBase):
    before_end_frog: Time = Field(default=Time(0, 15, 0), description='before_end_frog_help')
    strategy_frog: Strategy = Field(default=Strategy.Majority, description='strategy_frog_help')

    @field_validator('strategy_frog', mode='wrap')
    @classmethod
    def migrate_removed_strategy(cls, value, handler):
        # Legacy state is accepted for storage only, never exposed as an enum choice.
        if value in ('frog_bilibili', '需要重新选择策略'):
            return '需要重新选择策略'
        return handler(value)

    @field_serializer('strategy_frog')
    def serialize_strategy(self, value):
        return value.value if isinstance(value, Strategy) else value

    @property
    def needs_strategy_selection(self) -> bool:
        return self.strategy_frog == '需要重新选择策略'

class FrogBoss(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    frog_boss_config: FrogBossConfig = Field(default_factory=FrogBossConfig)

    @model_validator(mode='after')
    def disable_unselected_strategy(self):
        if self.frog_boss_config.needs_strategy_selection:
            self.scheduler.enable = False
        return self



