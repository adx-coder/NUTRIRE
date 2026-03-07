# NovaOps v2 - Working Plan

## Goal

Ship a hackathon-ready incident response demo that is reliable, low-cost, and easy to explain.

## Completed

- Built the multi-agent graph and specialist prompts
- Added schema validation for agent outputs
- Separated remediation planning from execution
- Added Ghost Mode approval and executor policy
- Added artifact persistence with structured output and validation summaries
- Added local knowledge retrieval with hackathon-safe defaults
- Added test coverage across parsing, execution, artifacts, API flow, and retrieval mode

## Next Steps

1. Repo cleanup and doc alignment
   - Normalize top-level docs
   - Remove outdated claims from working notes
   - Keep architecture description consistent with current code

2. Demo UX
   - Surface schema validation in the dashboard
   - Show artifact output clearly
   - Keep the incident flow easy to follow live

3. Submission prep
   - Freeze the architecture story
   - Record demo-friendly scenario runs
   - Prepare final README and demo checklist

## Non-Goals For Now

- Full managed Bedrock Knowledge Base rollout
- Production-grade infrastructure automation
- Broad new feature work beyond demo readiness
