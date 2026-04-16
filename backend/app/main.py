from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.api import health, config, jobs, assets, ws

STATIC_DIR = Path(__file__).parent / "static"

def create_app() -> FastAPI:
    app = FastAPI(title="ExtractAssets")
    app.include_router(health.router, prefix="/api")
    app.include_router(config.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(assets.router, prefix="/api")
    app.include_router(ws.router)

    if STATIC_DIR.exists():
        @app.get("/")
        def index():
            return FileResponse(STATIC_DIR / "index.html")

        @app.get("/{full_path:path}")
        def spa_catch_all(full_path: str):
            candidate = STATIC_DIR / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(STATIC_DIR / "index.html")

    return app

app = create_app()
