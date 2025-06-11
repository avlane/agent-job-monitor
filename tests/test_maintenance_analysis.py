import unittest
from datetime import datetime

from agent_job_monitor.analysis import analyse, check_missed, check_overruns, check_running
from agent_job_monitor.config import Config, Thresholds, parse_config
from agent_job_monitor.model import RunningJob

from .helpers import NOW, history, job, run, server
from .test_overruns import steady
from .test_schedule_times import schedule


def window(**kw):
    return parse_config({"maintenance": [dict({"start": "00:00", "end": "24:00"}, **kw)]})


class MaintenanceInAnalysisTest(unittest.TestCase):
    def codes(self, cfg, runs, running=None, schedules=None):
        report = analyse(server(), [job()], {"NIGHTLY": runs}, cfg, running, schedules)
        return [f.code for f in report.findings if f.severity != "info"]

    def test_an_overrun_inside_a_window_is_silenced(self):
        runs = steady(600, last=1700)  # the last run started at 07:00
        self.assertEqual(self.codes(Config(), runs), ["JOB_OVERRUN"])
        self.assertEqual(self.codes(window(start="06:30", end="07:30"), runs), [])
        self.assertEqual(self.codes(window(start="08:00", end="09:00"), runs), ["JOB_OVERRUN"])

    def test_only_the_listed_kinds_are_silenced(self):
        runs = steady(600, last=1700)
        self.assertEqual(self.codes(window(suppress=["missed"]), runs), ["JOB_OVERRUN"])
        self.assertEqual(self.codes(window(suppress=["overrun"]), runs), [])

    def test_a_job_that_is_running_long_during_a_window(self):
        runs = steady(600)
        running = {"NIGHTLY": RunningJob("NIGHTLY", datetime(2024, 5, 2, 7, 30), 1)}
        self.assertEqual(self.codes(Config(), runs, running), ["JOB_RUNNING_LONG"])
        self.assertEqual(self.codes(window(start="07:00", end="09:00", suppress=["running"]), runs, running), [])

    def test_a_missed_start_inside_a_window_is_not_missed(self):
        s = schedule(start_time=3600)
        runs = [run(55, 60), run(31, 60)]
        schedules = {"NIGHTLY": [s]}
        self.assertEqual(self.codes(Config(), runs, None, schedules), ["SCHEDULE_MISSED"])
        self.assertEqual(self.codes(window(start="00:30", end="01:30"), runs, None, schedules), [])

    def test_failures_are_never_silenced(self):
        self.assertEqual(self.codes(window(), history(1, 0)), ["JOB_FAILED"])

    def test_windows_can_be_limited_to_other_jobs(self):
        runs = steady(600, last=1700)
        self.assertEqual(self.codes(window(jobs=["Index*"]), runs), ["JOB_OVERRUN"])


class SkipArgumentTest(unittest.TestCase):
    def test_the_checks_accept_a_skip_callback(self):
        everything = lambda moment: True
        self.assertEqual(check_overruns(job(), steady(600, last=1700), Thresholds(), NOW, everything), [])
        self.assertEqual(check_running(job(), steady(600), RunningJob("NIGHTLY", datetime(2024, 5, 2, 7), 1), Thresholds(), NOW, everything), [])
        self.assertEqual(check_missed(job(), [run(31, 60)], None, [schedule(start_time=3600)], Thresholds(), NOW, None, everything), [])
