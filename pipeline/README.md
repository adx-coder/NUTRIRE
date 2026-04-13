# Nutrire Backend Pipeline

A 9-stage data pipeline that scrapes, enriches, deduplicates, geocodes, and exports 1,395 food assistance organizations across DC, Maryland, and Virginia into frontend-ready JSON.

## Architecture

```
Stage 1   Scrape         5 sources → 1,518 raw records
Stage 1b  Enrich         Website scrape + Mistral LLM + templates → heroCopy, hours, languages
Stage 2   Dedup          Cross-source fuzzy matching → 1,428 unique orgs
Stage 3   Geocode        CAFB ArcGIS + Nominatim + ZIP fallback → 98% lat/lon
Stage 4   Normalize      Phone formatting, hours parsing, reliability scores, IDs
Stage 5   Export         → public/data/enriched-orgs.json (frontend-ready)
Stage 7   Equity Gaps    Supply vs need per ZIP → 30 underserved areas
Stage 8   TLDAI          Temporal-Linguistic-Dignity Accessibility Index per ZIP
```

Each stage reads from the previous stage's output file. Re-run any stage independently without re-running the whole pipeline.

## Data Sources

| Source | Scraper | Method | Records | Coverage |
|--------|---------|--------|---------|----------|
| Capital Area Food Bank | `cafb.py` | Playwright → ArcGIS FeatureServer API | 382 | DC/MD/VA, structured hours |
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
| Coordinates | 100% | CAFB ArcGIS + Nominatim + ZIP centroid |
| Hours | 54% | Scraper + website scrape |
| heroCopy | 100% | Mistral LLM + templates |
| firstVisitGuide | 100% | Mistral LLM + templates |
| plainEligibility | 100% | Mistral LLM + templates |
| Languages | 51% | Scraper + LLM + ZIP inference |
| Services | 100% | Scraper + LLM |
| Requirements | 76% | Scraper + LLM |
| Accepts donations | 25% | LLM + website scrape |
| Accepts volunteers | 29% | LLM + website scrape |

## Setup

```bash
cd pipeline
python -m venv .venv
source .venv/Scripts/activate    # Windows
pip install -r requirements.txt
playwright install chromium
```

Create `pipeline/.env`:
```
MISTRAL_API_KEY=your_key_here
MISTRAL_MODEL=ministral-8b-latest
```

## Running

Each stage is a standalone script. Run in order:

```bash
# Stage 1: Scrape all sources (~2 min)
python scripts/stage1_scrape.py

# Stage 1b: Enrich via website scrape + LLM (~45 min scrape + ~25 min LLM)
python scripts/stage1b_enrich.py

# Stage 2: Deduplicate across sources (~5 sec)
python scripts/stage2_dedup.py

# Stage 3: Geocode all records (~15 min, cached after first run)
python scripts/stage3_geocode.py

# Stage 4: Normalize phones, hours, IDs (~instant)
python scripts/stage4_normalize.py

# Fix: Infer languages from ZIP demographics (~instant)
python scripts/fix_languages.py

# Stage 5: Export to frontend JSON (~instant)
python scripts/stage5_export.py

# Stage 7: Equity gap analysis (~instant)
python scripts/stage7_equity.py

# Stage 8: TLDAI accessibility index (~instant)
python scripts/stage8_tldai.py
```

Re-runs are fast — website scrape, LLM calls, and geocoding all use persistent caches in `pipeline/state/`.

## Output Files

### Frontend data (`public/data/`)

| File | Size | Contents |
|------|------|----------|
| `enriched-orgs.json` | 2.6 MB | 1,395 orgs with full enrichment |
| `equity-gaps.json` | 17 KB | 30 underserved areas with need/supply/gap scores |
| `access-summary.json` | 45 KB | Per-ZIP accessibility by day, language, dignity tier |
| `metadata.json` | 1 KB | Pipeline stats and source counts |

### Intermediate outputs (`pipeline/output/`)

| File | Stage | Records |
|------|-------|---------|
| `stage1_raw_records.json` | Scrape | 1,518 |
| `cafb_raw_features.json` | CAFB ArcGIS | 382 features with lat/lon |
| `stage1b_enriched_records.json` | Enrich | 1,518 |
| `stage2_deduped.json` | Dedup | 1,428 |
| `stage3_geocoded.json` | Geocode | 1,428 |
| `stage4_normalized.json` | Normalize | 1,428 |

### Caches (`pipeline/state/`)

| File | Entries | Purpose |
|------|---------|---------|
| `website-cache.json` | 778 | Playwright website scrape results |
| `stage1b-enrichment-cache.json` | 1,517 | Mistral LLM responses |
| `geocode-cache.json` | 1,166 | Nominatim geocode results |

### Logs (`pipeline/logs/`)

All logs are JSONL format with timestamps for audit:

| File | Entries | Purpose |
|------|---------|---------|
| `website_scrape.jsonl` | 778 | URL, status, latency, hours found |
| `llm_enrichment.jsonl` | 1,523 | Record name, cache hit/miss, fields extracted |
| `stage2_dedup.jsonl` | 391 | Merge decisions with scores |
| `stage3_geocode.jsonl` | 3,778 | Address, method, result coords |
| `template_fills.jsonl` | 598 | Template-generated fields per record |

## Novel Signals

### Equity Gap Analysis (Stage 7)

Computes supply vs need per ZIP code using org density against Census poverty/SNAP data. Identifies 30 underserved areas where new food distribution events would have the most impact.

```
Gap = max(0, NeedScore - SupplyScore)
NeedScore = 0.6 × poverty_rate + 0.4 × snap_rate
SupplyScore = weighted_org_count / (population / 5000) × NeedScore
```

### TLDAI — Temporal-Linguistic-Dignity Accessibility Index (Stage 8)

For each ZIP, answers: "Can a household speaking language L find a walk-in pantry on day D within 3km?"

Three dimensions:
- **Temporal**: which days of the week have open pantries
- **Linguistic**: which languages are served by nearby pantries
- **Dignity tier**: walk-in/no-ID (low friction) vs appointment/ID-required (high friction)

## LLM Enrichment

Uses **Mistral** (`ministral-8b-latest`) via function calling to extract structured fields from raw text + scraped website content:

- **Cost**: ~$0.21 for 1,518 records
- **Latency**: ~25 min sequential (0.15s sleep between calls)
- **Tool schema**: single `enrich_food_org` function extracting 15 fields in one call
- **Validation**: anti-hallucination check on hours (must appear in source text), banned words check on heroCopy, toneScore clamped to 0-1
- **Cache**: MD5-keyed persistent cache — re-runs cost $0

## Project Structure

```
pipeline/
├── .env                          # Mistral API key (gitignored)
├── .gitignore
├── requirements.txt
├── README.md
│
├── scripts/                      # 9 stage scripts
│   ├── stage1_scrape.py
│   ├── stage1b_enrich.py
│   ├── stage2_dedup.py
│   ├── stage3_geocode.py
│   ├── stage4_normalize.py
│   ├── stage5_export.py
│   ├── stage7_equity.py
│   ├── stage8_tldai.py
│   └── fix_languages.py
│
├── src/
│   ├── config.py                 # 6 source definitions
│   ├── scrapers/                 # 8 scrapers (Playwright + curl_cffi)
│   ├── utils/logger.py
│   └── validators/schemas.py     # Pydantic data models
│
├── output/                       # Intermediate stage results
├── state/                        # Persistent caches
└── logs/                         # JSONL audit logs
```
