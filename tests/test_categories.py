import unittest

from agent_job_monitor.analysis import analyse
from agent_job_monitor.config import ConfigError, parse_config
from agent_job_monitor.model import Job

from .helpers import history, server


class ExcludeCategoriesTest(unittest.TestCase):
    cfg = parse_config({"exclude": {"categories": ["REPL-*", "Report Server"], "jobs": ["syspolicy_*"]}})

    def test_categories_are_matched_by_pattern_and_ignore_case(self):
        self.assertTrue(self.cfg.is_excluded(Job("1", "Distribution clean up", True, "REPL-Distribution")))
        self.assertTrue(self.cfg.is_excluded(Job("2", "Subscriptions", True, "report server")))
        self.assertFalse(self.cfg.is_excluded(Job("3", "Nightly", True, "Database Maintenance")))

    def test_names_still_work_next_to_categories(self):
        self.assertTrue(self.cfg.is_excluded(Job("4", "syspolicy_purge_history", True, "")))

    def test_jobs_without_a_category(self):
        self.assertFalse(self.cfg.is_excluded(Job("5", "Plain", True)))

    def test_excluded_categories_are_not_checked(self):
        jobs = [Job("A", "Replication agent", True, "REPL-LogReader"), Job("B", "Nightly", True, "Database Maintenance")]
        report = analyse(server(), jobs, {"A": history(0, 0, 0), "B": history(1, 1)}, self.cfg)
        self.assertEqual(report.checked, ["Nightly"])
        self.assertEqual([f.job for f in report.findings if f.severity != "info"], [])

    def test_the_exclude_table_is_validated(self):
        for bad in ({"exclude": {"categories": "REPL-*"}}, {"exclude": {"category": []}}):
            with self.assertRaises(ConfigError):
                parse_config(bad)
