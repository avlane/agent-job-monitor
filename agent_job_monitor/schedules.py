"""Work out when a job should have started, from its schedule definition."""
from datetime import datetime, timedelta

FREQ_ONCE, FREQ_DAILY, FREQ_WEEKLY, FREQ_MONTHLY, FREQ_MONTHLY_RELATIVE = 1, 4, 8, 16, 32
SUBDAY_AT, SUBDAY_SECONDS, SUBDAY_MINUTES, SUBDAY_HOURS = 1, 2, 4, 8
_SUBDAY_UNIT = {SUBDAY_SECONDS: 1, SUBDAY_MINUTES: 60, SUBDAY_HOURS: 3600}


def sql_weekday_bit(day):
    """SQL Agent's weekday bit for a date: Sunday 1, Monday 2, Tuesday 4 ... Saturday 64."""
    return 1 << ((day.weekday() + 1) % 7)


def _sunday_on_or_before(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def runs_on_day(schedule, day):
    """Does the schedule fire on this date (ignoring the time of day)?"""
    if day < schedule.active_start_date or day > schedule.active_end_date:
        return False
    factor = max(schedule.freq_recurrence_factor, 1)
    if schedule.freq_type == FREQ_ONCE:
        return day == schedule.active_start_date
    if schedule.freq_type == FREQ_DAILY:
        return (day - schedule.active_start_date).days % max(schedule.freq_interval, 1) == 0
    if schedule.freq_type == FREQ_WEEKLY:
        weeks = (_sunday_on_or_before(day) - _sunday_on_or_before(schedule.active_start_date)).days // 7
        return bool(schedule.freq_interval & sql_weekday_bit(day)) and weeks % factor == 0
    return False  # monthly schedules are not handled yet; at-start and idle schedules have no clock times


def times_of_day(schedule):
    """Seconds since midnight at which the schedule fires on a day it is active."""
    if schedule.freq_type == FREQ_ONCE or schedule.freq_subday_type == SUBDAY_AT:
        return [schedule.active_start_seconds]
    unit = _SUBDAY_UNIT.get(schedule.freq_subday_type)
    if unit is None or schedule.freq_subday_interval <= 0:
        return [schedule.active_start_seconds]
    step = unit * schedule.freq_subday_interval
    return list(range(schedule.active_start_seconds, schedule.active_end_seconds + 1, step))


def expected_runs(schedule, start, end):
    """Datetimes in [start, end] at which the schedule should start its job."""
    found = []
    day = start.date()
    while day <= end.date():
        if runs_on_day(schedule, day):
            midnight = datetime.combine(day, datetime.min.time())
            for seconds in times_of_day(schedule):
                moment = midnight + timedelta(seconds=seconds)
                if start <= moment <= end:
                    found.append(moment)
        day += timedelta(days=1)
    return found
