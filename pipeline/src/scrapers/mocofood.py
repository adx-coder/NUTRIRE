"""
Scraper for Montgomery County Food Council directory.
Source: https://mocofoodcouncil.org/map/

The site uses a DRTS (Directories) WordPress plugin that renders structured
listing cards with data-name attributes on every field:
  entity_field_post_title           → org name
  entity_field_location_address     → street address + ZIP (with distance suffix)
  entity_field_field_phone          → phone (bare digits)
  entity_field_field_website        → website URL
  entity_field_field_email          → email
  entity_field_field_hours          → human-readable hours
  entity_field_field_food_assistance_type → "Choice Pantry, Pre-Packed, ..."
  entity_field_field_accessibility  → "Walk-in", "Appointment Required", ...
  entity_field_field_languages      → "Spanish, Amharic, ..."
  entity_field_field_special_features → "Delivery, Fresh Produce, ..."
  entity_field_post_content         → free-text description
"""
import re
from bs4 import BeautifulSoup
from src.validators.schemas import RawRecord

ZIP_RE = re.compile(r"\b\d{5}\b")

# ── Taxonomy mappings ─────────────────────────────────────────────────────────

_TYPE_TO_SERVICE: dict[str, str] = {
    "choice pantry":       "food_pantry",
    "pre-packed pantry":   "food_pantry",
    "pantry":              "food_pantry",
    "prepared meals":      "hot_meals",
    "mobile market":       "mobile_pantry",
}

_ACCESS_TO_REQ: dict[str, str] = {
    "appointment required":    "appointment_required",
    "walk-in":                 "walk_in",
    "walk in":                 "walk_in",
    "documentation required":  "photo_id",
    "id required":             "photo_id",
    "no id":                   "no_id_required",
}

_LANG_NORM: dict[str, str] = {
    "spanish": "Spanish", "french": "French", "amharic": "Amharic",
    "arabic": "Arabic", "chinese": "Chinese", "mandarin": "Chinese",
    "cantonese": "Chinese", "korean": "Korean", "vietnamese": "Vietnamese",
    "portuguese": "Portuguese", "russian": "Russian", "urdu": "Urdu",
    "bengali": "Bengali", "haitian creole": "Haitian Creole",
    "tigrinya": "Tigrinya", "farsi": "Farsi", "persian": "Farsi",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _field(card, data_name: str) -> str | None:
    """Extract text from a DRTS field by its full data-name attribute value."""
    el = card.select_one(f'[data-name="{data_name}"]')
    if not el:
        return None
    text = el.get_text(" ", strip=True)
    return text if text and text.lower() != "none" else None


def _field_link(card, data_name: str) -> str | None:
    """Extract the href from the first <a> inside a DRTS field."""
    el = card.select_one(f'[data-name="{data_name}"] a[href]')
    if not el:
        return None
    href = el.get("href", "")
    return href if href.startswith("http") else None


def _format_phone(raw: str) -> str | None:
    """Format bare digits or messy phone into (XXX) XXX-XXXX."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return None


def _clean_address(addr: str) -> tuple[str | None, str | None]:
    """Remove distance suffix ('1.25 mi') and extract ZIP (last 5-digit match)."""
    addr = re.sub(r"\s+\d+\.\d+\s+mi\s*$", "", addr).strip()
    # Use the LAST 5-digit number — ZIP comes after the street number
    all_zips = ZIP_RE.findall(addr)
    zip_code = all_zips[-1] if all_zips else None
    return (addr or None), zip_code


def _classify_comma_list(raw: str | None, mapping: dict[str, str]) -> list[str]:
    """Split a comma-separated field and map each value via a lookup table."""
    if not raw:
        return []
    out: list[str] = []
    for part in raw.lower().split(","):
        part = part.strip()
        for key, val in mapping.items():
            if key in part and val not in out:
                out.append(val)
    return out


def _classify_food_types(type_str: str | None, features: str | None) -> list[str]:
    combined = f"{type_str or ''} {features or ''}".lower()
    types: list[str] = []
    if "produce" in combined or "fresh" in combined:
        types.append("produce")
    if "canned" in combined or "non-perishable" in combined:
        types.append("canned_goods")
    if "prepared" in combined or "meal" in combined:
        types.append("protein")
    if "baby" in combined or "infant" in combined or "formula" in combined:
        types.append("baby_supplies")
    if "dairy" in combined:
        types.append("dairy")
    if "bread" in combined or "bakery" in combined:
        types.append("bread_bakery")
    return types


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_mocofood(content: str | bytes, source_id: str) -> list[RawRecord]:
    html = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    records: list[RawRecord] = []

    # Primary: DRTS structured cards
    cards = soup.select(".directory-listing-main")

    for card in cards:
        # ── Name ──────────────────────────────────────────────────────────
        name = _field(card, "entity_field_post_title")
        if not name or len(name) < 3 or len(name) > 200:
            continue

        # ── Address + ZIP ─────────────────────────────────────────────────
        addr_raw = _field(card, "entity_field_location_address")
        address, zip_code = _clean_address(addr_raw) if addr_raw else (None, None)

        # ── Phone ─────────────────────────────────────────────────────────
        phone_raw = _field(card, "entity_field_field_phone")
        phone = _format_phone(phone_raw) if phone_raw else None

        # ── Website (prefer <a> href over display text) ───────────────────
        website = _field_link(card, "entity_field_field_website") or _field(card, "entity_field_field_website")

        # ── Hours ─────────────────────────────────────────────────────────
        hours = _field(card, "entity_field_field_hours")

        # ── Structured taxonomy fields ────────────────────────────────────
        type_raw    = _field(card, "entity_field_field_food_assistance_type")
        access_raw  = _field(card, "entity_field_field_accessibility")
        lang_raw    = _field(card, "entity_field_field_languages")
        features    = _field(card, "entity_field_field_special_features")
        description = _field(card, "entity_field_post_content")

        services     = _classify_comma_list(type_raw, _TYPE_TO_SERVICE) or ["food_pantry"]
        requirements = _classify_comma_list(access_raw, _ACCESS_TO_REQ)
        food_types   = _classify_food_types(type_raw, features)
        languages    = _classify_comma_list(lang_raw, _LANG_NORM)

        # "Delivery" in features → add delivery service
        if features and "delivery" in features.lower() and "delivery" not in services:
            services.append("delivery")

        # ── Build rich raw_text for downstream LLM enrichment ─────────────
        parts = [name]
        if address:     parts.append(f"Address: {address}")
        if phone:       parts.append(f"Phone: {phone}")
        if website:     parts.append(f"Website: {website}")
        if hours:       parts.append(f"Hours: {hours}")
        if type_raw:    parts.append(f"Type: {type_raw}")
        if access_raw:  parts.append(f"Accessibility: {access_raw}")
        if lang_raw:    parts.append(f"Languages: {lang_raw}")
        if features:    parts.append(f"Features: {features}")
        if description: parts.append(description)
        raw_text = " | ".join(parts)

        try:
            records.append(RawRecord(
                source_id=source_id,
                name=name,
                address=address,
                zip=zip_code,
                phone=phone,
                website=website,
                hours=hours,
                food_types=food_types or None,
                requirements=requirements or None,
                services=services,
                languages=languages or None,
                raw_text=raw_text,
            ))
        except Exception:
            pass

    return records
