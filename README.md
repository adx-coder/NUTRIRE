# Nutrire Backend Pipeline

A 9-stage data pipeline that scrapes, enriches, deduplicates, geocodes, and exports **1,401 food assistance organizations** across DC, Maryland, and Virginia into frontend-ready JSON. Built for the NAFSI Data Challenge.

## Architecture

```
Stage 1    Scrape           5 sources → 1,518 raw records
Stage 1b   Enrich           Website scrape + Mistral LLM + templates → heroCopy, hours, languages
Stage 2    Dedup            Cross-source fuzzy matching → 1,428 unique orgs
Stage 3    Geocode          CAFB ArcGIS + Nominatim + ZIP fallback → 98% lat/lon
Stage 4    Normalize        Phone formatting, hours parsing, reliability, IDs, foodTypes, culturalNotes
Stage 5    Export           → public/data/enriched-orgs.json (frontend-ready)
Stage 6    Transit          WMATA Metro/Bus + OSRM road routing → walk times, generalized cost mode selection
Stage 7    Equity Gaps      Supply vs need per ZIP → 30 underserved areas
Stage 8    TLDAI            Temporal-Linguistic-Dignity Accessibility Index per ZIP
Stage 9    Weather          NWS alerts per org → severity, travel disruption flags
```

Each stage reads from the previous stage's output file. Re-run any stage independently without re-running the whole pipeline.

## Data Sources

| Source | Scraper | Method | Records | Coverage |
|--------|---------|--------|---------|----------|
| Capital Area Food Bank | `cafb.py` | Playwright + ArcGIS FeatureServer API | 382 | DC/MD/VA, structured hours |
| Maryland Food Bank | `mdfb.py` | Playwright pagination (29 pages) | 285 | MD statewide |
| 211 Maryland | `two11md.py` | Playwright Next.js SSR pagination | 403 | MD statewide |
| 211 Virginia | `two11md.py` | Playwright Next.js SSR pagination | 343 | VA statewide |
| MoCo Food Council | `mocofood.py` | DRTS WordPress plugin fields | 105 | Montgomery County, hours + languages |

Cloudflare-protected sites (CAFB, MDFB) use `curl_cffi` with Chrome TLS fingerprint impersonation.

## Data Quality

| Field | Coverage | Source |
|-------|----------|--------|
| Address | 98% | Scraper |
| Phone | 99% | Scraper |
| Coordinates | 100% (1,395/1,401) | CAFB ArcGIS + Nominatim + ZIP centroid |
| Hours | 54% (763/1,401) | Scraper + website scrape |
| heroCopy | 100% | Mistral LLM + templates |
| firstVisitGuide | 100% | Mistral LLM + templates |
| plainEligibility | 100% | Mistral LLM + templates |
| Languages | 39% (548/1,401) | Scraper + LLM + ZIP inference |
| Services | 100% | Scraper + LLM |
| foodTypes | 99% (1,383/1,401) | LLM + heuristic defaults |
| Website | 89% (1,240/1,401) | Scraper + CAFB fallback |
| culturalNotes | 19% (261/1,401) | LLM + name/language heuristics |
| Transit block | 100% (1,395/1,401) | WMATA API + OSRM routing |
| Weather alerts | Real-time snapshot | NWS API (free, no key) |
| Reliability score | 100% | Cross-source count + field completeness |
| Accepts donations | 23% | LLM + website scrape |
| Accepts volunteers | 27% | LLM + website scrape |

## Setup

```bash
cd pipeline-backend
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# source .venv/Scripts/activate  # Windows
pip install -r requirements.txt
playwright install chromium
```

Create `.env` in the project root:
```
MISTRAL_API_KEY=your_key_here
MISTRAL_MODEL=ministral-8b-latest
WMATA_API_KEY=your_key_here      # Get free at https://developer.wmata.com
```

The WMATA API key is required for Stage 6 (transit enrichment). Register at the WMATA developer portal for a free key.

## Running the Pipeline

Each stage is a standalone script. Run in order:

