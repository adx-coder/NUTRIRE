# Backend Enrichment Spec — Semantic Layer

> **What this is**: Adds a second LLM enrichment step to `pipeline/src/utils/llm_enricher.py`
> that generates dignity-first semantic copy (first-visit guide, plain eligibility,
> tone score, hero copy) on top of the existing tag classifier. Plus a local
> sentence-transformers embedding step for semantic search.
>
> **Why**: The current enricher only does tag classification. The frontend needs
> richer semantic fields to render the OrgCard and support natural-language search
> without a runtime LLM call.
>
> **Runtime contract**: Build-time only. Cached by `MD5(raw_text) + ':sem'` in the
> existing `state/llm-enrichment-cache.json`. Runtime is pure consumption.

---

## 1. New fields on `NormalizedRecord` (`validators/schemas.py`)

Add to the `NormalizedRecord` class, after the `feedbackScore` field:

```python
# ── Semantic enrichment (new) ─────────────────────────────────────
firstVisitGuide: Optional[list[str]] = None    # 2-3 warm bullets
plainEligibility: Optional[str] = None         # 1 sentence, dignity voice
culturalNotes: Optional[str] = None            # community served
toneScore: Optional[float] = None              # 0-1 first-timer friendliness
heroCopy: Optional[str] = None                 # 1 card-ready sentence
embedding: Optional[list[float]] = None        # 384-dim vector
```

## 2. New tool schema in `llm_enricher.py`

Add alongside the existing `_CLASSIFICATION_TOOL`:

```python
_SEMANTIC_TOOL = {
    "name": "write_org_copy",
    "description": (
        "Generate warm, dignity-first copy for a food assistance org. "
        "Never use: needy, emergency, recipient, beneficiary, eligible, "
        "underserved, low-income, assistance, food insecure, applicant. "
        "Write as a neighbor who has been there."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "firstVisitGuide": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 3,
                "description": (
                    "2-3 bullets about what will happen on a first visit. "
                    "8-15 words each. Second person. Concrete actions. "
                    "Example: 'Walk in the front door. Staff will greet you. "
                    "Expect about 15 minutes.'"
                )
            },
            "plainEligibility": {
                "type": "string",
                "maxLength": 100,
                "description": (
                    "One sentence, max 15 words. Best: 'Anyone welcome. "
                    "Bring nothing.' If ID required: 'Bring a photo ID and "
                    "something with your address.' Never 'eligible' or 'qualify'."
                )
            },
            "culturalNotes": {
                "type": "string",
                "description": (
                    "Empty string if not applicable. Otherwise one line about "
                    "the community served: 'Serves Ethiopian community, teff "
                    "and berbere available.' Only infer from clear evidence."
                )
            },
            "toneScore": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": (
                    "0-1 first-timer friendliness. 0.9+ = no questions asked, "
                    "walk-in, choice pantry. 0.5-0.7 = formal process, "
                    "paperwork, appointment. <0.4 = stale or hard-to-access."
                )
            },
            "heroCopy": {
                "type": "string",
                "maxLength": 140,
                "description": (
                    "One warm sentence, 10-20 words, describing what the place "
                    "actually is. Do NOT repeat the org name. Example: "
                    "'Walk-in fresh market with produce, bread, and dairy "
                    "every Saturday morning — no forms, no questions.'"
                )
            }
        },
        "required": [
            "firstVisitGuide", "plainEligibility",
            "toneScore", "heroCopy"
        ]
    }
}

_SEMANTIC_SYSTEM_PROMPT = """You write copy for Nutrire, a dignity-first food \
access app for DC/Maryland/Virginia. Users are families looking for food — \
stressed, often embarrassed, limited time.

Write as a neighbor who has been there, not as a charity. Use everyday \
language, short sentences, second person ("you"). Be specific about what \
the user will actually encounter.

BANNED WORDS: needy, emergency food, recipient, beneficiary, eligible, \
underserved, low-income, assistance, applicant, food insecure.

Use respectful, warm, brief language. If the source text is thin, keep the \
copy short — never invent details."""
```

## 3. New batch function in `llm_enricher.py`

```python
def semantic_enrich_batch(
    records: list, cache: Optional[dict] = None
) -> tuple[int, int]:
    """
    Generate semantic copy for each record via Claude tool-use.
    Mutates records in-place. Returns (api_calls, cache_hits).

    Cache key: MD5(raw_text) + ':sem' — distinct from classifier cache.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = None
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            log.warn("anthropic not installed")

    cache = cache if cache is not None else load_cache()
    calls = 0
    hits = 0
    dirty = False

    for rec in records:
        raw = (rec.raw_text or "").strip()
        if not raw:
            continue

        key = _cache_key(raw) + ":sem"

        if key in cache:
            result = cache[key]
            hits += 1
        elif client:
            try:
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1024,
                    system=_SEMANTIC_SYSTEM_PROMPT,
                    tools=[_SEMANTIC_TOOL],
                    tool_choice={"type": "tool", "name": "write_org_copy"},
                    messages=[{"role": "user", "content": raw[:2500]}],
                )
                result = None
                for block in msg.content:
                    if block.type == "tool_use" and block.name == "write_org_copy":
                        result = block.input
                        break
                if not result:
                    continue
                result["enriched_at"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                )
                cache[key] = result
                dirty = True
                calls += 1
                time.sleep(0.05)
            except Exception as exc:
                log.warn(f"semantic LLM call failed: {exc}")
                continue
        else:
            continue  # no API key, no cache — skip silently

        # Apply to record
        rec.firstVisitGuide = result.get("firstVisitGuide")
        rec.plainEligibility = result.get("plainEligibility")
        notes = result.get("culturalNotes")
        rec.culturalNotes = notes if notes else None
        rec.toneScore = result.get("toneScore")
        rec.heroCopy = result.get("heroCopy")

    if dirty:
        save_cache(cache)

    return calls, hits
```

