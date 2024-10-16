import io
import unittest
from datetime import datetime, timedelta

from agent_job_monitor.analysis import CRITICAL, INFO, WARNING, check_missed
from agent_job_monitor.cli import main
from agent_job_monitor.config import Thresholds
from agent_job_monitor.model import SUCCEEDED, JobRun, RunningJob

from .fakes import connection_from_fixture
from .helpers import NOW, job
from .test_schedule_times import schedule


def daily(hour=1, minute=0):
    return schedule(start_time=hour * 3600 + minute * 60)


def at(day, hour, minute=0, duration=600):
    return JobRun("NIGHTLY", datetime(2024, 5, day, hour, minute), duration, SUCCEEDED)


class CheckMissedTest(unittest.TestCase):
    th = Thresholds()

    def check(self, runs, schedules, running=None, agent_start=None, th=None, the_job=None):
        return check_missed(the_job or job(), runs, running, schedules, th or self.th, NOW, agent_start)

    def test_a_job_that_started_on_time_is_fine(self):
        runs = [JobRun("NIGHTLY", datetime(2024, 4, 30, 1), 600, SUCCEEDED), at(1, 1), at(2, 1)]
        self.assertEqual(self.check(runs, [daily(1)]), [])

    def test_a_missing_run_is_reported_with_its_time(self):
        (f,) = self.check([JobRun("NIGHTLY", datetime(2024, 4, 30, 1), 600, SUCCEEDED), at(1, 1)], [daily(1)])
        self.assertEqual((f.code, f.severity), ("SCHEDULE_MISSED", WARNING))
        self.assertEqual(f.detail["missed"], ["2024-05-02T01:00:00"])
        self.assertIn("1 scheduled run(s) did not start: 2024-05-02 01:00", f.message)

    def test_a_late_start_within_the_grace_period_counts(self):
        self.assertEqual(self.check([at(1, 1), at(2, 1, 5)], [daily(1)]), [])

    def test_a_start_later_than_the_grace_period_does_not(self):
        (f,) = self.check([at(1, 1), at(2, 1, 15)], [daily(1)])
        self.assertEqual(f.detail["missed"], ["2024-05-02T01:00:00"])

    def test_the_last_few_minutes_are_not_judged_yet(self):
        self.assertEqual(self.check([at(1, 7, 55)], [daily(7, 55)]), [])

    def test_many_misses_are_critical(self):
        hourly = schedule(subday_type=8, subday_interval=1, start_time=0)
        (f,) = self.check([at(1, 0, duration=60)], [hourly])
        self.assertEqual(f.severity, CRITICAL)
        self.assertEqual(len(f.detail["missed"]), 24)
        self.assertTrue(f.message.endswith(", ..."))

    def test_no_history_at_all_is_not_judged(self):
        self.assertEqual(self.check([], [daily(1)]), [])

    def test_disabled_schedules_and_jobs(self):
        s = daily(1)
        s.enabled = False
        self.assertEqual(self.check([at(1, 1)], [s]), [])
        self.assertEqual(self.check([at(1, 1)], [daily(1)], the_job=job(enabled=False)), [])

    def test_a_job_without_schedules_runs_on_demand(self):
        self.assertEqual(self.check([at(1, 1)], []), [])

    def test_a_run_in_progress_counts_as_started(self):
        running = RunningJob("NIGHTLY", datetime(2024, 5, 2, 1), 1)
        self.assertEqual(self.check([at(1, 1)], [daily(1)], running), [])

    def test_starts_before_the_agent_came_up_are_not_expected(self):
        self.assertEqual(self.check([at(1, 1)], [daily(1)], agent_start=datetime(2024, 5, 2, 3)), [])

    def test_a_start_skipped_because_the_previous_run_was_still_going_is_not_a_miss(self):
        runs = [at(1, 1), at(2, 0, duration=3 * 3600)]
        fs = self.check(runs, [daily(1)])
        self.assertEqual([(f.code, f.severity) for f in fs], [("SCHEDULE_SKIPPED", INFO)])
        self.assertEqual(fs[0].detail["skipped"], ["2024-05-02T01:00:00"])

    def test_history_older_than_the_oldest_known_run_is_not_judged(self):
        self.assertEqual(self.check([at(2, 6)], [daily(1)]), [])

    def test_the_grace_period_is_configurable(self):
        self.assertEqual(self.check([at(1, 1), at(2, 1, 15)], [daily(1)], th=Thresholds(grace_minutes=20)), [])


class FixtureTest(unittest.TestCase):
    def run_cli(self, fixture, *argv):
        out = io.StringIO()
        code = main(["--server", "X", *argv], connect=lambda a: connection_from_fixture(fixture), stdout=out)
        return code, out.getvalue()

    def test_healthy_server_misses_nothing(self):
        code, out = self.run_cli("healthy")
        self.assertEqual(code, 0)
        self.assertNotIn("SCHEDULE_MISSED", out)

    def test_the_job_that_stopped_running(self):
        code, out = self.run_cli("problems", "--job", "Purge*")
        self.assertEqual(code, 1)
        self.assertIn("[WARNING] Purge history: SCHEDULE_MISSED - 2 scheduled run(s) did not start: "
                      "2024-05-02 00:15, 2024-05-02 06:15", out)

    def test_a_disabled_job_is_not_checked(self):
        code, out = self.run_cli("problems", "--job", "Report*")
        self.assertEqual(code, 0)
        self.assertIn("0 job(s) checked", out)
