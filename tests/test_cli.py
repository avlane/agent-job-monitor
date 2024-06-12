import io
import os
import tempfile
import unittest

from agent_job_monitor.cli import main

from .fakes import FakeConnection, connection_from_fixture


def run(*argv, fixture="healthy", connect=None):
    out = io.StringIO()
    code = main(["--server", "SQLPROD01", *argv], connect=connect or (lambda a: connection_from_fixture(fixture)), stdout=out)
    return code, out.getvalue()


class CliTest(unittest.TestCase):
    def test_healthy_server_exits_zero(self):
        code, out = run()
        self.assertEqual(code, 0)
        self.assertIn("4 job(s) checked: 4 ok, 0 with warnings, 0 critical", out)
        self.assertIn("No problems found.", out)

    def test_critical_findings_exit_two(self):
        code, out = run(fixture="problems")
        self.assertEqual(code, 2)
        self.assertIn("[CRITICAL] ETL load: JOB_FAILED - 3 consecutive failure(s)", out)
        self.assertIn("step 3 'Load facts' failed: Executed as user: DOMAIN\\svc_agent. Transaction (Process ID 87) was deadlocked", out)

    def test_warnings_exit_one(self):
        code, out = run("--job", "Nightly*", fixture="problems")
        self.assertEqual(code, 1)
        self.assertIn("[WARNING] Nightly backup: JOB_OVERRUN", out)

    def test_job_filter(self):
        code, out = run("-j", "purge*", "-j", "index maintenance")
        self.assertIn("2 job(s) checked", out)

    def test_filter_without_a_match(self):
        self.assertEqual(run("--job", "nothing*")[0], 3)

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "report.txt")
            code, out = run("-o", target)
            self.assertEqual((code, out), (0, ""))
            with open(target, encoding="utf-8") as fh:
                self.assertIn("agent-job-monitor report for SQLPROD01", fh.read())

    def test_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "monitor.toml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[thresholds]\ncritical_failures = 5\n")
            code, out = run("--config", path, "--job", "ETL*", fixture="problems")
        self.assertEqual(code, 1)
        self.assertIn("[WARNING] ETL load: JOB_FAILED", out)

    def test_bad_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "monitor.toml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[thresholds]\nbogus = 1\n")
            self.assertEqual(run("--config", path)[0], 3)

    def test_connection_failure(self):
        def boom(args):
            raise OSError("login timeout")

        self.assertEqual(run(connect=boom)[0], 3)

    def test_query_failure(self):
        self.assertEqual(run(connect=lambda a: FakeConnection({"server": {}}))[0], 3)

    def test_the_connection_is_closed(self):
        conn = connection_from_fixture("healthy")
        run(connect=lambda a: conn)
        self.assertTrue(conn.closed)

    def test_usage_errors_do_not_collide_with_finding_exit_codes(self):
        with self.assertRaises(SystemExit) as ctx:
            main([])
        self.assertEqual(ctx.exception.code, 3)

    def test_help_and_version(self):
        for flag in ("--help", "--version"):
            with self.assertRaises(SystemExit) as ctx:
                main([flag])
            self.assertEqual(ctx.exception.code, 0)
