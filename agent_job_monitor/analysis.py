"""Compare job history with the thresholds and produce findings."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .model import FAILED


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


def analyse(server, jobs, runs, config):
    """Findings for every enabled job. `runs` is {job_id: [JobRun, ...]} oldest first."""
    checked, findings = [], []
    for job in jobs:
        if not job.enabled:
            continue
        checked.append(job.name)
        findings += check_failures(job, runs.get(job.job_id, []), config.thresholds)
    findings.sort(key=lambda f: (f.severity.rank, f.job.lower(), f.code))
    return Report(server.name, server.now, checked, findings)
