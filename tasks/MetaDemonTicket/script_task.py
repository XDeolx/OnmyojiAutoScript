from module.exception import TaskEnd
from module.cooperation import Cooperation
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.MetaDemonTicket.ticket_farming import run_ticket_farming


class ScriptTask(GameUi):
    def run(self):
        mode = self.config.meta_demon_ticket.general_config.mode
        runtime = getattr(self, 'cooperation_runtime', None)
        owned_runtime = runtime is None
        runtime = runtime or Cooperation(self.config.config_name)
        self.cooperation_runtime = runtime
        try:
            if owned_runtime:
                runtime.start()
            runtime.publish('MetaDemonTicket')
            full = run_ticket_farming(self, mode)
            self.goto_page(page_main)
            self.set_next_run(task='MetaDemonTicket', success=full)
        finally:
            if owned_runtime:
                runtime.close()
            self.cooperation_runtime = None
        raise TaskEnd
