import io
import re
import unittest

from agent_job_monitor.analysis import analyse
from agent_job_monitor.cli import main
from agent_job_monitor.collect import collect
from agent_job_monitor.config import Config
from agent_job_monitor.prometheus import escape_label, render_prometheus
from agent_job_monitor.report import render

from .fakes import connection_from_fixture
from .helpers import history, job, server

SAMPLE_LINE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{(.*)\})? (-?[0-9.eE+-]+|NaN|\+Inf|-Inf)$')
LABEL = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


def parse(text):
    """A strict-enough parser for the exposition format: {(metric, labels tuple): float}."""
    samples, help_seen, type_seen = {}, set(), set()
    for line in text.splitlines():
        if line.startswith("# HELP "):
            name = line.split()[2]
            assert name not in help_seen, "HELP repeated for " + name
            help_seen.add(name)
        elif line.startswith("# TYPE "):
            name = line.split()[2]
            assert name not in type_seen, "TYPE repeated for " + name
            assert line.split()[3] in ("gauge", "counter"), line
            type_seen.add(name)
        else:
            match = SAMPLE_LINE.match(line)
            assert match, "not a sample line: %r" % line
            labels = tuple(LABEL.findall(match.group(3) or ""))
            samples[(match.group(1), labels)] = float(match.group(4))
    assert help_seen == type_seen
    return samples


def report_for(fixture):
    conn = connection_from_fixture(fixture)
    c = collect(conn, 30)
    return analyse(c.server, c.jobs, c.runs, Config(), c.running, c.schedules)


class EscapeTest(unittest.TestCase):
    def test_escapes(self):
        self.assertEqual(escape_label('plain'), 'plain')
        self.assertEqual(escape_label('a"b'), 'a\\"b')
        self.assertEqual(escape_label('a\\b'), 'a\\\\b')
        self.assertEqual(escape_label('a\nb'), 'a\\nb')

    def test_backslash_is_escaped_before_the_quote(self):
        self.assertEqual(escape_label('\\"'), '\\\\\\"')


class RenderPrometheusTest(unittest.TestCase):
    def setUp(self):
        self.text = render_prometheus(report_for("problems"))
        self.samples = parse(self.text)

    def value(self, metric, job):
        return self.samples[(metric, (("server", "SQLPROD01"), ("job", job)))]

    def test_the_output_parses_and_ends_with_a_newline(self):
        self.assertTrue(self.text.endswith("\n"))
        self.assertGreater(len(self.samples), 20)

    def test_job_metrics(self):
        self.assertEqual(self.value("agent_job_enabled", "Nightly backup"), 1)
        self.assertEqual(self.value("agent_job_enabled", "Report refresh"), 0)
        self.assertEqual(self.value("agent_job_last_run_succeeded", "ETL load"), 0)
        self.assertEqual(self.value("agent_job_last_run_succeeded", "Nightly backup"), 1)
        self.assertEqual(self.value("agent_job_consecutive_failures", "ETL load"), 3)
        self.assertEqual(self.value("agent_job_last_run_age_seconds", "Nightly backup"), 7 * 3600)
        self.assertEqual(self.value("agent_job_running_seconds", "Index maintenance"), 4.5 * 3600)
        self.assertEqual(self.value("agent_job_missed_runs", "Purge history"), 2)
        self.assertEqual(self.value("agent_job_missed_runs", "Nightly backup"), 0)

    def test_metrics_without_a_value_are_left_out(self):
        self.assertNotIn(("agent_job_running_seconds", (("server", "SQLPROD01"), ("job", "Nightly backup"))), self.samples)
        self.assertNotIn(("agent_job_last_run_succeeded", (("server", "SQLPROD01"), ("job", "Report refresh"))), self.samples)

    def test_server_wide_metrics(self):
        labels = (("server", "SQLPROD01"),)
        self.assertEqual(self.samples[("agent_job_monitor_jobs_checked", labels)], 4)
        self.assertEqual(self.samples[("agent_job_monitor_findings", labels + (("severity", "critical"),))], 1)
        self.assertEqual(self.samples[("agent_job_monitor_findings", labels + (("severity", "warning"),))], 3)
        self.assertEqual(self.samples[("agent_job_monitor_findings", labels + (("severity", "info"),))], 1)

    def test_unusual_job_names_survive(self):
        report = analyse(server(), [job('We "quote" \\ and\nbreak', job_id="X")], {"X": history(1, 1)}, Config())
        samples = parse(render_prometheus(report))
        key = ("agent_job_enabled", (("server", "SQLPROD01"), ("job", 'We \\"quote\\" \\\\ and\\nbreak')))
        self.assertEqual(samples[key], 1)

    def test_render_dispatches_on_the_format_name(self):
        self.assertEqual(render(report_for("healthy"), "prometheus"), render_prometheus(report_for("healthy")))

    def test_command_line(self):
        out = io.StringIO()
        code = main(["--server", "SQLPROD01", "--format", "prometheus"],
                    connect=lambda a: connection_from_fixture("healthy"), stdout=out)
        self.assertEqual(code, 0)
        self.assertIn("# TYPE agent_job_last_run_succeeded gauge", out.getvalue())
