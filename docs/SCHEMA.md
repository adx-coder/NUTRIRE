# Nutrire — Data Contract (SCHEMA.md)

This document is the contract between the UI team and the backend team.

The UI consumes **static JSON files** at build time (no runtime API calls, GitHub Pages is static). The backend team produces those JSON files from the agentic pipeline. This document defines the exact shapes the UI expects.

**Ground rules:**
- All files UTF-8, camelCase, ISO 8601 timestamps, ISO 639-1 language codes, FIPS geo codes.
- Every file carries a `schemaVersion` at the root. Breaking changes bump the major.
- The UI must render gracefully when optional fields are missing. Optional fields are marked with `?`.
- **The atomic unit is the Event, not the Pantry.** Events are time-bound instances. An Organization can host many Events over time.
- Confidence and freshness are first-class fields on every Event — the UI surfaces them prominently.

---

## File layout

The backend team produces these files into `/public/data/` in the UI repo (or ships them via CI to the same path):

```
/public/data/
  graph.json       # events, orgs, locations, edges, embeddings
  tracts.geojson   # census tract polygons with enrichment
  shifts.json      # volunteer shifts
  insights.json    # equity gap stats + recommendations + coverage
  meta.json        # version, generated timestamp, sources, licenses
```

The UI imports these as static JSON at build time.

---

## 1. Event

The atomic unit of food access. A specific instance at a specific time and place.

```ts
interface Event {
  id: string;                      // stable, format: "evt_<slug>"
  schemaVersion: "1.0";

  // Relationships
  orgId: string;                   // → Organization.id
  locationId: string;              // → Location.id

  // Identity
  title: string;                   // "Saturday Fresh Market"
  description: string;             // 1-3 sentences, plain language
  type: EventType;

  // Time
  schedule: Schedule;
  nextOccurrence: TimeWindow | null; // next upcoming instance; null if none scheduled
  indoorOutdoor: "indoor" | "outdoor" | "mixed";

  // Content
  foodTypes: FoodType[];           // what will actually be distributed
  estimatedPortions: number | null; // typical served per session

  // Access
  eligibility: Eligibility;
  languages: string[];             // ISO 639-1 codes of languages spoken at check-in
  accessibility: Accessibility;

  // Trust
  confidence: ConfidenceSignal;
  sources: SourceCitation[];
  lastVerified: string;            // ISO 8601

  // Weather (optional, only set when event is outdoor/mixed)
  weather?: WeatherFlag;

  // Meta
  createdAt: string;
  updatedAt: string;
}

type EventType =
  | "food_pantry"          // boxes/bags of groceries
  | "hot_meal"             // prepared meal, eat on-site or take-out
  | "mobile_distribution"  // truck that comes to a location
  | "pop_up"               // one-time or irregular
  | "school_meal"          // free summer/weekend meals for kids
  | "grocery_rescue"       // surplus from stores, rescued
  | "community_fridge";    // 24/7 open fridge
```

### Schedule

```ts
type Schedule =
  | { kind: "one_time"; at: TimeWindow }
  | {
      kind: "recurring";
      pattern: "weekly" | "biweekly" | "monthly" | "first_of_month" | "last_of_month";
      dayOfWeek?: 0 | 1 | 2 | 3 | 4 | 5 | 6;   // 0 = Sunday
      dayOfMonth?: number;                       // 1-31
      time: { start: string; end: string };      // HH:MM 24h
      timezone: string;                           // "America/New_York"
      exceptions?: string[];                      // ISO dates to skip
    };

interface TimeWindow {
  start: string;  // ISO 8601
  end: string;    // ISO 8601
}
```

### Eligibility

This is the most important object for Maria. The UI surfaces it as plain-English content, not a filter panel.

```ts
interface Eligibility {
  walkIn: boolean;
  appointmentRequired: boolean;
  idRequired: boolean;
  proofOfAddressRequired: boolean;
  proofOfIncomeRequired: boolean;
  referralRequired: boolean;

  residencyRestriction: string | null;    // e.g., "DC residents" | null
  populationRestriction: string | null;   // e.g., "seniors 60+" | "families with children" | null
  ageRestriction: { min?: number; max?: number } | null;

  firstTimeExtraDocs: boolean;            // true = first visit requires more paperwork than subsequent
  notes: string;                          // free text, <200 chars, plain language

  // Derived dignity fields (backend computes these from booleans above)
  frictionScore: number;                  // 0 = none, 1 = heavy. Used by ranking engine.
  plainSummary: string;                   // human-readable one-liner: "Anyone welcome. Bring nothing."
}
```

