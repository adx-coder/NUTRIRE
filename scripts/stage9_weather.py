"""
Stage 9 -- Weather Alerts via NOAA National Weather Service (NWS).

No API key required.  The NWS API is completely free for US locations.

For every org with lat/lon we call:
  GET https://api.weather.gov/alerts/active?point={lat},{lon}

We filter for severe/relevant alerts and write them into each record's
weather_alert field, plus emit a summary file.

New fields written to each record
──────────────────────────────────
  is_outdoor          bool      (always False for pantries unless manually tagged)
  weather_alert       dict | None
    event             str       e.g. "Tornado Warning"
    level             str       "warning" | "watch" | "advisory" | "statement"
    severity          str       NWS severity: Extreme/Severe/Moderate/Minor/Unknown
    headline          str       NWS short headline
    description       str       full NWS description (first 400 chars)
    instruction       str       NWS action instruction
    valid_from        str       ISO8601 onset time
    valid_until       str       ISO8601 expiration time
    affects_travel    bool      True if alert likely disrupts travel to pantry
    nws_id            str       NWS alert ID (for deduplication)

Additional output
──────────────────
  public/data/weather-alerts.json   all active alerts keyed by org id
                                    (intended for nightly refresh, NOT baked-in)

Input:   output/stage6_transit.json   (or stage4_normalized.json with --from-stage4)
Output:  output/stage9_weather.json
         public/data/weather-alerts.json

Cache:   state/weather-cache.json     keyed by "lat_lon" 2dp (NWS grid squares
                                      are ~2.5km × 2.5km, so 2dp ≈ 1.1km precision)
         TTL: 1 hour (weather is transient)

Usage:
  python scripts/stage9_weather.py
  python scripts/stage9_weather.py --from-stage4        # if stage6 not yet run
  python scripts/stage9_weather.py --limit 20
  python scripts/stage9_weather.py --dry-run
"""

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ── Paths ─────────────────────────────────────────────────────────────────────
PIPELINE      = Path(__file__).resolve().parents[1]
INPUT_S6      = PIPELINE / "output" / "stage6_transit.json"
INPUT_S4      = PIPELINE / "output" / "stage4_normalized.json"
OUTPUT        = PIPELINE / "output" / "stage9_weather.json"
STATE_DIR     = PIPELINE / "state"
LOG_DIR       = PIPELINE / "logs"
WEATHER_CACHE = STATE_DIR / "weather-cache.json"
LOG_FILE      = LOG_DIR / "stage9_weather.jsonl"

PROJECT       = PIPELINE.parent
PUBLIC_DIR    = PROJECT / "public" / "data"
PUBLIC_ALERTS = PUBLIC_DIR / "weather-alerts.json"

