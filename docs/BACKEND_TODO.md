# Backend — Remaining Work

> **Context:** The core pipeline is built and working (9 stages, 1,395 orgs, 4 frontend JSON files). This doc covers what's left to go from "working" to "impressive" — prioritized by judge impact.

---

## What's Done (don't redo)

| Component | Status | Output |
|---|---|---|
| 5-source scraping (CAFB, MDFB, 211MD, 211VA, MoCoFood) | Done | 1,518 raw records |
| LLM enrichment (Mistral function calling) | Done | heroCopy, firstVisitGuide, plainEligibility, hours, languages, services, requirements |
| Cross-source deduplication (Union-Find) | Done | 1,428 unique orgs |
| 3-tier geocoding (ArcGIS + Nominatim + ZIP centroid) | Done | 100% lat/lon coverage |
| Normalization (phones, hours, IDs, reliability scores) | Done | Clean structured records |
| Export to frontend JSON | Done | enriched-orgs.json (1,395 orgs) |
| Equity gap analysis (supply vs need per ZIP) | Done | equity-gaps.json (30 underserved areas) |
| TLDAI accessibility index | Done | access-summary.json (per-ZIP day/language/dignity) |
| ZIP-based language inference | Done | 51% language coverage |
| JSONL audit logs for every stage | Done | Full traceability |
| Persistent caches (website, LLM, geocode) | Done | Re-runs cost $0 |

---

## Priority 1 — Required for Submission (do these first)

### P1.1: Verify frontend loads real data
- Run `npm run dev`, confirm BestMatch shows 1,395 real orgs (not mock data)
- Confirm Map page shows pins + equity gap circles
- Confirm Donate/Volunteer pages filter correctly
- Confirm OrgDetail page loads individual org by ID
- **If "still loading" bug persists:** check browser console for JSON parse errors or CORS issues

### P1.2: Deploy to GitHub Pages
- `npm run build` → verify `dist/data/` has all 4 JSON files
- Push to GitHub, enable Pages from `gh-pages` branch or `dist/` folder
- Test deployed URL loads data correctly

### P1.3: Kiro Prompts (30% of grade!)
- The challenge requires prompt engineering documentation in Kiro markdown format
- Document the Mistral function-calling prompt used in stage1b (the `enrich_food_org` tool schema)
- Document the anti-hallucination validation logic
- Document the equity gap formula and TLDAI dimensions
- See `docs/STITCH_PROMPT.md` for the design spec format to follow

### P1.4: Report (20% of grade!)
- Architecture diagram (the 9-stage pipeline)
- Novel signals: equity gaps + TLDAI (no other team has these)
- Data quality table (coverage percentages)
- LLM cost breakdown ($0.21 total for 1,518 records)
- Cross-source deduplication methodology

---

## Priority 2 — High Impact Improvements (if time allows)

### P2.1: Add `culturalNotes` field via Mistral
- **What:** For each org, generate a 1-2 sentence note about the cultural context of the community it serves (e.g., "This pantry stocks halal options and has Amharic-speaking staff")
- **Where:** Add to the Mistral tool schema in `pipeline/scripts/stage1b_enrich.py`, add field to `enrich_food_org` function
- **Frontend:** Display on OrgDetail page below heroCopy
- **Cost:** ~$0.05 incremental (cache means re-enriching only new records)
- **Impact:** Judges will notice dignity-first cultural awareness

### P2.2: Confidence badges on frontend
- **What:** Show "Verified by 3 sources" or "Single source" badges based on `crossSourceCount`
- **Where:** Already in the data (`crossSourceCount`, `sourceIds` fields). Just needs UI badges in OrgDetail and BestMatch cards
- **Impact:** Shows data quality transparency — judges love this

