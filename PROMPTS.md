# Nutrire - Kiro Prompt Markdown

## Read This First

This prompt pack is written for **independent judge replication in Kiro on a clean machine**.

The app is **not valid** if it renders a beautiful interface with zero organizations. The core experience depends on shipped JSON data. Therefore:

1. **Run Prompt 0 first.**
2. Prompts 1-9 may assume the data files exist **only after Prompt 0 succeeds**.
3. If the checked-in data files are missing, Kiro must generate a **seeded fallback dataset** large enough to demonstrate the product end to end.
4. Do **not** silently proceed with an empty array and do **not** use a tiny 5-record mock as the main dataset.

The final app should prove these three things to a judge:

- A household can find a strong food-access option immediately.
- A donor or volunteer can discover nearby ways to help.
- A researcher can inspect non-empty equity gap analysis and mapped resources.

## Context for Kiro

We are building **Nutrire**, a mobile-first food access app for the DC / Maryland / Virginia metro area. It transforms fragmented directory data into a unified, warm, premium-feeling tool for:

- households seeking food
- donors wanting to help
- volunteers looking for opportunities
- researchers reviewing access gaps

The app is a static React SPA deployed on GitHub Pages. The shipped implementation uses frontend-consumable JSON files in `public/data/`:

- `public/data/enriched-orgs.json`
- `public/data/equity-gaps.json`
- `public/data/access-summary.json`
- `public/data/metadata.json`

When the repo is complete, these files contain roughly:

- 1,395 organizations
- 30 equity gaps
- non-empty access summary metadata

The prompt pack must still work on a clean machine even if those files are absent.

## Prompt 0: Data Bootstrap and Replication Guardrails

Create the folders `public/data`, `src/data`, and `src/types.ts` if they do not already exist.

### Critical rule

The application must never depend on hidden local files or unstated setup. Before building UI pages, make sure the data files below exist and are non-empty:

- `public/data/enriched-orgs.json`
- `public/data/equity-gaps.json`
- `public/data/access-summary.json`
- `public/data/metadata.json`

### Preferred behavior

If these files already exist in the workspace, **preserve and use them exactly as checked in**.

### Required fallback behavior on a clean machine

If any of the files are missing, create a seeded demo dataset that is rich enough for judges to test the product properly.

Minimum seeded fallback requirements:

- at least **24 organizations** across DC, MD, and VA
- at least **8 organizations with structured hours**
- at least **8 organizations open now or opening today**
- at least **8 organizations with `acceptsFoodDonations` or `acceptsMoneyDonations`**
- at least **8 organizations with `acceptsVolunteers`**
- at least **8 organizations with Spanish or Amharic in `languages`**
- at least **10 organizations with valid `lat` and `lon` spread across the region**
- at least **8 equity gap records**
- at least **8 access summary ZIP entries**

The seeded data must exercise the real UI:

- groceries
- hot meals
- baby supplies
- map pins
- best-match ranking
- org detail
- donate flow
- volunteer flow
- recommendations

Include realistic DMV examples such as DC, Silver Spring, Langley Park, Hyattsville, Rockville, Alexandria, and Arlington. Use warm but plain-language AI copy.

### Metadata requirements

If generating fallback metadata, set:

- `totalOrganizations` to the number of seeded orgs
- `generatedAt` to an ISO timestamp
- `coverage` object with counts for hours, coords, languages, and hero copy

### Acceptance checks for Prompt 0

After Prompt 0, these must be true:

- `public/data/enriched-orgs.json` exists and contains a non-empty array
- `public/data/equity-gaps.json` exists and contains a non-empty `gaps` array
- `public/data/access-summary.json` exists and contains non-empty ZIP summary data
- `public/data/metadata.json` exists and reports a non-zero organization count

Do not continue to later prompts until these conditions are satisfied.

---

## Prompt 1: Project Foundation

Create a React + Vite + TypeScript project called `Nutrire` with this setup.

### Dependencies

- react
- react-dom
- react-router-dom v6
- tailwindcss
- postcss
- autoprefixer
- framer-motion
- zustand
- maplibre-gl
- react-map-gl
- react-leaflet
- leaflet
- lucide-react
- clsx
- fuse.js
- date-fns

### Tailwind and design tokens

Create `src/styles/tokens.css` with CSS variables:

- background `#EDE8E0`
- ink `#1F2421`
- ink-soft `#4A524E`
- ink-muted `#7E867F`
- sage `#4F7F6A`
- sage-deep `#3A6551`
- sage-soft `#E8EFE9`
- terracotta `#C96F4A`
- mustard `#D9A441`
- stone `#9A9A92`

Extend Tailwind so these are available as utility classes such as `bg-sage-deep`, `text-ink`, `border-terracotta`.

### Fonts

Import Inter for body text and Inter Tight for display text in `index.html`.

### TypeScript data model

