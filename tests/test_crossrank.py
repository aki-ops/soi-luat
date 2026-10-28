"""Reranker top-5 (cross-encoder) và nhãn "độ tin cậy cao": chỉ xếp lại 5 Điều đầu, khoản/điểm đi theo Điều, dự phòng khi thiếu mô hình."""

import os
from pathlib import Path

import pytest

from soiluat import crossrank, search, semantic
from soiluat.ingest import ingest_path

TEXT = "Nghị định số 7/2024/NĐ-CP\n" + "".join(
    f"Điều {k}. Mục {k}\n1. Nội dung kw{k}.\na) Điểm của kw{k}.\n" for k in range(1, 8))


class FakeRanker:
    """Điểm 3 nếu Điều chứa nguyên cụm câu hỏi, 0 nếu không."""

    def score(self, query, docs):
        return [3.0 if query.lower() in d.lower() else 0.0 for d in docs]


@pytest.fixture
def doc(db, tmp_path):
    p = tmp_path / "nd7.txt"
    p.write_text(TEXT, encoding="utf-8")
    return ingest_path(db, p, tmp_path)


@pytest.fixture
def fake(monkeypatch, db):
    semantic.set_mode(db, "advance")
    monkeypatch.setattr(crossrank, "_RK", FakeRanker())
    monkeypatch.setattr(crossrank, "_RK_TRIED", True)
    monkeypatch.delenv("SOILUAT_SEMANTIC", raising=False)


def _unit(db, path):
    return db.execute("SELECT id FROM units WHERE path = ?", (path,)).fetchone()[0]


def _ids(db):
    return [_unit(db, f"D{k}") for k in range(1, 8)]


def test_only_top5_reranked_and_children_follow_their_dieu(db, doc, fake):
    d = _ids(db)
    k3 = _unit(db, "D3.K1")
    out, gap = crossrank.rerank_top(db, "kw3", [d[0], d[1], d[2], k3, d[3], d[4], d[5], d[6]])
    assert out == [d[2], k3, d[0], d[1], d[3], d[4], d[5], d[6]]  # D3 lên đầu cùng khoản của nó; D6, D7 giữ chỗ
    assert gap == 3.0


def test_candidate_outside_top5_is_not_touched(db, doc, fake):
    d = _ids(db)
    out, gap = crossrank.rerank_top(db, "kw7", d)  # D7 ở hạng 7: ngoài TOPN, không được kéo lên
    assert out == d and gap == 0.0


def test_gap_is_difference_of_first_two_scores(db, doc, fake):
    d = _ids(db)
    _, gap = crossrank.rerank_top(db, "khong co trong dieu nao", d)
    assert gap == 0.0  # hai Điều đầu bằng điểm: không chắc chắn


def test_normal_mode_does_not_load_ranker(db, doc, monkeypatch):
    monkeypatch.setattr(crossrank, "ranker", lambda: pytest.fail("normal không được nạp reranker"))
    d = _ids(db)
    assert crossrank.rerank_top(db, "kw3", d) == (d, None)


def test_no_model_keeps_order_and_gap_none(db, doc, monkeypatch, tmp_path):
    semantic.set_mode(db, "advance")
    monkeypatch.setenv("SOILUAT_RERANK_DIR", str(tmp_path / "khong_co"))
    monkeypatch.setattr(crossrank, "_RK", None)
    monkeypatch.setattr(crossrank, "_RK_TRIED", False)
    monkeypatch.delenv("SOILUAT_SEMANTIC", raising=False)
    d = _ids(db)
    assert crossrank.ranker() is None and crossrank.rerank_top(db, "kw3", d) == (d, None)


def test_fewer_than_two_dieu_not_scored(db, doc, fake):
    d = _ids(db)
    assert crossrank.rerank_top(db, "kw3", d[:1]) == (d[:1], None)
    assert crossrank.rerank_top(db, "kw3", []) == ([], None)


def test_env_off_switch(db, doc, fake, monkeypatch):
    monkeypatch.setattr(crossrank, "_RK_TRIED", False)
    monkeypatch.setenv("SOILUAT_SEMANTIC", "0")
    assert crossrank.ranker() is None


def test_cascade_search_sets_sure_from_gap(db, doc, fake, monkeypatch):
    class Hot:  # chỉ Điều 3 được điểm cao, bất kể câu hỏi
        def score(self, query, docs):
            return [3.0 if "kw3" in d else 0.0 for d in docs]

    monkeypatch.setattr(crossrank, "_RK", Hot())
    monkeypatch.setattr(semantic, "rerank", lambda conn, q, ids, doc_ids=None: ids)  # chỉ kiểm bước reranker
    r = search.cascade_search(db, "nội dung")  # "nội dung" có ở mọi Điều nên BM25 trả đủ 7 Điều
    assert r.sure is True and r.ids[0] in (_unit(db, "D3"), _unit(db, "D3.K1"))
    monkeypatch.setattr(crossrank, "SURE_GAP", 3.5)
    assert search.cascade_search(db, "nội dung").sure is False


def test_cascade_search_sure_none_in_normal_mode(db, doc, monkeypatch):
    monkeypatch.setattr(crossrank, "ranker", lambda: pytest.fail("normal không được nạp reranker"))
    assert search.cascade_search(db, "kw3").sure is None


def test_frozen_model_dir_beside_exe(tmp_path, monkeypatch):
    import sys

    monkeypatch.delenv("SOILUAT_RERANK_DIR", raising=False)
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path / "data"))
    assert crossrank.model_dir() == tmp_path / "data" / "models" / "aiteamvn-reranker"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "SoiLuat" / "SoiLuat.exe"))
    assert crossrank.model_dir() == tmp_path / "dist" / "SoiLuat" / "models" / "aiteamvn-reranker"


@pytest.mark.skipif(not os.environ.get("SOILUAT_RERANK_DIR"), reason="cần SOILUAT_RERANK_DIR trỏ tới mô hình thật")
def test_real_model_scores_related_text_higher():
    pytest.importorskip("onnxruntime")
    rk = crossrank.Ranker(Path(os.environ["SOILUAT_RERANK_DIR"]))
    helmet, tax = rk.score("không đội mũ bảo hiểm bị phạt bao nhiêu", [
        "Điều 6. Xử phạt\nPhạt tiền người điều khiển xe mô tô không đội mũ bảo hiểm",
        "Điều 3. Thuế\nThời hạn nộp hồ sơ khai thuế giá trị gia tăng"])
    assert helmet > tax
    long = rk.score("quy định", ["quy định " * 2000])  # dài hơn MAXLEN vẫn chấm được (cắt phần Điều)
    assert len(long) == 1
