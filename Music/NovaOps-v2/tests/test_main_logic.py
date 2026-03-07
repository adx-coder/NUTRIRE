import unittest

from agents.main import _extract_action_from_text
from agents.schemas import parse_remediation


class MainLogicTests(unittest.TestCase):
    def test_parse_remediation_prefers_tool_field(self):
        plan = parse_remediation('{"tool": "restart_pods", "parameters": {"service_name": "api"}}')
        self.assertEqual(plan.to_action_dict(), {"tool": "restart_pods", "parameters": {"service_name": "api"}})

    def test_extract_action_from_json_text(self):
        action = _extract_action_from_text(
            '{"action_taken":"scale_deployment","parameters":{"service_name":"checkout","target_replicas":4}}'
        )
        self.assertEqual(action["tool"], "scale_deployment")
        self.assertEqual(action["parameters"]["target_replicas"], 4)

    def test_extract_action_from_embedded_json_preserves_parameters(self):
        action = _extract_action_from_text(
            'Recommended action: {"action_taken":"rollback_deployment","parameters":{"service_name":"checkout"}}'
        )
        self.assertEqual(
            action,
            {"tool": "rollback_deployment", "parameters": {"service_name": "checkout"}},
        )

    def test_extract_action_defaults_to_noop_when_missing(self):
        action = _extract_action_from_text("no remediation proposed")
        self.assertEqual(action, {"tool": "noop_require_human", "parameters": {}})

    def test_parse_remediation_rejects_unknown_tool(self):
        plan = parse_remediation('{"action_taken": "delete_cluster", "parameters": {"service_name": "api"}}')
        self.assertEqual(plan.action_taken, "noop_require_human")


if __name__ == "__main__":
    unittest.main()
