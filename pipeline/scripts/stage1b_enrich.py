"""
Stage 1b -- Enrich 1,518 raw records to competition quality.

Three steps:
  Step 1: Batch-scrape org websites for hours + content (Playwright async)
  Step 2: Mistral LLM enrichment (function calling, ministral-8b)
  Step 3: Template fallback for any remaining gaps

Usage:
  cd pipeline
  source .venv/Scripts/activate
  python scripts/stage1b_enrich.py                    # full run
  python scripts/stage1b_enrich.py --limit 5          # test 5 records
  python scripts/stage1b_enrich.py --skip-scrape      # skip website scraping
  python scripts/stage1b_enrich.py --skip-llm         # skip LLM, template only
  python scripts/stage1b_enrich.py --dry-run           # show counts only
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ── Paths ─────────────────────────────────────────────────────────────────────

PIPELINE  = Path(__file__).resolve().parents[1]
INPUT     = PIPELINE / "output" / "stage1_raw_records.json"
OUTPUT    = PIPELINE / "output" / "stage1b_enriched_records.json"
STATE_DIR = PIPELINE / "state"
LOG_DIR   = PIPELINE / "logs"
WEB_CACHE = STATE_DIR / "website-cache.json"
LLM_CACHE = STATE_DIR / "stage1b-enrichment-cache.json"

for d in [STATE_DIR, LOG_DIR, OUTPUT.parent]:
    d.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def _jsonl_log(path: Path, entry: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

WEB_LOG = LOG_DIR / "website_scrape.jsonl"
LLM_LOG = LOG_DIR / "llm_enrichment.jsonl"
TPL_LOG = LOG_DIR / "template_fills.jsonl"

# ── Cache helpers ─────────────────────────────────────────────────────────────

def _load_cache(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_cache(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

# ── Hours regex ───────────────────────────────────────────────────────────────

HOURS_RE = re.compile(
    r"(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
    r"[\s,\u2013\-:]+\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)",
    re.IGNORECASE,
)
HOURS_BLOCK_RE = re.compile(
    r"hours?\s*(?:of\s*operation)?[\s:]+(.{20,300})",
    re.IGNORECASE,
)

# ── Step 0: URL dedup ────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    url = url.lower().rstrip("/")
    url = re.sub(r"^https?://(?:www\.)?", "https://", url)
    return url

def dedup_urls(records: list[dict]) -> dict[str, list[int]]:
    """Map normalized URL -> [record indices]."""
    url_map: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        url = rec.get("website")
        if not url:
            continue
        norm = _normalize_url(url)
        url_map.setdefault(norm, []).append(i)
    return url_map

# ── Step 1: Website scraping ─────────────────────────────────────────────────

async def _scrape_one(browser, sem, url: str, orig_url: str, cache: dict) -> dict:
    """Scrape a single URL. Returns cache entry."""
    norm = _normalize_url(url)
    if norm in cache and cache[norm].get("status") == "ok":
        return cache[norm]

    t0 = time.time()
    entry = {"url": orig_url, "norm_url": norm, "status": "error",
             "body_text": None, "hours_found": None,
             "donate_url": None, "volunteer_url": None, "fetched_at": _ts()}

    async with sem:
        page = None
        try:
            page = await browser.new_page()
            await page.goto(orig_url, timeout=15000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            body = await page.inner_text("body")
            body = body[:5000]
            entry["body_text"] = body
            entry["status"] = "ok"
            entry["bytes"] = len(body)

            # Extract hours via regex
            hours_m = HOURS_RE.search(body)
            if not hours_m:
                hours_m = HOURS_BLOCK_RE.search(body)
            entry["hours_found"] = hours_m.group().strip() if hours_m else None

            # Check for donate/volunteer links
            donate_els = await page.query_selector_all('a[href*="donat"], a[href*="give"], a[href*="contribut"]')
            for el in donate_els[:1]:
                href = await el.get_attribute("href")
                if href and href.startswith("http"):
                    entry["donate_url"] = href
                    break

            volunteer_els = await page.query_selector_all('a[href*="volunt"], a[href*="signup"], a[href*="sign-up"]')
            for el in volunteer_els[:1]:
                href = await el.get_attribute("href")
                if href and href.startswith("http"):
                    entry["volunteer_url"] = href
                    break

        except Exception as exc:
            err_type = type(exc).__name__
            if "timeout" in err_type.lower() or "timeout" in str(exc).lower():
                entry["status"] = "timeout"
            elif "ssl" in str(exc).lower() or "cert" in str(exc).lower():
                entry["status"] = "ssl_error"
            else:
                entry["status"] = f"error:{err_type}"
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    latency = int((time.time() - t0) * 1000)
    entry["latency_ms"] = latency
    cache[norm] = entry

    _jsonl_log(WEB_LOG, {"ts": _ts(), "url": orig_url, "status": entry["status"],
                         "bytes": entry.get("bytes", 0),
                         "hours_found": bool(entry["hours_found"]),
                         "donate_found": bool(entry["donate_url"]),
                         "latency_ms": latency})
    return entry


async def scrape_websites(url_map: dict[str, list[int]], records: list[dict], cache: dict):
    """Scrape all unique URLs with 5 concurrent tabs."""
    from playwright.async_api import async_playwright

    total = len(url_map)
    sem = asyncio.Semaphore(5)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        tasks = []
        for norm_url, indices in url_map.items():
            orig_url = records[indices[0]].get("website", norm_url)
            tasks.append(_scrape_one(browser, sem, norm_url, orig_url, cache))

        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 50 == 0:
                print(f"  Website scrape: {done}/{total} done")

        await browser.close()

    ok = sum(1 for v in cache.values() if v.get("status") == "ok")
    timeout = sum(1 for v in cache.values() if v.get("status") == "timeout")
    err = sum(1 for v in cache.values() if "error" in (v.get("status") or ""))
    hrs = sum(1 for v in cache.values() if v.get("hours_found"))
    don = sum(1 for v in cache.values() if v.get("donate_url"))
    vol = sum(1 for v in cache.values() if v.get("volunteer_url"))
    print(f"  Website scrape done: {ok} ok, {timeout} timeout, {err} error")
    print(f"  Hours found: {hrs}, Donate links: {don}, Volunteer links: {vol}")


# ── Step 2: Mistral LLM enrichment ───────────────────────────────────────────

SYSTEM_PROMPT = """You are extracting structured data from food assistance organizations in the Washington DC / Maryland / Virginia area.

