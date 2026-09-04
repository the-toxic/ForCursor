from app.errors import sanitize_error


def test_sanitize_error_hides_bot_token() -> None:
    raw = (
        "Client error '400 Bad Request' for url "
        "'https://api.telegram.org/bot8625989217:AAFWYZsVZne1g2C3Y-KzSQSx1wKSEhqJE7Y/sendPhoto'"
    )
    cleaned = sanitize_error(raw)
    assert "AAFWYZsVZne1g2C3Y-KzSQSx1wKSEhqJE7Y" not in cleaned
    assert "8625989217" not in cleaned
    assert "sendPhoto" in cleaned
