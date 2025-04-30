import unittest
from datetime import datetime

from agent_job_monitor.analysis import check_missed
from agent_job_monitor.config import Thresholds
from agent_job_monitor.model import SUCCEEDED, JobRun
from agent_job_monitor.schedules import interval_seconds

from .helpers import NOW, job
from .test_schedule_times import schedule


class IntervalSecondsTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(interval_seconds(schedule(subday_type=2, subday_interval=30)), 30)
        self.assertEqual(interval_seconds(schedule(subday_type=4, subday_interval=5)), 300)
        self.assertEqual(interval_seconds(schedule(subday_type=8, subday_interval=2)), 7200)

    def test_fixed_time_schedules_have_none(self):
        self.assertIsNone(interval_seconds(schedule()))
        self.assertIsNone(interval_seconds(schedule(freq_type=1)))
        self.assertIsNone(interval_seconds(schedule(subday_type=4, subday_interval=0)))


class FrequentSchedulesTest(unittest.TestCase):
    def runs(self):
        return [JobRun("NIGHTLY", datetime(2024, 5, 1, 8), 5, SUCCEEDED)]

    def test_a_schedule_faster_than_the_limit_is_not_checked(self):
        every_20_seconds = schedule(subday_type=2, subday_interval=20, start_time=0)
        self.assertEqual(check_missed(job(), self.runs(), None, [every_20_seconds], Thresholds(), NOW), [])

    def test_the_limit_is_configurable(self):
        every_20_seconds = schedule(subday_type=2, subday_interval=20, start_time=0)
        found = check_missed(job(), self.runs(), None, [every_20_seconds], Thresholds(min_schedule_seconds=10, max_expected=50), NOW)
        self.assertEqual(len(found[0].detail["missed"]), 50)

    def test_only_the_newest_expected_starts_are_examined(self):
        every_minute = schedule(subday_type=4, subday_interval=1, start_time=0)
        (f,) = check_missed(job(), self.runs(), None, [every_minute], Thresholds(), NOW)
        self.assertEqual(len(f.detail["missed"]), 500)
        self.assertEqual(f.detail["missed"][-1], "2024-05-02T07:50:00")
        self.assertEqual(f.detail["expected_in_window"], 500)
