"""
Stage 3 -- Geocode all records (lat/lon for the map).

Three tiers:
  1. CAFB records: extract lat/lon from ArcGIS raw features (free, instant)
  2. Address geocoding via Nominatim (free, 1.1s rate limit, cached)
  3. ZIP centroid fallback for records with no geocodable address

Input:  output/stage2_deduped.json
Output: output/stage3_geocoded.json

Usage:
  python scripts/stage3_geocode.py
  python scripts/stage3_geocode.py --dry-run
  python scripts/stage3_geocode.py --limit 20
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PIPELINE   = Path(__file__).resolve().parents[1]
INPUT      = PIPELINE / "output" / "stage2_deduped.json"
OUTPUT     = PIPELINE / "output" / "stage3_geocoded.json"
STATE_DIR  = PIPELINE / "state"
LOG_DIR    = PIPELINE / "logs"
GEO_CACHE  = STATE_DIR / "geocode-cache.json"
LOG_FILE   = LOG_DIR / "stage3_geocode.jsonl"
CAFB_FEAT  = PIPELINE / "output" / "cafb_raw_features.json"

for d in [STATE_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# DMV bounding box for validation
DMV_BBOX = {"lat_min": 37.5, "lat_max": 40.0, "lon_min": -78.5, "lon_max": -76.0}

# ZIP centroid fallback (major DMV ZIPs)
ZIP_CENTROIDS: dict[str, tuple[float, float]] = {
    "20001": (38.9079, -77.0179), "20002": (38.9050, -76.9958),
    "20009": (38.9194, -77.0378), "20010": (38.9333, -77.0332),
    "20011": (38.9521, -77.0239), "20017": (38.9393, -76.9897),
    "20020": (38.8571, -76.9754), "20032": (38.8311, -77.0068),
    "20706": (38.9617, -76.8472), "20737": (38.9617, -76.9264),
    "20740": (38.9807, -76.9369), "20743": (38.8833, -76.8908),
    "20744": (38.7422, -76.9952), "20770": (38.9959, -76.8753),
    "20781": (38.9507, -76.9482), "20782": (38.9685, -76.9661),
    "20783": (38.9866, -76.9826), "20784": (38.9426, -76.9065),
    "20785": (38.9324, -76.8870), "20852": (39.0537, -77.1222),
    "20853": (39.0846, -77.1230), "20854": (39.0312, -77.1870),
    "20877": (39.1372, -77.1958), "20878": (39.1101, -77.2312),
    "20895": (39.0361, -77.0699), "20901": (39.0149, -77.0098),
    "20902": (39.0362, -77.0356), "20903": (39.0083, -76.9685),
    "20904": (39.0581, -76.9783), "20906": (39.0838, -77.0578),
    "20910": (38.9918, -77.0306), "21201": (39.2960, -76.6210),
    "21215": (39.3453, -76.6768), "21229": (39.2804, -76.6869),
    "22041": (38.8541, -77.1360), "22042": (38.8622, -77.1917),
    "22044": (38.8648, -77.1551), "22101": (38.9462, -77.1892),
    "22204": (38.8583, -77.0870), "22301": (38.8203, -77.0573),
    "22314": (38.8051, -77.0591),
}


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def _jsonl_log(entry: dict):
    entry["ts"] = _ts()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _load_cache(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_cache(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

def _in_dmv(lat: float, lon: float) -> bool:
    return (DMV_BBOX["lat_min"] <= lat <= DMV_BBOX["lat_max"] and
            DMV_BBOX["lon_min"] <= lon <= DMV_BBOX["lon_max"])


# ── Tier 1: CAFB lat/lon from ArcGIS features ─────────────────────��──────────

def load_cafb_coords() -> dict[str, tuple[float, float]]:
    """Load CAFB coords keyed by org name (lowercased)."""
    coords: dict[str, tuple[float, float]] = {}
    if not CAFB_FEAT.exists():
        return coords
    try:
        features = json.loads(CAFB_FEAT.read_text(encoding="utf-8"))
        for feat in features:
            attrs = feat.get("attributes", {})
            name = (attrs.get("name") or "").strip().lower()
            lat = attrs.get("latitude")
            lon = attrs.get("longitude")
            if name and lat and lon:
                coords[name] = (float(lat), float(lon))
    except Exception:
        pass
    return coords


# ── Tier 2: Nominatim geocoding ───────────────────────────────────────────────

def geocode_nominatim(address: str, cache: dict) -> tuple[float, float] | None:
    """Geocode via Nominatim with cache. Returns (lat, lon) or None."""
    cache_key = address.lower().strip()
    if cache_key in cache:
        cached = cache[cache_key]
        if cached and "lat" in cached and "lon" in cached:
            return (cached["lat"], cached["lon"])
        return None  # cached miss or corrupted entry

    import httpx
    time.sleep(1.1)  # Nominatim rate limit

    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1,
                    "countrycodes": "us", "addressdetails": 0},
            headers={"User-Agent": "Nutrire-Pipeline/1.0 (food-resource-aggregator)"},
            timeout=10,
        )
        results = resp.json()
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            cache[cache_key] = {"lat": lat, "lon": lon}
            return (lat, lon)
    except Exception:
        pass

    cache[cache_key] = None  # cache the miss
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stage 3: geocode records")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    data = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]
    if args.limit > 0:
        records = records[:args.limit]

    total = len(records)
    already_have = sum(1 for r in records if r.get("lat") and r.get("lon"))
    print(f"Stage 3: geocoding {total} records ({already_have} already have coords)")

    if args.dry_run:
        need_geocode = sum(1 for r in records if not r.get("lat"))
        has_address = sum(1 for r in records if not r.get("lat") and r.get("address"))
        has_zip = sum(1 for r in records if not r.get("lat") and not r.get("address") and r.get("zip"))
        print(f"  Need geocoding: {need_geocode}")
        print(f"    With address (Nominatim): {has_address}")
        print(f"    ZIP only (fallback): {has_zip}")
        return

    # Tier 1: CAFB coords
    cafb_coords = load_cafb_coords()
    cafb_matched = 0
    for rec in records:
        if rec.get("lat") and rec.get("lon"):
            continue
        name_lower = (rec.get("name") or "").strip().lower()
        if name_lower in cafb_coords:
            lat, lon = cafb_coords[name_lower]
            if _in_dmv(lat, lon):
                rec["lat"] = lat
                rec["lon"] = lon
                cafb_matched += 1
                _jsonl_log({"name": rec["name"][:50], "method": "cafb_arcgis",
                           "lat": lat, "lon": lon})
    print(f"  Tier 1 (CAFB ArcGIS): {cafb_matched} records geocoded")

    # Tier 2: Nominatim
    geo_cache = _load_cache(GEO_CACHE)
    nominatim_count = 0
    nominatim_miss = 0
    need_nominatim = [r for r in records if not r.get("lat") and r.get("address")]

    print(f"  Tier 2 (Nominatim): {len(need_nominatim)} records to geocode...")
    for i, rec in enumerate(need_nominatim):
        addr = rec.get("address", "")
        city = rec.get("city", "")
        state = rec.get("state", "")
        zip_code = rec.get("zip", "")

        # Build full address for geocoding
        full_addr = addr
        if city and city.lower() not in addr.lower():
            full_addr += f", {city}"
        if state and state not in addr:
            full_addr += f", {state}"
        if zip_code and zip_code not in addr:
            full_addr += f" {zip_code}"

        result = geocode_nominatim(full_addr, geo_cache)
        if result:
            lat, lon = result
            if _in_dmv(lat, lon):
                rec["lat"] = lat
                rec["lon"] = lon
                nominatim_count += 1
                _jsonl_log({"name": rec["name"][:50], "method": "nominatim",
                           "address": full_addr[:80], "lat": lat, "lon": lon})
            else:
                nominatim_miss += 1
                _jsonl_log({"name": rec["name"][:50], "method": "nominatim",
                           "address": full_addr[:80], "status": "outside_dmv",
                           "lat": lat, "lon": lon})
        else:
            nominatim_miss += 1

        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(need_nominatim)} ({nominatim_count} success, {nominatim_miss} miss)")
            _save_cache(GEO_CACHE, geo_cache)  # periodic save

    _save_cache(GEO_CACHE, geo_cache)
    print(f"  Tier 2 (Nominatim): {nominatim_count} geocoded, {nominatim_miss} missed")

    # Tier 3: ZIP centroid fallback
    zip_count = 0
    for rec in records:
        if rec.get("lat") and rec.get("lon"):
            continue
        zip_code = rec.get("zip", "")
        if zip_code in ZIP_CENTROIDS:
            lat, lon = ZIP_CENTROIDS[zip_code]
            rec["lat"] = lat
            rec["lon"] = lon
            rec["geocode_method"] = "zip_centroid"
            zip_count += 1
            _jsonl_log({"name": rec["name"][:50], "method": "zip_centroid",
                       "zip": zip_code, "lat": lat, "lon": lon})
    print(f"  Tier 3 (ZIP centroid): {zip_count} records")

    # Summary
    total_geocoded = sum(1 for r in records if r.get("lat") and r.get("lon"))
    missing = total - total_geocoded

    # Save
    output_data = {
        "stats": {
            "total": total,
            "geocoded": total_geocoded,
            "missing": missing,
            "cafb_arcgis": cafb_matched,
            "nominatim": nominatim_count,
            "zip_centroid": zip_count,
        },
        "total": total,
        "records": records,
    }
    OUTPUT.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"GEOCODE: {total_geocoded}/{total} records have lat/lon ({missing} missing)")
    print(f"{'='*60}")
    print(f"  CAFB ArcGIS: {cafb_matched}")
    print(f"  Nominatim:   {nominatim_count}")
    print(f"  ZIP centroid: {zip_count}")
    print(f"  Still missing: {missing}")


if __name__ == "__main__":
    main()
