from bs4 import BeautifulSoup

from app.collector.html_text import html_to_plain, telegram_html_from_message
from app.collector.public_preview import parse_preview_html


def test_inline_markup_stays_on_one_line() -> None:
    html = """
    <div class="tgme_widget_message_text">
      <b>ИИ-агенты научились смотреть YouTube —</b> релизнулся сборник.
      <br/><br/>•&nbsp;Смотреть видео любой длины и делать их <b>детальные расшифровки.</b>
      <br/><tg-emoji emoji-id="1"><i class="emoji"><b>😶</b></i></tg-emoji><tg-emoji emoji-id="2"><i class="emoji"><b>😶</b></i></tg-emoji>
      <br/><a href="https://example.com">тут.</a>
    </div>
    """
    tag = BeautifulSoup(html, "lxml").select_one(".tgme_widget_message_text")
    converted = telegram_html_from_message(tag)
    assert converted.startswith("<b>ИИ-агенты научились смотреть YouTube —</b> релизнулся")
    assert "\n<b>" not in converted
    assert "• Смотреть видео" in converted or "• Смотреть видео" in converted.replace("\xa0", " ")
    assert converted.count("\n😶") == 0
    assert "😶</tg-emoji><tg-emoji" in converted.replace("\n", "")
    assert '<a href="https://example.com">тут.</a>' in converted
    plain = html_to_plain(converted)
    assert "ИИ-агенты научились смотреть YouTube — релизнулся" in plain
    assert "😶😶" in plain.replace("\n", "")


def test_parse_preview_keeps_video_and_plain_text() -> None:
    html = """
    <div class="tgme_channel_info_header_title">Бэкдор</div>
    <div class="tgme_widget_message" data-post="whackdoor/31088">
      <video class="tgme_widget_message_video" src="https://cdn4.telesco.pe/file/demo.mp4?token=abc"></video>
      <div class="tgme_widget_message_text"><b>Заголовок —</b> текст дальше.<br/>• пункт</div>
      <time datetime="2026-09-04T08:00:00+00:00"></time>
    </div>
    """
    posts = parse_preview_html(html, "whackdoor")
    assert posts[0].video_url == "https://cdn4.telesco.pe/file/demo.mp4?token=abc"
    assert posts[0].text.startswith("Заголовок — текст дальше.")
    assert "• пункт" in posts[0].text
    assert "<b>Заголовок —</b> текст дальше." in posts[0].html_text
