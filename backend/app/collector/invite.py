from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

from app.collector.public_preview import is_valid_username, normalize_username

INVITE_URL_RE = re.compile(
    r"(?:https?://)?(?:t(?:elegram)?\.(?:me|dog)|telegram\.me)/(?:joinchat/|\+)([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
INVITE_TG_RE = re.compile(r"^tg://join\?invite=([A-Za-z0-9_-]+)", re.IGNORECASE)
INVITE_PLUS_RE = re.compile(r"^\+([A-Za-z0-9_-]+)$")


@dataclass(frozen=True, slots=True)
class SourceRef:
    kind: str
    username: str
    invite_hash: str | None = None
    invite_link: str | None = None


def extract_invite_hash(value: str) -> str | None:
    raw = unquote((value or "").strip())
    if not raw:
        return None
    for pattern in (INVITE_URL_RE, INVITE_TG_RE, INVITE_PLUS_RE):
        match = pattern.search(raw)
        if match:
            return match.group(1)
    return None


def invite_storage_username(invite_hash: str) -> str:
    return f"invite_{invite_hash}"


def invite_url(invite_hash: str) -> str:
    return f"https://t.me/+{invite_hash}"


def parse_source_ref(value: str) -> SourceRef | None:
    raw = unquote((value or "").strip())
    if not raw:
        return None
    invite_hash = extract_invite_hash(raw)
    if invite_hash:
        return SourceRef(
            kind="private",
            username=invite_storage_username(invite_hash),
            invite_hash=invite_hash,
            invite_link=invite_url(invite_hash),
        )
    username = normalize_username(raw)
    if not is_valid_username(username):
        return None
    return SourceRef(kind="public", username=username)
