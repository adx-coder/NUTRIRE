// Nutrire — types mirroring docs/SCHEMA.md
// Keep these in lockstep with the backend contract.

// -------- shared primitives --------

export type ISODate = string;
export type LangCode = "en" | "es" | "am" | "vi" | "fr" | "zh" | "ar" | "ko" | "ru" | "ht" | "ur" | "bn";
export type StateCode = "DC" | "MD" | "VA";

export interface Address {
  line1: string;
  line2?: string;
  city: string;
  state: StateCode;
  zip: string;
}

export interface Coords {
  lat: number;
  lng: number;
}

export interface TimeWindow {
  start: ISODate;
  end: ISODate;
}

// -------- event --------

export type EventType =
  | "food_pantry"
  | "hot_meal"
  | "mobile_distribution"
  | "pop_up"
  | "school_meal"
  | "grocery_rescue"
  | "community_fridge";

export type Schedule =
  | { kind: "one_time"; at: TimeWindow }
  | {
      kind: "recurring";
      pattern: "weekly" | "biweekly" | "monthly" | "first_of_month" | "last_of_month";
      dayOfWeek?: 0 | 1 | 2 | 3 | 4 | 5 | 6;
      dayOfMonth?: number;
      time: { start: string; end: string };
      timezone: string;
      exceptions?: string[];
    };

export type FoodType =
  | "produce"
  | "dairy"
  | "protein"
  | "grains"
  | "canned_goods"
  | "bread"
  | "frozen"
  | "prepared_meal"
  | "baby_formula"
  | "diapers"
  | "hygiene_products"
  | "pet_food"
  | "cultural_specific";

export interface Eligibility {
  walkIn: boolean;
  appointmentRequired: boolean;
  idRequired: boolean;
  proofOfAddressRequired: boolean;
  proofOfIncomeRequired: boolean;
  referralRequired: boolean;
  residencyRestriction: string | null;
  populationRestriction: string | null;
  ageRestriction: { min?: number; max?: number } | null;
  firstTimeExtraDocs: boolean;
  notes: string;
  /** 0 = none, 1 = heavy. Used by ranking engine. */
  frictionScore: number;
  /** "Anyone welcome. Bring nothing." */
  plainSummary: string;
}

export interface Accessibility {
  wheelchairAccessible: boolean;
  parkingAvailable: boolean;
  childrenWelcome: boolean;
  seatingAvailable: boolean;
  restroomsAvailable: boolean;
  petsAllowed: boolean;
  privateEntranceAvailable: boolean;
  stigmaFreeSignals: string[];
}

export interface ConfidenceSignal {
  tier: "verified" | "likely" | "stale" | "unknown";
  lastConfirmedAt: ISODate;
  lastConfirmedBy: "org" | "crowd" | "automated" | "cross_source";
  freshnessDays: number;
  crossSourceMatches: number;
  recurrenceMatched: boolean;
  sourceReliability: number;
  reliabilityScore: number;
  humanExplanation: string;
}

export interface SourceCitation {
  sourceUrl: string;
  sourceName: string;
  sourceType: "food_bank_list" | "org_website" | "social_media" | "news" | "government" | "manual";
  fetchedAt: ISODate;
  extractedBy: "llm" | "manual" | "scraper";
  confidence: number;
}

export interface WeatherFlag {
  status: "clear" | "watch" | "warning";
  forecast: string;
  alertReason?: string;
  checkedAt: ISODate;
}

export type CuisineTag =
  | "halal"
  | "kosher"
  | "vegetarian"
  | "vegan"
  | "gluten_free"
  | "latino"
  | "ethiopian"
  | "east_african"
  | "west_african"
  | "asian"
  | "south_asian"
  | "caribbean"
  | "middle_eastern"
  | "diabetic_friendly";

export interface FoodItem {
  name: string;                 // "Fresh eggs", "Chicken", "Bananas"
  quantity?: number;            // numeric count
  unit?: string;                // "dozen", "lb", "bags", "boxes"
  note?: string;                // "organic", "frozen", "limit 1 per family"
}

