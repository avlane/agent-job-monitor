"""Turn raw sysjobhistory rows into job runs with their steps."""
from .model import JobRun, StepRun
from .msdbtime import decode_datetime, decode_duration


def assemble_runs(rows):
    """({job_id: [JobRun, ...] oldest first}, {job_id: [StepRun, ...]} for steps of runs not finished yet).

    sysjobhistory holds one row per step, written when the step ends, and one outcome row
    (step_id 0) written when the job ends. The step rows that precede an outcome row belong to it.
    """
    runs, open_steps = {}, {}
    for row in sorted(rows, key=lambda r: r["instance_id"]):
        job_id = row["job_id"]
        start = decode_datetime(row["run_date"], row["run_time"])
        if start is None:
            continue
        duration = decode_duration(row["run_duration"])
        if row["step_id"] == 0:
            steps = open_steps.pop(job_id, [])
            runs.setdefault(job_id, []).append(
                JobRun(job_id, start, duration, int(row["run_status"]), row["message"] or "", steps))
        else:
            open_steps.setdefault(job_id, []).append(
                StepRun(int(row["step_id"]), row["step_name"], int(row["run_status"]), start, duration,
                        row["message"] or "", int(row["sql_message_id"] or 0), int(row["sql_severity"] or 0)))
    return runs, open_steps
