import unittest
from datetime import datetime

from agent_job_monitor.model import FAILED, SUCCEEDED
from agent_job_monitor.queries import fetch_history_rows
from agent_job_monitor.runs import assemble_runs

from .fakes import connection_from_fixture

NIGHTLY = "0A1B2C3D-0000-4000-8000-000000000001"
ETL = "0A1B2C3D-0000-4000-8000-000000000002"
INDEX = "0A1B2C3D-0000-4000-8000-000000000003"
PURGE = "0A1B2C3D-0000-4000-8000-000000000004"


def row(job_id, instance, step_id, status, date, time, duration, name="step", message=""):
    return dict(job_id=job_id, instance_id=instance, step_id=step_id, step_name=name, run_status=status,
                run_date=date, run_time=time, run_duration=duration, message=message, sql_message_id=0,
                sql_severity=0, retries_attempted=0)


class AssembleRunsTest(unittest.TestCase):
    def test_steps_belong_to_the_outcome_row_after_them(self):
        runs, open_steps = assemble_runs([
            row("A", 1, 1, 1, 20240502, 10000, 100, "one"),
            row("A", 2, 2, 1, 20240502, 10140, 200, "two"),
            row("A", 3, 0, 1, 20240502, 10000, 500),
            row("A", 4, 1, 1, 20240503, 10000, 50, "one"),
            row("A", 5, 0, 0, 20240503, 10000, 50),
        ])
        first, second = runs["A"]
        self.assertEqual([s.name for s in first.steps], ["one", "two"])
        self.assertEqual((first.start, first.duration, first.status), (datetime(2024, 5, 2, 1), 300, SUCCEEDED))
        self.assertEqual([s.name for s in second.steps], ["one"])
        self.assertEqual(second.status, FAILED)
        self.assertEqual(open_steps, {})

    def test_steps_without_an_outcome_row_are_a_run_in_progress(self):
        runs, open_steps = assemble_runs([row("A", 1, 1, 1, 20240502, 10000, 100, "one")])
        self.assertEqual(runs, {})
        self.assertEqual([s.name for s in open_steps["A"]], ["one"])

    def test_jobs_do_not_mix(self):
        runs, _ = assemble_runs([row("A", 1, 1, 1, 20240502, 10000, 10), row("B", 2, 1, 1, 20240502, 10000, 20),
                                 row("B", 3, 0, 1, 20240502, 10000, 20), row("A", 4, 0, 1, 20240502, 10000, 10)])
        self.assertEqual([len(runs["A"][0].steps), len(runs["B"][0].steps)], [1, 1])

    def test_rows_are_ordered_by_instance_id_not_by_position(self):
        runs, _ = assemble_runs([row("A", 3, 0, 1, 20240502, 10000, 30), row("A", 1, 1, 1, 20240502, 10000, 10),
                                 row("A", 2, 2, 1, 20240502, 10010, 20)])
        self.assertEqual([s.step_id for s in runs["A"][0].steps], [1, 2])

    def test_rows_with_an_unusable_date_are_skipped(self):
        runs, open_steps = assemble_runs([row("A", 1, 0, 1, 0, 0, 10)])
        self.assertEqual((runs, open_steps), ({}, {}))

    def test_end_time(self):
        (run,) = assemble_runs([row("A", 1, 0, 1, 20240502, 235900, 130)])[0]["A"]
        self.assertEqual(run.end, datetime(2024, 5, 3, 0, 0, 30))


class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.conn = connection_from_fixture("healthy")
        self.runs, self.open_steps = assemble_runs(fetch_history_rows(self.conn, datetime(2024, 4, 1)))

    def test_since_is_passed_as_a_date_number(self):
        (sql, params), = [e for e in self.conn.executed if "sysjobhistory" in e[0]]
        self.assertEqual(params, (20240401,))

    def test_runs_per_job(self):
        self.assertEqual({job: len(runs) for job, runs in self.runs.items()},
                         {NIGHTLY: 15, ETL: 12, INDEX: 15, PURGE: 30})

    def test_runs_are_oldest_first_and_carry_their_steps(self):
        nightly = self.runs[NIGHTLY]
        self.assertEqual(nightly, sorted(nightly, key=lambda r: r.start))
        self.assertEqual([s.name for s in nightly[-1].steps], ["Full backup", "Verify backup", "Delete old files"])
        self.assertEqual(nightly[-1].start, datetime(2024, 5, 2, 1, 0, 0))
        self.assertTrue(all(r.succeeded for r in nightly))

    def test_nothing_is_left_open_in_a_healthy_history(self):
        self.assertEqual(self.open_steps, {})
