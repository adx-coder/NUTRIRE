# Nutrire — Food Access Intelligence Pipeline

A 10-stage data pipeline that scrapes, enriches, deduplicates, geocodes, and exports **1,395 food assistance organizations** across DC, Maryland, and Virginia into frontend-ready JSON.

Built for the NourishNet Data Challenge 2026.

## Architecture

```
Source Layer        5 scrapers (Playwright + curl_cffi)
                    ↓ 1,518 raw records
Enrichment Layer    Website scrape → Mistral Small LLM → template fallback
                    ↓ heroCopy, hours, languages, eligibility, donations
Dedup Layer         Cross-source fuzzy matching (Union-Find)
                    ↓ 1,428 unique orgs
Geo Layer           CAFB ArcGIS + Nominatim + ZIP centroid → 100% lat/lon
                    ↓
Normalize Layer     Phone, hours, IDs, reliability, foodTypes, culturalNotes
                    ↓
Transit Layer       WMATA Metro/Bus + OSRM road routing → walk times
                    ↓
Weather Layer       NWS alerts → severity, travel disruption flags
                    ↓
Analytics Layer     Equity gaps (30 ZIPs) + TLDAI accessibility (60 ZIPs)
                    ↓
Export              → frontend/public/data/*.json (4 files, frontend-ready)
```

## Quick Start

```bash
# Setup
cp .env.example .env         # add your Mistral API key
pip install -r requirements.txt
playwright install chromium

# Run full pipeline (~45 min first run, ~5 min cached)
python scripts/stage1_scrape.py
python scripts/stage1b_enrich.py
python scripts/stage2_dedup.py
python scripts/stage3_geocode.py
python scripts/stage4_normalize.py
python scripts/fix_languages.py
python scripts/stage6_transit.py
python scripts/stage9_weather.py
python scripts/stage7_equity.py
python scripts/stage8_tldai.py
python scripts/stage5_export.py
```

All stages use persistent caches. Re-runs are instant except for the first scrape and LLM enrichment.

## Data Sources

| Source | Scraper | Method | Records |
|--------|---------|--------|---------|
| Capital Area Food Bank | `cafb.py` | Playwright → ArcGIS FeatureServer API | 382 |
| Maryland Food Bank | `mdfb.py` | Playwright pagination (29 pages) | 285 |
| 211 Maryland | `two11md.py` | Playwright Next.js SSR pagination | 403 |
| 211 Virginia | `two11md.py` | Playwright Next.js SSR pagination | 343 |
| MoCo Food Council | `mocofood.py` | DRTS WordPress plugin structured fields | 105 |

Cloudflare-protected sites use `curl_cffi` with Chrome TLS fingerprint impersonation.

## Data Quality (Post-Pipeline)

| Field | Coverage | Method |
|-------|----------|--------|
| Coordinates | 100% (1,395) | CAFB ArcGIS + Nominatim + ZIP centroid |
| Phone | 99% | Scraper |
| heroCopy | 97% (1,367) | Mistral Small LLM + diversified templates |
| firstVisitGuide | 100% | Mistral Small LLM + templates |
| plainEligibility | 100% | Mistral Small LLM + 5-variant templates |
| foodTypes | 99% | LLM + heuristic defaults |
| Hours | 54% (757) | Scraper + website scrape + LLM |
| Languages | 51% (713) | Scraper + LLM + ZIP-based inference |
| Website | 88% | Scraper + CAFB directory fallback |
| culturalNotes | 19% (259) | LLM + name/language heuristics |
| Transit (metro/bus) | 29% (402) | WMATA API + OSRM routing |
| Weather alerts | 71% (993) | NWS API (real-time snapshot) |
| Neighborhood | 32% (458) | ZIP → neighborhood mapping (90 DMV ZIPs) |
| Urgency signal | 4% (56) | Equity gap cross-reference |
| Donations accepted | 23% | LLM + website evidence |
| Volunteers accepted | 18% | LLM + website evidence |

## Novel Signals

### Equity Gap Analysis (Stage 7)

Identifies **30 underserved ZIP codes** by computing supply vs need:

```
NeedScore  = 0.6 * poverty_rate + 0.4 * snap_rate
SupplyScore = weighted_org_count / (population / 5000) * NeedScore
Gap         = max(0, NeedScore - SupplyScore)
```

Uses hardcoded Census ACS poverty/SNAP data for 60 DMV ZIP codes. Each gap includes a suggested host org for new distribution events.

### TLDAI — Temporal-Linguistic-Dignity Accessibility Index (Stage 8)

For each ZIP, answers: *"Can a household speaking language L find a walk-in pantry on day D within 3km?"*

Three dimensions scored per ZIP:
- **Temporal** — which days of the week have open pantries nearby
- **Linguistic** — which languages are served by nearby pantries
- **Dignity** — walk-in/no-ID (low friction) vs appointment/ID-required (high friction)

### Generalized-Cost Transit Mode Selection (Stage 6)

Research-backed model for recommending Metro vs Bus:

```
cost = walk_minutes * 1.5 + avg_wait * 1.2
```

Metro's frequency advantage (3 min avg wait vs 10 min for bus) gives it an 8.4-minute equivalent advantage, matching research showing riders walk 2-2.5x further for rail.