```bash
# Stage 1: Scrape all 5 sources (~2 min)
python scripts/stage1_scrape.py

# Stage 1b: Enrich via website scrape + Mistral LLM (~45 min scrape + ~25 min LLM)
python scripts/stage1b_enrich.py

# Stage 2: Deduplicate across sources (~5 sec)
python scripts/stage2_dedup.py

# Stage 3: Geocode all records (~15 min, cached after first run)
python scripts/stage3_geocode.py

# Stage 4: Normalize phones, hours, IDs, add defaults (~instant)
python scripts/stage4_normalize.py

# Fix: Infer languages from ZIP demographics (~instant)
python scripts/fix_languages.py

# Stage 6: Transit enrichment — WMATA + OSRM (~40 min first run, cached after)
python scripts/stage6_transit.py

# Stage 9: Weather alerts from NWS (~15 min, 1-hour cache)
python scripts/stage9_weather.py

# Stage 5: Export to frontend JSON (~instant)
python scripts/stage5_export.py

# Stage 7: Equity gap analysis (~instant)
python scripts/stage7_equity.py

# Stage 8: TLDAI accessibility index (~instant)
python scripts/stage8_tldai.py
```

Re-runs are fast -- website scrape, LLM calls, geocoding, and transit routing all use persistent caches in `state/`.

### Optional Flags

```bash
# Stage 6
python scripts/stage6_transit.py --limit 50      # Process only first 50 orgs
python scripts/stage6_transit.py --dry-run        # Preview without API calls
python scripts/stage6_transit.py --no-osrm        # Use haversine instead of OSRM

# Stage 9
python scripts/stage9_weather.py --from-stage4    # Use stage4 output if stage6 not yet run
python scripts/stage9_weather.py --limit 20       # Process only first 20 orgs
python scripts/stage9_weather.py --dry-run        # Preview without API calls
```

### Integration Test

```bash
python scripts/test_transit_weather.py --sample 8
```

Runs 81 assertions across 8 test suites:
- WMATA Metro station API (102 stations)
- WMATA Bus stop API (7,505 stops)
- OSRM road-network routing validation
- NWS Weather API connectivity
- Per-org transit enrichment with real OSRM
- Generalized-cost mode selection (10 unit test cases)
- Per-org weather alert attachment
- End-to-end data flow + full field audit (50 fields)

## Transit Enrichment (Stage 6)

### Data Sources

| Source | Type | Count | API |
|--------|------|-------|-----|
| WMATA Rail Stations | Metro | 102 stations | WMATA StationList API |
| WMATA Bus Stops | Bus | 7,505 stops (DMV) | WMATA BusStops API |
| OSRM | Walking routes | On-demand | Public OSRM server |

### How It Works

1. **Load transit data**: Fetch all Metro stations and DMV bus stops from WMATA API (cached 7 days)
2. **Haversine pre-filter**: For each org, find the 3 closest Metro stations (within 2km) and 3 closest bus stops (within 3km) by crow-flies distance
3. **OSRM routing**: Call OSRM for actual road-network walking distance/time for each candidate
4. **Mode selection**: Pick primary recommendation using generalized cost model

### Generalized Cost Mode Selection

Instead of a fixed distance threshold, the pipeline uses a **research-backed generalized cost model** to decide between Metro and Bus:

```
cost = walk_minutes x 1.5 (walk penalty) + avg_wait x 1.2 (wait penalty)
```

| Parameter | Metro | Bus | Source |
|-----------|-------|-----|--------|
| Walk penalty | 1.5x | 1.5x | TRB generalized cost research |
| Wait penalty | 1.2x | 1.2x | TRB generalized cost research |
| Avg wait time | 3.0 min | 10.0 min | WMATA headway data (~6 min / ~20 min) |

Metro's frequency advantage (3 min avg wait vs 10 min for bus) gives it a built-in **8.4-minute equivalent advantage**, meaning Metro wins even when ~450m further than the nearest bus. This aligns with research showing riders walk 2-2.5x further for rail transit.

**Example decisions:**
| Metro dist | Bus dist | Metro cost | Bus cost | Winner |
|-----------|---------|-----------|---------|--------|
| 500m | 100m | 13.0 | 13.9 | Metro (frequency wins) |
| 800m | 100m | 18.6 | 13.9 | Bus (walk gap too large) |
| 300m | 300m | 9.2 | 17.6 | Metro (equal walk, lower wait) |
| 1800m | 200m | 37.4 | 15.8 | Bus (huge walk gap) |

### Transit Fields

