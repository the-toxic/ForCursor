from __future__ import annotations

from datetime import datetime, timedelta

from app.collector.base import CollectedPost

_NOW = datetime(2026, 9, 4, 10, 0, 0)


def _post(
    username: str,
    post_id: int,
    text: str,
    minutes: int,
    title: str,
) -> CollectedPost:
    return CollectedPost(
        source_username=username,
        source_title=title,
        external_id=f"{username}/{post_id}",
        post_id=post_id,
        text=text,
        photo_url=None,
        source_url=f"https://t.me/{username}/{post_id}",
        posted_at=_NOW - timedelta(minutes=minutes),
    )


DEMO_POSTS = [
    _post(
        "demo_alpha",
        101,
        "ЦБ сохранил ключевую ставку на уровне 16%. Регулятор отметил устойчивое инфляционное давление и обещал вернуться к вопросу на следующем заседании.",
        80,
        "Демо Альфа",
    ),
    _post(
        "demo_beta",
        55,
        "Банк России оставил ключевую ставку 16 процентов. В сообщении регулятора говорится об устойчивом инфляционном давлении, решение пересмотрят на следующем заседании.",
        75,
        "Демо Бета",
    ),
    _post(
        "demo_gamma",
        9,
        "ЦБ сохранил ключевую ставку на уровне 16%. Регулятор отметил устойчивое инфляционное давление и обещал вернуться к вопросу на следующем заседании.\nИсточник",
        70,
        "Демо Гамма",
    ),
    _post(
        "demo_alpha",
        102,
        "В Москве открыли новый участок метро. Поездки по нему начнутся с понедельника, интервал в час пик — две минуты.",
        60,
        "Демо Альфа",
    ),
    _post(
        "demo_beta",
        56,
        "Учёные опубликовали карту течения Гольфстрима за последние 30 лет. Скорость потока снизилась, но катастрофического обрушения не зафиксировали.",
        50,
        "Демо Бета",
    ),
    _post(
        "demo_gamma",
        10,
        "Исследователи представили карту Гольфстрима за 30 лет: скорость течения уменьшилась, обрушения потока нет.",
        45,
        "Демо Гамма",
    ),
    _post(
        "demo_alpha",
        103,
        "Сборная вышла в финал чемпионата после серии пенальти. Решающий удар на 119-й минуте серии реализовал капитан.",
        30,
        "Демо Альфа",
    ),
    _post(
        "demo_beta",
        57,
        "Коротко: курс рубля стабилен.",
        20,
        "Демо Бета",
    ),
    _post(
        "demo_gamma",
        11,
        "Стартап из Новосибирска привлёк раунд на разработку квантовых сенсоров. Деньги пойдут на пилот с промышленными партнёрами.",
        10,
        "Демо Гамма",
    ),
]


class DemoCollector:
    def __init__(self, posts: list[CollectedPost] | None = None) -> None:
        self.posts = posts or DEMO_POSTS

    async def fetch(self, username: str) -> list[CollectedPost]:
        return [post for post in self.posts if post.source_username == username]
