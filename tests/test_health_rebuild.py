from soiluat.health import health_row, write_csv
from soiluat.rebuild import set_page_reviewed
from pathlib import Path


def test_health_csv(tmp_path):
    src = Path(__file__).parent / "fixtures" / "nd15.txt"
    dest = tmp_path / "nd15.txt"
    dest.write_bytes(src.read_bytes())
    row = health_row(dest)
    assert row["so_dieu"]
    assert int(row["so_dieu"]) >= 3
    assert int(row["co_cum_phat_tien_tu"]) == 1
    out = tmp_path / "h.csv"
    write_csv([row], out)
    text = out.read_text(encoding="utf-8")
    assert "so_hieu" in text
    assert "_TONG" in text
    assert "ty_le_xu_phat" in text


def test_rebuild_after_review(db, sample_doc):
    page = db.execute("SELECT id FROM pages WHERE doc_id = ?", (sample_doc,)).fetchone()
    new = "Điều 99. Văn bản đã sửa tay unique_xyz_token\n1. Nội dung đã đối chiếu."
    set_page_reviewed(db, page["id"], new)
    hit = db.execute(
        "SELECT id FROM units WHERE search_text LIKE ?",
        ("%unique xyz token%",),
    ).fetchone()
    if hit is None:
        hit = db.execute(
            "SELECT id FROM units u JOIN units_fts f ON f.rowid = u.id "
            "WHERE units_fts MATCH ?",
            ("unique",),
        ).fetchone()
    assert hit is not None
