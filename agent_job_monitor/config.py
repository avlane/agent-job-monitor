"""Thresholds for the checks, read from a TOML file."""
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


@dataclass
class Config:
    thresholds: Thresholds = field(default_factory=Thresholds)


def _thresholds(section):
    if not isinstance(section, dict):
        raise ConfigError("[thresholds] must be a table")
    known = {f.name: f for f in fields(Thresholds)}
    unknown = set(section) - set(known)
    if unknown:
        raise ConfigError("[thresholds]: unknown key(s): %s" % ", ".join(sorted(unknown)))
    values = {}
    for key, value in section.items():
        wants_int = isinstance(getattr(Thresholds(), key), int)
        valid = isinstance(value, int) if wants_int else isinstance(value, (int, float))
        if isinstance(value, bool) or not valid or value <= 0:
            raise ConfigError("[thresholds] %s must be a positive %s" % (key, "whole number" if wants_int else "number"))
        values[key] = value
    return replace(Thresholds(), **values)


def parse_config(data):
    if not isinstance(data, dict):
        raise ConfigError("the top level of the config must be a table")
    unknown = set(data) - {"thresholds"}
    if unknown:
        raise ConfigError("unknown key(s): %s" % ", ".join(sorted(unknown)))
    return Config(_thresholds(data.get("thresholds", {})))


def load_config(path):
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        raise ConfigError("cannot read %s: %s" % (path, exc)) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError("%s is not valid TOML: %s" % (path, exc)) from exc
    return parse_config(data)