### Accessibility

```ts
interface Accessibility {
  wheelchairAccessible: boolean;
  parkingAvailable: boolean;
  childrenWelcome: boolean;
  seatingAvailable: boolean;
  restroomsAvailable: boolean;
  petsAllowed: boolean;
  privateEntranceAvailable: boolean;      // dignity signal — matters
  stigmaFreeSignals: string[];            // e.g., ["no questions asked", "choice model"]
}
```

### FoodType

```ts
type FoodType =
  | "produce"
  | "dairy"
  | "protein"                // meat, fish, eggs, beans
  | "grains"
  | "canned_goods"
  | "bread"
  | "frozen"
  | "prepared_meal"
  | "baby_formula"
  | "diapers"
  | "hygiene_products"
  | "pet_food"
  | "cultural_specific";     // flagged when org notes halal, kosher, latino, asian etc
```

### ConfidenceSignal

```ts
interface ConfidenceSignal {
  tier: "verified" | "likely" | "stale" | "unknown";
  lastConfirmedAt: string;            // ISO 8601
  lastConfirmedBy: "org" | "crowd" | "automated" | "cross_source";

  // Components used to compute tier
  freshnessDays: number;              // days since lastConfirmedAt
  crossSourceMatches: number;         // number of independent sources agreeing
  recurrenceMatched: boolean;         // does the recurring schedule match reality
  sourceReliability: number;          // 0..1 — food bank 1.0, unknown blog 0.3

  // UI-facing
  reliabilityScore: number;           // 0..1 weighted composite
  humanExplanation: string;           // "Confirmed by the pantry 2 hours ago"
}
```

**Tier rules (backend computes):**
- `verified` — confirmed in the last 7 days by org or cross-source match
- `likely` — within 30 days, or recurring pattern matched in last 30 days
- `stale` — 30–90 days, or cross-source conflicts
- `unknown` — >90 days or single unreliable source

The UI will:
- Show `verified` with a green badge.
- Show `likely` with a mustard badge.
- Show `stale` with a gray badge and dignity copy ("We haven't confirmed this recently. Call first.").
- Never put `stale` or `unknown` as the Best Match.

### SourceCitation

```ts
interface SourceCitation {
  sourceUrl: string;
  sourceName: string;             // e.g., "Capital Area Food Bank"
  sourceType: "food_bank_list" | "org_website" | "social_media" | "news" | "government" | "manual";
  fetchedAt: string;              // ISO 8601
  extractedBy: "llm" | "manual" | "scraper";
  confidence: number;             // 0..1 — how much this source trusts itself
}
```

### WeatherFlag

```ts
interface WeatherFlag {
  status: "clear" | "watch" | "warning";
  forecast: string;               // "Thunderstorms likely, 2-5pm"
  alertReason?: string;           // "Outdoor distribution may be cancelled"
  checkedAt: string;              // ISO 8601
}
```

---

## 2. Organization

```ts
interface Organization {
  id: string;                     // "org_<slug>"
  schemaVersion: "1.0";
  name: string;
  type: OrgType;
  description: string;            // 1-3 sentences

  contact: {
    website?: string;
    phone?: string;
    email?: string;
    address?: Address;
    socialLinks?: { platform: string; url: string }[];
  };

  // For donor and volunteer views
  donationInfo?: DonationInfo;
  volunteerInfo?: VolunteerInfo;

  // Aggregated trust
  reliability: number;            // 0..1 composite from its Events' confidence signals
  missionTags: string[];          // "hunger_relief", "immigrant_services", "youth", etc.

  createdAt: string;
  updatedAt: string;
}

type OrgType =
  | "food_bank"      // large regional (e.g., Capital Area Food Bank)
  | "pantry"         // direct distribution
  | "church"
  | "nonprofit"
  | "government"
  | "mutual_aid"
  | "school"
  | "community_center"
  | "other";

interface DonationInfo {
  acceptsFood: boolean;
  acceptsMoney: boolean;
  acceptsVolunteerTime: boolean;
  dropOffAddress?: Address;
  dropOffHours?: string;                   // plain text
  currentNeeds?: string[];                 // "rice", "diapers", "canned protein"
  donateUrl?: string;
  taxDeductible: boolean;
}

interface VolunteerInfo {
  openShiftIds: string[];                  // → Shift.id
  rolesNeeded: string[];                   // "driver", "translator", "sorter"
  signUpUrl?: string;
  minimumAge?: number;
  backgroundCheckRequired: boolean;
}
```

---

## 3. Location

