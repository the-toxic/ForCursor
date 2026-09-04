from __future__ import annotations

import re

BOT_TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}")
BOT_PATH_RE = re.compile(r"/bot[^/\s]+")


def sanitize_error(message: str) -> str:
    cleaned = BOT_TOKEN_RE.sub("***", message)
    return BOT_PATH_RE.sub("/bot***/", cleaned)
