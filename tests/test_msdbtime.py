import unittest
from datetime import datetime

from agent_job_monitor.msdbtime import decode_datetime, decode_duration, encode_datetime, encode_duration


class DecodeDatetimeTest(unittest.TestCase):
    def test_date_and_time(self):
        self.assertEqual(decode_datetime(20240502, 13045), datetime(2024, 5, 2, 1, 30, 45))

    def test_midnight_is_time_zero(self):
        self.assertEqual(decode_datetime(20240502, 0), datetime(2024, 5, 2))

    def test_short_times_have_leading_zeros_dropped(self):
        self.assertEqual(decode_datetime(20240502, 5), datetime(2024, 5, 2, 0, 0, 5))
        self.assertEqual(decode_datetime(20240502, 1500), datetime(2024, 5, 2, 0, 15, 0))

    def test_no_date(self):
        self.assertIsNone(decode_datetime(0, 0))
        self.assertIsNone(decode_datetime(None, 0))

    def test_impossible_values_are_none(self):
        self.assertIsNone(decode_datetime(20241345, 0))
        self.assertIsNone(decode_datetime(20240502, 256100))


class DecodeDurationTest(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(decode_duration(0), 0)
        self.assertEqual(decode_duration(45), 45)
        self.assertEqual(decode_duration(130), 90)
        self.assertEqual(decode_duration(13045), 5445)
        self.assertEqual(decode_duration(None), 0)

    def test_more_than_a_day(self):
        self.assertEqual(decode_duration(260000), 26 * 3600)
        self.assertEqual(decode_duration(1000000), 100 * 3600)

    def test_round_trip(self):
        for seconds in (0, 1, 59, 60, 3599, 3600, 86399, 93784, 360000):
            self.assertEqual(decode_duration(encode_duration(seconds)), seconds)

    def test_encode_datetime(self):
        moment = datetime(2024, 5, 2, 1, 30, 45)
        self.assertEqual(encode_datetime(moment), (20240502, 13045))
        self.assertEqual(decode_datetime(*encode_datetime(moment)), moment)
