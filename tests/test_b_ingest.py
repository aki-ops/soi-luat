"""B — nạp: L7, L9 (nhóm văn bản), L10, L11, L12/H5, L21, ghi chú, rebuild."""

from dataclasses import dataclass, field
from pathlib import Path

import soiluat.ingest as ingest_mod
from soiluat.extract import ExtractedPage
from soiluat.ingest import ingest_path, relative_path
from soiluat.rebuild import rebuild_document
from soiluat.sohieu import find_ngay_ban_hanh, find_ngay_hieu_luc, infer_loai_text

from test_b_parse import D11, Note


@dataclass
class Page(ExtractedPage):
    notes: list = field(default_factory=list)
    ocr_conf: float | None = None


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_l7_file_trung_dieu_nap_duoc(db, tmp_path):
    p = _write(
        tmp_path / "trung.txt",
        "Nghị định số 1/2020/NĐ-CP\nĐiều 1. A\n1. Một.\n1. Lặp khoản.\nĐiều 2. B\n1. Hai.\n"
        "Điều 1. A lặp\n1. Một lặp.\nĐiều 2. B lặp\n1. Hai lặp.\n",
    )
    doc_id = ingest_path(db, p, tmp_path)
    paths = {r["path"] for r in db.execute("SELECT path FROM units WHERE doc_id = ?", (doc_id,))}
    assert {"D1", "D1.K1~2", "D1~2", "D1~2.K1", "D2~2.K1"} <= paths
    doc = db.execute("SELECT multi_document_suspected FROM documents").fetchone()
    assert doc["multi_document_suspected"] == 1


def test_l9_hai_van_ban_mot_file(db, tmp_path):
    p = _write(tmp_path / "hai.txt", D11)
    first = ingest_path(db, p, tmp_path)
    docs = db.execute("SELECT * FROM documents ORDER BY id").fetchall()
    assert len(docs) == 2 and docs[0]["id"] == first
    assert docs[0]["file_path"] == "hai.txt" and docs[1]["file_path"] == "hai.txt#vb2"
    assert docs[1]["sha256"] == docs[0]["sha256"] + "#vb2"
    assert docs[1]["so_hieu"] == "88/2023/NĐ-CP"
    assert docs[1]["ngay_ban_hanh"] == "2019-07-05"
    n2 = db.execute("SELECT COUNT(*) FROM units WHERE doc_id = ?", (docs[1]["id"],)).fetchone()[0]
    assert n2 >= 4
    # nạp lại nội dung khác: cập nhật cả nhóm, giữ links đã duyệt
    u1 = db.execute("SELECT id FROM units WHERE doc_id = ? AND path = 'D1.K1'", (docs[0]["id"],)).fetchone()
    u2 = db.execute("SELECT id FROM units WHERE doc_id = ? AND path = 'D2.K1'", (docs[1]["id"],)).fetchone()
    db.execute("INSERT INTO links(sanction_unit, duty_unit, method, confirmed) VALUES (?, ?, 'tay', 1)",
               (u1["id"], u2["id"]))
    db.commit()
    _write(p, D11.replace("trong 5 năm.", "trong 10 năm."))
    ingest_path(db, p, tmp_path)
    docs2 = db.execute("SELECT id, file_path FROM documents ORDER BY id").fetchall()
    assert [d["id"] for d in docs2] == [d["id"] for d in docs]
    assert db.execute("SELECT COUNT(*) FROM links WHERE confirmed = 1").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM units WHERE raw_text LIKE '%10 năm%'").fetchone()[0] == 1
    # còn một văn bản: #vb2 bị xoá
    _write(p, D11.split("BỘ XÂY DỰNG\nCỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập")[0])
    ingest_path(db, p, tmp_path)
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1


