import io
import re
import pdfplumber
from src.validators.schemas import RawRecord

PHONE_RE = re.compile(r"(?:\+1[\-.\s]?)?\(?\d{3}\)?[\-.\s]\d{3}[\-.\s]\d{4}")
ADDR_RE  = re.compile(
    r"\d{1,5}\s+[A-Za-z0-9\s.,\'#\-]{3,50}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl|Pkwy)\.?",
    re.IGNORECASE,
)
ZIP_RE   = re.compile(r"\b\d{5}(?:-\d{4})?\b")
HOURS_RE = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*[\s,\u2013\-]+\d{1,2}(?::\d{2})?\s*[ap]m",
    re.IGNORECASE,
)


def scrape_generic_pdf(content: str | bytes, source_id: str) -> list[RawRecord]:
    raw_bytes = content if isinstance(content, bytes) else content.encode("latin-1", errors="replace")
    records: list[RawRecord] = []
    try:
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]
        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue
            name = lines[0]
            if not name or len(name) < 3 or len(name) > 150:
                continue
            if re.match(r"^(page\s+\d+|\d+)$", name, re.IGNORECASE):
                continue
            block_text = " ".join(lines)
            phone_m = PHONE_RE.search(block_text)
            addr_m  = ADDR_RE.search(block_text)
            zip_m   = ZIP_RE.search(block_text)
            hours_m = HOURS_RE.search(block_text)
            if not phone_m and not addr_m and not zip_m:
                continue
            try:
                records.append(RawRecord(
                    source_id=source_id, name=name,
                    address=addr_m.group().strip() if addr_m else None,
                    zip=zip_m.group() if zip_m else None,
                    phone=phone_m.group().strip() if phone_m else None,
                    hours=hours_m.group() if hours_m else None,
                    raw_text=block_text,
                ))
            except Exception:
                pass
    except Exception as e:
        print(f"[generic_pdf] parse error for {source_id}: {e}")
    return records
