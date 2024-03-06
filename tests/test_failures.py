import unittest

from agent_job_monitor.analysis import CRITICAL, WARNING, analyse, check_failures, consecutive_failures
from agent_job_monitor.config import Config, Thresholds
from agent_job_monitor.model import CANCELED, FAILED, SUCCEEDED

from .helpers import history, job, run, server


class ConsecutiveFailuresTest(unittest.TestCase):
    def test_counts_from_the_newest_run(self):
        self.assertEqual(consecutive_failures(history(1, 0, 1, 0, 0)), 2)

    def test_a_success_last_means_none(self):
        self.assertEqual(consecutive_failures(history(0, 0, 1)), 0)

    def test_all_failed(self):
        self.assertEqual(consecutive_failures(history(0, 0, 0, 0)), 4)

    def test_no_runs(self):
        self.assertEqual(consecutive_failures([]), 0)

    def test_a_canceled_run_ends_the_streak(self):
        runs = history(0, 0, 1)
        runs[-1].status = CANCELED
        self.assertEqual(consecutive_failures(runs), 0)


class CheckFailuresTest(unittest.TestCase):
    th = Thresholds()

    def test_a_job_whose_last_run_succeeded_is_fine(self):
        self.assertEqual(check_failures(job(), history(0, 1), self.th), [])

    def test_a_job_without_history_has_no_failure(self):
        self.assertEqual(check_failures(job(), [], self.th), [])

    def test_first_failure_is_a_warning(self):
        (f,) = check_failures(job(), history(1, 1, 0), self.th)
        self.assertEqual((f.code, f.severity), ("JOB_FAILED", WARNING))
        self.assertEqual(f.detail["consecutive_failures"], 1)
        self.assertIn("1 consecutive failure(s), the last started at 2024-05-01 13:00", f.message)

    def test_repeated_failures_are_critical(self):
        (f,) = check_failures(job(), history(1, 0, 0, 0), self.th)
        self.assertEqual(f.severity, CRITICAL)
        self.assertEqual(f.detail["consecutive_failures"], 3)

    def test_the_critical_count_is_configurable(self):
        (f,) = check_failures(job(), history(1, 0, 0), Thresholds(critical_failures=2))
        self.assertEqual(f.severity, CRITICAL)


class AnalyseTest(unittest.TestCase):
    def test_disabled_jobs_are_not_checked(self):
        jobs = [job("Off", enabled=False, job_id="OFF"), job("On", job_id="ON")]
        runs = {"OFF": history(0, 0, 0), "ON": history(1, 1)}
        report = analyse(server(), jobs, runs, Config())
        self.assertEqual(report.checked, ["On"])
        self.assertEqual(report.findings, [])
        self.assertEqual(report.counts(), {"jobs": 1, "critical": 0, "warning": 0, "ok": 1})

    def test_findings_are_sorted_worst_first(self):
        jobs = [job("B", job_id="B"), job("A", job_id="A")]
        runs = {"B": history(1, 0, 0, 0), "A": history(1, 0)}
        report = analyse(server(), jobs, runs, Config())
        self.assertEqual([(f.job, str(f.severity)) for f in report.findings], [("B", "critical"), ("A", "warning")])
        self.assertEqual(report.counts(), {"jobs": 2, "critical": 1, "warning": 1, "ok": 0})
