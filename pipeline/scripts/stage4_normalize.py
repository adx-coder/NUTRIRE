"""
Stage 4 -- Normalize: phone formatting, hours parsing, reliability, state/city, IDs.

Input:  output/stage3_geocoded.json
Output: output/stage4_normalized.json

Usage:
  python scripts/stage4_normalize.py
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PIPELINE = Path(__file__).resolve().parents[1]
INPUT    = PIPELINE / "output" / "stage3_geocoded.json"
OUTPUT   = PIPELINE / "output" / "stage4_normalized.json"


# ── Phone formatting ──────────────────────────────────────────────────────────

def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw  # return as-is if can't normalize


# ── Hours parsing ─────────────────────────────────────────────────────────────

_DAY_MAP = {
    "mon": "mon", "monday": "mon", "tue": "tue", "tuesday": "tue",
    "wed": "wed", "wednesday": "wed", "thu": "thu", "thursday": "thu",
    "fri": "fri", "friday": "fri", "sat": "sat", "saturday": "sat",
    "sun": "sun", "sunday": "sun",
}
_DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?", re.IGNORECASE)


def _parse_time(match) -> str | None:
    """Convert regex match to HH:MM 24h format."""
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower().replace(".", "")

    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    elif not meridiem and hour < 8:
        # Bare numbers 1-7 without AM/PM: ambiguous, likely PM for close times
        # Don't adjust here — context-dependent
        pass

    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def parse_hours_structured(raw: str | None) -> list[dict] | None:
    """Parse hours string into [{day, open, close, note}] list. Returns None if unparseable."""
    if not raw:
        return None

    entries = []
    # Split by comma, semicolon, or day name boundaries
    parts = re.split(r"[,;]\s*", raw)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Find day names
        day_matches = []
        for word in re.findall(r"[a-zA-Z]+", part):
            day = _DAY_MAP.get(word.lower())
            if day:
                day_matches.append(day)

        # Find time ranges
        times = list(_TIME_RE.finditer(part))

        if day_matches and len(times) >= 2:
            open_t = _parse_time(times[0])
            close_t = _parse_time(times[1])
            if open_t and close_t:
                # Extract note (everything after the time range)
                note = None
                last_time_end = times[1].end()
                remainder = part[last_time_end:].strip().lstrip(";:,- ").strip()
                if remainder and len(remainder) > 3:
                    note = remainder

                for day in day_matches:
                    entry = {"day": day, "open": open_t, "close": close_t}
                    if note:
                        entry["note"] = note
                    entries.append(entry)

    return entries if entries else None


# ── State/city inference ──────────────────────────────────────────────────────

def infer_state(zip_code: str | None) -> str | None:
    if not zip_code or len(zip_code) < 5:
        return None
    z = int(zip_code[:5])
    if 20001 <= z <= 20099 or 20200 <= z <= 20599:
        return "DC"
    elif 20600 <= z <= 21999:
        return "MD"
    elif 22000 <= z <= 24699 or 20100 <= z <= 20199:
        return "VA"
    return None


def infer_city(address: str | None, state: str | None) -> str | None:
    """Try to extract city from address string."""
    if not address:
        return None
    # Pattern: "123 Main St, CityName, ST 12345"
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        # City is usually second-to-last part (before "ST ZIP")
        candidate = parts[-2] if len(parts) >= 3 else parts[-1]
        # Remove ZIP and state
        candidate = re.sub(r"\b\d{5}(-\d{4})?\b", "", candidate).strip()
        candidate = re.sub(r"\b(MD|VA|DC|USA)\b", "", candidate, flags=re.IGNORECASE).strip()
        if candidate and len(candidate) > 1 and candidate[0].isupper():
            return candidate
    return None


# ── ID generation ─────────────��───────────────────────���───────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:60]


# ── Reliability scoring ────────────────────────��─────────────────────────────

def compute_reliability(rec: dict) -> dict:
    """Compute reliability signal."""
    cross = rec.get("cross_source_count", 1)
    has_hours = bool(rec.get("hours"))
    has_phone = bool(rec.get("phone"))
    has_website = bool(rec.get("website"))

    # Base score: all sources scraped today = fresh
    score = 0.8
    if cross >= 3:
        score += 0.15
    elif cross >= 2:
        score += 0.1
    if has_hours:
        score += 0.05
    if has_phone and has_website:
        score += 0.05

    score = min(1.0, score)

    if score >= 0.9:
        tier = "fresh"
    elif score >= 0.7:
        tier = "recent"
    elif score >= 0.4:
        tier = "stale"
    else:
        tier = "unknown"

    return {
        "tier": tier,
        "score": round(score, 2),
        "lastConfirmedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]
    total = len(records)
    print(f"Stage 4: normalizing {total} records")

    hours_parsed = 0
    phones_formatted = 0
    states_inferred = 0
    cities_inferred = 0

    for rec in records:
        # ID
        sid = rec.get("source_id", "unknown")
        name = rec.get("name", "unnamed")
        rec["id"] = f"org_{sid}__{slugify(name)}"

        # Phone
        old_phone = rec.get("phone")
        rec["phone"] = normalize_phone(old_phone)
        if rec["phone"] and rec["phone"] != old_phone:
            phones_formatted += 1

        # Hours parsing
        hours_raw = rec.get("hours")
        if hours_raw:
            structured = parse_hours_structured(hours_raw)
            if structured:
                rec["hours_structured"] = structured
                hours_parsed += 1
            else:
                rec["hours_structured"] = None
        else:
            rec["hours_structured"] = None

        # State
        if not rec.get("state"):
            inferred = infer_state(rec.get("zip"))
            if inferred:
                rec["state"] = inferred
                states_inferred += 1

        # City
        if not rec.get("city"):
            inferred = infer_city(rec.get("address"), rec.get("state"))
            if inferred:
                rec["city"] = inferred
                cities_inferred += 1

        # Reliability
        rec["reliability"] = compute_reliability(rec)

    # Save
    output_data = {
        "stats": {
            "total": total,
            "hours_parsed": hours_parsed,
            "phones_formatted": phones_formatted,
            "states_inferred": states_inferred,
            "cities_inferred": cities_inferred,
        },
        "total": total,
        "records": records,
    }
    OUTPUT.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Report
    has_id = sum(1 for r in records if r.get("id"))
    has_hours_struct = sum(1 for r in records if r.get("hours_structured"))
    has_state = sum(1 for r in records if r.get("state"))
    has_city = sum(1 for r in records if r.get("city"))
    has_phone = sum(1 for r in records if r.get("phone"))
    has_reliability = sum(1 for r in records if r.get("reliability"))

    print(f"\n{'='*60}")
    print(f"NORMALIZE: {total} records")
    print(f"{'='*60}")
    print(f"  IDs generated:       {has_id}/{total}")
    print(f"  Phones formatted:    {phones_formatted} changed, {has_phone} total")
    print(f"  Hours parsed:        {has_hours_struct}/{total} ({round(has_hours_struct/total*100)}%)")
    print(f"  States:              {has_state}/{total} ({states_inferred} inferred)")
    print(f"  Cities:              {has_city}/{total} ({cities_inferred} inferred)")
    print(f"  Reliability scored:  {has_reliability}/{total}")


if __name__ == "__main__":
    main()
