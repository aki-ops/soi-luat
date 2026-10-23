"""B — importer CLI: L13 + H3."""

import json
import sqlite3
from dataclasses import dataclass, field

import soiluat.ingest as ingest_mod
from soiluat.extract import ExtractedPage
from soiluat.importer import main


@dataclass
class Page(ExtractedPage):
    notes: list = field(default_factory=list)
    ocr_conf: float | None = None


def _jobs(tmp_path):
    conn = sqlite3.connect(tmp_path / "soiluat.db")
    rows = conn.execute("SELECT status, file_path, error FROM import_jobs ORDER BY id").fetchall()
    conn.close()
    return rows


def test_l13_loi_mot_file_khong_dung_ca_luot(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path / "data"))
    src = tmp_path / "in"
    src.mkdir()
    (src / "a.txt").write_text("Nghị định số 1/2020/NĐ-CP\nĐiều 1. A\n1. Một.\n", encoding="utf-8")
    (src / "b_hong.docx").write_bytes(b"khong phai docx")
    (src / "c.txt").write_text("Nghị định số 2/2020/NĐ-CP\nĐiều 1. C\n1. Ba.\n", encoding="utf-8")
    (src / "d_trung.txt").write_text("Nghị định số 1/2020/NĐ-CP\nĐiều 1. A\n1. Một.\n", encoding="utf-8")
    (src / "~$a.docx").write_bytes(b"file tam")
    (src / "ghi_chu.xyz").write_text("x", encoding="utf-8")
    assert main([str(src)]) == 1
    out = capsys.readouterr().out
    assert "lỗi" in out and "c.txt" in out and "ghi_chu.xyz" in out
    assert "~$a.docx" not in out
    assert "Tổng 4 file: đủ 2, lỗi 1, trùng 1" in out
    st = [r[0] for r in _jobs(tmp_path / "data")]
    assert st.count("done") == 2 and st.count("failed") == 1 and st.count("skipped_duplicate") == 1


def test_health_khong_crash_file_loi(tmp_path):
    from soiluat.health import scan_dir

    (tmp_path / "hong.docx").write_bytes(b"khong phai docx")
    (tmp_path / "~$tam.docx").write_bytes(b"x")
    (tmp_path / "hai.txt").write_text(
        "Nghị định số 1/2020/NĐ-CP\nĐiều 1. A\n1. x.\nĐiều 2. B\n1. y.\n"
        "Điều 1. A lặp\n1. x.\n", encoding="utf-8")
    rows = {r["file"].rsplit("\\", 1)[-1].rsplit("/", 1)[-1]: r for r in scan_dir(tmp_path)}
    assert set(rows) == {"hong.docx", "hai.txt"}
    assert rows["hong.docx"]["loai"] == "loi" and rows["hong.docx"]["so_hieu"]
    assert rows["hai.txt"]["nghi_nhieu_van_ban"] == 1


def test_h3_check_ocr_json(capsys, monkeypatch):
    import soiluat.importer as imp

    monkeypatch.setattr(imp, "check_ocr", lambda: {"ok": False, "message": "thiếu"})
    assert main(["--check-ocr"]) == 0
    line = capsys.readouterr().out.strip().splitlines()
    assert len(line) == 1 and json.loads(line[0])["ok"] is False


def test_h3_check_ocr_that(capsys):
    assert main(["--check-ocr"]) == 0
    st = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "ok" in st and "message" in st


def test_h3_can_ocr_canh_bao(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path / "data"))
    pages = [
        Page(1, "Nghị định số 1/2020/NĐ-CP\nĐiều 1. A\n1. Một.", "text_ok", "pdf_text"),
        Page(2, "", "image", "pdf_text", ocr_status="cho_ocr"),
    ]
    monkeypatch.setattr(ingest_mod, "extract_file", lambda path: pages)
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"gia")
    assert main([str(f)]) == 0
    assert "cần OCR" in capsys.readouterr().out
    st, _, err = _jobs(tmp_path / "data")[-1]
    assert st == "done" and err == "1 trang cần OCR, nạp lại với --ocr"


def test_h3_ocr_khong_dung_duoc_thi_failed(tmp_path, monkeypatch, capsys):
    import soiluat.ocr as ocr

    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path / "data"))

    def boom(path, pages):
        raise RuntimeError("Chưa cài Tesseract (tesseract.exe) và gói ngôn ngữ vie")

    monkeypatch.setattr(ocr, "maybe_ocr_pages", boom)
    f = tmp_path / "anh.txt"
    f.write_text("Điều 1. A\n1. B.\n", encoding="utf-8")
    assert main([str(f), "--ocr"]) == 1
    st, _, err = _jobs(tmp_path / "data")[-1]
    assert st == "failed" and "Tesseract" in err
