import unittest

from agent_job_monitor.analysis import CRITICAL, WARNING, analyse, check_overruns, overrun_limit
from agent_job_monitor.baseline import compute_baseline
from agent_job_monitor.config import Config, Thresholds
from agent_job_monitor.msdbtime import format_duration

from .helpers import NOW, history, job, run, server


def steady(duration, count=10, last=None, last_hours_ago=1):
    """`count` runs of `duration` seconds, one a day, then a final run of `last` seconds."""
    runs = [run((count - n) * 24 + 2, duration) for n in range(count)]
    return runs + [run(last_hours_ago, last if last is not None else duration)]


class OverrunLimitTest(unittest.TestCase):
    th = Thresholds()

    def test_the_factor_dominates_for_a_steady_job(self):
        self.assertEqual(overrun_limit(compute_baseline([600] * 10), self.th), 1200.0)

    def test_a_noisy_job_gets_a_wider_limit(self):
        base = compute_baseline([300, 900, 600, 1200, 450, 700, 650, 560, 980, 640])
        self.assertGreater(overrun_limit(base, self.th), 2 * base.median)


class CheckOverrunsTest(unittest.TestCase):
    th = Thresholds()

    def check(self, runs, th=None):
        return check_overruns(job(), runs, th or self.th, NOW)

    def test_a_normal_run_is_fine(self):
        self.assertEqual(self.check(steady(600, last=700)), [])

    def test_a_run_over_twice_the_median_is_an_overrun(self):
        (f,) = self.check(steady(600, last=1500))
        self.assertEqual((f.code, f.severity), ("JOB_OVERRUN", WARNING))
        self.assertEqual(f.detail["ratio"], 2.5)
        self.assertEqual(f.detail["median_seconds"], 600.0)
        self.assertEqual(f.detail["baseline_runs"], 10)
        self.assertIn("took 25m 00s, 2.5 times the median 10m 00s of the previous 10 runs (limit 20m 00s)", f.message)

    def test_a_huge_overrun_is_critical(self):
        (f,) = self.check(steady(600, last=3000))
        self.assertEqual(f.severity, CRITICAL)

    def test_small_jobs_are_not_flagged_for_a_few_seconds(self):
        self.assertEqual(self.check(steady(10, last=60)), [])  # 6 times the median but only 50 s longer

    def test_not_enough_history_means_no_check(self):
        self.assertEqual(self.check(steady(600, count=4, last=5000)), [])
        self.assertEqual(len(self.check(steady(600, count=5, last=5000))), 1)

    def test_failed_runs_do_not_enter_the_baseline_and_are_not_overruns(self):
        runs = steady(600, last=700)
        runs.insert(3, run(500, 5, status=0))
        self.assertEqual(self.check(runs), [])
        failed_long = steady(600) + [run(1, 9000, status=0)]
        self.assertEqual(self.check(failed_long), [])

    def test_runs_before_the_window_are_not_reported(self):
        runs = steady(600, last=3000, last_hours_ago=30)
        self.assertEqual(self.check(runs), [])
        self.assertEqual(len(self.check(runs, Thresholds(lookback_hours=48))), 1)

    def test_the_worst_run_in_the_window_is_reported_with_a_count(self):
        runs = steady(600) + [run(5, 1400), run(3, 3000), run(1, 1300)]
        (f,) = self.check(runs)
        self.assertEqual(f.detail["duration_seconds"], 3000)
        self.assertEqual(f.detail["overruns_in_window"], 3)

    def test_each_run_is_judged_against_the_runs_before_it(self):
        # a job that slowly became slower: the last run is long for the old baseline but the
        # baseline moves with it
        runs = [run(300 - n * 24, 600 + n * 40) for n in range(10)] + [run(1, 1100)]
        self.assertEqual(self.check(runs, Thresholds(baseline_runs=5)), [])

    def test_thresholds_are_configurable(self):
        runs = steady(600, last=1000)
        self.assertEqual(self.check(runs), [])
        self.assertEqual(len(self.check(runs, Thresholds(overrun_factor=1.5, overrun_mad_multiplier=1.0))), 1)


class FormatDurationTest(unittest.TestCase):
    def test_examples(self):
        self.assertEqual([format_duration(s) for s in (0, 45, 60, 1560, 3600, 3725, 93784)],
                         ["0s", "45s", "1m 00s", "26m 00s", "1h 00m 00s", "1h 02m 05s", "26h 03m 04s"])


class AnalyseIncludesOverrunsTest(unittest.TestCase):
    def test_findings_from_both_checks(self):
        runs = {"NIGHTLY": steady(600, last=1700)}
        report = analyse(server(), [job()], runs, Config())
        self.assertEqual([f.code for f in report.findings], ["JOB_OVERRUN"])
        self.assertEqual(report.counts()["warning"], 1)
