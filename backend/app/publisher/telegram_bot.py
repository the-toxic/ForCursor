from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.collector.base import CollectedPost


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

    async def publish(self, post: CollectedPost) -> PublishResult:
        text = format_post(post)
        if self.dry_run or not self.is_configured:
            return PublishResult(message_id=None, dry_run=True)

        api = f"https://api.telegram.org/bot{self.token}"
        payload: dict[str, object] = {
            "chat_id": self.target_channel,
            "disable_web_page_preview": False,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            if post.photo_url:
                response = await client.post(
                    f"{api}/sendPhoto",
                    data={**payload, "caption": text[:1024], "photo": post.photo_url},
                )
            else:
                response = await client.post(
                    f"{api}/sendMessage",
                    json={**payload, "text": text},
                )
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("description") or "Telegram API error")
            message_id = str(data["result"]["message_id"])
        return PublishResult(message_id=message_id, dry_run=False)