## 4. New local embeddings module `pipeline/src/utils/embedder.py`

```python
"""
Local sentence-transformers embeddings. 384-dim via all-MiniLM-L6-v2.
Runs offline after the one-time model download.

Cache strategy: MD5(joined text) → vector. Cached in state/embedding-cache.json.
"""
import hashlib
import json
from pathlib import Path

from src.utils.logger import Logger

log = Logger("embedder")

_MODEL = None
_CACHE_PATH = Path(__file__).resolve().parents[3] / "state" / "embedding-cache.json"


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            log.warn("sentence-transformers not installed — pip install sentence-transformers")
            return None
    return _MODEL


def _load_cache() -> dict:
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def _org_text(rec) -> str:
    parts = [
        rec.name,
        rec.heroCopy,
        ", ".join(rec.services or []),
        ", ".join(rec.food_types or []),
        ", ".join(rec.languages or []),
        rec.culturalNotes or "",
    ]
    return " | ".join(p for p in parts if p)


def compute_embeddings_batch(records: list) -> int:
    """Populate rec.embedding for each record. Returns count of newly computed."""
    model = _get_model()
    if model is None:
        return 0

    cache = _load_cache()
    computed = 0
    dirty = False

    for rec in records:
        text = _org_text(rec)
        if not text:
            continue
        key = hashlib.md5(text.encode("utf-8")).hexdigest()

        if key in cache:
            rec.embedding = cache[key]
        else:
            vec = model.encode(text, convert_to_numpy=False)
            rec.embedding = [float(x) for x in vec]
            cache[key] = rec.embedding
            dirty = True
            computed += 1

    if dirty:
        _save_cache(cache)
    return computed
```

Add to `pipeline/requirements.txt`:

```
sentence-transformers>=2.7.0
```

## 5. Integration into `orchestrator.py`

After the existing classification step:

```python
from src.utils.llm_enricher import enrich_batch, semantic_enrich_batch
from src.utils.embedder import compute_embeddings_batch

# Existing step — tag classification
classify_calls, classify_hits = enrich_batch(normalized)
log.info(f"classification: {classify_calls} calls, {classify_hits} hits")

# NEW — semantic copy
sem_calls, sem_hits = semantic_enrich_batch(normalized)
log.info(f"semantic: {sem_calls} calls, {sem_hits} hits")

# NEW — local embeddings for semantic search
emb_count = compute_embeddings_batch(normalized)
log.info(f"embeddings: {emb_count} newly computed")
```

## 6. Cost estimate

At ~100 orgs:

| Step | Model | Cost |
|---|---|---|
| Existing classifier | Haiku tool-use | ~$0.30 |
| New semantic enricher | Haiku tool-use | ~$0.50 |
| Embeddings | Local (free) | $0 |

**~$0.80 for a full re-run**. Cache means incremental runs are free.

## 7. Reproducibility

All caches (`llm-enrichment-cache.json`, `embedding-cache.json`) are committed to the repo. After backend team runs the full pipeline once, anyone can rebuild without any API key. The demo pipeline never makes a live API call.

## 8. What the frontend consumes

The frontend reads `organizations.json` and expects every record to include the new fields. Missing fields gracefully degrade:

- Missing `firstVisitGuide` → hide the "What to expect" section on OrgCard
- Missing `plainEligibility` → fall back to a rule-based summary from `requirements`
- Missing `embedding` → fall back to Fuse.js keyword search
- Missing `heroCopy` → show name + services chips only
- Missing `toneScore` → exclude from ranking (don't penalize)

## 9. Dignity copy enforcement (post-generation check)

Add this validation after each LLM call, before caching:

```python
_BANNED_WORDS = {
    "needy", "emergency", "recipient", "beneficiary", "eligible",
    "underserved", "low-income", "assistance", "food insecure",
    "applicant",
}

def _dignity_check(result: dict) -> bool:
    """Returns True if all strings pass the banned-words test."""
    def check(text: str) -> bool:
        lower = text.lower()
        return not any(w in lower for w in _BANNED_WORDS)

    if not check(result.get("plainEligibility", "")):
        return False
    if not check(result.get("heroCopy", "")):
        return False
    for bullet in result.get("firstVisitGuide") or []:
        if not check(bullet):
            return False
    if not check(result.get("culturalNotes", "")):
        return False
    return True
```

If `_dignity_check` fails, retry once with a stricter prompt. If it fails twice, skip (record keeps its tag data but no semantic copy).
