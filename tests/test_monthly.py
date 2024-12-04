import unittest
from datetime import date, datetime

from agent_job_monitor.schedules import expected_runs, relative_day, runs_on_day

from .test_schedule_times import schedule


class MonthlyTest(unittest.TestCase):
    def test_day_of_month(self):
        s = schedule(freq_type=16, interval=15)
        self.assertEqual([d for d in range(1, 32) if runs_on_day(s, date(2024, 5, d))], [15])

    def test_a_day_that_does_not_exist_in_the_month_does_not_run(self):
        s = schedule(freq_type=16, interval=31)
        self.assertTrue(runs_on_day(s, date(2024, 5, 31)))
        self.assertFalse(any(runs_on_day(s, date(2024, 6, d)) for d in range(1, 31)))

    def test_every_third_month(self):
        s = schedule(freq_type=16, interval=1, factor=3, start_date=date(2024, 1, 1))
        got = [m for m in range(1, 13) if runs_on_day(s, date(2024, m, 1))]
        self.assertEqual(got, [1, 4, 7, 10])

    def test_months_are_counted_from_the_start_month_across_years(self):
        s = schedule(freq_type=16, interval=10, factor=2, start_date=date(2023, 12, 1))
        self.assertTrue(runs_on_day(s, date(2024, 2, 10)))
        self.assertFalse(runs_on_day(s, date(2024, 1, 10)))
        self.assertTrue(runs_on_day(s, date(2025, 2, 10)))


class RelativeDayTest(unittest.TestCase):
    def test_first_monday(self):
        self.assertEqual(relative_day(2024, 5, 1, 2), date(2024, 5, 6))

    def test_second_tuesday_and_fourth_friday(self):
        self.assertEqual(relative_day(2024, 5, 2, 3), date(2024, 5, 14))
        self.assertEqual(relative_day(2024, 5, 8, 6), date(2024, 5, 24))

    def test_last_sunday_and_last_day(self):
        self.assertEqual(relative_day(2024, 5, 16, 1), date(2024, 5, 26))
        self.assertEqual(relative_day(2024, 5, 16, 8), date(2024, 5, 31))

    def test_weekdays_and_weekend_days(self):
        self.assertEqual(relative_day(2024, 6, 1, 9), date(2024, 6, 3))      # first weekday: June 1 is a Saturday
        self.assertEqual(relative_day(2024, 6, 16, 9), date(2024, 6, 28))    # last weekday
        self.assertEqual(relative_day(2024, 6, 1, 10), date(2024, 6, 1))     # first weekend day
        self.assertEqual(relative_day(2024, 6, 16, 10), date(2024, 6, 30))

    def test_an_unknown_position_gives_none(self):
        self.assertIsNone(relative_day(2024, 2, 99, 2))

    def test_the_schedule_uses_it(self):
        s = schedule(freq_type=32, interval=2, relative=1)  # first Monday of every month
        got = expected_runs(s, datetime(2024, 5, 1), datetime(2024, 7, 31, 23))
        self.assertEqual([t.date() for t in got], [date(2024, 5, 6), date(2024, 6, 3), date(2024, 7, 1)])

    def test_every_second_month_on_the_last_day(self):
        s = schedule(freq_type=32, interval=8, relative=16, factor=2, start_date=date(2024, 1, 1))
        got = expected_runs(s, datetime(2024, 1, 1), datetime(2024, 6, 30, 23))
        self.assertEqual([t.date() for t in got], [date(2024, 1, 31), date(2024, 3, 31), date(2024, 5, 31)])
