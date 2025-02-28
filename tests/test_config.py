import os
import tempfile
import unittest

from agent_job_monitor.config import Config, ConfigError, Thresholds, load_config, parse_config


class ParseConfigTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(parse_config({}).thresholds, Thresholds())

    def test_overrides(self):
        th = parse_config({"thresholds": {"critical_failures": 5, "overrun_factor": 3, "lookback_hours": 6.5}}).thresholds
        self.assertEqual((th.critical_failures, th.overrun_factor, th.lookback_hours), (5, 3, 6.5))
        self.assertEqual(th.baseline_runs, 20)

    def test_unknown_keys(self):
        for bad in ({"threshold": {}}, {"thresholds": {"overrun": 2}}):
            with self.assertRaises(ConfigError):
                parse_config(bad)

    def test_values_must_be_positive_numbers_of_the_right_kind(self):
        for bad in ({"critical_failures": 0}, {"critical_failures": 2.5}, {"overrun_factor": -1},
                    {"overrun_factor": "2"}, {"min_runs": True}):
            with self.assertRaises(ConfigError, msg=bad):
                parse_config({"thresholds": bad})

    def test_thresholds_must_be_a_table(self):
        with self.assertRaises(ConfigError):
            parse_config({"thresholds": [1]})


class LoadConfigTest(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "monitor.toml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_load(self):
        cfg = load_config(self.write("[thresholds]\nmin_runs = 8\n"))
        self.assertEqual(cfg.thresholds.min_runs, 8)

    def test_invalid_toml(self):
        with self.assertRaises(ConfigError):
            load_config(self.write("[thresholds"))

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config("/nonexistent/monitor.toml")

    def test_default_object(self):
        self.assertEqual(Config().thresholds.critical_overrun_factor, 4.0)


class PerJobThresholdsTest(unittest.TestCase):
    def test_defaults_for_unlisted_jobs(self):
        cfg = parse_config({"thresholds": {"critical_failures": 4}, "jobs": {"ETL load": {"critical_failures": 1}}})
        self.assertEqual(cfg.thresholds_for("Nightly").critical_failures, 4)

    def test_a_job_table_overrides_only_what_it_lists(self):
        cfg = parse_config({"thresholds": {"overrun_factor": 3}, "jobs": {"ETL load": {"critical_failures": 1}}})
        th = cfg.thresholds_for("etl LOAD")
        self.assertEqual((th.critical_failures, th.overrun_factor), (1, 3))

    def test_patterns_and_the_exact_name_wins(self):
        cfg = parse_config({"jobs": {"Backup *": {"min_runs": 3}, "Backup log": {"min_runs": 9}}})
        self.assertEqual(cfg.thresholds_for("Backup full").min_runs, 3)
        self.assertEqual(cfg.thresholds_for("backup log").min_runs, 9)
        self.assertEqual(cfg.thresholds_for("Other").min_runs, 5)

    def test_exclusions(self):
        from .helpers import job

        cfg = parse_config({"exclude": {"jobs": ["Replication*", "syspolicy_*"]}})
        self.assertTrue(cfg.is_excluded(job("REPLICATION agent")))
        self.assertTrue(cfg.is_excluded(job("syspolicy_purge_history")))
        self.assertFalse(cfg.is_excluded(job("Nightly")))

    def test_errors_name_the_table(self):
        with self.assertRaises(ConfigError) as ctx:
            parse_config({"jobs": {"ETL load": {"critical_failure": 1}}})
        self.assertIn("[jobs.ETL load]: unknown key(s): critical_failure", str(ctx.exception))
        for bad in ({"jobs": []}, {"jobs": {"X": []}}, {"exclude": []}, {"exclude": {"jobs": "X"}},
                    {"exclude": {"jobz": []}}, {"jobs": {"X": {"min_runs": 0}}}):
            with self.assertRaises(ConfigError):
                parse_config(bad)
