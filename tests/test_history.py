import unittest
from datetime import date

from agent_job_monitor.analysis import INFO, analyse, check_history
from agent_job_monitor.config import Config, Thresholds
from agent_job_monitor.model import RunningJob

from .helpers import NOW, history, job, server
from .test_schedule_times import schedule

SCHEDULED = [schedule()]


class CheckHistoryTest(unittest.TestCase):
    th = Thresholds()

    def test_enough_successful_runs(self):
        self.assertEqual(check_history(job(), history(*[1] * 6), None, SCHEDULED, self.th), [])

    def test_too_few_successful_runs(self):
        (f,) = check_history(job(), history(1, 0, 1, 0, 1), None, SCHEDULED, self.th)
        self.assertEqual((f.code, f.severity), ("NO_BASELINE", INFO))
        self.assertEqual(f.detail, {"successful_runs": 3, "needed": 5})
        self.assertIn("only 3 successful run(s) in the history, at least 5 are needed", f.message)

    def test_only_failures_count_as_no_baseline(self):
        (f,) = check_history(job(), history(0, 0, 0, 0, 0, 0), None, SCHEDULED, self.th)
        self.assertEqual(f.detail["successful_runs"], 0)

    def test_a_scheduled_job_without_any_history(self):
        (f,) = check_history(job(), [], None, SCHEDULED, self.th)
        self.assertEqual(f.code, "NO_HISTORY")

    def test_an_on_demand_job_is_not_expected_to_have_a_rhythm(self):
        self.assertEqual(check_history(job(), [], None, [], self.th), [])
        self.assertEqual(check_history(job(), history(1, 1), None, [], self.th), [])

    def test_a_disabled_schedule_does_not_count(self):
        s = schedule()
        s.enabled = False
        self.assertEqual(check_history(job(), [], None, [s], self.th), [])

    def test_a_job_that_is_running_for_the_first_time_has_history_in_the_making(self):
        self.assertEqual(check_history(job(), [], RunningJob("NIGHTLY", NOW, 1), SCHEDULED, self.th), [])

    def test_info_findings_do_not_change_the_counts(self):
        future = schedule(start_date=date(2030, 1, 1))
        report = analyse(server(), [job()], {"NIGHTLY": history(1, 1)}, Config(), None, {"NIGHTLY": [future]})
        self.assertEqual([f.code for f in report.findings], ["NO_BASELINE"])
        self.assertEqual(report.counts(), {"jobs": 1, "critical": 0, "warning": 0, "ok": 1})
