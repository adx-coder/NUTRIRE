"""
Scraper for Capital Area Food Bank — Active Agencies.
Source: ArcGIS FeatureServer behind https://www.capitalareafoodbank.org/find-food-assistance/

The food finder is an ArcGIS Web AppBuilder widget. We load it in Playwright,
then use fetch() from within the browser to query the feature service API
(bypasses TLS/CORS issues). Returns ~382 partner agencies with:
  name, address, city, state, zip, phone, email, lat/lng,
  per-day structured hours, appointment flags, residency requirements.
"""
import json
import re
from src.validators.schemas import RawRecord

_FEATURE_URL = (
    "https://services.arcgis.com/oCjyzxNy34f0pJCV/arcgis/rest/services/"
    "Active_Agencies_Last_45_Days/FeatureServer/0/query"
)
_ARCGIS_APP = (
    "https://www.arcgis.com/apps/webappviewer/index.html"
    "?id=eda83bc6f90144ce8934d35972f63832"
)

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DAY_SHORT = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
              "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}


def _build_hours_string(attrs: dict) -> str | None:
    """Assemble per-day hours into a single human-readable string."""
    parts = []
    for day in _DAYS:
        h = attrs.get(f"Hours_{day}")
        if h:
            h = h.replace("\r\n", "; ").strip()
            parts.append(f"{_DAY_SHORT[day]}: {h}")
    return ", ".join(parts) if parts else None


def _extract_requirements(attrs: dict) -> list[str]:
    """Extract requirements from appointment/residency/reqs fields."""
    reqs: list[str] = []

    has_appt = any(
        str(attrs.get(f"ByAppointmentOnly_{d}", "")).lower() == "yes"
        for d in _DAYS
    )
    has_walkin = any(
        str(attrs.get(f"ByAppointmentOnly_{d}", "")).lower() == "no"
        for d in _DAYS
    )
    has_residency = any(
        str(attrs.get(f"ResidentsOnly_{d}", "")).lower() == "yes"
        for d in _DAYS
    )

    if has_appt:
        reqs.append("appointment_required")
    if has_walkin:
        reqs.append("walk_in")
    if has_residency:
        reqs.append("proof_of_address")

    # Check Reqs_ fields for ID requirements
    for d in _DAYS:
        r = str(attrs.get(f"Reqs_{d}") or "").lower()
        if "id" in r and "no_id_required" not in reqs and "photo_id" not in reqs:
            reqs.append("photo_id")
        if "no id" in r and "no_id_required" not in reqs:
            reqs.append("no_id_required")

    return reqs


def _extract_languages(attrs: dict) -> list[str]:
    """Infer languages from notes fields."""
    langs: list[str] = []
    all_notes = " ".join(str(attrs.get(f"Notes_{d}") or "") for d in _DAYS).lower()
    if "spanish" in all_notes or "espanol" in all_notes:
        langs.append("Spanish")
    if "amharic" in all_notes:
        langs.append("Amharic")
    if "french" in all_notes:
        langs.append("French")
    if "arabic" in all_notes:
        langs.append("Arabic")
    if "chinese" in all_notes or "mandarin" in all_notes:
        langs.append("Chinese")
    if "korean" in all_notes:
        langs.append("Korean")
    return langs


def _fetch_features_playwright() -> list[dict]:
    """Fetch all features using Playwright to bypass TLS/CORS."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    import time
    features = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(_ARCGIS_APP, timeout=60000)
        time.sleep(5)

        result = page.evaluate('''async () => {
            const url = ''' + json.dumps(_FEATURE_URL) + ''';
            const params = new URLSearchParams({
                where: '1=1',
                outFields: '*',
                f: 'json',
                resultRecordCount: '2000',
                resultOffset: '0'
            });
            try {
                const resp = await fetch(url + '?' + params.toString());
                const data = await resp.json();
                return data.features || [];
            } catch(e) {
                return [];
            }
        }''')

        features = result if isinstance(result, list) else []
        browser.close()

    return features


def scrape_cafb(content: str | bytes, source_id: str) -> list[RawRecord]:
    """
    Scrape CAFB partner agencies via ArcGIS feature service.
    The `content` arg (initial HTML) is ignored -- we query the API directly.
    """
    features = _fetch_features_playwright()
    records: list[RawRecord] = []

    for feat in features:
        attrs = feat.get("attributes", {})
        name = attrs.get("name")
        if not name or len(name) < 3:
            continue

        address = attrs.get("address1", "")
        city = attrs.get("city", "")
        state = attrs.get("state", "")
        zip_code = attrs.get("zip", "")

        full_address = f"{address}, {city}, {state} {zip_code}".strip(", ")
        phone = attrs.get("phone")
        email = attrs.get("email")

        hours = _build_hours_string(attrs)
        requirements = _extract_requirements(attrs)
        languages = _extract_languages(attrs)

        # TEFAP status
        tefap = attrs.get("tefap", "")
        services = ["food_pantry"]
        if tefap and "tefap" in tefap.lower():
            services.append("snap_assistance")

        # Build raw text for downstream enrichment
        parts = [name]
        if full_address: parts.append(f"Address: {full_address}")
        if phone: parts.append(f"Phone: {phone}")
        if email: parts.append(f"Email: {email}")
        if hours: parts.append(f"Hours: {hours}")
        if tefap: parts.append(f"TEFAP: {tefap}")
        for day in _DAYS:
            note = attrs.get(f"Notes_{day}")
            if note:
                parts.append(f"{_DAY_SHORT[day]} notes: {note}")
            req = attrs.get(f"Reqs_{day}")
            if req:
                parts.append(f"{_DAY_SHORT[day]} reqs: {req}")
        raw_text = " | ".join(parts)

        try:
            records.append(RawRecord(
                source_id=source_id,
                name=name,
                address=full_address or None,
                city=city or None,
                state=state or None,
                zip=zip_code or None,
                phone=phone,
                website=None,
                hours=hours,
                services=services,
                requirements=requirements or None,
                languages=languages or None,
                raw_text=raw_text,
            ))
        except Exception:
            pass

    return records
