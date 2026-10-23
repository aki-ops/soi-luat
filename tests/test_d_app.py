"""Agent D: cổng, lệnh Importer, nạp từ UI, /jobs OCR, từ điển, hiển thị trang, xuất Word."""

from __future__ import annotations

import socket
import subprocess
import sys

import pytest
from docx import Document
from fastapi.testclient import TestClient

import soiluat.app as appmod
from soiluat.cards import Card

H = {"Host": "127.0.0.1:8007"}  # cổng khác 8000: Host guard vẫn nhận


def _card(**extra) -> Card:
    c = Card(
        kind="Quy định liên quan",
        title="Điều 5. Báo cáo",
        sample="",
        duty_text="Doanh nghiệp phải báo cáo định kỳ.",
        duty_addr="15/2020/NĐ-CP · Điều 5 khoản 1",
        sanction_text="",
        sanction_addr="",
        hieu_luc="chua_ro",
        link_status="",
        ocr_unverified=True,
        unit_ids=[1],
        page_from=3,
        so_hieu="15/2020/NĐ-CP",
        file_path="nd15.docx",
        warnings=["Hiệu lực chưa rõ"],
    )
    for k, v in extra.items():  # page_to/notes/intent: trường C thêm, có thể chưa có
        setattr(c, k, v)
    return c


@pytest.fixture
def no_ocr_check(monkeypatch):
    monkeypatch.setattr(appmod, "_ocr_cache", {"ok": True, "langs": ["vie"], "message": ""})


# --- cổng ---


def test_pick_port_skips_busy_port():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    busy = srv.getsockname()[1]
    try:
        assert appmod._port_busy(busy)
        got = appmod.pick_port(busy, tries=20)
        assert busy < got <= busy + 20
    finally:
        srv.close()


def test_main_reads_env_port(monkeypatch):
    seen = {}
    monkeypatch.setenv("SOILUAT_PORT", "8123")
    monkeypatch.setenv("SOILUAT_NO_BROWSER", "1")
    monkeypatch.setattr(appmod, "pick_port", lambda p: seen.setdefault("want", p))
    monkeypatch.setattr(appmod.uvicorn, "run", lambda *a, **k: seen.setdefault("port", k["port"]))
    monkeypatch.setattr(appmod.webbrowser, "open", lambda *a: pytest.fail("không được mở trình duyệt"))
    appmod.main([])
    assert seen == {"want": 8123, "port": 8123}
    seen.clear()
    appmod.main(["--port", "9001"])
    assert seen["port"] == 9001


# --- lệnh Importer ---


def test_importer_cmd_source():
    assert appmod.importer_cmd(["x", "--ocr"]) == [sys.executable, "-m", "soiluat.importer", "x", "--ocr"]


