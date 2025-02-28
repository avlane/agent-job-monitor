import os
import unittest

from agent_job_monitor.config import load_config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")


class ExampleConfigTest(unittest.TestCase):
    def test_the_example_config_loads(self):
        cfg = load_config(os.path.join(EXAMPLES, "monitor.toml"))
        self.assertEqual(cfg.thresholds_for("ETL load").critical_failures, 1)
        self.assertEqual(cfg.thresholds_for("Index maintenance weekly").overrun_factor, 3.0)
        self.assertEqual(cfg.thresholds_for("Other").critical_failures, 3)
        self.assertEqual(cfg.exclude_jobs, ["syspolicy_purge_history", "Replication*"])
