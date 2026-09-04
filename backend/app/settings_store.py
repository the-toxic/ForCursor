from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AppSetting

RUNTIME_KEYS = (
    "similarity_threshold",
    "poll_interval_seconds",
    "min_text_length",
    "target_channel",
    "telegram_api_id",
    "telegram_api_hash",
)


def _coerce(key: str, raw: str, fallback: object) -> object:
    if raw == "":
        return fallback
    if key in {"similarity_threshold"}:
        return float(raw)
    if key in {"poll_interval_seconds", "min_text_length"}:
        return int(raw)
    return raw


def read_runtime_settings(db: Session, base: Settings) -> dict[str, object]:
    stored = {row.key: row.value for row in db.query(AppSetting).all()}
    return {
        "similarity_threshold": _coerce(
            "similarity_threshold",
            stored.get("similarity_threshold", ""),
            base.similarity_threshold,
        ),
        "poll_interval_seconds": _coerce(
            "poll_interval_seconds",
            stored.get("poll_interval_seconds", ""),
            base.poll_interval_seconds,
        ),
        "min_text_length": _coerce(
            "min_text_length",
            stored.get("min_text_length", ""),
            base.min_text_length,
        ),
        "target_channel": _coerce(
            "target_channel",
            stored.get("target_channel", ""),
            base.target_channel,
        ),
        "app_mode": base.app_mode,
        "bot_configured": bool(base.bot_token and (stored.get("target_channel") or base.target_channel)),
    }


def read_telegram_credentials(db: Session, base: Settings) -> tuple[int, str]:
    stored = {row.key: row.value for row in db.query(AppSetting).all()}
    raw_id = stored.get("telegram_api_id") or (str(base.telegram_api_id) if base.telegram_api_id else "")
    api_hash = stored.get("telegram_api_hash") or base.telegram_api_hash or ""
    try:
        api_id = int(raw_id) if raw_id else 0
    except ValueError:
        api_id = 0
    return api_id, api_hash


def write_runtime_settings(db: Session, updates: dict[str, object]) -> None:
    for key, value in updates.items():
        if key not in RUNTIME_KEYS or value is None:
            continue
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=str(value)))
        else:
            row.value = str(value)
    db.commit()