Each org receives:
- `nearestTransit` -- station/stop name
- `nearestTransitType` -- `"metro"` or `"bus"`
- `nearestTransitLines` -- line codes (e.g., `["RD", "GR"]`)
- `transitDistanceMeters` -- OSRM walking distance
- `transit_detail.nearest_metro` -- full Metro details (id, name, lines, walk_distance_m, walk_minutes, osrm_used)
- `transit_detail.nearest_bus` -- full Bus details (id, route, stop_name, walk_distance_m, walk_minutes)
- `transit_detail.walk_minutes_to_metro` / `walk_minutes_to_bus`
- `transit_detail.reachable_hours_of_week` -- Metro service hour slots (0-167)
- `transit_detail.transit_summary` -- human-readable one-liner

## Weather Alerts (Stage 9)

### How It Works

- Calls the **NWS (National Weather Service) API** for each org's lat/lon -- free, no API key required
- Filters for 25+ relevant alert types (tornado, flood, blizzard, heat, ice, etc.)
- Picks the **worst active alert** ranked by NWS severity (Extreme > Severe > Moderate > Minor)
- Classifies each alert with `affectsTravel` flag for transit-disrupting conditions
- Cache keyed at 2 decimal places (~1.1km precision, matching NWS grid resolution), 1-hour TTL

### Weather Fields

Each org receives:
- `weatherAlert.event` -- e.g., "Tornado Warning", "Special Weather Statement"
- `weatherAlert.level` -- `"warning"` | `"watch"` | `"advisory"` | `"statement"`
- `weatherAlert.severity` -- NWS severity: Extreme/Severe/Moderate/Minor/Unknown
- `weatherAlert.headline` -- NWS short headline
- `weatherAlert.description` -- full NWS description (first 400 chars)
- `weatherAlert.instruction` -- NWS recommended action
- `weatherAlert.validFrom` / `validUntil` -- ISO8601 alert window
- `weatherAlert.affectsTravel` -- boolean, True if alert disrupts travel to pantry

### Standalone Refresh

Weather alerts are also exported to `public/data/weather-alerts.json` as a standalone file that can be refreshed independently via cron without re-running the full pipeline.

## Equity Gap Analysis (Stage 7)

Computes supply vs need per ZIP code using org density against Census poverty/SNAP data. Identifies **30 underserved areas** where new food distribution events would have the most impact.

```
Gap = max(0, NeedScore - SupplyScore)
NeedScore = 0.6 x poverty_rate + 0.4 x snap_rate
SupplyScore = weighted_org_count / (population / 5000) x NeedScore
```

Output: `public/data/equity-gaps.json` -- 30 ZIPs ranked by gap score.

## TLDAI -- Temporal-Linguistic-Dignity Accessibility Index (Stage 8)

For each ZIP, answers: "Can a household speaking language L find a walk-in pantry on day D within 3km?"

Three dimensions:
- **Temporal**: which days of the week have open pantries
- **Linguistic**: which languages are served by nearby pantries
- **Dignity tier**: walk-in/no-ID (low friction) vs appointment/ID-required (high friction)

Output: `public/data/access-summary.json` -- 60 ZIPs with dayAccess, languageAccess, dignityAccess, and composite accessScore.

## Stage 4 Enrichments

Beyond basic normalization (phone formatting, hours parsing, state/city inference, ID generation), Stage 4 applies several data quality heuristics:

| Enrichment | Records Affected | Logic |
|-----------|-----------------|-------|
| Default foodTypes | 715 orgs (50%) | Any `food_pantry` service without foodTypes gets `["canned_goods"]` |
| CAFB website fallback | 351 orgs | CAFB records without website get the CAFB directory URL |
| culturalNotes inference | 154 orgs | Inferred from org name keywords and non-English languages served |
| extractedBy provenance | All orgs | Tags whether fields came from LLM (`ministral-8b`) or template |
| Reliability scoring | All orgs | Cross-source count + field completeness = tier (fresh/recent/stale/unknown) |

## LLM Enrichment (Stage 1b)

Uses **Mistral** (`ministral-8b-latest`) via function calling to extract structured fields from raw text + scraped website content:

- **Cost**: ~$0.21 for 1,518 records
- **Latency**: ~25 min sequential (0.15s sleep between calls)
- **Tool schema**: single `enrich_food_org` function extracting 15 fields in one call
- **Validation**: anti-hallucination check on hours (must appear in source text), banned words check on heroCopy, toneScore clamped to 0-1
- **Cache**: MD5-keyed persistent cache -- re-runs cost $0

## Output Files

### Frontend data (`public/data/`)

