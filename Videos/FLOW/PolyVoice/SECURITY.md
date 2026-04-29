# Security Policy

## Supported versions

PolyVoice is in pre-alpha. Security fixes are applied to `main` only until the first stable release.

| Version | Supported          |
|---------|--------------------|
| `main`  | :white_check_mark: |
| `0.x`   | :x: (use `main`)   |

After v1.0, supported versions and a security backport policy will be documented here.

## Reporting a vulnerability

**Please do not file public GitHub issues for security problems.**

Email: `security@netoai.org`

Include:
- A description of the issue and its impact
- Steps to reproduce (or a proof of concept)
- The version / commit hash of the code you tested
- Whether the issue affects production deployments or only local dev
- Whether you'd like credit (and how) when disclosed

You can encrypt your report with our PGP key (published at `https://netoai.org/.well-known/security.txt` once available; until then, contact the address above for the key).

## Response process

We aim for:
- **Acknowledgment** within 48 hours of receipt
- **Initial triage** within 5 business days
- **Fix or mitigation** within 30 days for high-severity issues, 90 days for moderate, best-effort for low

We will coordinate disclosure timing with you. We support a **standard 90-day disclosure window** after a fix is available, unless you and we agree otherwise.

## Scope

In scope:
- Vulnerabilities in PolyVoice source code
- Vulnerabilities in our published Docker images, Helm charts, and reference deploy artifacts
- Vulnerabilities introduced by supply-chain dependencies that we pin or vendor

Out of scope:
- Vulnerabilities in upstream services or providers (Twilio, FreeSWITCH, vLLM, etc.) — please report those upstream
- Configuration mistakes in user deployments (we'll harden defaults; misconfiguration of a downstream deployment is the operator's responsibility)
- Issues only reproducible with `polyvoice` running with `DEBUG=true` or in non-default unsafe modes

## Hall of fame

Coordinated disclosures will be credited here once they happen.

## What "compliance-ready" does and does not mean

PolyVoice ships **HIPAA-mode** and **PCI-mode** configuration profiles in v0.2+. These profiles harden defaults (audit logging, data residency, no telemetry to third parties). They are necessary but not sufficient for compliance: your deployment, your hosting environment, your BAA with vendors, and your operational practices are all part of compliance and are out of our control. Refer to `docs/compliance/` (lands Sprint 5) for the full deployment checklist.
