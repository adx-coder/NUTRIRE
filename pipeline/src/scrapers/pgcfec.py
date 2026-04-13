import re
from bs4 import BeautifulSoup
from src.validators.schemas import RawRecord

PHONE_RE = re.compile(r"(?:\+1[\-.\s]?)?\(?\d{3}\)?[\-.\s]\d{3}[\-.\s]\d{4}")
ADDR_RE  = re.compile(
    r"\d{1,5}\s+[A-Za-z0-9\s.,\'#\-]{3,50}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl|Pkwy|Terrace|Ter)\.?",
    re.IGNORECASE,
)
ZIP_RE   = re.compile(r"\b\d{5}\b")
HOURS_RE = re.compile(
    r"(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
    r"[\s,\u2013\-]+\d{1,2}(?::\d{2})?\s*[ap]m",
    re.IGNORECASE,
)
NAV_HEADINGS = re.compile(r"^(find food|resources|about|contact|home|menu|services|programs)$", re.I)


def scrape_pgcfec(content: str | bytes, source_id: str) -> list[RawRecord]:
    html = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one(".entry-content, .page-content, article, main") or soup.body
    records: list[RawRecord] = []

    for heading in root.find_all(["h2", "h3", "h4"]):
        name = heading.get_text(strip=True)
        if not name or len(name) < 3 or len(name) > 150 or NAV_HEADINGS.match(name):
            continue

        lines: list[str] = []
        sib = heading.find_next_sibling()
        depth = 0
        while sib and depth < 8:
            if sib.name in ("h2", "h3", "h4"):
                break
            lines.append(sib.get_text(" ", strip=True))
            sib = sib.find_next_sibling()
            depth += 1

        body = " ".join(lines)
        raw_text = f"{name} {body}"

        phone_m = PHONE_RE.search(raw_text)
        addr_m  = ADDR_RE.search(raw_text)
        zip_m   = ZIP_RE.search(raw_text)
        hours_m = HOURS_RE.search(raw_text)
        url_m   = re.search(r"https?://[^\s)>\"']+", body)

        food_types = [ft for pattern, ft in [
            (r"produce|vegetable|fruit", "produce"),
            (r"canned|non-perishable", "canned_goods"),
            (r"hot meal|prepared|cooked", "prepared_meals"),
            (r"baby|infant|formula", "baby_supplies"),
        ] if re.search(pattern, raw_text, re.I)]

        requirements = [req for pattern, req in [
            (r"photo id|government.?issued", "photo_id"),
            (r"no id", "no_id_required"),
            (r"appointment", "appointment_required"),
            (r"walk.?in", "walk_in"),
            (r"proof of address", "proof_of_address"),
        ] if re.search(pattern, raw_text, re.I)]

        try:
            records.append(RawRecord(
                source_id=source_id, name=name,
                address=addr_m.group().strip() if addr_m else None,
                zip=zip_m.group() if zip_m else None,
                phone=phone_m.group().strip() if phone_m else None,
                website=url_m.group() if url_m else None,
                hours=hours_m.group() if hours_m else None,
                food_types=food_types or None,
                requirements=requirements or None,
                services=["food_pantry"], raw_text=raw_text,
            ))
        except Exception:
            pass

    return records
