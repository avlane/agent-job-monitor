"""Thresholds and job selection, read from a TOML file."""
import fnmatch
import tomllib
from dataclasses import dataclass, field, fields, replace


class ConfigError(ValueError):
    """The configuration file is unreadable or invalid."""


@dataclass(frozen=True)
class Thresholds:
    critical_failures: int = 3  # consecutive failed runs that make a failing job critical
    lookback_hours: float = 24.0  # failures and overruns older than this are not reported
    baseline_runs: int = 20  # successful runs before the examined one that form its baseline
    min_runs: int = 5  # fewer earlier runs than this: no baseline, no overrun check
    overrun_factor: float = 2.0  # a run longer than this many times the median is an overrun ...
    overrun_mad_multiplier: float = 4.0  # ... when it is also this many robust standard deviations above it
    min_overrun_seconds: int = 300  # ... and at least this much longer than the median
    critical_overrun_factor: float = 4.0  # times the median that make an overrun critical
    step_min_overrun_seconds: int = 120  # a step must also be this much longer than its median to be reported
    grace_minutes: float = 10.0  # a scheduled run may start this late before it counts as missed
    critical_missed: int = 3  # missed runs in the window that make the finding critical
    min_schedule_seconds: int = 60  # schedules that fire more often than this are not checked for missed runs
    max_expected: int = 500  # at most this many of the newest expected starts are examined per job
    agent_silence_minutes: int = 30  # no job has started for this long ...
    agent_silence_min_due: int = 3  # ... although at least this many scheduled starts were due


KINDS = ("overrun", "steps", "running", "missed")  # what a maintenance window can silence
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class MaintenanceWindow:
    """A time of day (and optionally days of the week) in which long or late runs are expected."""

    start: int  # seconds since midnight
    end: int
    days: tuple = ()  # weekday numbers (Monday is 0) of the day the window starts; empty means every day
    jobs: tuple = ()  # name patterns; empty means every job
    suppress: tuple = KINDS
    name: str = ""

    def covers(self, moment):
        seconds = moment.hour * 3600 + moment.minute * 60 + moment.second
        if self.start <= self.end:
            inside, start_day = self.start <= seconds < self.end, moment.weekday()
        elif seconds >= self.start:
            inside, start_day = True, moment.weekday()
        else:  # the part of an overnight window after midnight belongs to the day before
            inside, start_day = seconds < self.end, (moment.weekday() - 1) % 7
        return inside and (not self.days or start_day in self.days)

    def applies_to(self, job_name):
        name = job_name.lower()
        return not self.jobs or any(fnmatch.fnmatchcase(name, pattern.lower()) for pattern in self.jobs)


@dataclass
class Config:
    thresholds: Thresholds = field(default_factory=Thresholds)
    jobs: dict = field(default_factory=dict)  # lower-case job name or pattern -> Thresholds for that job
    exclude_jobs: list = field(default_factory=list)  # job name patterns that are never checked
    maintenance: list = field(default_factory=list)  # MaintenanceWindow

    def in_maintenance(self, job_name, moment, kind):
        """Is `moment` inside a window that silences `kind` findings for this job?"""
        return any(w.covers(moment) and w.applies_to(job_name) and kind in w.suppress for w in self.maintenance)

    def thresholds_for(self, name):
        """Per-job thresholds: an exact name wins, then the first matching pattern, else the defaults."""
        key = name.lower()
        if key in self.jobs:
            return self.jobs[key]
        for pattern, thresholds in self.jobs.items():
            if fnmatch.fnmatchcase(key, pattern):
                return thresholds
        return self.thresholds

    def is_excluded(self, job):
        name = job.name.lower()
        return any(fnmatch.fnmatchcase(name, pattern.lower()) for pattern in self.exclude_jobs)


def _thresholds(section, where, base=None):
    if not isinstance(section, dict):
        raise ConfigError("%s must be a table" % where)
    base = base or Thresholds()
    known = {f.name for f in fields(Thresholds)}
    unknown = set(section) - known
    if unknown:
        raise ConfigError("%s: unknown key(s): %s" % (where, ", ".join(sorted(unknown))))
    values = {}
    for key, value in section.items():
        wants_int = isinstance(getattr(Thresholds(), key), int)
        valid = isinstance(value, int) if wants_int else isinstance(value, (int, float))
        if isinstance(value, bool) or not valid or value <= 0:
            raise ConfigError("%s %s must be a positive %s" % (where, key, "whole number" if wants_int else "number"))
        values[key] = value
    return replace(base, **values)


def _names(value, where):
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ConfigError("%s must be a list of non-empty names or patterns" % where)
    return list(value)


def _clock(text, where):
    try:
        hours, minutes = text.split(":")
        hours, minutes = int(hours), int(minutes)
    except (AttributeError, ValueError):
        raise ConfigError("%s must be a time like 02:30" % where) from None
    if not (0 <= hours <= 24 and 0 <= minutes < 60) or (hours == 24 and minutes):
        raise ConfigError("%s must be a time like 02:30" % where)
    return hours * 3600 + minutes * 60


def _window(entry, number):
    where = "[[maintenance]] #%d" % number
    if not isinstance(entry, dict):
        raise ConfigError("%s must be a table" % where)
    unknown = set(entry) - {"name", "start", "end", "days", "jobs", "suppress"}
    if unknown:
        raise ConfigError("%s: unknown key(s): %s" % (where, ", ".join(sorted(unknown))))
    if "start" not in entry or "end" not in entry:
        raise ConfigError("%s needs start and end" % where)
    days = entry.get("days", [])
    if not isinstance(days, list) or any(d not in _DAYS for d in days):
        raise ConfigError("%s: days must be a list of %s" % (where, ", ".join(_DAYS)))
    suppress = entry.get("suppress", list(KINDS))
    if not isinstance(suppress, list) or not suppress or any(k not in KINDS for k in suppress):
        raise ConfigError("%s: suppress must be a list of %s" % (where, ", ".join(KINDS)))
    return MaintenanceWindow(
        _clock(entry["start"], where + " start"), _clock(entry["end"], where + " end"),
        tuple(_DAYS.index(d) for d in days), tuple(_names(entry.get("jobs", []), where + " jobs")),
        tuple(suppress), str(entry.get("name", "")))


def parse_config(data):
    if not isinstance(data, dict):
        raise ConfigError("the top level of the config must be a table")
    unknown = set(data) - {"thresholds", "jobs", "exclude", "maintenance"}
    if unknown:
        raise ConfigError("unknown key(s): %s" % ", ".join(sorted(unknown)))
    defaults = _thresholds(data.get("thresholds", {}), "[thresholds]")
    jobs_section = data.get("jobs", {})
    if not isinstance(jobs_section, dict):
        raise ConfigError("[jobs] must be a table of per-job tables")
    jobs = {name.lower(): _thresholds(section, "[jobs.%s]" % name, defaults) for name, section in jobs_section.items()}
    exclude = data.get("exclude", {})
    if not isinstance(exclude, dict) or set(exclude) - {"jobs"}:
        raise ConfigError("[exclude] must be a table with a jobs list")
    windows = data.get("maintenance", [])
    if not isinstance(windows, list):
        raise ConfigError("maintenance must be a list of [[maintenance]] tables")
    return Config(defaults, jobs, _names(exclude.get("jobs", []), "[exclude] jobs"),
                  [_window(entry, n) for n, entry in enumerate(windows, 1)])


def load_config(path):
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        raise ConfigError("cannot read %s: %s" % (path, exc)) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError("%s is not valid TOML: %s" % (path, exc)) from exc
    return parse_config(data)
