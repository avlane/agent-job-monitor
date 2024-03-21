import unittest

from agent_job_monitor.analysis import check_failures, failed_step, shorten
from agent_job_monitor.config import Thresholds
from agent_job_monitor.model import FAILED

from .helpers import job, run, step


class FailedStepTest(unittest.TestCase):
    def test_first_failed_step(self):
        r = run(1, status=FAILED, steps=[step(1), step(2, "Load", FAILED, message="deadlock"), step(3, "Never", FAILED)])
        self.assertEqual(failed_step(r).name, "Load")

    def test_none_when_no_step_failed(self):
        self.assertIsNone(failed_step(run(1, status=FAILED, steps=[step(1)])))
        self.assertIsNone(failed_step(run(1, status=FAILED)))

    def test_finding_names_the_step_and_message(self):
        r = run(1, status=FAILED, steps=[step(1), step(2, "Load facts", FAILED, message="Error 1205\n  deadlock victim", msg_id=1205, severity=13)])
        (f,) = check_failures(job(), [r], Thresholds())
        self.assertIn("step 2 'Load facts' failed: Error 1205 deadlock victim", f.message)
        self.assertEqual((f.detail["step_id"], f.detail["sql_message_id"], f.detail["sql_severity"]), (2, 1205, 13))

    def test_a_failure_outside_any_step_has_no_step_detail(self):
        (f,) = check_failures(job(), [run(1, status=FAILED)], Thresholds())
        self.assertNotIn("step", f.message)
        self.assertNotIn("step_id", f.detail)


class ShortenTest(unittest.TestCase):
    def test_whitespace_is_collapsed(self):
        self.assertEqual(shorten("a\n b\t\tc"), "a b c")

    def test_long_text_is_cut(self):
        text = shorten("word " * 100, 40)
        self.assertEqual(len(text), 40)
        self.assertTrue(text.endswith("..."))

    def test_empty(self):
        self.assertEqual(shorten(None), "")