Create `src/types.ts` and define the main frontend shape around `EnrichedOrganization`, `OpenStatus`, and `RankedOrg`. Match the shipped backend-facing model used by the app, including:

- identity and contact
- geography
- services
- food types
- access requirements
- languages
- reliability
- AI block
- transit block
- donation and volunteer flags
- weather alert
- open status
- ranked result

### Data loader

Create `src/data/load-data.ts`.

Requirements:

- export `useOrgs()`
- export `getOrgs()`
- export `getEquityGaps()`
- export `getAccessSummary()`
- export `mockUserLocation` at Washington DC center
- fetch from `data/enriched-orgs.json`, `data/equity-gaps.json`, and `data/access-summary.json`
- if those files fail to load, use the seeded dataset created in Prompt 0 rather than a tiny toy fallback
- use singleton caching so multiple pages do not refetch repeatedly

### State

Create `src/store/location.ts` with Zustand store values:

- `location`
- `language` as `"en" | "es" | "am"`
- `intent`

Actions:

- `setLocation`
- `setLanguage`
- `setIntent`

### Routes

Create `src/App.tsx` with routes:

- `/` Home
- `/find` BestMatch
- `/org/:id` OrgDetail
- `/all` AllOptions
- `/give` GiveHome
- `/give/donate` Donate
- `/give/volunteer` Volunteer
- `/map` Map
- `/recommendations` Recommendations
- `/methodology` Methodology

Catch-all redirects to `/`.

### Document shell

In `index.html`:

- set `viewport-fit=cover`
- set `theme-color` to `#EDE8E0`
- use title `Nutrire - Free groceries and meals near you`
- set favicon to `/favicon.png`

### Acceptance checks for Prompt 1

- the app boots
- routing works
- the data loader returns non-empty org data when Prompt 0 succeeded

---

## Prompt 2: Core Utility Libraries

Create these files:

- `src/lib/geo.ts`
- `src/lib/time.ts`
- `src/lib/open-status.ts`
- `src/lib/freshness.ts`
- `src/lib/rank-orgs.ts`
- `src/lib/use-weather.ts`

### Required functions

`src/lib/geo.ts`

- `haversineMeters(a, b)`
- `walkMinutes(meters)` using roughly meters / 80
- `driveMinutes(meters)` using roughly meters / 450 with minimum 3

`src/lib/time.ts`

- `relativeTimeShort(iso)`

`src/lib/open-status.ts`

- `computeOpenStatus(org, now)`
- parse `org.ai.parsedHours`
- return states: `open`, `opens_today`, `opens_this_week`, `closed_long`, `unknown`
- return readable English fallback label plus translation key data

`src/lib/freshness.ts`

- `reliabilityTone(r)`
- returns dot color, label, translation metadata, and whether the org should be promoted or deserves an urgent call-first cue

`src/lib/rank-orgs.ts`

- rank by proximity, open status, access friction, confidence, tone, language match, and optional service intent
- return sorted `RankedOrg[]`

`src/lib/use-weather.ts`

- fetch from Open-Meteo
- 10-minute in-memory cache
- silent failure

### Acceptance checks for Prompt 2

- a non-empty org dataset can be ranked
- open status labels are computed
- weather hook does not crash if the API fails

---

## Prompt 3: Internationalization

Create a complete i18n system for:

- English
- Spanish
- Amharic

Files:

- `src/i18n/translations.ts`
- `src/i18n/useT.ts`
- `src/i18n/useLocalizedAI.ts`
- `src/components/LangSwitcher.tsx`

### Requirements

- translate navigation, home, match, org detail, filters, map, recommendations, methodology, donate, volunteer, and give-home labels
- use interpolation with `{{var}}`
- fall back to English if a key is missing
- if AI translations exist in `org.ai.translations[lang]`, prefer them
- `LangSwitcher` must use accessible radio semantics

### Acceptance checks for Prompt 3

- switching language updates visible UI labels
- AI copy falls back safely to English if translations are absent

---

## Prompt 4: Shared Layout and Interaction Rules

Build shared UI primitives and rules before the pages:

- `TopNav`
- `LocationInput`
- `BackupCard`
- `Chip`
- `GlassBackdrop`
- `PageHeader`
- `ErrorBoundary`

### Non-negotiable UX rules

- no nested interactive elements
- all icon-only buttons have `aria-label`
- direct route loads must still have safe back behavior
- pages must never strand the user on an unusable empty state
- all major empty states must provide a next action

### Design language

Warm premium glass aesthetic:

- warm paper background
- low-opacity sage / mustard / lilac orbs
- subtle grain texture
- translucent cards with blur and white borders
- no charity brochure feeling
- no stock-photo aesthetic
- no government portal styling

---

## Prompt 5: Home Page

Build `src/pages/Home.tsx`.

This is the first thing judges see, so it must immediately prove the app is real.

### Layout

- full viewport height
- no desktop scroll
- top nav with logo, links, language switcher, mobile menu
- central hero with display headline
- location input
- quick actions for groceries, hot meals, baby supplies
- trending strip populated from real org data

