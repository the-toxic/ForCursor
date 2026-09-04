from pathlib import Path

from app.collector.public_preview import is_valid_username, normalize_username, parse_preview_html


def test_normalize_and_validate_username() -> None:
    assert normalize_username("https://t.me/s/Demo_News") == "Demo_News"
    assert is_valid_username("@bbc")
    assert not is_valid_username("ab")
    assert not is_valid_username("news with space")


def test_parse_preview_html_extracts_posts() -> None:
    html = Path(__file__).parent.joinpath("fixtures/tme_sample.html").read_text(encoding="utf-8")
    posts = parse_preview_html(html, "demo_news")
    assert [post.post_id for post in posts] == [10, 11]
    assert posts[0].text == "Первая новость про ставку ЦБ"
    assert posts[1].photo_url == "https://cdn.example/photo.jpg"
    assert posts[0].source_title == "Новости Демо"
    assert posts[1].source_url == "https://t.me/demo_news/11"
