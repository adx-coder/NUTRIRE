<p align="center">
  <img src="public/logos/nutrire-full.png" alt="Nutrire" width="280" />
</p>

<h3 align="center">Free groceries and meals, near you.</h3>

<p align="center">
  <a href="https://adx-coder.github.io/NUTRIRE/">
    <img src="https://img.shields.io/badge/Live_Demo-adx--coder.github.io-4F7F6A?style=for-the-badge" alt="Live Demo" />
  </a>
  &nbsp;
  <img src="https://img.shields.io/badge/Organizations-1,395-D9A441?style=for-the-badge" alt="1,395 orgs" />
  &nbsp;
  <img src="https://img.shields.io/badge/Languages-EN_·_ES_·_AM-C96F4A?style=for-the-badge" alt="3 languages" />
</p>

<p align="center">
  <em>A premium, mobile-first food access intelligence app for the DC / Maryland / Virginia metro area.<br/>
  Built for the <strong>NourishNet Data Challenge 2025</strong> - University of Maryland · NSF Funded.</em>
</p>

---

## The Problem

Food distribution in the DMV is fragmented across hundreds of nonprofits, churches, food banks, and community groups - each with their own websites, schedules, and eligibility rules. A family in need has to check multiple sites, interpret inconsistent formats, and hope the information is current. **Nutrire fixes this.**

## What Nutrire Does

<table>
<tr>
<td width="50%">

### For Households
One answer, not a list. Nutrire picks your **single best option** based on distance, open status, access friction, and data confidence - then explains what to expect in warm, anxiety-reducing language.

### For Donors & Volunteers
Discover which organizations near you accept food, money, or time. Filter by distance, donation type, or language need.

</td>
<td width="50%">

### For Researchers
An **equity gap engine** that identifies underserved ZIP codes by computing need (poverty, SNAP rates) vs. supply (nearby orgs, frequency, hours). Surfaces where new pantries would close the biggest gaps.

### Multilingual
Full UI + all AI-generated content translated into **English, Spanish, and Amharic** - the three priority languages of the DMV.

</td>
</tr>
</table>

---

## Key Features

| | Feature | Description |
|---|---|---|
| **📊** | **1,395 organizations** | Scraped, deduplicated, geocoded from 6 DMV data sources |
| **🤖** | **AI enrichment** | LLM-generated hero copy, eligibility summaries, first-visit guides, cultural notes |
| **🌍** | **Trilingual** | Full UI + AI content in English, Spanish, Amharic |
| **🌦️** | **Live weather** | Real-time conditions from Open-Meteo on every org card |
| **⏰** | **Real-time status** | Parsed hours vs. current time = live open/closed detection |
| **📍** | **Geolocation ranking** | Browser location API → proximity-scored results |
| **📈** | **Equity gap analysis** | Need vs. supply across 60+ ZIP codes with gap recommendations |
| **🚌** | **Transit directions** | WMATA bus/metro with walking distances + natural language directions |
| **✅** | **Confidence scoring** | Multi-factor reliability tiers with source cross-validation |

---

## Architecture

```
┌─────────────────────────────────┐     ┌──────────────────────────────┐
│     DATA PIPELINE (Python)      │     │     FRONTEND (React/Vite)    │
│                                 │     │                              │
│  Scrape 6 sources               │     │  Static JSON - no backend    │
│  ↓                              │     │                              │
│  LLM enrich (Mistral Small)     │     │  React 18 + TypeScript       │
│  ↓                              │     │  Tailwind CSS + Framer Motion│
│  Dedup + geocode                │────▶│  MapLibre GL (maps)          │
│  ↓                              │     │  Zustand (state)             │
│  Transit (WMATA API)            │     │  Open-Meteo (live weather)   │
│  ↓                              │     │  Fuse.js (fuzzy search)      │
│  Translate (ES + AM)            │     │                              │
│  ↓                              │     │  3 product doors:            │
│  Equity gap analysis            │     │    /find  → households       │
│  ↓                              │     │    /give  → donors/volunteers│
│  Export → public/data/*.json    │     │    /map   → researchers      │
└─────────────────────────────────┘     └──────────────────────────────┘
```

**No runtime LLM dependency.** All AI content is pre-computed and shipped as static JSON. The frontend is a pure SPA deployable on GitHub Pages with zero backend.

---

## Data Pipeline

9 stages, fully cached, re-runs in ~5 minutes:

