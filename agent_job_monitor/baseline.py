"""Rolling duration baselines: median, median absolute deviation and the 95th percentile."""
import statistics
from dataclasses import dataclass

MAD_TO_SIGMA = 1.4826  # scales the median absolute deviation to a standard deviation for normal data


@dataclass(frozen=True)
class Baseline:
    runs: int
    median: float
    mad: float  # median absolute deviation
    p95: float
    minimum: float
    maximum: float

    @property
    def sigma(self):
        return self.mad * MAD_TO_SIGMA


def percentile(sorted_values, q):
    """The q-th percentile (0 to 100) with linear interpolation between ranks."""
    if not sorted_values:
        raise ValueError("no values")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * q / 100.0
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def compute_baseline(durations):
    """Baseline of a list of durations in seconds, or None for an empty list."""
    values = sorted(durations)
    if not values:
        return None
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    return Baseline(len(values), float(median), float(mad), percentile(values, 95), float(values[0]), float(values[-1]))


def baseline_before(runs, index, count):
    """Baseline of the up to `count` successful runs before runs[index], or None without any."""
    earlier = [r.duration for r in runs[:index] if r.succeeded]
    return compute_baseline(earlier[-count:])
