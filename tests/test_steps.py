import unittest
from datetime import timedelta

from agent_job_monitor.analysis import INFO, WARNING, analyse, check_steps
from agent_job_monitor.config import Config, Thresholds
from agent_job_monitor.model import FAILED

from .helpers import NOW, job, run, server, step


def with_steps(hours_ago, durations, status=1):
    r = run(hours_ago, sum(durations), status)
    r.steps = [step(n, "Step %d" % n, duration=d) for n, d in enumerate(durations, 1)]
    return r


def usual(count=10):
    return [with_steps((count - n) * 24 + 2, [100, 600, 60]) for n in range(count)]


class CheckStepsTest(unittest.TestCase):
    th = Thresholds()

    def test_normal_steps_are_fine(self):
        self.assertEqual(check_steps(job(), usual() + [with_steps(1, [110, 640, 62])], self.th, NOW), [])

    def test_a_slow_step_is_reported_with_its_position_and_ratio(self):
        (f,) = check_steps(job(), usual() + [with_steps(1, [100, 1800, 60])], self.th, NOW)
        self.assertEqual((f.code, f.severity), ("STEP_OVERRUN", WARNING))
        self.assertEqual((f.detail["step_id"], f.detail["step_name"], f.detail["ratio"]), (2, "Step 2", 3.0))
        self.assertIn("step 2 'Step 2' of the run that started at 2024-05-02 07:00 took 30m 00s, 3.0 times its median 10m 00s", f.message)

    def test_short_steps_need_a_minimum_absolute_difference(self):
        self.assertEqual(check_steps(job(), usual() + [with_steps(1, [100, 600, 150])], self.th, NOW), [])  # 2.5x of 60 s but only 90 s longer

    def test_each_step_has_its_own_baseline(self):
        (f,) = check_steps(job(), usual() + [with_steps(1, [450, 600, 60])], self.th, NOW)
        self.assertEqual(f.detail["step_id"], 1)

    def test_only_the_worst_step_is_reported(self):
        (f,) = check_steps(job(), usual() + [with_steps(1, [450, 1800, 60])], self.th, NOW)
        self.assertEqual(f.detail["step_id"], 1)  # 4.5 times its median beats 3.0 times

    def test_not_enough_history(self):
        self.assertEqual(check_steps(job(), usual(3) + [with_steps(1, [100, 1800, 60])], self.th, NOW), [])

    def test_failed_steps_and_failed_runs_are_not_compared(self):
        bad = with_steps(1, [100, 5000, 60], status=FAILED)
        self.assertEqual(check_steps(job(), usual() + [bad], self.th, NOW), [])

    def test_runs_outside_the_window_are_ignored(self):
        self.assertEqual(check_steps(job(), usual() + [with_steps(40, [100, 1800, 60])], self.th, NOW), [])


class AnalyseStepsTest(unittest.TestCase):
    def test_the_step_that_explains_a_job_overrun_is_informational(self):
        runs = usual() + [with_steps(1, [100, 2000, 60])]
        report = analyse(server(), [job()], {"NIGHTLY": runs}, Config())
        codes = {f.code: f for f in report.findings}
        self.assertEqual(set(codes), {"JOB_OVERRUN", "STEP_OVERRUN"})
        self.assertEqual(codes["STEP_OVERRUN"].severity, INFO)
        self.assertTrue(codes["STEP_OVERRUN"].message.endswith("this is what made the job overrun"))

    def test_a_slow_step_without_a_job_overrun_stays_a_warning(self):
        runs = usual() + [with_steps(1, [100, 1300, 60])]
        report = analyse(server(), [job()], {"NIGHTLY": runs}, Config())
        self.assertEqual([(f.code, str(f.severity)) for f in report.findings], [("STEP_OVERRUN", "warning")])
        self.assertEqual(report.counts()["warning"], 1)

    def test_info_findings_do_not_make_a_job_unhealthy(self):
        runs = usual() + [with_steps(1, [100, 2000, 60])]
        report = analyse(server(), [job()], {"NIGHTLY": runs}, Config())
        self.assertEqual(report.counts(), {"jobs": 1, "critical": 0, "warning": 1, "ok": 0})
