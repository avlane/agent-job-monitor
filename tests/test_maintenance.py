import unittest
from datetime import datetime

from agent_job_monitor.config import ConfigError, MaintenanceWindow, parse_config


def at(day, hour, minute=0):
    return datetime(2024, 5, day, hour, minute)  # 2024-05-01 is a Wednesday


class CoversTest(unittest.TestCase):
    def test_a_window_inside_one_day(self):
        w = MaintenanceWindow(2 * 3600, 4 * 3600)
        self.assertTrue(w.covers(at(2, 2)))
        self.assertTrue(w.covers(at(2, 3, 59)))
        self.assertFalse(w.covers(at(2, 4)))
        self.assertFalse(w.covers(at(2, 1, 59)))

    def test_an_overnight_window(self):
        w = MaintenanceWindow(22 * 3600, 2 * 3600)
        self.assertTrue(w.covers(at(2, 23)))
        self.assertTrue(w.covers(at(3, 1)))
        self.assertFalse(w.covers(at(3, 2)))
        self.assertFalse(w.covers(at(3, 21, 59)))

    def test_days_name_the_day_the_window_starts(self):
        saturday_night = MaintenanceWindow(22 * 3600, 2 * 3600, days=(5,))
        self.assertTrue(saturday_night.covers(at(4, 23)))   # Saturday 23:00
        self.assertTrue(saturday_night.covers(at(5, 1)))    # Sunday 01:00 belongs to Saturday's window
        self.assertFalse(saturday_night.covers(at(5, 23)))  # Sunday 23:00
        self.assertFalse(saturday_night.covers(at(4, 1)))   # Saturday 01:00 belongs to Friday's

    def test_job_patterns(self):
        w = MaintenanceWindow(0, 3600, jobs=("Index*", "Backup log"))
        self.assertTrue(w.applies_to("index maintenance"))
        self.assertTrue(w.applies_to("BACKUP LOG"))
        self.assertFalse(w.applies_to("ETL load"))
        self.assertTrue(MaintenanceWindow(0, 1).applies_to("anything"))


class ParseTest(unittest.TestCase):
    def test_a_full_window(self):
        cfg = parse_config({"maintenance": [{"name": "weekend", "start": "22:00", "end": "02:30", "days": ["sat"],
                                             "jobs": ["Index*"], "suppress": ["overrun", "running"]}]})
        (w,) = cfg.maintenance
        self.assertEqual((w.start, w.end, w.days, w.jobs, w.suppress, w.name),
                         (79200, 9000, (5,), ("Index*",), ("overrun", "running"), "weekend"))

    def test_defaults(self):
        (w,) = parse_config({"maintenance": [{"start": "01:00", "end": "05:00"}]}).maintenance
        self.assertEqual((w.days, w.jobs, w.suppress), ((), (), ("overrun", "steps", "running", "missed")))

    def test_midnight_may_be_written_as_24_00(self):
        (w,) = parse_config({"maintenance": [{"start": "23:00", "end": "24:00"}]}).maintenance
        self.assertEqual(w.end, 86400)

    def test_in_maintenance(self):
        cfg = parse_config({"maintenance": [{"start": "02:00", "end": "04:00", "jobs": ["Index*"], "suppress": ["overrun"]}]})
        self.assertTrue(cfg.in_maintenance("Index maintenance", at(2, 3), "overrun"))
        self.assertFalse(cfg.in_maintenance("Index maintenance", at(2, 3), "missed"))
        self.assertFalse(cfg.in_maintenance("Nightly", at(2, 3), "overrun"))
        self.assertFalse(cfg.in_maintenance("Index maintenance", at(2, 5), "overrun"))

    def test_errors(self):
        bad = [
            {"maintenance": {"start": "01:00", "end": "02:00"}},
            {"maintenance": ["01:00"]},
            {"maintenance": [{"start": "01:00"}]},
            {"maintenance": [{"start": "1am", "end": "02:00"}]},
            {"maintenance": [{"start": "25:00", "end": "02:00"}]},
            {"maintenance": [{"start": "01:00", "end": "02:00", "days": ["someday"]}]},
            {"maintenance": [{"start": "01:00", "end": "02:00", "suppress": ["failures"]}]},
            {"maintenance": [{"start": "01:00", "end": "02:00", "suppress": []}]},
            {"maintenance": [{"start": "01:00", "end": "02:00", "color": "red"}]},
        ]
        for data in bad:
            with self.assertRaises(ConfigError, msg=data):
                parse_config(data)
