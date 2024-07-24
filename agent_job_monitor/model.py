"""Plain data objects for Agent jobs and their history."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

FAILED, SUCCEEDED, RETRY, CANCELED, IN_PROGRESS = 0, 1, 2, 3, 4
STATUS_NAMES = {FAILED: "failed", SUCCEEDED: "succeeded", RETRY: "retry", CANCELED: "canceled",
                IN_PROGRESS: "in progress"}


@dataclass
class Job:
    job_id: str
    name: str
    enabled: bool = True
    category: str = ""
    owner: str = ""


@dataclass
class StepRun:
    step_id: int
    name: str
    status: int
    start: datetime
    duration: int  # seconds
    message: str = ""
    sql_message_id: int = 0
    sql_severity: int = 0


@dataclass
class JobRun:
    """One execution of a job: the outcome row of sysjobhistory plus the step rows before it."""

    job_id: str
    start: datetime
    duration: int  # seconds
    status: int
    message: str = ""
    steps: list = field(default_factory=list)

    @property
    def end(self):
        return self.start + timedelta(seconds=self.duration)

    @property
    def succeeded(self):
        return self.status == SUCCEEDED


@dataclass
class ServerInfo:
    name: str
    now: datetime  # GETDATE() on the server; msdb times are in this clock
    agent_start: Optional[datetime] = None


@dataclass
class RunningJob:
    """A job that is executing now (sysjobactivity of the current Agent session)."""

    job_id: str
    start: datetime
    last_step_id: int = 0
    last_step_date: Optional[datetime] = None