```ts
interface Location {
  id: string;                     // "loc_<slug>"
  schemaVersion: "1.0";
  address: Address;
  coords: { lat: number; lng: number };
  neighborhood?: string;          // "Columbia Heights"
  tractGeoid: string;             // → Tract.geoid
  countyFips: string;

  transitProximity: TransitProximity[];   // list of nearby stops
  walkabilityScore?: number;              // 0..1 based on OSM sidewalk data
}

interface Address {
  line1: string;
  line2?: string;
  city: string;
  state: "DC" | "MD" | "VA";
  zip: string;
}

interface TransitProximity {
  stopId: string;
  stopName: string;
  agency: "WMATA" | "MTA" | "DC_Circulator" | "MARC" | "VRE" | "other";
  routeIds: string[];             // bus/rail lines
  walkMinutes: number;            // from location to stop
  headwayMinutes?: number;        // typical wait between arrivals
}
```

---

## 4. Tract (census tract with enrichment)

This is the spatial unit for the Equity Gap map.

```ts
interface Tract {
  geoid: string;                  // 11-digit FIPS code
  schemaVersion: "1.0";
  name: string;                   // "Census Tract 24.01, Montgomery County, MD"
  countyFips: string;

  // Geometry lives in tracts.geojson (below)

  demographics: {
    population: number;
    povertyRate: number;          // 0..1
    medianHouseholdIncome: number;
    noVehicleHouseholdsPct: number;
    snapEnrollmentPct: number;
    snapEligibleEstimatePct: number;   // derived; SNAP gap = eligible - enrolled
    rentBurdenedPct: number;           // % spending >30% income on rent
    childPovertyRate: number;
  };

  languageProfile: LanguageSpeakers[];

  foodAccess: {
    isFoodDesert: boolean;
    category: "LILA" | "LI" | "LA" | null;     // USDA LILA categories
    distanceToSupermarketMiles: number;
  };

  transitScore: number;           // 0..1 — how well-served by transit

  // Computed scores (backend produces these)
  needScore: number;              // 0..1
  supplyScore: number;            // 0..1
  equityGap: number;              // -1..+1 (Need - Supply, normalized)
  equityGapRank: number;          // rank within DMV; 1 = worst served

  // Cached nearby events (denormalized for UI perf)
  nearbyEventIds: string[];       // events within 20 min transit
}

interface LanguageSpeakers {
  code: string;                   // ISO 639-1; "es", "am", "vi", "fr", "zh", "ar"
  name: string;                   // "Spanish", "Amharic"
  speakers: number;
  percentOfTract: number;         // 0..1
}
```

### tracts.geojson

Standard GeoJSON `FeatureCollection`. Each feature is a tract polygon with `properties.geoid` matching the Tract.geoid. The UI joins on geoid at load time.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "geoid": "11001000100", "name": "DC Tract 1.00" },
      "geometry": { "type": "Polygon", "coordinates": [ ... ] }
    }
  ]
}
```

---

## 5. Shift (volunteer opportunity)

Lives in `shifts.json`.

```ts
interface Shift {
  id: string;                     // "shift_<slug>"
  schemaVersion: "1.0";
  orgId: string;
  eventId?: string;               // optional link to a specific Event
  role: string;                   // "Sort donations" | "Drive delivery"
  roleDescription: string;
  startsAt: string;               // ISO 8601
  endsAt: string;
  spotsTotal: number;
  spotsFilled: number;
  skillsRequired: string[];
  languagesNeeded: string[];
  minimumAge: number;
  physicalRequirements?: string;  // "lift up to 30 lb"
  signUpUrl?: string;
  contactEmail?: string;
  location: Location;             // may duplicate Event.locationId
}
```

---

## 6. GapRecommendation

Generated by the recommendation engine. Lives in `insights.json`.

```ts
interface GapRecommendation {
  id: string;                     // "rec_<slug>"
  schemaVersion: "1.0";

  area: {
    centroidLat: number;
    centroidLng: number;
    neighborhoodLabel: string;    // "Langley Park, MD 20783"
    tractGeoids: string[];        // tracts in the cluster
  };

  why: string;                    // plain-English paragraph for the Research view

  stats: {
    population: number;
    needScore: number;
    underservedPopulation: number;
    nearestMatchedEventMinutes: number;   // transit minutes to nearest language-matched event
    languageGaps: string[];               // ["es", "am"]
    foodDesert: boolean;
  };

  suggestedHost: {
    orgId: string;
    orgName: string;
    rationale: string;
    distanceFromCentroidMiles: number;
  } | null;

