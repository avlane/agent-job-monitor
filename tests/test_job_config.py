import unittest


class PerJobConfigInAnalysisTest(unittest.TestCase):
    def test_a_stricter_job_goes_critical_earlier(self):
        from agent_job_monitor.analysis import analyse
        from agent_job_monitor.config import parse_config

        from .helpers import history, job, server

        jobs = [job("Strict", job_id="S"), job("Lenient", job_id="L")]
        runs = {"S": history(1, 0), "L": history(1, 0)}
        cfg = parse_config({"jobs": {"Strict": {"critical_failures": 1}}})
        severities = {f.job: str(f.severity) for f in analyse(server(), jobs, runs, cfg).findings}
        self.assertEqual(severities, {"Strict": "critical", "Lenient": "warning"})

    def test_excluded_jobs_are_not_checked_at_all(self):
        from agent_job_monitor.analysis import analyse
        from agent_job_monitor.config import parse_config

        from .helpers import history, job, server

        jobs = [job("syspolicy_purge_history", job_id="P"), job("Nightly", job_id="N")]
        runs = {"P": history(0, 0, 0), "N": history(1, 1)}
        report = analyse(server(), jobs, runs, parse_config({"exclude": {"jobs": ["syspolicy_*"]}}))
        self.assertEqual(report.checked, ["Nightly"])
        self.assertEqual(report.findings, [])
        self.assertNotIn("syspolicy_purge_history", report.summaries)