def test_l10_trang_khi_nap_va_rebuild(db, tmp_path, monkeypatch):
    pages = [
        Page(1, "Nghị định số 1/2020/NĐ-CP\nĐiều 1. Một\n1. Khoản một.", "text_ok", "pdf_text",
             ocr_conf=0.91),
        Page(2, "Điều 2. Hai\n1. Khoản hai[^1].", "text_ok", "pdf_text",
             notes=[Note("footnote", "chú thích hai", "1")]),
    ]
    monkeypatch.setattr(ingest_mod, "extract_file", lambda path: pages)
    p = _write(tmp_path / "x.pdf", "giả")
    doc_id = ingest_path(db, p, tmp_path)

    def pg():
        return {
            r["path"]: (r["page_from"], r["page_to"])
            for r in db.execute("SELECT path, page_from, page_to FROM units WHERE doc_id = ?", (doc_id,))
        }

    assert pg()["D1.K1"] == (1, 1) and pg()["D2.K1"] == (2, 2)
    conf = db.execute("SELECT ocr_conf FROM pages WHERE page_no = 1").fetchone()[0]
    assert abs(conf - 0.91) < 1e-9
    gc = db.execute(
        "SELECT u.page_from, pu.path AS ppath FROM units u JOIN units pu ON pu.id = u.parent_id "
        "WHERE u.level = 'ghi_chu'"
    ).fetchone()
    assert gc["ppath"] == "D2.K1" and gc["page_from"] == 2
    assert not db.execute(
        "SELECT 1 FROM unit_labels l JOIN units u ON u.id = l.unit_id WHERE u.level = 'ghi_chu'"
    ).fetchone()
    rebuild_document(db, doc_id)
    assert pg()["D2.K1"] == (2, 2) and "GC1" in pg()


def test_l11_metadata(db, tmp_path):
    p = _write(tmp_path / "meta.docx.txt", D11.split("BỘ XÂY DỰNG\nCỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập")[0])
    ingest_path(db, p, tmp_path)
    d = db.execute("SELECT * FROM documents").fetchone()
    assert d["ngay_ban_hanh"] == "2023-09-15"
    assert d["ngay_hieu_luc"] == "2023-07-01"
    assert d["loai"] == "thong_tu"
    assert d["hieu_luc"] == "chua_ro"
    assert find_ngay_hieu_luc("Thông tư này có hiệu lực thi hành kể từ ngày 01/01/2023.") == "2023-01-01"
    assert find_ngay_hieu_luc("có hiệu lực kể từ ngày ký") is None
    assert find_ngay_ban_hanh("Căn cứ Luật ngày 19 tháng 6 năm 2015;") is None
    assert infer_loai_text("BỘ TÀI CHÍNH\nSố: 1234/BTC-TCT\nV/v hướng dẫn") == "cong_van"
    assert infer_loai_text("Văn bản lạ không rõ loại", None) is None
    assert infer_loai_text("QUỐC HỘI\nLUẬT\nDOANH NGHIỆP") == "luat"


def test_l11_loai_khong_phai_duoi_file(db, tmp_path):
    p = _write(tmp_path / "x.txt", "Điều 1. A\n1. Nội dung.\nĐiều 2. B\n1. Hai.\n")
    ingest_path(db, p, tmp_path)
    assert db.execute("SELECT loai FROM documents").fetchone()["loai"] is None


