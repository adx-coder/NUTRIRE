"""Multi-agent war room graph - Strands GraphBuilder orchestration.

Flow:
  Triage -> (LogAnalyst + MetricsAnalyst + K8sInspector + GitHubAnalyst) [parallel]
         -> RootCauseReasoner -> Critic
         -> if PASS: RemediationPlanner
         -> if FAIL: back to analysts (max 3 loops)
"""

import json
import logging
import re
from typing import Any

from strands import Agent
from strands.multiagent import GraphBuilder

from agents.models import get_model
from agents.prompts import (
    CRITIC_PROMPT,
    GITHUB_ANALYST_PROMPT,
    K8S_INSPECTOR_PROMPT,
    LOG_ANALYST_PROMPT,
    METRICS_ANALYST_PROMPT,
    remediation_prompt,
    root_cause_prompt,
    triage_prompt,
)
from agents.skills import (
    classify_domain,
    get_all_skill_summaries,
    load_analyst_skill,
    load_remediation_skill,
    load_shared_skill,
)
from tools.investigation import INVESTIGATION_TOOLS
from tools.retrieve_knowledge import retrieve_knowledge

logger = logging.getLogger(__name__)

MAX_REFLECTION_LOOPS = 3


class SilentCallbackHandler:
    """Callback handler that suppresses noisy stdout on Windows terminals."""

    def __init__(self):
        self.tool_count = 0

    def __call__(self, **kwargs: Any) -> None:
        tool_use = kwargs.get("event", {}).get("contentBlockStart", {}).get("start", {}).get("toolUse")
        if tool_use:
            self.tool_count += 1
            logger.info(f"Tool #{self.tool_count}: {tool_use['name']}")


def _get_critic_text(state) -> str:
    """Safely extract text from the critic node's result."""
    try:
        node_result = state.results.get("critic")
        if node_result is None:
            return ""

        agent_result = node_result.result
        msg = getattr(agent_result, "message", None)
        if msg is None:
            return str(agent_result).lower()

        if isinstance(msg, dict):
            content = msg.get("content", [])
        else:
            content = getattr(msg, "content", [])

        texts = []
        for block in (content if isinstance(content, list) else []):
            if isinstance(block, dict) and "text" in block:
                texts.append(str(block["text"]))
            elif isinstance(block, str):
                texts.append(block)

        return " ".join(texts).lower() if texts else str(agent_result).lower()
    except Exception as exc:
        logger.error(f"Failed to extract critic result: {exc}")
        return ""


def _parse_verdict(result_text: str) -> str:
    """Parse critic verdict text. Returns PASS, FAIL, or UNKNOWN."""
    if not result_text:
        return "UNKNOWN"

    raw_text = result_text
    text = result_text.lower()

    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(raw_text[start : end + 1])
            verdict = str(parsed.get("verdict", "")).upper()
            if verdict in {"PASS", "FAIL"}:
                return verdict
    except Exception:
        pass

    if re.search(r"\bverdict\b[:\s]*\bpass\b", text):
        return "PASS"
    if re.search(r"\bverdict\b[:\s]*\bfail\b", text):
        return "FAIL"
    return "UNKNOWN"


def _critic_passed(state) -> bool:
    """Condition: critic approved hypothesis -> proceed to remediation planning."""
    verdict = _parse_verdict(_get_critic_text(state))
    if verdict == "PASS":
        return True

    loop_count = state.invocation_state.get("reflection_loops", 0)
    if loop_count >= MAX_REFLECTION_LOOPS:
        logger.warning(
            f"Max reflection loops ({MAX_REFLECTION_LOOPS}) reached with verdict={verdict}. "
            "Proceeding to remediation planning with escalation bias."
        )
        return True

    return False


def _critic_failed(state) -> bool:
    """Condition: critic rejected -> loop back to analysts if under max loops."""
    verdict = _parse_verdict(_get_critic_text(state))
    if verdict == "PASS":
        return False

    loop_count = state.invocation_state.get("reflection_loops", 0)
    if loop_count >= MAX_REFLECTION_LOOPS:
        return False

    state.invocation_state["reflection_loops"] = loop_count + 1
    logger.info(f"Critic rejected ({verdict}). Reflection loop {loop_count + 1}/{MAX_REFLECTION_LOOPS}")
    return True


