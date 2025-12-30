import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DEFAULT_DB_PATH = DATA_DIR / "db.sqlite3"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"


def ensure_runtime_paths() -> None:
    """Make sure required folders and files exist before startup."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    if not ENV_FILE.exists():
        ENV_FILE.write_text(
            "# Fill in the required values before running the app\n"
            "BOT_TOKEN=\n"
            "API_URL=http://localhost\n"
            "CHAT_ID=\n"
            "HOST=127.0.0.1\n"
            "PORT=8000\n"
            "DATABASE_URL=\n"
            "ADMINS=\n"
            "ADMIN_USERNAME=admin\n"
            "ADMIN_PASSWORD=change-me\n"
            "SECRET_KEY=change-me-please\n"
            "SESSION_TTL_SECONDS=43200\n"
            "ABOUT_MIN_LEN=10\n"
            "MAX_PHOTOS=3\n"
            "LIKE_LIMIT_PER_HOUR=20\n"
            "VIEW_LIMIT_PER_MIN=40\n"
            "ACTION_LIMIT_PER_MIN=60\n"
            "DAILY_RESET_ENABLED=1\n"
            "DAILY_RESET_HOUR=8\n"
            "DAILY_RESET_TZ=Europe/Kyiv\n",
            encoding="utf-8",
        )

    DEFAULT_DB_PATH.touch(exist_ok=True)


def _parse_admins(raw: str | None) -> List[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    items = [x.strip() for x in raw.split(",") if x.strip()]
    out: List[int] = []
    for item in items:
        try:
            out.append(int(item))
        except ValueError:
            continue
    return out


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    bot_token: str
    api_url: str
    chat_id: str
    host: str
    port: int
    database_url: str
    admin_username: str
    admin_password: str
    secret_key: str
    session_ttl_seconds: int
    admins: List[int]
    about_min_len: int = 10
    max_photos: int = 3
    like_limit_per_hour: int = 20
    view_limit_per_min: int = 40
    action_limit_per_min: int = 60
    reset_enabled: bool = True
    reset_hour: int = 8
    reset_timezone: str = "Europe/Kyiv"

    @property
    def sqlite_path(self) -> Path | None:
        if self.database_url.startswith("sqlite"):
            # sqlite+aiosqlite:///C:/... or sqlite+aiosqlite:///./db.sqlite3
            trimmed = self.database_url.split(":///", maxsplit=1)[-1]
            return Path(trimmed).resolve()
        return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    ensure_runtime_paths()
    load_dotenv(ENV_FILE)

    host = os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("PORT", "8000"))

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}"

    return Settings(
        bot_token=_require_env("BOT_TOKEN"),
        api_url=os.getenv("API_URL", f"http://{host}:{port}").strip() or f"http://{host}:{port}",
        chat_id=os.getenv("CHAT_ID", "").strip(),
        host=host,
        port=port,
        database_url=db_url,
        admin_username=os.getenv("ADMIN_USERNAME", "admin").strip() or "admin",
        admin_password=os.getenv("ADMIN_PASSWORD", "change-me").strip() or "change-me",
        secret_key=os.getenv("SECRET_KEY", "change-me-please").strip() or "change-me-please",
        session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "43200")),
        admins=_parse_admins(os.getenv("ADMINS")),
        about_min_len=int(os.getenv("ABOUT_MIN_LEN", "10")),
        max_photos=int(os.getenv("MAX_PHOTOS", "3")),
        like_limit_per_hour=int(os.getenv("LIKE_LIMIT_PER_HOUR", "20")),
        view_limit_per_min=int(os.getenv("VIEW_LIMIT_PER_MIN", "40")),
        action_limit_per_min=int(os.getenv("ACTION_LIMIT_PER_MIN", "60")),
        reset_enabled=_parse_bool(os.getenv("DAILY_RESET_ENABLED"), True),
        reset_hour=int(os.getenv("DAILY_RESET_HOUR", "8")),
        reset_timezone=os.getenv("DAILY_RESET_TZ", "Europe/Kyiv").strip() or "Europe/Kyiv",
    )


# Compatibility aliases for existing imports
Config = Settings
load_config = get_settings