| Stage | Script | What it does |
|-------|--------|-------------|
| 1 | `stage1_scrape.py` | Scrape 6 DMV food resource websites |
| 1b | `stage1b_enrich.py` | LLM enrichment via Mistral Small (open-weight) |
| 2 | `stage2_dedup.py` | Cross-source fuzzy deduplication |
| 3 | `stage3_geocode.py` | Geocode all addresses to lat/lon |
| 4 | `stage4_normalize.py` | Normalize hours, phones, tags, reliability |
| 5 | `stage5_export.py` | Export to frontend JSON |
| 7 | `stage7_equity.py` | Equity gap analysis (Census ACS data) |
| 8 | `stage8_tldai.py` | Temporal-Linguistic-Dignity Accessibility Index |
| 9 | `stage9_translate.py` | Translate AI content to Spanish + Amharic |

### Data Sources

| Source | Method | Records |
|--------|--------|---------|
| Capital Area Food Bank | ArcGIS API + Playwright | 800+ |
| Maryland Food Bank | Playwright pagination | 285+ |
| 211 Maryland | Next.js SSR scrape | 400+ |
| Montgomery County Food Council | WordPress plugin | 105+ |
| PG County Food Equity Council | HTML scrape | 50+ |
| Additional: US Census/ACS, WMATA API, Open-Meteo | APIs | enrichment |

### Data Coverage (1,395 orgs)

| Field | Coverage |
|-------|----------|
| Name, address, coordinates | 100% |
| AI hero copy + eligibility + first-visit guide | 98-100% |
| Spanish + Amharic translations | 100% |
| Food types | 99% |
| Phone | 99% |
| Hours (raw) | 54% |
| Languages spoken (non-English) | 51% |
| Transit directions | 29% |

---

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev          # → http://localhost:5173

# Production build
npm run build
npm run preview      # → preview the built app
```

**Requirements:** Node.js 18+, npm 9+

### Re-running the pipeline (optional - data is pre-built)

```bash
cd pipeline
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt

python scripts/stage1_scrape.py      # scrape sources
python scripts/stage1b_enrich.py     # LLM enrich (needs MISTRAL_API_KEY)
python scripts/stage2_dedup.py       # deduplicate
python scripts/stage3_geocode.py     # geocode addresses
python scripts/stage4_normalize.py   # normalize fields
python scripts/stage5_export.py      # export to frontend JSON
python scripts/stage7_equity.py      # equity gap analysis
python scripts/stage8_tldai.py       # accessibility index
python scripts/stage9_translate.py   # translate to ES + AM
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite |
| Styling | Tailwind CSS, Framer Motion |
| Maps | MapLibre GL (Carto Voyager tiles) |
| State | Zustand |
| Search | Fuse.js |
| Weather | Open-Meteo (free, no API key) |
| i18n | Custom `useT()` + `useLocalizedAI()` hooks |
| Pipeline | Python, Playwright, Mistral Small LLM |
| Deploy | GitHub Pages via GitHub Actions |

---

## Project Structure

```
src/
  pages/           Home, BestMatch, OrgDetail, AllOptions, Map,
                   Recommendations, Donate, Volunteer, GiveHome, Methodology
  components/      TopNav, BackupCard, LocationInput, LangSwitcher,
                   Chip, ErrorBoundary, GlassBackdrop, PageHeader
  i18n/            translations.ts (140 keys × 3 langs), useT.ts, useLocalizedAI.ts
  lib/             rank-orgs, open-status, freshness, use-weather, geo, time
  data/            load-data.ts, mock-orgs.ts
  store/           location.ts (Zustand)

pipeline/
  scripts/         9 pipeline stages
  src/             scrapers (6), validators, config
  state/           persistent caches

public/data/       Shipped JSON (enriched-orgs, equity-gaps, access-summary, metadata)
docs/              FINAL_SYSTEM.md (canonical arch), design specs, schema docs
```

---

## Novel Contributions

### Equity Gap Engine
Identifies 30 underserved ZIP codes using Census ACS poverty/SNAP data vs. org supply density. Each gap includes a suggested host organization for new distribution events.

### TLDAI - Temporal-Linguistic-Dignity Accessibility Index
For each ZIP: *"Can a household speaking language L find a walk-in pantry on day D within 3km?"* Three dimensions: temporal coverage, linguistic access, dignity (friction level).

### AI-Powered First-Visit Guides
Every organization has a warm, LLM-generated "what to expect" guide that reduces the anxiety of visiting a food pantry for the first time - a UX innovation no other food access tool offers.

---

<p align="center">
  <img src="public/logos/nutrire-mark.png" alt="Nutrire" width="40" />
  <br/>
  <sub>NourishNet Data Challenge 2025 · University of Maryland · NSF Funded</sub>
  <br/>
  <sub>MIT License</sub>
</p>
