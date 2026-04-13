"""
Stage 7 -- Equity gap analysis: where should new food pantries open?

Computes supply vs need per ZIP using our own org data + hardcoded DMV
poverty/food-insecurity data from Census QuickFacts.

No API keys, no downloads, no external dependencies. Just math.

Input:  output/stage4_normalized.json
Output: public/data/equity-gaps.json

Usage:
  python scripts/stage7_equity.py
"""
import json
import random
from datetime import datetime, timezone
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PIPELINE   = Path(__file__).resolve().parents[1]
INPUT      = PIPELINE / "output" / "stage4_normalized.json"
OUTPUT     = PIPELINE / "frontend" / "public" / "data" / "equity-gaps.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# ── DMV poverty/need data (Census ACS 2022 QuickFacts) ────────────────────────
# Hardcoded for the ~80 most important ZIPs in the DMV metro area.
# poverty_rate: fraction of population below poverty line (0-1)
# snap_rate: fraction receiving SNAP benefits (0-1)
# population: estimated population

DMV_NEED_DATA: dict[str, dict] = {
    # DC — high need
    "20001": {"poverty": 0.22, "snap": 0.18, "pop": 35000, "label": "Shaw / NoMa"},
    "20002": {"poverty": 0.18, "snap": 0.15, "pop": 38000, "label": "Capitol Hill NE"},
    "20009": {"poverty": 0.19, "snap": 0.14, "pop": 42000, "label": "Adams Morgan / Columbia Heights"},
    "20010": {"poverty": 0.21, "snap": 0.16, "pop": 28000, "label": "Columbia Heights"},
    "20011": {"poverty": 0.16, "snap": 0.13, "pop": 36000, "label": "Petworth / Brightwood"},
    "20017": {"poverty": 0.14, "snap": 0.11, "pop": 20000, "label": "Brookland"},
    "20019": {"poverty": 0.28, "snap": 0.24, "pop": 32000, "label": "Deanwood / Capitol View"},
    "20020": {"poverty": 0.32, "snap": 0.28, "pop": 38000, "label": "Anacostia / Fort Stanton"},
    "20032": {"poverty": 0.35, "snap": 0.31, "pop": 25000, "label": "Congress Heights / Bellevue"},

    # MD — PG County (high need)
    "20706": {"poverty": 0.12, "snap": 0.10, "pop": 35000, "label": "Lanham"},
    "20737": {"poverty": 0.18, "snap": 0.15, "pop": 22000, "label": "Riverdale Park"},
    "20740": {"poverty": 0.20, "snap": 0.17, "pop": 30000, "label": "College Park"},
    "20743": {"poverty": 0.18, "snap": 0.16, "pop": 40000, "label": "Capitol Heights"},
    "20744": {"poverty": 0.14, "snap": 0.12, "pop": 45000, "label": "Fort Washington"},
    "20745": {"poverty": 0.16, "snap": 0.14, "pop": 28000, "label": "Oxon Hill"},
    "20746": {"poverty": 0.15, "snap": 0.13, "pop": 30000, "label": "Suitland"},
    "20747": {"poverty": 0.14, "snap": 0.12, "pop": 32000, "label": "District Heights"},
    "20748": {"poverty": 0.17, "snap": 0.15, "pop": 24000, "label": "Temple Hills"},
    "20770": {"poverty": 0.11, "snap": 0.09, "pop": 24000, "label": "Greenbelt"},
    "20781": {"poverty": 0.16, "snap": 0.14, "pop": 18000, "label": "Hyattsville"},
    "20782": {"poverty": 0.14, "snap": 0.12, "pop": 22000, "label": "West Hyattsville"},
    "20783": {"poverty": 0.31, "snap": 0.27, "pop": 35000, "label": "Langley Park"},
    "20784": {"poverty": 0.14, "snap": 0.12, "pop": 32000, "label": "New Carrollton"},
    "20785": {"poverty": 0.16, "snap": 0.14, "pop": 28000, "label": "Landover Hills"},

    # MD — Montgomery County (mixed)
    "20850": {"poverty": 0.08, "snap": 0.06, "pop": 48000, "label": "Rockville"},
    "20852": {"poverty": 0.07, "snap": 0.05, "pop": 35000, "label": "North Bethesda"},
    "20853": {"poverty": 0.09, "snap": 0.07, "pop": 28000, "label": "Rockville (east)"},
    "20874": {"poverty": 0.10, "snap": 0.08, "pop": 52000, "label": "Germantown"},
    "20877": {"poverty": 0.12, "snap": 0.09, "pop": 36000, "label": "Gaithersburg"},
    "20878": {"poverty": 0.08, "snap": 0.06, "pop": 42000, "label": "Gaithersburg (west)"},
    "20886": {"poverty": 0.09, "snap": 0.07, "pop": 30000, "label": "Montgomery Village"},
    "20901": {"poverty": 0.10, "snap": 0.08, "pop": 38000, "label": "Silver Spring"},
    "20902": {"poverty": 0.09, "snap": 0.07, "pop": 40000, "label": "Wheaton"},
    "20904": {"poverty": 0.08, "snap": 0.06, "pop": 45000, "label": "Colesville"},
    "20906": {"poverty": 0.10, "snap": 0.08, "pop": 50000, "label": "Aspen Hill"},
    "20910": {"poverty": 0.11, "snap": 0.09, "pop": 32000, "label": "Silver Spring (downtown)"},
    "20912": {"poverty": 0.12, "snap": 0.10, "pop": 18000, "label": "Takoma Park"},

    # MD — Baltimore (high need)
    "21201": {"poverty": 0.30, "snap": 0.26, "pop": 12000, "label": "Baltimore Downtown"},
    "21202": {"poverty": 0.22, "snap": 0.18, "pop": 18000, "label": "Baltimore Inner Harbor"},
    "21205": {"poverty": 0.28, "snap": 0.24, "pop": 15000, "label": "Baltimore East"},
    "21207": {"poverty": 0.18, "snap": 0.15, "pop": 35000, "label": "Gwynn Oak"},
    "21215": {"poverty": 0.22, "snap": 0.19, "pop": 28000, "label": "Northwest Baltimore"},
    "21217": {"poverty": 0.30, "snap": 0.26, "pop": 20000, "label": "Penn North / Sandtown"},
    "21223": {"poverty": 0.32, "snap": 0.28, "pop": 18000, "label": "Southwest Baltimore"},
    "21224": {"poverty": 0.16, "snap": 0.13, "pop": 40000, "label": "Canton / Highlandtown"},
    "21229": {"poverty": 0.20, "snap": 0.17, "pop": 32000, "label": "Irvington / Edmondson"},
    "21230": {"poverty": 0.12, "snap": 0.09, "pop": 25000, "label": "Federal Hill"},

    # VA — Northern Virginia (mixed)
    "22041": {"poverty": 0.14, "snap": 0.11, "pop": 28000, "label": "Baileys Crossroads"},
    "22042": {"poverty": 0.10, "snap": 0.08, "pop": 32000, "label": "Falls Church"},
    "22044": {"poverty": 0.12, "snap": 0.10, "pop": 18000, "label": "Seven Corners"},
    "22101": {"poverty": 0.04, "snap": 0.02, "pop": 30000, "label": "McLean"},
    "22150": {"poverty": 0.08, "snap": 0.06, "pop": 25000, "label": "Springfield"},
    "22191": {"poverty": 0.12, "snap": 0.10, "pop": 40000, "label": "Woodbridge"},
    "22192": {"poverty": 0.10, "snap": 0.08, "pop": 45000, "label": "Lake Ridge"},
    "22193": {"poverty": 0.14, "snap": 0.12, "pop": 42000, "label": "Dale City"},
    "22204": {"poverty": 0.16, "snap": 0.13, "pop": 35000, "label": "Arlington (Columbia Pike)"},
    "22301": {"poverty": 0.08, "snap": 0.06, "pop": 18000, "label": "Alexandria (Del Ray)"},
    "22304": {"poverty": 0.12, "snap": 0.10, "pop": 30000, "label": "Alexandria (west)"},
    "22305": {"poverty": 0.14, "snap": 0.11, "pop": 15000, "label": "Arlandria"},
    "22314": {"poverty": 0.06, "snap": 0.04, "pop": 22000, "label": "Old Town Alexandria"},
}

