from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SourceCreate(BaseModel):
    username: str = Field(min_length=2, max_length=512)


class SourceUpdate(BaseModel):
    enabled: bool | None = None
    title: str | None = None


class SourceOut(BaseModel):
    id: int
    username: str
    title: str | None
    enabled: bool
    source_kind: str = "public"
    invite_link: str | None = None
    last_post_id: int | None
    last_fetched_at: datetime | None
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("source_kind", mode="before")
    @classmethod
    def default_source_kind(cls, value: str | None) -> str:
        return value or "public"


class ItemOut(BaseModel):
    id: int
    source_username: str
    external_id: str
    raw_text: str
    photo_url: str | None
    source_url: str | None
    status: str
    similarity: float | None
    matched_item_id: int | None
    posted_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StatsOut(BaseModel):
    sources: int
    published: int
    duplicates: int
    skipped: int
    items_total: int
    mode: str
    last_fetch_at: datetime | None = None


class SettingsOut(BaseModel):
    app_mode: str
    target_channel: str
    similarity_threshold: float
    poll_interval_seconds: int
    min_text_length: int
    bot_configured: bool


class SettingsUpdate(BaseModel):
    similarity_threshold: float | None = Field(default=None, ge=0.5, le=0.99)
    poll_interval_seconds: int | None = Field(default=None, ge=15, le=3600)
    min_text_length: int | None = Field(default=None, ge=10, le=500)
    target_channel: str | None = None


class FetchResult(BaseModel):
    fetched: int
    published: int
    duplicates: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class TelegramUserStatusOut(BaseModel):
    configured: bool
    authorized: bool
    code_sent: bool = False
    user_id: int | None = None
    first_name: str | None = None
    username: str | None = None
    phone: str | None = None
    error: str | None = None


class TelegramCredentialsIn(BaseModel):
    api_id: int = Field(ge=1)
    api_hash: str = Field(min_length=8, max_length=128)


class TelegramSendCodeIn(BaseModel):
    phone: str = Field(min_length=8, max_length=32)
    api_id: int | None = Field(default=None, ge=1)
    api_hash: str | None = Field(default=None, min_length=8, max_length=128)


class TelegramSignInIn(BaseModel):
    phone: str = Field(min_length=8, max_length=32)
    code: str = Field(min_length=3, max_length=16)
    password: str | None = None
