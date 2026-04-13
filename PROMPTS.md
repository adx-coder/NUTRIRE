# Nutrire - Kiro Prompt Markdown

## Context for Kiro

We are building Nutrire, a mobile-first food access app for the DC/Maryland/Virginia metro area. It transforms fragmented data from community food resource websites into a unified, easy-to-use tool for three audiences: households seeking food, donors wanting to help, and volunteers looking for opportunities.

The app is a static React SPA deployed on GitHub Pages. All data comes from a pre-built JSON file (`public/data/enriched-orgs.json`) containing 1,395 food assistance organizations scraped from 6 DMV sources, enriched with AI-generated content, and translated into English, Spanish, and Amharic.

---

## Prompt 1: Project Foundation

Create a React + Vite + TypeScript project called "Nutrire" with the following setup:

**Dependencies to install:**
- react, react-dom, react-router-dom (v6)
- tailwindcss, postcss, autoprefixer
- framer-motion (animations)
- zustand (state management)
- maplibre-gl, react-map-gl (maps)
- lucide-react (icons)
- clsx (class merging)
- fuse.js (fuzzy search)
- date-fns (date formatting)

**Tailwind config:**
Add custom colors as CSS variables in src/styles/tokens.css:
- Background: #EDE8E0 (warm paper)
- Ink: #1F2421 (primary text), #4A524E (soft), #7E867F (muted)
- Sage: #4F7F6A (primary/trust), #3A6551 (deep), #E8EFE9 (soft)
- Terracotta: #C96F4A (urgent)
- Mustard: #D9A441 (warm/likely confidence)
- Stone: #9A9A92 (stale)
Extend the tailwind config to use these as color classes (e.g., `text-sage-deep`, `bg-ink`).

**Fonts:** Import Inter (body) and Inter Tight (display) from Google Fonts in index.html.

**TypeScript types in src/types.ts:**

```typescript
export interface EnrichedOrganization {
  id: string;
  name: string;
  address: string;
  phone: string | null;
  website: string | null;
  hoursRaw: string;
  zip: string;
  neighborhood?: string;
  lat: number;
  lon: number;
  state: string;
  city: string;
  services: string[];
  foodTypes: string[];
  accessRequirements: string[];
  languages: string[];
  reliability: {
    tier: "fresh" | "recent" | "stale" | "unknown";
    score: number;
    lastConfirmedAt: string;
  };
  ai: {
    heroCopy: string;
    firstVisitGuide: string[];
    plainEligibility: string;
    culturalNotes: string | null;
    toneScore: number;
    qualityScore: number;
    generatedAt: string;
    model: string;
    parsedHours?: Record<string, any>;
    translations?: Record<string, {
      heroCopy?: string;
      plainEligibility?: string;
      firstVisitGuide?: string[];
      culturalNotes?: string;
    }>;
  };
  transit?: {
    transitSummary?: string;
    transitDirections?: {
      naturalDirections?: string;
      recommended?: string;
    };
    nearestBus?: { stopName: string; route: string; walkMinutes: number };
    nearestMetro?: { stationName: string; line: string; walkMinutes: number };
  };
  nearestTransitLines?: string[];
  nearestTransitType?: string;
  sourceId: string;
  sourceName: string;
  sourceIds: string[];
  crossSourceCount: number;
  acceptsFoodDonations: boolean;
  acceptsMoneyDonations: boolean;
  acceptsVolunteers: boolean;
  donateUrl?: string;
  volunteerUrl?: string;
  weatherAlert?: { event: string; affectsTravel: boolean } | null;
}

export type OpenState = "open" | "opens_today" | "opens_this_week" | "closed_long" | "unknown";

export interface OpenStatus {
  state: OpenState;
  label: string;
  labelKey?: string;
  labelVars?: Record<string, string | number>;
}

export interface RankedOrg {
  org: EnrichedOrganization;
  distanceMeters: number;
  walkMinutes: number;
  transitMinutes: number | null;
  driveMinutes: number;
  openStatus: OpenStatus;
  why: string;
  score: number;
}
```

**Data loader (src/data/load-data.ts):**
Create a hook `useOrgs()` that fetches `public/data/enriched-orgs.json` on mount, parses it as `EnrichedOrganization[]`, and returns the array. Include a mock fallback with 5 sample DMV organizations in case the JSON fails to load. Export a `mockUserLocation` constant at { lat: 38.9072, lng: -77.0369 } (Washington DC center).

**Zustand store (src/store/location.ts):**
Store: `location` (browser geolocation result or null), `language` ("en" | "es" | "am"), `intent` (service filter or null). Actions: `setLocation`, `setLanguage`, `setIntent`.