### Urgency Signals for Donors

Cross-references equity gap scores with individual orgs: *"Donations to this pantry go 3.2x further — Fort Washington has 6,860 underserved residents but only 3 food resources."*

## LLM Enrichment

We use **Mistral Small** — an open-weight model (Apache 2.0 license, weights available on Hugging Face) — deliberately chosen for **full reproducibility**. Any researcher can download the model weights and reproduce our enrichment results exactly, without depending on a proprietary API. The versioned cache key (`PROMPT_VERSION + combined_text`) ensures deterministic outputs across runs.

| Parameter | Value |
|-----------|-------|
| Model | `mistral-small-latest` (open-weight, 119B MoE, 6.5B active params) |
| License | Apache 2.0 (weights on HuggingFace: `mistralai/Mistral-Small-3.1-24B-Instruct-2503`) |
| Cost | ~$0.80 for 1,518 records via Mistral API |
| Method | Function calling with 15-field tool schema (`enrich_food_org`) |
| Validation | Anti-hallucination on hours (token evidence check), banned-word filter on heroCopy, URL evidence check on donate/volunteer URLs, boilerplate detection and replacement |
| Cache | Versioned MD5 key (`PROMPT_VERSION + combined_text`) — prompt or model changes auto-invalidate |
| Reproducibility | Self-hostable via vLLM/Ollama with identical weights; API results cached for offline replay |

## Output Files

### Frontend (`frontend/public/data/`)

| File | Records | Description |
|------|---------|-------------|
| `enriched-orgs.json` | 1,395 | Full org records with 50+ fields |
| `equity-gaps.json` | 30 | Underserved ZIP codes with gap scores |
| `access-summary.json` | 60 | Per-ZIP accessibility by day/language/dignity |
| `metadata.json` | — | Pipeline stats, source counts, coverage |

### Intermediate (`output/`)

| File | Stage | Records |
|------|-------|---------|
| `stage1_raw_records.json` | Scrape | 1,518 |
| `stage1b_enriched_records.json` | Enrich | 1,518 |
| `stage2_deduped.json` | Dedup | 1,428 |
| `stage3_geocoded.json` | Geocode | 1,428 |
| `stage4_normalized.json` | Normalize | 1,428 |
| `stage6_transit.json` | Transit | 1,428 |
| `stage9_weather.json` | Weather | 1,428 |

### Caches (`state/`) and Logs (`logs/`)

All caches are JSON. All logs are JSONL with timestamps. Re-runs hit cache and cost $0.

## External APIs

| API | Key | Cost | Stage |
|-----|-----|------|-------|
| Mistral AI | `MISTRAL_API_KEY` | ~$0.80/run | 1b |
| WMATA | `WMATA_API_KEY` | Free | 6 |
| OSRM | None | Free | 6 |
| NWS | None | Free | 9 |
| Nominatim | None | Free (1 req/s) | 3 |

## Project Structure

```
Nutrire/
├── .env.example              # API key template
├── requirements.txt          # Python dependencies
├── README.md
│
├── scripts/                  # Pipeline stages (run in order)
│   ├── stage1_scrape.py      # 5-source scraping
│   ├── stage1b_enrich.py     # Website scrape + Mistral LLM + templates
│   ├── stage2_dedup.py       # Cross-source deduplication
│   ├── stage3_geocode.py     # 3-tier geocoding
│   ├── stage4_normalize.py   # Phone, hours, IDs, defaults
│   ├── fix_languages.py      # ZIP-based language inference
│   ├── stage6_transit.py     # WMATA + OSRM transit
│   ├── stage9_weather.py     # NWS weather alerts
│   ├── stage7_equity.py      # Equity gap analysis
│   ├── stage8_tldai.py       # TLDAI accessibility index
│   ├── stage5_export.py      # Export to frontend JSON
│   ├── analytics_server.py   # Search analytics endpoint
│   └── test_transit_weather.py  # Integration tests
│
├── src/
│   ├── config.py             # Source definitions (24 sources, 6 enabled)
│   ├── scrapers/             # Playwright + curl_cffi scrapers
│   │   ├── cafb.py           # ArcGIS FeatureServer via in-browser fetch
│   │   ├── mdfb.py           # GeoMyWP pagination
│   │   ├── two11md.py        # Next.js SSR pagination (MD + VA)
│   │   ├── mocofood.py       # DRTS WordPress plugin
│   │   ├── pgcfec.py         # PG County (disabled, iframe-only)
│   │   ├── caroline.py       # Caroline County (disabled, not metro DMV)
│   │   ├── generic_html.py   # Fallback HTML parser
│   │   └── generic_pdf.py    # PDF parser
│   ├── utils/
│   │   └── logger.py         # Colorama console logger + UTF-8 safety
│   └── validators/
│       └── schemas.py        # Pydantic models (RawRecord, NormalizedRecord)
│
├── output/                   # Intermediate stage results (gitignored)
├── state/                    # Persistent caches (gitignored)
├── logs/                     # JSONL audit logs (gitignored)
│
└── frontend/                 # React + Vite app (separate)
    └── public/data/          # Pipeline outputs consumed by frontend
```
