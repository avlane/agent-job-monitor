import unittest
from datetime import date, datetime

from agent_job_monitor.msdbtime import decode_date, decode_seconds_of_day
from agent_job_monitor.queries import fetch_schedules

from .fakes import connection_from_fixture


class DecodeTest(unittest.TestCase):
    def test_date(self):
        self.assertEqual(decode_date(20240502), date(2024, 5, 2))
        self.assertEqual(decode_date(99991231), date(9999, 12, 31))
        self.assertIsNone(decode_date(0))
        self.assertIsNone(decode_date(20241399))

    def test_seconds_of_day(self):
        self.assertEqual(decode_seconds_of_day(0), 0)
        self.assertEqual(decode_seconds_of_day(13045), 5445)
        self.assertEqual(decode_seconds_of_day(235959), 86399)
        self.assertEqual(decode_seconds_of_day(1500), 900)


class FetchSchedulesTest(unittest.TestCase):
    def setUp(self):
        self.schedules = fetch_schedules(connection_from_fixture("healthy"))

    def test_grouped_by_job(self):
        self.assertEqual(len(self.schedules), 5)
        (nightly,) = self.schedules["0A1B2C3D-0000-4000-8000-000000000001"]
        self.assertEqual(nightly.name, "Nightly backup schedule")
        self.assertTrue(nightly.enabled)

    def test_daily_schedule_fields(self):
        (s,) = self.schedules["0A1B2C3D-0000-4000-8000-000000000002"]
        self.assertEqual((s.freq_type, s.freq_interval, s.freq_subday_type), (4, 1, 1))
        self.assertEqual(s.active_start_seconds, 2 * 3600 + 30 * 60)
        self.assertEqual(s.active_end_seconds, 86399)
        self.assertEqual((s.active_start_date, s.active_end_date), (date(2023, 1, 1), date(9999, 12, 31)))

    def test_every_six_hours(self):
        (s,) = self.schedules["0A1B2C3D-0000-4000-8000-000000000004"]
        self.assertEqual((s.freq_subday_type, s.freq_subday_interval, s.active_start_seconds), (8, 6, 900))

    def test_next_run_is_none_when_not_computed(self):
        (s,) = self.schedules["0A1B2C3D-0000-4000-8000-000000000001"]
        self.assertIsNone(s.next_run)
