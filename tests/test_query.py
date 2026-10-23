from soiluat.query import classify_query, strip_question
from soiluat.sohieu import citation_remainder


def test_classify_so_hieu():
    assert classify_query("Điều 5 Nghị định 15/2020/NĐ-CP") == "so_hieu"


def test_classify_keyword():
    assert classify_query("báo cáo định kỳ") == "keyword"


def test_strip_question():
    q = strip_question("phải làm gì khi chậm báo cáo?")
    assert "phải làm gì" not in q.lower()
    assert "báo cáo" in q.lower() or "cham" in q.lower() or "chậm" in q.lower()


def test_citation_remainder_keeps_keywords():
    assert citation_remainder("báo cáo 15/2020") == "báo cáo"
    assert citation_remainder("Điều 5 Nghị định 15/2020/NĐ-CP") == ""
    assert citation_remainder("báo cáo định kỳ") == "báo cáo định kỳ"
