# NovaOps v2

**Autonomous multi-agent SRE war room powered by Amazon Nova 2 Lite.**

NovaOps v2 responds to production alerts end-to-end: it triages the incident, dispatches four specialist analysts in parallel, reasons over their findings, validates the reasoning path with an adversarial critic, proposes a remediation action, and gates that action through a policy engine before any execution touches infrastructure. Every decision is logged to an append-only audit trail. Human override is always available.

Built for the Amazon Nova AI Hackathon 2026.

---

## How It Works

```
Alert
  |
  v
Triage Agent          -- classifies domain, severity (P1-P4), service
  |
  +-- Log Analyst -------+
  +-- Metrics Analyst ---|-- run in parallel
  +-- K8s Inspector  ----|
  +-- GitHub Analyst ----+
  |
  v
Root Cause Reasoner   -- synthesises findings, forms ranked hypotheses
  |
  v
Critic Agent          -- adversarial review; can reject and loop (max 3x)
  |
  v
Remediation Planner   -- proposes one of: rollback / scale / restart / noop
  |
  v
Governance Gate       -- evaluates risk score + policy; ALLOW_AUTO | REQUIRE_APPROVAL | DENY
  |
  v
Executor              -- runs remediation tool (or waits for human approval)
```

All agent outputs are validated against typed schemas and written to `plans/{incident_id}/` as inspectable JSON artifacts.

---

## Governance

Every proposed remediation passes through a policy engine before execution.

**Risk score (0-100):**
- Action weight: rollback=40, restart=20, scale=15, noop=0
- Severity weight: P1=30, P2=20, P3=10, P4=5
- Confidence penalty: `max(0, (0.75 - confidence) * 40)` for low-confidence decisions

**Policy decisions (first match wins, evaluated in priority order):**

| Policy | Condition | Decision |
|---|---|---|
| noop_requires_approval | action=noop | REQUIRE_APPROVAL |
| p1_always_requires_approval | severity=P1 | REQUIRE_APPROVAL |
| rollback_always_requires_approval | action=rollback | REQUIRE_APPROVAL |
| low_confidence_escalate | confidence < 0.65 | REQUIRE_APPROVAL |
| high_confidence_p3_p4_auto | P3/P4 + restart/scale + conf >= 0.75 | ALLOW_AUTO |
| p2_scale_high_confidence | P2 + scale + conf >= 0.85 | ALLOW_AUTO |
| default_require_approval | (catch-all) | REQUIRE_APPROVAL |

**Confidence precedence (deterministic):**
`critic.confidence > root_cause.confidence_overall > top_hypothesis.confidence > 0.0`

**Artifacts written per incident:**
- `governance.json` — full decision record
- `governance_report.md` — human-readable summary with risk bar and audit table
- `audit.jsonl` — append-only event log (TRIAGE_COMPLETE, HYPOTHESIS_FORMED, CRITIC_VERDICT, GOVERNANCE_DECISION, EXECUTION_STARTED, EXECUTION_COMPLETE, HUMAN_OVERRIDE, ...)

---

## Repository Layout

```
agents/         orchestration graph, prompts, schemas, artifacts, PIR generation
aggregator/     log, metric, Kubernetes, and GitHub data fetchers (live + mock)
api/            FastAPI server, SQLite history DB, Slack notifier, PagerDuty webhook
governance/     GovernanceGate, PolicyEngine, AuditLog, report generator
tools/          tool wrappers, RemediationExecutor, knowledge retrieval
evaluation/     15 scenario harness covering 6 failure domains
skills/         domain playbooks (oom, traffic_surge, deadlock, config_drift, ...)
runbooks/       learned PIR content for RAG
plans/          generated investigation artifacts (git-ignored)
tests/          37 unit tests
```

---

## Quick Start

```bash
python -m venv venv
source venv/Scripts/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Run in fully offline mock mode (no Bedrock spend)
NOVAOPS_USE_MOCK=1 python -m agents "P2 OOM alert on payment-service in prod"
```

### Live mode (Amazon Nova 2 Lite on Bedrock)

```bash
export AWS_DEFAULT_REGION=us-east-2
export AWS_BEARER_TOKEN_BEDROCK=<your-token>
export NOVAOPS_USE_MOCK=0
python -m agents "P2 traffic surge on checkout-service in prod"
```

### API server

```bash
uvicorn api.server:app --reload
# POST /api/webhook/pagerduty  — trigger investigation
# GET  /api/incidents/{id}     — fetch status + artifacts
# POST /api/incidents/{id}/approve  — human approval → governance gate → execution
# GET  /api/governance/{id}/decision
# GET  /api/governance/{id}/audit
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NOVAOPS_USE_MOCK` | `true` | Offline mode — no Bedrock calls |
| `NOVA_MODEL_ID` | `us.amazon.nova-2-lite-v1:0` | Bedrock inference profile |
| `AWS_DEFAULT_REGION` | `us-east-1` | Bedrock region |
| `AWS_BEARER_TOKEN_BEDROCK` | — | Bearer token for Bedrock access |
| `HACKATHON_MODE` | `false` | Alias for mock mode |
| `SLACK_WEBHOOK_URL` | — | Ghost Mode approval notifications |
| `USE_BEDROCK_KB` | `false` | Use managed Bedrock Knowledge Bases for RAG |

---

## Evaluation

```bash
python -m evaluation --list          # show all 15 scenarios
python -m evaluation --scenario 1    # run one scenario
python -m evaluation --domain oom    # run all OOM scenarios
python -m evaluation --all           # run full suite
```

Scenarios cover: `oom`, `traffic_surge`, `deadlock`, `config_drift`, `dependency_failure`, `cascading_failure`.

---

## Tests

```bash
python -m unittest discover -s tests -v
# 37 tests, < 1s
```

---

## Artifacts

Each investigation writes to `plans/{incident_id}/`:

| File | Contents |
|---|---|
| `report.md` | Full investigation report |
| `governance.json` | Policy decision, risk score, confidence |
| `governance_report.md` | Human-readable governance summary |
| `audit.jsonl` | Append-only event log |
| `structured.json` | Typed agent outputs |
| `validation.json` | Schema validation scores |
| `trace.json` | Failure metadata (if investigation failed) |
| `findings/*.json` | Per-agent structured findings |
| `plan.md` | Investigation plan (updated to COMPLETED) |
