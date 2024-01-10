# agent-job-monitor

Reads the SQL Server Agent job history from `msdb` and reports failed jobs, jobs and steps that run
much longer than they usually do, and jobs that did not run when their schedule says they should
have. Output is text, JSON or the Prometheus text format.

Work in progress.