  suggestedCadence: string;       // "Weekly, Saturday morning"
  expectedReachHouseholds: number;
  priority: number;               // 1..N, 1 = highest
}
```

---

## 7. Insights (aggregated stats)

`insights.json` top-level shape:

```ts
interface Insights {
  schemaVersion: "1.0";
  generatedAt: string;

  coverage: {
    totalEvents: number;
    totalOrgs: number;
    totalTracts: number;
    verifiedPct: number;
    likelyPct: number;
    stalePct: number;
    unknownPct: number;
  };

  equityGap: {
    meanGap: number;
    p50Gap: number;
    p95Gap: number;
    worstTractGeoids: string[];         // top 20 underserved tracts
  };

  languageCoverage: {
    [languageCode: string]: {
      name: string;
      speakersInDMV: number;
      reachableEvents: number;          // events supporting this language within 20 min transit of any speaker cluster
      coveragePct: number;              // 0..1 — share of speakers with at least one reachable event
      biggestGapTractGeoid: string | null;
    };
  };

  recommendations: GapRecommendation[];
}
```

---

## 8. Graph (master file)

`graph.json` is the primary file the UI loads. It carries events, orgs, locations, optional edges, and optional embeddings.

```ts
interface GraphFile {
  schemaVersion: "1.0";
  generatedAt: string;

  events: Event[];
  organizations: Organization[];
  locations: Location[];

  // Optional: explicit relational edges (the UI can also derive these from foreign keys)
  edges?: Edge[];

  // Optional: precomputed embeddings for semantic search
  // Keyed by event.id → vector (float32, fixed dimensionality from all-MiniLM-L6-v2 = 384)
  embeddings?: {
    model: "all-MiniLM-L6-v2";
    dimensions: 384;
    vectors: { [eventId: string]: number[] };
  };
}

interface Edge {
  from: { type: NodeType; id: string };
  to: { type: NodeType; id: string };
  type: EdgeType;
  weight?: number;
  metadata?: Record<string, unknown>;
}

type NodeType = "event" | "organization" | "location" | "tract";

type EdgeType =
  | "hosts"          // org hosts event
  | "located_at"     // event located_at location
  | "serves"         // event serves tract
  | "contained_in"   // location contained_in tract
  | "near"           // spatial adjacency
  | "speaks"         // event speaks language
  | "supplies"       // org supplies org
  | "requires"       // event requires eligibility-tag
  | "similar_to";    // semantic similarity between events
```

---

## 9. Meta

`meta.json` — versioning and provenance.

```ts
interface Meta {
  schemaVersion: "1.0";
  generatedAt: string;
  pipelineVersion: string;        // e.g., "0.3.1"
  sources: SourceRef[];
  licenses: LicenseRef[];
  coverageRegion: "DMV";
  coverageStates: ("DC" | "MD" | "VA")[];
  knownLimitations: string[];     // honest list for the methodology page
}

interface SourceRef {
  name: string;
  url: string;
  lastFetched: string;
  recordCount: number;
  usage: string;                  // "event extraction" | "tract enrichment" | "transit routing"
}

