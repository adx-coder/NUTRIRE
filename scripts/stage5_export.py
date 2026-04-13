"""
Stage 5 -- Export normalized records to frontend-consumable JSON.

Transforms pipeline records into clean JSON for the React frontend.
Drops internal fields (raw_text, etc.), renames to camelCase where needed,
maps language names to codes, builds nested AI enrichment block.

Reads the richest available stage output in priority order:
  stage9_weather.json  (transit + weather)
  stage6_transit.json  (transit only)
  stage4_normalized.json  (base)

New fields exported (transit):
  transit.nearestMetro          {name, lines, walkMinutes, walkDistanceM, osrmUsed}
  transit.nearestBus            {route, stopName, walkMinutes, walkDistanceM, osrmUsed}
  transit.walkMinutesToMetro    int
  transit.walkMinutesToBus      int
  transit.reachableHoursOfWeek  [int]   0-167 hour-of-week Metro is running
  transit.transitSummary        str     human-readable one-liner
  transit.enrichedAt            str     ISO timestamp

New fields exported (weather):
  weatherAlert                  null | {event, level, severity, headline,
                                        description, instruction,
                                        validFrom, validUntil,
                                        affectsTravel, nwsId, fetchedAt}

Input:  output/stage9_weather.json  (preferred)
        output/stage6_transit.json  (fallback)
        output/stage4_normalized.json  (base fallback)
Output: public/data/enriched-orgs.json
        public/data/metadata.json

Usage:
  python scripts/stage5_export.py
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PIPELINE    = Path(__file__).resolve().parents[1]
PROJECT     = PIPELINE  # Nutrire root (scripts/ is one level below)
OUTPUT_DIR  = PROJECT / "frontend" / "public" / "data"
OUTPUT_ORGS = OUTPUT_DIR / "enriched-orgs.json"
OUTPUT_META = OUTPUT_DIR / "metadata.json"
EQUITY_GAPS = OUTPUT_DIR / "equity-gaps.json"
TRANSIT_LLM_CACHE = PIPELINE / "state" / "transit-llm-cache.json"

# Pick richest available input
def _pick_input() -> Path:
    for name in ("stage9_weather.json", "stage6_transit.json", "stage4_normalized.json"):
        p = PIPELINE / "output" / name
        if p.exists():
            return p
    raise FileNotFoundError("No pipeline output found. Run at least stage4_normalize.py first.")

INPUT = _pick_input()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Language name → code mapping
LANG_CODE: dict[str, str] = {
    "spanish": "es", "french": "fr", "amharic": "am", "arabic": "ar",
    "chinese": "zh", "vietnamese": "vi", "korean": "ko", "portuguese": "pt",
    "russian": "ru", "haitian creole": "ht", "urdu": "ur", "bengali": "bn",
    "tigrinya": "ti", "farsi": "fa", "persian": "fa",
}

# Source ID → human-readable name
SOURCE_NAMES: dict[str, str] = {
    "cafb": "Capital Area Food Bank",
    "mdfb-find-food": "Maryland Food Bank",
    "two11md": "211 Maryland",
    "two11va": "211 Virginia",
    "mocofood": "Montgomery County Food Council",
}

# ZIP → neighborhood name for DMV ZIPs
ZIP_NEIGHBORHOOD: dict[str, str] = {
    # DC
    "20001": "Shaw", "20002": "Trinidad", "20003": "Capitol Hill",
    "20004": "Penn Quarter", "20005": "Downtown", "20006": "Foggy Bottom",
    "20007": "Georgetown", "20008": "Cleveland Park", "20009": "Adams Morgan",
    "20010": "Columbia Heights", "20011": "Petworth", "20012": "Brightwood",
    "20015": "Chevy Chase DC", "20016": "Tenleytown", "20017": "Brookland",
    "20018": "Woodridge", "20019": "Deanwood", "20020": "Anacostia",
    "20024": "Southwest Waterfront", "20032": "Congress Heights",
    "20036": "Dupont Circle", "20037": "West End",
    # MD — Montgomery
    "20814": "Bethesda", "20815": "Chevy Chase", "20850": "Rockville",
    "20851": "Rockville", "20852": "North Bethesda", "20853": "Burtonsville",
    "20854": "Potomac", "20874": "Germantown", "20877": "Gaithersburg",
    "20878": "Gaithersburg", "20886": "Montgomery Village",
    "20895": "Kensington", "20901": "Silver Spring", "20902": "Wheaton",
    "20903": "Silver Spring", "20904": "Colesville", "20906": "Aspen Hill",
    "20910": "Silver Spring", "20912": "Takoma Park",
    # MD — PG County
    "20706": "Lanham", "20707": "Laurel", "20710": "Bladensburg",
    "20712": "Mt Rainier", "20715": "Bowie", "20735": "Clinton",
    "20737": "Riverdale Park", "20740": "College Park",
    "20743": "Capitol Heights", "20744": "Fort Washington",
    "20745": "Oxon Hill", "20746": "Suitland", "20747": "District Heights",
    "20748": "Temple Hills", "20770": "Greenbelt", "20774": "Upper Marlboro",
    "20781": "Hyattsville", "20782": "Hyattsville", "20783": "Langley Park",
    "20784": "Hyattsville", "20785": "Cheverly",
    # VA — NoVA
    "22003": "Annandale", "22030": "Fairfax", "22041": "Baileys Crossroads",
    "22042": "Falls Church", "22043": "Falls Church", "22046": "Falls Church",
    "22101": "McLean", "22150": "Springfield", "22180": "Vienna",
    "22191": "Woodbridge", "22192": "Woodbridge", "22193": "Dale City",
    "22201": "Arlington", "22202": "Arlington", "22204": "Arlington",
    "22301": "Alexandria", "22304": "Alexandria", "22306": "Alexandria",
    # MD — Baltimore area
    "21201": "Baltimore", "21202": "Inner Harbor", "21206": "Baltimore",
    "21211": "Hampden", "21213": "Clifton Park", "21215": "Baltimore",
    "21217": "Bolton Hill", "21218": "Charles Village", "21224": "Canton",
    "21228": "Catonsville", "21230": "Federal Hill",
    "21042": "Ellicott City", "21044": "Columbia", "21045": "Columbia",
}

# Service value normalization (fix collisions from LLM output)
SERVICE_NORMALIZE = {
    "drive_thru": "drive_through",
    "mobile_food_bank": "mobile_pantry",
}

# Values that are requirements, not services
NOT_SERVICES = {"walk_in", "no_id_required", "appointment_required"}


def _lang_to_code(name: str) -> str:
    """Convert language name to ISO code."""
    return LANG_CODE.get(name.lower(), name.lower()[:2])


def _build_weekly_schedule(hours_structured: list[dict] | None, hours_raw: str | None) -> dict | None:
    """Convert [{day, open, close, note}] to {mon: [{start, end, note}], ...} format."""
    schedule: dict = {"raw": hours_raw or ""}

    if not hours_structured:
        return schedule if hours_raw else None

    for entry in hours_structured:
        day = entry.get("day")
        if not day:
            continue
        slot = {"start": entry.get("open", ""), "end": entry.get("close", "")}
        if entry.get("note"):
            slot["note"] = entry["note"]
        schedule.setdefault(day, []).append(slot)

    return schedule


def _build_transit_block(rec: dict) -> dict | None:
    """Extract transit_detail into a clean camelCase frontend block."""
    detail = rec.get("transit_detail")
    if not detail:
        return None

    metro_raw = detail.get("nearest_metro")
    bus_raw   = detail.get("nearest_bus")

    metro = None
    if metro_raw:
        metro = {
            "name":           metro_raw.get("name"),
            "stationId":      metro_raw.get("id"),
            "lines":          metro_raw.get("lines", []),
            "walkMinutes":    metro_raw.get("walk_minutes"),
            "walkDistanceM":  metro_raw.get("walk_distance_m"),
            "lat":            metro_raw.get("lat"),
            "lon":            metro_raw.get("lon"),
            "osrmUsed":       metro_raw.get("osrm_used", False),
        }

    bus = None
    if bus_raw:
        bus = {
            "stopId":         bus_raw.get("id"),
            "stopName":       bus_raw.get("stop_name"),
            "route":          bus_raw.get("route"),
            "allRoutes":      bus_raw.get("all_routes", []),
            "walkMinutes":    bus_raw.get("walk_minutes"),
            "walkDistanceM":  bus_raw.get("walk_distance_m"),
            "lat":            bus_raw.get("lat"),
            "lon":            bus_raw.get("lon"),
            "osrmUsed":       bus_raw.get("osrm_used", False),
        }

    # Build actionable transit directions (#3)
    directions = _build_transit_directions(metro_raw, bus_raw, rec)

    return {
        "nearestMetro":           metro,
        "nearestBus":             bus,
        "walkMinutesToMetro":     detail.get("walk_minutes_to_metro"),
        "walkMinutesToBus":       detail.get("walk_minutes_to_bus"),
        "reachableHoursOfWeek":   detail.get("reachable_hours_of_week", []),
        "transitSummary":         detail.get("transit_summary", ""),
        "transitDirections":      directions,
        "enrichedAt":             detail.get("enriched_at", ""),
    }


def _build_transit_directions_template(metro_raw: dict | None, bus_raw: dict | None,
                                       rec: dict) -> dict | None:
    """Fallback: build transit directions from templates when LLM is unavailable."""
    primary_type = rec.get("nearestTransitType")
    directions: dict = {}

    if metro_raw:
        lines = metro_raw.get("lines", [])
        name = metro_raw.get("name", "")
        walk_min = metro_raw.get("walk_minutes")
        line_str = "/".join(lines) if lines else "Metro"
        directions["metro"] = {
            "action": f"Take the {line_str} line to {name}" +
                      (f" ({walk_min} min walk from stop)" if walk_min else ""),
            "lines": lines,
            "station": name,
            "walkMinutes": walk_min,
        }

    if bus_raw:
        route = bus_raw.get("route", "")
        all_routes = bus_raw.get("all_routes", [route]) if route else []
        stop_name = bus_raw.get("stop_name", "")
        walk_min = bus_raw.get("walk_minutes")
        route_str = "/".join(all_routes) if all_routes else "Bus"
        directions["bus"] = {
            "action": f"Take the {route_str} bus, get off at {stop_name}" +
                      (f" ({walk_min} min walk from stop)" if walk_min else ""),
            "routes": all_routes,
            "stopName": stop_name,
            "walkMinutes": walk_min,
        }

    if not directions:
        return None

    directions["recommended"] = primary_type or ("metro" if metro_raw else "bus")
    return directions


# ── LLM-powered transit directions ──────────────────────────────────────────

TRANSIT_PROMPT = """You are writing brief, friendly transit directions to a food assistance organization.
Write like you're texting a friend who needs to get there. Be specific with route numbers and stop names.
2-3 sentences max. If both metro and bus are available, mention both but recommend the better option.
Do NOT include org name or address in the directions — the user already knows where they're going.
Do NOT say "you can" or "you could" — just say what to do: "Hop on the…", "Take the…", "Grab the…" etc."""

_transit_llm_cache: dict = {}
_transit_llm_client = None


def _load_transit_cache() -> dict:
    """Load LLM transit directions cache from disk."""
    if TRANSIT_LLM_CACHE.exists():
        try:
            return json.loads(TRANSIT_LLM_CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_transit_cache(cache: dict):
    """Persist LLM transit directions cache."""
    TRANSIT_LLM_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TRANSIT_LLM_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _get_transit_client():
    """Lazy-init Mistral client for transit directions."""
    global _transit_llm_client
    if _transit_llm_client is None:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            return None
        from mistralai.client import Mistral
        _transit_llm_client = Mistral(api_key=api_key)
    return _transit_llm_client


def _transit_cache_key(metro_raw: dict | None, bus_raw: dict | None, rec: dict) -> str:
    """Build a stable cache key from transit data."""
    blob = json.dumps({
        "metro": metro_raw,
        "bus": bus_raw,
        "name": rec.get("name", ""),
        "address": rec.get("address", ""),
    }, sort_keys=True)
    return hashlib.md5(blob.encode("utf-8")).hexdigest()


def _build_llm_transit_input(metro_raw: dict | None, bus_raw: dict | None, rec: dict) -> str:
    """Build the user message for the LLM."""
    parts = [f"Destination: {rec.get('name', '?')} at {rec.get('address', '?')}, {rec.get('city', '')}, {rec.get('state', '')}"]

    if metro_raw:
        lines = metro_raw.get("lines", [])
        parts.append(f"Nearest metro: {metro_raw.get('name', '?')} station"
                     f" ({', '.join(lines) if lines else 'Metro'} line)"
                     f" — {metro_raw.get('walk_minutes', '?')} min walk from station to org")

    if bus_raw:
        routes = bus_raw.get("all_routes", [bus_raw.get("route", "?")])
        parts.append(f"Nearest bus: stop \"{bus_raw.get('stop_name', '?')}\""
                     f" (routes: {', '.join(routes)})"
                     f" — {bus_raw.get('walk_minutes', '?')} min walk from stop to org")

    return "\n".join(parts)


def _call_transit_llm(metro_raw: dict | None, bus_raw: dict | None,
                      rec: dict) -> str | None:
    """Call Mistral to generate natural transit directions. Returns text or None."""
    client = _get_transit_client()
    if not client:
        return None

    model = os.getenv("MISTRAL_MODEL", "ministral-8b-latest")
    user_msg = _build_llm_transit_input(metro_raw, bus_raw, rec)

    for attempt in range(3):
        try:
            resp = client.chat.complete(
                model=model,
                messages=[
                    {"role": "system", "content": TRANSIT_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=200,
                temperature=0.7,
            )
            text = resp.choices[0].message.content.strip()
            if text:
                return text
            break
        except Exception as exc:
            err = str(exc)
            if "429" in err or "rate" in err.lower():
                time.sleep(2 ** (attempt + 1))
            elif any(c in err for c in ("500", "502", "503")):
                time.sleep(3)
            else:
                break
    return None


def _build_transit_directions(metro_raw: dict | None, bus_raw: dict | None,
                              rec: dict) -> dict | None:
    """Build transit directions using LLM, with template fallback."""
    global _transit_llm_cache

    # Template-based structured data (always computed for metro/bus sub-fields)
    template = _build_transit_directions_template(metro_raw, bus_raw, rec)
    if template is None:
        return None

    # Try LLM for natural-language directions
    cache_key = _transit_cache_key(metro_raw, bus_raw, rec)

    if cache_key in _transit_llm_cache:
        cached = _transit_llm_cache[cache_key]
        template["naturalDirections"] = cached.get("text", "")
        return template

    llm_text = _call_transit_llm(metro_raw, bus_raw, rec)

    if llm_text:
        _transit_llm_cache[cache_key] = {
            "text": llm_text,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        template["naturalDirections"] = llm_text
    else:
        # Build a simple natural sentence from the template actions
        actions = []
        if template.get("metro"):
            actions.append(template["metro"]["action"])
        if template.get("bus"):
            actions.append(template["bus"]["action"])
        template["naturalDirections"] = ". ".join(actions) + "." if actions else ""

    return template


def _build_nearest_transit_simple(rec: dict) -> dict | None:
    """Build a {name, distanceMeters, walkMinutes} object from top-level transit fields."""
    name = rec.get("nearestTransit")
    if not name:
        return None
    transit_type = rec.get("nearestTransitType", "bus")
    detail = rec.get("transit_detail") or {}
    walk_key = f"walk_minutes_to_{transit_type}"
    return {
        "name": name,
        "distanceMeters": rec.get("transitDistanceMeters") or 0,
        "walkMinutes": detail.get(walk_key),
    }


def _build_weather_block(rec: dict) -> dict | None:
    """Convert weather_alert dict to camelCase frontend block."""
    alert = rec.get("weather_alert")
    if not alert:
        return None
    return {
        "event":          alert.get("event"),
        "level":          alert.get("level"),
        "severity":       alert.get("severity"),
        "headline":       alert.get("headline"),
        "description":    alert.get("description"),
        "instruction":    alert.get("instruction"),
        "validFrom":      alert.get("valid_from"),
        "validUntil":     alert.get("valid_until"),
        "affectsTravel":  alert.get("affects_travel", False),
        "nwsId":          alert.get("nws_id"),
        "fetchedAt":      alert.get("fetched_at"),
    }


def _load_equity_gaps() -> dict[str, dict]:
    """Load equity gap data keyed by ZIP code."""
    if not EQUITY_GAPS.exists():
        return {}
    try:
        data = json.loads(EQUITY_GAPS.read_text(encoding="utf-8"))
        gaps = data.get("gaps", [])
        return {g["zip"]: g for g in gaps if "zip" in g}
    except Exception:
        return {}

_EQUITY_BY_ZIP: dict[str, dict] = _load_equity_gaps()


def _build_urgency(zip_code: str) -> dict | None:
    """Build urgency signal for donors based on equity gap data."""
    gap_info = _EQUITY_BY_ZIP.get(zip_code)
    if not gap_info:
        return None
    gap_score = gap_info.get("gap", 0)
    if gap_score <= 0.01:
        return None

    pop = gap_info.get("population", 0)
    underserved = gap_info.get("underservedPopulation", gap_info.get("underserved_population", 0))
    nearby_orgs = gap_info.get("nearbyOrgCount", gap_info.get("nearby_org_count", 0))
    label = gap_info.get("label", zip_code)

    # Compute a multiplier: how much more impact donations have here
    # compared to the average area
    avg_gap = 0.03  # rough average gap across all ZIPs
    multiplier = round(gap_score / avg_gap, 1) if avg_gap > 0 else 1.0

    if gap_score >= 0.06:
        level = "high"
    elif gap_score >= 0.03:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "gapScore": round(gap_score, 4),
        "multiplier": multiplier,
        "population": pop,
        "underservedPopulation": underserved,
        "nearbyOrgCount": nearby_orgs,
        "areaLabel": label,
        "message": f"{label} has {underserved:,} underserved residents"
                   f" but only {nearby_orgs} food resource{'s' if nearby_orgs != 1 else ''}"
                   f" — donations here go {multiplier}x further.",
    }


def transform_record(rec: dict) -> dict:
    """Transform a pipeline record to frontend EnrichedOrganization format."""

    # Languages: names → codes
    lang_codes = [_lang_to_code(l) for l in (rec.get("languages") or [])]

    # Null out only truly garbage heroCopy/plainEligibility (not template-generated variants)
    hero_raw = (rec.get("heroCopy") or "").strip()
    if (hero_raw.lower().startswith("nourishing")
            or hero_raw in ("N/A", "n/a", "")
            or "No structured food" in hero_raw):
        hero_raw = None

    pe_raw = (rec.get("plainEligibility") or "").strip()
    if pe_raw.lower() in ("everyone welcome. bring nothing.", "n/a",
                           "no food assistance services listed.", ""):
        # Replace boilerplate with a varied template based on requirements
        import random
        reqs = rec.get("requirements") or []
        if "no_id_required" in reqs:
            pe_raw = random.choice([
                "Open to all — no ID or documents needed.",
                "Everyone is welcome. No paperwork or identification required.",
                "Just show up — no documents, no proof of address, no barriers.",
                "Come as you are. No ID needed, no questions asked.",
            ])
        elif "photo_id" in reqs:
            pe_raw = random.choice([
                "Bring a photo ID. Call ahead if you have questions.",
                "A photo ID is requested — call if you don't have one.",
            ])
        else:
            pe_raw = random.choice([
                "Open to the community. Call ahead to confirm what to bring.",
                "Available to community members — call for current requirements.",
                "Check with the org about what to bring — requirements may vary.",
                "Stop by or call to find out what you need for your first visit.",
                "Open to residents in the service area — call for details.",
            ])

    # Neighborhood from ZIP
    zip_code = rec.get("zip") or ""
    neighborhood = ZIP_NEIGHBORHOOD.get(zip_code)

    # Normalize state
    state = (rec.get("state") or "").strip()
    if state.lower() == "va":
        state = "VA"
    elif state.lower() == "md":
        state = "MD"
    elif state.lower() == "dc":
        state = "DC"

    # Normalize services (fix collisions)
    raw_services = rec.get("services") or ["food_pantry"]
    services = []
    for s in raw_services:
        s = SERVICE_NORMALIZE.get(s, s)
        if s not in NOT_SERVICES and s not in services:
            services.append(s)
    if not services:
        services = ["food_pantry"]

    # Build AI enrichment block
    ai: dict = {
        "heroCopy": hero_raw,
        "firstVisitGuide": rec.get("firstVisitGuide") or [],
        "plainEligibility": pe_raw or "",
        "culturalNotes": rec.get("culturalNotes"),
        "toneScore": rec.get("toneScore", 0.6),
        "qualityScore": (rec.get("reliability") or {}).get("score", 0.5),
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": rec.get("extractedBy", "ministral-8b"),
    }

    # Parsed hours
    parsed = _build_weekly_schedule(rec.get("hours_structured"), rec.get("hours"))
    if parsed:
        ai["parsedHours"] = parsed

    # Transit block (from stage 6) — suppress empty shells where metro+bus both null
    transit_block = _build_transit_block(rec)
    if transit_block and not transit_block.get("nearestMetro") and not transit_block.get("nearestBus"):
        transit_block = None  # don't emit empty transit shell to frontend

    # Weather block (from stage 9)
    weather_block = _build_weather_block(rec)

    # Source info
    source_id = rec.get("source_id", "unknown")

    out = {
        # Identity
        "id": rec.get("id", ""),
        "name": rec.get("name", ""),

        # Contact
        "address": rec.get("address", ""),
        "phone": rec.get("phone"),
        "website": rec.get("website"),

        # Hours raw
        "hoursRaw": rec.get("hours", ""),

        # Geography
        "zip": zip_code,
        "neighborhood": neighborhood,
        "lat": rec.get("lat"),
        "lon": rec.get("lon"),
        "state": state,
        "city": rec.get("city", ""),

        # Tags
        "services": services,
        "foodTypes": rec.get("food_types") or [],
        "accessRequirements": rec.get("requirements") or [],
        "languages": lang_codes,

        # Reliability
        "reliability": rec.get("reliability") or {"tier": "unknown", "score": 0.5,
                                                   "lastConfirmedAt": datetime.now(timezone.utc).isoformat()},
        # AI enrichment
        "ai": ai,

        # Transit enrichment (stage 6) — null if stage 6 not yet run
        "transit": transit_block,

        # Convenience top-level transit fields (for quick filtering/sorting)
        "nearestTransit":        _build_nearest_transit_simple(rec),
        "nearestTransitType":    rec.get("nearestTransitType"),
        "nearestTransitLines":   rec.get("nearestTransitLines"),
        "transitDistanceMeters": rec.get("transitDistanceMeters"),

        # Weather alert (stage 9) — null if no active alert or stage 9 not run
        "weatherAlert": weather_block,

        # Provenance
        "sourceId": source_id,
        "sourceName": SOURCE_NAMES.get(source_id, source_id),
        "sourceIds": rec.get("source_ids") or [source_id],
        "crossSourceCount": rec.get("cross_source_count", 1),

        # Donor/volunteer
        "acceptsFoodDonations": rec.get("accepts_food_donations", False),
        "acceptsMoneyDonations": rec.get("accepts_money_donations", False),
        "acceptsVolunteers": rec.get("accepts_volunteers", False),
        "donateUrl": rec.get("donate_url"),
        "volunteerUrl": rec.get("volunteer_url"),

        # Urgency signal for donors (from equity gap analysis)
        "urgency": _build_urgency(rec.get("zip", "")),

        # Timestamps
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    return out


def build_metadata(records: list[dict], exported: list[dict]) -> dict:
    """Build metadata.json with pipeline stats."""
    by_state: dict[str, int] = {}
    by_source: dict[str, int] = {}
    has_hours   = 0
    has_coords  = 0
    has_hero    = 0
    has_transit = 0
    has_metro   = 0
    has_bus     = 0
    has_weather = 0
    osrm_used   = 0
    has_website = 0
    has_food_types = 0
    has_cultural = 0
    has_languages = 0

    for r in exported:
        st = r.get("state", "?")
        by_state[st] = by_state.get(st, 0) + 1
        sid = r.get("sourceId", "?")
        by_source[sid] = by_source.get(sid, 0) + 1
        if r.get("hoursRaw"):
            has_hours += 1
        if r.get("lat") and r.get("lon"):
            has_coords += 1
        if r.get("ai", {}).get("heroCopy"):
            has_hero += 1
        if r.get("website"):
            has_website += 1
        if r.get("foodTypes"):
            has_food_types += 1
        if r.get("ai", {}).get("culturalNotes"):
            has_cultural += 1
        if r.get("languages"):
            has_languages += 1
        tr = r.get("transit") or {}
        if tr:
            has_transit += 1
        if tr.get("nearestMetro"):
            has_metro += 1
            if tr["nearestMetro"].get("osrmUsed"):
                osrm_used += 1
        if tr.get("nearestBus"):
            has_bus += 1
        if r.get("weatherAlert"):
            has_weather += 1

    total = len(exported)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "inputFile":   INPUT.name,
        "totalOrganizations": total,
        "byState": by_state,
        "bySource": by_source,
        "coverage": {
            "hasHours":        has_hours,
            "hasCoords":       has_coords,
            "hasHeroCopy":     has_hero,
            "hasWebsite":      has_website,
            "hasFoodTypes":    has_food_types,
            "hasCulturalNotes": has_cultural,
            "hasLanguages":    has_languages,
            "hasTransit":      has_transit,
            "hasMetro":        has_metro,
            "hasBus":          has_bus,
            "activeWeatherAlerts": has_weather,
            "osrmRoutedOrgs":  osrm_used,
            "hasHoursPct":     round(has_hours  / total * 100) if total else 0,
            "hasCoordsPct":    round(has_coords / total * 100) if total else 0,
            "hasWebsitePct":   round(has_website / total * 100) if total else 0,
            "hasFoodTypesPct": round(has_food_types / total * 100) if total else 0,
            "hasTransitPct":   round(has_transit / total * 100) if total else 0,
            "hasLanguagesPct": round(has_languages / total * 100) if total else 0,
        },
        "sources": [
            {"id": sid, "name": SOURCE_NAMES.get(sid, sid), "count": count}
            for sid, count in sorted(by_source.items(), key=lambda x: -x[1])
        ],
    }


def main():
    global _transit_llm_cache

    data = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]
    total = len(records)
    print(f"Stage 5: exporting {total} records to frontend format")

    # Load LLM transit directions cache
    _transit_llm_cache = _load_transit_cache()
    cache_before = len(_transit_llm_cache)
    print(f"  Transit LLM cache: {cache_before} entries loaded")

    # Transform all records
    exported = [transform_record(r) for r in records]

    # Save updated transit LLM cache
    cache_after = len(_transit_llm_cache)
    if cache_after > cache_before:
        _save_transit_cache(_transit_llm_cache)
        print(f"  Transit LLM cache: {cache_after - cache_before} new entries ({cache_after} total)")

    # Filter out records without essential fields
    valid = [r for r in exported if r.get("name") and r.get("address") and r.get("lat") and r.get("lon")]
    dropped = len(exported) - len(valid)
    if dropped:
        print(f"  Dropped {dropped} records with no name or address")
    exported = valid

    # Save orgs
    OUTPUT_ORGS.write_text(json.dumps(exported, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved {len(exported)} orgs to {OUTPUT_ORGS}")

    # Save metadata
    meta = build_metadata(records, exported)
    OUTPUT_META.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved metadata to {OUTPUT_META}")

    # Summary
    n = len(exported)
    pct = lambda x: round(x / n * 100) if n else 0
    has_lat     = sum(1 for r in exported if r.get("lat"))
    has_hours   = sum(1 for r in exported if r.get("hoursRaw"))
    has_hero    = sum(1 for r in exported if r.get("ai", {}).get("heroCopy"))
    has_guide   = sum(1 for r in exported if r.get("ai", {}).get("firstVisitGuide"))
    has_lang    = sum(1 for r in exported if r.get("languages"))
    has_transit = sum(1 for r in exported if r.get("transit"))
    has_metro   = sum(1 for r in exported if (r.get("transit") or {}).get("nearestMetro"))
    has_bus     = sum(1 for r in exported if (r.get("transit") or {}).get("nearestBus"))
    has_weather = sum(1 for r in exported if r.get("weatherAlert"))
    osrm_routed = sum(1 for r in exported
                      if (r.get("transit") or {}).get("nearestMetro", {}) and
                         (r.get("transit", {}).get("nearestMetro") or {}).get("osrmUsed"))

    has_llm_dir  = sum(1 for r in exported
                       if (r.get("transit") or {}).get("transitDirections", {}) and
                          (r.get("transit", {}).get("transitDirections") or {}).get("naturalDirections"))
    has_website  = sum(1 for r in exported if r.get("website"))
    has_ft       = sum(1 for r in exported if r.get("foodTypes"))
    has_cultural = sum(1 for r in exported if r.get("ai", {}).get("culturalNotes"))

    print(f"\n{'='*60}")
    print(f"EXPORT: {n} records -> public/data/  (input: {INPUT.name})")
    print(f"{'='*60}")
    print(f"  With coordinates:       {has_lat}/{n} ({pct(has_lat)}%)")
    print(f"  With hours:             {has_hours}/{n} ({pct(has_hours)}%)")
    print(f"  With website:           {has_website}/{n} ({pct(has_website)}%)")
    print(f"  With foodTypes:         {has_ft}/{n} ({pct(has_ft)}%)")
    print(f"  With heroCopy:          {has_hero}/{n} ({pct(has_hero)}%)")
    print(f"  With firstVisitGuide:   {has_guide}/{n} ({pct(has_guide)}%)")
    print(f"  With culturalNotes:     {has_cultural}/{n} ({pct(has_cultural)}%)")
    print(f"  With languages:         {has_lang}/{n} ({pct(has_lang)}%)")
    print(f"  -- Transit (stage 6) ----------------------------------")
    print(f"  With transit block:     {has_transit}/{n} ({pct(has_transit)}%)")
    print(f"    Nearest Metro:        {has_metro}  (OSRM real routes: {osrm_routed})")
    print(f"    Nearest Bus stop:     {has_bus}")
    print(f"    LLM directions:       {has_llm_dir}")
    print(f"  -- Weather (stage 9) ----------------------------------")
    print(f"  Active weather alerts:  {has_weather}")
    print(f"\n  Frontend files:")
    print(f"    {OUTPUT_ORGS}")
    print(f"    {OUTPUT_META}")


if __name__ == "__main__":
    main()
