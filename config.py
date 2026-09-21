import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "tenders.db"

SITE_BASE_URL = "https://epms.ppra.gov.pk"
ACTIVE_TENDERS_PATH = "/public/tenders/active-tenders"

FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_GRAPH_API_VERSION = "v21.0"

# Pages per filter combination (newest first on page 1).
PAGES_TO_SCRAPE = int(os.getenv("PAGES_TO_SCRAPE", "2"))

# PPRA listing filters (IDs from the site's select options).
# tender_type=1 → Tender Notice only.
TENDER_TYPE = os.getenv("TENDER_TYPE", "1")

# Works + Goods + Non-consultancy Services
PROCUREMENT_CATEGORIES = [
    ("1", "Goods"),
    ("2", "Works"),
    ("4", "Non-consultancy Services"),
]

# Civil Works, Health/Medicines, Info and Comm Tech
SECTORS = [
    ("6", "Civil Works"),
    ("13", "Health/Medicines"),
    ("14", "Info and Comm Tech"),
]

# City filter uses city name strings on PPRA (not numeric ids).
CITIES = [
    c.strip()
    for c in os.getenv("CITIES", "Islamabad,Lahore,Karachi").split(",")
    if c.strip()
]

# Digest buckets = sectors (same order as SECTORS). Override with niche ids:
# civil_works, health, ict
_ENABLED_NICHES_RAW = os.getenv("ENABLED_NICHES", "civil_works,health,ict")
ENABLED_NICHES = [n.strip() for n in _ENABLED_NICHES_RAW.split(",") if n.strip()]

MAX_DIGEST_POSTS_PER_DAY = int(os.getenv("MAX_DIGEST_POSTS_PER_DAY", "3"))
# Cards on the digest image (aim for a readable set — at least 4 when available).
DIGEST_MAX_ITEMS = int(os.getenv("DIGEST_MAX_ITEMS", "4"))
# Max tenders listed in the Facebook caption.
DIGEST_CAPTION_MAX = int(os.getenv("DIGEST_CAPTION_MAX", "10"))

POST_DELAY_SECONDS = int(os.getenv("POST_DELAY_SECONDS", "3600"))
RUN_TIME = os.getenv("RUN_TIME", "09:00")
