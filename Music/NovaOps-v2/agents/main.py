"""NovaOps v2 — Main entry point.

Usage:
    python -m agents.main "OOM alert on payment-service in production"
"""

import sys
import logging
from datetime import datetime

from agents.graph import build_war_room
from agents.artifacts import (
    build_validation_summary,
    create_investigation,
    persist_graph_artifacts,
    save_report,
)
from agents.schemas import parse_remediation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("novaops")


def _extract_action_from_text(text: str) -> dict:
    """Parse remediation action from text. Used by eval runner too."""
    plan = parse_remediation(text)
    return plan.to_action_dict()


def run(alert_text: str) -> dict:
    """Run the full war room investigation pipeline."""
    print(f"\n{'='*60}")
    print(f"  NovaOps v2 — Autonomous SRE War Room")
    print(f"  Alert: {alert_text}")
    print(f"  Time: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Create investigation directory
    incident_id = create_investigation(alert_text)
    print(f"[*] Investigation ID: {incident_id}")

    # Build the multi-agent graph
    print("[*] Building war room graph...")
    graph, domain = build_war_room(alert_text)
    print(f"[*] Domain: {domain}")

    # Run the graph
    print("[*] Starting investigation...\n")
    graph_result = graph(alert_text)
    node_texts, war_room = persist_graph_artifacts(incident_id, graph_result)

    # Extract result using typed schemas
    proposed_action = war_room.proposed_action()
    result_text = war_room.summary_text()
    validation_summary = build_validation_summary(node_texts, war_room)

    if not result_text:
        result_text = str(graph_result)

    # Fallback: if schema parsing didn't find an action, try raw text
    if proposed_action.get("tool") == "noop_require_human" and result_text:
        fallback = parse_remediation(result_text)
        if fallback.is_valid():
            proposed_action = fallback.to_action_dict()

    print(f"\n{'='*60}")
    print(f"  Investigation Complete")
    print(f"{'='*60}")
    print(f"\n{result_text[:2000]}\n")

    # Save report
    report_path = save_report(
        incident_id,
        domain,
        alert_text,
        result_text,
        validation_summary=validation_summary,
    )
    print(f"[*] Report saved: {report_path}")

    return {
        "incident_id": incident_id,
        "domain": domain,
        "result": result_text[:5000],
        "proposed_action": proposed_action,
        "validation_summary": validation_summary,
        "report_path": report_path,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m agents.main \"<alert description>\"")
        print("Example: python -m agents.main \"OOM alert on payment-service\"")
        sys.exit(1)

    alert_text = " ".join(sys.argv[1:])
    run(alert_text)


if __name__ == "__main__":
    main()
