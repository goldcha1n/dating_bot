from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin
from app.config import Settings, STATIC_DIR
from app.db import create_engine, create_sessionmaker
from db import init_db


def create_api(settings: Settings) -> FastAPI:
    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)

    app = FastAPI(title="Адмін панель")
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(admin.router)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.on_event("startup")
    async def _init_db() -> None:
        await init_db(engine)

    @app.on_event("shutdown")
    async def _shutdown_db() -> None:
        await engine.dispose()

    return app
