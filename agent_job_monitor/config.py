"""Thresholds for the checks."""
from dataclasses import dataclass, field


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


@dataclass
class Config:
    thresholds: Thresholds = field(default_factory=Thresholds)
