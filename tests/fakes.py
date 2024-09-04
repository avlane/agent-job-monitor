"""A fake DB-API connection that answers the msdb queries from a JSON fixture."""
import json
import os

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = None
        self._rows = []

    def execute(self, sql, *params):
        self.conn.executed.append((sql, params))
        for marker, supplier in self.conn.responders:
            if marker in sql:
                rows = supplier(self.conn, params)
                cols = list(rows[0]) if rows else []
                self.description = [(c, None, None, None, None, None, None) for c in cols]
                self._rows = [tuple(r[c] for c in cols) for r in rows]
                return self
        raise AssertionError("no fake response for: " + sql.strip()[:60])

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, doc):
        self.doc = doc
        self.executed = []
        self.closed = False
        self.responders = [
            ("GETDATE()", lambda c, p: [c.doc["server"]]),
            ("FROM msdb.dbo.sysjobs AS j", lambda c, p: c.doc["jobs"]),
            ("FROM msdb.dbo.sysjobhistory AS h", lambda c, p: c.doc["history"]),
            ("FROM msdb.dbo.sysjobactivity AS ja", lambda c, p: c.doc["activity"]),
            ("FROM msdb.dbo.sysjobschedules AS js", lambda c, p: c.doc["schedules"]),
        ]

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


def load_fixture(name):
    with open(os.path.join(FIXTURES, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def connection_from_fixture(name):
    return FakeConnection(load_fixture(name))
