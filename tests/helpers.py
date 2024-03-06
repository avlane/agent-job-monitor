"""Builders for small, hand-made job histories used by the unit tests."""
from datetime import datetime, timedelta

from agent_job_monitor.model import FAILED, SUCCEEDED, Job, JobRun, ServerInfo, StepRun

NOW = datetime(2024, 5, 2, 8, 0, 0)


def server():
    return ServerInfo("SQLPROD01", NOW, NOW - timedelta(days=12))


def job(name="Nightly", enabled=True, job_id=None):
    return Job(job_id or name.upper(), name, enabled)


def run(hours_ago, duration=600, status=SUCCEEDED, steps=(), job_id="NIGHTLY"):
    """A run that started `hours_ago` hours before NOW."""
    return JobRun(job_id, NOW - timedelta(hours=hours_ago), duration, status, "", list(steps))


def step(step_id, name="step", status=SUCCEEDED, duration=60, message="", hours_ago=1, msg_id=0, severity=0):
    return StepRun(step_id, name, status, NOW - timedelta(hours=hours_ago), duration, message, msg_id, severity)


def history(*statuses, step_hours=24, duration=600):
    """Runs, oldest first, one every `step_hours`, with the given statuses (1 succeeded, 0 failed)."""
    count = len(statuses)
    return [run((count - n) * step_hours - 5, duration, status) for n, status in enumerate(statuses)]