RULES:
1. Only extract hours_raw if the text explicitly states operating hours. NEVER guess or invent hours.
2. For services/food_types/requirements/languages: only tag what the text clearly supports.
3. heroCopy must be warm, dignity-first, 10-20 words. Never use these words: needy, eligible, recipient, beneficiary, handout, charity case, underprivileged, less fortunate.
4. firstVisitGuide: 2-3 practical bullets about what a first-timer should expect.
5. plainEligibility: what to bring (ID, proof of address) or "Everyone welcome. Bring nothing."
6. culturalNotes: only if the text mentions a specific cultural community being served.
7. accepts_food_donations/accepts_money_donations/accepts_volunteers: true ONLY if explicitly mentioned.
8. donate_url/volunteer_url: extract URLs only if they appear in the text."""

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "enrich_food_org",
        "description": "Extract all structured fields and generate dignity-first copy for a food assistance org.",
        "parameters": {
            "type": "object",
            "properties": {
                "hours_raw": {"type": "string", "description": "Hours ONLY if explicitly stated. Null if not found."},
                "services": {"type": "array", "items": {"type": "string", "enum": ["food_pantry","hot_meals","delivery","snap_assistance","drive_through","mobile_pantry","community_garden"]}},
                "food_types": {"type": "array", "items": {"type": "string", "enum": ["produce","canned_goods","dairy","bread_bakery","protein","baby_supplies","frozen"]}},
                "requirements": {"type": "array", "items": {"type": "string", "enum": ["appointment_required","walk_in","no_id_required","photo_id","proof_of_address","income_verification"]}},
                "languages": {"type": "array", "items": {"type": "string", "enum": ["Spanish","French","Amharic","Arabic","Chinese","Vietnamese","Korean","Portuguese"]}},
                "heroCopy": {"type": "string", "description": "One warm sentence (10-20 words). Do NOT include org name."},
                "firstVisitGuide": {"type": "array", "items": {"type": "string"}, "description": "2-3 bullets (8-15 words each) about first visit."},
                "plainEligibility": {"type": "string", "description": "One sentence, max 15 words."},
                "culturalNotes": {"type": "string", "description": "Cultural community served, or null."},
                "toneScore": {"type": "number", "description": "0-1 first-timer friendliness."},
                "accepts_food_donations": {"type": "boolean"},
                "accepts_money_donations": {"type": "boolean"},
                "donate_url": {"type": "string"},
                "accepts_volunteers": {"type": "boolean"},
                "volunteer_url": {"type": "string"},
            },
            "required": ["services","food_types","requirements","languages","heroCopy","firstVisitGuide","plainEligibility","toneScore"],
        },
    },
}

BANNED_WORDS = {"needy", "eligible", "recipient", "beneficiary", "handout",
                "charity case", "underprivileged", "less fortunate"}


def _build_combined_text(rec: dict, web_cache: dict) -> str:
    """Combine raw_text + website body text."""
    parts = [rec.get("raw_text", "")]
    url = rec.get("website")
    if url:
        norm = _normalize_url(url)
        entry = web_cache.get(norm, {})
        body = entry.get("body_text")
        if body:
            parts.append("---WEBSITE---")
            parts.append(body[:3000])
    return "\n".join(parts)[:4000]


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()


def _validate_llm_result(result: dict, combined_text: str) -> dict:
    """Validate and clean LLM output. Returns cleaned result."""
    # toneScore: clamp to 0-1
    ts = result.get("toneScore")
    if ts is not None:
        result["toneScore"] = max(0.0, min(1.0, float(ts)))

    # heroCopy: check for banned words
    hero = result.get("heroCopy", "")
    if any(bw in hero.lower() for bw in BANNED_WORDS):
        result["heroCopy"] = None  # will be filled by template

    # hours_raw: anti-hallucination check
    hours = result.get("hours_raw")
    if hours:
        # At least one word from hours should appear in the input
        words = [w.strip() for w in re.split(r"[\s,\-:]+", hours) if len(w.strip()) > 2]
        lower_text = combined_text.lower()
        if not any(w.lower() in lower_text for w in words):
            result["hours_raw"] = None  # hallucinated

    # firstVisitGuide: reject overly long bullets
    guide = result.get("firstVisitGuide", [])
    result["firstVisitGuide"] = [b for b in guide if isinstance(b, str) and len(b) <= 100]

    # donate_url/volunteer_url: evidence check
    for url_field in ("donate_url", "volunteer_url"):
        url_val = result.get(url_field)
        if url_val and url_val not in combined_text:
            result[url_field] = None

    return result


def _merge_llm_into_record(rec: dict, result: dict):
    """Merge validated LLM result into record."""
    # Taxonomy: UNION with existing
    for field in ("services", "food_types", "requirements", "languages"):
        existing = list(rec.get(field) or [])
        for val in (result.get(field) or []):
            if val not in existing:
                existing.append(val)
        rec[field] = existing

    # hours_raw: only if record has no hours
    if not rec.get("hours") and result.get("hours_raw"):
        rec["hours"] = result["hours_raw"]

    # Semantic copy: overwrite (LLM is authoritative)
    for field in ("heroCopy", "firstVisitGuide", "plainEligibility",
                  "culturalNotes", "toneScore"):
        val = result.get(field)
        if val is not None:
            rec[field] = val

    # Donor/volunteer: only set if true
    for field in ("accepts_food_donations", "accepts_money_donations", "accepts_volunteers"):
        if result.get(field):
            rec[field] = True
    for field in ("donate_url", "volunteer_url"):
        if result.get(field):
            rec[field] = result[field]


def llm_enrich_all(records: list[dict], web_cache: dict, llm_cache: dict):
    """Enrich all records via Mistral LLM."""
    from mistralai.client import Mistral

    api_key = os.getenv("MISTRAL_API_KEY")
    model = os.getenv("MISTRAL_MODEL", "ministral-8b-latest")
    if not api_key:
        print("  No MISTRAL_API_KEY — skipping LLM enrichment")
        return

    client = Mistral(api_key=api_key)
    total = len(records)
    calls = 0
    cache_hits = 0
    errors = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for i, rec in enumerate(records):
        combined = _build_combined_text(rec, web_cache)
        key = _md5(combined)

        # Cache check
        if key in llm_cache:
            cached = llm_cache[key]
            _merge_llm_into_record(rec, cached.get("result", {}))
            cache_hits += 1
            _jsonl_log(LLM_LOG, {"ts": _ts(), "name": rec.get("name","?"),
                                 "source": rec.get("source_id","?"),
                                 "cache": "hit", "key": key})
            continue

        # API call with retry
        t0 = time.time()
        result = None
        last_error = None

        for attempt in range(3):
            try:
                resp = client.chat.complete(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": combined},
                    ],
                    tools=[TOOL_DEF],
                    tool_choice="any",
                    max_tokens=1024,
                )
                tc = resp.choices[0].message.tool_calls
                if tc:
                    result = json.loads(tc[0].function.arguments)
                    total_input_tokens += resp.usage.prompt_tokens
                    total_output_tokens += resp.usage.completion_tokens
                break
            except Exception as exc:
                last_error = str(exc)
                if "429" in last_error or "rate" in last_error.lower():
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)
                elif "500" in last_error or "502" in last_error or "503" in last_error:
                    time.sleep(3)
                else:
                    break  # non-retryable

        latency = int((time.time() - t0) * 1000)
        calls += 1

        if result:
            result = _validate_llm_result(result, combined)
            _merge_llm_into_record(rec, result)
            llm_cache[key] = {"cached_at": _ts(), "result": result,
                              "latency_ms": latency}
            enriched_fields = [f for f in result if result[f] is not None and result[f] != []]
            _jsonl_log(LLM_LOG, {"ts": _ts(), "name": rec.get("name","?")[:50],
                                 "source": rec.get("source_id","?"),
                                 "cache": "miss", "latency_ms": latency,
                                 "fields": len(enriched_fields), "errors": None})
        else:
            errors += 1
            _jsonl_log(LLM_LOG, {"ts": _ts(), "name": rec.get("name","?")[:50],
                                 "source": rec.get("source_id","?"),
                                 "cache": "miss", "latency_ms": latency,
                                 "fields": 0, "errors": last_error})

        # Rate limit
        time.sleep(0.15)

        if (i + 1) % 100 == 0:
            print(f"  LLM: {i+1}/{total} ({cache_hits} cached, {errors} errors)")

    print(f"  LLM done: {calls} calls, {cache_hits} cached, {errors} errors")
    print(f"  Tokens: {total_input_tokens} in, {total_output_tokens} out")


# ── Step 3: Template fallback ─────────────────────────────────────────────────

ZIP_LANG = {
    "207": ["Spanish"],
    "209": ["Spanish", "Amharic"],
    "200": ["Spanish", "Amharic"],
    "201": ["Spanish"],
    "220": ["Spanish"],
    "221": ["Spanish"],
    "222": ["Spanish", "Vietnamese"],
    "223": ["Spanish"],
}


def template_enrich(rec: dict):
    """Fill any remaining gaps with template-generated values."""
    filled = []
    svcs = rec.get("services") or ["food_pantry"]
    reqs = rec.get("requirements") or []

    # heroCopy
    if not rec.get("heroCopy"):
        if "walk_in" in reqs and "no_id_required" in reqs:
            rec["heroCopy"] = "Welcoming community pantry open to everyone -- just walk in, no paperwork needed."
        elif "walk_in" in reqs:
            rec["heroCopy"] = "Neighborhood food pantry where walk-ins are always welcome."
        elif "delivery" in svcs:
            rec["heroCopy"] = "Food delivery service bringing groceries to your door."
        elif "hot_meals" in svcs:
            rec["heroCopy"] = "Hot meals served to the community -- come as you are."
        elif "mobile_pantry" in svcs:
            rec["heroCopy"] = "Mobile food distribution bringing fresh groceries to your neighborhood."
        else:
            rec["heroCopy"] = "Local food pantry serving the community with groceries and support."
        filled.append("heroCopy")

    # firstVisitGuide
    if not rec.get("firstVisitGuide"):
        bullets = []
        if "walk_in" in reqs:
            bullets.append("Walk in during open hours -- no appointment needed.")
        elif "appointment_required" in reqs:
            bullets.append("Call ahead to schedule your visit.")
        else:
            bullets.append("Check the hours and stop by during distribution times.")

        if "no_id_required" in reqs:
            bullets.append("No ID or documents required -- everyone is welcome.")
        elif "photo_id" in reqs and "proof_of_address" in reqs:
            bullets.append("Bring a photo ID and proof of address if you have them.")
        elif "photo_id" in reqs:
            bullets.append("Bring a photo ID if you have one.")
        else:
            bullets.append("Bring an ID if you have one, but ask if unsure.")

        bullets.append("Staff will help you choose what you need.")
        rec["firstVisitGuide"] = bullets[:3]
        filled.append("firstVisitGuide")

    # plainEligibility
    if not rec.get("plainEligibility"):
        if "no_id_required" in reqs:
            rec["plainEligibility"] = "Everyone welcome. No ID or documents needed."
        elif "photo_id" in reqs and "proof_of_address" in reqs:
            rec["plainEligibility"] = "Bring a photo ID and proof of address."
        elif "photo_id" in reqs:
            rec["plainEligibility"] = "Bring a photo ID. Call ahead if you have questions."
        elif "income_verification" in reqs:
            rec["plainEligibility"] = "Bring proof of income and a photo ID."
        else:
            rec["plainEligibility"] = "Open to the community. Call ahead to confirm what to bring."
        filled.append("plainEligibility")

    # toneScore
    if rec.get("toneScore") is None:
        if "walk_in" in reqs and "no_id_required" in reqs:
            rec["toneScore"] = 0.9
        elif "walk_in" in reqs:
            rec["toneScore"] = 0.7
        elif "appointment_required" in reqs:
            rec["toneScore"] = 0.45
        else:
            rec["toneScore"] = 0.6
        filled.append("toneScore")

    # Languages by ZIP
    if not rec.get("languages"):
        z = rec.get("zip") or ""
        prefix = z[:3]
        if prefix in ZIP_LANG:
            rec["languages"] = list(ZIP_LANG[prefix])
            filled.append("languages")

    if filled:
        _jsonl_log(TPL_LOG, {"ts": _ts(), "name": rec.get("name","?")[:50],
                             "source": rec.get("source_id","?"),
                             "fields_filled": filled})


# ── Step 4: Quality report ────────────────────────────────────────────────────

def quality_report(before: list[dict], after: list[dict]):
    """Print before/after field completeness."""
    fields = ["hours", "heroCopy", "firstVisitGuide", "plainEligibility",
              "languages", "food_types", "requirements", "toneScore",
              "accepts_food_donations", "accepts_money_donations", "accepts_volunteers",
              "donate_url", "volunteer_url"]

    def _count(records, field):
        return sum(1 for r in records if r.get(field))

    total = len(after)
    print(f"\n{'='*65}")
    print(f"ENRICHMENT QUALITY REPORT ({total} records)")
    print(f"{'='*65}")
    print(f"{'Field':<25} {'Before':>8} {'After':>8} {'Delta':>10}")
    print(f"{'-'*25} {'-'*8} {'-'*8} {'-'*10}")

    for f in fields:
        b = _count(before, f)
        a = _count(after, f)
        delta = a - b
        pct = f"+{delta}" if delta > 0 else str(delta)
        print(f"{f:<25} {b:>8} {a:>8} {pct:>10}")

    # Per-source breakdown
    sources = sorted(set(r.get("source_id", "?") for r in after))
    print(f"\nPer-source:")
    for sid in sources:
        src_before = [r for r in before if r.get("source_id") == sid]
        src_after = [r for r in after if r.get("source_id") == sid]
        h_b = _count(src_before, "hours")
        h_a = _count(src_after, "hours")
        hero_a = _count(src_after, "heroCopy")
        print(f"  {sid:<18} {len(src_after):>4} records  hours: {h_b}->{h_a}  heroCopy: {hero_a}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stage 1b: enrich raw records")
    parser.add_argument("--skip-scrape", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--source", type=str, default="")
    args = parser.parse_args()

    # Load input
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]
    if args.source:
        records = [r for r in records if r.get("source_id") == args.source]
    if args.limit > 0:
        records = records[:args.limit]

    print(f"Stage 1b: enriching {len(records)} records")

    # Save a copy of before state for quality report
    import copy
    before = copy.deepcopy(records)

    if args.dry_run:
        url_map = dedup_urls(records)
        print(f"  Unique URLs to scrape: {len(url_map)}")
        print(f"  Records needing LLM: {len(records)}")
        print(f"  API key set: {bool(os.getenv('MISTRAL_API_KEY'))}")
        return

    # Step 0: URL dedup
    url_map = dedup_urls(records)
    print(f"  Unique website URLs: {len(url_map)}")

    # Step 1: Website scraping
    web_cache = _load_cache(WEB_CACHE)
    if not args.skip_scrape and url_map:
        print(f"\nStep 1: Scraping {len(url_map)} websites...")
        asyncio.run(scrape_websites(url_map, records, web_cache))
        _save_cache(WEB_CACHE, web_cache)

        # Apply scraped hours to records missing hours
        for norm_url, indices in url_map.items():
            entry = web_cache.get(norm_url, {})
            hours_found = entry.get("hours_found")
            if hours_found:
                for idx in indices:
                    if idx < len(records) and not records[idx].get("hours"):
                        records[idx]["hours"] = hours_found
    else:
        print("\nStep 1: Skipped (--skip-scrape or no URLs)")

    # Step 2: LLM enrichment
    llm_cache = _load_cache(LLM_CACHE)
    if not args.skip_llm:
        print(f"\nStep 2: Mistral LLM enrichment ({len(records)} records)...")
        llm_enrich_all(records, web_cache, llm_cache)
        _save_cache(LLM_CACHE, llm_cache)
    else:
        print("\nStep 2: Skipped (--skip-llm)")

    # Step 3: Template fallback
    print(f"\nStep 3: Template fallback...")
    for rec in records:
        template_enrich(rec)
    print(f"  Template fallback done")

    # Step 4: Save + report
    output_data = {
        "stats": data.get("stats", {}),
        "total": len(records),
        "records": records,
        "enriched_at": _ts(),
    }
    OUTPUT.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved to {OUTPUT}")

    quality_report(before, records)


if __name__ == "__main__":
    main()
