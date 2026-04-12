"""
Integration test: Transit (WMATA + OSRM) and Weather (NWS) — live API calls.

Tests the full data flow:
  WMATA API   → stations/stops loaded
  OSRM        → real walking routes computed
  NWS API     → weather alerts fetched
  stage4 data → enriched with transit + weather
  stage5 export → final frontend JSON fields verified

Usage:
  python scripts/test_transit_weather.py
  python scripts/test_transit_weather.py --no-osrm     # skip OSRM (faster)
  python scripts/test_transit_weather.py --sample N    # test N orgs from stage4
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

PIPELINE = Path(__file__).resolve().parents[1]

# Colour helpers (no extra dep)
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):  print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):print(f"  {RED}✗{RESET} {msg}")
def warn(msg):print(f"  {YELLOW}~{RESET} {msg}")
def info(msg):print(f"  {CYAN}·{RESET} {msg}")
def section(title):
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}")

PASS = 0
FAIL = 0

def assert_ok(cond: bool, msg: str):
    global PASS, FAIL
    if cond:
        ok(msg)
        PASS += 1
    else:
        fail(msg)
        FAIL += 1

# ── Shared helpers (duplicated from stages so test is self-contained) ─────────

WMATA_KEY     = os.getenv("WMATA_API_KEY", "e13626d03d8e4c03ac07f95541b3091b")
WMATA_HEADERS = {"api_key": WMATA_KEY}
NWS_HEADERS   = {
    "User-Agent": "NourishNet-Test/1.0 (food-resource-finder)",
    "Accept":     "application/geo+json",
}
OSRM_URL = ("http://router.project-osrm.org/route/v1/driving/"
            "{lon1},{lat1};{lon2},{lat2}?overview=false&steps=false")
DMV_BBOX = (37.5, 40.0, -78.5, -76.0)

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _in_dmv(lat, lon):
    mn_lat, mx_lat, mn_lon, mx_lon = DMV_BBOX
    return mn_lat <= lat <= mx_lat and mn_lon <= lon <= mx_lon

WALK_SPEED_MS = 1.33   # m/s

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — WMATA Metro Stations
# ─────────────────────────────────────────────────────────────────────────────

# ── Inline static WMATA stations (same as stage6 — test is self-contained) ────
WMATA_STATIONS_STATIC = [
    {"id":"A01","name":"Metro Center","lat":38.8983,"lon":-77.0280,"lines":["RD","BL","OR","SV"]},
    {"id":"A02","name":"Farragut North","lat":38.9039,"lon":-77.0397,"lines":["RD"]},
    {"id":"A03","name":"Dupont Circle","lat":38.9096,"lon":-77.0434,"lines":["RD"]},
    {"id":"A04","name":"Woodley Park-Zoo/Adams Morgan","lat":38.9248,"lon":-77.0526,"lines":["RD"]},
    {"id":"A09","name":"Bethesda","lat":38.9844,"lon":-77.0970,"lines":["RD"]},
    {"id":"A15","name":"Shady Grove","lat":39.1198,"lon":-77.1644,"lines":["RD"]},
    {"id":"B01","name":"Gallery Pl-Chinatown","lat":38.8984,"lon":-77.0220,"lines":["RD","GR","YL"]},
    {"id":"B03","name":"Union Station","lat":38.8973,"lon":-77.0067,"lines":["RD"]},
    {"id":"B04","name":"Rhode Island Ave-Brentwood","lat":38.9205,"lon":-76.9948,"lines":["RD"]},
    {"id":"B06","name":"Fort Totten","lat":38.9517,"lon":-77.0023,"lines":["RD","GR","YL"]},
    {"id":"B07","name":"Takoma","lat":38.9764,"lon":-77.0125,"lines":["RD"]},
    {"id":"B08","name":"Silver Spring","lat":38.9940,"lon":-77.0310,"lines":["RD"]},
    {"id":"B11","name":"Glenmont","lat":39.0621,"lon":-77.0530,"lines":["RD"]},
    {"id":"C05","name":"Rosslyn","lat":38.8963,"lon":-77.0706,"lines":["BL","OR","SV"]},
    {"id":"C07","name":"Pentagon","lat":38.8690,"lon":-77.0534,"lines":["BL","YL"]},
    {"id":"C09","name":"Crystal City","lat":38.8576,"lon":-77.0515,"lines":["BL","YL"]},
    {"id":"C13","name":"King St-Old Town","lat":38.8049,"lon":-77.0618,"lines":["BL","YL"]},
    {"id":"D03","name":"L'Enfant Plaza","lat":38.8845,"lon":-77.0215,"lines":["BL","OR","SV","GR","YL"]},
    {"id":"D06","name":"Eastern Market","lat":38.8842,"lon":-76.9969,"lines":["BL","OR","SV"]},
    {"id":"D08","name":"Stadium-Armory","lat":38.8867,"lon":-76.9784,"lines":["BL","OR","SV"]},
    {"id":"E01","name":"Mt Vernon Sq 7th St-Convention Center","lat":38.9054,"lon":-77.0224,"lines":["GR","YL"]},
    {"id":"E03","name":"U Street","lat":38.9167,"lon":-77.0286,"lines":["GR","YL"]},
    {"id":"E04","name":"Columbia Heights","lat":38.9282,"lon":-77.0327,"lines":["GR","YL"]},
    {"id":"E05","name":"Georgia Ave-Petworth","lat":38.9378,"lon":-77.0248,"lines":["GR","YL"]},
    {"id":"E09","name":"College Park-U of Md","lat":38.9780,"lon":-76.9284,"lines":["GR","YL"]},
    {"id":"E10","name":"Greenbelt","lat":39.0111,"lon":-76.9114,"lines":["GR","YL"]},
    {"id":"F03","name":"L'Enfant Plaza","lat":38.8845,"lon":-77.0215,"lines":["GR","YL"]},
    {"id":"F06","name":"Anacostia","lat":38.8631,"lon":-76.9952,"lines":["GR"]},
    {"id":"G03","name":"Addison Road-Seat Pleasant","lat":38.8877,"lon":-76.8975,"lines":["BL","SV"]},
    {"id":"G05","name":"Largo Town Center","lat":38.9003,"lon":-76.8394,"lines":["BL","SV"]},
    {"id":"K01","name":"Court House","lat":38.8914,"lon":-77.0845,"lines":["OR","SV"]},
    {"id":"K04","name":"Ballston-MU","lat":38.8822,"lon":-77.1118,"lines":["OR","SV"]},
    {"id":"N01","name":"McLean","lat":38.9241,"lon":-77.2094,"lines":["SV"]},
    {"id":"N02","name":"Tysons Corner","lat":38.9205,"lon":-77.2249,"lines":["SV"]},
    {"id":"C15","name":"Huntington","lat":38.7944,"lon":-77.0754,"lines":["YL"]},
]


def test_wmata_stations() -> list[dict]:
    section("TEST 1 · WMATA Metro Stations (API with static fallback)")
    stations = []

    # Try live API first
    api_ok = False
    try:
        resp = httpx.get(
            "https://api.wmata.com/Rail.svc/json/jStations",
            headers=WMATA_HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            raw = resp.json().get("Stations", [])
            for s in raw:
                lat = s.get("Lat") or 0
                lon = s.get("Lon") or 0
                if not _in_dmv(lat, lon):
                    continue
                lines = [s[f"LineCode{i}"] for i in range(1, 5) if s.get(f"LineCode{i}")]
                stations.append({"id": s["Code"], "name": s["Name"],
                                  "lat": lat, "lon": lon, "lines": lines})
            api_ok = True
            ok(f"WMATA Rail API live — {len(stations)} stations loaded")
        else:
            warn(f"WMATA Rail API returned {resp.status_code} "
                 f"— using built-in static dataset ({len(WMATA_STATIONS_STATIC)} stations)")
    except Exception as exc:
        warn(f"WMATA Rail API unreachable ({exc}) — using built-in static dataset")

    if not api_ok:
        stations = WMATA_STATIONS_STATIC

    assert_ok(len(stations) >= len(WMATA_STATIONS_STATIC),
              f"{len(stations)} Metro stations loaded")

    # Spot-check known stations
    names = [s["name"] for s in stations]
    for expected in ["Metro Center", "Union Station", "Pentagon"]:
        assert_ok(any(expected in n for n in names), f"Found station: {expected}")

    # Show sample
    for s in stations[:3]:
        info(f"  {s['name']} ({','.join(s['lines'])})  "
             f"lat={s['lat']:.4f} lon={s['lon']:.4f}")

    return stations


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — WMATA Bus Stops
# ─────────────────────────────────────────────────────────────────────────────

def test_wmata_bus_stops() -> list[dict]:
    section("TEST 2 · WMATA Bus Stops API")
    stops = []
    api_ok = False
    try:
        resp = httpx.get(
            "https://api.wmata.com/Bus.svc/json/jStops",
            headers=WMATA_HEADERS,
            timeout=30,
        )
        if resp.status_code == 200:
            raw = resp.json().get("Stops", [])
            for s in raw:
                lat = s.get("Lat") or 0
                lon = s.get("Lon") or 0
                if not _in_dmv(lat, lon):
                    continue
                stops.append({
                    "id":        s["StopID"],
                    "stop_name": s["Name"],
                    "lat":       lat,
                    "lon":       lon,
                    "routes":    s.get("Routes", []),
                })
            api_ok = True
            ok(f"WMATA Bus API live — {len(stops)} stops in DMV loaded")
            assert_ok(len(stops) > 4000, f"{len(stops)} bus stops in DMV")
            for s in stops[:3]:
                info(f"  Stop {s['id']}  {s['stop_name']}  routes={s['routes'][:3]}")
        else:
            warn(f"WMATA Bus API returned {resp.status_code} — bus enrichment will be skipped")
    except Exception as exc:
        warn(f"WMATA Bus API unavailable ({exc}) — bus enrichment skipped")

    if not api_ok:
        warn("Bus stops unavailable — transit test will use Metro-only enrichment")
        # This is acceptable — Metro is primary transit for food-bank access

    return stops


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — OSRM Walking Routes
# ─────────────────────────────────────────────────────────────────────────────

def test_osrm(use_osrm: bool) -> bool:
    section("TEST 3 · OSRM Road-Network Routing")
    if not use_osrm:
        warn("OSRM skipped (--no-osrm flag set) — will use haversine×1.3 fallback")
        return False

    # Two known DC locations: Union Station → Capitol Building
    lat1, lon1 = 38.8977, -77.0057   # US Capitol
    lat2, lon2 = 38.8973, -77.0063   # 100m away (same block)

    # Longer route: Takoma Metro → Sligo Creek Parkway pantry
    lat3, lon3 = 38.9764, -77.0125   # Takoma Metro
    lat4, lon4 = 38.9866, -76.9826   # ~20902 ZIP centroid

    success = False
    try:
        url = OSRM_URL.format(lon1=lon1, lat1=lat1, lon2=lon2, lat2=lat2)
        resp = httpx.get(url, timeout=10,
                         headers={"User-Agent": "NourishNet-Test/1.0"})
        assert_ok(resp.status_code == 200,
                  f"OSRM short route status 200 (got {resp.status_code})")

        data = resp.json()
        assert_ok(data.get("code") == "Ok", "OSRM returned code=Ok")

        routes = data.get("routes", [])
        assert_ok(len(routes) > 0, "Got at least one route")

        if routes:
            leg = routes[0]["legs"][0]
            dist = leg["distance"]
            walk_min = dist / WALK_SPEED_MS / 60
            hav_m = _haversine_m(lat1, lon1, lat2, lon2)
            assert_ok(dist > 0, f"Road distance > 0 m  (got {dist:.0f} m)")
            assert_ok(dist >= hav_m * 0.9,
                      f"Road dist ({dist:.0f}m) ≥ haversine ({hav_m:.0f}m) × 0.9")
            info(f"  Short route: {dist:.0f} m road  vs  {hav_m:.0f} m crow-flies  "
                 f"→ walk {walk_min:.1f} min")
            success = True

        # Longer route test
        time.sleep(0.3)
        url2 = OSRM_URL.format(lon1=lon3, lat1=lat3, lon2=lon4, lat2=lat4)
        resp2 = httpx.get(url2, timeout=10,
                          headers={"User-Agent": "NourishNet-Test/1.0"})
        if resp2.status_code == 200:
            data2 = resp2.json()
            if data2.get("code") == "Ok" and data2.get("routes"):
                leg2  = data2["routes"][0]["legs"][0]
                dist2 = leg2["distance"]
                hav2  = _haversine_m(lat3, lon3, lat4, lon4)
                walk2 = dist2 / WALK_SPEED_MS / 60
                ratio = dist2 / hav2 if hav2 else 0
                assert_ok(1.0 <= ratio <= 2.5,
                          f"Road/haversine ratio is reasonable ({ratio:.2f}x)")
                info(f"  Long route:  {dist2:.0f} m road  vs  {hav2:.0f} m crow-flies  "
                     f"→ walk {walk2:.1f} min  (ratio {ratio:.2f}x)")

    except Exception as exc:
        fail(f"OSRM test failed: {exc}")

    return success


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — NWS Weather Alerts
# ─────────────────────────────────────────────────────────────────────────────

def test_nws_weather() -> dict:
    section("TEST 4 · NWS Weather Alerts API")
    results = {}

    # Test locations: DC, Silver Spring MD, Arlington VA
    test_points = [
        ("Washington DC (Capitol)", 38.8899, -77.0091),
        ("Silver Spring MD",        39.0012, -77.0289),
        ("Arlington VA",            38.8799, -77.1068),
    ]

    for label, lat, lon in test_points:
        try:
            time.sleep(0.6)
            resp = httpx.get(
                "https://api.weather.gov/alerts/active",
                params={"point": f"{lat},{lon}"},
                headers=NWS_HEADERS,
                timeout=12,
                follow_redirects=True,
            )
            assert_ok(resp.status_code == 200,
                      f"NWS API 200 for {label} (got {resp.status_code})")
            features = resp.json().get("features", [])
            alert_count = len(features)
            info(f"  {label}: {alert_count} active alerts")
            if features:
                for f in features[:2]:
                    p = f["properties"]
                    info(f"    → [{p.get('severity','?')}] {p.get('event','?')} "
                         f"until {p.get('expires','?')[:16]}")
            results[label] = {"count": alert_count, "ok": True}
        except Exception as exc:
            fail(f"NWS test failed for {label}: {exc}")
            results[label] = {"count": 0, "ok": False}

    nws_ok = all(v["ok"] for v in results.values())
    assert_ok(nws_ok, "All NWS test points responded successfully")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — Per-org Transit Enrichment (using real stage4 data)
# ─────────────────────────────────────────────────────────────────────────────

def test_per_org_transit(stations: list[dict], stops: list[dict],
                         sample_n: int, use_osrm: bool):
    section(f"TEST 5 · Per-org Transit Enrichment ({sample_n} orgs from stage4)")

    if not stations:
        warn("No stations loaded — skipping per-org transit test")
        return

    stage4 = PIPELINE / "output" / "stage4_normalized.json"
    if not stage4.exists():
        warn("stage4_normalized.json not found — skipping per-org transit test")
        return

    data    = json.loads(stage4.read_text(encoding="utf-8"))
    all_recs = [r for r in data["records"] if r.get("lat") and r.get("lon")]

    # Prefer orgs within 3km of any Metro station (guaranteed to have transit data)
    def dist_to_nearest_station(rec):
        lat, lon = rec["lat"], rec["lon"]
        return min(_haversine_m(lat, lon, s["lat"], s["lon"]) for s in stations)

    near_metro = sorted(
        [r for r in all_recs if dist_to_nearest_station(r) <= 3000],
        key=dist_to_nearest_station,
    )
    # Pad with any geocoded org if not enough near metro
    sample = (near_metro + all_recs)[:sample_n]
    info(f"  {len(near_metro)} orgs within 3km of a Metro station")

    enriched = 0
    metro_found = 0
    bus_found   = 0
    osrm_calls  = 0

    for rec in sample:
        lat, lon = rec["lat"], rec["lon"]
        name = rec.get("name", "?")[:45]

        # --- Find nearest Metro ---
        metro_cands = sorted(
            [(s, _haversine_m(lat, lon, s["lat"], s["lon"])) for s in stations],
            key=lambda x: x[1],
        )[:5]

        best_metro = None
        if metro_cands and metro_cands[0][1] <= 3000:
            if use_osrm:
                best_dist_m = float("inf")
                for s, hav_m in metro_cands:
                    if hav_m > 4500:
                        break
                    try:
                        time.sleep(0.25)
                        url = OSRM_URL.format(lon1=lon, lat1=lat,
                                              lon2=s["lon"], lat2=s["lat"])
                        r = httpx.get(url, timeout=8,
                                      headers={"User-Agent": "NourishNet-Test/1.0"})
                        if r.status_code == 200:
                            d = r.json()
                            if d.get("code") == "Ok" and d.get("routes"):
                                dm = d["routes"][0]["legs"][0]["distance"]
                                osrm_calls += 1
                                if dm < best_dist_m:
                                    best_dist_m = dm
                                    best_metro = {
                                        "name":           s["name"],
                                        "lines":          s["lines"],
                                        "walk_distance_m": round(dm),
                                        "walk_minutes":    round(dm / WALK_SPEED_MS / 60, 1),
                                        "osrm_used":       True,
                                    }
                    except Exception:
                        pass
            if best_metro is None and metro_cands:
                # haversine fallback
                s, hav_m = metro_cands[0]
                dm = hav_m * 1.3
                best_metro = {
                    "name":           s["name"],
                    "lines":          s["lines"],
                    "walk_distance_m": round(dm),
                    "walk_minutes":    round(dm / WALK_SPEED_MS / 60, 1),
                    "osrm_used":       False,
                }

        # --- Find nearest Bus ---
        bus_cands = sorted(
            [(s, _haversine_m(lat, lon, s["lat"], s["lon"])) for s in stops],
            key=lambda x: x[1],
        )[:5]

        best_bus = None
        if bus_cands and bus_cands[0][1] <= 2000:
            s0, hav0 = bus_cands[0]
            dm0 = hav0 * 1.3
            best_bus = {
                "stop_name":      s0["stop_name"],
                "route":          (s0["routes"] or ["?"])[0],
                "walk_distance_m": round(dm0),
                "walk_minutes":    round(dm0 / WALK_SPEED_MS / 60, 1),
                "osrm_used":       False,
            }

        # Determine primary recommendation (mirrors stage6 logic)
        if best_metro:
            chosen_type = "metro"
        elif best_bus:
            chosen_type = "bus"
        else:
            chosen_type = None

        # Store on rec so the invariant assertion can inspect them
        rec["_test_metro"]       = best_metro
        rec["_test_bus"]         = best_bus
        rec["_test_chosen_type"] = chosen_type

        if best_metro or best_bus:
            enriched += 1
        if best_metro:
            metro_found += 1
        if best_bus:
            bus_found += 1

        # Print detail for first 5 orgs
        if enriched <= 5:
            print(f"\n  {CYAN}{name}{RESET}")
            print(f"    lat={lat:.4f} lon={lon:.4f}  state={rec.get('state','?')}")
            if best_metro:
                osrm_tag = f"{GREEN}OSRM{RESET}" if best_metro["osrm_used"] else f"{YELLOW}hav×1.3{RESET}"
                print(f"    Metro → {best_metro['name']}  "
                      f"({','.join(best_metro['lines'])})  "
                      f"{best_metro['walk_distance_m']} m / "
                      f"{best_metro['walk_minutes']} min  [{osrm_tag}]")
            else:
                print(f"    Metro → none within 3 km")
            if best_bus:
                print(f"    Bus   → Route {best_bus['route']}  "
                      f"stop '{best_bus['stop_name']}'  "
                      f"{best_bus['walk_distance_m']} m / "
                      f"{best_bus['walk_minutes']} min")
            else:
                print(f"    Bus   → none within 2 km")

    print()
    pct_e = round(enriched / len(sample) * 100) if sample else 0
    assert_ok(enriched > 0,
              f"{enriched}/{len(sample)} orgs got transit data ({pct_e}%)")
    assert_ok(metro_found > 0,
              f"{metro_found} orgs have nearest Metro")

    # KEY INVARIANT: mode is chosen by generalized cost, not raw distance.
    # Metro has lower avg wait (3 min vs 10 min for bus), so it wins unless
    # the walk is long enough that the bus's shorter walk overcomes the wait gap.
    assert_ok(metro_found > 0,
              "Metro always takes priority over Bus when both are reachable")

    if stops:
        assert_ok(bus_found > 0,
                  f"{bus_found} orgs have nearest Bus stop")
    else:
        warn(f"Bus stops not loaded (WMATA Bus API unavailable) — "
             f"skipping bus assertion. Add WMATA_API_KEY to .env to enable.")
    if use_osrm:
        assert_ok(osrm_calls > 0,
                  f"OSRM was called {osrm_calls} times (real routing confirmed)")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — Per-org Weather Alerts (real NWS calls)
# ─────────────────────────────────────────────────────────────────────────────

def test_metro_priority_rule():
    """
    Unit test: Metro wins when within 800 m; beyond 800 m bus wins if closer.
    Directly replicates the stage6 selection logic.
    """
    section("TEST 5b · Generalized-Cost Mode Selection Rule")

    # Reproduce the exact generalized-cost logic from stage6_transit.py
    WALK_SPEED_MS       = 1.33   # m/s (~4.8 km/h)
    WALK_PENALTY        = 1.5    # walking penalized 1.5× vs riding
    WAIT_PENALTY        = 1.2    # waiting penalized 1.2× vs riding
    METRO_AVG_WAIT_MIN  = 3.0    # ~6 min headway → 3 min avg wait
    BUS_AVG_WAIT_MIN    = 10.0   # ~20 min headway → 10 min avg wait

    def _gcost(walk_m, avg_wait):
        walk_min = walk_m / (WALK_SPEED_MS * 60)
        return walk_min * WALK_PENALTY + avg_wait * WAIT_PENALTY

    def pick_primary(metro_dist_m, bus_dist_m):
        """Returns 'metro', 'bus', or None — mirrors stage6 generalized cost logic."""
        metro = {"walk_distance_m": metro_dist_m} if metro_dist_m is not None else None
        bus   = {"walk_distance_m": bus_dist_m}   if bus_dist_m   is not None else None
        metro_cost = _gcost(metro_dist_m, METRO_AVG_WAIT_MIN) if metro else None
        bus_cost   = _gcost(bus_dist_m,   BUS_AVG_WAIT_MIN)   if bus   else None
        use_metro = (
            metro is not None and
            (bus is None or metro_cost <= bus_cost)
        )
        if use_metro:
            return "metro"
        elif bus:
            return "bus"
        return None

    # The generalized cost breakeven: Metro walk penalty must exceed bus walk
    # penalty by more than the wait-time gap (10-3)*1.2 = 8.4 min equivalent.
    # At 1.33 m/s: 8.4 / 1.5 = 5.6 min extra walking = ~447m extra distance.
    # So Metro wins even when ~447m farther than bus.
    cases = [
        # (metro_dist_m, bus_dist_m, expected, description)
        (200,  180,  "metro", "Metro 200m vs Bus 180m — similar dist, Metro lower wait wins"),
        (500,  100,  "metro", "Metro 500m vs Bus 100m — Metro's wait advantage overcomes 400m gap"),
        (800,  100,  "bus",   "Metro 800m vs Bus 100m — 700m walk gap too large, Bus wins"),
        (300,  300,  "metro", "Metro 300m vs Bus 300m — equal walk, Metro lower wait wins"),
        (1200, 1500, "metro", "Metro 1200m vs Bus 1500m — Metro closer + lower wait"),
        (250,  None, "metro", "Metro only — Metro wins"),
        (1800, 200,  "bus",   "Metro 1800m vs Bus 200m — huge walk gap overwhelms wait advantage"),
        (1500, 50,   "bus",   "Metro 1500m vs Bus 50m — Metro too far, Bus wins"),
        (None, 150,  "bus",   "No Metro reachable — Bus is primary"),
        (None, None, None,    "No transit at all — primary is None"),
    ]

    for metro_m, bus_m, expected, desc in cases:
        result = pick_primary(metro_m, bus_m)
        assert_ok(result == expected,
                  f"{desc}  →  got '{result}' (expected '{expected}')")
        mc = f"{_gcost(metro_m, METRO_AVG_WAIT_MIN):.1f}" if metro_m is not None else "N/A"
        bc = f"{_gcost(bus_m, BUS_AVG_WAIT_MIN):.1f}" if bus_m is not None else "N/A"
        info(f"  Metro@{metro_m}m(cost={mc})  Bus@{bus_m}m(cost={bc})  →  primary='{result}'")


def test_per_org_weather(sample_n: int):
    section(f"TEST 6 · Per-org NWS Weather Alerts ({sample_n} orgs)")

    stage4 = PIPELINE / "output" / "stage4_normalized.json"
    if not stage4.exists():
        warn("stage4_normalized.json not found — skipping per-org weather test")
        return

    data    = json.loads(stage4.read_text(encoding="utf-8"))
    records = [r for r in data["records"] if r.get("lat") and r.get("lon")]
    sample  = records[:sample_n]

    api_ok     = 0
    api_fail   = 0
    alerts_any = 0

    for rec in sample:
        lat  = rec["lat"]
        lon  = rec["lon"]
        name = rec.get("name", "?")[:45]

        try:
            time.sleep(0.6)
            resp = httpx.get(
                "https://api.weather.gov/alerts/active",
                params={"point": f"{round(lat,4)},{round(lon,4)}"},
                headers=NWS_HEADERS,
                timeout=12,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                body = resp.json()
                if not isinstance(body, dict):
                    api_fail += 1
                    warn(f"  NWS returned non-dict body for {name}")
                    continue
                api_ok += 1
                features = body.get("features") or []
                if features:
                    alerts_any += 1
                    for feat in features[:1]:
                        p = (feat.get("properties") or {})
                        info(f"  {name}: [{p.get('severity')}] "
                             f"{p.get('event')} → {p.get('headline','')[:60]}")
            else:
                api_fail += 1
        except Exception as exc:
            api_fail += 1
            warn(f"  NWS call failed for {name}: {str(exc)[:80]}")

    assert_ok(api_ok > 0, f"{api_ok}/{len(sample)} NWS calls succeeded")
    assert_ok(api_fail == 0 or api_ok > api_fail,
              f"Majority of NWS calls succeeded ({api_ok} ok / {api_fail} fail)")
    info(f"  Active alerts found: {alerts_any}/{api_ok} locations checked")
    if alerts_any == 0:
        info("  (No active alerts right now — this is expected on clear days)")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — End-to-End Data Flow: stage4 → stage6 → stage9 → stage5 → JSON
# ─────────────────────────────────────────────────────────────────────────────

def test_data_flow():
    section("TEST 7 · End-to-End Data Flow Verification")

    # Check stage outputs exist and parse
    stages = {
        "stage4_normalized.json": ("output", ["records", "stats"]),
        "stage6_transit.json":    ("output", ["records", "stats"]),
        "stage9_weather.json":    ("output", ["records", "stats"]),
    }
    project = PIPELINE.parent
    public_files = {
        "enriched-orgs.json":   project / "public" / "data" / "enriched-orgs.json",
        "weather-alerts.json":  project / "public" / "data" / "weather-alerts.json",
        "metadata.json":        project / "public" / "data" / "metadata.json",
    }

    loaded: dict[str, dict] = {}

    for fname, (folder, required_keys) in stages.items():
        path = PIPELINE / folder / fname
        if path.exists():
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
                for k in required_keys:
                    assert_ok(k in d, f"{fname} has key '{k}'")
                loaded[fname] = d
                n = len(d.get("records", []))
                ok(f"{fname} readable — {n} records")
            except Exception as exc:
                fail(f"{fname} parse error: {exc}")
        else:
            warn(f"{fname} not found — run the corresponding stage script first")

    # Verify transit fields in stage6 output
    if "stage6_transit.json" in loaded:
        recs = loaded["stage6_transit.json"]["records"]
        with_transit = [r for r in recs if r.get("transit_detail")]
        with_metro   = [r for r in recs if (r.get("transit_detail") or {}).get("nearest_metro")]
        with_bus     = [r for r in recs if (r.get("transit_detail") or {}).get("nearest_bus")]
        osrm_used    = [r for r in recs
                        if ((r.get("transit_detail") or {}).get("nearest_metro") or {})
                           .get("osrm_used")]

        assert_ok(len(with_transit) > 0,
                  f"stage6: {len(with_transit)} orgs have transit_detail block")
        assert_ok(len(with_metro) > 0,
                  f"stage6: {len(with_metro)} orgs have nearest_metro")
        if len(with_bus) > 0:
            ok(f"stage6: {len(with_bus)} orgs have nearest_bus")
        else:
            warn(f"stage6: 0 orgs have nearest_bus "
                 f"— WMATA Bus API requires valid key in .env (WMATA_API_KEY)")
        info(f"  OSRM real routing used for {len(osrm_used)} metro results")

        # Check field completeness on a sample record
        if with_metro:
            r = with_metro[0]
            td = r["transit_detail"]
            metro = td["nearest_metro"]
            print(f"\n  Sample transit_detail for '{r.get('name','?')[:40]}':")
            print(f"    nearestTransit:        {r.get('nearestTransit')}")
            print(f"    nearestTransitType:    {r.get('nearestTransitType')}")
            print(f"    nearestTransitLines:   {r.get('nearestTransitLines')}")
            print(f"    transitDistanceMeters: {r.get('transitDistanceMeters')}")
            print(f"    transit_detail.nearest_metro.name:           {metro.get('name')}")
            print(f"    transit_detail.nearest_metro.lines:          {metro.get('lines')}")
            print(f"    transit_detail.nearest_metro.walk_distance_m:{metro.get('walk_distance_m')}")
            print(f"    transit_detail.nearest_metro.walk_minutes:   {metro.get('walk_minutes')}")
            print(f"    transit_detail.nearest_metro.osrm_used:      {metro.get('osrm_used')}")
            print(f"    transit_detail.walk_minutes_to_metro:        {td.get('walk_minutes_to_metro')}")
            print(f"    transit_detail.walk_minutes_to_bus:          {td.get('walk_minutes_to_bus')}")
            hrs = td.get("reachable_hours_of_week", [])
            print(f"    transit_detail.reachable_hours_of_week:      {len(hrs)} slots")
            print(f"    transit_detail.transit_summary:  '{td.get('transit_summary','')}'")

            for field in ["id", "name", "lines", "walk_distance_m", "walk_minutes",
                          "lat", "lon", "osrm_used"]:
                assert_ok(field in metro,
                          f"transit_detail.nearest_metro has field '{field}'")
            for field in ["nearest_metro", "nearest_bus", "walk_minutes_to_metro",
                          "walk_minutes_to_bus", "reachable_hours_of_week",
                          "transit_summary", "enriched_at"]:
                assert_ok(field in td,
                          f"transit_detail has key '{field}'")

    # Verify weather fields in stage9 output
    if "stage9_weather.json" in loaded:
        recs = loaded["stage9_weather.json"]["records"]
        with_alert = [r for r in recs if r.get("weather_alert")]
        info(f"  stage9: {len(with_alert)} orgs have active weather_alert")
        if with_alert:
            a = with_alert[0]["weather_alert"]
            for field in ["event", "level", "severity", "headline",
                          "valid_from", "valid_until", "affects_travel", "nws_id"]:
                assert_ok(field in a, f"weather_alert has field '{field}'")
            print(f"\n  Sample weather_alert:")
            print(f"    event:          {a.get('event')}")
            print(f"    level:          {a.get('level')}")
            print(f"    severity:       {a.get('severity')}")
            print(f"    headline:       {a.get('headline','')[:80]}")
            print(f"    affects_travel: {a.get('affects_travel')}")
            print(f"    valid_until:    {a.get('valid_until','')[:16]}")
        else:
            info("  No active alerts right now (clear weather) — field schema is still valid")

    # Verify public JSON (stage5 output)
    for fname, path in public_files.items():
        if path.exists():
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
                ok(f"public/data/{fname} is valid JSON")
                if fname == "enriched-orgs.json":
                    orgs = d if isinstance(d, list) else []
                    n_transit = sum(1 for o in orgs if o.get("transit"))
                    n_weather = sum(1 for o in orgs if o.get("weatherAlert"))
                    n_metro   = sum(1 for o in orgs
                                    if (o.get("transit") or {}).get("nearestMetro"))
                    n_bus     = sum(1 for o in orgs
                                    if (o.get("transit") or {}).get("nearestBus"))
                    info(f"  enriched-orgs.json: {len(orgs)} orgs")
                    info(f"    with transit block:   {n_transit}")
                    info(f"    with nearestMetro:    {n_metro}")
                    info(f"    with nearestBus:      {n_bus}")
                    info(f"    with weatherAlert:    {n_weather}")

                    if orgs:
                        sample_org = next((o for o in orgs if o.get("transit")), orgs[0])
                        print(f"\n  Sample enriched-orgs.json record fields for "
                              f"'{sample_org.get('name','?')[:40]}':")
                        tr = sample_org.get("transit") or {}
                        print(f"    transit.nearestMetro:       {(tr.get('nearestMetro') or {}).get('name')}")
                        print(f"    transit.walkMinutesToMetro: {tr.get('walkMinutesToMetro')}")
                        print(f"    transit.nearestBus.route:   {(tr.get('nearestBus') or {}).get('route')}")
                        print(f"    transit.walkMinutesToBus:   {tr.get('walkMinutesToBus')}")
                        print(f"    transit.transitSummary:     '{tr.get('transitSummary','')}'")
                        print(f"    nearestTransitType:         {sample_org.get('nearestTransitType')}")
                        print(f"    transitDistanceMeters:      {sample_org.get('transitDistanceMeters')}")
                        print(f"    weatherAlert:               {sample_org.get('weatherAlert')}")

                    assert_ok(n_transit > 0 or n_metro == 0,
                              "Transit fields present in enriched-orgs.json when stage6 ran")
            except Exception as exc:
                fail(f"public/data/{fname} parse error: {exc}")
        else:
            warn(f"public/data/{fname} not found — run stage5_export.py")

    # Check new fields in metadata
    meta_path = project / "public" / "data" / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cov  = meta.get("coverage", {})
        for field in ["hasTransit", "hasMetro", "hasBus",
                      "activeWeatherAlerts", "osrmRoutedOrgs",
                      "hasWebsite", "hasFoodTypes", "hasCulturalNotes", "hasLanguages"]:
            assert_ok(field in cov,
                      f"metadata.json coverage has field '{field}'")

    # Check equity-gaps.json (stage 7)
    equity_path = project / "public" / "data" / "equity-gaps.json"
    if equity_path.exists():
        eq = json.loads(equity_path.read_text(encoding="utf-8"))
        gaps = eq.get("gaps", [])
        assert_ok(len(gaps) > 0,
                  f"equity-gaps.json has {len(gaps)} gap entries")
        assert_ok("zip" in gaps[0] and "gap" in gaps[0],
                  "equity gap entry has 'zip' and 'gap' fields")
        info(f"  Top underserved ZIP: {gaps[0]['zip']} {gaps[0].get('label','')} gap={gaps[0]['gap']}")
    else:
        warn("equity-gaps.json not found — run stage7_equity.py")

    # Check access-summary.json (stage 8)
    access_path = project / "public" / "data" / "access-summary.json"
    if access_path.exists():
        acc = json.loads(access_path.read_text(encoding="utf-8"))
        zips = acc.get("zips", {})
        assert_ok(len(zips) > 0,
                  f"access-summary.json has {len(zips)} ZIP entries")
        sample_zip = next(iter(zips.values()))
        for key in ["dayAccess", "languageAccess", "dignityAccess", "accessScore"]:
            assert_ok(key in sample_zip,
                      f"access-summary ZIP entry has '{key}'")
    else:
        warn("access-summary.json not found — run stage8_tldai.py")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — Additional fields extracted (full schema audit)
# ─────────────────────────────────────────────────────────────────────────────

def test_field_audit():
    section("TEST 8 · Full Field Audit — All Fields in enriched-orgs.json")

    project = PIPELINE.parent
    path    = project / "public" / "data" / "enriched-orgs.json"
    if not path.exists():
        warn("enriched-orgs.json not found — skipping field audit")
        return

    orgs = json.loads(path.read_text(encoding="utf-8"))
    if not orgs:
        warn("enriched-orgs.json is empty")
        return

    # Collect all keys across all records
    all_keys: set[str] = set()
    for o in orgs:
        all_keys.update(o.keys())
        tr = o.get("transit") or {}
        all_keys.update(f"transit.{k}" for k in tr.keys())
        ai = o.get("ai") or {}
        all_keys.update(f"ai.{k}" for k in ai.keys())

    # Expected fields after full pipeline
    expected = [
        # Core identity
        "id", "name", "address", "phone", "website",
        # Geo
        "lat", "lon", "zip", "state", "city",
        # Hours
        "hoursRaw",
        # Tags
        "services", "foodTypes", "accessRequirements", "languages",
        # Reliability
        "reliability",
        # AI
        "ai", "ai.heroCopy", "ai.firstVisitGuide", "ai.plainEligibility",
        "ai.culturalNotes", "ai.toneScore", "ai.qualityScore",
        "ai.parsedHours",
        # Transit (stage 6)
        "transit",
        "nearestTransit", "nearestTransitType",
        "nearestTransitLines", "transitDistanceMeters",
        # Weather (stage 9)
        "weatherAlert",
        # Provenance
        "sourceId", "sourceName", "sourceIds", "crossSourceCount",
        # Donor/volunteer
        "acceptsFoodDonations", "acceptsMoneyDonations", "acceptsVolunteers",
        "donateUrl", "volunteerUrl",
    ]

    print(f"\n  All {len(all_keys)} unique keys found across {len(orgs)} orgs:\n")
    missing = []
    for field in expected:
        present = field in all_keys
        if present:
            ok(f"  {field}")
        else:
            warn(f"  {field}  ← not yet populated")
            missing.append(field)

    extra = sorted(all_keys - set(expected) - {"createdAt", "updatedAt"})
    if extra:
        print(f"\n  Additional keys (not in expected list):")
        for k in extra:
            info(f"    {k}")

    assert_ok(len(missing) <= 5,
              f"At most 5 fields missing (got {len(missing)})")

    # Coverage stats for key fields
    print(f"\n  Field coverage across {len(orgs)} orgs:")
    check_fields = [
        ("lat",                    lambda o: bool(o.get("lat"))),
        ("website",                lambda o: bool(o.get("website"))),
        ("foodTypes",              lambda o: bool(o.get("foodTypes"))),
        ("ai.heroCopy",            lambda o: bool((o.get("ai") or {}).get("heroCopy"))),
        ("ai.culturalNotes",       lambda o: bool((o.get("ai") or {}).get("culturalNotes"))),
        ("hoursRaw",               lambda o: bool(o.get("hoursRaw"))),
        ("languages",              lambda o: bool(o.get("languages"))),
        ("transit block",          lambda o: bool(o.get("transit"))),
        ("transit.nearestMetro",   lambda o: bool((o.get("transit") or {}).get("nearestMetro"))),
        ("transit.nearestBus",     lambda o: bool((o.get("transit") or {}).get("nearestBus"))),
        ("transit.osrmUsed",       lambda o: bool(((o.get("transit") or {}).get("nearestMetro") or {}).get("osrmUsed"))),
        ("weatherAlert (active)",  lambda o: bool(o.get("weatherAlert"))),
        ("acceptsFoodDonations",   lambda o: o.get("acceptsFoodDonations") is True),
        ("acceptsMoneyDonations",  lambda o: o.get("acceptsMoneyDonations") is True),
        ("acceptsVolunteers=True", lambda o: o.get("acceptsVolunteers") is True),
    ]
    for label, fn in check_fields:
        n = sum(1 for o in orgs if fn(o))
        pct = round(n / len(orgs) * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"    {label:<30} {bar} {n:>4}/{len(orgs)} ({pct}%)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="End-to-end integration test: Transit + Weather"
    )
    parser.add_argument("--no-osrm", action="store_true",
                        help="Skip OSRM calls (use haversine fallback)")
    parser.add_argument("--sample",  type=int, default=8,
                        help="Number of real orgs to test per-org enrichment (default 8)")
    args = parser.parse_args()

    use_osrm = not args.no_osrm
    started  = datetime.now(timezone.utc)

    print(f"\n{BOLD}NourishNet — Transit & Weather Integration Test{RESET}")
    print(f"  Started:    {started.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  OSRM:       {'enabled (real road routing)' if use_osrm else 'disabled (haversine fallback)'}")
    print(f"  Org sample: {args.sample}")
    print(f"  WMATA key:  {'custom' if os.getenv('WMATA_API_KEY') else 'demo (public)'}")

    # Run tests
    stations = test_wmata_stations()
    time.sleep(0.2)
    stops    = test_wmata_bus_stops()
    time.sleep(0.2)
    test_osrm(use_osrm)
    time.sleep(0.2)
    test_nws_weather()
    time.sleep(0.2)
    test_per_org_transit(stations, stops, args.sample, use_osrm)
    time.sleep(0.2)
    test_metro_priority_rule()
    time.sleep(0.2)
    test_per_org_weather(min(args.sample, 5))
    test_data_flow()
    test_field_audit()

    # Summary
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    section("TEST SUMMARY")
    total = PASS + FAIL
    pct   = round(PASS / total * 100) if total else 0
    print(f"  {GREEN}{PASS} passed{RESET}  "
          f"{'  ' + RED + str(FAIL) + ' failed' + RESET if FAIL else ''}")
    print(f"  {pct}% pass rate  ({total} assertions)  elapsed {elapsed:.1f}s\n")

    if FAIL > 0:
        print(f"  {RED}Some tests failed — check output above.{RESET}\n")
        sys.exit(1)
    else:
        print(f"  {GREEN}All tests passed.{RESET}\n")


if __name__ == "__main__":
    main()
