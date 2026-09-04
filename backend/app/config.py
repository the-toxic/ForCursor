from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_mode: str = Field(default="demo")
    bot_token: str = ""
    target_channel: str = ""
    source_channels: str = ""
    similarity_threshold: float = 0.82
    poll_interval_seconds: int = 90
    min_text_length: int = 40
    dedup_window: int = 400
    database_url: str = "sqlite:///./data/aggregator.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    auth_key: str = "toxic"

    @property
    def is_demo(self) -> bool:
        return self.app_mode.strip().lower() == "demo"

    @property
    def source_usernames(self) -> list[str]:
        return [
            item.strip().lstrip("@")
            for item in self.source_channels.split(",")
            if item.strip()
        ]

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
