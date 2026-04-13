"""
Stage 2 -- Deduplicate enriched records across sources.

Same org can appear in CAFB + MDFB + 211MD + MoCoFood. This script merges
duplicates into a single canonical record with the richest data.

Input:  output/stage1b_enriched_records.json
Output: output/stage2_deduped.json

Usage:
  python scripts/stage2_dedup.py
  python scripts/stage2_dedup.py --dry-run     # show merge groups only
  python scripts/stage2_dedup.py --threshold 75 # adjust fuzzy match threshold
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rapidfuzz import fuzz

PIPELINE = Path(__file__).resolve().parents[1]
INPUT    = PIPELINE / "output" / "stage1b_enriched_records.json"
OUTPUT   = PIPELINE / "output" / "stage2_deduped.json"
LOG_DIR  = PIPELINE / "logs"
LOG_FILE = LOG_DIR / "stage2_dedup.jsonl"

LOG_DIR.mkdir(parents=True, exist_ok=True)

# Source priority for canonical selection (higher = preferred)
SOURCE_PRIORITY = {
    "mocofood": 5,   # richest: hours + languages + types + features
    "cafb": 4,       # structured hours + requirements + lat/lon
    "two11md": 3,    # descriptions + tags
    "two11va": 3,
    "mdfb-find-food": 2,  # name + address + phone only
}


def _jsonl_log(entry: dict):
    from datetime import datetime, timezone
    entry["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Union-Find ────────────────────────────────────────────────────────────────

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


# ── Matching ──────────────────────────────────────────────────────────────────

def _clean_name(name: str) -> str:
    """Normalize name for comparison."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [", inc.", ", inc", " inc.", " inc", " llc", " corp"]:
        name = name.removesuffix(suffix)
    # Normalize punctuation
    name = re.sub(r"[''`]", "'", name)
    name = re.sub(r"[.,:;!?]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _street_number(address: str | None) -> str | None:
    """Extract leading street number from address."""
    if not address:
        return None
    m = re.match(r"^(\d+)\s", address.strip())
    return m.group(1) if m else None


def find_duplicates(records: list[dict], threshold: int = 80) -> list[list[int]]:
    """Find duplicate groups using union-find."""
    n = len(records)
    uf = UnionFind(n)

    names = [_clean_name(r.get("name", "")) for r in records]
    zips = [r.get("zip", "") for r in records]
    street_nums = [_street_number(r.get("address")) for r in records]

    # Pre-compute hours signatures to avoid merging different programs
    hours_sigs = [r.get("hours", "") or "" for r in records]

    for i in range(n):
        if not names[i]:
            continue
        for j in range(i + 1, n):
            if not names[j]:
                continue

            # Strategy 1: exact name + same ZIP + compatible hours
            if names[i] == names[j] and zips[i] and zips[i] == zips[j]:
                # If BOTH have hours and hours are very different, these are different programs
                if hours_sigs[i] and hours_sigs[j]:
                    # Same org different schedule — don't merge if from same source
                    if records[i].get("source_id") == records[j].get("source_id"):
                        continue  # skip: same source, same name, different hours = different program
                uf.union(i, j)
                continue

            # Strategy 2: high confidence name match (>92%) + same ZIP
            if zips[i] and zips[i] == zips[j]:
                score = fuzz.token_sort_ratio(names[i], names[j])
                if score >= 92:
                    uf.union(i, j)
                    continue

            # Strategy 3: fuzzy name (>80%) + same street number + same ZIP
            if (street_nums[i] and street_nums[j] and
                street_nums[i] == street_nums[j] and
                zips[i] and zips[i] == zips[j]):
                score = fuzz.token_sort_ratio(names[i], names[j])
                if score >= threshold:
                    uf.union(i, j)

    # Collect groups
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = uf.find(i)
        groups.setdefault(root, []).append(i)

    return list(groups.values())


# ── Merging ───────────────────────────────────────────────────────────────────

def _fields_filled(rec: dict) -> int:
    """Count non-null, non-empty fields."""
    count = 0
    for k, v in rec.items():
        if k in ("raw_text", "source_id"):
            continue
        if v is not None and v != "" and v != []:
            count += 1
    return count


def _source_score(rec: dict) -> int:
    return SOURCE_PRIORITY.get(rec.get("source_id", ""), 1)


def merge_group(records: list[dict], indices: list[int]) -> dict:
    """Merge a group of duplicate records into one canonical record."""
    group = [records[i] for i in indices]

    # Sort by: has hours, fields filled, source priority
    group.sort(key=lambda r: (
        bool(r.get("hours")),
        bool(r.get("heroCopy")),
        bool(r.get("languages")),
        _fields_filled(r),
        _source_score(r),
    ), reverse=True)

    # Canonical = first (best)
    canonical = dict(group[0])

    # Collect all source_ids
    all_sources = []
    for r in group:
        sid = r.get("source_id", "")
        if sid and sid not in all_sources:
            all_sources.append(sid)
    canonical["source_ids"] = all_sources
    canonical["cross_source_count"] = len(all_sources)

    # Backfill missing scalar fields from other records
    # heroCopy/plainEligibility: keep canonical only (don't mix copy from different programs)
    backfill_scalars = ["address", "phone", "website", "hours", "zip", "city", "state",
                        "culturalNotes", "donate_url", "volunteer_url"]
    for field in backfill_scalars:
        if not canonical.get(field):
            for r in group[1:]:
                val = r.get(field)
                if val:
                    canonical[field] = val
                    break

    # heroCopy/plainEligibility/toneScore: keep canonical only (best source)
    # Already set from canonical — no backfill needed for these

    # List fields: conflict-aware merge
    # services, food_types, languages: union (these don't conflict)
    for field in ("services", "food_types", "languages"):
        existing = list(canonical.get(field) or [])
        for r in group[1:]:
            for val in (r.get(field) or []):
                if val not in existing:
                    existing.append(val)
        canonical[field] = existing

    # requirements: conflict-aware (don't mix walk_in + appointment_required)
    canonical_reqs = list(canonical.get("requirements") or [])
    for r in group[1:]:
        for req in (r.get("requirements") or []):
            if req in canonical_reqs:
                continue
            # Skip contradictory requirements
            if req == "walk_in" and "appointment_required" in canonical_reqs:
                continue
            if req == "appointment_required" and "walk_in" in canonical_reqs:
                continue
            if req == "no_id_required" and "photo_id" in canonical_reqs:
                continue
            if req == "photo_id" and "no_id_required" in canonical_reqs:
                continue
            canonical_reqs.append(req)
    canonical["requirements"] = canonical_reqs

    # firstVisitGuide: keep canonical only, max 3 (don't merge different program guides)
    guide = canonical.get("firstVisitGuide") or []
    canonical["firstVisitGuide"] = guide[:3]

    # Booleans: OR
    for field in ("accepts_food_donations", "accepts_money_donations", "accepts_volunteers"):
        if not canonical.get(field):
            for r in group[1:]:
                if r.get(field):
                    canonical[field] = True
                    break

    # Reconciliation warnings
    warnings = []
    all_hours = [r.get("hours") for r in group if r.get("hours")]
    if len(set(all_hours)) > 1:
        warnings.append("Hours differ between sources -- showing most trusted.")
    all_reqs = set()
    for r in group:
        all_reqs.update(r.get("requirements") or [])
    if "walk_in" in all_reqs and "appointment_required" in all_reqs:
        warnings.append("Some sources say walk-in, others say appointment needed.")
    if warnings:
        canonical["reconciliation_warnings"] = warnings

    return canonical


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stage 2: deduplicate records")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--threshold", type=int, default=80, help="Fuzzy match threshold (0-100)")
    args = parser.parse_args()

    data = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]
    total_before = len(records)
    print(f"Stage 2: deduplicating {total_before} records (threshold={args.threshold})")

    # Find duplicate groups
    groups = find_duplicates(records, threshold=args.threshold)
    multi_groups = [g for g in groups if len(g) > 1]
    single_groups = [g for g in groups if len(g) == 1]

    print(f"  {len(multi_groups)} merge groups (will merge {sum(len(g) for g in multi_groups)} records)")
    print(f"  {len(single_groups)} unique records (no duplicates)")

    # Show merge groups
    if multi_groups:
        print(f"\n  Top merge groups:")
        for g in sorted(multi_groups, key=len, reverse=True)[:15]:
            names = [records[i].get("name", "?")[:40] for i in g]
            sources = [records[i].get("source_id", "?") for i in g]
            print(f"    [{len(g)}] {' + '.join(set(sources))}: {names[0]}")

    if args.dry_run:
        print("\n  --dry-run: not merging")
        return

    # Merge
    output_records = []
    for g in groups:
        if len(g) == 1:
            rec = dict(records[g[0]])
            rec["source_ids"] = [rec.get("source_id", "")]
            rec["cross_source_count"] = 1
            output_records.append(rec)
        else:
            merged = merge_group(records, g)
            output_records.append(merged)

            _jsonl_log({
                "action": "merge",
                "group_size": len(g),
                "canonical_name": merged.get("name", "?")[:50],
                "canonical_source": merged.get("source_id", "?"),
                "all_sources": merged.get("source_ids", []),
                "fields_backfilled": [f for f in ["hours", "phone", "website", "languages"]
                                      if not records[g[0]].get(f) and merged.get(f)],
            })

    total_after = len(output_records)
    merged_count = total_before - total_after

    # Save
    output_data = {
        "stats": {
            "total_before": total_before,
            "total_after": total_after,
            "merged": merged_count,
            "merge_groups": len(multi_groups),
        },
        "total": total_after,
        "records": output_records,
    }
    OUTPUT.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"DEDUP: {total_before} -> {total_after} ({merged_count} duplicates merged)")
    print(f"{'='*60}")

    # Per-source breakdown
    source_counts: dict[str, int] = {}
    multi_source = 0
    for r in output_records:
        sid = r.get("source_id", "?")
        source_counts[sid] = source_counts.get(sid, 0) + 1
        if r.get("cross_source_count", 1) > 1:
            multi_source += 1

    print(f"\nPer-source (canonical):")
    for sid, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"  {sid}: {count}")
    print(f"\nCross-source validated: {multi_source} records ({round(multi_source/total_after*100)}%)")

    # Field completeness after merge
    fields = ["hours", "heroCopy", "firstVisitGuide", "plainEligibility",
              "languages", "food_types", "requirements", "phone", "address", "website"]
    print(f"\nField completeness after dedup:")
    for f in fields:
        count = sum(1 for r in output_records if r.get(f))
        pct = round(count / total_after * 100)
        print(f"  {f}: {count}/{total_after} ({pct}%)")


if __name__ == "__main__":
    main()