| File | Contents |
|------|----------|
| `enriched-orgs.json` | 1,401 orgs with full enrichment (50 fields per org) |
| `equity-gaps.json` | 30 underserved areas with need/supply/gap scores |
| `access-summary.json` | Per-ZIP accessibility by day, language, dignity tier (60 ZIPs) |
| `weather-alerts.json` | Active NWS alerts keyed by org ID (refreshable independently) |
| `metadata.json` | Pipeline stats, source counts, field coverage |

### Intermediate outputs (`output/`)

| File | Stage | Records |
|------|-------|---------|
| `stage1_raw_records.json` | Scrape | 1,518 |
| `cafb_raw_features.json` | CAFB ArcGIS | 382 features with lat/lon |
| `stage1b_enriched_records.json` | Enrich | 1,518 |
| `stage2_deduped.json` | Dedup | 1,428 |
| `stage3_geocoded.json` | Geocode | 1,428 |
| `stage4_normalized.json` | Normalize | 1,428 |
| `stage6_transit.json` | Transit | 1,428 (1,396 enriched) |
| `stage9_weather.json` | Weather | 1,428 |

### Caches (`state/`)

| File | Purpose | TTL |
|------|---------|-----|
| `website-cache.json` | Playwright website scrape results | Permanent |
| `stage1b-enrichment-cache.json` | Mistral LLM responses | Permanent |
| `geocode-cache.json` | Nominatim geocode results | Permanent |
| `transit-cache.json` | Per-org WMATA + OSRM results | 7 days |
| `wmata-stations-cache.json` | All 102 Metro stations | 7 days |
| `wmata-stops-cache.json` | 7,505 DMV bus stops | 7 days |
| `weather-cache.json` | NWS alerts per grid square | 1 hour |

### Logs (`logs/`)

All logs are JSONL format with timestamps for audit:

| File | Purpose |
|------|---------|
| `website_scrape.jsonl` | URL, status, latency, hours found |
| `llm_enrichment.jsonl` | Record name, cache hit/miss, fields extracted |
| `stage2_dedup.jsonl` | Merge decisions with scores |
| `stage3_geocode.jsonl` | Address, method, result coords |
| `template_fills.jsonl` | Template-generated fields per record |
| `stage6_transit.jsonl` | Per-org Metro/Bus/OSRM results |
| `stage9_weather.jsonl` | Per-org NWS alert lookups |

## External APIs

| API | Key Required | Cost | Used In |
|-----|-------------|------|---------|
| Mistral AI | Yes (`MISTRAL_API_KEY`) | ~$0.21 / full run | Stage 1b |
| WMATA | Yes (`WMATA_API_KEY`) | Free | Stage 6 |
| OSRM | No | Free | Stage 6 |
| NWS Weather | No | Free | Stage 9 |
| Nominatim | No | Free (rate-limited) | Stage 3 |
| CAFB ArcGIS | No | Free | Stage 1 |

## Project Structure

```
pipeline-backend/
|-- .env                              # API keys (gitignored)
|-- .gitignore
|-- requirements.txt
|-- README.md
|
|-- scripts/                          # Pipeline stages
|   |-- stage1_scrape.py              # Scrape 5 sources
|   |-- stage1b_enrich.py             # Website scrape + Mistral LLM
|   |-- stage2_dedup.py               # Cross-source deduplication
|   |-- stage3_geocode.py             # Geocoding (ArcGIS + Nominatim)
|   |-- stage4_normalize.py           # Phone, hours, IDs, defaults
|   |-- stage5_export.py              # Export to frontend JSON
|   |-- stage6_transit.py             # WMATA + OSRM transit enrichment
|   |-- stage7_equity.py              # Equity gap analysis
|   |-- stage8_tldai.py               # TLDAI accessibility index
|   |-- stage9_weather.py             # NWS weather alerts
|   |-- fix_languages.py              # ZIP-based language inference
|   |-- test_transit_weather.py       # 81-assertion integration test
|
|-- src/
|   |-- config.py                     # Source definitions
|   |-- scrapers/                     # Playwright + curl_cffi scrapers
|   |-- utils/logger.py
|   |-- validators/schemas.py         # Pydantic data models
|
|-- output/                           # Intermediate stage results
|-- state/                            # Persistent caches
|-- logs/                             # JSONL audit logs
|
|-- frontend/                         # React + Vite frontend (separate)
    |-- src/
    |-- public/data/                  # Pipeline outputs consumed by frontend
    |-- package.json
    |-- vite.config.ts
```