**React Router (src/App.tsx):**
Routes: `/` (Home), `/find` (BestMatch), `/org/:id` (OrgDetail), `/all` (AllOptions), `/give` (GiveHome), `/give/donate` (Donate), `/give/volunteer` (Volunteer), `/map` (Map), `/recommendations` (Recommendations), `/methodology` (Methodology). Catch-all redirects to `/`.

**index.html:** Set viewport-fit=cover, theme-color #EDE8E0, title "Nutrire - Free groceries and meals near you".

---

## Prompt 2: Core Utility Libraries

Create these utility files that power the app logic:

**src/lib/geo.ts:**
- `haversineMeters(a: {lat, lng}, b: {lat, lng})` - haversine distance in meters
- `walkMinutes(meters)` - meters / 80 (avg walking speed), rounded
- `driveMinutes(meters)` - meters / 450 (avg city driving), rounded, minimum 3

**src/lib/time.ts:**
- `relativeTimeShort(iso: string)` - returns "2h ago", "3d ago", "1w ago" etc.

**src/lib/open-status.ts:**
- `computeOpenStatus(org: EnrichedOrganization, now: Date): OpenStatus`
- Parse `org.ai.parsedHours` which has structure `{ raw: string, mon?: [{start, end, note}], tue?: [...], ... }`
- Compare current day/time against slots. Return states: "open" (within a slot), "opens_today" (slot later today), "opens_this_week" (next available day), "unknown" (no structured hours), "closed_long" (no upcoming slots found)
- Return both an English `label` string and a `labelKey` + `labelVars` for i18n

**src/lib/freshness.ts:**
- `reliabilityTone(r: ReliabilitySignal)` - returns `{ dotColor, label, labelKey, labelVars, shouldPromote, urgentCall }` based on tier (fresh/recent/stale/unknown)

**src/lib/rank-orgs.ts:**
- `rankOrgs(orgs, options)` - scores and sorts organizations
- Scoring weights: proximity 0.35, open status 0.25, access friction 0.15, confidence 0.15, tone 0.10
- Options: userLocation, now (Date), mode, languages[], preferServices[], maxResults
- Language match gets +0.08 boost
- Returns RankedOrg[] sorted by score descending

**src/lib/use-weather.ts:**
- `useWeather(lat, lon)` - React hook that fetches current weather from Open-Meteo API (free, no key): `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&temperature_unit=fahrenheit&timezone=auto`
- Returns `{ temp, label, isAdverse }` or null
- 10-minute in-memory cache per lat/lon
- Silent failure (weather is non-critical)

---

## Prompt 3: i18n System (English, Spanish, Amharic)

Create a complete internationalization system supporting three languages. This is critical because the DMV has large Spanish-speaking and Amharic-speaking communities, and the DC Language Access Act mandates language access.

**src/i18n/translations.ts:**
Create three dictionaries (en, es, am) with these key groups. Use `{{var}}` for interpolation. Export as `Record<UILang, Record<string, string>>`.

Navigation keys: nav.give, nav.equityMap, nav.research, nav.volunteer, nav.back, nav.change

Home keys: home.heroLine1 ("Free groceries" / "Alimentos gratis" / "ነፃ ግሮሰሪ"), home.heroLine2 ("and meals," / "y comidas," / "እና ምግብ,"), home.nearYou, home.tagline, home.chip.groceries, home.chip.hotMeals, home.chip.babySupplies, home.trending, home.openNow, home.openingSoon, home.input.placeholder, home.input.nearMe, home.input.useMyLocation

Match keys: match.getDirections, match.callFirst, match.whatToExpect, match.alternatives, match.allOptions ("All {{count}}"), match.empty.title, match.empty.body

Org keys: org.send, org.hours, org.eligibility, org.callForHours, org.byAppointment, org.whatsAvailable, org.gettingThere, org.ifThatDoesntWork, org.notFound, org.accurate, org.noted, org.sources

Filter keys: filter.openNow, filter.today, filter.walkable, filter.nearMetro, filter.spanish, filter.amharic, filter.noId, filter.delivers

Status keys: status.open, status.opensAt ("Opens at {{time}}"), status.opensDay ("Opens {{day}} {{time}}"), status.closed, status.callForHours, status.byAppointment

Freshness keys: fresh.lastChecked ("Last checked {{time}}"), fresh.stale, fresh.unknown

Donate keys: donate.eyebrow, donate.title, donate.subtitle, donate.acceptsFood, donate.acceptsMoney, donate.cta
Volunteer keys: vol.eyebrow, vol.title, vol.subtitle, vol.cta, vol.welcome

