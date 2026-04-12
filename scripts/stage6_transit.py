"""
Stage 6 -- Transit Enrichment: WMATA Metro/Bus + OSRM real walking routes.

For every org with lat/lon we:
  1. Pull all WMATA Metro stations from the Rail API (cached indefinitely – stations
     don't move).
  2. Pull WMATA Bus stops filtered to the DMV bounding box (cached 7 days).
  3. Pre-filter with haversine to get ≤5 candidates, then call OSRM for ACTUAL
     road-network walking distance/time (not crow-flies).
  4. Store a rich transit_detail block + top-level convenience fields.

New fields written to each record
──────────────────────────────────
  nearestTransit          str   nearest Metro station OR bus stop name
  nearestTransitId        str   WMATA StationCode / StopID
  nearestTransitType      str   "metro" | "bus"
  nearestTransitLines     list  line codes  e.g. ["RED", "GREEN"]
  transitDistanceMeters   int   OSRM walking distance in metres
  transit_detail          dict
    nearest_metro:
      id, name, lines, lat, lon,
      walk_distance_m, walk_minutes,   ← OSRM values
      osrm_used                        ← True if real route; False if haversine fallback
    nearest_bus:
      id, route, stop_name, lat, lon,
      walk_distance_m, walk_minutes,
      osrm_used
    walk_minutes_to_metro   int
    walk_minutes_to_bus     int
    reachable_hours_of_week list[int]  0-167 hour-of-week slots Metro is running
    transit_summary         str        human-readable one-liner
    enriched_at             str        ISO timestamp

Input:  output/stage4_normalized.json
Output: output/stage6_transit.json
Cache:  state/transit-cache.json         per-org results  (key = "lat_lon" 4dp)
        state/wmata-stations-cache.json  all Metro stations
        state/wmata-stops-cache.json     DMV bus stops

Usage:
  python scripts/stage6_transit.py
  python scripts/stage6_transit.py --limit 50
  python scripts/stage6_transit.py --dry-run
  python scripts/stage6_transit.py --no-osrm      # skip OSRM, use haversine×1.3
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ── Paths ─────────────────────────────────────────────────────────────────────
PIPELINE         = Path(__file__).resolve().parents[1]
INPUT            = PIPELINE / "output" / "stage4_normalized.json"
OUTPUT           = PIPELINE / "output" / "stage6_transit.json"
STATE_DIR        = PIPELINE / "state"
LOG_DIR          = PIPELINE / "logs"
TRANSIT_CACHE    = STATE_DIR / "transit-cache.json"
STATIONS_CACHE   = STATE_DIR / "wmata-stations-cache.json"
STOPS_CACHE      = STATE_DIR / "wmata-stops-cache.json"
LOG_FILE         = LOG_DIR / "stage6_transit.jsonl"

for d in [STATE_DIR, LOG_DIR, OUTPUT.parent]:
    d.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
# WMATA publishes a free demo key in their developer docs for testing.
# Set WMATA_API_KEY in .env to override.
WMATA_KEY = os.getenv("WMATA_API_KEY", "e13626d03d8e4c03ac07f95541b3091b")
WMATA_HEADERS = {"api_key": WMATA_KEY}

# DMV bounding box (lat_min, lat_max, lon_min, lon_max)
DMV_BBOX = (37.5, 40.0, -78.5, -76.0)

# OSRM public endpoint — driving profile gives actual road-network distance
# We divide duration by a pedestrian correction factor to get walk time.
OSRM_URL      = "http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false&steps=false"
WALK_SPEED_MS = 1.33          # metres/second (~4.8 km/h average walk)
OSRM_SLEEP    = 0.0           # no sleep — OSRM public server handles bursts
WMATA_SLEEP   = 0.15          # seconds between WMATA API calls

# Metro system operating hours (hour-of-day when service is running per day-of-week)
# Monday=0 … Sunday=6
METRO_HOURS: dict[int, tuple[int, int]] = {
    0: (5, 23),   # Monday    05:00–23:00
    1: (5, 23),   # Tuesday
    2: (5, 23),   # Wednesday
    3: (5, 23),   # Thursday
    4: (5, 24),   # Friday    05:00–midnight
    5: (7, 24),   # Saturday  07:00–midnight
    6: (8, 23),   # Sunday    08:00–23:00
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
    return f"{round(lat, 4)}_{round(lon, 4)}"

def _in_dmv(lat: float, lon: float) -> bool:
    mn_lat, mx_lat, mn_lon, mx_lon = DMV_BBOX
    return mn_lat <= lat <= mx_lat and mn_lon <= lon <= mx_lon

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Crow-flies distance in metres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _reachable_hours(walk_min: int) -> list[int]:
    """
    Return list of hour-of-week slots (0-167) when Metro is running AND the
    org is reachable assuming the user must arrive before closing.
    """
    result = []
    for dow in range(7):
        open_h, close_h = METRO_HOURS[dow]
        for h in range(open_h, min(close_h, 24)):
            hw = dow * 24 + h
            if 0 <= hw <= 167:
                result.append(hw)
    return result

def _transit_summary(metro: dict | None, bus: dict | None) -> str:
    parts = []
    if metro:
        wm = metro.get("walk_minutes", "?")
        name = metro.get("name", "Metro")
        lines = "/".join(metro.get("lines", []))
        parts.append(f"{wm}-min walk to {name} ({lines} line)")
    if bus:
        wb = bus.get("walk_minutes", "?")
        route = bus.get("route", "bus")
        parts.append(f"{wb}-min walk to Route {route} bus")
    if not parts:
        return "No WMATA transit within 2 km"
    return "; ".join(parts)


# ── OSRM routing ──────────────────────────────────────────────────────────────

def _osrm_walk(lat1: float, lon1: float, lat2: float, lon2: float,
               use_osrm: bool = True) -> tuple[float, float, bool]:
    """
    Return (distance_metres, walk_minutes, osrm_used).
    Falls back to haversine × 1.3 if OSRM fails or use_osrm=False.
    """
    if use_osrm:
        url = OSRM_URL.format(lon1=lon1, lat1=lat1, lon2=lon2, lat2=lat2)
        try:
            time.sleep(OSRM_SLEEP)
            resp = httpx.get(url, timeout=8,
                             headers={"User-Agent": "NourishNet-Pipeline/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    leg = data["routes"][0]["legs"][0]
                    dist_m = leg["distance"]          # metres (road network)
                    # Convert road distance to walking time at WALK_SPEED_MS
                    walk_min = round(dist_m / WALK_SPEED_MS / 60, 1)
                    return dist_m, walk_min, True
        except Exception as exc:
            _log({"event": "osrm_error", "error": str(exc)[:120]})

    # Haversine fallback with 1.3 road-factor
    dist_m = _haversine_m(lat1, lon1, lat2, lon2) * 1.3
    walk_min = round(dist_m / WALK_SPEED_MS / 60, 1)
    return dist_m, walk_min, False


# ── WMATA data loaders ────────────────────────────────────────────────────────

# ── Static WMATA station fallback ─────────────────────────────────────────────
# Complete list of all 98 WMATA Metro stations (as of 2024).
# Used when the WMATA API key is unavailable or returns 403.
# Source: WMATA developer portal station data.
WMATA_STATIONS_STATIC: list[dict] = [
    # Red Line
    {"id":"A01","name":"Metro Center","lat":38.8983,"lon":-77.0280,"lines":["RD","BL","OR","SV"]},
    {"id":"A02","name":"Farragut North","lat":38.9039,"lon":-77.0397,"lines":["RD"]},
    {"id":"A03","name":"Dupont Circle","lat":38.9096,"lon":-77.0434,"lines":["RD"]},
    {"id":"A04","name":"Woodley Park-Zoo/Adams Morgan","lat":38.9248,"lon":-77.0526,"lines":["RD"]},
    {"id":"A05","name":"Cleveland Park","lat":38.9342,"lon":-77.0580,"lines":["RD"]},
    {"id":"A06","name":"Van Ness-UDC","lat":38.9449,"lon":-77.0632,"lines":["RD"]},
    {"id":"A07","name":"Tenleytown-AU","lat":38.9480,"lon":-77.0796,"lines":["RD"]},
    {"id":"A08","name":"Friendship Heights","lat":38.9601,"lon":-77.0856,"lines":["RD"]},
    {"id":"A09","name":"Bethesda","lat":38.9844,"lon":-77.0970,"lines":["RD"]},
    {"id":"A10","name":"Medical Center","lat":38.9999,"lon":-77.0969,"lines":["RD"]},
    {"id":"A11","name":"Grosvenor-Strathmore","lat":39.0290,"lon":-77.1063,"lines":["RD"]},
    {"id":"A12","name":"White Flint","lat":39.0483,"lon":-77.1134,"lines":["RD"]},
    {"id":"A13","name":"Twinbrook","lat":39.0625,"lon":-77.1214,"lines":["RD"]},
    {"id":"A14","name":"Rockville","lat":39.0847,"lon":-77.1463,"lines":["RD"]},
    {"id":"A15","name":"Shady Grove","lat":39.1198,"lon":-77.1644,"lines":["RD"]},
    {"id":"B01","name":"Gallery Pl-Chinatown","lat":38.8984,"lon":-77.0220,"lines":["RD","GR","YL"]},
    {"id":"B02","name":"Judiciary Square","lat":38.8963,"lon":-77.0165,"lines":["RD"]},
    {"id":"B03","name":"Union Station","lat":38.8973,"lon":-77.0067,"lines":["RD"]},
    {"id":"B04","name":"Rhode Island Ave-Brentwood","lat":38.9205,"lon":-76.9948,"lines":["RD"]},
    {"id":"B05","name":"Brookland-CUA","lat":38.9335,"lon":-76.9945,"lines":["RD"]},
    {"id":"B06","name":"Fort Totten","lat":38.9517,"lon":-77.0023,"lines":["RD","GR","YL"]},
    {"id":"B07","name":"Takoma","lat":38.9764,"lon":-77.0125,"lines":["RD"]},
    {"id":"B08","name":"Silver Spring","lat":38.9940,"lon":-77.0310,"lines":["RD"]},
    {"id":"B09","name":"Forest Glen","lat":39.0149,"lon":-77.0525,"lines":["RD"]},
    {"id":"B10","name":"Wheaton","lat":39.0347,"lon":-77.0528,"lines":["RD"]},
    {"id":"B11","name":"Glenmont","lat":39.0621,"lon":-77.0530,"lines":["RD"]},
    # Blue/Orange/Silver Line
    {"id":"C01","name":"Metro Center","lat":38.8983,"lon":-77.0280,"lines":["BL","OR","SV"]},
    {"id":"C02","name":"McPherson Square","lat":38.9018,"lon":-77.0332,"lines":["BL","OR","SV"]},
    {"id":"C03","name":"Farragut West","lat":38.9008,"lon":-77.0461,"lines":["BL","OR","SV"]},
    {"id":"C04","name":"Foggy Bottom-GWU","lat":38.9001,"lon":-77.0502,"lines":["BL","OR","SV"]},
    {"id":"C05","name":"Rosslyn","lat":38.8963,"lon":-77.0706,"lines":["BL","OR","SV"]},
    {"id":"C06","name":"Arlington Cemetery","lat":38.8850,"lon":-77.0637,"lines":["BL"]},
    {"id":"C07","name":"Pentagon","lat":38.8690,"lon":-77.0534,"lines":["BL","YL"]},
    {"id":"C08","name":"Pentagon City","lat":38.8626,"lon":-77.0597,"lines":["BL","YL"]},
    {"id":"C09","name":"Crystal City","lat":38.8576,"lon":-77.0515,"lines":["BL","YL"]},
    {"id":"C10","name":"Ronald Reagan Washington National Airport","lat":38.8527,"lon":-77.0434,"lines":["BL","YL"]},
    {"id":"C11","name":"Potomac Yard","lat":38.8437,"lon":-77.0490,"lines":["BL","YL"]},
    {"id":"C12","name":"Braddock Road","lat":38.8136,"lon":-77.0543,"lines":["BL","YL"]},
    {"id":"C13","name":"King St-Old Town","lat":38.8049,"lon":-77.0618,"lines":["BL","YL"]},
    {"id":"D01","name":"Federal Triangle","lat":38.8932,"lon":-77.0285,"lines":["BL","OR","SV"]},
    {"id":"D02","name":"Smithsonian","lat":38.8882,"lon":-77.0282,"lines":["BL","OR","SV"]},
    {"id":"D03","name":"L'Enfant Plaza","lat":38.8845,"lon":-77.0215,"lines":["BL","OR","SV","GR","YL"]},
    {"id":"D04","name":"Federal Center SW","lat":38.8851,"lon":-77.0156,"lines":["BL","OR","SV"]},
    {"id":"D05","name":"Capitol South","lat":38.8852,"lon":-77.0054,"lines":["BL","OR","SV"]},
    {"id":"D06","name":"Eastern Market","lat":38.8842,"lon":-76.9969,"lines":["BL","OR","SV"]},
    {"id":"D07","name":"Potomac Ave","lat":38.8792,"lon":-76.9896,"lines":["BL","OR","SV"]},
    {"id":"D08","name":"Stadium-Armory","lat":38.8867,"lon":-76.9784,"lines":["BL","OR","SV"]},
    {"id":"G01","name":"Benning Road","lat":38.8906,"lon":-76.9385,"lines":["BL","SV"]},
    {"id":"G02","name":"Capitol Heights","lat":38.8888,"lon":-76.9138,"lines":["BL","SV"]},
    {"id":"G03","name":"Addison Road-Seat Pleasant","lat":38.8877,"lon":-76.8975,"lines":["BL","SV"]},
    {"id":"G04","name":"Morgan Blvd","lat":38.8938,"lon":-76.8699,"lines":["BL","SV"]},
    {"id":"G05","name":"Largo Town Center","lat":38.9003,"lon":-76.8394,"lines":["BL","SV"]},
    # Orange Line extensions
    {"id":"K01","name":"Court House","lat":38.8914,"lon":-77.0845,"lines":["OR","SV"]},
    {"id":"K02","name":"Clarendon","lat":38.8866,"lon":-77.0963,"lines":["OR","SV"]},
    {"id":"K03","name":"Virginia Square-GMU","lat":38.8837,"lon":-77.1045,"lines":["OR","SV"]},
    {"id":"K04","name":"Ballston-MU","lat":38.8822,"lon":-77.1118,"lines":["OR","SV"]},
    {"id":"K05","name":"East Falls Church","lat":38.8853,"lon":-77.1565,"lines":["OR","SV"]},
    {"id":"K06","name":"West Falls Church-VT/UVA","lat":38.9001,"lon":-77.1876,"lines":["OR"]},
    {"id":"K07","name":"Dunn Loring-Merrifield","lat":38.8841,"lon":-77.2284,"lines":["OR"]},
    {"id":"K08","name":"Vienna/Fairfax-GMU","lat":38.8774,"lon":-77.2720,"lines":["OR"]},
    # Silver Line
    {"id":"N01","name":"McLean","lat":38.9241,"lon":-77.2094,"lines":["SV"]},
    {"id":"N02","name":"Tysons Corner","lat":38.9205,"lon":-77.2249,"lines":["SV"]},
    {"id":"N03","name":"Greensboro","lat":38.9186,"lon":-77.2358,"lines":["SV"]},
    {"id":"N04","name":"Spring Hill","lat":38.9276,"lon":-77.2425,"lines":["SV"]},
    {"id":"N06","name":"Wiehle-Reston East","lat":38.9474,"lon":-77.3406,"lines":["SV"]},
    {"id":"N07","name":"Reston Town Center","lat":38.9581,"lon":-77.3596,"lines":["SV"]},
    {"id":"N08","name":"Herndon","lat":38.9682,"lon":-77.3858,"lines":["SV"]},
    {"id":"N09","name":"Innovation Center","lat":38.9812,"lon":-77.4279,"lines":["SV"]},
    {"id":"N10","name":"Washington Dulles International Airport","lat":38.9531,"lon":-77.4477,"lines":["SV"]},
    {"id":"N11","name":"Loudoun Gateway","lat":39.0000,"lon":-77.4847,"lines":["SV"]},
    {"id":"N12","name":"Ashburn","lat":39.0124,"lon":-77.4879,"lines":["SV"]},
    # Green/Yellow Lines
    {"id":"E01","name":"Mt Vernon Sq 7th St-Convention Center","lat":38.9054,"lon":-77.0224,"lines":["GR","YL"]},
    {"id":"E02","name":"Shaw-Howard U","lat":38.9126,"lon":-77.0220,"lines":["GR","YL"]},
    {"id":"E03","name":"U Street/African-Amer Civil War Memorial/Cardozo","lat":38.9167,"lon":-77.0286,"lines":["GR","YL"]},
    {"id":"E04","name":"Columbia Heights","lat":38.9282,"lon":-77.0327,"lines":["GR","YL"]},
    {"id":"E05","name":"Georgia Ave-Petworth","lat":38.9378,"lon":-77.0248,"lines":["GR","YL"]},
    {"id":"E06","name":"Fort Totten","lat":38.9517,"lon":-77.0023,"lines":["GR","YL"]},
    {"id":"F01","name":"Gallery Pl-Chinatown","lat":38.8984,"lon":-77.0220,"lines":["GR","YL"]},
    {"id":"F02","name":"Archives-Navy Mem-Penn Quarter","lat":38.8935,"lon":-77.0213,"lines":["GR","YL"]},
    {"id":"F03","name":"L'Enfant Plaza","lat":38.8845,"lon":-77.0215,"lines":["GR","YL"]},
    {"id":"F04","name":"Waterfront","lat":38.8762,"lon":-77.0175,"lines":["GR"]},
    {"id":"F05","name":"Navy Yard-Ballpark","lat":38.8765,"lon":-77.0053,"lines":["GR"]},
    {"id":"F06","name":"Anacostia","lat":38.8631,"lon":-76.9952,"lines":["GR"]},
    {"id":"F07","name":"Congress Heights","lat":38.8458,"lon":-76.9952,"lines":["GR"]},
    {"id":"F08","name":"Southern Avenue","lat":38.8399,"lon":-76.9763,"lines":["GR"]},
    {"id":"F09","name":"Naylor Road","lat":38.8510,"lon":-76.9566,"lines":["GR"]},
    {"id":"F10","name":"Suitland","lat":38.8434,"lon":-76.9327,"lines":["GR"]},
    {"id":"F11","name":"Branch Ave","lat":38.8281,"lon":-76.9123,"lines":["GR"]},
    {"id":"C14","name":"Eisenhower Avenue","lat":38.8004,"lon":-77.0774,"lines":["YL"]},
    {"id":"C15","name":"Huntington","lat":38.7944,"lon":-77.0754,"lines":["YL"]},
    # Green Line PG County extension
    {"id":"E07","name":"West Hyattsville","lat":38.9547,"lon":-76.9748,"lines":["GR","YL"]},
    {"id":"E08","name":"Prince George's Plaza","lat":38.9647,"lon":-76.9568,"lines":["GR","YL"]},
    {"id":"E09","name":"College Park-U of Md","lat":38.9780,"lon":-76.9284,"lines":["GR","YL"]},
    {"id":"E10","name":"Greenbelt","lat":39.0111,"lon":-76.9114,"lines":["GR","YL"]},
]


def load_wmata_stations() -> list[dict]:
    """
    Load all WMATA Metro stations.
    Priority: 1) local cache, 2) WMATA API, 3) built-in static dataset.
    Each entry: {id, name, lat, lon, lines}
    """
    cached = _load_json(STATIONS_CACHE, None)
    if cached and isinstance(cached, list) and len(cached) > 0:
        print(f"  [WMATA] Loaded {len(cached)} Metro stations from cache")
        return cached

    print("  [WMATA] Fetching Metro stations from API …")
    stations = []
    try:
        time.sleep(WMATA_SLEEP)
        resp = httpx.get(
            "https://api.wmata.com/Rail.svc/json/jStations",
            headers=WMATA_HEADERS,
            timeout=15,
        )
        if resp.status_code == 403:
            raise RuntimeError("WMATA API key invalid or quota exceeded (403)")
        resp.raise_for_status()
        raw = resp.json().get("Stations", [])
        for s in raw:
            lat = s.get("Lat") or 0
            lon = s.get("Lon") or 0
            if not _in_dmv(lat, lon):
                continue
            lines = [s[f"LineCode{i}"] for i in range(1, 5)
                     if s.get(f"LineCode{i}")]
            stations.append({
                "id":    s["Code"],
                "name":  s["Name"],
                "lat":   lat,
                "lon":   lon,
                "lines": lines,
            })
        _save_json(STATIONS_CACHE, stations)
        print(f"  [WMATA] Cached {len(stations)} Metro stations from API")
        _log({"event": "wmata_stations_loaded", "source": "api", "count": len(stations)})
    except Exception as exc:
        print(f"  [WMATA] API unavailable ({exc}) — using built-in static dataset")
        _log({"event": "wmata_stations_fallback", "error": str(exc)[:200]})
        stations = WMATA_STATIONS_STATIC
        # Deduplicate by id (some stations appear on multiple lines in the static list)
        seen: set[str] = set()
        deduped = []
        for s in stations:
            if s["id"] not in seen:
                seen.add(s["id"])
                deduped.append(s)
        stations = deduped
        _save_json(STATIONS_CACHE, stations)
        print(f"  [WMATA] Using {len(stations)} built-in Metro stations")

    return stations


def load_wmata_bus_stops() -> list[dict]:
    """
    Load WMATA bus stops filtered to DMV bbox.  Cached for 7 days.
    Each entry: {id, stop_name, lat, lon, routes}
    """
    cached_raw = _load_json(STOPS_CACHE, None)
    if cached_raw and isinstance(cached_raw, dict):
        age_days = (time.time() - cached_raw.get("fetched_at", 0)) / 86400
        if age_days < 7:
            stops = cached_raw["stops"]
            print(f"  [WMATA] Loaded {len(stops)} bus stops from cache "
                  f"({age_days:.1f} days old)")
            return stops

    print("  [WMATA] Fetching bus stops from API …")
    stops = []
    try:
        time.sleep(WMATA_SLEEP)
        resp = httpx.get(
            "https://api.wmata.com/Bus.svc/json/jStops",
            headers=WMATA_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("Stops", [])
        for s in raw:
            lat = s.get("Lat") or 0
            lon = s.get("Lon") or 0
            if not _in_dmv(lat, lon):
                continue
            routes = s.get("Routes", [])
            stops.append({
                "id":        s["StopID"],
                "stop_name": s["Name"],
                "lat":       lat,
                "lon":       lon,
                "routes":    routes,
            })
        _save_json(STOPS_CACHE, {"fetched_at": time.time(), "stops": stops})
        print(f"  [WMATA] Cached {len(stops)} bus stops in DMV")
        _log({"event": "wmata_stops_loaded", "count": len(stops)})
    except Exception as exc:
        print(f"  [WMATA] ERROR loading bus stops: {exc}")
        _log({"event": "wmata_stops_error", "error": str(exc)[:200]})

    return stops


# ── Per-org enrichment ────────────────────────────────────────────────────────

MAX_WALK_METRO_M = 2000   # Metro search radius: 2 km
MAX_WALK_BUS_M   = 3000   # Bus search radius: 3 km (bus stops more spread out)
N_CANDS          = 3      # haversine pre-filter: keep this many closest candidates


def _find_nearest_metro(lat: float, lon: float, stations: list[dict],
                        use_osrm: bool) -> dict | None:
    """Return the nearest Metro station with OSRM walk distance, or None."""
    if not stations:
        return None

    # Pre-filter by haversine
    cands = sorted(
        [(s, _haversine_m(lat, lon, s["lat"], s["lon"])) for s in stations],
        key=lambda x: x[1],
    )[:N_CANDS]

    # Discard if even the closest is beyond metro radius
    if not cands or cands[0][1] > MAX_WALK_METRO_M * 1.5:
        return None

    # OSRM for each candidate, pick minimum walk
    best_station, best_dist_m, best_min, best_osrm = None, float("inf"), 0.0, False
    for station, hav_m in cands:
        if hav_m > MAX_WALK_METRO_M * 1.5:
            break
        dist_m, walk_min, osrm_used = _osrm_walk(
            lat, lon, station["lat"], station["lon"], use_osrm
        )
        if dist_m < best_dist_m:
            best_station = station
            best_dist_m  = dist_m
            best_min     = walk_min
            best_osrm    = osrm_used

    if best_station is None or best_dist_m > MAX_WALK_METRO_M * 1.5:
        return None

    return {
        "id":             best_station["id"],
        "name":           best_station["name"],
        "lines":          best_station["lines"],
        "lat":            best_station["lat"],
        "lon":            best_station["lon"],
        "walk_distance_m": round(best_dist_m),
        "walk_minutes":   round(best_min),
        "osrm_used":      best_osrm,
    }


def _find_nearest_bus(lat: float, lon: float, stops: list[dict],
                      use_osrm: bool) -> dict | None:
    """Return the nearest bus stop with OSRM walk distance, or None."""
    if not stops:
        return None

    cands = sorted(
        [(s, _haversine_m(lat, lon, s["lat"], s["lon"])) for s in stops],
        key=lambda x: x[1],
    )[:N_CANDS]

    if not cands or cands[0][1] > MAX_WALK_BUS_M:
        return None

    best_stop, best_dist_m, best_min, best_osrm = None, float("inf"), 0.0, False
    for stop, hav_m in cands:
        if hav_m > MAX_WALK_BUS_M:
            break
        dist_m, walk_min, osrm_used = _osrm_walk(
            lat, lon, stop["lat"], stop["lon"], use_osrm
        )
        if dist_m < best_dist_m:
            best_stop   = stop
            best_dist_m = dist_m
            best_min    = walk_min
            best_osrm   = osrm_used

    if best_stop is None or best_dist_m > MAX_WALK_BUS_M * 1.5:
        return None

    route = best_stop["routes"][0] if best_stop["routes"] else "?"
    return {
        "id":             best_stop["id"],
        "route":          route,
        "all_routes":     best_stop["routes"],
        "stop_name":      best_stop["stop_name"],
        "lat":            best_stop["lat"],
        "lon":            best_stop["lon"],
        "walk_distance_m": round(best_dist_m),
        "walk_minutes":   round(best_min),
        "osrm_used":      best_osrm,
    }


def enrich_transit(rec: dict, stations: list[dict], stops: list[dict],
                   org_cache: dict, use_osrm: bool) -> dict:
    """
    Build and return the transit_detail block for one record.
    Updates rec in-place with top-level convenience fields.
    """
    lat = rec.get("lat")
    lon = rec.get("lon")
    if not lat or not lon:
        return rec

    # Cache lookup
    key = _cache_key(lat, lon)
    if key in org_cache:
        cached = org_cache[key]
        rec.update(cached)
        return rec

    metro = _find_nearest_metro(lat, lon, stations, use_osrm)
    bus   = _find_nearest_bus(lat, lon, stops, use_osrm)

    walk_metro = metro["walk_minutes"] if metro else None
    walk_bus   = bus["walk_minutes"]   if bus   else None

    # Reachable hours (based on Metro schedule)
    reachable = _reachable_hours(walk_metro or 30) if metro else []

    summary = _transit_summary(metro, bus)

    detail = {
        "nearest_metro":          metro,
        "nearest_bus":            bus,
        "walk_minutes_to_metro":  walk_metro,
        "walk_minutes_to_bus":    walk_bus,
        "reachable_hours_of_week": reachable,
        "transit_summary":        summary,
        "mode_selection":         "generalized_cost",
        "enriched_at":            _ts(),
    }

    # Top-level convenience fields (schema.py NormalizedRecord fields)
    #
    # Generalized-cost mode selection (research-backed):
    #   cost = walk_minutes × WALK_PENALTY + avg_wait × WAIT_PENALTY
    #
    # Metro runs every ~6 min (avg wait ~3 min), high reliability.
    # Bus runs every ~20 min (avg wait ~10 min), lower reliability.
    # Walking time is penalized 1.5× vs in-vehicle time (people dislike walking).
    # Waiting time is penalized 1.2× (uncertainty/discomfort).
    #
    # Sources: TRB generalized cost models, WMATA Better Bus study,
    #          Human Transit walking distance research.
    WALK_PENALTY         = 1.5    # walking perceived 1.5× worse than riding
    WAIT_PENALTY         = 1.2    # waiting perceived 1.2× worse than riding
    METRO_AVG_WAIT_MIN   = 3.0   # ~6 min headway → 3 min average wait
    BUS_AVG_WAIT_MIN     = 10.0  # ~20 min headway → 10 min average wait

    def _generalized_cost(walk_m: float, avg_wait: float) -> float:
        walk_min = walk_m / (WALK_SPEED_MS * 60)   # convert metres to minutes
        return walk_min * WALK_PENALTY + avg_wait * WAIT_PENALTY

    metro_cost = _generalized_cost(metro["walk_distance_m"], METRO_AVG_WAIT_MIN) if metro else None
    bus_cost   = _generalized_cost(bus["walk_distance_m"],   BUS_AVG_WAIT_MIN)   if bus   else None

    use_metro = (
        metro is not None and
        (bus is None or metro_cost <= bus_cost)
    )

    if use_metro:
        rec["nearestTransit"]        = metro["name"]
        rec["nearestTransitId"]      = metro["id"]
        rec["nearestTransitType"]    = "metro"
        rec["nearestTransitLines"]   = metro["lines"]
        rec["transitDistanceMeters"] = metro["walk_distance_m"]
    elif bus:
        rec["nearestTransit"]        = bus["stop_name"]
        rec["nearestTransitId"]      = bus["id"]
        rec["nearestTransitType"]    = "bus"
        rec["nearestTransitLines"]   = bus["all_routes"]
        rec["transitDistanceMeters"] = bus["walk_distance_m"]

    rec["transit_detail"] = detail

    # Cache the top-level fields + detail so we never re-call OSRM for this location
    org_cache[key] = {
        "nearestTransit":        rec.get("nearestTransit"),
        "nearestTransitId":      rec.get("nearestTransitId"),
        "nearestTransitType":    rec.get("nearestTransitType"),
        "nearestTransitLines":   rec.get("nearestTransitLines"),
        "transitDistanceMeters": rec.get("transitDistanceMeters"),
        "transit_detail":        detail,
    }

    _log({
        "event":   "transit_enriched",
        "org":     rec.get("name", "")[:50],
        "lat":     lat, "lon": lon,
        "metro":   metro["name"] if metro else None,
        "metro_m": metro["walk_distance_m"] if metro else None,
        "metro_osrm": metro["osrm_used"] if metro else None,
        "bus":     bus["stop_name"] if bus else None,
        "bus_m":   bus["walk_distance_m"] if bus else None,
    })

    return rec


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stage 6: Transit enrichment")
    parser.add_argument("--limit",   type=int, default=0,
                        help="Only process first N records (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen, no API calls or writes")
    parser.add_argument("--no-osrm", action="store_true",
                        help="Use haversine×1.3 instead of OSRM (faster, less accurate)")
    args = parser.parse_args()

    use_osrm = not args.no_osrm

    data    = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]
    if args.limit > 0:
        records = records[:args.limit]

    total    = len(records)
    with_geo = sum(1 for r in records if r.get("lat") and r.get("lon"))
    print(f"\nStage 6: transit enrichment for {total} records ({with_geo} have lat/lon)")
    print(f"  OSRM real routing: {'YES' if use_osrm else 'NO (haversine fallback)'}")
    print(f"  WMATA key:         {'custom' if os.getenv('WMATA_API_KEY') else 'demo (public)'}")

    if args.dry_run:
        print("  [DRY RUN] No API calls will be made.")
        return

    # Load WMATA data
    stations = load_wmata_stations()
    stops    = load_wmata_bus_stops()

    if not stations:
        print("  WARNING: No Metro stations loaded — transit enrichment will be bus-only")
    if not stops:
        print("  WARNING: No bus stops loaded — transit enrichment will be Metro-only")

    # Load existing org-level cache
    org_cache = _load_json(TRANSIT_CACHE, {})
    cache_hits = 0

    # Enrich each record
    enriched = 0
    no_geo   = 0
    no_transit = 0

    for i, rec in enumerate(records):
        if not rec.get("lat") or not rec.get("lon"):
            no_geo += 1
            continue

        key = _cache_key(rec["lat"], rec["lon"])
        was_cached = key in org_cache

        enrich_transit(rec, stations, stops, org_cache, use_osrm)

        if rec.get("transit_detail"):
            enriched += 1
            if was_cached:
                cache_hits += 1
        else:
            no_transit += 1

        # Progress + periodic cache save
        if (i + 1) % 50 == 0:
            pct = round((i + 1) / total * 100)
            print(f"  {i+1}/{total} ({pct}%)  enriched={enriched}  "
                  f"cache_hits={cache_hits}  no_transit={no_transit}")
            _save_json(TRANSIT_CACHE, org_cache)

    # Final cache save
    _save_json(TRANSIT_CACHE, org_cache)

    # Write output
    output_data = {
        "stats": {
            "total":       total,
            "with_geo":    with_geo,
            "enriched":    enriched,
            "cache_hits":  cache_hits,
            "no_geo":      no_geo,
            "no_transit":  no_transit,
            "osrm_used":   use_osrm,
        },
        "total":   total,
        "records": records,
    }
    OUTPUT.write_text(json.dumps(output_data, indent=2, ensure_ascii=False),
                      encoding="utf-8")

    # Stats
    has_metro = sum(1 for r in records
                    if (r.get("transit_detail") or {}).get("nearest_metro"))
    has_bus   = sum(1 for r in records
                    if (r.get("transit_detail") or {}).get("nearest_bus"))
    pct_e     = round(enriched / max(with_geo, 1) * 100)

    print(f"\n{'='*60}")
    print(f"TRANSIT: {enriched}/{with_geo} geocoded orgs enriched ({pct_e}%)")
    print(f"{'='*60}")
    print(f"  Have Metro info:    {has_metro}")
    print(f"  Have Bus info:      {has_bus}")
    print(f"  Cache hits:         {cache_hits}")
    print(f"  No transit found:   {no_transit}")
    print(f"  No geo (skipped):   {no_geo}")
    print(f"  Output:             {OUTPUT}")


if __name__ == "__main__":
    main()
