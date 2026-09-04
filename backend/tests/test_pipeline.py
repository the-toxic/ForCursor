import pytest
from sqlalchemy.orm import Session

from app.models import Item
from app.pipeline import NewsPipeline
from app.publisher.telegram_bot import format_post
from app.collector.demo import DEMO_POSTS


@pytest.mark.asyncio
async def test_pipeline_publishes_unique_and_skips_duplicates(
    db_session: Session,
    pipeline: NewsPipeline,
) -> None:
    from app.pipeline import seed_demo_sources

    seed_demo_sources(db_session)
    first = await pipeline.run_once(db_session)
    second = await pipeline.run_once(db_session)

    assert first.fetched >= 6
    assert first.published >= 4
    assert first.duplicates >= 1
    assert first.skipped >= 1
    assert second.fetched == 0

    statuses = {row.status for row in db_session.query(Item).all()}
    assert {"published", "duplicate", "skipped"} <= statuses


def test_format_post_adds_source() -> None:
    text = format_post(DEMO_POSTS[0])
    assert "ключевую ставку" in text
    assert "Демо Альфа" in text
    assert "https://t.me/demo_alpha/101" in text
    assert "Источник:" not in text
    assert "disable_web_page_preview" not in text
