"""
Stage 8 -- Simplified TLDAI: Temporal-Linguistic-Dignity Accessibility Index.

For each ZIP in the DMV, compute accessibility across 3 dimensions:
  - Day of week (Mon-Sun): are pantries open on this day?
  - Language: are there pantries that speak this language?
  - Dignity tier: walk-in/no-ID vs appointment/paperwork

Uses haversine distance (3km radius) and our existing hours/language/requirement data.

Input:  output/stage4_normalized.json
Output: public/data/access-summary.json

Usage:
  python scripts/stage8_tldai.py
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PIPELINE = Path(__file__).resolve().parents[1]
PROJECT  = PIPELINE.parent
INPUT    = PIPELINE / "output" / "stage4_normalized.json"
OUTPUT   = PROJECT / "public" / "data" / "access-summary.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
LANGUAGES = ["Spanish", "Amharic", "Chinese", "Vietnamese", "Korean", "Arabic", "French"]
DIGNITY_TIERS = ["low_friction", "any_walk_in", "appointment_ok"]

# Use the same ZIP centroids from equity gap analysis
from stage7_equity import ZIP_CENTROIDS, DMV_NEED_DATA


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _org_open_on_day(rec: dict, day: str) -> bool:
    """Check if org has hours on this day."""
    hs = rec.get("hours_structured")
    if not hs:
        # No structured hours — check raw for day name
        raw = (rec.get("hours") or "").lower()
        if not raw:
            return True  # unknown hours = assume available (generous)
        day_names = {
            "mon": ["mon", "monday"], "tue": ["tue", "tuesday"], "wed": ["wed", "wednesday"],
            "thu": ["thu", "thursday"], "fri": ["fri", "friday"],
            "sat": ["sat", "saturday"], "sun": ["sun", "sunday"],
        }
        for name in day_names.get(day, []):
            if name in raw:
                return True
        # Check for ranges like "monday-friday" or "mon-fri"
        if day in ("mon", "tue", "wed", "thu", "fri") and ("weekday" in raw or "mon" in raw and "fri" in raw):
            return True
        return False

    # Check structured hours
    return any(entry.get("day") == day for entry in hs)


def _org_speaks_language(rec: dict, lang: str) -> bool:
    """Check if org serves this language."""
    return lang in (rec.get("languages") or [])


def _org_dignity_tier(rec: dict) -> str:
    """Classify org by friction level."""
    reqs = rec.get("requirements") or []
    if "walk_in" in reqs and "no_id_required" in reqs:
        return "low_friction"
    elif "walk_in" in reqs:
        return "any_walk_in"
    else:
        return "appointment_ok"


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]
    geo_orgs = [(r, r["lat"], r["lon"]) for r in records if r.get("lat") and r.get("lon")]
    print(f"Stage 8: TLDAI ({len(geo_orgs)} geo orgs, {len(ZIP_CENTROIDS)} ZIPs)")

    per_zip = {}

    for zip_code, centroid in ZIP_CENTROIDS.items():
        clat, clon = centroid
        need = DMV_NEED_DATA.get(zip_code, {})
        label = need.get("label", zip_code)

        # Find orgs within 3km
        nearby = [rec for rec, lat, lon in geo_orgs if _haversine_km(clat, clon, lat, lon) <= 3.0]

        if not nearby:
            per_zip[zip_code] = {
                "zip": zip_code,
                "label": label,
                "centroidLat": clat,
                "centroidLon": clon,
                "nearbyOrgCount": 0,
                "accessScore": 0.0,
                "dayAccess": {d: 0 for d in DAYS},
                "languageAccess": {l: 0 for l in LANGUAGES},
                "dignityAccess": {t: 0 for t in DIGNITY_TIERS},
                "gaps": ["No food resources within walking distance."],
            }
            continue

        # Day access: how many orgs open on each day
        day_access = {}
        for day in DAYS:
            open_count = sum(1 for r in nearby if _org_open_on_day(r, day))
            day_access[day] = open_count

        # Language access: how many orgs serve each language
        lang_access = {}
        for lang in LANGUAGES:
            count = sum(1 for r in nearby if _org_speaks_language(r, lang))
            lang_access[lang] = count

        # Dignity tier: how many orgs at each friction level
        dignity_access = defaultdict(int)
        for r in nearby:
            tier = _org_dignity_tier(r)
            dignity_access[tier] += 1
            # Lower tiers include higher tiers
            if tier == "low_friction":
                dignity_access["any_walk_in"] += 1
                dignity_access["appointment_ok"] += 1
            elif tier == "any_walk_in":
                dignity_access["appointment_ok"] += 1

        # Overall access score (0-1)
        day_coverage = sum(1 for d, c in day_access.items() if c > 0) / 7
        lang_diversity = sum(1 for l, c in lang_access.items() if c > 0) / len(LANGUAGES)
        low_friction_avail = 1.0 if dignity_access["low_friction"] > 0 else 0.5 if dignity_access["any_walk_in"] > 0 else 0.2
        access_score = round(0.4 * day_coverage + 0.3 * low_friction_avail + 0.3 * min(1.0, len(nearby) / 5), 2)

        # Identify gaps
        gaps = []
        zero_days = [d for d in DAYS if day_access[d] == 0]
        if zero_days:
            day_labels = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday",
                         "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}
            gaps.append(f"No food resources on {', '.join(day_labels[d] for d in zero_days)}.")
        if dignity_access["low_friction"] == 0:
            gaps.append("No walk-in, no-ID-required options available.")
        for lang in ["Spanish", "Amharic"]:
            if lang_access[lang] == 0 and zip_code in ("20783", "20009", "20010", "20901", "20902", "20910", "20912", "22304"):
                gaps.append(f"No {lang}-speaking food resources despite large {lang}-speaking community.")

        per_zip[zip_code] = {
            "zip": zip_code,
            "label": label,
            "centroidLat": clat,
            "centroidLon": clon,
            "nearbyOrgCount": len(nearby),
            "accessScore": access_score,
            "dayAccess": day_access,
            "languageAccess": lang_access,
            "dignityAccess": dict(dignity_access),
            "gaps": gaps,
        }

    # Save
    output = {
        "generatedAt": "2026-04-12",
        "totalZips": len(per_zip),
        "zips": per_zip,
        "summary": {
            "avgAccessScore": round(sum(z["accessScore"] for z in per_zip.values()) / len(per_zip), 2),
            "zipsWithZeroOrgs": sum(1 for z in per_zip.values() if z["nearbyOrgCount"] == 0),
            "zipsWithWeekendGap": sum(1 for z in per_zip.values()
                                      if z["dayAccess"].get("sat", 0) == 0 and z["dayAccess"].get("sun", 0) == 0),
            "zipsWithNoLowFriction": sum(1 for z in per_zip.values()
                                         if z["dignityAccess"].get("low_friction", 0) == 0),
        }
    }
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nTLDAI Summary:")
    print(f"  Avg access score: {output['summary']['avgAccessScore']}")
    print(f"  ZIPs with 0 orgs: {output['summary']['zipsWithZeroOrgs']}")
    print(f"  ZIPs with no weekend access: {output['summary']['zipsWithWeekendGap']}")
    print(f"  ZIPs with no low-friction options: {output['summary']['zipsWithNoLowFriction']}")

    # Show worst access
    worst = sorted(per_zip.values(), key=lambda z: z["accessScore"])
    print(f"\n  Worst access ZIPs:")
    for z in worst[:5]:
        print(f"    {z['zip']} {z['label']:<30} score={z['accessScore']} orgs={z['nearbyOrgCount']} gaps={z['gaps'][:1]}")


if __name__ == "__main__":
    main()
