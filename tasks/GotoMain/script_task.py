# This Python file uses the following encoding: utf-8
from module.exception import TaskEnd
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main


class ScriptTask(GameUi):
    def run(self) -> None:
        self.device.stuck_record_clear()
        # Navigation failures are not evidence of server maintenance.
        self.goto_page(page_main)
        raise TaskEnd
