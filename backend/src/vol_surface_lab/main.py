from __future__ import annotations

from fastapi import FastAPI

from vol_surface_lab.config import get_settings
from vol_surface_lab.routers import router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Vol Surface Lab API",
        version="0.1.0",
        description=(
            "Research-only implied volatility surfaces from EOD option CSV uploads. "
            "No broker connectivity or live trading. See /api/v1 routes for assumptions."
        ),
    )
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
