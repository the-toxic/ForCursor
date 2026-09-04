from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    AuthKeyDuplicatedError,
    AuthKeyInvalidError,
    AuthKeyUnregisteredError,
    ChannelPrivateError,
    FloodWaitError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionExpiredError,
    SessionPasswordNeededError,
    SessionRevokedError,
    UserAlreadyParticipantError,
)
from telethon.extensions import html as telethon_html
from telethon.tl.custom.message import Message
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.functions.updates import GetStateRequest
from telethon.tl.types import Channel, Chat, ChatInvite, ChatInviteAlready, InputPeerChannel, InputPeerChat
from telethon.utils import get_display_name, get_peer_id

from app.collector.base import CollectedPost
from app.errors import sanitize_error
from app.models import Source

FETCH_LIMIT = 40
MAX_VIDEO_BYTES = 49 * 1024 * 1024
SESSION_DEAD_MESSAGE = (
    "Сессия Telegram на сервере слетела. В Telegram на телефоне подтвердите вход, "
    "если приходило уведомление «новый вход», затем в админке нажмите «Выйти из Telegram» "
    "и войдите заново по коду."
)
SESSION_ERRORS = (
    AuthKeyUnregisteredError,
    AuthKeyDuplicatedError,
    AuthKeyInvalidError,
    SessionRevokedError,
    SessionExpiredError,
)


def session_file_path(session_path: str) -> Path:
    path = Path(session_path)
    if path.suffix != ".session":
        return path.with_suffix(".session")
    return path


def map_telegram_error(exc: Exception) -> str:
    if isinstance(exc, SESSION_ERRORS) or "not registered in the system" in str(exc).lower():
        return SESSION_DEAD_MESSAGE
    if isinstance(exc, PhoneNumberInvalidError):
        return "Некорректный номер телефона. Укажите его в международном формате, например +79001234567."
    if isinstance(exc, PhoneCodeInvalidError):
        return "Неверный код из Telegram."
    if isinstance(exc, PhoneCodeExpiredError):
        return "Код истек. Запросите новый."
    if isinstance(exc, SessionPasswordNeededError):
        return "Нужен пароль двухфакторной защиты."
    if isinstance(exc, InviteHashExpiredError):
        return (
            "Ссылка-приглашение больше не действует. Если аккаунт уже в канале, "
            "войдите заново в админке и добавьте канал ещё раз. Иначе попросите новую ссылку."
        )
    if isinstance(exc, InviteHashInvalidError):
        return "Некорректная ссылка-приглашение."
    if isinstance(exc, ChannelPrivateError):
        return "Канал закрыт, и этот аккаунт туда не вступил."
    if isinstance(exc, FloodWaitError):
        return f"Telegram просит подождать {exc.seconds} секунд и повторить."
    return sanitize_error(str(exc) or exc.__class__.__name__)


def private_message_url(peer_id: int, message_id: int) -> str:
    raw = str(peer_id)
    if raw.startswith("-100"):
        return f"https://t.me/c/{raw[4:]}/{message_id}"
    return f"https://t.me/c/{abs(peer_id)}/{message_id}"


def entity_access_hash(entity: object) -> str | None:
    access_hash = getattr(entity, "access_hash", None)
    if access_hash is None:
        return None
    return str(access_hash)


def input_peer_from_ids(peer_id: int, access_hash: int | None):
    raw = str(peer_id)
    if raw.startswith("-100"):
        channel_id = int(raw[4:])
        if access_hash is None:
            raise RuntimeError("Для закрытого канала нет access_hash. Добавьте его по ссылке ещё раз после входа.")
        return InputPeerChannel(channel_id, access_hash)
    if peer_id < 0:
        return InputPeerChat(-peer_id)
    if access_hash is None:
        raise RuntimeError("Для закрытого канала нет access_hash. Добавьте его по ссылке ещё раз после входа.")
    return InputPeerChannel(peer_id, access_hash)


def _message_html(message: Message) -> str:
    text = message.message or ""
    if not text:
        return ""
    try:
        return telethon_html.unparse(text, message.entities)
    except Exception:
        return text


def _is_video_message(message: Message) -> bool:
    if message.video:
        return True
    document = message.document
    if document is None:
        return False
    mime = (getattr(document, "mime_type", None) or "").lower()
    return mime.startswith("video/")


@dataclass(frozen=True, slots=True)
class JoinedChannel:
    title: str
    username: str
    peer_id: int
    access_hash: str | None


