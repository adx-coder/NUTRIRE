# NovaOps v2

NovaOps v2 is a multi-agent incident response system built for the Amazon Nova hackathon track. It investigates alerts with specialist agents, validates the reasoning path, proposes safe remediation, and stores a full filesystem-first audit trail for demo and review.

## Current State

- Multi-agent graph orchestration with triage, analysts, reasoner, critic, and remediation planner
- Typed schema validation for agent outputs
- Ghost Mode approval before remediation execution
- Local knowledge retrieval by default for hackathon-safe cost control
- Investigation artifacts written to `plans/{incident_id}/`
- Evaluation harness with scenario-based scoring
- Test suite covering parsing, execution, artifacts, API flow, and retrieval mode

## Repository Layout

- `agents/`: orchestration, prompts, schemas, artifacts, PIR generation
- `aggregator/`: log, metric, Kubernetes, and GitHub data fetchers
- `tools/`: tool wrappers, executor, knowledge retrieval
- `api/`: FastAPI server, history database, Slack notifier
- `evaluation/`: scenarios and runner
- `skills/`: shared and domain-specific playbooks
- `plans/`: generated investigation outputs
- `runbooks/`: learned PIR content
- `tests/`: unit tests

## Quick Start

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python -m agents.main "OOM alert on payment-service"
```

## Hackathon Defaults

The project is set up to avoid unnecessary managed-service spend:

- `HACKATHON_MODE=true`
- `NOVAOPS_USE_MOCK=true` by default in `.env.example`
- local TF-IDF knowledge retrieval is preferred unless you explicitly opt into managed Bedrock KB usage

The managed setup helper in `scripts/setup_bedrock_kb.py` requires `--allow-managed-kb`.

## Run Tests

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Main Artifacts

Each run creates a folder under `plans/` containing:

- `report.md`
- `structured.json`
- `validation.json`
- `trace.json`
- `findings/*.json`

These files are intended to be demoable and inspectable without needing a debugger.