### Hero requirements

- warm premium glass look
- headline feels decisive and welcoming
- no institutional tone
- show a rotating “verified resources” tagline in multiple languages
- if `metadata.totalOrganizations` is available, use that count in the hero copy

### Critical data proof

The home page must demonstrate that the dataset is non-empty:

- trending strip shows real organizations from loaded data
- if data exists, do not show a toy demo count
- if only seeded fallback data exists, the UI should still look complete and non-empty

### Acceptance checks for Prompt 5

- home renders with non-empty trending results
- quick action chips navigate to filtered search flow
- the page looks complete on desktop and mobile

---

## Prompt 6: Best Match and Org Detail

Create:

- `src/pages/BestMatch.tsx`
- `src/pages/OrgDetail.tsx`

### BestMatch

This is the core innovation: one answer, not a list.

- use `rankOrgs()`
- promote the best result into a hero surface
- show status, name, neighborhood, hero copy, reliability, weather, and travel framing
- include a map strip with user pin, org pin, and route line
- action row includes directions, share, and call when phone is present
- show backup alternatives below

### OrgDetail

Full deep-dive view:

- map area
- identity card
- what-to-expect guide
- eligibility
- food types
- hours
- transit guidance
- fallback alternatives

### Map requirement for these pages

Use **MapLibre with the exact Carto Voyager style URL**:

`https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json`

Do not leave the basemap source vague. Do not substitute another provider unless Carto Voyager fails.

If the basemap fails to load:

- keep the page usable
- show the rest of the card content
- do not blank the route

### Acceptance checks for Prompt 6

- `/find` shows a real ranked best match from loaded data
- `/org/:id` works when opened directly
- the map uses the exact Carto Voyager style URL

---

## Prompt 7: All Options, Donate, Volunteer, Give

Create:

- `src/pages/AllOptions.tsx`
- `src/pages/Donate.tsx`
- `src/pages/Volunteer.tsx`
- `src/pages/GiveHome.tsx`

### AllOptions

- fuzzy search across org names and AI copy
- filters for open now, today, walkable, near metro, Spanish, Amharic, no ID, delivers
- list and optional map layout
- non-empty state if data exists

### Donate

- show nearby organizations that accept food or money
- provide clear CTA buttons
- no nested clickable cards

### Volunteer

- show organizations that accept volunteers
- filters like distance and sign-up link
- show language demand where available

### GiveHome

- two clear doorways: donate and volunteer

### Acceptance checks for Prompt 7

- `/all` returns real results, not an empty shell
- `/give/donate` and `/give/volunteer` have non-empty cards if the dataset supports them

---

## Prompt 8: Equity Map, Recommendations, Methodology

Create:

- `src/pages/Map.tsx`
- `src/pages/Recommendations.tsx`
- `src/pages/Methodology.tsx`

### Map page

This is the research contribution surface.

- load organizations from `useOrgs()`
- load gaps from `getEquityGaps()`
- render org markers and gap markers
- support toggles for all / resources / gaps
- clicking an org opens a side panel
- clicking a gap opens a side panel with need, supply, gap, population, underserved count, and suggested host

### Recommendations page

- paginated or stepped exploration of equity gaps sorted by severity
- map-backed or map-adjacent view is acceptable
- must be non-empty when `equity-gaps.json` is present or seeded

### Methodology page

- long-form explanation of data pipeline, enrichment, ranking, equity analysis, accessibility index, confidence scoring, and limitations
- tone may be more academic because judges and researchers will read it

### Map implementation detail

If using MapLibre here too, use the exact style URL:

`https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json`

If using Leaflet for this page instead, use Carto light tiles consistently and document the chosen tile source in code comments.

### Acceptance checks for Prompt 8

- `/map` shows non-empty organizations or gaps
- `/recommendations` shows non-empty gap recommendations
- methodology reads like documentation, not placeholder filler

---

## Prompt 9: Polish, Accessibility, and Production Readiness

Do a final pass across the whole app.

### Required fixes

- remove console noise except useful warnings
- eliminate broken empty states
- ensure direct navigation and back buttons are safe
- remove invalid nested click targets
- add accessible labels everywhere needed
- ensure responsive behavior on mobile and desktop
- keep pages from crashing if optional fields are missing

### Production requirements

- wrap app in `ErrorBoundary`
- ensure Vite base is correct for GitHub Pages deployment
- create `.github/workflows/deploy.yml`
- build with `npm ci && npm run build`

### Final acceptance checks

A judge should be able to run the prompts and observe:

- home page with visible real resource count and non-empty trending data
- `/find` with a real best match
- `/org/:id` with detail content
- `/all` with a real list
- `/give/donate` and `/give/volunteer` with actionable cards
- `/map` with visible markers
- `/recommendations` with non-empty research content

Do not ship a prompt result that is visually polished but functionally empty.
