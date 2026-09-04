from app.collector.invite import extract_invite_hash, parse_source_ref
from app.telegram_user import map_telegram_error, private_message_url


def test_extract_invite_hash_from_common_links() -> None:
    assert extract_invite_hash("https://t.me/+AbCdEfGhIjKlMn") == "AbCdEfGhIjKlMn"
    assert extract_invite_hash("https://t.me/joinchat/AbCdEfGhIjKlMn") == "AbCdEfGhIjKlMn"
    assert extract_invite_hash("http://telegram.me/joinchat/Hello_World-1") == "Hello_World-1"
    assert extract_invite_hash("tg://join?invite=AbCdEf123") == "AbCdEf123"
    assert extract_invite_hash("+InviteHash_01") == "InviteHash_01"
    assert extract_invite_hash("https://t.me/%2BAbCdEfGhIjKlMn") == "AbCdEfGhIjKlMn"
    assert extract_invite_hash("https://t.me/s/wylsared") is None
    assert extract_invite_hash("@bbc_news") is None


def test_parse_source_ref_public_and_private() -> None:
    private = parse_source_ref("https://t.me/+AbCdEfGhIjKlMn")
    assert private is not None
    assert private.kind == "private"
    assert private.username == "invite_AbCdEfGhIjKlMn"
    assert private.invite_hash == "AbCdEfGhIjKlMn"

    public = parse_source_ref("https://t.me/s/Demo_News")
    assert public is not None
    assert public.kind == "public"
    assert public.username == "Demo_News"

    assert parse_source_ref("ab") is None
    assert parse_source_ref("https://example.com/x") is None


def test_private_message_url() -> None:
    assert private_message_url(-1001234567890, 42) == "https://t.me/c/1234567890/42"


def test_maps_unregistered_session_to_login_hint() -> None:
    class CheckChatInviteRequest:
        pass

    from telethon.errors import AuthKeyUnregisteredError

    message = map_telegram_error(AuthKeyUnregisteredError(CheckChatInviteRequest()))
    assert "Сессия Telegram" in message
    assert "войдите заново" in message.lower()
