import unittest
from datetime import datetime, timedelta

from agent_job_monitor.analysis import AGENT, CRITICAL, analyse, check_agent
from agent_job_monitor.config import Config, Thresholds
from agent_job_monitor.model import SUCCEEDED, JobRun, RunningJob

from .helpers import NOW, history, job, server
from .test_schedule_times import schedule


def jobs_and_schedules(count=4, minute=40):
    jobs = [job("Job %d" % n, job_id="J%d" % n) for n in range(count)]
    schedules = {"J%d" % n: [schedule(start_time=7 * 3600 + minute * 60)] for n in range(count)}
    return jobs, schedules


def runs_before(hours_ago, count=4):
    return {"J%d" % n: [JobRun("J%d" % n, NOW - timedelta(hours=hours_ago), 60, SUCCEEDED)] for n in range(count)}


class CheckAgentTest(unittest.TestCase):
    th = Thresholds()

    def test_nothing_started_although_several_starts_were_due(self):
        jobs, schedules = jobs_and_schedules()
        (f,) = check_agent(jobs, runs_before(3), {}, schedules, self.th, NOW)
        self.assertEqual((f.job, f.code, f.severity), (AGENT, "AGENT_SILENT", CRITICAL))
        self.assertEqual(f.detail["due"], 4)
        self.assertIn("no job has started since 2024-05-02 05:00, although 4 scheduled start(s) were due in the last 30 minutes", f.message)

    def test_something_started_in_the_window_means_the_agent_is_alive(self):
        jobs, schedules = jobs_and_schedules()
        runs = runs_before(3)
        runs["J0"].append(JobRun("J0", NOW - timedelta(minutes=25), 60, SUCCEEDED))
        self.assertEqual(check_agent(jobs, runs, {}, schedules, self.th, NOW), [])

    def test_a_running_job_counts_as_a_start(self):
        jobs, schedules = jobs_and_schedules()
        running = {"J1": RunningJob("J1", NOW - timedelta(minutes=20), 1)}
        self.assertEqual(check_agent(jobs, runs_before(3), running, schedules, self.th, NOW), [])

    def test_too_few_due_starts_prove_nothing(self):
        jobs, schedules = jobs_and_schedules(count=2)
        self.assertEqual(check_agent(jobs, runs_before(3, 2), {}, schedules, self.th, NOW), [])

    def test_nothing_due_in_the_window(self):
        jobs, schedules = jobs_and_schedules(minute=5)  # due at 07:05, before the window
        self.assertEqual(check_agent(jobs, runs_before(3), {}, schedules, self.th, NOW), [])

    def test_an_agent_that_has_only_just_started_is_not_blamed(self):
        jobs, schedules = jobs_and_schedules()
        self.assertEqual(check_agent(jobs, runs_before(3), {}, schedules, self.th, NOW, NOW - timedelta(minutes=5)), [])

    def test_disabled_jobs_and_schedules_are_not_due(self):
        jobs, schedules = jobs_and_schedules()
        for j in jobs[:2]:
            j.enabled = False
        self.assertEqual(check_agent(jobs, runs_before(3), {}, schedules, self.th, NOW), [])

    def test_no_history_at_all(self):
        jobs, schedules = jobs_and_schedules()
        (f,) = check_agent(jobs, {}, {}, schedules, self.th, NOW)
        self.assertIn("since the start of the history", f.message)
        self.assertIsNone(f.detail["last_start"])


class AgentInReportsTest(unittest.TestCase):
    def test_a_silent_agent_makes_the_report_critical_without_miscounting_jobs(self):
        jobs, schedules = jobs_and_schedules()
        report = analyse(server(), jobs, runs_before(3), Config(), None, schedules)
        self.assertIn(AGENT, [f.job for f in report.findings])
        counts = report.counts()
        self.assertEqual(counts["jobs"], 4)
        self.assertEqual(counts["critical"], 1)
        self.assertGreaterEqual(counts["ok"], 0)
        self.assertEqual(counts["jobs"] - counts["ok"], counts["warning"] + counts["critical"] - 1)
