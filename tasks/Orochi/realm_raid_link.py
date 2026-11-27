"""Solo raid detours and a final-only raid after successful team completion."""
from datetime import datetime
import time

from module.exception import GamePageUnknownError, TaskEnd, ScriptError
from module.logger import logger


class RealmRaidLink:
    def _raid_link_enabled(self):
        # Pets and TrueOrochi reuse run_alone(), but must never trigger this detour.
        if not getattr(self, '_raid_link_active', False):
            return False
        settings = self.config.orochi
        return settings.orochi_config.user_status == 'alone' and settings.realm_raid_link.enable

    def _queue_team_realm_raid(self, success):
        settings = self.config.orochi
        if (success and getattr(self, '_raid_link_active', False)
                and getattr(self, '_orochi_team_completed', False)
                and settings.orochi_config.user_status in ('leader', 'member', 'wild')
                and settings.realm_raid_link.team_finish_enable):
            # Run as a separate scheduled task after Orochi has saved its completion.
            self.config.task_call('RealmRaid')
            logger.info('Orochi team task completed; personal realm raid scheduled')

    def _raid_check_due(self):
        if not self._raid_link_enabled():
            return False
        link = self.config.orochi.realm_raid_link
        return ((link.interval_count > 0 and self.current_count - self._raid_last_count >= link.interval_count)
                or (link.interval_minutes > 0 and time.monotonic() - self._raid_last_time >= link.interval_minutes * 60))

    def _make_raid_runner(self):
        from tasks.RealmRaid.script_task import ScriptTask

        class LinkedRaid(ScriptTask):
            completed = False
            succeeded = False

            def set_next_run(self, task, finish=False, success=False, **kwargs):
                super().set_next_run(task, finish=finish, success=success, **kwargs)
                if task == 'RealmRaid':
                    self.completed = True
                    self.succeeded = success

        return LinkedRaid(config=self.config, device=self.device)

    def _read_raid_tickets(self, runner):
        previous = None
        for _ in range(5):
            runner.screenshot()
            current, remaining, total = runner.O_NUMBER.ocr(self.device.image)
            value = (current, remaining, total)
            if total > 0 and 0 <= current <= total and current + remaining == total:
                if value == previous:
                    return current
                previous = value
            else:
                previous = None
            time.sleep(0.3)
        raise GamePageUnknownError('Cannot confirm realm raid ticket count')

    def _restore_orochi_page(self):
        from tasks.Orochi.page import page_orochi
        self.goto_page(page_orochi)
        if not self.check_layer(self.config.orochi.orochi_config.layer):
            raise GamePageUnknownError('Cannot restore Orochi layer after ticket check')
        self.check_lock(self.config.orochi.general_battle_config.lock_team_enable,
                        self.I_OROCHI_LOCK, self.I_OROCHI_UNLOCK)

    def _set_link_soul_buff(self, enabled):
        if self.config.orochi.orochi_config.soul_buff_enable:
            from tasks.GameUi.page import page_main
            # Soul preset switching leaves us in records, where no buff entry exists.
            self.goto_page(page_main)
            self.open_buff()
            self.soul(is_open=enabled)
            self.close_buff()

    def _validate_raid_resume_souls(self):
        raid = self.config.realm_raid.switch_soul_config
        if not (raid.enable or raid.enable_switch_by_name):
            return
        own = self.config.orochi.switch_soul
        def numbered(value):
            parts = str(value).split(',')
            return len(parts) == 2 and all(p.strip().isdigit() and int(p) > 0 for p in parts)
        if own.auto_switch_soul:
            field = {'拾层': 'ten_switch', '悲鸣': 'eleven_switch',
                     '神罚': 'twelve_switch', '虚无': 'thirteen_switch'}.get(self.config.orochi.orochi_config.layer)
            valid = field and numbered(getattr(own, field))
        else:
            valid = ((own.enable and numbered(own.switch_group_team))
                     or (own.enable_switch_by_name and own.group_name.strip() and own.team_name.strip()))
        if not valid:
            raise ScriptError('突破会切换御魂；开启续刷前请配置有效的八岐大蛇御魂方案')

    def _run_linked_realm_raid(self, final=False):
        """Return True when the current Orochi run should stop after this detour."""
        if not self._raid_link_enabled():
            return False
        from tasks.GameUi.page import page_realm_raid, page_main
        started = datetime.now()
        try:
            runner = self._make_raid_runner()
            runner.goto_page(page_realm_raid)
            tickets = self._read_raid_tickets(runner)
            link = self.config.orochi.realm_raid_link
            base = self.config.realm_raid.raid_config.number_base
            if tickets <= 0 or tickets < base or (not final and tickets < link.ticket_threshold):
                logger.info('Realm raid ticket threshold not reached')
                if not final:
                    self._restore_orochi_page()
                return False
            logger.info('Start linked personal realm raid')
            if not final and link.resume_after_raid:
                self._validate_raid_resume_souls()
            runner.goto_page(page_main)
            self._set_link_soul_buff(False)
            try:
                runner.run()
            except TaskEnd:
                if not runner.completed:
                    raise
            if not runner.completed or not runner.succeeded:
                raise ScriptError('Linked realm raid did not finish successfully; Orochi resume cancelled')
            # Never refill the original quota after the final check.
            resume = (not final and link.resume_after_raid and self.current_count < self.limit_count
                      and started - self.start_time < self.limit_time)
            if resume:
                self.switch_orochi_souls()
                self._set_link_soul_buff(True)
                self._restore_orochi_page()
                logger.info(f'Resume Orochi: {self.limit_count - self.current_count} battles remaining')
                return False
            self._raid_link_stopped = True
            return True
        finally:
            # Checks, raids and restoration do not consume the parent time budget.
            self.start_time += datetime.now() - started
            self._raid_last_count = self.current_count
            self._raid_last_time = time.monotonic()
