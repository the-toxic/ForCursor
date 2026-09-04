from app.dedup.normalize import normalize_text, significant_tokens, text_hash


def test_normalize_strips_links_mentions_and_noise() -> None:
    raw = (
        "ЦБ сохранил ставку 16%\n"
        "Подробнее: https://example.com/news\n"
        "@some_channel\n"
        "#экономика\n"
        "Подписывайтесь на канал"
    )
    assert normalize_text(raw) == "цб сохранил ставку 16"


def test_same_news_same_hash() -> None:
    left = "ЦБ сохранил ключевую ставку на уровне 16%. https://t.me/foo"
    right = "ЦБ сохранил ключевую ставку на уровне 16%.\nИсточник"
    assert text_hash(left) == text_hash(right)


def test_significant_tokens_drop_stopwords() -> None:
    tokens = significant_tokens("В Москве открыли новый участок метро")
    assert any(token.startswith("москв") for token in tokens)
    assert "новый" in tokens
    assert "в" not in tokens