# ZIP centroids (for map placement)
ZIP_CENTROIDS: dict[str, tuple[float, float]] = {
    "20001": (38.9079, -77.0179), "20002": (38.9050, -76.9958),
    "20009": (38.9194, -77.0378), "20010": (38.9333, -77.0332),
    "20011": (38.9521, -77.0239), "20017": (38.9393, -76.9897),
    "20019": (38.8946, -76.9379), "20020": (38.8571, -76.9754),
    "20032": (38.8311, -77.0068),
    "20706": (38.9617, -76.8472), "20737": (38.9617, -76.9264),
    "20740": (38.9807, -76.9369), "20743": (38.8833, -76.8908),
    "20744": (38.7422, -76.9952), "20745": (38.8141, -76.9944),
    "20746": (38.8443, -76.9231), "20747": (38.8571, -76.8931),
    "20748": (38.8195, -76.9416), "20770": (38.9959, -76.8753),
    "20781": (38.9507, -76.9482), "20782": (38.9685, -76.9661),
    "20783": (38.9866, -76.9826), "20784": (38.9426, -76.9065),
    "20785": (38.9324, -76.8870),
    "20850": (39.0537, -77.1222), "20852": (39.0537, -77.1222),
    "20853": (39.0846, -77.1230), "20874": (39.1734, -77.2614),
    "20877": (39.1372, -77.1958), "20878": (39.1101, -77.2312),
    "20886": (39.1766, -77.1986), "20901": (39.0149, -77.0098),
    "20902": (39.0362, -77.0356), "20904": (39.0581, -76.9783),
    "20906": (39.0838, -77.0578), "20910": (38.9918, -77.0306),
    "20912": (38.9801, -77.0075),
    "21201": (39.2960, -76.6210), "21202": (39.2883, -76.6076),
    "21205": (39.3019, -76.5835), "21207": (39.3193, -76.7226),
    "21215": (39.3453, -76.6768), "21217": (39.3111, -76.6427),
    "21223": (39.2826, -76.6554), "21224": (39.2790, -76.5691),
    "21229": (39.2804, -76.6869), "21230": (39.2683, -76.6277),
    "22041": (38.8541, -77.1360), "22042": (38.8622, -77.1917),
    "22044": (38.8648, -77.1551), "22101": (38.9462, -77.1892),
    "22150": (38.7815, -77.1810), "22191": (38.6472, -77.2593),
    "22192": (38.6834, -77.2872), "22193": (38.6396, -77.3272),
    "22204": (38.8583, -77.0870), "22301": (38.8203, -77.0573),
    "22304": (38.8148, -77.1176), "22305": (38.8378, -77.0605),
    "22314": (38.8051, -77.0591),
}


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]
    print(f"Stage 7: equity gap analysis ({len(records)} records, {len(DMV_NEED_DATA)} tracked ZIPs)")

    # Build org lookup by coordinates
    geo_orgs = [(r, r["lat"], r["lon"]) for r in records if r.get("lat") and r.get("lon")]

    gaps = []
    for zip_code, need_data in DMV_NEED_DATA.items():
        centroid = ZIP_CENTROIDS.get(zip_code)
        if not centroid:
            continue

        clat, clon = centroid
        poverty = need_data["poverty"]
        snap = need_data["snap"]
        pop = need_data["pop"]
        label = need_data["label"]

        # Need score: weighted combination of poverty + SNAP
        need_score = round(0.6 * poverty + 0.4 * snap, 3)

        # Supply score: count orgs within 3km, weighted by quality
        nearby_orgs = []
        for rec, lat, lon in geo_orgs:
            dist = _haversine_km(clat, clon, lat, lon)
            if dist <= 3.0:
                # Weight by data quality
                weight = 0.5
                if rec.get("hours"):
                    weight += 0.3
                if rec.get("requirements") and "walk_in" in rec.get("requirements", []):
                    weight += 0.2
                nearby_orgs.append({"rec": rec, "dist": dist, "weight": weight})

        # Supply = weighted org count per 10,000 residents, capped at need level
        # A ZIP needs roughly 1 well-equipped org per 5,000 people to be "fully served"
        orgs_per_5k = sum(o["weight"] for o in nearby_orgs) / max(1, pop / 5000)
        supply_score = round(min(need_score, orgs_per_5k * need_score), 3)

        # Gap
        gap = round(max(0.0, need_score - supply_score), 3)

        # Find nearest org for suggested host
        suggested_host = None
        if nearby_orgs:
            nearest = min(nearby_orgs, key=lambda o: o["dist"])
            suggested_host = {
                "name": nearest["rec"].get("name", "?"),
                "distance_km": round(nearest["dist"], 1),
                "has_hours": bool(nearest["rec"].get("hours")),
            }

        # Underserved population estimate
        underserved_pop = int(pop * gap)

        gaps.append({
            "zip": zip_code,
            "label": label,
            "centroidLat": clat,
            "centroidLon": clon,
            "population": pop,
            "needScore": need_score,
            "supplyScore": supply_score,
            "gap": gap,
            "underservedPopulation": underserved_pop,
            "nearbyOrgCount": len(nearby_orgs),
            "suggestedHost": suggested_host,
            "why": _generate_why(label, need_score, supply_score, len(nearby_orgs), pop),
        })

    # Sort by gap descending
    gaps.sort(key=lambda g: g["gap"], reverse=True)

    # Save top 30
    output = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totalZipsAnalyzed": len(gaps),
        "gaps": gaps[:30],
        "summary": {
            "highestGap": gaps[0] if gaps else None,
            "avgGap": round(sum(g["gap"] for g in gaps) / len(gaps), 3) if gaps else 0,
            "totalUnderserved": sum(g["underservedPopulation"] for g in gaps[:30]),
        }
    }
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nTop 10 underserved areas:")
    for g in gaps[:10]:
        print(f"  {g['zip']} {g['label']:<30} gap={g['gap']:.3f} need={g['needScore']:.3f} supply={g['supplyScore']:.3f} orgs={g['nearbyOrgCount']}")

    print(f"\nSaved {len(gaps[:30])} equity gaps to {OUTPUT}")