export interface FoodEvent {
  id: string;
  schemaVersion: "1.0";
  orgId: string;
  locationId: string;
  title: string;
  description: string;
  type: EventType;
  schedule: Schedule;
  nextOccurrence: TimeWindow | null;
  indoorOutdoor: "indoor" | "outdoor" | "mixed";
  foodTypes: FoodType[];
  /** Free-form cultural / dietary tags. Shown as chips on the card. */
  cuisineTags?: CuisineTag[];
  /** Specific inventory on offer at this distribution. Optional — best-effort. */
  items?: FoodItem[];
  estimatedPortions: number | null;
  /** Optional hero image. When absent, card uses the gradient+icon fallback. */
  heroImageUrl?: string;
  eligibility: Eligibility;
  languages: LangCode[];
  accessibility: Accessibility;
  confidence: ConfidenceSignal;
  sources: SourceCitation[];
  lastVerified: ISODate;
  weather?: WeatherFlag;
  createdAt: ISODate;
  updatedAt: ISODate;
}

// -------- organization --------

export type OrgType =
  | "food_bank"
  | "pantry"
  | "church"
  | "nonprofit"
  | "government"
  | "mutual_aid"
  | "school"
  | "community_center"
  | "other";

export interface DonationInfo {
  acceptsFood: boolean;
  acceptsMoney: boolean;
  acceptsVolunteerTime: boolean;
  dropOffAddress?: Address;
  dropOffHours?: string;
  currentNeeds?: string[];
  donateUrl?: string;
  taxDeductible: boolean;
}

export interface VolunteerInfo {
  openShiftIds: string[];
  rolesNeeded: string[];
  signUpUrl?: string;
  minimumAge?: number;
  backgroundCheckRequired: boolean;
}

export interface Organization {
  id: string;
  schemaVersion: "1.0";
  name: string;
  type: OrgType;
  description: string;
  contact: {
    website?: string;
    phone?: string;
    email?: string;
    address?: Address;
    socialLinks?: { platform: string; url: string }[];
  };
  donationInfo?: DonationInfo;
  volunteerInfo?: VolunteerInfo;
  reliability: number;
  missionTags: string[];
  createdAt: ISODate;
  updatedAt: ISODate;
}

// -------- location --------

export interface TransitProximity {
  stopId: string;
  stopName: string;
  agency: "WMATA" | "MTA" | "DC_Circulator" | "MARC" | "VRE" | "other";
  routeIds: string[];
  walkMinutes: number;
  headwayMinutes?: number;
}

export interface Location {
  id: string;
  schemaVersion: "1.0";
  address: Address;
  coords: Coords;
  neighborhood?: string;
  tractGeoid: string;
  countyFips: string;
  transitProximity: TransitProximity[];
  walkabilityScore?: number;
}

// -------- tract --------

export interface LanguageSpeakers {
  code: LangCode;
  name: string;
  speakers: number;
  percentOfTract: number;
}

export interface Tract {
  geoid: string;
  schemaVersion: "1.0";
  name: string;
  countyFips: string;
  demographics: {
    population: number;
    povertyRate: number;
    medianHouseholdIncome: number;
    noVehicleHouseholdsPct: number;
    snapEnrollmentPct: number;
    snapEligibleEstimatePct: number;
    rentBurdenedPct: number;
    childPovertyRate: number;
  };
  languageProfile: LanguageSpeakers[];
  foodAccess: {
    isFoodDesert: boolean;
    category: "LILA" | "LI" | "LA" | null;
    distanceToSupermarketMiles: number;
  };
  transitScore: number;
  needScore: number;
  supplyScore: number;
  equityGap: number;
  equityGapRank: number;
  nearbyEventIds: string[];
}

// -------- shift --------

export interface Shift {
  id: string;
  schemaVersion: "1.0";
  orgId: string;
  eventId?: string;
  role: string;
  roleDescription: string;
  startsAt: ISODate;
  endsAt: ISODate;
  spotsTotal: number;
  spotsFilled: number;
  skillsRequired: string[];
  languagesNeeded: LangCode[];
  minimumAge: number;
  physicalRequirements?: string;
  signUpUrl?: string;
  contactEmail?: string;
  location: Location;
}

// -------- gap recommendation --------

export interface GapRecommendation {
  id: string;
  schemaVersion: "1.0";
  area: {
    centroidLat: number;
    centroidLng: number;
    neighborhoodLabel: string;
    tractGeoids: string[];
  };
  why: string;
  stats: {
    population: number;
    needScore: number;
    underservedPopulation: number;
    nearestMatchedEventMinutes: number;
    languageGaps: LangCode[];
    foodDesert: boolean;
  };
  suggestedHost: {
    orgId: string;
    orgName: string;
    rationale: string;
    distanceFromCentroidMiles: number;
  } | null;
  suggestedCadence: string;
  expectedReachHouseholds: number;
  priority: number;
}

