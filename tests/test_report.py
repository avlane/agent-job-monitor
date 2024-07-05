import json
import unittest

from agent_job_monitor.analysis import analyse
from agent_job_monitor.config import Config
from agent_job_monitor.report import render, render_text

from .helpers import history, job, server
from .test_overruns import steady


def sample_report():
    jobs = [job("Nightly", job_id="N"), job("Broken", job_id="B"), job("Fine", job_id="F")]
    runs = {"N": steady(600, last=1700), "B": history(1, 0, 0, 0), "F": history(1, 1)}
    return analyse(server(), jobs, runs, Config())


class TextReportTest(unittest.TestCase):
    def setUp(self):
        self.text = render_text(sample_report())

    def test_header_and_summary(self):
        self.assertTrue(self.text.startswith("agent-job-monitor report for SQLPROD01 at 2024-05-02 08:00:00\n"))
        self.assertIn("3 job(s) checked: 1 ok, 1 with warnings, 1 critical", self.text)

    def test_findings_worst_first(self):
        lines = [l for l in self.text.splitlines() if l.startswith("[")]
        self.assertTrue(lines[0].startswith("[CRITICAL] Broken: JOB_FAILED - 3 consecutive failure(s)"))
        self.assertTrue(lines[1].startswith("[WARNING] Nightly: JOB_OVERRUN"))

    def test_clean_report(self):
        report = analyse(server(), [job("Fine", job_id="F")], {"F": history(1, 1)}, Config())
        self.assertIn("No problems found.", render_text(report))

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            render(sample_report(), "xml")


class JsonReportTest(unittest.TestCase):
    def test_structure(self):
        doc = json.loads(render(sample_report(), "json"))
        self.assertEqual(doc["server"], "SQLPROD01")
        self.assertEqual(doc["server_time"], "2024-05-02T08:00:00")
        self.assertEqual(doc["summary"], {"jobs": 3, "critical": 1, "warning": 1, "ok": 1})
        self.assertEqual([f["code"] for f in doc["findings"]], ["JOB_FAILED", "JOB_OVERRUN"])

    def test_finding_fields(self):
        doc = json.loads(render(sample_report(), "json"))
        first = doc["findings"][0]
        self.assertEqual(set(first), {"job", "code", "severity", "message", "detail"})
        self.assertEqual((first["job"], first["severity"]), ("Broken", "critical"))
        self.assertEqual(first["detail"]["consecutive_failures"], 3)

    def test_no_findings(self):
        report = analyse(server(), [job("Fine", job_id="F")], {"F": history(1, 1)}, Config())
        self.assertEqual(json.loads(render(report, "json"))["findings"], [])
