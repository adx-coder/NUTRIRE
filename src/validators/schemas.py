from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HoursEntry(BaseModel):
    day: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    open: str
    close: str
    note: Optional[str] = None


class RawRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[str] = None
    food_types: Optional[list[str]] = None
    requirements: Optional[list[str]] = None
    services: Optional[list[str]] = None
    languages: Optional[list[str]] = None
    event_date: Optional[str] = None
    event_frequency: Optional[Literal["one-time", "weekly", "biweekly", "monthly", "ongoing"]] = None
    raw_text: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v.strip()

    @field_validator("website", mode="before")
    @classmethod
    def clean_website(cls, v: object) -> Optional[str]:
        if not v:
            return None
        s = str(v).strip()
        return s if s.startswith("http") else None


class NormalizedRecord(RawRecord):
    # ── Geo ───────────────────────────────────────────────────────────────────
    lat: Optional[float] = None
    lon: Optional[float] = None
    full_address: str = ""

    # ── Transit enrichment (WMATA haversine fallback) ─────────────────────────
    nearestTransit: Optional[str] = None
    nearestTransitId: Optional[str] = None
    nearestTransitType: Optional[str] = None
    nearestTransitLines: Optional[list[str]] = None
    transitDistanceMeters: Optional[int] = None

    # ── NEW: multi-agency transit detail ─────────────────────────────────────
    transit_detail: Optional[dict] = None
    # Shape: {
    #   nearest_metro: {id, name, lines, distance_meters, walk_minutes} | None
    #   nearest_bus:   {id, agency, name, distance_meters, walk_minutes} | None
    #   reachable_hours_of_week: [int]   # 0..167 hours when transit-reachable
    # }

    # ── Census tract insecurity enrichment ───────────────────────────────────
    tract_id: Optional[str] = None
    tract_insecurity_score: Optional[float] = None
    tract_poverty_rate: Optional[float] = None
    tract_snap_rate: Optional[float] = None
    tract_median_income: Optional[int] = None
    tract_population: Optional[int] = None

    # ── NEW: CDC Social Vulnerability Index ──────────────────────────────────
    svi_composite: Optional[float] = None
    svi_socioeconomic: Optional[float] = None
    svi_household: Optional[float] = None
    svi_minority: Optional[float] = None
    svi_housing_transport: Optional[float] = None

    # ── Food desert / low food access zone ───────────────────────────────────
    is_food_desert: bool = False
    food_access_zone: Optional[str] = None
    food_access_designation: Optional[str] = None

    # ── Source provenance ─────────────────────────────────────────────────────
    source_ids: list[str] = Field(default_factory=list)

    # ── Reliability ───────────────────────────────────────────────────────────
    dataReliabilityScore: float = 0.5
    dataReliabilityLabel: Literal["fresh", "recent", "stale", "unknown"] = "unknown"
    dataLastChangedAt: Optional[str] = None

    # ── User feedback signals ─────────────────────────────────────────────────
    userReportCount: int = 0
    userPositiveCount: int = 0
    userNegativeCount: int = 0
    feedbackScore: Optional[float] = None   # positiveCount / totalCount  (0..1)

    # ── Visit outcome signals (needs-met log) ─────────────────────────────────
    visitCount: int = 0                     # confirmed visits logged
    needsMetCount: int = 0                  # visits where needs WERE met
    needsNotMetCount: int = 0               # visits where needs were NOT met
    needsMetRate: Optional[float] = None    # recency-weighted met / total  (0..1)
    needsMetScore: Optional[float] = None   # needsMetRate normalised for blending

    # ── Hours ─────────────────────────────────────────────────────────────────
    hours_structured: Optional[list[dict]] = None
    by_appointment: bool = False
    always_open: bool = False

    # ── NEW: hours reconciliation ─────────────────────────────────────────────
    hoursConfidence: Optional[float] = None
    hoursSources: Optional[list[str]] = None
    hoursConflicts: Optional[list[dict]] = None

    # ── Computed ranking score ────────────────────────────────────────────────
    priorityScore: float = 0.0

    # ── Derived / classified ──────────────────────────────────────────────────
    name_tokens: list[str] = Field(default_factory=list)
    food_types: list[str] = Field(default_factory=list)    # type: ignore[assignment]
    requirements: list[str] = Field(default_factory=list)  # type: ignore[assignment]
    services: list[str] = Field(default_factory=list)      # type: ignore[assignment]
    languages: list[str] = Field(default_factory=list)     # type: ignore[assignment]
    confidence: float = 0.5

    # ── NEW: agentic extraction provenance ───────────────────────────────────
    extractedBy: Optional[str] = None
    # e.g. "claude-haiku-4-5-20251001" | "claude-sonnet-4-5" | "regex"

    confidence_per_field: Optional[dict] = None
    # {name: float, address: float, hours: float, services: float, requirements: float}

    evidence: Optional[dict] = None
    # {hours: str, services: str, requirements: str, residency: str | None}

    # ── NEW: residency + population from extractor ────────────────────────────
    residencyRestriction: Optional[str] = None
    populationServed: Optional[str] = None

    # ── NEW: semantic enrichment fields (Enricher agent) ─────────────────────
    firstVisitGuide: Optional[list[str]] = None   # 2-3 plain-language bullets
    plainEligibility: Optional[str] = None        # one-sentence summary
    culturalNotes: Optional[str] = None
    toneScore: Optional[float] = None             # 0..1 first-timer friendliness
    heroCopy: Optional[str] = None                # one warm sentence for card

    # ── NEW: weather alert (outdoor events) ──────────────────────────────────
    is_outdoor: bool = False
    weather_alert: Optional[dict] = None
    # {level: "watch"|"warning", reason: str, valid_until: str (ISO)}

    # ── NEW: sentence embedding for semantic search ───────────────────────────
    embedding: Optional[list[float]] = None       # 384-dim all-MiniLM-L6-v2
