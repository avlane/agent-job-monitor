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


@dataclass
class Config:
    thresholds: Thresholds = field(default_factory=Thresholds)
    jobs: dict = field(default_factory=dict)  # lower-case job name or pattern -> Thresholds for that job
    exclude_jobs: list = field(default_factory=list)  # job name patterns that are never checked

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


def parse_config(data):
    if not isinstance(data, dict):
        raise ConfigError("the top level of the config must be a table")
    unknown = set(data) - {"thresholds", "jobs", "exclude"}
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
    return Config(defaults, jobs, _names(exclude.get("jobs", []), "[exclude] jobs"))


def load_config(path):
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        raise ConfigError("cannot read %s: %s" % (path, exc)) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError("%s is not valid TOML: %s" % (path, exc)) from exc
    return parse_config(data)