interface LicenseRef {
  dataset: string;
  license: string;                // "CC-BY-4.0", "public domain", etc.
  attribution: string;
}
```

---

## 10. UI guarantees

The UI commits to:

1. **Never crash on missing optional fields.** Every `?` field is handled with a graceful fallback.
2. **Never display stale events as Best Match.** Ranking engine filters `stale` and `unknown` out of the top slot.
3. **Render any subset of languages.** EN is the baseline; all other language strings are progressively loaded. Missing translations fall back to EN with a dignity disclaimer.
4. **Handle empty result sets with actionable fallback.** "No events in the next 24 hours near you — here are 3 nearby orgs to call directly." Never a blank screen.
5. **Respect `confidence.tier` in dignity copy.** Stale events get "We haven't confirmed this recently" prefixes, not hidden rejections.
6. **Display `sources` on every Event Detail.** Users can see where the data came from and when.
7. **Localize freshness strings** — "2 hours ago" in Spanish, not "2 horas ago."

---

## 11. Naming and formatting conventions

- **IDs:** prefixed namespaces — `evt_`, `org_`, `loc_`, `rec_`, `shift_`. Lowercase, hyphens allowed.
- **Timestamps:** ISO 8601 with timezone — `2026-04-12T15:30:00-04:00`. Never naive strings.
- **Durations:** minutes as integers. Not strings like "2 hours."
- **Distances:** meters internally, converted to miles in UI. Expose meters in JSON.
- **Percentages:** 0..1 floats. Not 0..100 integers.
- **Languages:** ISO 639-1 two-letter. `es` not `Spanish`.
- **Geography:** FIPS codes. County `24031`, tract `24031702900`.
- **Missing values:** `null`, never empty string. Omit optional fields entirely when unknown.

---

## 12. Versioning policy

- Every file has a `schemaVersion` at the root.
- **Minor bumps** (`1.0` → `1.1`) add fields. UI ignores unknown fields gracefully.
- **Major bumps** (`1.0` → `2.0`) remove or rename fields. UI must be updated in lockstep.
- Backend ships a `CHANGELOG.md` alongside the pipeline repo.

---

## 13. Example: one complete Event

```json
{
  "id": "evt_marthas-table-saturday-market",
  "schemaVersion": "1.0",
  "orgId": "org_marthas-table",
  "locationId": "loc_marthas-table-14th-st",
  "title": "Saturday Fresh Market",
  "description": "Free groceries including produce, dairy, and bread. Walk-up, no questions asked.",
  "type": "food_pantry",
  "schedule": {
    "kind": "recurring",
    "pattern": "weekly",
    "dayOfWeek": 6,
    "time": { "start": "10:00", "end": "13:00" },
    "timezone": "America/New_York"
  },
  "nextOccurrence": {
    "start": "2026-04-11T10:00:00-04:00",
    "end": "2026-04-11T13:00:00-04:00"
  },
  "indoorOutdoor": "indoor",
  "foodTypes": ["produce", "dairy", "bread", "canned_goods"],
  "estimatedPortions": 120,
  "eligibility": {
    "walkIn": true,
    "appointmentRequired": false,
    "idRequired": false,
    "proofOfAddressRequired": false,
    "proofOfIncomeRequired": false,
    "referralRequired": false,
    "residencyRestriction": null,
    "populationRestriction": null,
    "ageRestriction": null,
    "firstTimeExtraDocs": false,
    "notes": "Everyone welcome. No questions asked.",
    "frictionScore": 0.0,
    "plainSummary": "Anyone welcome. Bring nothing."
  },
  "languages": ["en", "es"],
  "accessibility": {
    "wheelchairAccessible": true,
    "parkingAvailable": false,
    "childrenWelcome": true,
    "seatingAvailable": true,
    "restroomsAvailable": true,
    "petsAllowed": false,
    "privateEntranceAvailable": false,
    "stigmaFreeSignals": ["no questions asked", "walk-up"]
  },
  "confidence": {
    "tier": "verified",
    "lastConfirmedAt": "2026-04-09T14:00:00-04:00",
    "lastConfirmedBy": "org",
    "freshnessDays": 1,
    "crossSourceMatches": 2,
    "recurrenceMatched": true,
    "sourceReliability": 0.95,
    "reliabilityScore": 0.94,
    "humanExplanation": "Confirmed by Martha's Table 1 day ago"
  },
  "sources": [
    {
      "sourceUrl": "https://marthastable.org/find-food/",
      "sourceName": "Martha's Table",
      "sourceType": "org_website",
      "fetchedAt": "2026-04-09T14:00:00-04:00",
      "extractedBy": "llm",
      "confidence": 0.95
    }
  ],
  "lastVerified": "2026-04-09T14:00:00-04:00",
  "createdAt": "2026-03-15T09:00:00-04:00",
  "updatedAt": "2026-04-09T14:00:00-04:00"
}
```

---

## 14. What the UI needs first (for scaffolding against mocks)

The UI will hand-write a mock file matching this schema to unblock frontend work. The backend team should aim to produce a compatible `graph.json` with at least **15 events across 6 orgs, covering DC + Montgomery County + Fairfax**, as the first end-to-end milestone.

**Minimum viable first drop:**
- `graph.json` with 15 real events (any confidence tier, any mix of eligibility)
- `meta.json` with source list
- Everything else (`tracts.geojson`, `insights.json`, `shifts.json`) can come later and the UI will render fallback states.

---

## 15. Open questions for the backend team

Raise these in the first sync:

1. Who owns geocoding (Nominatim vs. something else)? How are we handling rate limits?
2. GTFS feed versions — WMATA updates weekly, we need a pinned snapshot per build.
3. ACS year — 2022 5-year estimates (latest available)?
4. Confidence tier thresholds — are the 7/30/90 day windows the right cut points?
5. Embedding generation — build-time Python script, or during the Node pipeline via transformers.js?
6. How often does the pipeline run? CI nightly? On-demand?
7. Data deletion — if a pantry closes, does the Event get removed or marked `unknown`?

---

**End of contract. Questions to @ui-team.**
