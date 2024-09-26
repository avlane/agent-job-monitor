import unittest
from datetime import date, datetime

from agent_job_monitor.model import Schedule
from agent_job_monitor.schedules import expected_runs, runs_on_day, sql_weekday_bit, times_of_day


def schedule(freq_type=4, interval=1, subday_type=1, subday_interval=0, start_time=3600, end_time=86399,
             start_date=date(2024, 1, 1), end_date=date(9999, 12, 31), factor=0, relative=0):
    return Schedule("J", 1, "s", True, freq_type, interval, subday_type, subday_interval, relative, factor,
                    start_date, end_date, start_time, end_time)


class WeekdayBitTest(unittest.TestCase):
    def test_sunday_is_one_and_saturday_is_sixty_four(self):
        self.assertEqual([sql_weekday_bit(date(2024, 5, d)) for d in range(5, 12)], [1, 2, 4, 8, 16, 32, 64])


class TimesOfDayTest(unittest.TestCase):
    def test_once_a_day(self):
        self.assertEqual(times_of_day(schedule(start_time=5400)), [5400])

    def test_every_n_hours_up_to_the_end_time(self):
        self.assertEqual(times_of_day(schedule(subday_type=8, subday_interval=6, start_time=900)),
                         [900, 22500, 44100, 65700])

    def test_every_n_minutes_inside_a_window(self):
        self.assertEqual(times_of_day(schedule(subday_type=4, subday_interval=30, start_time=8 * 3600, end_time=10 * 3600)),
                         [28800, 30600, 32400, 34200, 36000])

    def test_every_n_seconds(self):
        self.assertEqual(times_of_day(schedule(subday_type=2, subday_interval=20, start_time=0, end_time=60)), [0, 20, 40, 60])

    def test_a_zero_interval_falls_back_to_the_start_time(self):
        self.assertEqual(times_of_day(schedule(subday_type=4, subday_interval=0, start_time=100)), [100])


class RunsOnDayTest(unittest.TestCase):
    def test_daily(self):
        s = schedule()
        self.assertTrue(runs_on_day(s, date(2024, 5, 2)))

    def test_every_third_day_counts_from_the_start_date(self):
        s = schedule(interval=3, start_date=date(2024, 5, 1))
        self.assertEqual([d for d in range(1, 11) if runs_on_day(s, date(2024, 5, d))], [1, 4, 7, 10])

    def test_active_dates(self):
        s = schedule(start_date=date(2024, 5, 2), end_date=date(2024, 5, 4))
        self.assertEqual([d for d in range(1, 7) if runs_on_day(s, date(2024, 5, d))], [2, 3, 4])

    def test_once(self):
        s = schedule(freq_type=1, start_date=date(2024, 5, 3))
        self.assertEqual([d for d in range(1, 7) if runs_on_day(s, date(2024, 5, d))], [3])

    def test_weekly_on_selected_days(self):
        s = schedule(freq_type=8, interval=2 + 16)  # Monday and Thursday
        self.assertEqual([d for d in range(6, 13) if runs_on_day(s, date(2024, 5, d))], [6, 9])

    def test_weekly_with_a_recurrence_factor(self):
        s = schedule(freq_type=8, interval=2, factor=2, start_date=date(2024, 5, 6))  # every other Monday
        self.assertEqual([d for d in range(1, 32) if runs_on_day(s, date(2024, 5, d))], [6, 20])

    def test_other_frequencies_have_no_clock_days(self):
        self.assertFalse(runs_on_day(schedule(freq_type=64), date(2024, 5, 2)))
        self.assertFalse(runs_on_day(schedule(freq_type=128), date(2024, 5, 2)))


class ExpectedRunsTest(unittest.TestCase):
    def test_daily_runs_in_a_window(self):
        s = schedule(start_time=3600)
        self.assertEqual(expected_runs(s, datetime(2024, 5, 1, 12), datetime(2024, 5, 3, 12)),
                         [datetime(2024, 5, 2, 1), datetime(2024, 5, 3, 1)])

    def test_the_window_edges_are_inclusive(self):
        s = schedule(start_time=3600)
        self.assertEqual(expected_runs(s, datetime(2024, 5, 2, 1), datetime(2024, 5, 2, 1)), [datetime(2024, 5, 2, 1)])

    def test_every_six_hours(self):
        s = schedule(subday_type=8, subday_interval=6, start_time=900)
        got = expected_runs(s, datetime(2024, 5, 1, 8), datetime(2024, 5, 2, 7, 50))
        self.assertEqual([t.strftime("%d %H:%M") for t in got], ["01 12:15", "01 18:15", "02 00:15", "02 06:15"])

    def test_nothing_before_the_schedule_starts(self):
        s = schedule(start_date=date(2024, 6, 1))
        self.assertEqual(expected_runs(s, datetime(2024, 5, 1), datetime(2024, 5, 31)), [])
