from __future__ import annotations

import html
from dataclasses import dataclass

import httpx

from app.collector.base import CollectedPost
from app.collector.html_text import strip_custom_emoji_tags
from app.errors import sanitize_error

MAX_VIDEO_BYTES = 49 * 1024 * 1024
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://t.me/",
}


@dataclass(frozen=True, slots=True)
class PublishResult:
    message_id: str | None
    dry_run: bool


def format_post(post: CollectedPost) -> str:
    source = html.escape(post.source_title or post.source_username)
    url = html.escape(post.source_url, quote=True)
    body = (post.html_text or html.escape(post.text)).strip()
    footer = f'\n\n<a href="{url}">{source}</a>'
    return f"{body}{footer}" if body else footer.strip()


class TelegramPublisher:
    def __init__(self, token: str, target_channel: str, dry_run: bool = False) -> None:
        self.token = token
        self.target_channel = target_channel
        self.dry_run = dry_run

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.target_channel) and not self.dry_run

    async def _telegram_json(self, client: httpx.AsyncClient, method: str, **kwargs) -> dict:
        response = await client.post(f"https://api.telegram.org/bot{self.token}/{method}", **kwargs)
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Telegram вернул не JSON ({response.status_code})") from exc
        if not data.get("ok"):
            raise RuntimeError(data.get("description") or f"Telegram error {response.status_code}")
        return data

    async def _send_html_message(self, client: httpx.AsyncClient, text: str) -> str:
        payload = {
            "chat_id": self.target_channel,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "link_preview_options": {"is_disabled": True},
        }
        try:
            data = await self._telegram_json(client, "sendMessage", json=payload)
        except RuntimeError:
            payload["text"] = strip_custom_emoji_tags(text)
            data = await self._telegram_json(client, "sendMessage", json=payload)
        return str(data["result"]["message_id"])

    async def _download(self, client: httpx.AsyncClient, url: str, timeout: float) -> tuple[bytes, str] | None:
        try:
            response = await client.get(
                url,
                headers=DOWNLOAD_HEADERS,
                timeout=timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
        except Exception:
            return None
        content_type = response.headers.get("content-type", "").split(";")[0]
        return response.content, content_type

    async def _send_photo(self, client: httpx.AsyncClient, post: CollectedPost, text: str) -> str | None:
        if not post.photo_url or post.video_url:
            return None
        downloaded = await self._download(client, post.photo_url, timeout=15.0)
        if downloaded is None:
            return None
        content, content_type = downloaded
        if not content_type.startswith("image/"):
            return None
        caption = text if len(text) <= 1024 else ""
        try:
            data = await self._telegram_json(
                client,
                "sendPhoto",
                data={
                    "chat_id": self.target_channel,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                files={"photo": ("photo.jpg", content, content_type)},
            )
            message_id = str(data["result"]["message_id"])
        except Exception:
            return None
        if not caption:
            await self._send_html_message(client, text)
        return message_id

    async def _send_video(self, client: httpx.AsyncClient, post: CollectedPost, text: str) -> str | None:
        if not post.video_url:
            return None
        downloaded = await self._download(client, post.video_url, timeout=90.0)
        if downloaded is None:
            return None
        content, content_type = downloaded
        if len(content) > MAX_VIDEO_BYTES:
            return None
        if content_type and not content_type.startswith(("video/", "application/octet-stream")):
            if not post.video_url.endswith(".mp4"):
                return None
            content_type = "video/mp4"
        caption = text if len(text) <= 1024 else ""
        try:
            data = await self._telegram_json(
                client,
                "sendVideo",
                data={
                    "chat_id": self.target_channel,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "supports_streaming": True,
                    "disable_web_page_preview": True,
                },
                files={"video": ("video.mp4", content, content_type or "video/mp4")},
            )
            message_id = str(data["result"]["message_id"])
        except Exception:
            return None
        if caption:
            return message_id
        await self._send_html_message(client, text)
        return message_id

    async def publish(self, post: CollectedPost) -> PublishResult:
        text = format_post(post)
        if self.dry_run or not self.is_configured:
            return PublishResult(message_id=None, dry_run=True)

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                message_id = await self._send_video(client, post, text)
                if message_id is None:
                    message_id = await self._send_photo(client, post, text)
                if message_id is None:
                    message_id = await self._send_html_message(client, text)
        except Exception as exc:
            raise RuntimeError(sanitize_error(str(exc))) from exc
        return PublishResult(message_id=message_id, dry_run=False)
