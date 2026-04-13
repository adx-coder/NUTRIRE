"""
Scraper registry — maps source config `scraper` field to scrape functions.

Each scraper takes (content: str | bytes, source_id: str) → list[RawRecord].
Only sources with `enabled=True` in config.py are scraped at runtime.
"""
from typing import Callable

from src.scrapers.cafb import scrape_cafb
from src.scrapers.mdfb import scrape_mdfb
from src.scrapers.two11md import scrape_two11md, scrape_two11va
from src.scrapers.mocofood import scrape_mocofood
from src.scrapers.pgcfec import scrape_pgcfec
from src.scrapers.caroline import scrape_caroline
from src.scrapers.generic_html import scrape_generic_html
from src.scrapers.generic_pdf import scrape_generic_pdf

SCRAPER_REGISTRY: dict[str, Callable] = {
    "cafb": scrape_cafb,
    "mdfb": scrape_mdfb,
    "two11md": scrape_two11md,
    "two11va": scrape_two11va,
    "mocofood": scrape_mocofood,
    "pgcfec": scrape_pgcfec,
    "caroline": scrape_caroline,
    "generic_html": scrape_generic_html,
    "generic_pdf": scrape_generic_pdf,
}
