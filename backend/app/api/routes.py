from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collector.invite import parse_source_ref
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
    TelegramCredentialsIn,
    TelegramSendCodeIn,
    TelegramSignInIn,
    TelegramUserStatusOut,
)
from app.settings_store import read_runtime_settings, read_telegram_credentials, write_runtime_settings
from app.telegram_user import telegram_user_service

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
async def create_source(
    payload: SourceCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Source:
    parsed = parse_source_ref(payload.username)
    if parsed is None:
        raise HTTPException(
            status_code=400,
            detail="Укажите @username публичного канала или invite-ссылку t.me/+…",
        )
    existing = db.scalar(select(Source).where(Source.username == parsed.username))
    if existing:
        raise HTTPException(status_code=409, detail="Такой источник уже добавлен")
    if parsed.invite_hash:
        duplicate_invite = db.scalar(select(Source).where(Source.invite_hash == parsed.invite_hash))
        if duplicate_invite:
            raise HTTPException(status_code=409, detail="Такой источник уже добавлен")

    if parsed.kind == "public":
        source = Source(username=parsed.username, enabled=True, source_kind="public")
        db.add(source)
        db.commit()
        db.refresh(source)
        return source

    api_id, api_hash = read_telegram_credentials(db, settings)
    if not api_id or not api_hash:
        raise HTTPException(
            status_code=400,
            detail="Чтобы добавить закрытый канал, укажите API ID и API Hash в блоке «Закрытые каналы».",
        )
    if not await telegram_user_service.is_authorized(api_id, api_hash, settings.telegram_session_path):
        raise HTTPException(
            status_code=400,
            detail="Войдите в Telegram-аккаунт в блоке «Закрытые каналы», затем вставьте ссылку-приглашение.",
        )
    try:
        title, _joined_username, peer_id = await telegram_user_service.join_invite(
            api_id,
            api_hash,
            settings.telegram_session_path,
            parsed.invite_hash or "",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    source = Source(
        username=parsed.username,
        title=title,
        enabled=True,
        source_kind="private",
        invite_hash=parsed.invite_hash,
        invite_link=parsed.invite_link,
        telegram_peer_id=str(peer_id),
    )
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


@router.get("/telegram-user", response_model=TelegramUserStatusOut)
async def telegram_user_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TelegramUserStatusOut:
    api_id, api_hash = read_telegram_credentials(db, settings)
    payload = await telegram_user_service.status(api_id, api_hash, settings.telegram_session_path)
    return TelegramUserStatusOut(**payload)


@router.post("/telegram-user/credentials", response_model=TelegramUserStatusOut)
async def save_telegram_credentials(
    payload: TelegramCredentialsIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TelegramUserStatusOut:
    write_runtime_settings(
        db,
        {"telegram_api_id": payload.api_id, "telegram_api_hash": payload.api_hash.strip()},
    )
    status = await telegram_user_service.status(
        payload.api_id,
        payload.api_hash.strip(),
        settings.telegram_session_path,
    )
    return TelegramUserStatusOut(**status)


@router.post("/telegram-user/send-code")
async def send_telegram_code(
    payload: TelegramSendCodeIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if payload.api_id and payload.api_hash:
        write_runtime_settings(
            db,
            {"telegram_api_id": payload.api_id, "telegram_api_hash": payload.api_hash.strip()},
        )
    api_id, api_hash = read_telegram_credentials(db, settings)
    if not api_id or not api_hash:
        raise HTTPException(
            status_code=400,
            detail="Сначала укажите API ID и API Hash с my.telegram.org.",
        )
    try:
        return await telegram_user_service.send_code(
            api_id,
            api_hash,
            settings.telegram_session_path,
            payload.phone,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/telegram-user/sign-in", response_model=TelegramUserStatusOut)
async def sign_in_telegram(
    payload: TelegramSignInIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TelegramUserStatusOut:
    api_id, api_hash = read_telegram_credentials(db, settings)
    if not api_id or not api_hash:
        raise HTTPException(
            status_code=400,
            detail="Сначала укажите API ID и API Hash с my.telegram.org.",
        )
    try:
        await telegram_user_service.sign_in(
            api_id,
            api_hash,
            settings.telegram_session_path,
            payload.phone,
            payload.code,
            payload.password,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    status = await telegram_user_service.status(api_id, api_hash, settings.telegram_session_path)
    return TelegramUserStatusOut(**status)


@router.post("/telegram-user/logout", response_model=TelegramUserStatusOut)
async def logout_telegram(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TelegramUserStatusOut:
    await telegram_user_service.logout()
    api_id, api_hash = read_telegram_credentials(db, settings)
    status = await telegram_user_service.status(api_id, api_hash, settings.telegram_session_path)
    return TelegramUserStatusOut(**status)


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
