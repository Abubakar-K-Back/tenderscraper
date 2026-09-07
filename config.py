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

PAGES_TO_SCRAPE = int(os.getenv("PAGES_TO_SCRAPE", "2"))
MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "15"))
POST_DELAY_SECONDS = int(os.getenv("POST_DELAY_SECONDS", "8"))
