from soiluat.search import apply_doc_filters, cascade_search
from soiluat.sohieu import infer_co_quan, infer_loai


def test_infer_loai_and_co_quan():
    assert infer_loai("15/2020/NĐ-CP") == "nghi_dinh"
    assert infer_loai("12/2021/TT-NHNN") == "thong_tu"
    assert infer_co_quan("CỘNG HÒA\nCHÍNH PHỦ\nHà Nội") == "CHÍNH PHỦ"


def test_ingest_sets_loai_nghi_dinh(db, sample_doc):
    row = db.execute(
        "SELECT loai, so_hieu FROM documents WHERE id = ?", (sample_doc,)
    ).fetchone()
    assert row["loai"] == "nghi_dinh"
    assert "15/2020" in (row["so_hieu"] or "")


def test_filter_hieu_luc(db, sample_doc):
    ids, _, _ = cascade_search(db, "bao cao")
    assert ids
    empty = apply_doc_filters(db, ids, hieu_luc="con")
    assert empty == []
    same = apply_doc_filters(db, ids, hieu_luc="chua_ro")
    assert same == ids
    none = apply_doc_filters(db, ids, loai="thong_tu")
    assert none == []
    nd = apply_doc_filters(db, ids, loai="nghi_dinh")
    assert nd == ids
