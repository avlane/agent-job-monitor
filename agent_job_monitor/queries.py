"""SQL used to read Agent jobs and history from msdb, and the row mapping."""
from datetime import datetime

from .model import Job, ServerInfo

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
