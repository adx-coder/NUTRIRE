import re
from bs4 import BeautifulSoup
from src.validators.schemas import RawRecord

PHONE_RE  = re.compile(r"(?:\+1[\-.\s]?)?\(?\d{3}\)?[\-.\s]\d{3}[\-.\s]\d{4}")
ADDR_RE   = re.compile(
    r"\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Za-z0-9\s.,\'#\-]{3,50}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl|Terrace|Ter|Circle|Cir|Highway|Hwy|Pkwy|Parkway)\.?",
    re.IGNORECASE,
)
HOURS_RE  = re.compile(
    r"(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
    r"[\s,\u2013\-]+\d{1,2}(?::\d{2})?\s*[ap]m\s*[\-\u2013to]+\s*\d{1,2}(?::\d{2})?\s*[ap]m",
    re.IGNORECASE,
)
ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")


def _phone(text: str) -> str | None:
    m = PHONE_RE.search(text)
    return m.group().strip() if m else None


def _address(text: str) -> str | None:
    m = ADDR_RE.search(text)
    return m.group().strip() if m else None


def _zip(text: str) -> str | None:
    m = ZIP_RE.search(text)
    return m.group() if m else None


def _hours(text: str) -> str | None:
    matches = HOURS_RE.findall(text)
    return "; ".join(matches) if matches else None


def scrape_generic_html(content: str | bytes, source_id: str) -> list[RawRecord]:
    html = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["nav", "footer", "script", "style", "header"]):
        tag.decompose()

    records: list[RawRecord] = []

    # Strategy 1: heading + following siblings
    for heading in soup.find_all(["h2", "h3", "h4"]):
        name = heading.get_text(strip=True)
        if not name or len(name) > 120:
            continue
        body_parts: list[str] = []
        sib = heading.find_next_sibling()
        depth = 0
        while sib and depth < 5:
            if sib.name in ("h2", "h3", "h4"):
                break
            body_parts.append(sib.get_text(" ", strip=True))
            sib = sib.find_next_sibling()
            depth += 1
        body = " ".join(body_parts)
        raw_text = f"{name} {body}"
        phone, address, zip_ = _phone(raw_text), _address(raw_text), _zip(raw_text)
        if not phone and not address:
            continue
        try:
            records.append(RawRecord(source_id=source_id, name=name, address=address,
                                     zip=zip_, phone=phone, hours=_hours(raw_text), raw_text=raw_text))
        except Exception:
            pass

    # Strategy 2: table rows
    for row in soup.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 2:
            continue
        row_text = " ".join(cells)
        phone, address = _phone(row_text), _address(row_text)
        if not cells[0] or (not phone and not address):
            continue
        try:
            records.append(RawRecord(source_id=source_id, name=cells[0],
                                     address=address, phone=phone, raw_text=row_text))
        except Exception:
            pass

    # Strategy 3: list items
    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)
        if len(text) < 15 or len(text) > 400:
            continue
        phone, address = _phone(text), _address(text)
        if not phone and not address:
            continue
        name = re.split(r"[,\n\u2014\u2013]", text)[0].strip()
        if not name or len(name) > 100:
            continue
        try:
            records.append(RawRecord(source_id=source_id, name=name,
                                     address=address, phone=phone, raw_text=text))
        except Exception:
            pass

    return records
