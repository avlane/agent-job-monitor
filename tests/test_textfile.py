import io
import os
import tempfile
import unittest
from unittest import mock

from agent_job_monitor.cli import main
from agent_job_monitor.textfile import write_atomically

from .fakes import connection_from_fixture


class WriteAtomicallyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "agent_jobs.prom")

    def test_writes_the_file(self):
        write_atomically(self.path, "a 1\n")
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "a 1\n")

    def test_replaces_an_existing_file_and_leaves_no_temporary_file(self):
        write_atomically(self.path, "old\n")
        write_atomically(self.path, "new\n")
        self.assertEqual(os.listdir(self.tmp.name), ["agent_jobs.prom"])
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "new\n")

    def test_the_file_is_world_readable(self):
        write_atomically(self.path, "a 1\n")
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o644)

    def test_a_failure_leaves_the_old_file_and_no_temporary_file(self):
        write_atomically(self.path, "old\n")
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                write_atomically(self.path, "new\n")
        self.assertEqual(os.listdir(self.tmp.name), ["agent_jobs.prom"])
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "old\n")

    def test_missing_directory(self):
        with self.assertRaises(OSError):
            write_atomically(os.path.join(self.tmp.name, "nope", "x.prom"), "a 1\n")


class TextfileOptionTest(unittest.TestCase):
    def test_metrics_are_written_next_to_the_normal_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "jobs.prom")
            out = io.StringIO()
            code = main(["--server", "SQLPROD01", "--textfile", path], connect=lambda a: connection_from_fixture("problems"),
                        stdout=out)
            self.assertEqual(code, 2)
            self.assertIn("agent-job-monitor report for SQLPROD01", out.getvalue())
            with open(path, encoding="utf-8") as fh:
                self.assertIn('agent_job_consecutive_failures{server="SQLPROD01",job="ETL load"} 3', fh.read())

    def test_unwritable_path_is_an_error(self):
        code = main(["--server", "SQLPROD01", "--textfile", "/nonexistent/dir/jobs.prom"],
                    connect=lambda a: connection_from_fixture("healthy"), stdout=io.StringIO())
        self.assertEqual(code, 3)
