import unittest

from agent_job_monitor.baseline import compute_baseline, baseline_before, percentile

from .helpers import history, run


class PercentileTest(unittest.TestCase):
    def test_interpolation(self):
        values = [10, 20, 30, 40, 50]
        self.assertEqual(percentile(values, 0), 10)
        self.assertEqual(percentile(values, 50), 30)
        self.assertEqual(percentile(values, 100), 50)
        self.assertEqual(percentile(values, 25), 20)
        self.assertAlmostEqual(percentile(values, 90), 46.0)

    def test_single_value(self):
        self.assertEqual(percentile([7], 95), 7.0)

    def test_empty(self):
        with self.assertRaises(ValueError):
            percentile([], 50)


class ComputeBaselineTest(unittest.TestCase):
    def test_statistics(self):
        b = compute_baseline([100, 110, 90, 105, 95, 400])
        self.assertEqual(b.runs, 6)
        self.assertEqual(b.median, 102.5)
        self.assertEqual((b.minimum, b.maximum), (90.0, 400.0))
        self.assertEqual(b.mad, 7.5)
        self.assertAlmostEqual(b.sigma, 7.5 * 1.4826)

    def test_the_median_ignores_an_outlier(self):
        self.assertEqual(compute_baseline([60, 61, 59, 60, 10000]).median, 60.0)

    def test_identical_durations_have_no_spread(self):
        b = compute_baseline([300] * 8)
        self.assertEqual((b.median, b.mad, b.p95), (300.0, 0.0, 300.0))

    def test_p95_is_near_the_top(self):
        b = compute_baseline(list(range(1, 101)))
        self.assertAlmostEqual(b.p95, 95.05)

    def test_empty(self):
        self.assertIsNone(compute_baseline([]))


class BaselineBeforeTest(unittest.TestCase):
    def test_only_earlier_successful_runs_count(self):
        runs = [run(50, 100), run(40, 5, status=0), run(30, 200), run(20, 999)]
        b = baseline_before(runs, 3, 20)
        self.assertEqual((b.runs, b.median), (2, 150.0))

    def test_only_the_newest_runs_up_to_the_count(self):
        runs = [run(60 - n, duration=100 + n) for n in range(10)] + [run(1, 500)]
        b = baseline_before(runs, 10, 3)
        self.assertEqual((b.runs, b.minimum, b.maximum), (3, 107.0, 109.0))

    def test_the_first_run_has_no_baseline(self):
        self.assertIsNone(baseline_before(history(1, 1), 0, 20))
