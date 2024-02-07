import unittest
from datetime import datetime

from agent_job_monitor.queries import fetch_jobs, fetch_server

from .fakes import connection_from_fixture


class ServerTest(unittest.TestCase):
    def test_server_and_clock(self):
        info = fetch_server(connection_from_fixture("healthy"))
        self.assertEqual(info.name, "SQLPROD01")
        self.assertEqual(info.now, datetime(2024, 5, 2, 8, 0, 0))
        self.assertEqual(info.agent_start, datetime(2024, 4, 20, 4, 2, 11))


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.jobs = {j.name: j for j in fetch_jobs(connection_from_fixture("healthy"))}

    def test_every_job(self):
        self.assertEqual(sorted(self.jobs), ["ETL load", "Index maintenance", "Nightly backup", "Purge history", "Report refresh"])

    def test_fields(self):
        job = self.jobs["Nightly backup"]
        self.assertEqual((job.job_id, job.category, job.owner), ("0A1B2C3D-0000-4000-8000-000000000001", "Database Maintenance", "sa"))
        self.assertIs(job.enabled, True)
        self.assertIs(self.jobs["Report refresh"].enabled, False)
