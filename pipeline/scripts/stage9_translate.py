"""
Stage 9 -- Fast async translation of AI enrichment fields (es + am).

Batches all text fields per org into one translate call per language,
and runs multiple orgs concurrently with asyncio.

Usage:
  cd pipeline
  python scripts/stage9_translate.py

Requires: pip install deep-translator aiohttp
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("ERROR: pip install deep-translator")
    sys.exit(1)

# ── Paths ────────────────────────────────────────────────────────────────────
PIPELINE   = Path(__file__).resolve().parents[1]
PROJECT    = PIPELINE.parent
ORGS_PATH  = PROJECT / "public" / "data" / "enriched-orgs.json"
CACHE_PATH = PIPELINE / "state" / "translation-cache.json"

CONCURRENCY = 15  # parallel translation workers
SEPARATOR   = " ||| "  # join fields into one string, split after


# ── Cache ────────────────────────────────────────────────────────────────────
def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Batch translate: join all fields into one string ─────────────────────────
def _translate_org_lang(ai: dict, lang: str, retries: int = 3) -> dict:
    """Translate all AI fields for one org in ONE api call by joining them."""
    hero = ai.get("heroCopy", "") or ""
    elig = ai.get("plainEligibility", "") or ""
    guide = ai.get("firstVisitGuide", []) or []
    cultural = ai.get("culturalNotes") or ""

    # Pack all text into one string with separators
    guide_joined = SEPARATOR.join(guide) if guide else ""
    parts = [hero, elig, guide_joined, cultural]
    packed = SEPARATOR.join(parts)

    if not packed.strip() or packed.strip() == (SEPARATOR * 3).strip():
        return {
            "heroCopy": hero,
            "plainEligibility": elig,
            "firstVisitGuide": guide,
            "culturalNotes": cultural if cultural else None,
        }

    for attempt in range(retries):
        try:
            translated = GoogleTranslator(source="en", target=lang).translate(packed[:4900])
            if translated:
                split = translated.split(SEPARATOR)
                # Pad if split produced fewer parts
                while len(split) < 4:
                    split.append("")

                t_hero = split[0].strip()
                t_elig = split[1].strip()
                t_guide_joined = split[2].strip()
                t_cultural = split[3].strip() if len(split) > 3 else ""

                t_guide = [g.strip() for g in t_guide_joined.split(SEPARATOR)] if t_guide_joined else []
                # If guide count doesn't match, fall back to individual translation
                if guide and len(t_guide) != len(guide):
                    t_guide = []
                    for item in guide:
                        try:
                            t = GoogleTranslator(source="en", target=lang).translate(item[:4900])
                            t_guide.append(t or item)
                        except Exception:
                            t_guide.append(item)

                return {
                    "heroCopy": t_hero or hero,
                    "plainEligibility": t_elig or elig,
                    "firstVisitGuide": t_guide if t_guide else guide,
                    "culturalNotes": t_cultural if t_cultural else (cultural if cultural else None),
                }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
            else:
                pass

    # Fallback: return English
    return {
        "heroCopy": hero,
        "plainEligibility": elig,
        "firstVisitGuide": guide,
        "culturalNotes": cultural if cultural else None,
    }


def _translate_org(org: dict) -> tuple[str, dict]:
    """Translate one org into both languages. Returns (org_id, {es: {...}, am: {...}})."""
    ai = org.get("ai", {})
    es = _translate_org_lang(ai, "es")
    am = _translate_org_lang(ai, "am")
    return org["id"], {"es": es, "am": am}


# ── Async orchestrator ───────────────────────────────────────────────────────
async def run_translations(todo: list[dict], cache: dict):
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=CONCURRENCY)

    total = len(todo)
    done = 0
    failed = 0
    start = time.time()

    # Process in waves of CONCURRENCY
    for i in range(0, total, CONCURRENCY):
        wave = todo[i : i + CONCURRENCY]
        futures = [loop.run_in_executor(executor, _translate_org, org) for org in wave]
        results = await asyncio.gather(*futures, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                failed += 1
                done += 1
                continue
            org_id, translations = r
            cache[org_id] = translations
            done += 1

        # Save cache after each wave
        save_cache(cache)

        elapsed = time.time() - start
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        print(f"  [{done}/{total}] {round(rate, 1)} orgs/sec, ETA {int(eta)}s, failed={failed}", flush=True)

    executor.shutdown(wait=False)
    return failed


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    orgs = json.loads(ORGS_PATH.read_text(encoding="utf-8"))
    print(f"Loaded {len(orgs)} orgs")

    cache = load_cache()
    print(f"Cache: {len(cache)} orgs already translated")

    todo = [o for o in orgs if o["id"] not in cache]
    print(f"To translate: {len(todo)} ({len(orgs) - len(todo)} cached)\n")

    if todo:
        failed = asyncio.run(run_translations(todo, cache))
        print(f"\nDone translating: {len(todo) - failed} success, {failed} failed")

    # ── Merge ────────────────────────────────────────────────────────────────
    print(f"\nMerging into {ORGS_PATH.name}...")
    merged = 0
    for org in orgs:
        if org["id"] in cache:
            org.setdefault("ai", {})["translations"] = cache[org["id"]]
            merged += 1

    ORGS_PATH.write_text(
        json.dumps(orgs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Merged: {merged}/{len(orgs)}")

    dist = PROJECT / "dist" / "data" / "enriched-orgs.json"
    if dist.exists():
        dist.write_text(json.dumps(orgs, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Also updated dist/")

    print("Done!")


if __name__ == "__main__":
    main()
