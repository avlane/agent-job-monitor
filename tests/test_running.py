import unittest
from datetime import timedelta

from agent_job_monitor.analysis import CRITICAL, WARNING, analyse, check_running
from agent_job_monitor.config import Config, Thresholds
from agent_job_monitor.model import RunningJob
from agent_job_monitor.queries import fetch_running

from .fakes import connection_from_fixture
from .helpers import NOW, job, run, server
from .test_overruns import steady


def running_since(hours):
    return RunningJob("NIGHTLY", NOW - timedelta(hours=hours), 2, NOW - timedelta(minutes=30))


class CheckRunningTest(unittest.TestCase):
    th = Thresholds()

    def test_a_job_that_is_not_running_has_no_finding(self):
        self.assertEqual(check_running(job(), steady(600), None, self.th, NOW), [])

    def test_running_for_a_normal_time_is_fine(self):
        self.assertEqual(check_running(job(), steady(600), running_since(0.25), self.th, NOW), [])

    def test_running_much_longer_than_usual(self):
        (f,) = check_running(job(), steady(600), running_since(0.5), self.th, NOW)
        self.assertEqual((f.code, f.severity), ("JOB_RUNNING_LONG", WARNING))
        self.assertEqual((f.detail["elapsed_seconds"], f.detail["ratio"], f.detail["last_step_id"]), (1800, 3.0, 2))
        self.assertIn("running since 2024-05-02 07:30 (30m 00s), 3.0 times the median 10m 00s of the previous 11 runs (limit 20m 00s)", f.message)

    def test_hours_longer_is_critical(self):
        (f,) = check_running(job(), steady(600), running_since(3), self.th, NOW)
        self.assertEqual(f.severity, CRITICAL)

    def test_without_a_baseline_nothing_is_said(self):
        self.assertEqual(check_running(job(), steady(600, count=3), running_since(5), self.th, NOW), [])

    def test_failed_runs_do_not_count_towards_the_baseline(self):
        runs = steady(600) + [run(1 + n / 10, 30000, status=0) for n in range(3)]
        (f,) = check_running(job(), runs, running_since(0.5), self.th, NOW)
        self.assertEqual(f.detail["median_seconds"], 600.0)

    def test_analyse_passes_the_running_jobs_on(self):
        report = analyse(server(), [job()], {"NIGHTLY": steady(600)}, Config(), {"NIGHTLY": running_since(0.5)})
        self.assertEqual([f.code for f in report.findings], ["JOB_RUNNING_LONG"])


class FetchRunningTest(unittest.TestCase):
    def test_problems_fixture_has_one_running_job(self):
        running = fetch_running(connection_from_fixture("problems"))
        (job_id, entry), = running.items()
        self.assertEqual(job_id, "0A1B2C3D-0000-4000-8000-000000000003")
        self.assertEqual(entry.start.isoformat(), "2024-05-02T03:30:00")
        self.assertEqual(entry.last_step_id, 2)

    def test_healthy_fixture_has_none(self):
        self.assertEqual(fetch_running(connection_from_fixture("healthy")), {})

    def test_the_command_line_reports_it(self):
        import io

        from agent_job_monitor.cli import main

        out = io.StringIO()
        main(["--server", "X", "--job", "Index*"], connect=lambda a: connection_from_fixture("problems"), stdout=out)
        self.assertIn("[WARNING] Index maintenance: JOB_RUNNING_LONG - running since 2024-05-02 03:30 (4h 30m 00s)", out.getvalue())
