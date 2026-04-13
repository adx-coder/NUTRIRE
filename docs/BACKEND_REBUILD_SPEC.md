# Nutrire — Backend Rebuild Spec

> **Audience:** Nutrire backend team.
> **Purpose:** Full rebuild specification. Replaces the current `pipeline/` design with an LLM-first agentic extraction layer feeding a 20-source data fusion cube.
> **Status:** Draft, to be iterated with the frontend team.

---

## Contents

1. [Why we're rebuilding](#why-were-rebuilding)
2. [What we have now (honest audit)](#what-we-have-now-honest-audit)
3. [The new architecture, in one picture](#the-new-architecture-in-one-picture)
4. [Source plan — what we keep, cut, add](#source-plan--what-we-keep-cut-add)
5. [The agentic extraction layer](#the-agentic-extraction-layer)
6. [The data fusion layer](#the-data-fusion-layer)
7. [The accessibility cube](#the-accessibility-cube)
8. [Output JSON contracts](#output-json-contracts)
9. [Implementation phases](#implementation-phases)
10. [Deprecations](#deprecations)
11. [Evaluation + success metrics](#evaluation--success-metrics)
12. [Appendix: prompt texts](#appendix-prompt-texts)

---

## Why we're rebuilding

We're not rebuilding because the current pipeline is bad. It's architecturally clean — 9 stages, delta detection, committed cache, typed records, tool-use enum constraints. The engineering is solid.

We're rebuilding because **the pipeline is optimizing for the wrong metric**. Nutrire is a UX + research challenge, not a data ingestion challenge. The current pipeline:

1. **Ships 23 sources but produces signal from 5–6.** The rest are portal homepages, stale PDFs, national aggregate dashboards, and wrong-use-case datasets (EPA landfill, USDA SNAP retailer).
2. **Uses LLMs for tag classification only.** The Anthropic Haiku call in `llm_enricher.py` asks "which of these 28 enum values apply?" — a task a 2017 CRF could do. The LLM's actual strengths (semantic extraction from messy unstructured text, confidence scoring, cultural context, multilingual handling, warm copy) are untouched.
3. **Has a silent bug in the census lookup.** `enrich_insecurity` picks the max-insecurity county in the state as the tract value for every org, so within-state food insecurity is a constant. The claimed "per-tract" data is per-state.
4. **Doesn't produce the semantic fields the UI needs.** No `firstVisitGuide`, no `plainEligibility`, no `heroCopy`, no `culturalNotes`, no `embedding`. The UI has to fabricate these or stay flat.
5. **Regex parses hours.** 140 lines of `normalize.py` heuristics miss "1st Saturday of month," "By appointment," bilingual hours, and half the real-world formats.
6. **Doesn't fuse geospatial sources meaningfully.** Transit is nearest-stop haversine (not walking distance, not multi-agency, not schedule-aware). Food desert is DC Open Data only (no MD or VA). No CDC SVI. No OSM routing. No temporal accessibility.

The result is a pipeline that produces **plausible-looking records** that fall apart the moment a judge asks "how does Langley Park compare to Bethesda in your ranking?" We need the pipeline to produce **demonstrably novel signals** that no other tool in this space has.

---

## What we have now (honest audit)

### Stage 1 — Watch

**What it does:** `agents/watcher.py` checks each source for content-hash or HTTP-header changes. Delta detection is legit.

**Keeps working after rebuild:** yes, with minor config updates.

### Stage 2 — Scrape

**Scrapers:** `cafb`, `mdfb`, `two11md`, `mocofood`, `pgcfec`, `caroline`, `generic_html`, `generic_pdf`.

**Problem:** only ~8 scrapers for 23 source entries. The rest fall through to `generic_html` which, when pointed at a Socrata portal homepage, extracts nothing.

**What happens in rebuild:** we consolidate to ~10 real scrapers that actually produce records. `generic_html` becomes a fallback with LLM-first extraction (not regex).

### Stage 3 — Normalize

**What it does:** `normalizers/normalize.py` cleans name, phone, address, runs regex classifiers for services/food_types/requirements/languages, parses hours via regex, computes reliability decay.

**Problems:**

- `parse_hours_structured` is 140 lines of regex heuristics with a silent bug ("bare number 1-7 treated as PM")
- Classifiers are regex lookups against English keywords only (no native script support)
- No confidence scoring
- No evidence grounding
- `hours_structured` fails silently and returns None for anything unusual

**What happens in rebuild:** `normalize.py` shrinks to ~40 lines of pure deterministic cleanup (phone format, address whitespace, name title-case, reliability decay). All extraction responsibilities move to the agentic layer.

### Stage 3b — LLM enrich

**What it does:** `utils/llm_enricher.py` sends each record's `raw_text` to Claude Haiku with a tool-use schema that enforces enum classifications. Merges results with existing regex tags (union, never removes).

**What's good:**

- Cache-first by `md5(raw_text)`
- Enum-constrained tool schema prevents hallucinated categories
- Graceful fallback when no API key (uses cache only)

**What's missing:**

- LLM only does classification, not extraction
- No semantic copy generation (firstVisitGuide, plainEligibility, etc.)
- No confidence scoring
- No evidence grounding
- No multi-model routing (Haiku only)

**What happens in rebuild:** `llm_enricher.py` is deleted. Its functionality is absorbed into the 4-agent pipeline under `agents/` — where classification becomes a side-effect of the main extraction call, not a separate stage.

### Stage 4 — Geocode

**What it does:** `utils/geocoder.py` calls Nominatim. Fine, keeps working.

### Stage 5 — Transit

**What it does:** `utils/transit.py` fetches WMATA rail stations + bus stops, does haversine per-org to find the nearest stop within 5 km. Caches 30 days.

**Problems:**

- Haversine ≠ walking distance
- Only WMATA (no Ride On, TheBus, DC Circulator, MARC, VRE)
- Nearest-stop only (ignores frequency, ignores alternatives)
- No user-to-org transit time (the signal is only org-to-nearest-stop)
- Bus coverage bounded by 6 hardcoded BUS_CENTERS → holes in coverage

**What happens in rebuild:** replaced by a multi-agency GTFS-based transit graph with real schedules. See [Fusion 2](#fusion-2--multi-agency-transit-schedule-graph).

### Stage 6 — Food insecurity (Census)

**What it does:** `utils/food_insecurity.py` fetches ACS 5-year tract data for DMV counties, computes per-tract insecurity scores.

**Problems:**

- Fetching the data is correct. The lookup is broken.
- `enrich_insecurity` maps ZIP prefix → state, then picks the max-insecurity county in the state and assigns its average to every org in the state
- `tract_id` stored is `"{state}{county}_avg"` — a synthetic ID, not a real FIPS
- Within a state, every org has the same `tract_insecurity_score`

**What happens in rebuild:** replaced with TIGER spatial join + per-tract assignment. See [Fusion 8](#fusion-8--real-tract-lookup-svi--lila-composite).

### Stage 6b — Food access zones

**What it does:** `utils/food_access.py` fetches DC Open Data food desert polygons, does point-in-polygon per org.

**What's good:** the spatial join is real.

**Problem:** DC Open Data only. MD and VA orgs never get `is_food_desert: True` even if they sit in a federally-designated USDA LILA tract.

**What happens in rebuild:** extended to national USDA Food Access Research Atlas CSV. MD and VA orgs finally get correct food desert flags.

### Stage 7 — Entity resolution

**What it does:** `resolvers/entity_resolver.py` dedupes by name similarity, name+ZIP match, phone match, or token overlap + same ZIP.

**Problem:** phone-based dedup over-merges when orgs share a central helpline.

**What happens in rebuild:** phone-based dedup disabled. Replaced with name+address fuzzy match + confidence-weighted merging. See [Phase 5](#phase-5--entity-resolution-fix).

### Stage 8 — Corrections + scoring

**What it does:** `corrections/merger.py` applies manual fixes and user feedback, `scoring.py` computes `priorityScore`.

**Problem:** `priorityScore` weights 20% on the broken insecurity signal, making it effectively a per-state constant. Real signal is ~57% reliability + 43% transit.

**What happens in rebuild:** `priorityScore` is rewritten to be replaced by a per-user ranking function that uses fused signals from the data cube, not a single static score. See [Fusion 3](#fusion-3--temporal-linguistic-dignity-accessibility-index-tldai).

### Stage 9 — Export

**What it does:** `graph/exporter.py` writes 5 JSON files + copies them to `frontend/public/data/`.

**What's good:** the file set (organizations, locations, graph, metadata, events, delta) is correct. We extend it, we don't replace it.

**What we add:** `insights.json` (equity gap + recommendations), `access-cube.json` (the accessibility cube).

### Stage 9b — Neo4j

**What it does:** `graph/builder.py` writes the same data to a Neo4j instance.

**Problem:** Neo4j is never consumed by the frontend. `exporter.py` already writes `graph.json` from the records directly. Neo4j is pure dead weight with zero downstream value, and the try/except means the pipeline silently no-ops when Neo4j isn't running.

**What happens in rebuild:** **deleted.** Remove `graph/builder.py`, remove the `create_driver` + `build_graph` calls from `orchestrator.py`. Save everyone ~500 lines of code and one infrastructure dependency.

---

## The new architecture, in one picture

```
  ┌────────────────────────────────────────────────────────────────────┐
  │                         EXTERNAL SOURCES (20)                      │
  │                                                                    │
  │  Supply (5)   Demand (4)   Routing (4)   Shocks (3)   Verify (2)   │
  │  Anchors (2)                                                       │
  └────────────────────────────┬───────────────────────────────────────┘
                               │
      ┌────────────────────────┼────────────────────────┐
      │                        │                        │
      ▼                        ▼                        ▼
  ┌───────┐              ┌───────────┐            ┌────────────┐
  │Watcher│              │ Static DL │            │ Live API   │
  │(delta)│              │ (ACS/LILA/│            │ (NOAA/BLS) │
  │       │              │  SVI/OSM) │            │            │
  └───┬───┘              └─────┬─────┘            └──────┬─────┘
      │                        │                        │
      └────────────────────────┼────────────────────────┘
                               ▼
               ┌───────────────────────────────┐
               │    Agentic Extraction Layer    │
               │                                │
               │    Planner → Extractor →       │
               │         Critic → (Refiner) →   │
               │              Enricher          │
               │                                │
               │    ↓ NormalizedRecord[]        │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │    Data Fusion Layer           │
               │                                │
               │  • TIGER spatial join          │
               │  • USDA LILA + CDC SVI         │
               │  • OSM walking routes          │
               │  • Multi-agency GTFS           │
               │  • Multi-source hours merge    │
               │  • NOAA weather overlay        │
               │  • BLS + SNAP demand forecast  │
               │  • Cultural match scoring      │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │    Accessibility Cube          │
               │                                │
               │  (orgs × tracts × hours        │
               │   × languages × dignity)       │
               │                                │
               │  Computed once, cached.        │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │    Exporter                    │
               │                                │
               │  frontend/public/data/         │
               │   • organizations.json         │
               │   • locations.json             │
               │   • graph.json                 │
               │   • insights.json (gap+recs)   │
               │   • access-cube.json           │
               │   • metadata.json              │
               │   • delta-latest.json          │
               └───────────────────────────────┘
```

---

## Source plan — what we keep, cut, add

### Keep (5 sources — the real DMV supply backbone)

| ID | What it gives | Role |
|---|---|---|
| `cafb` | ~400 DMV pantries, highest quality | Primary supply |
| `mdfb-find-food` | ~280 MD orgs | MD coverage |
| `two11md` | ~100 orgs with social-service context | Supply + cross-refs |
| `mocofood` | ~100 orgs, best filter taxonomy | Supply + dignity signals |
| `pgcfec` | ~80 orgs in underserved PG tracts | Equity coverage |

**Deduped expected: ~500 unique DMV orgs.**

### Cut (18 sources — fluff that produces no usable signal)

| ID | Why cut |
|---|---|
| `mdfb-hunger-map` | Duplicate of `mdfb-find-food` |
| `two11md-alt` | Duplicate of `two11md` |
| `caroline` | Caroline County is not metro DMV |
| `feeding-america` | National aggregate dashboard, no extractable org data |
| `mda-insecurity-map` | MD Dept of Ag insecurity map, aggregate only |
| `usda-food-atlas` | Aggregate census atlas, we pull the CSV directly instead |
| `pg-healthy-food` | ArcGIS dashboard, not scrapable |
| `md-open-data` | Portal homepage, zero orgs extracted |
| `dc-open-data` | Portal homepage |
| `va-open-data` | Portal homepage |
| `pg-open-data` | Portal homepage |
| `md-compass` | Generic business map, not pantry-specific |
| `umd-extension` | Thin page, occasional links |
| `epa-excess-food` | Food WASTE, wrong use case |
| `epa-landfill` | Literally landfill data |
| `usda-snap` | SNAP retailers (stores), not free-food pantries |
| `kofc-pdf` | 2019 PDF, stale |
| `msa-pdf` | 2012 PDF, very stale |

**Rationale:** each of these either (a) doesn't produce org-level records, (b) produces stale or wrong-use-case data, or (c) is a duplicate. Cutting them simplifies the pipeline, reduces surface area for bugs, and focuses effort on the 5 sources that actually carry the product.

### Add (8 new sources for fusion)

| New source | What it gives | Fusion role |
|---|---|---|
| **TIGER/Line 2022 tract shapefiles** | Real DMV tract polygons | Spatial join (replaces ZIP hack) |
| **USDA Food Access Research Atlas 2019 CSV** | Tract-level LILA flags for the entire US | MD + VA food desert detection |
| **CDC Social Vulnerability Index 2022** | Tract-level composite SVI (4 themes) | Secondary vulnerability lens |
| **WMATA GTFS feed** | Full WMATA schedule | Time-aware transit graph |
| **Ride On + TheBus + DC Circulator + MARC + VRE GTFS feeds** | Non-WMATA DMV transit | Multi-agency fusion |
| **OpenStreetMap street network** (via `osmnx`) | Walkable sidewalk graph | Real walk time (replaces haversine) |
| **NOAA NWS API** | 7-day forecast per lat/lon | Outdoor event reliability |
| **BLS LAUS monthly** | County unemployment trend | Demand forecast leading indicator |

**Total after rebuild: 5 kept + 8 new = 13 active sources.** Each produces real signal. Zero fluff.

### Runtime vs build-time sources

- **Build-time static downloads (once or rarely):** TIGER, USDA LILA, CDC SVI, GTFS feeds (monthly refresh), OSM extracts
- **Build-time live API:** ACS (cached 90d), NOAA (daily refresh), BLS (monthly refresh), WMATA GTFS-RT (ignored for demo)
- **Runtime:** none. All enrichment is pre-computed.

---

## The agentic extraction layer

### Rationale

The current pipeline's weakest point is **how it turns unstructured HTML/PDF into typed records**. Regex + a classifier LLM misses:

- Non-English pages (Amharic/Spanish/Chinese/Arabic native script)
- Messy hours formats ("1st Saturday of month", "by appointment only", "evenings")
- Mobile/rotating locations
- Multi-org directory pages
- Scanned PDFs
- Confidence-per-field
- Evidence grounding

The rebuild replaces the regex extractor with a 4-agent loop that's LLM-first, confidence-scored, and evidence-grounded. This is SOTA for unstructured-to-structured extraction in 2026.

### The 4 agents

```
raw_text + source_metadata
         │
         ▼
  ┌─────────────┐
  │  PLANNER    │  decides strategy based on source type + size
  │  (Mistral)  │  → {strategy, chunks?, language?}
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  EXTRACTOR  │  LLM with tool-use, returns typed records
  │  (Mistral → │  with per-field confidence + evidence spans
  │   Claude)   │
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  CRITIC     │  validates via rules + evidence span cross-check
  │  (Mistral)  │  → {valid, issues, refine_context?}
  └──────┬──────┘
    pass │  fail
         │  │
    ┌────┘  └──────────┐
    │                  ▼
    │          ┌─────────────┐
    │          │  REFINER    │  re-extract with critic feedback,
    │          │  (Claude    │  escalated model
    │          │   Sonnet)   │
    │          └──────┬──────┘
    │                 │
    │  still fails    │ pass
    │  after N tries  │
    │      │          │
    │      ▼          ▼
    │  REVIEW QUEUE   (validated records)
    │                      │
    └──────────────────────┤
                           ▼
                    ┌─────────────┐
                    │  ENRICHER   │  semantic pass:
                    │  (Claude    │  firstVisitGuide,
                    │   Haiku)    │  plainEligibility, etc.
                    └─────────────┘
```

### File layout

```
pipeline/src/agents/
├── __init__.py
├── router.py                # get_client(role) → provider+model dispatch
├── planner.py               # decides extraction strategy per source
├── extractor.py             # primary LLM extraction with tool-use
├── critic.py                # validates extractor output
├── refiner.py               # re-extracts with critic feedback
├── enricher.py              # generates semantic fields
├── vision_extractor.py      # scanned PDF → text via vision model
└── prompts/
    ├── planner_system.md
    ├── extractor_system.md
    ├── critic_system.md
    ├── refiner_system.md
    └── enricher_system.md
```

### Model routing — Claude only (`router.py`)

Single provider (Anthropic) for simplicity. Role-based tiering across Haiku / Sonnet so cheap tasks stay cheap and hard tasks get the stronger model.

```python
# pipeline/src/agents/router.py

import os
from typing import Literal

AgentRole = Literal[
    "planner",
    "extractor.cheap",
    "extractor.strong",
    "critic",
    "refiner",
    "enricher",
    "vision",
]

# Claude-only routing. No Mistral, no fallback layer.
ROUTING_TABLE: dict[AgentRole, str] = {
    "planner":          "claude-haiku-4-5-20251001",
    "extractor.cheap":  "claude-haiku-4-5-20251001",
    "extractor.strong": "claude-sonnet-4-5",
    "critic":           "claude-haiku-4-5-20251001",
    "refiner":          "claude-sonnet-4-5",
    "enricher":         "claude-haiku-4-5-20251001",
    "vision":           "claude-sonnet-4-5",
}

_CLIENT = None

def get_client(role: AgentRole) -> tuple[str, object] | None:
    """Return (model_id, anthropic_client) for a given agent role. None if no key."""
    global _CLIENT
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    if _CLIENT is None:
        import anthropic
        _CLIENT = anthropic.Anthropic()
    return ROUTING_TABLE[role], _CLIENT
```

Single env var: `ANTHROPIC_API_KEY`. One SDK. One cache schema. No provider adapters.

**Cost estimates per org (Claude-only, cached runs are free):**

| Agent | Model | Typical call | Cost per call |
|---|---|---|---|
| Planner | Haiku 4.5 | 200 tok in, 50 tok out | ~$0.0008 |
| Extractor (cheap path) | Haiku 4.5 | 2000 tok in, 500 tok out | ~$0.008 |
| Extractor (escalated) | Sonnet 4.5 | 2000 tok in, 500 tok out | ~$0.04 |
| Critic | Haiku 4.5 | 800 tok in, 200 tok out | ~$0.0035 |
| Refiner | Sonnet 4.5 | 2500 tok in, 800 tok out | ~$0.055 |
| Enricher | Haiku 4.5 | 1500 tok in, 400 tok out | ~$0.007 |
| Vision (scanned PDF) | Sonnet 4.5 | ~8000 tok (image input) | ~$0.09 |

**Full extraction of a new org (cheap path — Planner + Extractor + Critic + Enricher on Haiku):** ~$0.019

**Full extraction with Refiner escalation (~15% of orgs):** ~$0.074

**Full extraction with vision (scanned PDF rare path):** ~$0.11

**100-org full re-extraction (weighted mix):** ~$3.00

**500-org full re-extraction (projected DMV scale):** ~$15.00

**Cached re-run:** $0.00. The committed cache means every subsequent run is free.

### The Extractor — tool schema

```python
# pipeline/src/agents/extractor.py
"""
Primary extraction agent. LLM reads raw HTML/text and returns
one or more typed NormalizedRecord-compatible dicts with
per-field confidence + evidence spans.
"""

EXTRACTOR_TOOL = {
    "name": "extract_food_orgs",
    "description": (
        "Extract one or more food assistance organization records from raw "
        "scraped content. Only extract fields clearly supported by the text. "
        "For each extracted field, provide a confidence score (0..1) and an "
        "evidence span (the exact source sentence that supports it). "
        "Return an empty list if no org records can be extracted."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "orgs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Organization name, title-cased",
                        },
                        "address": {"type": ["string", "null"]},
                        "city":    {"type": ["string", "null"]},
                        "state":   {"enum": ["DC", "MD", "VA", None]},
                        "zip":     {"type": ["string", "null"], "pattern": "^\\d{5}$"},
                        "phone":   {"type": ["string", "null"]},
                        "website": {"type": ["string", "null"]},

                        "hours_raw": {"type": ["string", "null"]},
                        "hours_structured": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "day":   {"enum": ["mon","tue","wed","thu","fri","sat","sun"]},
                                    "open":  {"type": "string", "pattern": "^\\d{2}:\\d{2}$"},
                                    "close": {"type": "string", "pattern": "^\\d{2}:\\d{2}$"},
                                    "note":  {"type": ["string", "null"]}
                                },
                                "required": ["day", "open", "close"]
                            }
                        },
                        "by_appointment": {"type": "boolean"},
                        "always_open":    {"type": "boolean"},

                        "services": {
                            "type": "array",
                            "items": {
                                "enum": [
                                    "food_pantry", "hot_meals", "delivery",
                                    "snap_assistance", "drive_through",
                                    "mobile_pantry", "community_garden"
                                ]
                            }
                        },
                        "food_types": {
                            "type": "array",
                            "items": {
                                "enum": [
                                    "produce", "canned_goods", "dairy",
                                    "bread_bakery", "protein",
                                    "baby_supplies", "frozen"
                                ]
                            }
                        },
                        "requirements": {
                            "type": "array",
                            "items": {
                                "enum": [
                                    "appointment_required", "walk_in",
                                    "no_id_required", "photo_id",
                                    "proof_of_address", "income_verification"
                                ]
                            }
                        },
                        "languages": {
                            "type": "array",
                            "items": {
                                "enum": [
                                    "Spanish", "French", "Amharic", "Arabic",
                                    "Chinese", "Vietnamese", "Korean", "Portuguese"
                                ]
                            }
                        },

                        "residency_restriction": {
                            "type": ["string", "null"],
                            "description": (
                                "If the org restricts service to specific "
                                "residents (e.g. 'DC residents only', "
                                "'Montgomery County residents'), extract that "
                                "restriction verbatim. Null if not mentioned."
                            )
                        },
                        "population_served": {
                            "type": ["string", "null"],
                            "description": "e.g. 'seniors 60+', 'families with children'"
                        },
                        "cultural_notes": {
                            "type": ["string", "null"],
                            "description": (
                                "If the org serves a specific community "
                                "(Ethiopian, Latino, halal, kosher, etc.), "
                                "note it. Empty string or null if not."
                            )
                        },

                        "confidence": {
                            "type": "object",
                            "description": "Per-field confidence (0..1) based on evidence strength",
                            "properties": {
                                "name":         {"type": "number", "minimum": 0, "maximum": 1},
                                "address":      {"type": "number", "minimum": 0, "maximum": 1},
                                "hours":        {"type": "number", "minimum": 0, "maximum": 1},
                                "services":     {"type": "number", "minimum": 0, "maximum": 1},
                                "requirements": {"type": "number", "minimum": 0, "maximum": 1}
                            },
                            "required": ["name", "address", "hours", "services"]
                        },

                        "evidence": {
                            "type": "object",
                            "description": (
                                "For each critical field, quote the exact source sentence "
                                "that supports the extraction. Used by the Critic agent "
                                "to verify grounding."
                            ),
                            "properties": {
                                "hours":        {"type": "string"},
                                "services":     {"type": "string"},
                                "requirements": {"type": "string"},
                                "residency":    {"type": ["string", "null"]}
                            }
                        }
                    },
                    "required": ["name", "confidence", "evidence"]
                }
            }
        },
        "required": ["orgs"]
    }
}
```

See [Appendix: prompt texts](#appendix-prompt-texts) for the full system prompts.

### The Critic — validation logic

```python
# pipeline/src/agents/critic.py

import re
from difflib import SequenceMatcher

PHONE_RE = re.compile(r"^\(\d{3}\) \d{3}-\d{4}$")
ZIP_RE   = re.compile(r"^\d{5}$")

def critic_check(record: dict, raw_text: str) -> dict:
    """
    Validate an extracted record. Returns:
      {
        "valid": bool,
        "issues": [str],  # human-readable reasons
        "field_confidence_override": {...}  # critic-adjusted confidences
      }
    """
    issues: list[str] = []
    overrides: dict[str, float] = {}

    # ─ Rule checks ─────────────────────────────────────────────────────
    if record.get("phone") and not PHONE_RE.match(record["phone"]):
        issues.append(f"phone '{record['phone']}' not in (XXX) XXX-XXXX format")

    if record.get("zip") and not ZIP_RE.match(record["zip"]):
        issues.append(f"zip '{record['zip']}' is not 5 digits")

    for slot in record.get("hours_structured") or []:
        if slot["open"] >= slot["close"]:
            issues.append(
                f"hours {slot['day']} {slot['open']}-{slot['close']} "
                f"is inconsistent (open >= close)"
            )

    # ─ Evidence grounding check ────────────────────────────────────────
    evidence = record.get("evidence", {})
    raw_lower = raw_text.lower()

    for field, span in evidence.items():
        if not span:
            continue
        span_lower = span.lower()

        # Exact substring match first
        if span_lower in raw_lower:
            continue

        # Fuzzy match fallback — allow ~90% similarity for minor spacing
        ratio = SequenceMatcher(None, span_lower[:200], raw_lower).ratio()
        if ratio < 0.55:
            issues.append(
                f"evidence span for '{field}' not found in source — "
                f"possible hallucination"
            )
            overrides[field] = min(record.get("confidence", {}).get(field, 0.5), 0.3)

    # ─ Confidence floor ────────────────────────────────────────────────
    conf = record.get("confidence", {})
    for critical in ("name", "hours", "services"):
        if conf.get(critical, 1.0) < 0.5:
            issues.append(f"low confidence on critical field '{critical}'")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "field_confidence_override": overrides,
    }
```

### Orchestration

```python
# pipeline/src/agents/orchestrator.py

def run_agentic_extraction(
    raw_text: str,
    source_id: str,
    source_url: str,
) -> list[dict]:
    """
    Run the full agent loop for one source. Returns a list of
    validated + semantically-enriched records ready for the spatial
    enrichment stages.
    """
    # 1. Planner — decide strategy
    planner = get_client("planner")
    strategy = planner_agent(raw_text, source_id, planner)

    # 2. Extractor — cheap first pass
    extractor_cheap = get_client("extractor.cheap")
    records = extractor_agent(raw_text, strategy, extractor_cheap)

    # 3. Critic loop per record
    critic = get_client("critic")
    refiner = get_client("refiner")
    validated: list[dict] = []

    for rec in records:
        critique = critic_check(rec, raw_text)

        if critique["valid"]:
            validated.append(rec)
            continue

        # 3a. Refine with critic feedback
        refined = refiner_agent(rec, raw_text, critique, refiner)
        if refined:
            second_critique = critic_check(refined, raw_text)
            if second_critique["valid"]:
                validated.append(refined)
            else:
                queue_for_review(refined, second_critique, source_url)
        else:
            queue_for_review(rec, critique, source_url)

    # 4. Semantic enrichment
    enricher = get_client("enricher")
    for rec in validated:
        enricher_agent(rec, enricher)

    return validated
```

---

## The data fusion layer

### Purpose

The agentic layer gives us **records**. The fusion layer gives us **signals nobody else computes** by combining records with external spatial, temporal, and demographic data.

Each fusion is a discrete function that takes pipeline records + external data and produces a new field or new JSON output.

### Fusion 1 — Real walking time (OSM street network)

**Replaces:** haversine-based `_transit_score` in `scoring.py`

**Ingredients:**
- org lat/lon (from records)
- OSM walking network for DMV (from `osmnx` extract)

**Implementation:**

```python
# pipeline/src/fusion/osm_routing.py

import osmnx as ox
import networkx as nx
from functools import lru_cache

# Load DMV walking graph once
_WALK_GRAPH: nx.MultiDiGraph | None = None

def load_walk_graph():
    global _WALK_GRAPH
    if _WALK_GRAPH is None:
        # Load pre-downloaded graph (saved as .graphml)
        _WALK_GRAPH = ox.load_graphml("pipeline/data/dmv-walk-graph.graphml")
    return _WALK_GRAPH

@lru_cache(maxsize=100_000)
def walk_time_minutes(origin_lat: float, origin_lon: float,
                      dest_lat: float, dest_lon: float) -> int | None:
    """True walk time via OSM street network."""
    G = load_walk_graph()
    try:
        o = ox.nearest_nodes(G, origin_lon, origin_lat)
        d = ox.nearest_nodes(G, dest_lon, dest_lat)
        length_meters = nx.shortest_path_length(G, o, d, weight="length")
        # Urban walking pace: 80 m/min (1.3 m/s)
        return max(1, round(length_meters / 80))
    except (nx.NetworkXNoPath, KeyError):
        return None
```

**Output:** `walk_minutes` replaces the haversine-based distance in all per-org accessibility computations.

**Setup cost:** one-time `ox.graph_from_place("DMV area", network_type="walk")` takes ~5 minutes, produces ~50MB graph file committed to `pipeline/data/`.

### Fusion 2 — Multi-agency transit schedule graph

**Replaces:** `utils/transit.py` haversine-to-nearest-stop.

**Ingredients:**
- WMATA GTFS feed
- Ride On (MoCo) GTFS feed
- TheBus (PG County) GTFS feed
- DC Circulator GTFS feed
- MARC GTFS feed
- VRE GTFS feed
- OSM walking network (for walk-to-stop, walk-from-stop)

**Implementation:**

Use `gtfs_kit` Python library to parse all 6 feeds into unified DataFrames. Build a time-expanded graph where nodes are (stop, hour) and edges are scheduled trips.

```python
# pipeline/src/fusion/transit_graph.py

import gtfs_kit as gk
from pathlib import Path
import networkx as nx
from datetime import datetime

DATA = Path(__file__).resolve().parents[2] / "data"

GTFS_FEEDS = {
    "wmata":     DATA / "gtfs-wmata.zip",
    "ridon":     DATA / "gtfs-ridon.zip",
    "thebus":    DATA / "gtfs-thebus.zip",
    "circ":      DATA / "gtfs-circulator.zip",
    "marc":      DATA / "gtfs-marc.zip",
    "vre":       DATA / "gtfs-vre.zip",
}

_GRAPH: nx.DiGraph | None = None

def build_transit_graph():
    """Build a unified DMV transit graph from all 6 GTFS feeds."""
    global _GRAPH
    G = nx.DiGraph()
    for agency, path in GTFS_FEEDS.items():
        feed = gk.read_feed(str(path), dist_units="m")
        # Add stops as nodes
        for _, s in feed.stops.iterrows():
            nid = f"{agency}:{s['stop_id']}"
            G.add_node(nid, agency=agency, lat=s["stop_lat"], lon=s["stop_lon"],
                       name=s["stop_name"])
        # Add schedule edges from stop_times
        # (Simplified — production should use time-expanded graph)
        # ...
    _GRAPH = G
    return G

def transit_time_minutes(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    hour_of_week: int,  # 0..167
) -> int | None:
    """
    Total transit time: walk to nearest stop + bus/train ride + walk from stop.
    Returns None if no reachable path within 60 minutes.
    """
    # Use OSM walk graph for access legs + GTFS for transit leg
    # Simplified: nearest stop walk + 15 mph transit + walk from stop
    ...
```

**For the hackathon timeline:** a simplified version using hourly schedule tables, not full time-expanded graph, is acceptable. It reduces accuracy but ships.

**Output per org:**
- `nearest_metro` — closest Metro rail station with distance + lines
- `nearest_bus` — closest bus stop across ALL 6 agencies
- `transit_accessible_hours` — boolean[168] mask of hours when org is reachable from its tract centroid via transit

### Fusion 3 — Temporal-Linguistic-Dignity Accessibility Index (TLDAI)

**The central research contribution.**

**Ingredients:**
- org `hours_structured` (from extractor agent)
- org `languages` (from extractor)
- org `requirements` (from extractor — determines dignity tier)
- org lat/lon
- tract centroid + demographics (TIGER + ACS)
- ACS language-at-home distribution per tract
- OSM walking graph (Fusion 1)
- Multi-agency transit graph (Fusion 2)

**Computation:**

```python
# pipeline/src/fusion/tldai.py

def compute_tldai(orgs: list, tracts: dict) -> dict:
    """
    Compute the Temporal-Linguistic-Dignity Accessibility Index.

    Returns a 4D sparse tensor:
      tldai[tract_geoid][language_code][hour_of_week][dignity_tier] = float(0..1)

    Where:
      - hour_of_week is 0..167 (mon 00:00 to sun 23:00)
      - dignity_tier in {"low_friction", "any_walk_in", "appointment_ok"}
      - value = fraction of tract's population in that language that can
        reach at least one matching pantry within 30 min transit at that hour
    """
    result: dict = {}

    for tract_id, tract in tracts.items():
        result[tract_id] = {}
        for lang_entry in tract["languages"]:
            lang_code = lang_entry["code"]
            result[tract_id][lang_code] = {}

            for hour in range(168):
                result[tract_id][lang_code][hour] = {
                    "low_friction":    0.0,
                    "any_walk_in":     0.0,
                    "appointment_ok":  0.0,
                }

                for org in orgs:
                    # Language match
                    if lang_code != "en" and lang_code not in map(_lang_to_code, org["languages"]):
                        continue

                    # Temporal match — is the org open at hour?
                    if not _is_open_at_hour(org["hours_structured"], hour):
                        continue

                    # Transit time from tract centroid
                    t_minutes = transit_time_minutes(
                        tract["centroid_lat"], tract["centroid_lon"],
                        org["lat"], org["lon"],
                        hour_of_week=hour,
                    )
                    if t_minutes is None or t_minutes > 30:
                        continue

                    # Dignity tiers
                    reqs = set(org["requirements"])
                    if "walk_in" in reqs and "no_id_required" in reqs \
                       and "photo_id" not in reqs and "proof_of_address" not in reqs:
                        result[tract_id][lang_code][hour]["low_friction"] = 1.0

                    if "walk_in" in reqs:
                        result[tract_id][lang_code][hour]["any_walk_in"] = 1.0

                    result[tract_id][lang_code][hour]["appointment_ok"] = 1.0

    return result
```

**Output:** `insights.json` contains a `tldai` field with the sparse tensor.

**Frontend consumption:** The Equity Gap map renders a choropleth where each tract's color depends on the user's selected (language, hour, dignity) slice of the tensor. Judges toggle between "Spanish speakers, Saturday morning, walk-in only" and "any language, weekday evening, any access" and watch the map redraw.

### Fusion 4 — Multi-source hours reconciliation

**Ingredients:**
- Primary: org's own website (scraped) → `hours_structured` from extractor
- Secondary: OSM `amenity=food_bank` tag with `opening_hours` field (for orgs that have OSM records)
- Tertiary: Google Places API hours (optional, requires API key)
- Quaternary: user feedback reports (`feedback.jsonl` from corrections stage)

**Implementation:**

```python
# pipeline/src/fusion/hours_reconciler.py

def reconcile_hours(
    primary: list[dict],    # from extractor
    osm: list[dict] | None, # from OSM amenity query
    google: list[dict] | None, # from Google Places API
    feedback: dict | None,  # aggregated user reports
) -> dict:
    """
    Reconcile hours across sources, producing:
      {
        "hours_structured": [...],  # merged canonical schedule
        "hours_sources":    [...],  # which source contributed each slot
        "hours_conflicts":  [...],  # list of (slot, sources_disagreeing)
        "hours_confidence": float,  # 0..1 composite confidence
      }
    """
    # Build a slot → source map
    slot_map: dict[tuple, list[str]] = {}
    for source_name, slots in [
        ("primary", primary),
        ("osm", osm or []),
        ("google", google or []),
    ]:
        for s in slots:
            key = (s["day"], s["open"], s["close"])
            slot_map.setdefault(key, []).append(source_name)

    # Merge — any slot confirmed by ≥1 source is in the canonical schedule
    canonical = []
    for (day, o, c), sources in slot_map.items():
        canonical.append({
            "day": day, "open": o, "close": c,
            "confirmed_by": sources,
        })

    # Detect conflicts — slots on the same day with different times across sources
    conflicts = _detect_slot_conflicts(slot_map)

    # Composite confidence
    source_count = max(len(s) for s in slot_map.values()) if slot_map else 0
    confidence = min(1.0, 0.4 + 0.2 * source_count - 0.15 * len(conflicts))

    return {
        "hours_structured": canonical,
        "hours_confidence": round(confidence, 2),
        "hours_sources": sorted({s for srcs in slot_map.values() for s in srcs}),
        "hours_conflicts": conflicts,
    }
```

**Output:** every org in `organizations.json` carries a `hours_confidence` field + optional `hours_conflicts` array. The UI shows "Confirmed by 3 sources" badge or a "Sources disagree" warning.

### Fusion 5 — Weather-aware outdoor event reliability

**Ingredients:**
- Event `indoor_outdoor` flag (new field — extractor infers from raw_text: "mobile market", "outdoor distribution", "parking lot event")
- NOAA NWS API forecast per org coordinates (7-day)

**Implementation:**

```python
# pipeline/src/fusion/weather.py

import httpx
from datetime import datetime, timedelta

def fetch_noaa_forecast(lat: float, lon: float) -> list[dict]:
    """7-day hourly forecast from NOAA NWS API (free, no key)."""
    # Step 1: get forecast grid point
    pt = httpx.get(f"https://api.weather.gov/points/{lat},{lon}").json()
    hourly_url = pt["properties"]["forecastHourly"]
    # Step 2: fetch hourly forecast
    forecast = httpx.get(hourly_url).json()
    return forecast["properties"]["periods"][:168]  # 7 days * 24h

def weather_alert_for_org(org: dict, forecast: list[dict]) -> dict | None:
    """
    Return a weather alert if the org has an outdoor event AND
    the forecast at event time is unfavorable.
    """
    if not org.get("is_outdoor"):
        return None

    # For each scheduled event time in the next 7 days
    for slot in org.get("next_7_day_events", []):
        event_time = slot["start"]  # ISO datetime
        hour_forecast = _find_forecast_for_time(forecast, event_time)
        if not hour_forecast:
            continue

        precip_pct = hour_forecast.get("probabilityOfPrecipitation", {}).get("value", 0)
        temp_f = hour_forecast["temperature"]
        wind_mph = int(hour_forecast["windSpeed"].split()[0])

        if precip_pct >= 60:
            return {"level": "warning", "reason": f"{precip_pct}% chance of rain"}
        if precip_pct >= 30:
            return {"level": "watch", "reason": f"{precip_pct}% chance of rain"}
        if temp_f < 35 or temp_f > 95:
            return {"level": "watch", "reason": f"{temp_f}°F temperature"}
        if wind_mph > 25:
            return {"level": "watch", "reason": f"{wind_mph} mph winds"}

    return None
```

**Output:** every outdoor org with an upcoming event gets a `weather_alert` field. UI shows `⚠️ Heavy rain forecast Saturday morning — call before going` on the card.

### Fusion 6 — Demand surge forecasting

**Ingredients:**
- BLS Local Area Unemployment Statistics (LAUS) monthly per county
- USDA FNS SNAP enrollment monthly per state (state-level only, not county)
- 30-day rolling deltas

**Implementation:**

```python
# pipeline/src/fusion/demand_forecast.py

def compute_demand_forecast(county_fips: str, months_history: int = 12) -> dict:
    """
    Return a per-county demand trend + 14-day forecast.
      {
        "trend": -1..+1,  # direction + magnitude
        "forecast_pct_change": float,  # expected demand change next 14 days
        "signals": [str],  # reasoning
      }
    """
    # Fetch BLS LAUS
    unemp = _fetch_bls_laus(county_fips, months_history)
    # Compute 3-month delta
    delta_3mo = unemp[-1]["rate"] - unemp[-4]["rate"] if len(unemp) >= 4 else 0

    signals = []
    if delta_3mo > 0.5:
        signals.append(f"Unemployment up {delta_3mo:.1f} points over 3 months")
    if delta_3mo < -0.5:
        signals.append(f"Unemployment down {abs(delta_3mo):.1f} points over 3 months")

    # SNAP trend
    snap = _fetch_snap_state_trend(_county_to_state(county_fips))
    snap_delta = (snap[-1] - snap[-4]) / snap[-4] if len(snap) >= 4 and snap[-4] else 0

    trend = delta_3mo * 0.25 + snap_delta * 0.75  # normalize
    forecast_pct = trend * 10  # rough projection

    return {
        "county_fips": county_fips,
        "trend": round(max(-1, min(1, trend)), 2),
        "forecast_pct_change": round(forecast_pct, 1),
        "signals": signals,
    }
```

**Output:** `insights.json` has a `demand_forecast` map per county. Donor view surfaces this. Research view adds it as a layer.

### Fusion 7 — Cultural match scoring

**Ingredients:**
- org `cultural_notes` (from extractor agent's LLM output)
- org `languages` (from extractor)
- tract ACS language-at-home distribution
- tract ACS race/ethnicity distribution (future: pull these variables too)

**Implementation:**

```python
# pipeline/src/fusion/cultural_match.py

# Cultural → language mappings
CULTURAL_LANG_HINTS = {
    "ethiopian":   ["Amharic"],
    "eritrean":    ["Amharic", "Arabic"],
    "east_african": ["Amharic", "Arabic"],
    "latino":      ["Spanish"],
    "hispanic":    ["Spanish"],
    "caribbean":   ["Spanish", "French"],
    "haitian":     ["French"],
    "west_african": ["French"],
    "arab":        ["Arabic"],
    "chinese":     ["Chinese"],
    "vietnamese":  ["Vietnamese"],
    "korean":      ["Korean"],
    "brazilian":   ["Portuguese"],
}

def cultural_match_score(org: dict, tract: dict) -> float:
    """
    0..1 score for how well an org's cultural capability matches a tract's
    demographic needs.
    """
    # Language overlap
    org_langs = set(org.get("languages") or [])
    tract_lang_share = {l["code"]: l["percent"] for l in tract["languages"]}
    non_english_tract_share = sum(v for k, v in tract_lang_share.items() if k != "en")

    if non_english_tract_share < 0.05:
        return 0.5  # Tract is mostly English, no strong cultural need

    # Weighted language match
    lang_match = 0.0
    for lang in org_langs:
        code = _lang_to_code(lang)
        lang_match += tract_lang_share.get(code, 0)

    # Cultural notes match
    cultural_boost = 0.0
    if org.get("cultural_notes"):
        notes_lower = org["cultural_notes"].lower()
        for key, langs in CULTURAL_LANG_HINTS.items():
            if key in notes_lower:
                for lang in langs:
                    code = _lang_to_code(lang)
                    cultural_boost = max(cultural_boost, tract_lang_share.get(code, 0) * 0.5)

    return round(min(1.0, lang_match + cultural_boost), 3)
```

**Output:** per (org × tract) cultural match score. Used in ranking when user location is known.

### Fusion 8 — Real tract lookup + SVI + LILA composite

**Replaces:** the broken `_zip_to_state` hack in `food_insecurity.py`.

**Ingredients:**
- TIGER/Line 2022 tract shapefiles
- ACS 2022 5-year per-tract variables (already fetching these)
- USDA Food Access Research Atlas 2019 CSV (national, tract-level LILA)
- CDC SVI 2022 CSV (national, tract-level composite)

**Implementation:**

```python
# pipeline/src/fusion/spatial_tract.py

import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"

_TRACTS_GDF: gpd.GeoDataFrame | None = None

def load_tracts() -> gpd.GeoDataFrame:
    global _TRACTS_GDF
    if _TRACTS_GDF is None:
        # Pre-filtered to DMV counties
        _TRACTS_GDF = gpd.read_file(DATA / "dmv-tracts-2022.shp")
    return _TRACTS_GDF

def assign_tract(lat: float, lon: float) -> str | None:
    """Point-in-polygon — returns real 11-digit GEOID."""
    tracts = load_tracts()
    point = Point(lon, lat)
    match = tracts[tracts.contains(point)]
    if len(match) == 0:
        return None
    return match.iloc[0]["GEOID"]

def load_lila_flags() -> pd.DataFrame:
    """USDA Food Access Research Atlas 2019 — tract-level LILA flags."""
    return pd.read_csv(DATA / "usda-food-atlas-2019.csv", dtype={"CensusTract": str})

def load_svi() -> pd.DataFrame:
    """CDC Social Vulnerability Index 2022 — tract-level composite scores."""
    return pd.read_csv(DATA / "cdc-svi-2022.csv", dtype={"FIPS": str})

def enrich_tract_composite(records: list, acs_tracts: dict) -> None:
    """
    Replace the broken enrich_insecurity with a real spatial join.
    Mutates records in-place.
    """
    lila = load_lila_flags().set_index("CensusTract")
    svi  = load_svi().set_index("FIPS")

    for rec in records:
        if rec.lat is None or rec.lon is None:
            continue

        # 1. Real spatial join
        geoid = assign_tract(rec.lat, rec.lon)
        if not geoid:
            continue
        rec.tract_id = geoid

        # 2. Pull per-tract ACS
        acs = acs_tracts.get(geoid, {})
        rec.tract_poverty_rate     = acs.get("poverty_rate")
        rec.tract_snap_rate        = acs.get("snap_rate")
        rec.tract_median_income    = acs.get("median_income")
        rec.tract_population       = acs.get("population")
        rec.tract_insecurity_score = acs.get("insecurity_score")

        # 3. Pull USDA LILA flags
        if geoid in lila.index:
            row = lila.loc[geoid]
            rec.is_food_desert = bool(row.get("LILATracts_1And20", 0) or row.get("LILATracts_Vehicle", 0))
            rec.food_access_designation = _lila_label(row)

        # 4. Pull CDC SVI
        if geoid in svi.index:
            row = svi.loc[geoid]
            rec.svi_composite = float(row.get("RPL_THEMES", 0))
            rec.svi_socioeconomic = float(row.get("RPL_THEME1", 0))
            rec.svi_household = float(row.get("RPL_THEME2", 0))
            rec.svi_minority = float(row.get("RPL_THEME3", 0))
            rec.svi_housing_transport = float(row.get("RPL_THEME4", 0))
```

**Output:** every org now has real tract demographics + LILA flag (national, not DC-only) + CDC SVI. The gap map renders per-tract variation correctly.

---

## The accessibility cube

### What it is

A pre-computed 4D sparse data structure that answers:

> *"Can a household in tract T, speaking language L, with dignity threshold D, reach at least one matching pantry at hour H of the week?"*

### Schema

```python
# pipeline/src/cube.py

from typing import TypedDict

class CubeCell(TypedDict):
    reachable_count: int  # how many pantries match
    best_walk_minutes: int | None
    best_transit_minutes: int | None
    dignity_tier_fraction: float  # 0..1

# The cube shape:
#   {tract_geoid: {lang_code: {hour_of_week: {dignity_tier: CubeCell}}}}
#
# Size for DMV: ~800 tracts × ~8 languages × 168 hours × 3 tiers
#             ≈ 3.2M cells
# Sparse storage: ~500K non-zero cells (most are 0)
# Estimated JSON size: ~25-40MB uncompressed, ~5-8MB gzipped

Cube = dict[str, dict[str, dict[int, dict[str, CubeCell]]]]
```

### How it's computed

```python
# pipeline/src/cube.py

def build_accessibility_cube(records, tracts) -> Cube:
    cube: Cube = {}

    for tract_id, tract in tracts.items():
        cube[tract_id] = {}
        for lang_entry in tract["languages"]:
            if lang_entry["percent"] < 0.02:
                continue  # skip languages with <2% share
            lang = lang_entry["code"]
            cube[tract_id][lang] = {}

            for hour in range(168):
                tiers: dict = {
                    "low_friction":    {"reachable_count": 0, "best_walk_minutes": None,
                                        "best_transit_minutes": None, "dignity_tier_fraction": 0},
                    "any_walk_in":     {...},
                    "appointment_ok":  {...},
                }

                for org in records:
                    if not _is_open_at_hour(org, hour):
                        continue
                    if lang != "en" and lang not in _org_language_codes(org):
                        continue

                    walk = walk_time_minutes(
                        tract["centroid_lat"], tract["centroid_lon"],
                        org.lat, org.lon,
                    )
                    transit = transit_time_minutes(
                        tract["centroid_lat"], tract["centroid_lon"],
                        org.lat, org.lon, hour,
                    )
                    best_time = min(walk or 999, transit or 999)
                    if best_time > 30:
                        continue

                    # Determine which tiers this org satisfies
                    for tier in _dignity_tiers_for_org(org):
                        t = tiers[tier]
                        t["reachable_count"] += 1
                        if walk and (t["best_walk_minutes"] is None or walk < t["best_walk_minutes"]):
                            t["best_walk_minutes"] = walk
                        if transit and (t["best_transit_minutes"] is None or transit < t["best_transit_minutes"]):
                            t["best_transit_minutes"] = transit

                # Only store non-zero cells
                non_zero = {k: v for k, v in tiers.items() if v["reachable_count"] > 0}
                if non_zero:
                    cube[tract_id][lang][hour] = non_zero

    return cube
```

### Output

Written to `frontend/public/data/access-cube.json` for the Equity Gap map's dynamic layers.

---

## Output JSON contracts

The frontend consumes these files. Their shapes are the contract.

### `organizations.json` (extended)

```ts
interface Organization {
  // Core fields (matching current backend, unchanged)
  source_id: string;
  source_ids: string[];
  name: string;
  address: string | null;
  city: string | null;
  state: "DC" | "MD" | "VA" | null;
  zip: string | null;
  phone: string | null;
  website: string | null;
  hours: string | null;              // raw cleaned
  hours_structured: HoursEntry[] | null;

  lat: number | null;
  lon: number | null;
  full_address: string;

  services: string[];
  food_types: string[];
  requirements: string[];
  languages: string[];

  // Reliability & priority (existing)
  dataReliabilityScore: number;
  dataReliabilityLabel: "fresh" | "recent" | "stale" | "unknown";
  dataLastChangedAt: string | null;
  priorityScore: number;

  // User feedback (existing)
  userReportCount: number;
  userPositiveCount: number;
  userNegativeCount: number;
  feedbackScore: number | null;

  // NEW — semantic enrichment
  firstVisitGuide: string[];         // 2-3 bullets
  plainEligibility: string;          // one-sentence summary
  culturalNotes: string | null;
  toneScore: number;                 // 0..1
  heroCopy: string;                  // one-sentence card description

  // NEW — confidence + evidence from extractor
  confidence: {
    name: number;
    address: number;
    hours: number;
    services: number;
    requirements: number;
  };
  evidence: {
    hours: string;
    services: string;
    requirements: string;
    residency: string | null;
  };
  extractedBy: "mistral-small-latest" | "claude-haiku-4-5" | "claude-sonnet-4-5";

  // NEW — residency + population from extractor
  residencyRestriction: string | null;
  populationServed: string | null;

  // NEW — hours reconciliation
  hoursConfidence: number;
  hoursSources: string[];
  hoursConflicts: Array<{ slot: HoursEntry; sources: string[] }>;

  // NEW — real tract lookup
  tract_id: string;                   // REAL 11-digit FIPS
  tract_poverty_rate: number;
  tract_snap_rate: number;
  tract_median_income: number;
  tract_population: number;
  tract_insecurity_score: number;

  // NEW — SVI
  svi_composite: number;
  svi_socioeconomic: number;
  svi_household: number;
  svi_minority: number;
  svi_housing_transport: number;

  // NEW — USDA LILA
  is_food_desert: boolean;
  food_access_designation: string | null;

  // NEW — multi-agency transit
  transit: {
    nearest_metro: { id: string; name: string; lines: string[]; distance_meters: number; walk_minutes: number } | null;
    nearest_bus:   { id: string; agency: string; name: string; distance_meters: number; walk_minutes: number } | null;
    reachable_hours_of_week: number[];  // list of hours 0..167 when org is transit-reachable from its centroid
  };

  // NEW — weather
  weather_alert: {
    level: "watch" | "warning";
    reason: string;
    valid_until: string;  // ISO
  } | null;
  is_outdoor: boolean;

  // NEW — embedding for semantic search
  embedding: number[];  // 384-dim

  // Event flags (existing)
  event_date: string | null;
  event_frequency: "one-time" | "weekly" | "biweekly" | "monthly" | "ongoing" | null;
}
```

### `insights.json` (new)

```ts
interface Insights {
  generatedAt: string;

  equity_gap: {
    mean_gap: number;
    p50_gap: number;
    p95_gap: number;
    worst_tract_geoids: string[];

    per_tract: Record<string, {
      geoid: string;
      name: string;
      need_score: number;      // composite from ACS + LILA + SVI
      supply_score: number;    // from accessibility cube
      gap: number;             // need - supply, normalized
      reasoning: string;       // LLM-written paragraph
    }>;
  };

  recommendations: Array<{
    id: string;
    area: { neighborhoodLabel: string; centroidLat: number; centroidLng: number; tractGeoids: string[] };
    why: string;
    stats: {
      population: number;
      needScore: number;
      underservedPopulation: number;
      nearestMatchedMinutes: number;
      languageGaps: string[];
      foodDesert: boolean;
    };
    suggestedHost: { orgId: string; orgName: string; rationale: string; distanceFromCentroidMiles: number } | null;
    suggestedCadence: string;
    expectedReachHouseholds: number;
    priority: number;
  }>;

  demand_forecast: Record<string, {
    county_fips: string;
    trend: number;             // -1..+1
    forecast_pct_change: number;
    signals: string[];
  }>;

  coverage: {
    totalOrgs: number;
    totalTracts: number;
    verifiedPct: number;
    likelyPct: number;
    stalePct: number;
    unknownPct: number;
    languagesCovered: string[];
  };
}
```

### `access-cube.json` (new)

See [The accessibility cube](#the-accessibility-cube) above.

### `metadata.json` (extended)

Keeps the existing shape, adds:
- `sourceCount.active`, `sourceCount.disabled`
- `extractionStats.byModel` — how many orgs extracted by which model
- `extractionStats.reviewQueueSize`
- `dataFusion.tldaiComputed: bool`
- `dataFusion.weatherFetched: bool`
- `dataFusion.demandForecastCounties`

---

## Implementation phases

### Phase 0 — Cleanup + Git LFS setup (2 hours)

**Goal:** Remove fluff, unblock the rebuild, set up storage for 150MB of static data.

- [ ] Cut `config.py` SOURCES from 23 → 5 (CAFB, MDFB, 211MD, MoCoFood, PGCFEC)
- [ ] Delete scrapers that aren't used: `caroline`, `generic_pdf` (keep as fallback option)
- [ ] Remove Neo4j dependency: delete `graph/builder.py`, strip `create_driver` + `build_graph` from `orchestrator.py`
- [ ] Remove `llm_enricher.py` (functionality moves to `agents/`)
- [ ] Add new dirs: `pipeline/src/agents/`, `pipeline/src/fusion/`, `pipeline/data/static/`
- [ ] **Initialize Git LFS** for large static data files:
  ```bash
  git lfs install
  git lfs track "pipeline/data/static/*.shp" "pipeline/data/static/*.shx" \
                "pipeline/data/static/*.dbf" "pipeline/data/static/*.graphml" \
                "pipeline/data/static/gtfs-*.zip" "pipeline/data/static/*.geojson"
  git add .gitattributes
  ```
- [ ] Run `python run.py --force` with the trimmed config — verify ~500 orgs still produced

### Phase 1 — Download static data (1 hour)

**Goal:** Get all the new external data locally.

- [ ] Download TIGER 2022 tract shapefiles for DMV counties → `pipeline/data/static/tiger-dmv-2022/`
- [ ] Download USDA Food Access Research Atlas 2019 CSV → `pipeline/data/static/usda-food-atlas-2019.csv`
- [ ] Download CDC SVI 2022 CSV for DMV states → `pipeline/data/static/cdc-svi-2022-dmv.csv`
- [ ] Download OSM walking graph for DMV region via `osmnx` → `pipeline/data/static/dmv-walk-graph.graphml`
- [ ] Download GTFS feeds for WMATA + 5 other agencies → `pipeline/data/static/gtfs-*.zip`
- [ ] Commit all static data to the repo (with `.gitattributes` for large files if needed)

### Phase 2 — Agentic extractor (6 hours)

**Goal:** Replace regex extraction with the 4-agent loop.

- [ ] Create `pipeline/src/agents/router.py` with Claude-only `get_client(role)` dispatch
- [ ] Create `pipeline/src/agents/prompts/*.md` with system prompts for each agent
- [ ] Create `pipeline/src/agents/extractor.py` with the extraction tool schema + `extract_records()` function
- [ ] Create `pipeline/src/agents/critic.py` with rule checks + evidence grounding
- [ ] Create `pipeline/src/agents/refiner.py` for escalated re-extraction
- [ ] Create `pipeline/src/agents/enricher.py` for semantic field generation
- [ ] Create `pipeline/src/agents/orchestrator.py` with `run_agentic_extraction()`
- [ ] Hook into `pipeline/src/orchestrator.py` replacing Stage 3 (normalize) + Stage 3b (llm_enrich)
- [ ] Build the cache layer — `state/agentic-cache.json` with keys `{role}:{md5(raw_text)}`
- [ ] Run `python run.py --force` with `ANTHROPIC_API_KEY` set, fill cache, commit cache file

### Phase 3 — Spatial data fusion (4 hours)

**Goal:** Fix the broken census lookup and add USDA/SVI.

- [ ] Create `pipeline/src/fusion/spatial_tract.py` with `assign_tract()` via geopandas
- [ ] Modify `enrich_insecurity` to use real spatial join
- [ ] Load USDA LILA → attach `is_food_desert` + `food_access_designation` to MD/VA orgs
- [ ] Load CDC SVI → attach 4-theme scores to every org
- [ ] Verify with a smoke test: every org has a real 11-digit `tract_id`

### Phase 4 — OSM walking + multi-agency transit (6 hours)

**Goal:** Replace haversine with real routing.

- [ ] Create `pipeline/src/fusion/osm_routing.py` with `walk_time_minutes()` via `osmnx`
- [ ] Create `pipeline/src/fusion/transit_graph.py` with multi-agency GTFS graph
- [ ] Replace `utils/transit.py` haversine logic with graph queries
- [ ] Each org now carries `transit.nearest_metro`, `transit.nearest_bus`, `transit.reachable_hours_of_week`

### Phase 5 — Entity resolution fix (1 hour)

**Goal:** Stop phone-based over-merging.

- [ ] Modify `resolvers/entity_resolver.py` to disable phone-based matching
- [ ] Keep name+address fuzzy (with confidence weighting)
- [ ] Keep name+zip match
- [ ] Test with known duplicate clusters (e.g. Bread for the City appearing in multiple sources)

### Phase 6 — Hours reconciliation + OSM POI + Google Places (3 hours, optional)

**Goal:** Multi-source hours confidence.

- [ ] Create `pipeline/src/fusion/hours_reconciler.py`
- [ ] Query OSM Overpass API for `amenity=food_bank` in DMV → match to our orgs by name fuzzy + distance
- [ ] Optionally call Google Places API for hours (if GOOGLE_PLACES_KEY set)
- [ ] Merge all sources → emit `hours_confidence` + `hours_conflicts`

### Phase 7 — Weather alerts (2 hours)

**Goal:** NOAA forecast integration for outdoor events.

- [ ] Create `pipeline/src/fusion/weather.py` with NOAA NWS API calls
- [ ] Extractor flags `is_outdoor: bool` during extraction
- [ ] Fetch 7-day forecast per outdoor org, attach `weather_alert` if conditions bad
- [ ] Cache forecasts for 6 hours (they update)

### Phase 8 — Demand forecasting (3 hours)

**Goal:** BLS + SNAP trend analysis.

- [ ] Create `pipeline/src/fusion/demand_forecast.py`
- [ ] Fetch BLS LAUS per DMV county (monthly)
- [ ] Fetch USDA FNS SNAP state-level trend
- [ ] Compute trend + forecast per county → output in `insights.json`

### Phase 9 — TLDAI + accessibility cube (4 hours)

**Goal:** The research contribution — temporal × linguistic × dignity accessibility.

- [ ] Create `pipeline/src/cube.py` with `build_accessibility_cube()`
- [ ] Create `pipeline/src/fusion/tldai.py`
- [ ] Output `access-cube.json` and `insights.json` with TLDAI results
- [ ] For each underserved tract, call LLM to write a reasoning paragraph (~10-20 tracts, cached)

### Phase 10 — Gap + recommendation engine (3 hours)

**Goal:** Pre-computed placement recommendations.

- [ ] Create `pipeline/src/fusion/recommendations.py`
- [ ] Greedy optimizer: grid DMV at 1km resolution, for each candidate location simulate adding a pantry and measure additional reachable households
- [ ] Top 10 outputs, each with suggested host (nearest capable org)
- [ ] LLM writes per-recommendation reasoning paragraph

### Phase 11 — Embeddings (1 hour)

**Goal:** Semantic search support.

- [ ] `pip install sentence-transformers`
- [ ] One-time model download (`all-MiniLM-L6-v2`, ~100MB)
- [ ] Compute embedding per org at build time, cache, add to `organizations.json`

### Phase 12 — Evaluation with Claude-assisted gold set (3 hours)

**Goal:** Prove SOTA quality claims with a reproducible evaluation.

**Gold set construction — collaborative LLM + human workflow:**

Instead of hand-labeling 20 orgs from scratch (slow, error-prone), we use a **two-pass labeling protocol** where Claude proposes candidate labels and a human reviews/corrects them. This is faster, more consistent, and standard practice for LLM eval gold sets in 2026.

**Pass 1 — Claude proposes (~30 min):**

1. Pick 20 diverse DMV source pages (mix of: CAFB entries, MD Food Bank listings, MoCo Food Council rows, multi-org directory pages, a PDF, a bilingual page, a mobile pantry entry)
2. For each, give Claude Sonnet the raw HTML + the extraction tool schema with instructions: *"You are creating a gold-standard reference label for evaluation. Read this source carefully and return the MOST CORRECT extraction you can. Be conservative — prefer null over guesses. Confidence scores should reflect your actual certainty."*
3. Save output as `pipeline/evaluation/gold-candidates.json`

**Pass 2 — Human review (~1 hour):**

1. Open each Claude-proposed gold record side-by-side with the raw source
2. Human reviewer (one of us) confirms or corrects each field
3. Every corrected field gets a note explaining WHY Claude was wrong (useful for error analysis)
4. Save corrected version as `pipeline/evaluation/gold-final.json`

**Pass 3 — Pipeline comparison:**

1. Run the production pipeline on the same 20 sources
2. Diff pipeline output against `gold-final.json`
3. Compute per-field precision, recall, F1 + confidence calibration
4. Break down errors into buckets: hallucination, omission, wrong classification, wrong hours, wrong residency

**Files:**
- `pipeline/evaluation/gold-candidates.json` — Claude's proposed labels
- `pipeline/evaluation/gold-final.json` — human-corrected truth
- `pipeline/evaluation/results.json` — per-field metrics + error categories
- `pipeline/evaluation/eval.py` — scoring script
- `docs/EVALUATION.md` — human-readable report

**Why this is legitimate methodology:**

- LLM-assisted labeling is standard practice (Anthropic's Constitutional AI, OpenAI's RLHF datasets, academic preference datasets)
- The human-in-the-loop correction makes the gold set ground truth, not synthetic
- Error notes on each correction become the error taxonomy for the methodology section
- Reproducible: anyone can re-run the eval by pointing at the same source URLs
- Defensible: we cite the protocol + include the correction log as supplementary

**Success thresholds:**

| Field | Precision | Recall |
|---|---|---|
| `name` | ≥ 0.98 | ≥ 0.98 |
| `hours_structured` (non-null rate) | ≥ 0.92 | ≥ 0.88 |
| `services` (per-tag) | ≥ 0.92 | ≥ 0.85 |
| `requirements` (per-tag) | ≥ 0.88 | ≥ 0.82 |
| `residency_restriction` | ≥ 0.85 | ≥ 0.80 |
| `languages` (per-tag) | ≥ 0.90 | ≥ 0.80 |

Anything below threshold triggers a prompt revision + re-run before shipping.

**Reports:**
- `docs/EVALUATION.md` — full metrics + error analysis + prompt revision log
- PDF report methodology section cites this evaluation

---

## Deprecations

The following files/modules are removed or gutted:

| File | Fate |
|---|---|
| `utils/llm_enricher.py` | **Deleted.** Replaced by `agents/extractor.py` + `agents/enricher.py` |
| `graph/builder.py` | **Deleted.** Neo4j is dead weight. |
| `normalizers/normalize.py` — `parse_hours_structured()` | **Deleted.** LLM handles hours parsing. Keep phone/address/name normalization (40 lines). |
| `normalizers/normalize.py` — `_classify()` regex chains | **Deleted.** LLM extracts tags with enum constraints. |
| `utils/transit.py` — `enrich_transit_data()` | **Gutted.** Replaced by multi-agency GTFS graph. Keep `fetch_transit_stops()` only as fallback. |
| `utils/food_insecurity.py` — `_zip_to_state()` | **Deleted.** Replaced by TIGER spatial join. |
| `utils/food_insecurity.py` — `enrich_insecurity()` | **Rewritten.** Use real `tract_id` from spatial join. |
| `scrapers/caroline.py` | **Disabled** (Caroline County isn't metro DMV). |
| `scrapers/generic_pdf.py` | **Kept** but rarely used; replaced by `vision_extractor.py` for hard PDFs. |

Config cuts: the 18 sources listed in [Source plan → Cut](#cut-18-sources--fluff-that-produces-no-usable-signal).

---

## Evaluation + success metrics

The rebuild is done when:

1. **Extraction quality:** precision ≥ 0.90, recall ≥ 0.85 per critical field (`name`, `hours_structured`, `services`, `requirements`) across the 20-org gold set
2. **Census correctness:** every org has a real 11-digit tract GEOID; within a state, `tract_insecurity_score` varies across orgs
3. **Transit correctness:** walking times match OSM routing within 10% (spot check 10 orgs via Google Maps)
4. **Hours parsing:** ≥ 90% of orgs in the gold set have `hours_structured` populated (non-null)
5. **Semantic enrichment:** every org has `firstVisitGuide`, `plainEligibility`, `heroCopy`, `toneScore`
6. **Embeddings:** every org has a 384-dim vector
7. **TLDAI:** `access-cube.json` is produced with non-zero cells for every DMV tract
8. **Recommendations:** `insights.json` has ≥ 5 gap recommendations with suggested hosts
9. **Reproducibility:** `python run.py --force` succeeds on a clean checkout with no API keys, using only committed caches
10. **Cost:** full first-run extraction cost ≤ $5 for 500 orgs (Mistral cheap + Claude Haiku mid + Sonnet only on escalation)

Success metrics go into the PDF report methodology section with citations to specific code files.

---

## Appendix: prompt texts

### `prompts/extractor_system.md`

```
You are an extraction agent for Nutrire, a DMV food access directory.

Your job: given raw scraped content from a single food assistance organization's
website or directory entry, return one or more typed records that describe the
organization(s). You MUST use the `extract_food_orgs` tool.

Rules:

1. ONLY extract fields clearly supported by the source text. If you cannot
   find evidence for a field, leave it null — never guess.

2. For every extracted field, set a confidence score (0..1) based on how
   strongly the source text supports it:
   - 1.0: unambiguously stated (e.g. "Mon-Fri 9am-5pm" → hours 1.0)
   - 0.7: inferred from context (e.g. "serves lunch daily" → hot_meals 0.7)
   - 0.4: weakly suggested (e.g. org name contains "pantry" → food_pantry 0.4)

3. For critical fields (hours, services, requirements, residency), provide an
   `evidence` span — the exact source sentence that supports your extraction.
   If the evidence span is not verbatim in the source, your extraction will
   be rejected by the Critic.

4. Normalize hours into structured form. Parse "Mon-Fri 9am-5pm, Sat 10-1" as:
   [{day:mon,open:09:00,close:17:00}, ..., {day:sat,open:10:00,close:13:00}]
   For "by appointment" set by_appointment: true and leave hours_structured empty.
   For "24/7" or "always open" set always_open: true.

5. DO NOT make assumptions about unstated fields. If the page doesn't mention
   ID requirements, do NOT assume `no_id_required`. If it doesn't mention
   languages, do NOT assume English only.

6. If the page lists multiple organizations (directory page), return all of
   them as separate records in the `orgs` array.

7. Use only these service tags: food_pantry, hot_meals, delivery, snap_assistance,
   drive_through, mobile_pantry, community_garden.

8. Use only these food type tags: produce, canned_goods, dairy, bread_bakery,
   protein, baby_supplies, frozen.

9. Use only these requirement tags: appointment_required, walk_in, no_id_required,
   photo_id, proof_of_address, income_verification.

10. Use only these language tags: Spanish, French, Amharic, Arabic, Chinese,
    Vietnamese, Korean, Portuguese. Only include a language if the source
    explicitly says staff speak it or content is provided in it.

Return nothing except the tool call.
```

### `prompts/critic_system.md`

```
You are the critic agent for Nutrire. Your job: given an extracted record and
the raw source text it was extracted from, decide if the extraction is correct
and trustworthy.

You validate two kinds of things:

1. RULE-BASED CHECKS (deterministic, not your call):
   - Phone format (XXX) XXX-XXXX
   - Zip is 5 digits
   - Hours slots have open < close
   (These are pre-checked by Python code before you see the record.)

2. JUDGMENT CHECKS (your call):
   - Is the evidence span for each critical field actually in the source text?
     If the extractor claims "source says 'Sat 10am-1pm'" but that sentence
     is NOT in the raw text, flag hallucination.
   - Does the extracted classification match the evidence? If evidence says
     "closed Sundays" but the extractor tagged `walk_in` with confidence 0.9,
     something is wrong.
   - Does the residency restriction match the evidence? If the extractor
     extracted "DC residents only" but the source says "DC, MD, and VA
     welcome," flag as mis-extraction.
   - Is there contradictory evidence in the source that the extractor missed?

Return a JSON object via tool-use:
{
  "valid": bool,
  "issues": [string],  // concrete reasons if invalid
  "field_confidence_override": { field: new_confidence, ... }
}

Be conservative. If in doubt, flag. The Refiner agent will retry with your
feedback — false negatives are cheaper than false positives passing through.
```

### `prompts/enricher_system.md`

```
You write copy for Nutrire, a dignity-first food access app for DMV families.
Users are stressed, embarrassed, limited time. Write as a neighbor who has
been there — not as a charity brochure.

BANNED WORDS: needy, emergency food, recipient, beneficiary, eligible,
underserved, low-income, assistance, food insecure, applicant, qualify.
If you use any of these, your output will be rejected.

Given a food organization record, generate five fields:

1. firstVisitGuide — 2 or 3 plain bullets about what happens on a first visit.
   8-15 words each. Second person. Concrete physical actions.
   Example: "Walk in the front door. Staff will greet you. Expect 15 minutes."

2. plainEligibility — one sentence, max 15 words, saying what someone needs
   to bring (or not). Best: "Anyone welcome. Bring nothing." If ID is required:
   "Bring a photo ID and something with your address."

3. culturalNotes — optional. If the org clearly serves a specific community
   (Ethiopian, Latino, halal, kosher, etc.) write one line about it. Empty
   string if not applicable.

4. toneScore — 0..1 first-timer friendliness:
   - 0.9+ : no questions asked, walk-in, choice pantry
   - 0.6-0.8 : welcoming but formal process
   - 0.4-0.6 : appointment required, paperwork
   - 0.0-0.4 : stale or hard-to-access

5. heroCopy — one warm sentence (10-20 words) describing what the place
   actually is. Do NOT repeat the org name. Example: "Walk-in fresh market
   with produce, bread, and dairy every Saturday morning — no forms."

Return only via the tool call. Use the banned-words list as a hard rule.
```

### `prompts/refiner_system.md`

```
You are the refiner agent for Nutrire. The Extractor produced a record that
the Critic rejected. Your job: re-extract the org record from the raw source,
addressing the Critic's specific issues.

You will receive:
- The original raw source text
- The extractor's first attempt
- The Critic's list of issues with that attempt

Re-extract the record. Address each issue explicitly. If the Critic said
"hours evidence span not in source," find the REAL hours sentence or set
hours to null with confidence 0.0. If the Critic said "services don't match
evidence," re-read the source and reclassify.

Use the same `extract_food_orgs` tool schema as the original Extractor.
Your output will be re-checked by the Critic. If it still fails, the record
goes to a human review queue.

Be more conservative than the original Extractor. Prefer null + low confidence
over optimistic guesses.
```

### `prompts/planner_system.md`

```
You are the planner agent for Nutrire. Given a source's metadata (URL, MIME
type, content length, language detected) and a snippet of the raw content,
decide the extraction strategy for that source.

Return one of:

{
  "strategy": "single_org_page",    // one org per page
  "chunks": 1,
  "language": "en"
}

{
  "strategy": "directory_listing",  // multiple orgs per page
  "chunks": N,                      // split long lists into N chunks
  "language": "en"
}

{
  "strategy": "pdf_text",
  "chunks": 1,
  "language": "en"
}

{
  "strategy": "pdf_scanned",        // needs vision extractor
  "chunks": 1,
  "language": "en"
}

{
  "strategy": "json_api",           // direct field mapping
  "chunks": 1,
  "language": "en"
}

{
  "strategy": "multilingual_page",  // non-English content
  "chunks": 1,
  "language": "es" | "am" | "ar" | "zh" | ...
}

Return only via the planner tool call.
```

---

## Decisions (locked)

1. **Python version:** 3.11+. Dependencies: `geopandas`, `osmnx`, `gtfs_kit`, `sentence-transformers`, `anthropic`, `httpx`, `shapely`. No `mistralai`.

2. **LLM provider:** Anthropic only. Haiku 4.5 for cheap roles (Planner, Extractor cheap path, Critic, Enricher), Sonnet 4.5 for Refiner + Vision. Single env var `ANTHROPIC_API_KEY`.

3. **LLM budget:** no cap. Full first-run cost ~$3-15 for 100-500 orgs. Caches committed so subsequent runs are $0.

4. **Static data (150MB):** committed to repo via Git LFS. Anyone with `git lfs pull` has a fully working pipeline — TIGER shapefiles, USDA LILA CSV, CDC SVI CSV, OSM walk graph, all 6 GTFS feeds.

5. **Neo4j:** deleted. `graph/builder.py` removed, `create_driver` + `build_graph` calls stripped from `orchestrator.py`. `exporter.py`'s `graph.json` output is the only graph consumer.

6. **Caroline scraper:** disabled. Not metro DMV.

7. **Google Places API:** **kept** for hours reconciliation (Fusion 4). One-time scrape per org, results cached permanently. Places API cost: ~$0.017 per call (basic data field) × 500 orgs = ~$8.50 total, one-time. Re-runs are cache-hit and free. `GOOGLE_PLACES_API_KEY` is optional — pipeline runs without it, but hours_confidence is lower.

8. **Gold set for evaluation:** Claude-assisted collaborative labeling. Claude Sonnet proposes gold labels from raw sources, human reviews and corrects. See [Phase 12](#phase-12--evaluation-with-claude-assisted-gold-set-3-hours) for the protocol.

---

## Why this wins

Three citable novel contributions, each grounded in specific source fusions, each producing a user-visible feature:

1. **LLM-first evidence-grounded extraction with confidence scoring** — first production food-finder with per-field confidence + auditable evidence spans
2. **Temporal-Linguistic-Dignity Accessibility Index (TLDAI)** — first accessibility metric combining hour-of-week, language-matched, dignity-threshold dimensions
3. **Multi-source hours reconciliation** — first pipeline to cross-validate hours across ≥3 independent sources

All three are defensible in the NSF report. All three produce demo moments in the UI. All three are what separate us from "another pantry finder with a nicer coat of paint."

---

**End of spec.**
