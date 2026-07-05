import os
from pathlib import Path

from dotenv import load_dotenv

# packages/ai-worker/db/config.py → repo root .env
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://culinary:culinary_dev@localhost:15432/culinary_funding",
)
CRAWL_DELAY_SECONDS = float(os.getenv("CRAWL_DELAY_SECONDS", "30"))
BASE_URL = os.getenv("BASE_URL", "https://www.foerderdatenbank.de").rstrip("/")

SEARCH_START_URL = (
    f"{BASE_URL}/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html"
    "?submit=Suchen&filterCategories=FundingProgram&sortOrder=dateOfIssue_dt+desc"
)
