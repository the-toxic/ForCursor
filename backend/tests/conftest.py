from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api import routes
from app.auth import AccessKeyMiddleware
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Base
from app.pipeline import NewsPipeline, seed_demo_sources


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    get_settings.cache_clear()
    return Settings(
        app_mode="demo",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        bot_token="",
        target_channel="@demo_target",
        similarity_threshold=0.82,
        min_text_length=40,
        poll_interval_seconds=90,
        auth_key="toxic",
    )


@pytest.fixture
def db_session(settings: Settings) -> Generator[Session, None, None]:
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def pipeline(settings: Settings) -> NewsPipeline:
    return NewsPipeline(settings)


@pytest.fixture
def client(settings: Settings, db_session: Session, pipeline: NewsPipeline) -> Generator[TestClient, None, None]:
    seed_demo_sources(db_session)
    app = FastAPI()
    app.state.auth_key = settings.auth_key
    app.add_middleware(AccessKeyMiddleware)
    app.include_router(routes.router)
    app.state.pipeline = pipeline

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[routes.get_pipeline] = lambda: pipeline

    with TestClient(app, headers={"X-Auth-Key": settings.auth_key}) as test_client:
        yield test_client
