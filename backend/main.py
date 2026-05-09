"""FastAPI entrypoint for the Minecraft AI backend."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.builds import router as builds_router
<<<<<<< HEAD
from api.debug import router as debug_router
=======
from api.generate import router as generate_router
>>>>>>> origin/frontend
from api.health import router as health_router
from config import get_settings
from storage.jobs import JobStore


_settings = get_settings()
logging.basicConfig(
    level=_settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
_settings.artifacts_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = _settings
    app.state.job_store = JobStore()
    app.state.artifacts_dir = _settings.artifacts_dir
    app.state.tasks = set()
    try:
        yield
    finally:
        pending = list(app.state.tasks)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


app = FastAPI(
    title="Minecraft AI Backend",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(builds_router)
<<<<<<< HEAD
app.include_router(debug_router)
=======
app.include_router(generate_router)
>>>>>>> origin/frontend
app.mount(
    "/static",
    StaticFiles(directory=str(_settings.artifacts_dir), check_dir=False),
    name="static",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "minecraft-ai-backend",
        "version": "0.1.0",
        "docs": "/docs",
    }