def test_importer_cmd_frozen(tmp_path, monkeypatch):
    app_dir = tmp_path / "SoiLuat"
    app_dir.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app_dir / "SoiLuat.exe"))
    with pytest.raises(FileNotFoundError):
        appmod.importer_cmd(["--check-ocr"])
    sib = tmp_path / "SoiLuatImporter" / "SoiLuatImporter.exe"
    sib.parent.mkdir()
    sib.write_bytes(b"")
    assert appmod.importer_cmd(["a"]) == [str(sib), "a"]
    near = app_dir / "SoiLuatImporter.exe"
    near.write_bytes(b"")
    assert appmod.importer_cmd(["a"])[0] == str(near)
    assert appmod._child_kw()["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)


def test_spawn_with_ocr_and_missing_path(tmp_path, monkeypatch, no_ocr_check):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    called: list = []
    monkeypatch.setattr(appmod.subprocess, "Popen", lambda args, **kw: called.append((args, kw)))
    client = TestClient(appmod.app)
    src = tmp_path / "kho"
    src.mkdir()
    r = client.post("/import-spawn", data={"path": str(src), "ocr": "on", "doan": "on"}, follow_redirects=False)
    assert r.status_code == 303
    args, kw = called[0]
    assert args[-3:] == [str(src), "--ocr", "--doan"]
    assert kw["env"]["SOILUAT_DATA"] == str(tmp_path.resolve())
    r = client.post("/import-spawn", data={"path": str(tmp_path / "khong_co")})
    assert r.status_code == 400 and "Không thấy" in r.text
    assert len(called) == 1


# --- /jobs + trạng thái OCR ---


def _fake_run(result):
    def run(*a, **k):
        if isinstance(result, Exception):
            raise result
        return result

    return run


@pytest.mark.parametrize(
    "result",
    [
        subprocess.TimeoutExpired(["x"], 10),
        subprocess.CompletedProcess([], 2, stdout="usage: lỗi", stderr="bad"),
        subprocess.CompletedProcess([], 0, stdout="không phải json", stderr=""),
        OSError("không chạy được"),
    ],
)
def test_jobs_when_check_ocr_fails(tmp_path, monkeypatch, result):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    monkeypatch.setattr(appmod, "_ocr_cache", None)
    monkeypatch.setattr(appmod.subprocess, "run", _fake_run(result))
    r = TestClient(appmod.app).get("/jobs")
    assert r.status_code == 200
    assert "Không kiểm tra được OCR" in r.text
    assert 'name="ocr"' in r.text


def test_jobs_ocr_missing_shows_help_and_caches(tmp_path, monkeypatch):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    monkeypatch.setattr(appmod, "_ocr_cache", None)
    n = {"calls": 0}
    line = '{"ok": false, "tesseract_cmd": null, "tessdata": null, "langs": [], "message": "Thiếu vie"}'

    def run(*a, **k):
        n["calls"] += 1
        return subprocess.CompletedProcess([], 0, stdout="cảnh báo\n" + line + "\n", stderr="")

    monkeypatch.setattr(appmod.subprocess, "run", run)
    client = TestClient(appmod.app)
    r = client.get("/jobs")
    assert "Thiếu vie" in r.text and "winget" in r.text
    client.get("/jobs")
    assert n["calls"] == 1
    client.get("/jobs", params={"ocr": "lai"})
    assert n["calls"] == 2


# --- /review/synonyms ---


def test_synonyms_crud_with_csrf(tmp_path, monkeypatch):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    monkeypatch.delenv("SOILUAT_ALLOW_TEST_HOST", raising=False)
    from soiluat.config import db_path
    from soiluat.db import connect

    client = TestClient(appmod.app)
    page = client.get("/review/synonyms", headers=H)
    assert page.status_code == 200 and "Từ điển" in page.text
    token = page.cookies.get("soiluat_csrf")
    form = {"term": "XYZT", "alt": "cụm thử nghiệm riêng", "kind": "viet_tat"}
    assert client.post("/synonyms", headers=H, data=form, follow_redirects=False).status_code == 403
    r = client.post("/synonyms", headers=H, data={**form, "csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303

    def row():
        conn = connect(db_path())
        x = conn.execute("SELECT id, approved, kind FROM synonyms WHERE term = 'XYZT'").fetchone()
        conn.close()
        return x

    sid = row()["id"]
    assert row()["approved"] == 1 and row()["kind"] == "viet_tat"
    assert "cụm thử nghiệm riêng" in client.get("/review/synonyms", headers=H).text
    assert client.post(f"/synonyms/{sid}/approve", headers=H, data={"approved": "0"}, follow_redirects=False).status_code == 403
    client.post(f"/synonyms/{sid}/approve", headers=H, data={"approved": "0", "csrf_token": token}, follow_redirects=False)
    assert row()["approved"] == 0
    client.post(f"/synonyms/{sid}/approve", headers=H, data={"approved": "1", "csrf_token": token}, follow_redirects=False)
    assert row()["approved"] == 1
    assert client.post(f"/synonyms/{sid}/delete", headers=H, follow_redirects=False).status_code == 403
    client.post(f"/synonyms/{sid}/delete", headers=H, data={"csrf_token": token}, follow_redirects=False)
    assert row() is None


def test_home_links_synonyms(tmp_path, monkeypatch):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    assert "/review/synonyms" in TestClient(appmod.app).get("/").text


# --- hiển thị ---


def test_results_card_shows_pages_notes_intent():
    c = _card(page_to=4, notes=["gc1", "gc2", "gc3", "gc4"], intent="muc_phat")
    html = appmod.TEMPLATES.env.get_template("_results.html").render(
        cards=[c], n={"n1": 0, "n2": 0, "n3": 0, "n4": 1}, dates={1: {"ngay_ban_hanh": "2020-02-01", "ngay_hieu_luc": None}},
        csrf_token="t", q="x",
    )
    assert "Trang 3–4" in html
    assert "Ý định: mức phạt" in html
    assert "gc3" in html and "gc4" not in html
    assert "ban hành 2020-02-01" in html


def test_results_card_without_new_fields():
    from types import SimpleNamespace

    # Card kiểu 0.7: không có page_to/notes/intent
    c = SimpleNamespace(**{k: v for k, v in vars(_card()).items() if k not in ("page_to", "notes", "intent")})
    html = appmod.TEMPLATES.env.get_template("_results.html").render(
        cards=[c], n={"n1": 0, "n2": 0, "n3": 0, "n4": 1}, dates={}, csrf_token="t", q="x"
    )
    assert "Trang 3" in html


def test_unit_page_lists_notes_and_dates(tmp_path, monkeypatch, db, sample_doc):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    dieu = db.execute("SELECT * FROM units WHERE level = 'dieu' ORDER BY id LIMIT 1").fetchone()
    child = db.execute("SELECT id FROM units WHERE parent_id = ? LIMIT 1", (dieu["id"],)).fetchone()
    parent = child["id"] if child else dieu["id"]
    db.execute(
        "INSERT INTO units(doc_id, parent_id, path, level, raw_text, normalized_text, search_text, "
        "extraction_method, verification_status, page_from, page_to) "
        "VALUES (?, ?, 'GC1', 'ghi_chu', 'Chú thích kiểm thử D', '', '', 'docx', 'auto', 2, 2)",
        (dieu["doc_id"], parent),
    )
    db.execute("UPDATE documents SET ngay_ban_hanh = '2020-01-15', ngay_hieu_luc = '2020-03-01'")
    db.commit()
    r = TestClient(appmod.app).get(f"/unit/{dieu['id']}")
    assert r.status_code == 200
    assert "Chú thích kiểm thử D" in r.text
    assert "2020-01-15" in r.text and "2020-03-01" in r.text
    docs = TestClient(appmod.app).get("/review/docs")
    assert docs.status_code == 200 and "2020-01-15" in docs.text


# --- xuất Word ---


def test_export_has_page_file_notes_warnings(tmp_path):
    from soiluat.export_word import export_cards

    dest = tmp_path / "out.docx"
    export_cards([_card(page_to=5, notes=["Ghi chú cuối trang"])], dest)
    text = "\n".join(p.text for p in Document(str(dest)).paragraphs)
    assert "Trang 3–5" in text
    assert "nd15.docx" in text
    assert "Hạng" in text and "Điều 5 khoản 1" in text
    assert "Ghi chú cuối trang" in text
    assert "OCR chưa xác minh" in text
    assert "Hiệu lực: chua_ro" in text
