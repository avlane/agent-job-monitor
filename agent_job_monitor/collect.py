"""Read everything the checks need from msdb."""
from dataclasses import dataclass, field
from datetime import timedelta

from .queries import fetch_history_rows, fetch_jobs, fetch_server
from .runs import assemble_runs


@dataclass
class Collected:
    server: object
    jobs: list
    runs: dict  # job_id -> [JobRun, ...], oldest first
    open_steps: dict = field(default_factory=dict)  # job_id -> steps of a run that has not ended


def collect(conn, history_days=30):
    server = fetch_server(conn)
    jobs = fetch_jobs(conn)
    runs, open_steps = assemble_runs(fetch_history_rows(conn, server.now - timedelta(days=history_days)))
    return Collected(server, jobs, runs, open_steps)
