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


def check_failures(job, runs, thresholds):
    if not runs or runs[-1].status != FAILED:
        return []
    last = runs[-1]
    count = consecutive_failures(runs)
    severity = CRITICAL if count >= thresholds.critical_failures else WARNING
    return [Finding(job.name, "JOB_FAILED", severity,
                    "%d consecutive failure(s), the last started at %s" % (count, last.start.strftime("%Y-%m-%d %H:%M")),
                    {"consecutive_failures": count, "last_start": last.start.isoformat()})]


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
