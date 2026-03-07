import unittest
import uuid
import json
from pathlib import Path
from unittest.mock import patch

from api.history_db import IncidentHistoryDB
from api import server


class ApiLogicTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path("tests/.tmp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_dir / f"{uuid.uuid4().hex}.db"
        self.db = IncidentHistoryDB(str(self.db_path))

    def tearDown(self):
        self.db._conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_approve_incident_executes_scale_action(self):
        self.db.log_incident(
            incident_id="inc-1",
            service_name="checkout",
            alert_name="cpu high",
            proposed_action={
                "tool": "scale_deployment",
                "parameters": {
                    "service_name": "checkout",
                    "target_replicas": 6,
                    "namespace": "prod",
                },
            },
        )

        with patch.object(server, "db", self.db), patch.object(server, "executor") as executor_mock:
            executor_mock.execute.return_value = {
                "success": True,
                "tool": "scale_deployment",
                "result": {"success": True, "message": "scaled"},
            }
            response = server.approve_incident("inc-1")

        self.assertEqual(response["status"], "executed")
        self.assertEqual(response["tool"], "scale_deployment")
        executor_mock.execute.assert_called_once()
        incident = self.db.get_incident("inc-1")
        self.assertEqual(incident["status"], "executed")

    def test_approve_incident_marks_failure_for_non_executable_action(self):
        self.db.log_incident(
            incident_id="inc-2",
            service_name="checkout",
            alert_name="unknown issue",
            proposed_action={"tool": "noop_require_human", "parameters": {}},
        )

        with patch.object(server, "db", self.db), patch.object(server, "executor") as executor_mock:
            executor_mock.execute.return_value = {
                "success": False,
                "tool": "noop_require_human",
                "message": "No executable action proposed. Escalate to human.",
            }
            response = server.approve_incident("inc-2")

        self.assertEqual(response["status"], "execution_failed")
        incident = self.db.get_incident("inc-2")
        self.assertEqual(incident["status"], "execution_failed")

    def test_get_incident_includes_validation_summary_from_artifact(self):
        report_dir = self.temp_dir / "incident-artifacts"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "report.md"
        report_path.write_text("# report\n", encoding="utf-8")
        (report_dir / "validation.json").write_text(
            json.dumps({"schema_score": 0.75, "invalid_nodes": ["critic"]}),
            encoding="utf-8",
        )
        self.db.log_incident(
            incident_id="inc-3",
            service_name="checkout",
            alert_name="schema issue",
            proposed_action={"tool": "noop_require_human", "parameters": {}},
            report_path=str(report_path),
        )

        with patch.object(server, "db", self.db):
            response = server.get_incident("inc-3")

        self.assertEqual(response["data"]["validation_summary"]["schema_score"], 0.75)
        self.assertEqual(response["data"]["validation_summary"]["invalid_nodes"], ["critic"])


if __name__ == "__main__":
    unittest.main()
