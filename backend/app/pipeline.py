from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collector.base import CollectedPost
from app.collector.demo import DEMO_POSTS, DemoCollector
from app.collector.public_preview import PublicPreviewCollector, is_valid_username, normalize_username
from app.config import Settings
from app.dedup.engine import Candidate, decide
from app.dedup.normalize import normalize_text, text_hash
from app.errors import sanitize_error
from app.models import Item, Source
from app.publisher.telegram_bot import TelegramPublisher
from app.schemas import FetchResult
from app.settings_store import read_runtime_settings


def seed_demo_sources(db: Session) -> None:
    usernames = sorted({post.source_username for post in DEMO_POSTS})
    titles = {post.source_username: post.source_title for post in DEMO_POSTS}
    for username in usernames:
        existing = db.scalar(select(Source).where(Source.username == username))
        if existing:
            continue
        db.add(Source(username=username, title=titles.get(username), enabled=True))
    db.commit()


def seed_env_sources(db: Session, usernames: list[str]) -> None:
    for raw in usernames:
        username = normalize_username(raw)
        if not is_valid_username(username):
            continue
        existing = db.scalar(select(Source).where(Source.username == username))
        if existing:
            continue
        db.add(Source(username=username, enabled=True))
    db.commit()


class NewsPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()
        self.last_fetch_at: datetime | None = None

    def _collector(self):
        if self.settings.is_demo:
            return DemoCollector()
        return PublicPreviewCollector()

    def _publisher(self, target_channel: str) -> TelegramPublisher:
        return TelegramPublisher(
            token=self.settings.bot_token,
            target_channel=target_channel,
            dry_run=self.settings.is_demo or not self.settings.bot_token or not target_channel,
        )

    def _recent_candidates(self, db: Session) -> list[Candidate]:
        rows = (
            db.query(Item)
            .filter(Item.status == "published")
            .order_by(Item.id.desc())
            .limit(self.settings.dedup_window)
            .all()
        )
        return [
            Candidate(item_id=row.id, content_hash=row.content_hash, raw_text=row.raw_text)
            for row in reversed(rows)
        ]

    async def reclassify_duplicates(self, db: Session, threshold: float) -> int:
        published_rows = db.query(Item).filter(Item.status == "published").order_by(Item.id.asc()).all()
        duplicate_rows = db.query(Item).filter(Item.status == "duplicate").order_by(Item.id.asc()).all()
        recent = [
            Candidate(item_id=row.id, content_hash=row.content_hash, raw_text=row.raw_text)
            for row in published_rows
        ]
        promoted = 0
        for item in duplicate_rows:
            decision = decide(item.raw_text, recent, threshold)
            item.similarity = decision.similarity
            item.matched_item_id = decision.matched_item_id
            if decision.is_duplicate:
                continue
            item.status = "published"
            recent.append(
                Candidate(item_id=item.id, content_hash=item.content_hash, raw_text=item.raw_text)
            )
            promoted += 1
        db.commit()
        return promoted

    async def process_post(
        self,
        db: Session,
        post: CollectedPost,
        source: Source,
        threshold: float,
        min_text_length: int,
        publisher: TelegramPublisher,
        recent: list[Candidate],
    ) -> str:
        existing = db.scalar(select(Item).where(Item.external_id == post.external_id))
        if existing:
            return "seen"

        normalized = normalize_text(post.text)
        if len(normalized) < min_text_length:
            item = Item(
                source_id=source.id,
                source_username=post.source_username,
                external_id=post.external_id,
                raw_text=post.text,
                normalized_text=normalized,
                content_hash=text_hash(post.text),
                photo_url=post.photo_url,
                source_url=post.source_url,
                status="skipped",
                posted_at=post.posted_at,
            )
            db.add(item)
            db.commit()
            return "skipped"

        decision = decide(post.text, recent, threshold)
        status = "duplicate" if decision.is_duplicate else "published"
        published_id = None
        if status == "published":
            result = await publisher.publish(post)
            published_id = result.message_id

        item = Item(
            source_id=source.id,
            source_username=post.source_username,
            external_id=post.external_id,
            raw_text=post.text,
            normalized_text=normalized,
            content_hash=text_hash(post.text),
            photo_url=post.photo_url,
            source_url=post.source_url,
            status=status,
            similarity=decision.similarity,
            matched_item_id=decision.matched_item_id,
            published_message_id=published_id,
            posted_at=post.posted_at,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        if status == "published":
            recent.append(
                Candidate(item_id=item.id, content_hash=item.content_hash, raw_text=item.raw_text)
            )
        return status

    async def run_once(self, db: Session) -> FetchResult:
        async with self._lock:
            runtime = read_runtime_settings(db, self.settings)
            threshold = float(runtime["similarity_threshold"])
            min_text_length = int(runtime["min_text_length"])
            target_channel = str(runtime["target_channel"])
            publisher = self._publisher(target_channel)
            collector = self._collector()
            await self.reclassify_duplicates(db, threshold)
            recent = self._recent_candidates(db)

            counts = {"fetched": 0, "published": 0, "duplicates": 0, "skipped": 0}
            errors: list[str] = []
            sources = db.query(Source).filter(Source.enabled.is_(True)).all()

            for source in sources:
                try:
                    posts = await collector.fetch(source.username)
                    if posts and posts[0].source_title:
                        source.title = posts[0].source_title
                    source.error = None
                    source.last_fetched_at = datetime.now(UTC).replace(tzinfo=None)
                    for post in posts:
                        if source.last_post_id is not None and post.post_id <= source.last_post_id:
                            continue
                        counts["fetched"] += 1
                        try:
                            status = await self.process_post(
                                db,
                                post,
                                source,
                                threshold,
                                min_text_length,
                                publisher,
                                recent,
                            )
                        except Exception as exc:  # noqa: BLE001
                            errors.append(f"{source.username}: {sanitize_error(str(exc))}")
                            continue
                        count_key = {
                            "published": "published",
                            "duplicate": "duplicates",
                            "skipped": "skipped",
                        }.get(status)
                        if count_key:
                            counts[count_key] += 1
                        source.last_post_id = max(source.last_post_id or 0, post.post_id)
                    db.commit()
                except Exception as exc:  # noqa: BLE001 - ошибки источника не роняют весь проход
                    source.error = sanitize_error(str(exc))
                    db.commit()
                    errors.append(f"{source.username}: {source.error}")

            self.last_fetch_at = datetime.now(UTC).replace(tzinfo=None)
            return FetchResult(errors=errors, **counts)
