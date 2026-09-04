from __future__ import annotations

import hashlib
import re
import unicodedata

URL_RE = re.compile(r"(https?://\S+|t\.me/\S+|www\.\S+)", re.IGNORECASE)
MENTION_RE = re.compile(r"@[a-zA-Z0-9_]{3,}")
HASHTAG_RE = re.compile(r"#[\wа-яё]+", re.IGNORECASE)
NOISE_LINE_RE = re.compile(
    r"^(подписывайтесь|читайте также|читайте|смотрите|подробнее|источник|реклама|erid|promo|sponsored).*$",
    re.IGNORECASE,
)
NON_WORD_RE = re.compile(r"[^\w\sё-]", re.IGNORECASE)
SPACES_RE = re.compile(r"\s+")

RU_STOPWORDS = {
    "а",
    "без",
    "более",
    "больше",
    "будет",
    "будто",
    "бы",
    "был",
    "была",
    "были",
    "было",
    "быть",
    "в",
    "вам",
    "вас",
    "вдруг",
    "ведь",
    "во",
    "вот",
    "впрочем",
    "все",
    "всегда",
    "всего",
    "всех",
    "всю",
    "вы",
    "где",
    "да",
    "даже",
    "два",
    "для",
    "до",
    "другой",
    "его",
    "ее",
    "ей",
    "ему",
    "если",
    "есть",
    "еще",
    "ещё",
    "ж",
    "же",
    "за",
    "заявил",
    "заявила",
    "заявили",
    "и",
    "из",
    "или",
    "им",
    "иногда",
    "их",
    "к",
    "как",
    "какая",
    "какой",
    "когда",
    "конечно",
    "кто",
    "куда",
    "ли",
    "лучше",
    "между",
    "меня",
    "мне",
    "много",
    "может",
    "можно",
    "мой",
    "мы",
    "на",
    "над",
    "надо",
    "наконец",
    "нас",
    "не",
    "него",
    "нее",
    "ней",
    "нет",
    "ни",
    "нибудь",
    "никогда",
    "ним",
    "них",
    "ничего",
    "но",
    "ну",
    "о",
    "об",
    "один",
    "он",
    "она",
    "они",
    "оно",
    "опять",
    "от",
    "перед",
    "по",
    "под",
    "после",
    "потом",
    "потому",
    "почти",
    "при",
    "про",
    "раз",
    "разве",
    "с",
    "сам",
    "свое",
    "свою",
    "себе",
    "себя",
    "сегодня",
    "сейчас",
    "сказал",
    "сказала",
    "сказать",
    "со",
    "совсем",
    "так",
    "такой",
    "там",
    "тебя",
    "тем",
    "теперь",
    "то",
    "тогда",
    "того",
    "тоже",
    "только",
    "том",
    "тот",
    "три",
    "тут",
    "ты",
    "у",
    "уж",
    "уже",
    "хорошо",
    "хоть",
    "чего",
    "человек",
    "чем",
    "через",
    "что",
    "чтоб",
    "чтобы",
    "чуть",
    "эти",
    "этого",
    "этой",
    "этом",
    "этот",
    "эту",
    "я",
    "the",
    "and",
    "for",
    "with",
}


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def normalize_text(value: str) -> str:
    text = strip_html(value)
    text = unicodedata.normalize("NFKC", text)
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    text = HASHTAG_RE.sub(" ", text)
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or NOISE_LINE_RE.match(line):
            continue
        lines.append(line)
    text = " ".join(lines)
    text = text.lower().replace("ё", "е")
    text = NON_WORD_RE.sub(" ", text)
    text = SPACES_RE.sub(" ", text).strip()
    return text


_STEM_SUFFIXES = (
    "иями",
    "ями",
    "ами",
    "ией",
    "остью",
    "ностью",
    "ении",
    "ение",
    "ения",
    "ением",
    "ого",
    "ему",
    "ыми",
    "ими",
    "ой",
    "ей",
    "ом",
    "ем",
    "ах",
    "ях",
    "ов",
    "ев",
    "ий",
    "ый",
    "ая",
    "яя",
    "ое",
    "ее",
    "ые",
    "ие",
    "ую",
    "юю",
    "ою",
    "ею",
    "ии",
    "ых",
    "их",
    "ть",
    "а",
    "я",
    "о",
    "е",
    "у",
    "ю",
    "и",
    "ы",
)


def stem_token(token: str) -> str:
    if token.isdigit() or len(token) <= 4:
        return token
    for suffix in _STEM_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def significant_tokens(value: str) -> list[str]:
    normalized = normalize_text(value)
    return [
        stem_token(token)
        for token in normalized.split()
        if token not in RU_STOPWORDS and len(token) > 2
    ]


def text_hash(value: str) -> str:
    normalized = normalize_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
