"""Decode the integer encodings that msdb uses for dates, times and durations."""
from datetime import datetime


def decode_datetime(run_date, run_time):
    """msdb stores 20240502 and 13045 for 2024-05-02 01:30:45. Returns None for 0 or an impossible value."""
    if not run_date:
        return None
    year, rest = divmod(int(run_date), 10000)
    month, day = divmod(rest, 100)
    hour, rest = divmod(int(run_time or 0), 10000)
    minute, second = divmod(rest, 100)
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def decode_duration(value):
    """run_duration is HHMMSS as a number: 13045 is 1 h 30 min 45 s. Hours are not limited to 23."""
    hours, rest = divmod(int(value or 0), 10000)
    minutes, seconds = divmod(rest, 100)
    return hours * 3600 + minutes * 60 + seconds


def encode_datetime(moment):
    return moment.year * 10000 + moment.month * 100 + moment.day, moment.hour * 10000 + moment.minute * 100 + moment.second


def encode_duration(seconds):
    seconds = int(seconds)
    return (seconds // 3600) * 10000 + (seconds % 3600 // 60) * 100 + seconds % 60
