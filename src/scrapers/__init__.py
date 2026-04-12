from typing import Callable
from src.scrapers.generic_html import scrape_generic_html
from src.scrapers.generic_pdf import scrape_generic_pdf
from src.scrapers.cafb import scrape_cafb
from src.scrapers.mdfb import scrape_mdfb
from src.scrapers.two11md import scrape_two11md, scrape_two11va
from src.scrapers.pgcfec import scrape_pgcfec
from src.scrapers.mocofood import scrape_mocofood
from src.scrapers.caroline import scrape_caroline

SCRAPER_REGISTRY: dict[str, Callable] = {
    "cafb": scrape_cafb,
    "mdfb": scrape_mdfb,
    "two11md": scrape_two11md,
    "two11va": scrape_two11va,
    "pgcfec": scrape_pgcfec,
    "mocofood": scrape_mocofood,
    "caroline": scrape_caroline,
    "generic-html": scrape_generic_html,
    "generic-pdf": scrape_generic_pdf,
}
