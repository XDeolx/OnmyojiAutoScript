from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from tasks.ActivityShikigami.base_act import BaseAct
from tasks.ActivityShikigami.config import GeneralClimb


class ActivityShikigamiFatigueTest(unittest.TestCase):
    @staticmethod
    def create_task(**overrides):
        config = SimpleNamespace(
            fatigue_rest_enable=True,
            fatigue_rest_battle_count=60,
            fatigue_rest_delay_min=1.0,
            fatigue_rest_delay_max=5.0,
            fatigue_rest_minutes_min=5,
            fatigue_rest_minutes_max=10,
            fatigue_rest_settlement_delay_min=1.0,
            fatigue_rest_settlement_delay_max=3.0,
        )
        for name, value in overrides.items():
            setattr(config, name, value)
        task = BaseAct.__new__(BaseAct)
        task.conf = SimpleNamespace(general_climb=config)
        task.start_time = datetime.now()
        task._fatigue_battle_count = 0
        return task

    def test_delay_progresses_from_cycle_start_to_end(self):
        task = self.create_task()
        with patch(
            'tasks.ActivityShikigami.base_act.random.triangular',
            side_effect=[1.22, 4.76],
        ) as triangular, patch(
            'tasks.ActivityShikigami.base_act.time.sleep',
        ) as sleep:
            self.assertEqual(task._apply_fatigue_battle_delay(), 1.22)
            task._fatigue_battle_count = 59
            self.assertEqual(task._apply_fatigue_battle_delay(), 4.76)

        first_low, first_high, first_center = triangular.call_args_list[0].args
        last_low, last_high, last_center = triangular.call_args_list[1].args
        self.assertEqual((first_low, first_center), (1.0, 1.0))
        self.assertEqual((last_high, last_center), (5.0, 5.0))
        self.assertLess(first_high, last_low)
        sleep.assert_any_call(1.22)
        sleep.assert_any_call(4.76)

    def test_rest_starts_only_after_a_complete_cycle_and_resets_count(self):
        task = self.create_task(fatigue_rest_battle_count=3)
        task._fatigue_battle_count = 2
        with patch('tasks.ActivityShikigami.base_act.time.sleep') as sleep:
            task._apply_fatigue_rest()
        sleep.assert_not_called()

        task._fatigue_battle_count = 3
        with patch(
            'tasks.ActivityShikigami.base_act.random.uniform',
            return_value=7.5,
        ), patch('tasks.ActivityShikigami.base_act.time.sleep') as sleep:
            task._apply_fatigue_rest()

        sleep.assert_called_once_with(450.0)
        self.assertEqual(task._fatigue_battle_count, 0)

    def test_disabled_fatigue_does_not_wait_or_record_progress(self):
        task = self.create_task(fatigue_rest_enable=False)
        with patch('tasks.ActivityShikigami.base_act.time.sleep') as sleep:
            self.assertEqual(task._apply_fatigue_battle_delay(), 0.0)
            task._apply_fatigue_rest()
        task._record_fatigue_battle()

        sleep.assert_not_called()
        self.assertEqual(task._fatigue_battle_count, 0)

    def test_settlement_delay_waits_before_the_first_exit_click(self):
        task = self.create_task()
        context = SimpleNamespace()
        timer = SimpleNamespace(
            reached=lambda: False,
        )
        timer.start = lambda: timer

        with patch(
            'tasks.ActivityShikigami.base_act.random.uniform',
            return_value=2.35,
        ), patch('tasks.ActivityShikigami.base_act.Timer', return_value=timer) as timer_class:
            self.assertFalse(task._fatigue_settlement_click_ready(context))
            self.assertFalse(task._fatigue_settlement_click_ready(context))
            timer.reached = lambda: True
            self.assertTrue(task._fatigue_settlement_click_ready(context))

        timer_class.assert_called_once_with(2.35)
        self.assertEqual(context.fatigue_settlement_delay, 2.35)

    def test_config_rejects_reversed_fatigue_ranges(self):
        with self.assertRaises(ValidationError):
            GeneralClimb(fatigue_rest_delay_min=5, fatigue_rest_delay_max=1)
        with self.assertRaises(ValidationError):
            GeneralClimb(fatigue_rest_minutes_min=10, fatigue_rest_minutes_max=5)
        with self.assertRaises(ValidationError):
            GeneralClimb(
                fatigue_rest_settlement_delay_min=3,
                fatigue_rest_settlement_delay_max=1,
            )

    def test_pass_limit_keeps_old_single_value_as_easy_mode(self):
        config = GeneralClimb(pass_limit=50)

        self.assertEqual(config.pass_limit, '50')
        self.assertEqual(config.pass_limits_v, (50, 0))
        self.assertEqual(config.pass_limit_for('easy'), 50)
        self.assertEqual(config.pass_limit_for('hard'), 0)
        self.assertEqual(config.run_sequence_v[0], 'pass')

    def test_pass_limit_supports_easy_and_hard_modes(self):
        config = GeneralClimb(pass_limit='20,10')

        self.assertEqual(config.pass_limits_v, (20, 10))
        self.assertEqual(config.limit_for('pass'), 30)

    def test_pass_limit_rejects_invalid_mode_counts(self):
        with self.assertRaises(ValidationError):
            GeneralClimb(pass_limit='20,')
        with self.assertRaises(ValidationError):
            GeneralClimb(pass_limit='easy,10')
