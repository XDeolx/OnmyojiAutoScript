# This Python file uses the following encoding: utf-8
from datetime import datetime
from tasks.MetaDemon.boss_battle import BossBattle
from tasks.MetaDemon.config import MetaDemonMode


class ScriptTask(BossBattle):
    """超鬼王战斗和协助入口。"""

    def run(self):
        modes = [self.config.meta_demon.meta_demon_config.mode]
        for mode in modes:
            if mode == MetaDemonMode.BOSS_ASSIST:
                from tasks.MetaDemon.assistance import run_assistance
                from module.cooperation import Cooperation
                self.start_time = datetime.now()
                runtime = Cooperation(self.config.config_name)
                runtime.start()
                runtime.publish('MetaDemon')
                self.cooperation_runtime = runtime
                try:
                    return run_assistance(self)
                finally:
                    runtime.clear_outgoing_battle_states('MetaDemonAssistance')
                    runtime.close()
                    self.cooperation_runtime = None
            if mode == MetaDemonMode.BOSS_BATTLE:
                self.start_time = datetime.now()
                return super().run()
        self.set_next_run(task="MetaDemon", success=True)
        self.finish_task()