// -------- graph file --------

export interface GraphFile {
  schemaVersion: "1.0";
  generatedAt: ISODate;
  events: FoodEvent[];
  organizations: Organization[];
  locations: Location[];
  edges?: Edge[];
  embeddings?: {
    model: "all-MiniLM-L6-v2";
    dimensions: 384;
    vectors: { [eventId: string]: number[] };
  };
}

export type NodeType = "event" | "organization" | "location" | "tract";

export type EdgeType =
  | "hosts"
  | "located_at"
  | "serves"
  | "contained_in"
  | "near"
  | "speaks"
  | "supplies"
  | "requires"
  | "similar_to";

export interface Edge {
  from: { type: NodeType; id: string };
  to: { type: NodeType; id: string };
  type: EdgeType;
  weight?: number;
  metadata?: Record<string, unknown>;
}

// -------- ranking engine output (legacy event-based) --------

export interface RankedResult {
  event: FoodEvent;
  org: Organization;
  location: Location;
  distanceMeters: number;
  walkMinutes: number;
  transitMinutes: number | null;
  driveMinutes: number;
  minutesUntilStart: number;
  why: string;
  score: number;
}

// =========================================================================
// ENRICHED ORGANIZATION MODEL — the new shape backend produces
// =========================================================================
//
// Backend runs:
//   1. Scraper  → raw org records
//   2. Dedupe   → unique orgs
//   3. Regex tag → service/food/access/language tags
//   4. LLM enrichment → parsedHours, firstVisitGuide, plainEligibility, etc.
//   5. Output → enriched-orgs.json (consumed by this app)
//
// Runtime here is pure TS — no LLM calls. Everything is precomputed.

/** Backend's 7 service categories (regex-tagged). */
export type ServiceType =
  | "food_pantry"
  | "hot_meals"
  | "delivery"
  | "snap_assistance"
  | "drive_through"
  | "mobile_pantry"
  | "community_garden";

/** Backend's 7 food categories (regex-tagged). */
export type FoodCategory =
  | "produce"
  | "canned_goods"
  | "dairy"
  | "bread_bakery"
  | "protein"
  | "baby_supplies"
  | "frozen";

/** Backend's 6 access requirement tags (regex-tagged). */
export type AccessRequirement =
  | "appointment_required"
  | "walk_in"
  | "no_id_required"
  | "photo_id"
  | "proof_of_address"
  | "income_verification";

/** Data reliability — matches backend's fresh/recent/stale/unknown tiers. */
export type ReliabilityTier = "fresh" | "recent" | "stale" | "unknown";

export interface ReliabilitySignal {
  tier: ReliabilityTier;
  /** 0..1 numeric score backing the tier. */
  score: number;
  /** ISO date backend last confirmed this record. */
  lastConfirmedAt: string;
}

/** One weekly time slot, e.g. { start: "10:00", end: "13:00" }. */
export interface TimeSlot {
  start: string; // "HH:MM" 24h
  end: string;
  note?: string;
}

/** Structured weekly hours — LLM-parsed from the raw hours string. */
export interface WeeklySchedule {
  mon?: TimeSlot[];
  tue?: TimeSlot[];
  wed?: TimeSlot[];
  thu?: TimeSlot[];
  fri?: TimeSlot[];
  sat?: TimeSlot[];
  sun?: TimeSlot[];
  exceptions?: { date: string; note: string }[];
  byAppointment?: boolean;
  /** Always keep the original string — fallback when parsing fails. */
  raw: string;
}

export interface TransitProximitySimple {
  name: string;
  distanceMeters: number;
  walkMinutes?: number;
}

export interface TransitDirectionMode {
  action: string;
  lines?: string[];
  station?: string;
  routes?: string[];
  stopName?: string;
  walkMinutes?: number;
}

export interface TransitDirections {
  metro?: TransitDirectionMode;
  bus?: TransitDirectionMode;
  recommended: "metro" | "bus";
  naturalDirections?: string;
}

export interface TransitBlock {
  nearestMetro?: {
    name: string;
    stationId: string;
    lines: string[];
    walkMinutes: number;
    walkDistanceM: number;
    osrmUsed: boolean;
  };
  nearestBus?: {
    stopId: string;
    stopName: string;
    route: string;
    allRoutes: string[];
    walkMinutes: number;
    walkDistanceM: number;
    osrmUsed: boolean;
  };
  walkMinutesToMetro?: number;
  walkMinutesToBus?: number;
  transitSummary: string;
  transitDirections?: TransitDirections;
}

