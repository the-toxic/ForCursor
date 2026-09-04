from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes
from app.auth import AccessKeyMiddleware
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.pipeline import NewsPipeline, seed_demo_sources, seed_env_sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()
    pipeline = NewsPipeline(settings)
    app.state.pipeline = pipeline

    db = SessionLocal()
    try:
        if settings.is_demo:
            seed_demo_sources(db)
        seed_env_sources(db, settings.source_usernames)
    finally:
        db.close()

    stop_event = asyncio.Event()

    async def poller() -> None:
        while not stop_event.is_set():
            db_loop = SessionLocal()
            try:
                runtime_interval = settings.poll_interval_seconds
                from app.settings_store import read_runtime_settings

                runtime_interval = int(read_runtime_settings(db_loop, settings)["poll_interval_seconds"])
                await pipeline.run_once(db_loop)
            except Exception:
                pass
            finally:
                db_loop.close()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=runtime_interval)
            except TimeoutError:
                continue

    task = asyncio.create_task(poller())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Telegram News Aggregator",
        description="Сбор публичных каналов, дедупликация и публикация уникальных новостей.",
        lifespan=lifespan,
    )
    application.state.auth_key = settings.auth_key
    application.add_middleware(AccessKeyMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def pipeline_dep() -> NewsPipeline:
        return application.state.pipeline

    application.dependency_overrides[routes.get_pipeline] = pipeline_dep
    application.include_router(routes.router)
    return application


app = create_app()