class TelegramUserService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._client: TelegramClient | None = None
        self._api_id: int = 0
        self._api_hash: str = ""
        self._session_path: str = "./data/telegram_user"
        self._phone: str | None = None
        self._phone_code_hash: str | None = None

    def is_configured(self, api_id: int | None = None, api_hash: str | None = None) -> bool:
        resolved_id = api_id if api_id is not None else self._api_id
        resolved_hash = api_hash if api_hash is not None else self._api_hash
        return bool(resolved_id and resolved_hash)

    async def try_start(self, api_id: int, api_hash: str, session_path: str) -> None:
        if not api_id or not api_hash:
            return
        if not session_file_path(session_path).exists():
            self._session_path = session_path
            return
        async with self._lock:
            try:
                client = await self._ensure_client_locked(api_id, api_hash, session_path)
                await self._assert_alive_locked(client)
            except Exception:
                await self._invalidate_session_locked()

    async def shutdown(self) -> None:
        async with self._lock:
            await self._disconnect_locked()

    async def status(self, api_id: int, api_hash: str, session_path: str) -> dict[str, object]:
        empty = {
            "configured": False,
            "authorized": False,
            "code_sent": bool(self._phone_code_hash),
            "user_id": None,
            "first_name": None,
            "username": None,
            "phone": None,
            "error": None,
        }
        if not api_id or not api_hash:
            return empty
        session_exists = session_file_path(session_path).exists()
        if not session_exists and self._client is None:
            return {**empty, "configured": True}
        async with self._lock:
            try:
                client = await self._ensure_client_locked(api_id, api_hash, session_path)
                if not await client.is_user_authorized():
                    return {**empty, "configured": True}
                await self._assert_alive_locked(client)
                me = await client.get_me()
                return {
                    "configured": True,
                    "authorized": True,
                    "code_sent": False,
                    "user_id": me.id if me else None,
                    "first_name": getattr(me, "first_name", None),
                    "username": getattr(me, "username", None),
                    "phone": getattr(me, "phone", None),
                    "error": None,
                }
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, SESSION_ERRORS) or "not registered in the system" in str(exc).lower():
                    await self._invalidate_session_locked()
                return {
                    **empty,
                    "configured": True,
                    "error": map_telegram_error(exc),
                }

    async def send_code(self, api_id: int, api_hash: str, session_path: str, phone: str) -> dict[str, object]:
        clean_phone = phone.strip().replace(" ", "")
        async with self._lock:
            try:
                client = await self._ensure_client_locked(api_id, api_hash, session_path)
                sent = await client.send_code_request(clean_phone)
                self._phone = clean_phone
                self._phone_code_hash = sent.phone_code_hash
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(map_telegram_error(exc)) from exc
        return {"ok": True, "phone": clean_phone}

    async def sign_in(
        self,
        api_id: int,
        api_hash: str,
        session_path: str,
        phone: str,
        code: str,
        password: str | None = None,
    ) -> dict[str, object]:
        clean_phone = phone.strip().replace(" ", "") or (self._phone or "")
        async with self._lock:
            try:
                client = await self._ensure_client_locked(api_id, api_hash, session_path)
                try:
                    await client.sign_in(
                        phone=clean_phone,
                        code=code.strip(),
                        phone_code_hash=self._phone_code_hash,
                    )
                except SessionPasswordNeededError:
                    if not password:
                        raise RuntimeError("Нужен пароль двухфакторной защиты.") from None
                    await client.sign_in(password=password)
                self._phone_code_hash = None
                me = await client.get_me()
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(map_telegram_error(exc)) from exc
        return {
            "ok": True,
            "user_id": me.id if me else None,
            "first_name": getattr(me, "first_name", None),
            "username": getattr(me, "username", None),
            "phone": getattr(me, "phone", None),
        }

    async def logout(self) -> None:
        async with self._lock:
            client = self._client
            if client is not None:
                try:
                    if client.is_connected():
                        await client.log_out()
                except Exception:
                    pass
            await self._invalidate_session_locked()

    async def is_authorized(self, api_id: int, api_hash: str, session_path: str) -> bool:
        status = await self.status(api_id, api_hash, session_path)
        return bool(status.get("authorized"))

    async def join_invite(self, api_id: int, api_hash: str, session_path: str, invite_hash: str) -> JoinedChannel:
        async with self._lock:
            client = await self._authorized_client_locked(api_id, api_hash, session_path)
            entity = await self._join_invite_locked(client, invite_hash)
            title = get_display_name(entity) or invite_hash
            peer_id = get_peer_id(entity)
            username = getattr(entity, "username", None) or f"invite_{invite_hash}"
            return JoinedChannel(
                title=title,
                username=username,
                peer_id=peer_id,
                access_hash=entity_access_hash(entity),
            )

    async def fetch_source(
        self,
        api_id: int,
        api_hash: str,
        session_path: str,
        source: Source,
        since_id: int | None = None,
        limit: int = FETCH_LIMIT,
    ) -> tuple[list[CollectedPost], str, int, str | None]:
        async with self._lock:
            client = await self._authorized_client_locked(api_id, api_hash, session_path)
            entity = await self._entity_for_source_locked(client, source)
            title = get_display_name(entity) or source.title or source.username
            peer_id = get_peer_id(entity)
            access_hash = entity_access_hash(entity)
            display_username = source.title or getattr(entity, "username", None) or source.username

            newest: list[Message] = []
            async for message in client.iter_messages(entity, limit=limit):
                if since_id is not None and message.id <= since_id:
                    break
                if message.action:
                    continue
                newest.append(message)

            groups: dict[int, list[Message]] = {}
            singles: list[Message] = []
            for message in newest:
                if message.grouped_id:
                    groups.setdefault(int(message.grouped_id), []).append(message)
                else:
                    singles.append(message)

            posts: list[CollectedPost] = []
            access_hash_int = int(access_hash) if access_hash else None
            for message in singles:
                posts.append(
                    self._message_to_post(
                        [message],
                        display_username=display_username,
                        title=title,
                        peer_id=peer_id,
                        access_hash=access_hash_int,
                    )
                )
            for grouped in groups.values():
                posts.append(
                    self._message_to_post(
                        grouped,
                        display_username=display_username,
                        title=title,
                        peer_id=peer_id,
                        access_hash=access_hash_int,
                    )
                )
            posts.sort(key=lambda item: item.post_id)
            return posts, title, peer_id, access_hash

    async def hydrate_media(
        self,
        api_id: int,
        api_hash: str,
        session_path: str,
        post: CollectedPost,
    ) -> CollectedPost:
        if post.photo_bytes or post.video_bytes or not post.telegram_message_ids:
            return post
        if post.telegram_peer_id is None:
            return post
        async with self._lock:
            client = await self._authorized_client_locked(api_id, api_hash, session_path)
            peer = input_peer_from_ids(post.telegram_peer_id, post.telegram_access_hash)
            photo_parts: list[bytes] = []
            video_bytes: bytes | None = None
            for message_id in post.telegram_message_ids:
                message = await client.get_messages(peer, ids=message_id)
                if message is None:
                    continue
                if _is_video_message(message) and video_bytes is None:
                    payload = await self._download_media_locked(client, message)
                    if payload and len(payload) <= MAX_VIDEO_BYTES:
                        video_bytes = payload
                    continue
                if message.photo:
                    payload = await self._download_media_locked(client, message)
                    if payload:
                        photo_parts.append(payload)
            return replace(
                post,
                photo_bytes=photo_parts[0] if photo_parts else None,
                photo_bytes_list=tuple(photo_parts),
                video_bytes=video_bytes,
            )

    async def _join_invite_locked(self, client: TelegramClient, invite_hash: str):
        try:
            invite = await client(CheckChatInviteRequest(invite_hash))
        except SESSION_ERRORS as exc:
            await self._invalidate_session_locked()
            raise RuntimeError(map_telegram_error(exc)) from exc
        except (InviteHashExpiredError, InviteHashInvalidError):
            try:
                updates = await client(ImportChatInviteRequest(invite_hash))
            except UserAlreadyParticipantError:
                raise RuntimeError(
                    "Ссылка-приглашение больше не открывается, но аккаунт, возможно, уже в канале. "
                    "Войдите заново в админке и добавьте канал ещё раз. Если не выйдет — нужна новая ссылка."
                ) from None
            except SESSION_ERRORS as exc:
                await self._invalidate_session_locked()
                raise RuntimeError(map_telegram_error(exc)) from exc
            except Exception as exc:
                raise RuntimeError(map_telegram_error(exc)) from exc
            return self._chat_from_updates(updates)
        except Exception as exc:
            raise RuntimeError(map_telegram_error(exc)) from exc

        if isinstance(invite, ChatInviteAlready):
            return invite.chat
        if isinstance(invite, ChatInvite) and getattr(invite, "request_needed", False):
            raise RuntimeError(
                "Канал принимает участников только после одобрения заявки. "
                "Вступите с этого аккаунта вручную, затем добавьте ссылку снова."
            )
        try:
            updates = await client(ImportChatInviteRequest(invite_hash))
        except UserAlreadyParticipantError:
            checked = await client(CheckChatInviteRequest(invite_hash))
            if isinstance(checked, ChatInviteAlready):
                return checked.chat
            raise RuntimeError("Аккаунт уже в канале, но не удалось получить чат.") from None
        except SESSION_ERRORS as exc:
            await self._invalidate_session_locked()
            raise RuntimeError(map_telegram_error(exc)) from exc
        except Exception as exc:
            raise RuntimeError(map_telegram_error(exc)) from exc
        return self._chat_from_updates(updates)

    def _chat_from_updates(self, updates: object):
        chats = getattr(updates, "chats", None) or []
        for chat in chats:
            if isinstance(chat, (Channel, Chat)):
                return chat
        raise RuntimeError("Не удалось вступить в канал по ссылке.")

    async def _entity_for_source_locked(self, client: TelegramClient, source: Source):
        if source.telegram_peer_id:
            try:
                access_hash = int(source.telegram_access_hash) if source.telegram_access_hash else None
                return await client.get_entity(input_peer_from_ids(int(source.telegram_peer_id), access_hash))
            except SESSION_ERRORS as exc:
                await self._invalidate_session_locked()
                raise RuntimeError(map_telegram_error(exc)) from exc
            except Exception:
                try:
                    return await client.get_entity(int(source.telegram_peer_id))
                except Exception:
                    pass
        if source.invite_hash:
            return await self._join_invite_locked(client, source.invite_hash)
        raise RuntimeError("Для закрытого канала нет invite-ссылки и id чата.")

    def _message_to_post(
        self,
        messages: list[Message],
        *,
        display_username: str,
        title: str,
        peer_id: int,
        access_hash: int | None,
    ) -> CollectedPost:
        messages = sorted(messages, key=lambda item: item.id)
        main = next((item for item in messages if item.message), messages[0])
        html_text = _message_html(main)
        text = main.message or ""
        post_id = messages[-1].id
        album_id = messages[0].id
        return CollectedPost(
            source_username=display_username,
            source_title=title,
            external_id=f"private:{peer_id}:{album_id}",
            post_id=post_id,
            text=text,
            html_text=html_text,
            photo_url=None,
            source_url=private_message_url(peer_id, album_id),
            posted_at=main.date.replace(tzinfo=None) if main.date else None,
            telegram_peer_id=peer_id,
            telegram_access_hash=access_hash,
            telegram_message_ids=tuple(item.id for item in messages),
        )

    async def _download_media_locked(self, client: TelegramClient, message: Message) -> bytes | None:
        try:
            payload = await client.download_media(message, file=bytes)
        except Exception:
            return None
        if isinstance(payload, bytes) and payload:
            return payload
        return None

    async def _authorized_client_locked(
        self,
        api_id: int,
        api_hash: str,
        session_path: str,
    ) -> TelegramClient:
        client = await self._ensure_client_locked(api_id, api_hash, session_path)
        if not await client.is_user_authorized():
            raise RuntimeError("Войдите в Telegram-аккаунт в админке, чтобы читать закрытые каналы.")
        try:
            await self._assert_alive_locked(client)
        except SESSION_ERRORS as exc:
            await self._invalidate_session_locked()
            raise RuntimeError(map_telegram_error(exc)) from exc
        return client

    async def _assert_alive_locked(self, client: TelegramClient) -> None:
        await client(GetStateRequest())

    async def _ensure_client_locked(
        self,
        api_id: int,
        api_hash: str,
        session_path: str,
    ) -> TelegramClient:
        if (
            self._client is not None
            and self._api_id == api_id
            and self._api_hash == api_hash
            and self._session_path == session_path
        ):
            if not self._client.is_connected():
                await self._client.connect()
            return self._client
        await self._disconnect_locked()
        Path(session_path).parent.mkdir(parents=True, exist_ok=True)
        client = TelegramClient(session_path, int(api_id), api_hash)
        await client.connect()
        self._client = client
        self._api_id = int(api_id)
        self._api_hash = api_hash
        self._session_path = session_path
        return client

    async def _invalidate_session_locked(self) -> None:
        await self._disconnect_locked()
        self._phone = None
        self._phone_code_hash = None
        session_file = session_file_path(self._session_path)
        session_file.unlink(missing_ok=True)
        Path(str(session_file) + "-journal").unlink(missing_ok=True)

    async def _disconnect_locked(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            if client.is_connected():
                await client.disconnect()
        except Exception:
            pass


telegram_user_service = TelegramUserService()
