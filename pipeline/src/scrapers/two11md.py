"""
Scraper for 211 Maryland food pantry search.
Source: https://search.211md.org/search?query=food+pantry

Next.js app with SSR-rendered Tailwind cards (.bg-card). Pagination is
"Next" button driven. Uses Playwright to click through all ~21 pages
(~505 results, 25 per page). Falls back to SSR HTML (page 1 only)
if Playwright is unavailable.

Each card contains:
  a[data-testid="resource-link"]   -> org name + detail link
  p (near map-pin icon)            -> address (City, ST ZIPCODE format)
  a[href^="tel:"]                  -> phone
  a[href^="http"] (non-211)        -> website
  div.font-normal p                -> description
  a.border-border                  -> service taxonomy tags
"""
import re
import time
from bs4 import BeautifulSoup
from src.validators.schemas import RawRecord

ZIP_RE = re.compile(r"\b\d{5}\b")
ADDR_RE = re.compile(
    r"\d{1,5}\s+[A-Za-z0-9\s.,\'#\-]{3,60},\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s+\d{5}",
    re.IGNORECASE,
)
_DMV_STATE_RE = re.compile(r",\s*(MD|DC|VA)\s+\d{5}")


def _parse_cards_from_html(html: str, source_id: str, seen: set[str]) -> list[RawRecord]:
    """Parse .bg-card elements from HTML. Returns new records not in `seen`."""
    soup = BeautifulSoup(html, "lxml")
    records = []

    for card in soup.select(".bg-card"):
        # Name
        name_el = card.select_one('a[data-testid="resource-link"]')
        if not name_el:
            name_el = card.select_one("a.text-xl")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 3 or name in seen:
            continue

        raw_text = card.get_text(" ", strip=True)

        # Address
        address = None
        for p in card.find_all("p"):
            p_text = p.get_text(strip=True)
            if ADDR_RE.search(p_text):
                address = p_text
                break
        if not address:
            m = ADDR_RE.search(raw_text)
            if m:
                address = m.group().strip()

        # Filter to DMV only
        if address and not _DMV_STATE_RE.search(address):
            continue

        # ZIP (last match)
        zip_code = None
        if address:
            all_zips = ZIP_RE.findall(address)
            zip_code = all_zips[-1] if all_zips else None

        # Phone
        tel_el = card.find("a", href=re.compile(r"^tel:"))
        phone = tel_el.get_text(strip=True) if tel_el else None

        # Website (skip internal 211 links)
        website = None
        for a in card.find_all("a", href=re.compile(r"^https?://")):
            href = a["href"]
            if "211md.org" in href or "search.211" in href:
                continue
            website = href
            break

        # Description
        desc_el = card.select_one("div.font-normal p")
        description = None
        if desc_el:
            desc_text = desc_el.get_text(" ", strip=True)
            if len(desc_text) > 30:
                description = desc_text

        # Tags
        tag_links = card.select("a.border-border")
        tag_texts = [t.get_text(strip=True).lower() for t in tag_links]

        services: list[str] = []
        if any("pantry" in t or "food bank" in t for t in tag_texts):
            services.append("food_pantry")
        if any("meal" in t or "soup" in t or "congregate" in t for t in tag_texts):
            services.append("hot_meals")
        if any("mobile" in t for t in tag_texts):
            services.append("mobile_pantry")
        if any("delivery" in t or "home delivered" in t for t in tag_texts):
            services.append("delivery")
        if any("snap" in t or "food stamp" in t for t in tag_texts):
            services.append("snap_assistance")
        if not services:
            services.append("food_pantry")

        # Food types from description
        food_types: list[str] = []
        combined = f"{description or ''} {raw_text}".lower()
        if "produce" in combined or "fresh" in combined or "fruit" in combined:
            food_types.append("produce")
        if "canned" in combined or "nonperishable" in combined:
            food_types.append("canned_goods")
        if "prepared" in combined or "hot meal" in combined:
            food_types.append("protein")

        # Build raw text
        parts = [name]
        if address: parts.append(f"Address: {address}")
        if phone: parts.append(f"Phone: {phone}")
        if website: parts.append(f"Website: {website}")
        if description: parts.append(description)
        if tag_texts: parts.append(f"Tags: {', '.join(tag_texts)}")
        full_raw = " | ".join(parts)

        seen.add(name)
        try:
            records.append(RawRecord(
                source_id=source_id,
                name=name,
                address=address,
                zip=zip_code,
                phone=phone,
                website=website,
                services=services,
                food_types=food_types or None,
                raw_text=full_raw,
            ))
        except Exception:
            pass

    return records


def _scrape_211(search_url: str, source_id: str, content: str | bytes) -> list[RawRecord]:
    """
    Generic 211 scraper. Uses Playwright to paginate through all pages.
    Falls back to parsing SSR page 1 from `content`.
    """
    records: list[RawRecord] = []
    seen: set[str] = set()

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(search_url, timeout=30000)
            page.wait_for_selector(".bg-card", timeout=10000)

            for _ in range(25):  # Safety cap
                html = page.content()
                new_recs = _parse_cards_from_html(html, source_id, seen)
                records.extend(new_recs)

                if not new_recs:
                    break

                # Click Next
                next_btn = page.query_selector('button:has-text("Next"), a:has-text("Next")')
                if not next_btn:
                    break
                next_btn.click()
                time.sleep(2)
                try:
                    page.wait_for_selector(".bg-card", timeout=10000)
                except Exception:
                    break

            browser.close()

    except ImportError:
        # Playwright not installed — parse initial content only
        html = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
        records = _parse_cards_from_html(html, source_id, seen)

    return records


def scrape_two11md(content: str | bytes, source_id: str) -> list[RawRecord]:
    """Scrape 211 Maryland food pantry search results."""
    return _scrape_211(
        "https://search.211md.org/search?query=food+pantry",
        source_id, content,
    )


def scrape_two11va(content: str | bytes, source_id: str) -> list[RawRecord]:
    """Scrape 211 Virginia food pantry search results."""
    return _scrape_211(
        "https://search.211virginia.org/search?query=food+pantry",
        source_id, content,
    )
