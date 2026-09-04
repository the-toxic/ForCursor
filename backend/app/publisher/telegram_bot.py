from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.collector.base import CollectedPost
from app.errors import sanitize_error


@dataclass(frozen=True, slots=True)
class PublishResult:
    message_id: str | None
    dry_run: bool


def format_post(post: CollectedPost) -> str:
    source = post.source_title or post.source_username
    body = post.text.strip()
    footer = f"\n\n———\nИсточник: {source}\n{post.source_url}"
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

    async def _send_message(self, client: httpx.AsyncClient, text: str) -> str:
        data = await self._telegram_json(
            client,
            "sendMessage",
            json={
                "chat_id": self.target_channel,
                "text": text,
                "disable_web_page_preview": False,
            },
        )
        return str(data["result"]["message_id"])

    async def _send_photo(self, client: httpx.AsyncClient, post: CollectedPost, text: str) -> str | None:
        if not post.photo_url or not post.photo_url.startswith("http"):
            return None
        try:
            image = await client.get(
                post.photo_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://t.me/",
                },
                timeout=15.0,
                follow_redirects=True,
            )
            image.raise_for_status()
            content_type = image.headers.get("content-type", "image/jpeg").split(";")[0]
            if not content_type.startswith("image/"):
                return None
            data = await self._telegram_json(
                client,
                "sendPhoto",
                data={"chat_id": self.target_channel, "caption": text[:1024]},
                files={"photo": ("photo.jpg", image.content, content_type)},
            )
            return str(data["result"]["message_id"])
        except Exception:
            return None

    async def publish(self, post: CollectedPost) -> PublishResult:
        text = format_post(post)
        if self.dry_run or not self.is_configured:
            return PublishResult(message_id=None, dry_run=True)

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                message_id = await self._send_photo(client, post, text)
                if message_id is None:
                    message_id = await self._send_message(client, text)
        except Exception as exc:
            raise RuntimeError(sanitize_error(str(exc))) from exc
        return PublishResult(message_id=message_id, dry_run=False)
