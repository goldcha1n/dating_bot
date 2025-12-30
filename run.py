from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import uvicorn

from app.api import create_api
from app.bot import start_bot
from app.config import ENV_FILE, LOGS_DIR, Settings, ensure_runtime_paths, get_settings

# Repo root
BASE_DIR = Path(__file__).resolve().parent

logger = logging.getLogger(__name__)


def setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def print_diagnostics(settings: Settings) -> None:
    logger.info("Repo root: %s", BASE_DIR)
    logger.info(".env path: %s", ENV_FILE)
    if settings.sqlite_path:
        logger.info("DB path: %s", settings.sqlite_path)
    else:
        logger.info("DB url: %s", settings.database_url)
    logger.info("API listening: http://%s:%s", settings.host, settings.port)


async def start_api(settings: Settings) -> None:
    app = create_api(settings)
    config = uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info("api started")
    try:
        await server.serve()
    except asyncio.CancelledError:
        server.should_exit = True
        raise


async def main() -> None:
    ensure_runtime_paths()
    settings = get_settings()

    setup_logging(LOGS_DIR / "app.log")
    print_diagnostics(settings)

    tasks = [
        asyncio.create_task(start_api(settings), name="api"),
        asyncio.create_task(start_bot(settings), name="bot"),
    ]

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutdown requested, cancelling services...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        logger.exception("Service crashed, stopping services...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
