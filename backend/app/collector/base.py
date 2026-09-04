from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CollectedPost:
    source_username: str
    source_title: str | None
    external_id: str
    post_id: int
    text: str
    photo_url: str | None
    source_url: str
    posted_at: datetime | None
    html_text: str = ""
    video_url: str | None = None
    photo_urls: tuple[str, ...] = ()
