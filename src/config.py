from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class SourceConfig:
    id: str
    name: str
    url: str
    type: Literal["html", "pdf", "api"]
    scraper: str
    change_detection: Literal["content-hash", "http-headers", "always"]
    priority: Literal["high", "medium", "low"]
    tags: list[str]
    enabled: bool
    selector: Optional[str] = None


SOURCES: list[SourceConfig] = [
    SourceConfig(
        id="cafb", name="Capital Area Food Bank",
        url="https://www.capitalareafoodbank.org/",
        type="html", scraper="cafb", selector="main",
        change_detection="content-hash", priority="high",
        tags=["food-bank", "dc", "maryland", "virginia", "distribution"], enabled=True,
    ),
    SourceConfig(
        id="mdfb-find-food", name="Maryland Food Bank Find Food",
        url="https://mdfoodbank.org/find-food/#more",
        type="html", scraper="mdfb", selector="#content",
        change_detection="content-hash", priority="high",
        tags=["food-bank", "maryland", "pantry"], enabled=True,
    ),
    SourceConfig(
        id="two11md", name="211 Maryland Food Pantry Search",
        url="https://search.211md.org/search?query=food+pantry",
        type="html", scraper="two11md", selector=".results",
        change_detection="content-hash", priority="high",
        tags=["211", "maryland", "pantry", "directory"], enabled=True,
    ),
    SourceConfig(
        id="two11va", name="211 Virginia Food Pantry Search",
        url="https://search.211virginia.org/search?query=food+pantry",
        type="html", scraper="two11va", selector=".results",
        change_detection="content-hash", priority="high",
        tags=["211", "virginia", "pantry", "directory"], enabled=True,
    ),
    SourceConfig(
        id="pgcfec", name="PG County Food Equity Council",
        url="https://pgcfec.org/resources/find-food-food-pantry-listings/",
        type="html", scraper="pgcfec", selector=".entry-content",
        change_detection="content-hash", priority="medium",
        tags=["pg-county", "pantry", "food-equity"], enabled=True,
    ),
    SourceConfig(
        id="mocofood", name="Montgomery County Food Council Map",
        url="https://mocofoodcouncil.org/map/",
        type="html", scraper="mocofood", selector="#page",
        change_detection="content-hash", priority="medium",
        tags=["montgomery-county", "map", "pantry"], enabled=True,
    ),
    SourceConfig(
        id="feeding-america", name="Feeding America Map the Meal Gap",
        url="https://map.feedingamerica.org",
        type="html", scraper="generic_html", selector="body",
        change_detection="content-hash", priority="medium",
        tags=["food-insecurity", "national", "map"], enabled=False,  # aggregate dashboard, no org records
    ),
    SourceConfig(
        id="md-open-data", name="Maryland Open Data Portal",
        url="https://opendata.maryland.gov",
        type="api", scraper="generic_html", selector="main",
        change_detection="http-headers", priority="low",
        tags=["open-data", "maryland", "demographics"], enabled=False,  # portal homepage, zero orgs extracted
    ),
    SourceConfig(
        id="dc-open-data", name="DC Open Data Portal",
        url="https://opendata.dc.gov/",
        type="api", scraper="generic_html", selector="main",
        change_detection="http-headers", priority="low",
        tags=["open-data", "dc", "demographics"], enabled=False,  # portal homepage, zero orgs extracted
    ),
    SourceConfig(
        id="va-open-data", name="Virginia Open Data Portal",
        url="https://data.virginia.gov/",
        type="api", scraper="generic_html", selector="main",
        change_detection="http-headers", priority="low",
        tags=["open-data", "virginia", "demographics"], enabled=False,  # portal homepage, zero orgs extracted
    ),
    SourceConfig(
        id="pg-open-data", name="PG County Open Data",
        url="https://data.princegeorgescountymd.gov/",
        type="api", scraper="generic_html", selector="main",
        change_detection="http-headers", priority="low",
        tags=["open-data", "pg-county"], enabled=False,  # portal homepage, zero orgs extracted
    ),
    SourceConfig(
        id="mda-insecurity-map", name="Maryland Food Insecurity Map",
        url="https://mda.maryland.gov/",
        type="html", scraper="generic_html", selector="#content",
        change_detection="content-hash", priority="medium",
        tags=["food-insecurity", "maryland", "map"], enabled=False,  # MD Dept of Ag aggregate, no org records
    ),
    SourceConfig(
        id="usda-food-atlas", name="USDA Food Environment Atlas",
        url="https://www.ers.usda.gov/data-products/food-environment-atlas",
        type="html", scraper="generic_html", selector="main",
        change_detection="http-headers", priority="low",
        tags=["usda", "food-environment", "national"], enabled=False,  # aggregate census atlas, pull CSV directly instead
    ),
    SourceConfig(
        id="umd-extension", name="UMD Extension Food Access Resources",
        url="https://extension.umd.edu/resource/food-access-resources/",
        type="html", scraper="generic_html", selector=".field--type-text-with-summary",
        change_detection="content-hash", priority="medium",
        tags=["umd", "maryland", "food-access", "directory"], enabled=False,  # thin page, occasional links only
    ),
    SourceConfig(
        id="epa-excess-food", name="EPA Excess Food Opportunities Map",
        url="https://www.epa.gov/sustainable-management-food/excess-food-opportunities-map",
        type="html", scraper="generic_html", selector="main",
        change_detection="http-headers", priority="low",
        tags=["epa", "food-recovery", "waste"], enabled=False,  # food WASTE mapping, wrong use case
    ),
    SourceConfig(
        id="md-compass", name="Maryland Community Business Compass",
        url="https://compass.maryland.gov/map/",
        type="html", scraper="generic_html", selector="main",
        change_detection="http-headers", priority="low",
        tags=["maryland", "community", "map"], enabled=False,  # generic business map, not pantry-specific
    ),
    SourceConfig(
        id="pg-healthy-food", name="PG County Healthy Food Priority Areas",
        url="https://princegeorges.maps.arcgis.com/apps/dashboards/9f9202c51cc345ab9e0e1aa21a23bb76",
        type="html", scraper="generic_html", selector="body",
        change_detection="http-headers", priority="low",
        tags=["pg-county", "food-access", "arcgis"], enabled=False,  # ArcGIS dashboard, not scrapable
    ),
    SourceConfig(
        id="kofc-pdf", name="Food Pantry PDF — Knights of Columbus",
        url="https://kofc-md.org/wp-content/uploads/2019/06/food-pantries-in-mdpdf-1.pdf",
        type="pdf", scraper="generic_pdf",
        change_detection="http-headers", priority="low",
        tags=["pdf", "maryland", "pantry", "knights-of-columbus"], enabled=False,  # 2019 PDF, stale
    ),
    SourceConfig(
        id="msa-pdf", name="Food Pantry PDF — MSA Maryland",
        url="https://msa.maryland.gov/megafile/msa/speccol/sc5300/sc5339/000113/014000/014769/unrestricted/20120605e-021.pdf",
        type="pdf", scraper="generic_pdf",
        change_detection="http-headers", priority="low",
        tags=["pdf", "maryland", "pantry", "msa"], enabled=False,  # 2012 PDF, very stale
    ),
    SourceConfig(
        id="mdfb-hunger-map", name="Maryland Food Bank Hunger Map",
        url="https://mdfoodbank.org/hunger-in-maryland",
        type="html", scraper="mdfb", selector="#content",
        change_detection="content-hash", priority="medium",
        tags=["food-bank", "maryland", "hunger-map"], enabled=False,  # duplicate of mdfb-find-food
    ),
    SourceConfig(
        id="two11md-alt", name="211 Maryland Food Pantry Search (Full)",
        url="https://search.211md.org/search?query=food+pantry&query_label=food+pantry&query_type=text",
        type="html", scraper="two11md", selector=".results",
        change_detection="content-hash", priority="medium",
        tags=["211", "maryland", "pantry", "directory"], enabled=False,  # duplicate of two11md
    ),
    SourceConfig(
        id="caroline", name="Caroline County Food Pantries",
        url="https://carolinebettertogether.org/food-pantries",
        type="html", scraper="caroline", selector=".entry-content",
        change_detection="content-hash", priority="medium",
        tags=["caroline-county", "maryland", "pantry"], enabled=False,  # not metro DMV
    ),
    SourceConfig(
        id="usda-snap", name="USDA SNAP Retailer Locator",
        url="https://usda-fns.maps.arcgis.com/apps/webappviewer/index.html?id=15e1c457b56c4a729861d015cd626a23",
        type="html", scraper="generic_html", selector="body",
        change_detection="http-headers", priority="low",
        tags=["usda", "snap", "retail", "arcgis"], enabled=False,  # SNAP retailers (stores), not free-food pantries
    ),
    SourceConfig(
        id="epa-landfill", name="EPA Landfill Technical Data",
        url="https://www.epa.gov/lmop/landfill-technical-data",
        type="html", scraper="generic_html", selector="main",
        change_detection="http-headers", priority="low",
        tags=["epa", "landfill", "waste-diversion"], enabled=False,  # literally landfill data, wrong use case
    ),
]
