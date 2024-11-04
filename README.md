# agent-job-monitor

Reads the SQL Server Agent job history from `msdb` and reports

* **failed jobs**, with the failing step and its error, and how many runs in a row have failed
* **runs that take much longer than usual**, judged against a rolling baseline of the job's own
  recent successful runs (median, robust spread and 95th percentile), and the same for single steps
* **jobs that are running now for much longer than usual**
* **jobs that did not start when their schedule says they should have**

It only reads from the server.

## How the checks work

* *Failures*: the newest outcome of the job is a failure. The finding is critical after
  `critical_failures` failed runs in a row (default 3), a warning before that.
* *Overruns*: each successful run in the look-back window (default 24 hours) is compared with the up to
  `baseline_runs` (20) successful runs before it. It is an overrun if it took more than
  `overrun_factor` (2) times the median, and also more than `overrun_mad_multiplier` (4) robust standard
  deviations above it, and at least `min_overrun_seconds` (300) longer. With fewer than `min_runs` (5)
  earlier runs there is no baseline and nothing is reported. Failed runs are never part of a baseline.
* *Slow steps*: the same rule per step, against the history of the same step number. When the job itself
  overran in the same run, the slow step is only informational: it explains the overrun.
* *Running now*: `sysjobactivity` of the current Agent session, with the same limit.
* *Missed schedules*: the expected start times are computed from the enabled schedules (once, daily and
  weekly; monthly schedules are not checked yet) and compared with the runs. A start counts if the run began
  within `grace_minutes` (10) after it. Starts that fall inside an earlier run of the same job are reported
  as skipped (informational), starts before the Agent came up are not expected, and a job with no history at
  all is not judged.

**History retention matters.** By default the Agent keeps only 1000 rows of history in total and 100 per job,
and every step is a row. A job with five steps keeps 16 runs. Raise the limits in SQL Server Agent properties
(History) so that baselines have enough runs, and keep `min_runs` in mind when a job runs rarely.

## Install

```
pip install .
pip install ".[sqlserver]"      # adds pyodbc, needed to talk to a server
```

Python 3.11 or newer and the Microsoft ODBC driver for SQL Server (version 18 by default;
`--driver "ODBC Driver 17 for SQL Server"` for 17). Driver 18 encrypts by default; add
`--trust-server-certificate` for a self-signed certificate. The account needs read access to msdb:
membership of `SQLAgentReaderRole` (or sysadmin).

## Usage

```
agent-job-monitor --server SQLPROD01
agent-job-monitor --server SQLPROD01,1433 --config monitor.toml --format json -o report.json
agent-job-monitor --server SQLPROD01 --job "Nightly*" --job "ETL load"
agent-job-monitor --help
```

### Example

```
agent-job-monitor report for SQLPROD01 at 2024-05-02 08:00:00
4 job(s) checked: 0 ok, 3 with warnings, 1 critical

[CRITICAL] ETL load: JOB_FAILED - 3 consecutive failure(s), the last started at 2024-05-02 02:30; step 3 'Load facts' failed: Executed as user: DOMAIN\svc_agent. Transaction (Process ID 87) was deadlocked on lock resources ...
[WARNING] Index maintenance: JOB_RUNNING_LONG - running since 2024-05-02 03:30 (4h 30m 00s), 2.8 times the median 1h 37m 14s of the previous 15 runs (limit 3h 14m 28s); last step finished: 2
[WARNING] Nightly backup: JOB_OVERRUN - the run that started at 2024-05-02 01:00 took 57m 53s, 2.2 times the median 26m 16s of the previous 14 runs (limit 52m 33s)
[WARNING] Purge history: SCHEDULE_MISSED - 2 scheduled run(s) did not start: 2024-05-02 00:15, 2024-05-02 06:15
[INFO] Nightly backup: STEP_OVERRUN - step 1 'Full backup' of the run that started at 2024-05-02 01:00 took 52m 00s, 2.6 times its median 20m 16s; this is what made the job overrun
```

(Output for the `problems` fixture in `tests/fixtures`.)

## Configuration

```toml
[thresholds]
critical_failures = 3
lookback_hours = 24
baseline_runs = 20
min_runs = 5
overrun_factor = 2.0
overrun_mad_multiplier = 4.0
min_overrun_seconds = 300
critical_overrun_factor = 4.0
step_min_overrun_seconds = 120
grace_minutes = 10
critical_missed = 3
```

## Exit codes

| code | meaning |
| --- | --- |
| 0 | no warnings or critical findings |
| 1 | warnings only |
| 2 | at least one critical finding |
| 3 | usage, configuration, connection or query error |

## What has been tested, and what has not

Tested with `python3 -m unittest discover`, which needs neither pyodbc nor a server:

* decoding of the integer dates, times and durations of msdb
* the history assembly, baselines and every check, with hand-built histories and with two fixtures
* schedule expansion and missed-run detection
* the report formats and the command line, with a fake connection that answers each query from a JSON fixture
* connection-string building, and `connect()` with a fake `pyodbc`

## Development

```
python3 -m unittest discover
```
