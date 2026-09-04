from app.dedup.engine import Candidate, decide, score_pair
from app.dedup.normalize import text_hash


def test_near_duplicate_news_are_close_but_not_identical() -> None:
    original = (
        "ЦБ сохранил ключевую ставку на уровне 16%. Регулятор отметил устойчивое "
        "инфляционное давление и обещал вернуться к вопросу на следующем заседании."
    )
    paraphrase = (
        "Банк России оставил ключевую ставку 16 процентов. В сообщении регулятора "
        "говорится об устойчивом инфляционном давлении, решение пересмотрят на следующем заседании."
    )
    score = score_pair(original, paraphrase)
    assert 0.58 <= score < 0.85
    recent = [Candidate(item_id=1, content_hash="x", raw_text=original)]
    assert decide(paraphrase, recent, 0.6).is_duplicate
    assert not decide(paraphrase, recent, 0.9).is_duplicate


def test_unrelated_news_stay_unique() -> None:
    left = "В Москве открыли новый участок метро. Поездки начнутся с понедельника."
    right = "Стартап из Новосибирска привлёк раунд на разработку квантовых сенсоров."
    assert score_pair(left, right) < 0.5


def test_different_topics_are_not_duplicates() -> None:
    crypto = (
        "Сбер подключит криптообменники к своей платформе. Клиенты смогут покупать "
        "цифровые активы прямо в приложении банка, сообщила пресс-служба."
    )
    food = (
        "Производитель выпустил линейку снеков с пониженным сахаром. Новые вкусы "
        "появятся в сетях с понедельника, обещает компания."
    )
    assert score_pair(crypto, food) < 0.5
    decision = decide(food, [Candidate(item_id=1, content_hash="x", raw_text=crypto)], 0.6)
    assert not decision.is_duplicate


def test_exact_hash_short_circuits() -> None:
    text = "Учёные опубликовали карту течения Гольфстрима за последние 30 лет."
    recent = [Candidate(item_id=7, content_hash=text_hash(text), raw_text=text)]
    decision = decide(f"{text} https://t.me/x", recent, threshold=0.9)
    assert decision.is_duplicate
    assert decision.reason == "exact_hash"
    assert decision.matched_item_id == 7