export interface UrgencySignal {
  level: "high" | "medium" | "low";
  gapScore: number;
  multiplier: number;
  population: number;
  underservedPopulation: number;
  nearbyOrgCount: number;
  areaLabel: string;
  message: string;
}

export interface NeighborhoodContext {
  zip: string;
  povertyRate: number;            // 0..1
  snapRate: number;               // 0..1
  medianIncome: number;
  /** Backend's composite formula: 0.6·poverty + 0.3·snap + 0.1·incomeScore */
  foodInsecurityScore: number;    // 0..1
}

/** Build-time LLM enrichment block. All fields cached by input hash. */
export interface AIEnrichment {
  /** Structured hours parsed from raw string. May be absent if parse failed. */
  parsedHours?: WeeklySchedule;
  /** 3 plain-language bullets for "what to expect on your first visit". */
  firstVisitGuide: string[];
  /** One-sentence eligibility summary: "Anyone welcome. Bring nothing." */
  plainEligibility: string;
  /** Optional cultural/dietary notes: "Serves Ethiopian community, teff available". */
  culturalNotes?: string;
  /** 0..1, how welcoming this place is likely to be for a first-timer. */
  toneScore: number;
  /** Per-service confidence scores, LLM-verified above the regex tags. */
  serviceConfidence?: Partial<Record<ServiceType, number>>;
  /** Per-food-type confidence scores, LLM-verified. */
  foodTypeConfidence?: Partial<Record<FoodCategory, number>>;
  /** One warm sentence describing what the place is — card headline. */
  heroCopy?: string;
  /** Optional callouts when multiple sources disagree about a field. */
  reconciliationWarnings?: string[];
  /** 0..1 overall data quality score. */
  qualityScore: number;
  /** ISO date the enrichment was generated. */
  generatedAt: string;
  /** LLM model identifier used. */
  model: string;
}

/** The enriched org record — the atomic unit for the new UI. */
export interface EnrichedOrganization {
  // -- identity --
  id: string;
  name: string;

  // -- contact --
  address: string;                // cleaned street address
  phone?: string;                  // "(XXX) XXX-XXXX"
  website?: string;                // verified https URL
  email?: string;

  // -- raw hours string (kept alongside parsedHours) --
  hoursRaw: string;

  // -- geography --
  zip: string;
  neighborhood?: string;           // e.g., "Columbia Heights"
  lat: number;
  lon: number;
  state: StateCode | string;       // may be empty for records outside DMV
  city: string;

  // -- backend regex tags --
  services: ServiceType[];
  foodTypes: FoodCategory[];
  accessRequirements: AccessRequirement[];
  languages: LangCode[];

  // -- enrichment blocks --
  nearestTransit?: TransitProximitySimple | string;
  neighborhoodContext?: NeighborhoodContext;
  reliability: ReliabilitySignal;
  ai: AIEnrichment;

  // -- full transit block (stage 6) --
  transit?: TransitBlock;

  // -- urgency signal for donors (from equity gap analysis) --
  urgency?: UrgencySignal | null;

  // -- donor & volunteer --
  acceptsFoodDonations?: boolean;
  acceptsMoneyDonations?: boolean;
  acceptsVolunteers?: boolean;
  donateUrl?: string | null;
  volunteerUrl?: string | null;

  // -- provenance --
  sourceId: string;                // which of the 23 sources
  sourceName?: string;             // human-readable label
  sourceUrl?: string;              // direct link to source record
  sourceIds?: string[];            // all source IDs that reported this org
  crossSourceCount?: number;       // number of independent sources
  nearbyOrgIds?: string[];         // NEARBY edges within 1 km
  createdAt: string;
  updatedAt: string;
}

// -------- ranking output for the enriched model --------

export type OpenState = "open" | "opens_today" | "opens_this_week" | "closed_long" | "unknown";

export interface OpenStatus {
  state: OpenState;
  /** User-facing label: "Open now", "Opens at 10am", "Opens Saturday 10am", "Call for hours". */
  label: string;
  /** Absolute ISO timestamp for next state change, if known. */
  nextChangeAt?: string;
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
  searchScore?: number | null;
}

export interface UserContext {
  coords: Coords;
  /** User's preferred language (browser locale short code). */
  language: LangCode;
  /** "now" for deterministic ranking in the demo. */
  now: Date;
  /** Optional natural-language search query. */
  query?: string;
}

