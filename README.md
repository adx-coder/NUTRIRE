# Nutrire

**Free groceries and meals, near you.**

A premium, mobile-first food access app for the DC/Maryland/Virginia metro area. Nutrire transforms fragmented, unstructured data from community websites into a one-stop source of information for households, donors, and volunteers.

**Live demo:** [https://adx-coder.github.io/NUTRIRE/](https://adx-coder.github.io/NUTRIRE/)

---

## What it does

- **Households** find their single best food option in under 10 seconds, with LLM-generated "what to expect" guides that reduce first-visit anxiety
- **Donors** discover which organizations accept food or money donations nearby
- **Volunteers** find shifts at organizations that match their availability and language skills
- **Researchers** explore an equity gap analysis across 60+ census tracts with need/supply/gap scoring

## Key features

| Feature | Description |
|---|---|
| **1,395 organizations** | Scraped, deduplicated, geocoded, and enriched from 6 DMV data sources |
| **AI enrichment** | LLM-generated heroCopy, eligibility summaries, first-visit guides, and cultural notes for every org |
| **Multilingual** | Full UI + AI content translated into English, Spanish, and Amharic (the 3 DMV priority languages) |
| **Live weather** | Real-time weather from Open-Meteo API shown on every org card |
| **Real-time open/closed** | Parsed hours matched against current time for live status |
| **Browser geolocation** | Results ranked by proximity using the browser's location API |
| **Equity gap engine** | Need vs. supply analysis across 60+ ZIP codes with gap recommendations |
| **Transit directions** | WMATA bus/metro stop data with walking distances and natural language directions |
| **Confidence scoring** | Multi-factor reliability tiers (fresh/recent/stale) with source cross-validation |

## Architecture

```
Pipeline (offline, Python)          Frontend (React + Vite)
========================          =======================
Scrape 6 sources                  Static JSON (no backend)
  -> Dedup + geocode              React 18 + TypeScript
  -> LLM enrich (Mistral 8B)     Tailwind CSS + Framer Motion
  -> Transit (WMATA)              MapLibre GL (maps)
  -> Normalize + export           Zustand (state)
  -> Translate (es/am)            Open-Meteo (live weather)
  -> Equity gap analysis
```

**No runtime LLM dependency.** All AI content is pre-computed during the pipeline and shipped as static JSON. The frontend is a pure React SPA deployable on GitHub Pages with zero backend.

## Quick start

```bash
# Install
npm install

# Development
npm run dev
# Open http://localhost:5173

# Production build
npm run build
npm run preview
```

### Requirements

- Node.js 18+
- npm 9+

### Pipeline (optional — data is pre-built)

The data pipeline that produces `public/data/enriched-orgs.json` is in the `pipeline/` directory. To re-run it:

```bash
cd pipeline
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt

# Run stages sequentially
python scripts/stage1_scrape.py
python scripts/stage1b_enrich.py    # requires MISTRAL_API_KEY
python scripts/stage2_dedup.py
python scripts/stage3_geocode.py
python scripts/stage4_normalize.py
python scripts/stage5_export.py
python scripts/stage7_equity.py
python scripts/stage8_tldai.py
python scripts/stage9_translate.py   # requires ANTHROPIC_API_KEY or deep-translator
```

## Data sources

| Source | Type | Records |
|---|---|---|
| Capital Area Food Bank | HTML scrape | 800+ |
| Maryland Food Bank | HTML scrape | 200+ |
| 211 Maryland | HTML scrape | 150+ |
| Montgomery County Food Council | HTML scrape | 100+ |
| PG County Food Equity Council | HTML scrape | 50+ |
| Caroline County | HTML scrape | 20+ |

Additional enrichment: US Census/ACS (poverty, income, vehicle access), WMATA transit API, Open-Meteo weather API.

## Tech stack

- **React 18** + TypeScript + Vite
- **Tailwind CSS** — utility-first styling with custom design tokens
- **Framer Motion** — entrance animations and micro-interactions
- **MapLibre GL** — vector tile maps (Carto Voyager basemap)
- **Zustand** — lightweight state management
- **Open-Meteo** — free real-time weather API (no key required)
- **Fuse.js** — fuzzy search across org names and descriptions

## Project structure

```
src/
  pages/          Home, BestMatch, OrgDetail, AllOptions, Map,
                  Recommendations, Donate, Volunteer, Methodology
  components/     TopNav, BackupCard, LocationInput, LangSwitcher, Chip
  i18n/           translations.ts, useT.ts, useLocalizedAI.ts
  lib/            open-status, freshness, rank-orgs, weather, geo
  data/           load-data.ts, mock-orgs.ts
  store/          location.ts (Zustand)

pipeline/
  scripts/        stage1–9 pipeline scripts
  src/            scrapers, validators, config
  state/          caches (geocode, transit, translation)
  output/         intermediate pipeline outputs

public/data/      Final JSON consumed by the frontend
```

## Team

Built for the **NourishNet Data Challenge 2025**, organized by the University of Maryland with NSF funding.

## License

MIT
