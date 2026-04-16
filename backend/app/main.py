from fastapi import FastAPI
from app.api import health, config, jobs

def create_app() -> FastAPI:
    app = FastAPI(title="ExtractAssets")
    app.include_router(health.router, prefix="/api")
    app.include_router(config.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    return app

app = create_app()
