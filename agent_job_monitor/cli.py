"""Command line interface for agent-job-monitor."""
import argparse
import fnmatch
import os
import sys

from . import __version__
from .analysis import CRITICAL, WARNING, analyse
from .collect import collect
from .config import Config, ConfigError, load_config
from .connection import DEFAULT_DRIVER
from .report import render

EXIT_OK, EXIT_WARNING, EXIT_CRITICAL, EXIT_ERROR = 0, 1, 2, 3


class _Parser(argparse.ArgumentParser):
    """argparse exits with 2 on usage errors; that code is reserved for critical findings."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, "%s: error: %s\n" % (self.prog, message))


def build_parser():
    p = _Parser(
        prog="agent-job-monitor",
        description="Check SQL Server Agent jobs: failures, runs that take much longer than usual.",
        epilog="Exit codes: 0 clean, 1 warnings, 2 critical findings, 3 usage/config/connection error.",
    )
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    p.add_argument("--server", required=True, help="instance to check, e.g. SQLPROD01 or SQLPROD01,1433")
    p.add_argument("--config", help="TOML file with thresholds")
    p.add_argument("-j", "--job", action="append", default=[], metavar="PATTERN",
                   help="only check jobs whose name matches (wildcards * and ?; repeatable)")
    p.add_argument("--history-days", type=int, default=30, metavar="N",
                   help="how many days of job history to read (default: %(default)s)")
    p.add_argument("--format", choices=("text", "json"), default="text", help="report format (default: text)")
    p.add_argument("-o", "--output", help="write the report to this file instead of stdout")
    p.add_argument("--user", help="SQL login; the password is read from AGENT_JOB_MONITOR_PASSWORD")
    p.add_argument("--driver", default=DEFAULT_DRIVER, help="ODBC driver name (default: %(default)s)")
    p.add_argument("--no-encrypt", action="store_true", help="connect without encryption")
    p.add_argument("--trust-server-certificate", action="store_true",
                   help="accept the server certificate without validating it")
    return p


def default_connect(args):
    from .connection import connect

    return connect(
        args.server,
        driver=args.driver,
        user=args.user,
        password=os.environ.get("AGENT_JOB_MONITOR_PASSWORD"),
        encrypt=not args.no_encrypt,
        trust_server_certificate=args.trust_server_certificate,
    )


def exit_code(report):
    counts = report.counts()
    if counts["critical"]:
        return EXIT_CRITICAL
    if counts["warning"]:
        return EXIT_WARNING
    return EXIT_OK


def _error(message):
    print("agent-job-monitor: %s" % message, file=sys.stderr)
    return EXIT_ERROR


def select_jobs(jobs, patterns):
    if not patterns:
        return jobs
    chosen = [j for j in jobs if any(fnmatch.fnmatchcase(j.name.lower(), p.lower()) for p in patterns)]
    if not chosen:
        raise LookupError("no job matches: %s" % ", ".join(patterns))
    return chosen


def main(argv=None, connect=None, stdout=None):
    stdout = stdout or sys.stdout
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config) if args.config else Config()
    except ConfigError as exc:
        return _error(exc)
    try:
        conn = (connect or default_connect)(args)
    except Exception as exc:  # driver errors are not importable without the driver
        return _error("cannot connect to %s: %s" % (args.server, exc))
    try:
        collected = collect(conn, args.history_days)
    except Exception as exc:
        return _error("query failed: %s" % exc)
    finally:
        conn.close()
    try:
        jobs = select_jobs(collected.jobs, args.job)
    except LookupError as exc:
        return _error(exc)
    report = analyse(collected.server, jobs, collected.runs, config, collected.running, collected.schedules)
    text = render(report, args.format)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        stdout.write(text)
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
