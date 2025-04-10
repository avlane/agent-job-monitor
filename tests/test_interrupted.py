import unittest
from datetime import datetime

from agent_job_monitor.model import RETRY
from agent_job_monitor.runs import assemble_runs

from .test_runs import row


class InterruptedRunTest(unittest.TestCase):
    def test_steps_of_an_interrupted_run_are_not_attached_to_the_next_run(self):
        runs, open_steps = assemble_runs([
            row("A", 1, 1, 1, 20240501, 10000, 100, "one"),      # the server restarted after step 2
            row("A", 2, 2, 1, 20240501, 10140, 200, "two"),
            row("A", 3, 1, 1, 20240502, 10000, 100, "one"),      # next night, a complete run
            row("A", 4, 2, 1, 20240502, 10140, 200, "two"),
            row("A", 5, 3, 1, 20240502, 10500, 50, "three"),
            row("A", 6, 0, 1, 20240502, 10000, 350),
        ])
        (only,) = runs["A"]
        self.assertEqual([s.step_id for s in only.steps], [1, 2, 3])
        self.assertEqual(only.start, datetime(2024, 5, 2, 1))
        self.assertEqual(open_steps, {})

    def test_the_interrupted_steps_stay_open_when_nothing_follows(self):
        _, open_steps = assemble_runs([row("A", 1, 1, 1, 20240501, 10000, 100, "one")])
        self.assertEqual([s.step_id for s in open_steps["A"]], [1])

    def test_a_retried_step_writes_several_rows_for_the_same_run(self):
        runs, _ = assemble_runs([
            row("A", 1, 1, 1, 20240502, 10000, 100, "one"),
            row("A", 2, 2, RETRY, 20240502, 10140, 20, "two"),
            row("A", 3, 2, RETRY, 20240502, 10200, 20, "two"),
            row("A", 4, 2, 1, 20240502, 10300, 90, "two"),
            row("A", 5, 0, 1, 20240502, 10000, 330),
        ])
        self.assertEqual([(s.step_id, s.status) for s in runs["A"][0].steps], [(1, 1), (2, RETRY), (2, RETRY), (2, 1)])

    def test_two_runs_without_an_outcome_row_in_between_are_two_runs(self):
        _, open_steps = assemble_runs([row("A", 1, 1, 1, 20240501, 10000, 100), row("A", 2, 1, 1, 20240502, 10000, 100)])
        self.assertEqual(len(open_steps["A"]), 1)
        self.assertEqual(open_steps["A"][0].start, datetime(2024, 5, 2, 1))

    def test_other_jobs_are_unaffected(self):
        runs, open_steps = assemble_runs([row("A", 1, 1, 1, 20240501, 10000, 100), row("B", 2, 1, 1, 20240501, 10000, 100),
                                          row("A", 3, 1, 1, 20240502, 10000, 100)])
        self.assertEqual((len(open_steps["A"]), len(open_steps["B"])), (1, 1))