def build_war_room(alert_text: str) -> tuple:
    """Build the multi-agent graph for investigating an incident.

    Returns (graph, domain) - call graph(alert_text) to run.
    """
    domain = classify_domain(alert_text)
    logger.info(f"Domain classified: {domain}")

    skill_summaries = get_all_skill_summaries()
    triage_skill = load_shared_skill("triage") or ""
    analyst_skill = load_analyst_skill(domain) or ""
    remed_skill = load_remediation_skill(domain) or ""

    model_low = get_model("LOW")
    model_med = get_model("MEDIUM")
    model_high = get_model("HIGH")

    handler = SilentCallbackHandler()

    triage_agent = Agent(
        name="triage",
        system_prompt=triage_prompt(skill_summaries, triage_skill),
        model=model_low,
        tools=INVESTIGATION_TOOLS,
        callback_handler=handler,
    )

    log_analyst = Agent(
        name="log_analyst",
        system_prompt=LOG_ANALYST_PROMPT,
        model=model_med,
        tools=INVESTIGATION_TOOLS,
        callback_handler=handler,
    )

    metrics_analyst = Agent(
        name="metrics_analyst",
        system_prompt=METRICS_ANALYST_PROMPT,
        model=model_med,
        tools=INVESTIGATION_TOOLS,
        callback_handler=handler,
    )

    k8s_inspector = Agent(
        name="k8s_inspector",
        system_prompt=K8S_INSPECTOR_PROMPT,
        model=model_med,
        tools=INVESTIGATION_TOOLS,
        callback_handler=handler,
    )

    github_analyst = Agent(
        name="github_analyst",
        system_prompt=GITHUB_ANALYST_PROMPT,
        model=model_med,
        tools=INVESTIGATION_TOOLS,
        callback_handler=handler,
    )

    root_cause_reasoner = Agent(
        name="root_cause_reasoner",
        system_prompt=root_cause_prompt(analyst_skill),
        model=model_high,
        tools=[retrieve_knowledge],
        callback_handler=handler,
    )

    critic = Agent(
        name="critic",
        system_prompt=CRITIC_PROMPT,
        model=model_low,
        tools=[],
        callback_handler=handler,
    )

    remediation_planner = Agent(
        name="remediation_planner",
        system_prompt=remediation_prompt(remed_skill),
        model=model_med,
        # Ghost Mode safety: planner proposes action only, retrieve_knowledge is read-only.
        tools=[retrieve_knowledge],
        callback_handler=handler,
    )

    builder = GraphBuilder()

    builder.add_node(triage_agent, "triage")
    builder.add_node(log_analyst, "log_analyst")
    builder.add_node(metrics_analyst, "metrics_analyst")
    builder.add_node(k8s_inspector, "k8s_inspector")
    builder.add_node(github_analyst, "github_analyst")
    builder.add_node(root_cause_reasoner, "root_cause_reasoner")
    builder.add_node(critic, "critic")
    builder.add_node(remediation_planner, "remediation_planner")

    builder.add_edge("triage", "log_analyst")
    builder.add_edge("triage", "metrics_analyst")
    builder.add_edge("triage", "k8s_inspector")
    builder.add_edge("triage", "github_analyst")

    builder.add_edge("log_analyst", "root_cause_reasoner")
    builder.add_edge("metrics_analyst", "root_cause_reasoner")
    builder.add_edge("k8s_inspector", "root_cause_reasoner")
    builder.add_edge("github_analyst", "root_cause_reasoner")

    builder.add_edge("root_cause_reasoner", "critic")

    builder.add_edge("critic", "remediation_planner", condition=_critic_passed)
    builder.add_edge("critic", "log_analyst", condition=_critic_failed)
    builder.add_edge("critic", "metrics_analyst", condition=_critic_failed)
    builder.add_edge("critic", "k8s_inspector", condition=_critic_failed)
    builder.add_edge("critic", "github_analyst", condition=_critic_failed)

    builder.set_entry_point("triage")
    builder.set_execution_timeout(600)
    builder.set_max_node_executions(30)

    graph = builder.build()
    return graph, domain
