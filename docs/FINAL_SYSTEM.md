# Nutrire — Final System Architecture

> This document describes the **implemented system** as submitted. Other docs in this folder contain design explorations and future-state plans that informed the build but do not reflect the shipped product.

---

## What Nutrire Is

Nutrire is a **static React/Vite single-page application** that helps households, donors, and volunteers find and engage with food assistance organizations across DC, Maryland, and Virginia.

There is **no live backend service**. All data is pre-computed by a Python pipeline at build time and shipped as static JSON. The only runtime API calls are:

- **Open-Meteo** — free weather API (no key), called per-org on detail pages
- **Browser Geolocation** — used for proximity ranking

Everything else — AI-generated copy, translations, transit directions, equity analysis — is baked into the JSON at build time.

---

## Data Pipeline (Build Time)

```
Stage 1    Scrape 6 sources (Playwright + curl_cffi)        → 1,518 raw records
Stage 1b   LLM enrichment (Mistral Small 8B)                → heroCopy, eligibility, guides
Stage 2    Cross-source deduplication (Union-Find fuzzy)     → 1,428 unique orgs
Stage 3    Geocoding (CAFB ArcGIS + Nominatim + ZIP)        → 100% lat/lon
Stage 4    Normalize (hours, phones, tags, reliability)      → structured records
Stage 5    Export to frontend JSON                           → public/data/enriched-orgs.json
Stage 7    Equity gap analysis (30 ZIPs, Census ACS)         → public/data/equity-gaps.json
Stage 8    TLDAI accessibility index (60 ZIPs)               → public/data/access-summary.json
Stage 9    Translation (Google Translate, es + am)           → ai.translations in enriched-orgs.json
```

**Pipeline location:** `pipeline/scripts/stage*.py`
**Pipeline config:** `pipeline/src/config.py` (6 enabled sources)
**Pipeline caches:** `pipeline/state/` (geocode, transit, enrichment, translation)

### Key design choices

- **Mistral Small** (open-weight, Apache 2.0) for LLM enrichment — reproducible, self-hostable
- **All caches are persistent** — re-runs skip completed work, full pipeline runs in ~5 min cached
- **No runtime LLM dependency** — AI content is pre-computed, not generated on the fly

---

## Frontend Architecture (Runtime)

```
React 18 + TypeScript + Vite
├── src/pages/           10 route pages
├── src/components/      Shared UI (TopNav, BackupCard, LocationInput, etc.)
├── src/i18n/            3-language system (EN/ES/AM) with useT() + useLocalizedAI()
├── src/lib/             Pure logic (ranking, open-status, freshness, weather, geo)
├── src/data/            Data loading + mock fallback
├── src/store/           Zustand store (location, language, intent)
└── public/data/         Static JSON (the pipeline's output)
```

### Three product doors

| Door | Routes | Purpose |
|------|--------|---------|
| **Find Food** | `/` → `/find` → `/org/:id` → `/all` | Household flow: location → best match → detail → alternatives |
| **Give Help** | `/give` → `/give/donate`, `/give/volunteer` | Donor/volunteer discovery |
| **Research** | `/map` → `/recommendations` → `/methodology` | Equity gap analysis + methodology |

### Ranking engine (`rank-orgs.ts`)

Local, deterministic, no backend. Scores each org on:

| Factor | Weight | Source |
|--------|--------|--------|
| Proximity | 0.35 | Haversine distance from browser geolocation |
| Open status | 0.25 | Parsed hours vs. current time |
| Access friction | 0.15 | walk-in/no-ID vs. appointment/paperwork |
| Data confidence | 0.15 | Freshness tier (fresh/recent/stale/unknown) |
| Tone warmth | 0.10 | LLM-generated tone score |

Optional boosts: language match (+0.08), service-intent chips from home hero.

### i18n system

- **UI strings:** `translations.ts` with ~140 keys in EN/ES/AM, resolved by `useT()` hook
- **AI content:** `ai.translations.es` / `ai.translations.am` on each org, resolved by `useLocalizedAI()` hook
- **Status labels:** `open-status.ts` returns `labelKey` + `labelVars`, resolved by `useStatusLabel()` hook
- **Coverage:** All 1,395 orgs have Spanish and Amharic translations of heroCopy, eligibility, firstVisitGuide, and culturalNotes

### Live signals (runtime)

| Signal | Source | Freshness |
|--------|--------|-----------|
| Weather | Open-Meteo API | Real-time (10-min cache) |
| Open/closed status | Parsed hours vs. `new Date()` | Real-time |
| Distance/walk time | Browser geolocation + haversine | Real-time |
| Freshness label | `reliability.lastConfirmedAt` timestamp | Relative ("2h ago") |

---

## Data Shape

The atomic unit is an **EnrichedOrganization** (`public/data/enriched-orgs.json`). Each record has:

```
identity:    id, name, address, phone, website, neighborhood, city, state, zip
geo:         lat, lon
tags:        services[], foodTypes[], accessRequirements[], languages[]
hours:       hoursRaw, ai.parsedHours (structured day/time slots)
ai:          heroCopy, plainEligibility, firstVisitGuide[], culturalNotes, toneScore
i18n:        ai.translations.es.{heroCopy, plainEligibility, firstVisitGuide, culturalNotes}
             ai.translations.am.{...}
transit:     transit.transitSummary, transit.transitDirections.naturalDirections
             nearestTransitLines[], nearestTransitType
reliability: reliability.{tier, score, lastConfirmedAt}
provenance:  sourceId, sourceName, sourceIds[], crossSourceCount
giving:      acceptsFoodDonations, acceptsMoneyDonations, acceptsVolunteers, donateUrl, volunteerUrl
```

### Coverage (1,395 orgs)

| Field | Coverage |
|-------|----------|
| name, address, coordinates | 100% |
| heroCopy | 98% |
| plainEligibility, firstVisitGuide | 100% |
| Translations (es + am) | 100% |
| foodTypes | 99% |
| Phone | 99% |
| Hours (raw) | 54% |
| Hours (structured/parseable) | 31% |
| Languages (non-English) | 51% |
| Transit directions | 29% |
| Neighborhood | 33% |

---

## What the docs/ folder contains

| File | Status |
|------|--------|
| `FINAL_SYSTEM.md` | **This file.** Canonical description of the shipped system. |
| `DESIGN.md` | UI/UX design language and component spec. Written early in the project as the build target. The shipped app evolved from this spec, adopting a glassmorphism aesthetic and different component names, but the core design principles (warmth, dignity, one-answer-not-a-list) held. |
| `COPY.md` | Tone and copy guidelines. Current and enforced throughout the UI. |
| `STITCH_PROMPT.md` | Design brief used for screen mockups. Reference only. |

---

## Deployment

- **Build:** `npm run build` → `dist/`
- **Deploy:** GitHub Pages via GitHub Actions (`.github/workflows/deploy.yml`)
- **Base path:** `/NUTRIRE/`
- **No server required.** The entire app is static files.
