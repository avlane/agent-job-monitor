"""The Prometheus text exposition format (version 0.0.4) for a Report."""
from . import __version__


def escape_label(value):
    """Label values are quoted; backslash, double quote and newline must be escaped (in that order)."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _number(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return "%.6g" % value


def _sample(name, labels, value):
    rendered = ",".join('%s="%s"' % (key, escape_label(val)) for key, val in labels)
    return "%s{%s} %s" % (name, rendered, _number(value))


# (metric, help, function(summary, now) -> value or None)
JOB_METRICS = (
    ("agent_job_enabled", "1 if the job is enabled.", lambda s, now: s.enabled),
    ("agent_job_last_run_succeeded", "1 if the newest finished run of the job succeeded, 0 if it did not.",
     lambda s, now: None if s.last_status is None else s.last_status == 1),
    ("agent_job_last_run_age_seconds", "Seconds between the start of the newest finished run and the server time.",
     lambda s, now: None if s.last_start is None else max(0, (now - s.last_start).total_seconds())),
    ("agent_job_last_run_duration_seconds", "Duration of the newest finished run.",
     lambda s, now: s.last_duration),
    ("agent_job_consecutive_failures", "Failed runs in a row, counted from the newest.",
     lambda s, now: s.consecutive_failures),
    ("agent_job_running_seconds", "Seconds the job has been running; absent when it is not running.",
     lambda s, now: s.running_seconds),
    ("agent_job_missed_runs", "Scheduled starts in the look-back window for which the job has no run.",
     lambda s, now: s.missed_runs),
)


def render_prometheus(report):
    server = report.server
    lines = []
    for name, text, getter in JOB_METRICS:
        samples = []
        for job in sorted(report.summaries):
            value = getter(report.summaries[job], report.now)
            if value is not None:
                samples.append(_sample(name, (("server", server), ("job", job)), value))
        if samples:
            lines += ["# HELP %s %s" % (name, text), "# TYPE %s gauge" % name] + samples
    lines += [
        "# HELP agent_job_monitor_jobs_checked Number of enabled jobs that were examined.",
        "# TYPE agent_job_monitor_jobs_checked gauge",
        _sample("agent_job_monitor_jobs_checked", (("server", server),), len(report.checked)),
        "# HELP agent_job_monitor_findings Findings of this run by severity.",
        "# TYPE agent_job_monitor_findings gauge",
    ]
    for severity in ("critical", "warning", "info"):
        count = sum(1 for f in report.findings if f.severity == severity)
        lines.append(_sample("agent_job_monitor_findings", (("server", server), ("severity", severity)), count))
    lines += [
        "# HELP agent_job_monitor_info Version of the monitor that produced these metrics.",
        "# TYPE agent_job_monitor_info gauge",
        _sample("agent_job_monitor_info", (("server", server), ("version", __version__)), 1),
    ]
    return "\n".join(lines) + "\n"
