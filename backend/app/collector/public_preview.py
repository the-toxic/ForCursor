from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.collector.base import CollectedPost
from app.collector.html_text import html_to_plain, telegram_html_from_message

PREVIEW_URL = "https://t.me/s/{username}"
CHANNEL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,31}$")
BACKGROUND_IMAGE_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")


def normalize_username(value: str) -> str:
    username = value.strip()
    username = re.sub(r"^https?://t\.me/(s/)?", "", username, flags=re.IGNORECASE)
    return username.lstrip("@")


def is_valid_username(value: str) -> bool:
    return bool(CHANNEL_RE.fullmatch(normalize_username(value)))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _absolute_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return None


def _photos_from_message(message: Tag) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for photo in message.select(".tgme_widget_message_photo_wrap"):
        style = photo.get("style") or ""
        match = BACKGROUND_IMAGE_RE.search(style)
        url = _absolute_url(match.group(1) if match else None)
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= 10:
            break
    return urls


def _video_from_message(message: Tag) -> str | None:
    video = message.select_one("video.tgme_widget_message_video") or message.select_one(
        ".tgme_widget_message_video_wrap video"
    )
    if not video:
        return None
    return _absolute_url(video.get("src"))


def parse_preview_html(html: str, username: str) -> list[CollectedPost]:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.select_one(".tgme_channel_info_header_title")
    title = title_tag.get_text(strip=True) if title_tag else username

    posts: list[CollectedPost] = []
    for message in soup.select(".tgme_widget_message"):
        data_post = message.get("data-post")
        if not data_post or "/" not in data_post:
            continue
        channel, raw_id = data_post.split("/", maxsplit=1)
        if not raw_id.isdigit():
            continue

        text_tag = message.select_one(".tgme_widget_message_text")
        html_text = telegram_html_from_message(text_tag)
        text = html_to_plain(html_text)
        time_tag = message.select_one("time")
        posted_at = _parse_datetime(time_tag.get("datetime") if time_tag else None)
        source_url = urljoin("https://t.me/", data_post)
        photos = _photos_from_message(message)

        posts.append(
            CollectedPost(
                source_username=channel,
                source_title=title,
                external_id=data_post,
                post_id=int(raw_id),
                text=text,
                html_text=html_text,
                photo_url=photos[0] if photos else None,
                photo_urls=tuple(photos),
                video_url=_video_from_message(message),
                source_url=source_url,
                posted_at=posted_at,
            )
        )

    posts.sort(key=lambda item: item.post_id)
    return posts


class PublicPreviewCollector:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    async def fetch(self, username: str) -> list[CollectedPost]:
        clean = normalize_username(username)
        if not is_valid_username(clean):
            raise ValueError(f"Некорректное имя канала: {username}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; NewsAggregator/1.0; +https://t.me/)"
            ),
            "Accept-Language": "ru,en;q=0.8",
        }
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(PREVIEW_URL.format(username=clean), headers=headers)
            response.raise_for_status()
        return parse_preview_html(response.text, clean)
