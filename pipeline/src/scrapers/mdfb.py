"""
Scraper for Maryland Food Bank — Find Food page.
Source: https://mdfoodbank.org/find-food/

The page uses GeoMyWP plugin with AJAX-paginated results (10 per page, ~29 pages).
Site is behind Cloudflare, and pagination is JS-only (no URL params).
We use Playwright headless Chrome to click through all pages.

Each card is `.gmw-single-item` containing:
  h3.gmw-item-title            -> org name
  .gmw-item-address a          -> full address (Google Maps link text)
  .gmw-location-meta li        -> key/value pairs: website, phone, etc.
"""
import re
import time
from bs4 import BeautifulSoup
from src.validators.schemas import RawRecord

ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")


def _parse_card(card, source_id: str) -> RawRecord | None:
    """Parse a single .gmw-single-item card into a RawRecord."""
    title_el = card.select_one(".gmw-item-title")
    if not title_el:
        return None
    name = title_el.get_text(strip=True)
    if not name or len(name) < 3 or len(name) > 200:
        return None

    # Address from the Google Maps link
    addr_el = card.select_one(".gmw-item-address a")
    address = addr_el.get_text(strip=True) if addr_el else None
    if address:
        address = re.sub(r"\s+USA\s*$", "", address).strip()

    # Extract ZIP (last match — avoids street number)
    zip_code = None
    if address:
        all_zips = ZIP_RE.findall(address)
        zip_code = all_zips[-1][:5] if all_zips else None

    # Meta fields
    meta: dict[str, str] = {}
    for li in card.select(".gmw-location-meta li"):
        label_el = li.select_one(".label")
        info_el = li.select_one(".info")
        if label_el and info_el:
            key = label_el.get_text(strip=True).rstrip(":").strip().lower()
            val = info_el.get_text(strip=True)
            if val:
                meta[key] = val

    phone = meta.get("phone")
    website = meta.get("website")
    hours = meta.get("hours") or meta.get("schedule") or meta.get("distribution hours")

    if website and not website.startswith("http"):
        website = "https://" + website

    # Build raw text
    parts = [name]
    if address: parts.append(f"Address: {address}")
    if phone: parts.append(f"Phone: {phone}")
    if website: parts.append(f"Website: {website}")
    if hours: parts.append(f"Hours: {hours}")
    for k, v in meta.items():
        if k not in ("phone", "website", "hours", "schedule", "distribution hours"):
            parts.append(f"{k}: {v}")
    raw_text = " | ".join(parts)

    try:
        return RawRecord(
            source_id=source_id,
            name=name,
            address=address,
            zip=zip_code,
            phone=phone,
            website=website,
            hours=hours,
            services=["food_pantry"],
            raw_text=raw_text,
        )
    except Exception:
        return None


def scrape_mdfb(content: str | bytes, source_id: str) -> list[RawRecord]:
    """
    Scrape all MDFB food pantry listings using Playwright for JS pagination.
    Falls back to parsing just the initial HTML if Playwright is unavailable.
    """
    records: list[RawRecord] = []
    seen_names: set[str] = set()

    def _add_cards_from_html(html: str) -> int:
        """Parse cards from HTML, add new ones to records. Returns count added."""
        soup = BeautifulSoup(html, "lxml")
        added = 0
        for card in soup.select(".gmw-single-item"):
            rec = _parse_card(card, source_id)
            if rec and rec.name not in seen_names:
                seen_names.add(rec.name)
                records.append(rec)
                added += 1
        return added

    # Try Playwright for full pagination
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://mdfoodbank.org/find-food/", timeout=30000)
            page.wait_for_selector(".gmw-single-item", timeout=10000)

            for _ in range(35):  # Safety cap
                html = page.content()
                added = _add_cards_from_html(html)

                # Click Next if available
                next_btn = page.query_selector(".gmw-pagination .next")
                if not next_btn:
                    break
                next_btn.click()
                time.sleep(1.5)
                try:
                    page.wait_for_selector(".gmw-single-item", timeout=10000)
                except Exception:
                    break

            browser.close()

    except ImportError:
        # Playwright not installed — parse initial content only
        html = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
        _add_cards_from_html(html)

    return records
