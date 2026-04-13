"""
Stage 1 -- Scrape only.

Fetches each enabled source and runs its scraper.
CAFB, MDFB, and two11md use Playwright internally for JS-rendered pagination.
Disables pgcfec (iframe-only, no scrapable org data).
Saves raw records to output/stage1_raw_records.json for inspection.

Usage:
  cd pipeline
  source .venv/Scripts/activate
  python scripts/stage1_scrape.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import SOURCES
from src.scrapers import SCRAPER_REGISTRY

OUTPUT = Path(__file__).resolve().parents[1] / "output" / "stage1_raw_records.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Sources to skip (iframe-only pages with no scrapable org data)
SKIP_SOURCES = {"pgcfec"}

# Sources that handle their own fetching internally (Playwright-based scrapers)
# These scrapers ignore the `content` argument and fetch pages themselves.
SELF_FETCH_SOURCES = {"cafb", "mdfb", "two11md", "two11va"}


def _fetch(url: str) -> bytes | None:
    """Fetch URL content. Try curl_cffi first, then httpx."""
    try:
        from curl_cffi import requests as cf_requests
        resp = cf_requests.get(url, impersonate="chrome", timeout=30)
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass

    import httpx
    headers = {"User-Agent": "Nutrire-Pipeline/1.0 (food-resource-aggregator)"}
    resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    return resp.content


def main():
    all_records = []
    source_stats = {}

    for src in SOURCES:
        if not src.enabled:
            continue

        if src.id in SKIP_SOURCES:
            print(f"\n[{src.id}] SKIPPED (iframe-only, no org data)")
            source_stats[src.id] = {"status": "skipped", "reason": "iframe-only", "count": 0}
            continue

        scraper_key = src.scraper
        scraper = SCRAPER_REGISTRY.get(scraper_key) or SCRAPER_REGISTRY.get("generic-html")

        is_self_fetch = scraper_key in SELF_FETCH_SOURCES

        if is_self_fetch:
            # Scraper handles fetching internally (Playwright pagination)
            print(f"\n[{src.id}] Scraping with Playwright (self-fetch) ...")
            content = b""  # Scraper ignores this
        else:
            print(f"\n[{src.id}] Fetching {src.url} ...")
            try:
                content = _fetch(src.url)
                if content is None:
                    raise RuntimeError("Fetch returned None")
                print(f"  {len(content)} bytes")
            except Exception as exc:
                print(f"  FETCH ERROR: {exc}")
                source_stats[src.id] = {"status": "fetch_error", "error": str(exc), "count": 0}
                continue

        t0 = time.time()
        try:
            records = scraper(content, src.id)
        except Exception as exc:
            print(f"  SCRAPER ERROR: {exc}")
            source_stats[src.id] = {"status": "scraper_error", "error": str(exc), "count": 0}
            continue
        elapsed = time.time() - t0

        # Convert to dicts
        record_dicts = [r.model_dump(exclude_none=True) for r in records]
        all_records.extend(record_dicts)

        # Stats
        has_addr = sum(1 for d in record_dicts if d.get("address"))
        has_phone = sum(1 for d in record_dicts if d.get("phone"))
        has_hours = sum(1 for d in record_dicts if d.get("hours"))
        has_zip = sum(1 for d in record_dicts if d.get("zip"))
        has_web = sum(1 for d in record_dicts if d.get("website"))
        has_lang = sum(1 for d in record_dicts if d.get("languages"))

        source_stats[src.id] = {
            "status": "ok",
            "count": len(record_dicts),
            "has_address": has_addr,
            "has_phone": has_phone,
            "has_hours": has_hours,
            "has_zip": has_zip,
            "has_website": has_web,
            "has_languages": has_lang,
            "elapsed_s": round(elapsed, 1),
        }
        print(f"  {len(record_dicts)} records in {elapsed:.1f}s  (addr={has_addr} phone={has_phone} hours={has_hours} zip={has_zip} web={has_web} lang={has_lang})")

    # Save
    output_data = {
        "stats": source_stats,
        "total": len(all_records),
        "records": all_records,
    }
    OUTPUT.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"SAVED {len(all_records)} records to {OUTPUT}")
    print(f"{'='*60}")
    print(f"\nPer-source breakdown:")
    for sid, s in source_stats.items():
        status = s["status"]
        count = s.get("count", 0)
        if status == "ok":
            t = s.get("elapsed_s", 0)
            print(f"  OK  {sid}: {count} records in {t}s  (addr={s['has_address']} phone={s['has_phone']} hours={s['has_hours']})")
        elif status == "skipped":
            print(f"  --  {sid}: skipped ({s.get('reason', '')})")
        else:
            print(f"  ERR {sid}: {status}")


if __name__ == "__main__":
    main()
