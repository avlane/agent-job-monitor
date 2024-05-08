"""Render a Report as text or JSON."""


def render_text(report):
    counts = report.counts()
    lines = [
        "agent-job-monitor report for %s at %s" % (report.server or "(unknown server)", report.now.strftime("%Y-%m-%d %H:%M:%S")),
        "%d job(s) checked: %d ok, %d with warnings, %d critical" % (
            counts["jobs"], counts["ok"], counts["warning"], counts["critical"]),
        "",
    ]
    if not report.findings:
        lines.append("No problems found.")
    for f in report.findings:
        lines.append("[%s] %s: %s - %s" % (f.severity.upper(), f.job, f.code, f.message))
    return "\n".join(lines) + "\n"


RENDERERS = {"text": render_text}


def render(report, fmt="text"):
    try:
        return RENDERERS[fmt](report)
    except KeyError:
        raise ValueError("unknown report format: %s" % fmt) from None