for d in [STATE_DIR, LOG_DIR, OUTPUT.parent, PUBLIC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── NWS config ────────────────────────────────────────────────────────────────
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
NWS_HEADERS    = {
    "User-Agent":  "NourishNet/1.0 (food-resource-finder; contact@nourishnet.org)",
    "Accept":      "application/geo+json",
}
NWS_SLEEP      = 0.15   # seconds between NWS calls
CACHE_TTL_S    = 3600   # 1 hour cache TTL for weather data

# ── Alert classification ───────────────────────────────────────────────────────
# Events we surface (all others are ignored).
# Mapped to: (level, affects_travel)
RELEVANT_EVENTS: dict[str, tuple[str, bool]] = {
    # Life-threatening
    "Tornado Warning":              ("warning",   True),
    "Tornado Watch":                ("watch",     True),
    "Flash Flood Warning":          ("warning",   True),
    "Flash Flood Watch":            ("watch",     True),
    "Flood Warning":                ("warning",   True),
    "Flood Watch":                  ("watch",     False),
    "Severe Thunderstorm Warning":  ("warning",   True),
    "Severe Thunderstorm Watch":    ("watch",     True),
    "Winter Storm Warning":         ("warning",   True),
    "Winter Storm Watch":           ("watch",     True),
    "Blizzard Warning":             ("warning",   True),
    "Ice Storm Warning":            ("warning",   True),
    "Freezing Rain Advisory":       ("advisory",  True),
    "Wind Chill Warning":           ("warning",   True),
    "Wind Chill Advisory":          ("advisory",  False),
    "Extreme Cold Warning":         ("warning",   True),
    "Extreme Cold Watch":           ("watch",     False),
    "Heat Advisory":                ("advisory",  False),
    "Excessive Heat Warning":       ("warning",   True),
    "Excessive Heat Watch":         ("watch",     False),
    "Dense Fog Advisory":           ("advisory",  True),
    "High Wind Warning":            ("warning",   True),
    "High Wind Watch":              ("watch",     True),
    "Wind Advisory":                ("advisory",  False),
    "Tropical Storm Warning":       ("warning",   True),
    "Hurricane Warning":            ("warning",   True),
    "Hurricane Watch":              ("watch",     True),
    "Special Weather Statement":    ("statement", False),
    "Air Quality Alert":            ("advisory",  False),
}

NWS_SEVERITY_RANK = {
    "Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _log(entry: dict):
    entry["ts"] = _ts()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default

def _save_json(path: Path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

def _cache_key(lat: float, lon: float) -> str:
    # 2 decimal places ≈ 1.1km precision — matches NWS grid resolution
    return f"{round(lat, 2)}_{round(lon, 2)}"

def _cache_fresh(entry: dict) -> bool:
    fetched = entry.get("fetched_at", 0)
    return (time.time() - fetched) < CACHE_TTL_S


# ── NWS API ───────────────────────────────────────────────────────────────────

def _fetch_nws_alerts(lat: float, lon: float) -> list[dict]:
    """
    Call NWS active alerts endpoint for a coordinate.
    Returns raw list of GeoJSON feature properties, or [] on error.
    """
    try:
        time.sleep(NWS_SLEEP)
        resp = httpx.get(
            NWS_ALERTS_URL,
            params={"point": f"{round(lat, 4)},{round(lon, 4)}"},
            headers=NWS_HEADERS,
            timeout=12,
            follow_redirects=True,
        )
        if resp.status_code == 200:
            features = resp.json().get("features", [])
            return [f["properties"] for f in features if "properties" in f]
        elif resp.status_code == 404:
            # NWS returns 404 for locations outside coverage (e.g. offshore)
            return []
        else:
            _log({"event": "nws_http_error", "status": resp.status_code,
                  "lat": lat, "lon": lon})
            return []
    except Exception as exc:
        _log({"event": "nws_fetch_error", "error": str(exc)[:200],
              "lat": lat, "lon": lon})
        return []


def _pick_worst_alert(raw_alerts: list[dict]) -> dict | None:
    """
    From a list of NWS alert properties, pick the most severe relevant alert.
    Returns our normalised alert dict or None.
    """
    best: dict | None = None
    best_rank = -1

    for props in raw_alerts:
        event = props.get("event", "")
        if event not in RELEVANT_EVENTS:
            continue

        level, affects_travel = RELEVANT_EVENTS[event]
        severity = props.get("severity", "Unknown")
        rank = NWS_SEVERITY_RANK.get(severity, 0)

        # Also factor in level hierarchy for tie-breaking
        level_rank = {"warning": 3, "watch": 2, "advisory": 1, "statement": 0}
        total_rank = rank * 10 + level_rank.get(level, 0)

        if total_rank > best_rank:
            best_rank = total_rank
            # Trim description to 400 chars
            desc = (props.get("description") or "").strip()[:400]
            inst = (props.get("instruction") or "").strip()[:300]

            best = {
                "event":          event,
                "level":          level,
                "severity":       severity,
                "headline":       (props.get("headline") or "").strip()[:200],
                "description":    desc,
                "instruction":    inst,
                "valid_from":     props.get("onset", ""),
                "valid_until":    props.get("expires", "") or props.get("ends", ""),
                "affects_travel": affects_travel,
                "nws_id":         props.get("id", ""),
                "fetched_at":     _ts(),
            }

    return best


def get_weather_alert(lat: float, lon: float,
                      cache: dict) -> dict | None:
    """
    Return the worst active relevant NWS alert for (lat, lon), using cache.
    Returns None when no relevant alerts are active.
    """
    key = _cache_key(lat, lon)
    if key in cache and _cache_fresh(cache[key]):
        return cache[key].get("alert")   # None means "checked, nothing found"

    raw = _fetch_nws_alerts(lat, lon)
    alert = _pick_worst_alert(raw)

    cache[key] = {
        "fetched_at": time.time(),
        "alert":      alert,
        "raw_count":  len(raw),
    }
    return alert


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stage 9: Weather alerts (NWS)")
    parser.add_argument("--from-stage4", action="store_true",
                        help="Read from stage4_normalized.json instead of stage6")
    parser.add_argument("--limit",   type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    input_path = INPUT_S4 if args.from_stage4 else INPUT_S6
    if not input_path.exists():
        # Auto-fallback
        input_path = INPUT_S4 if INPUT_S6.exists() is False else INPUT_S6
    print(f"  Reading from: {input_path.name}")

    data    = json.loads(input_path.read_text(encoding="utf-8"))
    records = data["records"]
    if args.limit > 0:
        records = records[:args.limit]

    total    = len(records)
    with_geo = sum(1 for r in records if r.get("lat") and r.get("lon"))
    print(f"\nStage 9: weather alerts for {total} records ({with_geo} have lat/lon)")
    print(f"  NWS API: no key required — free US government data")
    print(f"  Cache TTL: {CACHE_TTL_S // 60} minutes")

    if args.dry_run:
        print("  [DRY RUN] No API calls will be made.")
        return

    cache         = _load_json(WEATHER_CACHE, {})
    cache_hits    = 0
    alerts_found  = 0
    travel_alerts = 0
    no_geo        = 0
    api_calls     = 0

    # Per-org public summary (org_id → alert | null)
    public_summary: dict[str, dict | None] = {}

    for i, rec in enumerate(records):
        lat = rec.get("lat")
        lon = rec.get("lon")
        if not lat or not lon:
            no_geo += 1
            continue

        key = _cache_key(lat, lon)
        was_cached = (key in cache and _cache_fresh(cache[key]))

        alert = get_weather_alert(lat, lon, cache)

        if not was_cached:
            api_calls += 1

        rec["weather_alert"] = alert
        # is_outdoor stays False for pantries (indoors) — frontend can override
        # when we have outdoor distribution events

        org_id = rec.get("id", rec.get("name", f"org_{i}"))
        public_summary[org_id] = alert

        if alert:
            alerts_found += 1
            if alert.get("affects_travel"):
                travel_alerts += 1
            _log({
                "event":   "alert_found",
                "org":     rec.get("name", "")[:50],
                "alert":   alert["event"],
                "level":   alert["level"],
                "severity": alert["severity"],
            })

        # Progress
        if (i + 1) % 50 == 0:
            pct = round((i + 1) / total * 100)
            print(f"  {i+1}/{total} ({pct}%)  "
                  f"alerts={alerts_found}  cache_hits={cache_hits}  "
                  f"api_calls={api_calls}")
            _save_json(WEATHER_CACHE, cache)

    _save_json(WEATHER_CACHE, cache)

    # Write stage output
    output_data = {
        "stats": {
            "total":          total,
            "with_geo":       with_geo,
            "alerts_found":   alerts_found,
            "travel_alerts":  travel_alerts,
            "cache_hits":     cache_hits,
            "api_calls":      api_calls,
            "no_geo":         no_geo,
        },
        "total":   total,
        "records": records,
    }
    OUTPUT.write_text(json.dumps(output_data, indent=2, ensure_ascii=False),
                      encoding="utf-8")

    # Write public alert summary (refreshable independently)
    public_out = {
        "generatedAt":    _ts(),
        "cache_ttl_mins": CACHE_TTL_S // 60,
        "total_alerts":   alerts_found,
        "travel_alerts":  travel_alerts,
        "alerts":         public_summary,   # {org_id: alert_dict | null}
    }
    PUBLIC_ALERTS.write_text(json.dumps(public_out, indent=2, ensure_ascii=False),
                             encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"WEATHER: {alerts_found} active alerts found across {with_geo} geocoded orgs")
    print(f"{'='*60}")
    print(f"  Travel-disrupting alerts:  {travel_alerts}")
    print(f"  API calls made:            {api_calls}")
    print(f"  Cache hits:                {cache_hits}")
    print(f"  No geo (skipped):          {no_geo}")
    print(f"  Stage output:              {OUTPUT}")
    print(f"  Public alerts JSON:        {PUBLIC_ALERTS}")
    if alerts_found == 0:
        print(f"\n  (No active alerts right now — this is normal on clear days.)")


if __name__ == "__main__":
    main()
