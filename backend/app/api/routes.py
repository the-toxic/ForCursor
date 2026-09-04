from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collector.public_preview import is_valid_username, normalize_username
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Item, Source
from app.pipeline import NewsPipeline, seed_demo_sources
from app.schemas import (
    FetchResult,
    ItemOut,
    SettingsOut,
    SettingsUpdate,
    SourceCreate,
    SourceOut,
    SourceUpdate,
    StatsOut,
)
from app.settings_store import read_runtime_settings, write_runtime_settings

router = APIRouter(prefix="/api")


def get_pipeline() -> NewsPipeline:
    raise RuntimeError("Pipeline is not bound")


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "mode": settings.app_mode}


@router.get("/stats", response_model=StatsOut)
def stats(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    pipeline: NewsPipeline = Depends(get_pipeline),
) -> StatsOut:
    def count(status: str | None = None) -> int:
        query = select(func.count(Item.id))
        if status:
            query = query.where(Item.status == status)
        return int(db.scalar(query) or 0)

    return StatsOut(
        sources=int(db.scalar(select(func.count(Source.id))) or 0),
        published=count("published"),
        duplicates=count("duplicate"),
        skipped=count("skipped"),
        items_total=count(),
        mode=settings.app_mode,
        last_fetch_at=pipeline.last_fetch_at,
    )


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)) -> list[Source]:
    return db.query(Source).order_by(Source.id.asc()).all()


@router.post("/sources", response_model=SourceOut)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)) -> Source:
    username = normalize_username(payload.username)
    if not is_valid_username(username):
        raise HTTPException(status_code=400, detail="Некорректное имя канала")
    existing = db.scalar(select(Source).where(Source.username == username))
    if existing:
        raise HTTPException(status_code=409, detail="Такой источник уже добавлен")
    source = Source(username=username, enabled=True)
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: int, payload: SourceUpdate, db: Session = Depends(get_db)) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Источник не найден")
    if payload.enabled is not None:
        source.enabled = payload.enabled
    if payload.title is not None:
        source.title = payload.title
    db.commit()
    db.refresh(source)
    return source


@router.delete("/sources/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Источник не найден")
    db.delete(source)
    db.commit()
    return {"ok": True}


@router.get("/items", response_model=list[ItemOut])
def list_items(status: str | None = None, limit: int = 50, db: Session = Depends(get_db)) -> list[Item]:
    query = db.query(Item).order_by(Item.id.desc())
    if status:
        query = query.filter(Item.status == status)
    return query.limit(min(limit, 200)).all()


@router.get("/settings", response_model=SettingsOut)
def get_runtime_settings(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> SettingsOut:
    runtime = read_runtime_settings(db, settings)
    return SettingsOut(**runtime)


@router.patch("/settings", response_model=SettingsOut)
def patch_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SettingsOut:
    write_runtime_settings(db, payload.model_dump(exclude_none=True))
    return SettingsOut(**read_runtime_settings(db, settings))


@router.post("/fetch", response_model=FetchResult)
async def fetch_now(
    db: Session = Depends(get_db),
    pipeline: NewsPipeline = Depends(get_pipeline),
) -> FetchResult:
    return await pipeline.run_once(db)


@router.post("/demo/reset", response_model=FetchResult)
async def reset_demo(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    pipeline: NewsPipeline = Depends(get_pipeline),
) -> FetchResult:
    if not settings.is_demo:
        raise HTTPException(status_code=400, detail="Сброс доступен только в demo-режиме")
    db.query(Item).delete()
    db.query(Source).delete()
    db.commit()
    seed_demo_sources(db)
    return await pipeline.run_once(db)
