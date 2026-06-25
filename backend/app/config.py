import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")
logger = logging.getLogger(__name__)


# 数据库配置
DB_DIR = BACKEND_DIR / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_DB_PATH = DB_DIR / "app.db"
DATABASE_URL = f"sqlite:///{SQLITE_DB_PATH.as_posix()}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 大模型配置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai_compatible")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))


# 认证 / JWT 配置
_jwt_secret_key = os.getenv("JWT_SECRET_KEY", "").strip()
JWT_SECRET_KEY_CONFIGURED = bool(_jwt_secret_key)
JWT_SECRET_KEY = _jwt_secret_key or secrets.token_urlsafe(32)
if not JWT_SECRET_KEY_CONFIGURED:
    logger.warning(
        "JWT_SECRET_KEY is not configured; using a process-local temporary key. "
        "Tokens will be invalid after backend restart."
    )

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)


# RAG / 向量库配置
_chroma_db_dir_raw = Path(os.getenv("CHROMA_DB_DIR", "db/chroma_db"))
CHROMA_DB_DIR = (
    _chroma_db_dir_raw
    if _chroma_db_dir_raw.is_absolute()
    else BACKEND_DIR / _chroma_db_dir_raw
)
CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "travel_guides")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
RERANK_MODEL = os.getenv("RERANK_MODEL", "qwen3-rerank")


# Redis / 缓存配置
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "trip_planner")
REDIS_DEFAULT_TTL_SECONDS = int(os.getenv("REDIS_DEFAULT_TTL_SECONDS", "1800"))
REDIS_WEATHER_TTL_SECONDS = int(os.getenv("REDIS_WEATHER_TTL_SECONDS", "1800"))
REDIS_MAP_TTL_SECONDS = int(os.getenv("REDIS_MAP_TTL_SECONDS", "86400"))
REDIS_RAG_TTL_SECONDS = int(os.getenv("REDIS_RAG_TTL_SECONDS", "21600"))
REDIS_RERANK_TTL_SECONDS = int(os.getenv("REDIS_RERANK_TTL_SECONDS", "21600"))


# 高德地图配置
AMAP_API_KEY = os.getenv("AMAP_API_KEY", "")
AMAP_BASE_URL = os.getenv("AMAP_BASE_URL", "https://restapi.amap.com/v3")
AMAP_DEFAULT_CITY = os.getenv("AMAP_DEFAULT_CITY", "")
AMAP_TIMEOUT_SECONDS = int(os.getenv("AMAP_TIMEOUT_SECONDS", "20"))
ENABLE_AMAP_ENRICHMENT = os.getenv("ENABLE_AMAP_ENRICHMENT", "false").lower() == "true"


# Tavily search, exposed only through the backend whitelist tool.
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_API_URL = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")
TAVILY_TIMEOUT_SECONDS = int(os.getenv("TAVILY_TIMEOUT_SECONDS", "20"))
TAVILY_MAX_RETRIES = int(os.getenv("TAVILY_MAX_RETRIES", "1"))


# Browser price observation. The tool is read-only and disabled by default.
BROWSER_ENABLED = os.getenv("BROWSER_ENABLED", "false").lower() == "true"
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
BROWSER_TIMEOUT_SECONDS = int(os.getenv("BROWSER_TIMEOUT_SECONDS", "30"))
BROWSER_ALLOWED_DOMAINS = [
    domain.strip().lower()
    for domain in os.getenv("BROWSER_ALLOWED_DOMAINS", "*").split(",")
    if domain.strip()
]
BROWSER_MAX_URLS = int(os.getenv("BROWSER_MAX_URLS", "4"))
BROWSER_MAX_PRICE_ITEMS = int(os.getenv("BROWSER_MAX_PRICE_ITEMS", "8"))
BROWSER_REQUIRE_HUMAN_ON_LOGIN = os.getenv("BROWSER_REQUIRE_HUMAN_ON_LOGIN", "true").lower() == "true"
BROWSER_REQUIRE_HUMAN_ON_CAPTCHA = os.getenv("BROWSER_REQUIRE_HUMAN_ON_CAPTCHA", "true").lower() == "true"
BROWSER_HUMAN_WAIT_SECONDS = int(os.getenv("BROWSER_HUMAN_WAIT_SECONDS", "60"))
# Connect to an already-running Chrome via CDP (e.g. http://localhost:9222).
# When set, this takes priority over launching a new browser.
BROWSER_CDP_URL = os.getenv("BROWSER_CDP_URL", "").strip() or None
# Path to a persistent Chrome user-data directory. When set and CDP is not used,
# the browser is launched with a persistent profile that preserves cookies and
# sessions across runs. Useful for keeping Ctrip login state.
BROWSER_USER_DATA_DIR = os.getenv("BROWSER_USER_DATA_DIR", "").strip() or None
