import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

# packages/ai-worker/db/config.py → repo root .env
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")


def _build_database_url() -> str:
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        url = explicit.strip().strip('"').strip("'")
        # psycopg3 driver prefix
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "culinary")
    password = os.getenv("DB_PASSWORD", "")
    name = os.getenv("DB_NAME", "culinary_funding")

    user_enc = quote_plus(user)
    password_enc = quote_plus(password)
    return f"postgresql+psycopg://{user_enc}:{password_enc}@{host}:{port}/{name}"


DATABASE_URL = _build_database_url()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "culinary")
DB_NAME = os.getenv("DB_NAME", "culinary_funding")
API_PORT = int(os.getenv("PORT", "3009"))

CRAWL_DELAY_SECONDS = float(os.getenv("CRAWL_DELAY_SECONDS", "30"))
BASE_URL = os.getenv("BASE_URL", "https://www.foerderdatenbank.de").rstrip("/")

SEARCH_START_URL = (
    f"{BASE_URL}/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html"
    "?submit=Suchen&filterCategories=FundingProgram&sortOrder=dateOfIssue_dt+desc"
)