Map keys: map.recommendations, map.view, map.all, map.resources, map.gaps, map.viewDetails, map.firstVisit, map.suggestedHost, map.noData, map.population, map.nearby, map.equityGap

Recommendations keys: rec.eyebrow, rec.title, rec.areasAnalyzed ("{{count}} areas analyzed"), rec.need, rec.supply, rec.gap, rec.people, rec.underserved, rec.orgs

Weather key: weather.travelAffected ("Travel may be affected")
Methodology keys: method.eyebrow, method.title

All options keys: all.optionsNear ("{{count}} options near {{location}}"), all.searchPlaceholder, all.showMore, all.noResults, all.clearAll, all.list, all.map

Give keys: give.eyebrow, give.title, give.subtitle, give.donate.title, give.donate.desc, give.donate.cta, give.vol.title, give.vol.desc, give.vol.cta

**src/i18n/useT.ts:**
Hook that reads language from the Zustand store, returns a `t(key, vars?)` function. Falls back to English if key missing. Interpolates `{{var}}` patterns.

**src/i18n/useLocalizedAI.ts:**
Hook that takes an org's `ai` block and returns it with translated fields (heroCopy, plainEligibility, firstVisitGuide, culturalNotes) if `ai.translations[lang]` exists, else returns the English original.

**src/components/LangSwitcher.tsx:**
Three pill buttons (EN, ES, AM) with `role="radiogroup"` and `aria-checked`. Highlights the active language in sage.

---

## Prompt 4: Home Page with Glass Aesthetic

Build the Home page at src/pages/Home.tsx. This is the first thing users and judges see.

**Design language:** Warm glassmorphism. Background is #EDE8E0 with radial gradient orbs (sage, purple, mustard at low opacity) floating behind content. A subtle paper grain texture overlay at 3.5% opacity. All cards use `backdrop-blur-xl`, white borders at 40-50% opacity, and soft layered shadows.

**Layout (full viewport height, no scroll on desktop):**

Top nav bar:
- Left: Nutrire logo image (from /logos/nutrire-mark.png, 36px) + "Nutrire" wordmark in Inter Tight 22px bold
- Right (desktop): nav links (Give, Equity Map, Research, Volunteer) as small text buttons + LangSwitcher
- Right (mobile): hamburger menu that opens a glass overlay with nav links + LangSwitcher

Main content area (xl: 2-column grid with sidebar):
- Left sidebar (xl only, 170px): three static glass buttons with emoji icons (broccoli for Groceries, soup for Hot meals, baby bottle for Baby supplies). Each has a glass treatment: multi-stop gradient background, layered shadows (inset top + outer), hover sweep effect. Clicking navigates to /find with a service filter.
- Center column (full width on mobile): vertically centered content

Hero section:
- h1: `t("home.heroLine1")` + `t("home.heroLine2")` in display font (clamp 38-74px)
- "near you." line in sage-deep color with a subtle underline swoosh animation
- Below headline: rotating tagline that cycles through the "1,400+ verified resources" text in English, Spanish, Amharic, French, Vietnamese every 3.2 seconds with vertical slide animation
- Location input component (max-width xl, centered)
- Quick action chips on mobile (hidden on xl since sidebar shows them)

Trending strip:
- Glass card (rounded-[30px]) showing up to 4 open/opening-soon orgs
- Each org in a small glass card with pulsing status dot, name, hours label
- Header: "Trending near you" translated via t()

Footer line:
- Small Nutrire leaf logo + "A NourishNet Data Challenge project - University of Maryland - NSF Funded" at 35% opacity

**Animations:**
- Use a `useFirstMount("home")` hook that tracks if this is the first visit. On first visit: staggered fade-up entrance animations (0.1s-1.5s delays). On return visits: skip all animations (instant render).

---

## Prompt 5: Best Match + Org Detail Pages

**BestMatch (src/pages/BestMatch.tsx) - "One answer, not a list":**

This is the core innovation. Instead of showing a list, the app picks the single best option for the user.

Use `rankOrgs()` to get sorted results. Show the #1 as a hero card:
- Glass card with status dot + label, org name (large), neighborhood, heroCopy paragraph
- Live weather from `useWeather(org.lat, org.lon)` - shows temp + conditions, amber warning if adverse
- Confidence dot + "Confirmed X ago" + source name
- Below: map strip with MapLibre GL (Carto Voyager tiles) showing user pin + org pin + dashed line
- Action row: "Get directions" button (sage, opens Google Maps), share icon button, phone icon button
- "If that doesn't work" section with 5 BackupCard components

BackupCard component (src/components/BackupCard.tsx):
- Compact glass card: org name, status dot + label, heroCopy (2-line clamp), eligibility, transit line badge, arrow icon
- Uses useLocalizedAI() for translated content

