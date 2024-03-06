"""Thresholds for the checks."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Thresholds:
    critical_failures: int = 3  # consecutive failed runs that make a failing job critical
    lookback_hours: float = 24.0  # failures and overruns older than this are not reported


@dataclass
class Config:
    thresholds: Thresholds = field(default_factory=Thresholds)
