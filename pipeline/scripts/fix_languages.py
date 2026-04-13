"""Fix: Infer languages from ZIP codes for records missing language data."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

INPUT = Path(__file__).resolve().parents[1] / "output" / "stage4_normalized.json"

# Specific ZIP → languages (Census ACS non-English speaking populations >10%)
ZIP_SPECIFIC = {
    # DC
    "20009": ["Spanish", "Amharic"], "20010": ["Spanish", "Amharic"],
    "20011": ["Spanish", "Amharic"], "20012": ["Spanish"],
    "20017": ["Spanish"], "20019": ["Spanish"], "20020": ["Spanish"],
    "20032": ["Spanish"],
    # MD — Silver Spring / Takoma Park
    "20901": ["Spanish", "Amharic"], "20902": ["Spanish", "Amharic"],
    "20903": ["Spanish"], "20904": ["Spanish", "Korean"],
    "20905": ["Spanish"], "20906": ["Spanish", "Amharic", "Chinese"],
    "20910": ["Spanish", "Amharic"], "20912": ["Spanish", "Amharic"],
    # MD — PG County
    "20706": ["Spanish"], "20707": ["Spanish"], "20708": ["Spanish"],
    "20710": ["Spanish"], "20712": ["Spanish"], "20720": ["Spanish"],
    "20721": ["Spanish"], "20737": ["Spanish"], "20740": ["Spanish"],
    "20743": ["Spanish"], "20744": ["Spanish"], "20745": ["Spanish"],
    "20746": ["Spanish"], "20747": ["Spanish"], "20748": ["Spanish"],
    "20770": ["Spanish"], "20781": ["Spanish"], "20782": ["Spanish"],
    "20783": ["Spanish"], "20784": ["Spanish"], "20785": ["Spanish"],
    # MD — Montgomery County
    "20850": ["Spanish", "Chinese"], "20851": ["Spanish"],
    "20852": ["Spanish", "Chinese"], "20853": ["Spanish"],
    "20854": ["Spanish", "Chinese"], "20855": ["Spanish"],
    "20874": ["Spanish"], "20876": ["Spanish"],
    "20877": ["Spanish"], "20878": ["Spanish", "Chinese"],
    "20886": ["Spanish", "Korean"], "20895": ["Spanish"],
    # MD — Baltimore area
    "21201": ["Spanish"], "21202": ["Spanish"], "21205": ["Spanish"],
    "21207": ["Spanish"], "21215": ["Spanish"], "21217": ["Spanish"],
    "21223": ["Spanish"], "21224": ["Spanish"], "21229": ["Spanish"],
    "21230": ["Spanish"], "21231": ["Spanish"],
    # VA — Northern Virginia
    "22003": ["Spanish", "Korean"], "22015": ["Spanish", "Korean"],
    "22031": ["Spanish", "Vietnamese"], "22033": ["Spanish", "Korean"],
    "22041": ["Spanish"], "22042": ["Spanish", "Vietnamese"],
    "22044": ["Spanish"], "22046": ["Spanish"],
    "22101": ["Spanish"], "22102": ["Spanish"],
    "22150": ["Spanish", "Korean"], "22151": ["Spanish"],
    "22152": ["Spanish"], "22153": ["Spanish"],
    "22191": ["Spanish"], "22192": ["Spanish"], "22193": ["Spanish"],
    "22204": ["Spanish"], "22205": ["Spanish"], "22206": ["Spanish"],
    "22207": ["Spanish"], "22301": ["Spanish"],
    "22304": ["Spanish", "Amharic"], "22305": ["Spanish"],
    "22312": ["Spanish", "Vietnamese"], "22314": ["Spanish"],
    "22407": ["Spanish"], "22408": ["Spanish"],
}

# 3-digit prefix fallback
ZIP_PREFIX = {
    "200": ["Spanish"],       # DC
    "201": ["Spanish"],       # DC
    "206": ["Spanish"],       # Southern PG County
    "207": ["Spanish"],       # PG County
    "208": ["Spanish"],       # Bethesda/Rockville
    "209": ["Spanish", "Amharic"],  # Silver Spring
    "220": ["Spanish"],       # Fairfax
    "221": ["Spanish"],       # Woodbridge/Manassas
    "222": ["Spanish", "Vietnamese"],  # Falls Church/Annandale
    "223": ["Spanish"],       # Alexandria/Arlington
    "230": ["Spanish"],       # Richmond suburbs
}


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    records = data["records"]

    filled = 0
    for r in records:
        if r.get("languages"):
            continue
        z = r.get("zip", "")
        if not z or len(z) < 3:
            continue

        langs = ZIP_SPECIFIC.get(z)
        if langs is None:
            langs = ZIP_PREFIX.get(z[:3])

        if langs:
            r["languages"] = list(langs)
            filled += 1

    # Save
    data["records"] = records
    INPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    has_lang = sum(1 for r in records if r.get("languages"))
    no_lang = len(records) - has_lang
    print(f"Filled {filled} records with ZIP-inferred languages")
    print(f"Now: {has_lang}/{len(records)} ({round(has_lang/len(records)*100)}%)")
    print(f"Still missing: {no_lang}")

    all_langs = []
    for r in records:
        all_langs.extend(r.get("languages", []))
    print(f"\nLanguage distribution:")
    for lang, count in Counter(all_langs).most_common():
        print(f"  {lang}: {count}")


if __name__ == "__main__":
    main()