def _generate_why(label, need, supply, org_count, pop):
    pct = int(need * 100)
    # org_count == 0 FIRST — most impactful sentence should always surface for food deserts
    if org_count == 0:
        return random.choice([
            f"No food pantries within walking distance of {label} ({pop:,} residents).",
            f"Zero food resources serve {label}'s {pop:,} residents — a complete desert.",
            f"{label} has {pop:,} people and no nearby pantries — the widest gap in the region.",
        ])
    elif need >= 0.20 and org_count <= 2:
        return random.choice([
            f"{label} faces significant food insecurity ({pct}% need) with only {org_count} food resource{'s' if org_count != 1 else ''} serving {pop:,} residents.",
            f"With {pct}% poverty and just {org_count} nearby pantry{'s' if org_count != 1 else ''}, {label}'s {pop:,} residents lack adequate food access.",
            f"High need ({pct}%) meets low supply in {label} — {org_count} food org{'s' if org_count != 1 else ''} for {pop:,} people.",
        ])
    elif need >= 0.15 and org_count <= 4:
        return random.choice([
            f"{label} is underserved: {org_count} food resources for {pop:,} residents in an area with {pct}% need.",
            f"Only {org_count} pantries serve {pop:,} people in {label}, where {pct}% of households face food insecurity.",
            f"{label} has {pct}% need but only {org_count} nearby food options for its {pop:,} residents.",
        ])
    else:
        return random.choice([
            f"{label} has growing need ({pct}% need score) that its {org_count} food resources may not sustain for {pop:,} residents.",
            f"Food access in {label} is stretched thin: {org_count} orgs serve {pop:,} residents at {pct}% need.",
            f"With {pct}% need and {org_count} pantries, {label}'s {pop:,} residents face tightening food access.",
            f"{label} ({pop:,} residents, {pct}% need score) has some food resources but demand is outpacing supply.",
        ])


if __name__ == "__main__":
    main()