### P2.3: "Open now" real-time filter
- **What:** Parse `ai.parsedHours` to check if org is open at current time
- **Where:** `src/lib/open-status.ts` (new file), used in BestMatch and AllOptions
- **Show:** "Open now" green badge, "Opens at 2pm" gray badge, "Show only open now" filter toggle
- **Impact:** The single most useful feature for a family searching for food right now

### P2.4: Browser language auto-detection
- **What:** Detect `navigator.language`, auto-filter to orgs serving that language
- **Where:** BestMatch page, add language filter dropdown with auto-selected default
- **Impact:** 51% of orgs have language data — this makes it visible

---

## Priority 3 — SOTA Upgrades (only if shipping everything above)

These are from the full BACKEND_REBUILD_SPEC.md. Each is a real upgrade but none are required for the hackathon.

### P3.1: Agentic extraction with critic loop
- Replace single Mistral call with Planner → Extractor → Critic → Refiner pipeline
- Adds per-field confidence scores and evidence grounding
- Estimated: 4-6 hours to build, needs Anthropic API key (Claude Haiku for cheap path)

### P3.2: Vector embeddings for semantic search
- Generate embeddings per org using Mistral Embed or OpenAI
- Store in `enriched-orgs.json` as `embedding` field
- Build frontend search that ranks by semantic similarity, not just text match
- Estimated: 2-3 hours (backend) + 2 hours (frontend search UI)

### P3.3: Real transit routing (GTFS + OSM)
- Replace haversine distance with real walking/transit time using WMATA GTFS + OSM sidewalk graph
- Estimated: 6-8 hours, requires osmnx + GTFS data download

### P3.4: TIGER tract-level spatial join
- Replace ZIP-based analysis with real Census tract polygons
- Gives per-tract food insecurity scores instead of per-ZIP approximations
- Estimated: 3-4 hours, requires TIGER shapefile download (~200MB)

### P3.5: CDC Social Vulnerability Index overlay
- Add SVI scores per tract as a secondary vulnerability lens alongside our equity gaps
- Estimated: 2 hours, requires SVI CSV download

---

## File Reference

```
pipeline/
├── scripts/
│   ├── stage1_scrape.py          # 5-source scraping
│   ├── stage1b_enrich.py         # Mistral LLM enrichment
│   ├── stage2_dedup.py           # Cross-source dedup
│   ├── stage3_geocode.py         # 3-tier geocoding
│   ├── stage4_normalize.py       # Phone/hours/ID normalization
│   ├── stage5_export.py          # Frontend JSON export
│   ├── stage7_equity.py          # Equity gap analysis
│   ├── stage8_tldai.py           # TLDAI accessibility index
│   └── fix_languages.py          # ZIP-based language inference
├── src/
│   ├── config.py                 # Source definitions
│   ├── scrapers/                 # 5 Playwright + curl_cffi scrapers
│   ├── utils/logger.py           # UTF-8 safe logging
│   └── validators/schemas.py     # Pydantic data models
├── output/                       # Intermediate stage results
├── state/                        # Persistent caches
├── logs/                         # JSONL audit logs
├── requirements.txt
└── README.md                     # Full architecture docs
```

## Environment Setup

```bash
cd pipeline
python -m venv .venv
source .venv/Scripts/activate    # Windows
pip install -r requirements.txt
playwright install chromium
```

Create `pipeline/.env`:
```
MISTRAL_API_KEY=<key>
MISTRAL_MODEL=ministral-8b-latest
```

## Re-running the Pipeline

All stages use persistent caches. Re-runs are fast:
```bash
python scripts/stage1_scrape.py      # ~2 min (Playwright)
python scripts/stage1b_enrich.py     # ~0 sec (cached)
python scripts/stage2_dedup.py       # ~5 sec
python scripts/stage3_geocode.py     # ~0 sec (cached)
python scripts/stage4_normalize.py   # instant
python scripts/fix_languages.py      # instant
python scripts/stage5_export.py      # instant
python scripts/stage7_equity.py      # instant
python scripts/stage8_tldai.py       # instant
```
