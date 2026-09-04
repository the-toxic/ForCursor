from app.dedup.engine import Candidate, decide, score_pair


def test_near_duplicate_news_are_detected() -> None:
    original = (
        "ЦБ сохранил ключевую ставку на уровне 16%. Регулятор отметил устойчивое "
        "инфляционное давление и обещал вернуться к вопросу на следующем заседании."
    )
    paraphrase = (
        "Банк России оставил ключевую ставку 16 процентов. В сообщении регулятора "
        "говорится об устойчивом инфляционном давлении, решение пересмотрят на следующем заседании."
    )
    assert score_pair(original, paraphrase) >= 0.82


def test_unrelated_news_stay_unique() -> None:
    left = "В Москве открыли новый участок метро. Поездки начнутся с понедельника."
    right = "Стартап из Новосибирска привлёк раунд на разработку квантовых сенсоров."
    assert score_pair(left, right) < 0.5


def test_exact_hash_short_circuits() -> None:
    text = "Учёные опубликовали карту течения Гольфстрима за последние 30 лет."
    from app.dedup.normalize import text_hash

    recent = [Candidate(item_id=7, content_hash=text_hash(text), raw_text=text)]
    decision = decide(f"{text} https://t.me/x", recent, threshold=0.9)
    assert decision.is_duplicate
    assert decision.reason == "exact_hash"
    assert decision.matched_item_id == 7
