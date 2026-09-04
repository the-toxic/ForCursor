from __future__ import annotations

import html
import re
from typing import Any

from bs4 import NavigableString, Tag

BLOCK_TAGS = {"p", "div", "section", "blockquote"}


def _escape(text: str) -> str:
    return html.escape(text, quote=False).replace("\xa0", " ")


def node_to_telegram_html(node: Any) -> str:
    if isinstance(node, NavigableString):
        return _escape(str(node))
    if not isinstance(node, Tag):
        return ""

    name = (node.name or "").lower()
    classes = node.get("class") or []
    if isinstance(classes, str):
        classes = [classes]

    if name == "br":
        return "\n"
    if name == "tg-emoji":
        fallback = (node.get_text("") or "").replace("\xa0", " ").strip() or "•"
        emoji_id = node.get("emoji-id")
        if emoji_id:
            return f'<tg-emoji emoji-id="{html.escape(str(emoji_id))}">{html.escape(fallback)}</tg-emoji>'
        return html.escape(fallback)
    if name == "i" and "emoji" in classes:
        return html.escape((node.get_text("") or "").replace("\xa0", " "))
    if name in {"b", "strong"}:
        inner = "".join(node_to_telegram_html(child) for child in node.children)
        return f"<b>{inner}</b>"
    if name in {"i", "em"}:
        inner = "".join(node_to_telegram_html(child) for child in node.children)
        return f"<i>{inner}</i>"
    if name == "a":
        href = (node.get("href") or "").strip()
        inner = "".join(node_to_telegram_html(child) for child in node.children)
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith(("http://", "https://", "tg://")):
            return f'<a href="{html.escape(href, quote=True)}">{inner}</a>'
        return inner
    if name in {"script", "style"}:
        return ""

    inner = "".join(node_to_telegram_html(child) for child in node.children)
    if name in BLOCK_TAGS:
        return f"{inner}\n"
    return inner


def telegram_html_from_message(text_tag: Tag | None) -> str:
    if text_tag is None:
        return ""
    raw = "".join(node_to_telegram_html(child) for child in text_tag.children)
    raw = raw.replace("\xa0", " ")
    raw = re.sub(r"[ \t]+\n", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def html_to_plain(telegram_html: str) -> str:
    from bs4 import BeautifulSoup

    if not telegram_html:
        return ""
    soup = BeautifulSoup(telegram_html, "lxml")
    text = soup.get_text("")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_custom_emoji_tags(telegram_html: str) -> str:
    return re.sub(r"</?tg-emoji(?:\s[^>]*)?>", "", telegram_html)
