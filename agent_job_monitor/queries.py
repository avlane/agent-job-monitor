"""SQL used to read Agent jobs and history from msdb, and the row mapping."""
from datetime import date, datetime

from .model import Job, RunningJob, Schedule, ServerInfo
from .msdbtime import decode_date, decode_datetime, decode_seconds_of_day

SERVER_SQL = """
SELECT @@SERVERNAME AS server_name,
       GETDATE() AS now,
       (SELECT MAX(agent_start_date) FROM msdb.dbo.syssessions) AS agent_start;
"""

JOBS_SQL = """
SELECT CONVERT(varchar(36), j.job_id) AS job_id, j.name, j.enabled, c.name AS category,
       SUSER_SNAME(j.owner_sid) AS owner
FROM msdb.dbo.sysjobs AS j
LEFT JOIN msdb.dbo.syscategories AS c ON c.category_id = j.category_id
ORDER BY j.name;
"""


def rows_as_dicts(cursor):
    """Turn a DB-API cursor result into a list of dicts keyed by lower-case column name."""
    names = [col[0].lower() for col in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _dt(value):
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def fetch_server(conn):
    cur = conn.cursor()
    try:
        cur.execute(SERVER_SQL)
        row = rows_as_dicts(cur)[0]
        return ServerInfo(row["server_name"], _dt(row["now"]), _dt(row["agent_start"]))
    finally:
        cur.close()


def fetch_jobs(conn):
    cur = conn.cursor()
    try:
        cur.execute(JOBS_SQL)
        return [Job(row["job_id"], row["name"], bool(row["enabled"]), row["category"] or "", row["owner"] or "")
                for row in rows_as_dicts(cur)]
    finally:
        cur.close()


HISTORY_SQL = """
SELECT CONVERT(varchar(36), h.job_id) AS job_id, h.instance_id, h.step_id, h.step_name, h.run_status,
       h.run_date, h.run_time, h.run_duration, h.message, h.sql_message_id, h.sql_severity, h.retries_attempted
FROM msdb.dbo.sysjobhistory AS h
WHERE h.run_date >= ?
ORDER BY h.instance_id;
"""


def fetch_history_rows(conn, since):
    """Raw sysjobhistory rows for runs that started on or after the date `since` (a datetime)."""
    cur = conn.cursor()
    try:
        cur.execute(HISTORY_SQL, since.year * 10000 + since.month * 100 + since.day)
        return rows_as_dicts(cur)
    finally:
        cur.close()


ACTIVITY_SQL = """
SELECT CONVERT(varchar(36), ja.job_id) AS job_id, ja.start_execution_date,
       ja.last_executed_step_id, ja.last_executed_step_date
FROM msdb.dbo.sysjobactivity AS ja
WHERE ja.session_id = (SELECT MAX(session_id) FROM msdb.dbo.syssessions)
  AND ja.start_execution_date IS NOT NULL
  AND ja.stop_execution_date IS NULL;
"""


def fetch_running(conn):
    """{job_id: RunningJob} for the jobs that are executing in the current Agent session."""
    cur = conn.cursor()
    try:
        cur.execute(ACTIVITY_SQL)
        return {
            row["job_id"]: RunningJob(row["job_id"], _dt(row["start_execution_date"]),
                                      int(row["last_executed_step_id"] or 0), _dt(row["last_executed_step_date"]))
            for row in rows_as_dicts(cur)
        }
    finally:
        cur.close()


SCHEDULES_SQL = """
SELECT CONVERT(varchar(36), js.job_id) AS job_id, s.schedule_id, s.name, s.enabled, s.freq_type, s.freq_interval,
       s.freq_subday_type, s.freq_subday_interval, s.freq_relative_interval, s.freq_recurrence_factor,
       s.active_start_date, s.active_end_date, s.active_start_time, s.active_end_time,
       js.next_run_date, js.next_run_time
FROM msdb.dbo.sysjobschedules AS js
JOIN msdb.dbo.sysschedules AS s ON s.schedule_id = js.schedule_id
ORDER BY js.job_id, s.schedule_id;
"""


def fetch_schedules(conn):
    """{job_id: [Schedule, ...]}"""
    cur = conn.cursor()
    try:
        cur.execute(SCHEDULES_SQL)
        schedules = {}
        for row in rows_as_dicts(cur):
            schedules.setdefault(row["job_id"], []).append(Schedule(
                job_id=row["job_id"], schedule_id=int(row["schedule_id"]), name=row["name"], enabled=bool(row["enabled"]),
                freq_type=int(row["freq_type"]), freq_interval=int(row["freq_interval"]),
                freq_subday_type=int(row["freq_subday_type"]), freq_subday_interval=int(row["freq_subday_interval"]),
                freq_relative_interval=int(row["freq_relative_interval"]),
                freq_recurrence_factor=int(row["freq_recurrence_factor"]),
                active_start_date=decode_date(row["active_start_date"]) or date.min,
                active_end_date=decode_date(row["active_end_date"]) or date.max,
                active_start_seconds=decode_seconds_of_day(row["active_start_time"]),
                active_end_seconds=decode_seconds_of_day(row["active_end_time"]),
                next_run=decode_datetime(row["next_run_date"], row["next_run_time"]),
            ))
        return schedules
    finally:
        cur.close()
