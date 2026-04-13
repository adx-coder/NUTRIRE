"""
Stage 5 -- Export normalized records to frontend-consumable JSON.

Transforms pipeline records into clean JSON for the React frontend.
Drops internal fields (raw_text, etc.), renames to camelCase where needed,
maps language names to codes, builds nested AI enrichment block.

Input:  output/stage4_normalized.json
Output: public/data/enriched-orgs.json
        public/data/metadata.json

Usage:
  python scripts/stage5_export.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PIPELINE    = Path(__file__).resolve().parents[1]
PROJECT     = PIPELINE.parent
INPUT       = PIPELINE / "output" / "stage4_normalized.json"
OUTPUT_DIR  = PROJECT / "public" / "data"
OUTPUT_ORGS = OUTPUT_DIR / "enriched-orgs.json"
OUTPUT_META = OUTPUT_DIR / "metadata.json"

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


def transform_record(rec: dict) -> dict:
    """Transform a pipeline record to frontend EnrichedOrganization format."""

    # Languages: names → codes
    lang_codes = [_lang_to_code(l) for l in (rec.get("languages") or [])]

    # Build AI enrichment block
    ai: dict = {
        "heroCopy": rec.get("heroCopy"),
        "firstVisitGuide": rec.get("firstVisitGuide") or [],
        "plainEligibility": rec.get("plainEligibility", ""),
        "culturalNotes": rec.get("culturalNotes"),
        "toneScore": rec.get("toneScore", 0.6),
        "qualityScore": (rec.get("reliability") or {}).get("score", 0.5),
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": "ministral-8b",
    }

    # Parsed hours
    parsed = _build_weekly_schedule(rec.get("hours_structured"), rec.get("hours"))
    if parsed:
        ai["parsedHours"] = parsed

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
        "zip": rec.get("zip", ""),
        "lat": rec.get("lat"),
        "lon": rec.get("lon"),
        "state": rec.get("state", ""),
        "city": rec.get("city", ""),

        # Tags
        "services": rec.get("services") or ["food_pantry"],
        "foodTypes": rec.get("food_types") or [],
        "accessRequirements": rec.get("requirements") or [],
        "languages": lang_codes,

        # Reliability
        "reliability": rec.get("reliability") or {"tier": "unknown", "score": 0.5,
                                                   "lastConfirmedAt": datetime.now(timezone.utc).isoformat()},
        # AI enrichment
        "ai": ai,

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

        # Timestamps
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    return out


def build_metadata(records: list[dict], exported: list[dict]) -> dict:
    """Build metadata.json with pipeline stats."""
    by_state: dict[str, int] = {}
    by_source: dict[str, int] = {}
    has_hours = 0
    has_coords = 0
    has_hero = 0

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

    total = len(exported)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "totalOrganizations": total,
        "byState": by_state,
        "bySource": by_source,
        "coverage": {
            "hasHours": has_hours,
            "hasCoords": has_coords,
            "hasHeroCopy": has_hero,
            "hasHoursPct": round(has_hours / total * 100) if total else 0,
            "hasCoordsPct": round(has_coords / total * 100) if total else 0,
        },
        "sources": [
            {"id": sid, "name": SOURCE_NAMES.get(sid, sid), "count": count}
            for sid, count in sorted(by_source.items(), key=lambda x: -x[1])
        ],
    }


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]
    total = len(records)
    print(f"Stage 5: exporting {total} records to frontend format")

    # Transform all records
    exported = [transform_record(r) for r in records]

    # Filter out records without essential fields
    valid = [r for r in exported if r.get("name") and r.get("address")]
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
    has_lat = sum(1 for r in exported if r.get("lat"))
    has_hours = sum(1 for r in exported if r.get("hoursRaw"))
    has_hero = sum(1 for r in exported if r.get("ai", {}).get("heroCopy"))
    has_guide = sum(1 for r in exported if r.get("ai", {}).get("firstVisitGuide"))
    has_lang = sum(1 for r in exported if r.get("languages"))

    print(f"\n{'='*60}")
    print(f"EXPORT: {len(exported)} records to public/data/")
    print(f"{'='*60}")
    print(f"  With coordinates:     {has_lat}/{len(exported)} ({round(has_lat/len(exported)*100)}%)")
    print(f"  With hours:           {has_hours}/{len(exported)} ({round(has_hours/len(exported)*100)}%)")
    print(f"  With heroCopy:        {has_hero}/{len(exported)} ({round(has_hero/len(exported)*100)}%)")
    print(f"  With firstVisitGuide: {has_guide}/{len(exported)} ({round(has_guide/len(exported)*100)}%)")
    print(f"  With languages:       {has_lang}/{len(exported)} ({round(has_lang/len(exported)*100)}%)")
    print(f"\n  Frontend files:")
    print(f"    {OUTPUT_ORGS}")
    print(f"    {OUTPUT_META}")


if __name__ == "__main__":
    main()
