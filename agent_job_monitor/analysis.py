"""Compare job history with the thresholds and produce findings."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from .baseline import baseline_before, compute_baseline
from .model import FAILED, SUCCEEDED
from .msdbtime import format_duration


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self):
        """0 is the worst, so sorting by rank puts critical findings first."""
        return list(Severity).index(self)


CRITICAL, WARNING, INFO = Severity.CRITICAL, Severity.WARNING, Severity.INFO


@dataclass
class Finding:
    job: str
    code: str
    severity: Severity
    message: str
    detail: dict = field(default_factory=dict)


@dataclass
class Report:
    server: str
    now: datetime
    checked: list  # names of the jobs that were examined
    findings: list

    def worst_by_job(self):
        worst = {}
        for f in self.findings:
            if f.severity == INFO:
                continue
            current = worst.get(f.job)
            if current is None or f.severity.rank < current.rank:
                worst[f.job] = f.severity
        return worst

    def counts(self):
        worst = self.worst_by_job()
        return {
            "jobs": len(self.checked),
            "critical": sum(1 for s in worst.values() if s == CRITICAL),
            "warning": sum(1 for s in worst.values() if s == WARNING),
            "ok": len(self.checked) - len(worst),
        }


def consecutive_failures(runs):
    """How many of the newest runs in a row failed."""
    count = 0
    for run in reversed(runs):
        if run.status != FAILED:
            break
        count += 1
    return count


def failed_step(run):
    """The first step of the run that failed, or None (the job may have failed outside any step)."""
    for step in run.steps:
        if step.status == FAILED:
            return step
    return None


def shorten(text, limit=200):
    """One line of at most `limit` characters; Agent messages are long and repeat the account name."""
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


def check_failures(job, runs, thresholds):
    if not runs or runs[-1].status != FAILED:
        return []
    last = runs[-1]
    count = consecutive_failures(runs)
    severity = CRITICAL if count >= thresholds.critical_failures else WARNING
    message = "%d consecutive failure(s), the last started at %s" % (count, last.start.strftime("%Y-%m-%d %H:%M"))
    detail = {"consecutive_failures": count, "last_start": last.start.isoformat()}
    step = failed_step(last)
    if step is not None:
        message += "; step %d '%s' failed: %s" % (step.step_id, step.name, shorten(step.message))
        detail.update(step_id=step.step_id, step_name=step.name, sql_message_id=step.sql_message_id,
                      sql_severity=step.sql_severity)
    return [Finding(job.name, "JOB_FAILED", severity, message, detail)]


def overrun_limit(baseline, thresholds):
    """The duration above which a run counts as too long: the larger of a multiple of the median and
    the median plus a few robust standard deviations."""
    return max(baseline.median * thresholds.overrun_factor,
               baseline.median + thresholds.overrun_mad_multiplier * baseline.sigma)


def check_overruns(job, runs, thresholds, now):
    """The worst overrun among the successful runs that started within the look-back window."""
    window_start = now - timedelta(hours=thresholds.lookback_hours)
    worst, count = None, 0
    for index, run in enumerate(runs):
        if not run.succeeded or run.start < window_start:
            continue
        base = baseline_before(runs, index, thresholds.baseline_runs)
        if base is None or base.runs < thresholds.min_runs:
            continue
        limit = overrun_limit(base, thresholds)
        if run.duration > limit and run.duration - base.median >= thresholds.min_overrun_seconds:
            count += 1
            ratio = run.duration / base.median if base.median else float("inf")
            if worst is None or ratio > worst[0]:
                worst = (ratio, run, base, limit)
    if worst is None:
        return []
    ratio, run, base, limit = worst
    severity = CRITICAL if ratio >= thresholds.critical_overrun_factor else WARNING
    message = "the run that started at %s took %s, %.1f times the median %s of the previous %d runs (limit %s)" % (
        run.start.strftime("%Y-%m-%d %H:%M"), format_duration(run.duration), ratio, format_duration(base.median),
        base.runs, format_duration(limit))
    return [Finding(job.name, "JOB_OVERRUN", severity, message,
                    {"start": run.start.isoformat(), "duration_seconds": run.duration, "ratio": round(ratio, 2),
                     "median_seconds": base.median, "p95_seconds": base.p95, "limit_seconds": round(limit),
                     "baseline_runs": base.runs, "overruns_in_window": count})]


def check_steps(job, runs, thresholds, now):
    """The step of a recent successful run that took the longest compared with the same step before."""
    window_start = now - timedelta(hours=thresholds.lookback_hours)
    worst = None
    for index, run in enumerate(runs):
        if not run.succeeded or run.start < window_start:
            continue
        earlier = [r for r in runs[:index] if r.succeeded]
        for step in run.steps:
            if step.status != SUCCEEDED:
                continue
            history = [s.duration for r in earlier for s in r.steps
                       if s.step_id == step.step_id and s.status == SUCCEEDED][-thresholds.baseline_runs:]
            base = compute_baseline(history)
            if base is None or base.runs < thresholds.min_runs:
                continue
            if step.duration > overrun_limit(base, thresholds) and \
                    step.duration - base.median >= thresholds.step_min_overrun_seconds:
                ratio = step.duration / base.median if base.median else float("inf")
                if worst is None or ratio > worst[0]:
                    worst = (ratio, run, step, base)
    if worst is None:
        return []
    ratio, run, step, base = worst
    message = "step %d '%s' of the run that started at %s took %s, %.1f times its median %s" % (
        step.step_id, step.name, run.start.strftime("%Y-%m-%d %H:%M"), format_duration(step.duration), ratio,
        format_duration(base.median))
    return [Finding(job.name, "STEP_OVERRUN", WARNING, message,
                    {"run_start": run.start.isoformat(), "step_id": step.step_id, "step_name": step.name,
                     "duration_seconds": step.duration, "ratio": round(ratio, 2), "median_seconds": base.median,
                     "baseline_runs": base.runs})]


def check_running(job, runs, running, thresholds, now):
    """A job that is executing now for much longer than its successful runs usually take."""
    if running is None:
        return []
    elapsed = (now - running.start).total_seconds()
    earlier = [r.duration for r in runs if r.succeeded][-thresholds.baseline_runs:]
    base = compute_baseline(earlier)
    if base is None or base.runs < thresholds.min_runs:
        return []
    limit = overrun_limit(base, thresholds)
    if elapsed <= limit or elapsed - base.median < thresholds.min_overrun_seconds:
        return []
    ratio = elapsed / base.median if base.median else float("inf")
    severity = CRITICAL if ratio >= thresholds.critical_overrun_factor else WARNING
    message = "running since %s (%s), %.1f times the median %s of the previous %d runs (limit %s)" % (
        running.start.strftime("%Y-%m-%d %H:%M"), format_duration(elapsed), ratio, format_duration(base.median),
        base.runs, format_duration(limit))
    if running.last_step_id:
        message += "; last step finished: %d" % running.last_step_id
    return [Finding(job.name, "JOB_RUNNING_LONG", severity, message,
                    {"start": running.start.isoformat(), "elapsed_seconds": round(elapsed), "ratio": round(ratio, 2),
                     "median_seconds": base.median, "limit_seconds": round(limit), "last_step_id": running.last_step_id})]


def analyse(server, jobs, runs, config, running=None):
    """Findings for every enabled job. `runs` is {job_id: [JobRun, ...]} oldest first."""
    checked, findings = [], []
    for job in jobs:
        if not job.enabled:
            continue
        checked.append(job.name)
        findings += check_failures(job, runs.get(job.job_id, []), config.thresholds)
        findings += check_overruns(job, runs.get(job.job_id, []), config.thresholds, server.now)
        steps = check_steps(job, runs.get(job.job_id, []), config.thresholds, server.now)
        explained = {f.detail["start"] for f in findings if f.job == job.name and f.code == "JOB_OVERRUN"}
        for f in steps:
            if f.detail["run_start"] in explained:
                f.severity = INFO
                f.message += "; this is what made the job overrun"
        findings += steps
        findings += check_running(job, runs.get(job.job_id, []), (running or {}).get(job.job_id),
                                  config.thresholds, server.now)
    findings.sort(key=lambda f: (f.severity.rank, f.job.lower(), f.code))
    return Report(server.name, server.now, checked, findings)