def test_l12_trung_ten_ngoai_data(db, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    a = _write(tmp_path / "ngoai" / "a" / "quy-dinh.txt", "Nghị định số 1/2017/NĐ-CP\nĐiều 1. A\n1. thang máy.\n")
    b = _write(tmp_path / "ngoai" / "b" / "quy-dinh.txt", "Nghị định số 2/2017/NĐ-CP\nĐiều 1. B\n1. nồi hơi.\n")
    ingest_path(db, a, data)
    ingest_path(db, b, data)
    rows = db.execute("SELECT file_path FROM documents ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0]["file_path"] == a.resolve().as_posix()
    assert relative_path(data / "x" / "y.txt", data) == "x/y.txt"


def test_l21_dan_chieu_van_ban_khac(db, tmp_path):
    goc = _write(
        tmp_path / "goc.txt",
        "Nghị định số 15/2020/NĐ-CP\nĐiều 4. A\n1. A.\nĐiều 5. Nghĩa vụ\n1. Tổ chức phải báo cáo goc_unique.\n",
    )
    ingest_path(db, goc, tmp_path)
    phat = _write(
        tmp_path / "phat.txt",
        "Thông tư số 9/2021/TT-BTC\nĐiều 4. Xử phạt\n"
        "1. Phạt tiền từ 1.000.000 đồng đến 2.000.000 đồng đối với hành vi vi phạm quy định tại "
        "khoản 1 Điều 5 Nghị định số 15/2020/NĐ-CP.\n"
        "2. Phạt tiền từ 3.000.000 đồng đến 4.000.000 đồng đối với hành vi vi phạm quy định tại "
        "khoản 1 Điều 5 Nghị định số 99/2099/NĐ-CP.\n"
        "Điều 5. Nghĩa vụ riêng\n1. Phải làm việc riêng.\n",
    )
    pid = ingest_path(db, phat, tmp_path)
    rows = db.execute(
        "SELECT su.path AS sp, du.doc_id AS dd, du.path AS dp FROM links l "
        "JOIN units su ON su.id = l.sanction_unit JOIN units du ON du.id = l.duty_unit "
        "WHERE l.method = 'dan_chieu'"
    ).fetchall()
    got = {(r["sp"], r["dd"], r["dp"]) for r in rows}
    assert ("D4.K1", 1, "D5.K1") in got
    # số hiệu không có trong kho → không nối về Điều 5 của chính văn bản
    assert not any(sp == "D4.K2" and dd == pid for sp, dd, _ in got)


def test_l21_dieu_nay_trong_dieu_trung(db, tmp_path):
    p = _write(
        tmp_path / "noibo.txt",
        "Nghị định số 9/2020/NĐ-CP\nĐiều 4. X\n1. X.\nĐiều 5. A\n1. A.\n"
        "Điều 5. Báo cáo và xử phạt\n1. Tổ chức phải nộp báo cáo.\n"
        "2. Phạt tiền từ 1.000.000 đồng đến 2.000.000 đồng đối với hành vi vi phạm khoản 1 Điều này.\n",
    )
    ingest_path(db, p, tmp_path)
    row = db.execute(
        "SELECT du.path FROM links l JOIN units du ON du.id = l.duty_unit WHERE l.method = 'noi_bo'"
    ).fetchone()
    assert row["path"] == "D5~2.K1"


def _jobs(db):
    return db.execute("SELECT COUNT(*) FROM import_jobs").fetchone()[0]


def test_nap_lai_cung_file_voi_ocr(db, tmp_path, monkeypatch):
    """File scan nạp lần đầu không --ocr; nạp lại với --ocr phải OCR, không bị bỏ qua là 'không đổi'."""
    f = _write(tmp_path / "scan.txt", "x")  # nội dung thật không dùng: _extract bị thay

    def fake_extract(path, run_ocr):
        if run_ocr:
            return [Page(1, "Nghị định số 5/2021/NĐ-CP\nĐiều 1. A\n1. Tổ chức phải báo cáo.\n",
                         "image", "ocr", ocr_status="ocr_xong")]
        return [Page(1, "", "image", "pdf_text", ocr_status="cho_ocr")]

    monkeypatch.setattr(ingest_mod, "_extract", fake_extract)
    doc_id = ingest_path(db, f, tmp_path)
    assert db.execute("SELECT COUNT(*) FROM units WHERE doc_id = ?", (doc_id,)).fetchone()[0] == 0

    n = _jobs(db)
    assert ingest_path(db, f, tmp_path) == doc_id and _jobs(db) == n  # không --ocr: vẫn bỏ qua

    assert ingest_path(db, f, tmp_path, run_ocr=True) == doc_id
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM units WHERE doc_id = ?", (doc_id,)).fetchone()[0] > 0
    assert db.execute("SELECT ocr_status FROM pages WHERE doc_id = ?", (doc_id,)).fetchone()[0] == "ocr_xong"

    n = _jobs(db)
    assert ingest_path(db, f, tmp_path, run_ocr=True) == doc_id
    assert _jobs(db) == n  # đã OCR xong: nạp lại với --ocr không làm lại


def test_nap_lai_cung_file_voi_doan(db, tmp_path):
    f = _write(
        tmp_path / "vb.txt",
        "Nghị định số 7/2022/NĐ-CP\nĐiều 1. A\n1. Tổ chức phải báo cáo.\nĐiều 2. B\n1. Hai.\n",
    )
    doc_id = ingest_path(db, f, tmp_path)
    levels = lambda: {r[0] for r in db.execute("SELECT level FROM units WHERE doc_id = ?", (doc_id,))}
    assert "dieu" in levels()

    assert ingest_path(db, f, tmp_path, force_doan=True) == doc_id
    assert levels() == {"doan"}
    assert db.execute("SELECT fallback_doan FROM documents WHERE id = ?", (doc_id,)).fetchone()[0] == 1

    n = _jobs(db)
    assert ingest_path(db, f, tmp_path, force_doan=True) == doc_id
    assert _jobs(db) == n  # đã chia đoạn: nạp lại với --doan không làm lại