**OrgDetail (src/pages/OrgDetail.tsx) - full deep-dive:**

Bento grid: map card left (spans full height on desktop), info cards stacked right.

Identity card: status + distance, org name (large), neighborhood, heroCopy, live weather, confidence line
Details card: "What to expect" bullets with sage checkmarks, eligibility glass card with cultural notes, "What's available" food type chips, Hours section (only if structured data exists), "Getting there" with transit summary + natural directions
Alternatives card: "If that doesn't work" with 4 backup rows, feedback ("Accurate?" with yes/no buttons)
Share sheet: bottom sheet with WhatsApp, Text, Copy buttons

Use useLocalizedAI() and useStatusLabel() for all translated content.

---

## Prompt 6: All Options, Donate, Volunteer, Give Pages

**AllOptions (src/pages/AllOptions.tsx):**
- Search bar with fuzzy search (Fuse.js) across org names and heroCopy
- Filter chips: Open now, Today, Walkable, Near metro, Espanol, Amharic, No ID, Delivers
- Split layout: list on left, optional MapLibre map on right (desktop) or toggled (mobile)
- Results as BackupCard list, paginated with "Show more" button
- All filter labels use t() for translation

**Donate (src/pages/Donate.tsx):**
- Header: "Where your help matters most this week" (via t())
- Filter chips: Accepts food, Accepts money, Within 5 mi, Has donate link
- Card list: org name, food/money badge chips, distance, donate button (links to org.donateUrl), view details link

**Volunteer (src/pages/Volunteer.tsx):**
- Header: "Give a few hours this week" (via t())
- Filter chips: Within 10 mi, Has sign-up link, Spanish needed
- Card list: org name, "Volunteers welcome" badge, language chips, sign-up button (links to org.volunteerUrl), view details link

**GiveHome (src/pages/GiveHome.tsx):**
- Two door cards: "Give food or money" and "Give time"
- Each links to /give/donate and /give/volunteer respectively

All pages use the shared TopNav component with a back button and the glass backdrop aesthetic.

---

## Prompt 7: Equity Map + Recommendations + Methodology

**Map (src/pages/Map.tsx):**
This is the research contribution page. Shows a full-viewport map with equity gap analysis.

- Load org data from useOrgs() and gap data from public/data/equity-gaps.json
- Display all orgs as small sage circle markers
- Display equity gaps as terracotta circle markers (radius proportional to gap severity)
- Radio toggle: All / Resources / Gaps
- Stats bar: "N resources - N gaps - N underserved"
- Click org: side panel with name, heroCopy, phone, eligibility, first-visit guide, "View details" link
- Click gap: side panel with ZIP, description, need/supply/gap bar charts, population stats, suggested host
- All labels translated via t() using map.* and rec.* keys

**Recommendations (src/pages/Recommendations.tsx):**
- Load equity gaps from JSON, sorted by gap score descending
- Paginated card view with prev/next navigation
- Each card: ZIP + area name, description, need/supply/gap horizontal bars, population stat, underserved count, nearby org count, suggested host
- Header: "Research contribution" eyebrow + "Equity Gap Analysis" title (via t())

**Methodology (src/pages/Methodology.tsx):**
- Long-form research documentation page
- Sections: Overview, Data Pipeline, AI Enrichment, Ranking Engine, Equity Gap Engine, TLDAI Accessibility Index, Transit Routing, Confidence Scoring, Limitations, Data Sources
- Academic tone appropriate for judges and researchers
- Uses TopNav with back button

---

## Prompt 8: Error Handling + Production Polish

**ErrorBoundary (src/components/ErrorBoundary.tsx):**
- Class component wrapping the entire app in src/main.tsx
- Catches any render error and shows a friendly fallback: Nutrire leaf emoji, "Something went wrong", "Go home" button
- Styled to match the warm #EDE8E0 background

**Accessibility pass:**
- All icon-only buttons get aria-labels (Share, Call, Clear search, Yes, No)
- LangSwitcher uses role="radio" + aria-checked instead of aria-pressed
- Search input has explicit aria-label

**Production cleanup:**
- Remove any console.log statements (keep console.warn for error fallbacks)
- Remove any dev-only routes (like /sandbox)
- Ensure all pages use the useFirstMount() hook to skip entrance animations on return navigation

**Favicon:** Set /favicon.png as the site icon in index.html using `<link rel="icon" type="image/png" href="/favicon.png">`.

**GitHub Pages deployment:**
- Set `base: "/NUTRIRE/"` in vite.config.ts
- Create .github/workflows/deploy.yml that builds with `npm ci && npm run build` and deploys the dist/ folder using actions/deploy-pages@v4
