"""Sprint 0.8.1: các lỗ hổng A1–A6 sau demo."""
from fastapi.testclient import TestClient

from soiluat import app as appmod
from soiluat.parse import parse_structure

SUA_DOI = (
    "Nghị định số 9/2024/NĐ-CP\n"
    "Điều 1. Sửa đổi, bổ sung một số điều\n"
    "1. Sửa đổi Điều 5 như sau:\n"
    "{open}Điều 5. Báo cáo định kỳ\n"
    "1. Cơ quan phải báo cáo hằng năm.\n"
    "2. Báo cáo gửi trước ngày 31 tháng 1.{close}\n"
    "2. Bổ sung khoản vào Điều 6.\n"
    "Điều 2. Hiệu lực thi hành\n"
    "1. Nghị định này có hiệu lực từ ngày ký.\n"
)


def _dieu_addrs(text):
    return [u.addr_part for u in parse_structure(text).units if u.level == "dieu"]


def test_a1_quoted_dieu_curly_and_straight_are_not_new_dieu():
    for o, c in (("“", "”"), ('"', '"')):
        addrs = _dieu_addrs(SUA_DOI.format(open=o, close=c))
        assert addrs == ["D1", "D2"], (o, addrs)


def test_a1_curly_quote_closing_line_stays_in_dieu():
    r = parse_structure(SUA_DOI.format(open="“", close="”"))
    d1 = " ".join(u.text for u in r.units if u.addr_part.startswith("D1"))
    assert "31 tháng 1" in d1 and "Bổ sung khoản vào Điều 6" not in d1.split("31 tháng 1")[0]


def test_a2_loai_filter_lists_all_types(tmp_path, monkeypatch):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    html = TestClient(appmod.app).get("/").text
    for v in ("luat", "nghi_quyet", "cong_van", "chi_thi", "phap_lenh", "nghi_dinh"):
        assert f'value="{v}"' in html


def test_a6_xu_phat_as_topic_keeps_phrase():
    from soiluat.query import split_intent

    assert split_intent("thẩm quyền xử phạt của Chủ tịch UBND") == ("", "thẩm quyền xử phạt của Chủ tịch UBND")
    assert split_intent("hình thức xử phạt vi phạm hành chính")[0] == ""
    assert split_intent("không báo cáo định kỳ bị phạt bao nhiêu") == ("muc_phat", "không báo cáo định kỳ")
    # cụm hỏi mức phạt vẫn bị bỏ khi chỗ khác trong câu có "thẩm quyền xử phạt"
    assert split_intent("mức phạt tiền không nộp báo cáo")[0] == "muc_phat"


def test_a3_dieu_only_is_capped(tmp_path, monkeypatch):
    from soiluat import search
    from soiluat.db import connect, init_schema
    from soiluat.ingest import ingest_path

    monkeypatch.setattr(search, "DIEU_CAP", 3)
    monkeypatch.setattr(appmod, "DIEU_CAP", 3)
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    conn = connect(tmp_path / "soiluat.db")
    init_schema(conn)
    for i in range(1, 6):
        f = tmp_path / f"v{i}.txt"
        f.write_text(
            f"Nghị định số {i}/2020/NĐ-CP\n"
            + "".join(f"Điều {d}. Nội dung {d} số {i}\n1. Khoản một.\n" for d in range(1, 6)),
            encoding="utf-8",
        )
        ingest_path(conn, f, tmp_path)
    conn.close()
    r = TestClient(appmod.app).get("/", params={"q": "Điều 5"})
    assert r.text.count('class="card') == 3
    assert "chỉ hiển thị 3" in r.text


def test_a4_comment_attaches_to_dieu_with_label():
    from types import SimpleNamespace as NS

    from soiluat.parse import parse_pages

    text = (
        "Nghị định số 1/2020/NĐ-CP\n"
        + "".join(f"Điều {d}. Tên điều {d}\n1. Khoản một của {d}.\n" for d in range(1, 5))
    )
    note = NS(kind="comment", text="Cần đối chiếu", ref="Điều 3. Tên điều 3")
    note2 = NS(kind="comment", text="Xem lại", ref="1. Khoản một của 2.")
    r = parse_pages([NS(page_no=1, text=text, notes=[note, note2])])
    got = {u.title: u.parent_addr for u in r.units if u.level == "ghi_chu"}
    assert got["Nhận xét"] in ("D3", "D2.K1")
    parents = sorted(u.parent_addr for u in r.units if u.level == "ghi_chu")
    assert parents == ["D2.K1", "D3"]


def test_a5_pdf_footnote_split_and_attached(tmp_path):
    import os

    import pytest

    fitz = pytest.importorskip("fitz")
    font = r"C:\Windows\Fonts\arial.ttf"
    if not os.path.exists(font):
        pytest.skip("không có arial.ttf")
    from soiluat.extract import extract_pdf
    from soiluat.parse import parse_pages

    NAMES = {1: "một", 2: "hai", 3: "ba", 4: "bốn"}
    doc = fitz.open()
    page = doc.new_page()
    page.insert_font(fontname="vn", fontfile=font)
    y = 60
    for line in ["Nghị định số 7/2024/NĐ-CP"] + [
        t for d in range(1, 5) for t in (f"Điều {d}. Tên điều {NAMES[d]}", f"1. Nội dung khoản của điều {NAMES[d]} khá dài để đủ chữ.")
    ]:
        page.insert_text((60, y), line, fontname="vn", fontsize=11)
        y += 22
    # chỉ số mũ "2" sau tên Điều 3 (cỡ nhỏ, nâng lên), footnote ở cuối trang
    page.insert_text((60 + 11 * 0.5 * len("Điều 3. Tên điều ba") + 4, 60 + 22 * 5 - 4), "2", fontname="vn", fontsize=7)
    page.insert_text((60, 780), "2 Điều này được sửa đổi bởi Nghị định số 1/2025/NĐ-CP.", fontname="vn", fontsize=8)
    path = tmp_path / "fn.pdf"
    doc.save(path)
    pages = extract_pdf(path)
    assert [n.text.replace("­", "-") for n in pages[0].notes] == ["Điều này được sửa đổi bởi Nghị định số 1/2025/NĐ-CP."]
    assert "sửa đổi bởi Nghị định số 1/2025" not in pages[0].text
    r = parse_pages(pages)
    gc = [u for u in r.units if u.level == "ghi_chu"]
    assert len(gc) == 1 and gc[0].parent_addr == "D3"


def test_c_page_image_route(tmp_path, monkeypatch):
    import pytest

    fitz = pytest.importorskip("fitz")
    from soiluat.db import connect, init_schema
    from soiluat.ingest import ingest_path

    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((60, 80), "Nghi dinh so 3/2024/ND-CP", fontsize=11)
    for d in range(1, 5):
        page.insert_text((60, 80 + 30 * d), f"Dieu {d}. Ten dieu", fontsize=11)
        page.insert_text((60, 95 + 30 * d), "1. Noi dung khoan mot.", fontsize=11)
    pdf = tmp_path / "v.pdf"
    doc.save(pdf)
    conn = connect(tmp_path / "soiluat.db")
    init_schema(conn)
    did = ingest_path(conn, pdf, tmp_path)
    uid = conn.execute("SELECT id FROM units WHERE doc_id = ? LIMIT 1", (did,)).fetchone()["id"]
    conn.close()
    c = TestClient(appmod.app)
    r = c.get(f"/page/{did}/1")
    assert r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert c.get(f"/page/{did}/9").status_code == 404
    assert c.get("/page/999/1").status_code == 404
    assert f"/page/{did}/1" in c.get(f"/unit/{uid}").text
    pdf.unlink()  # file gốc mất → 404, không lỗi 500
    assert c.get(f"/page/{did}/1").status_code == 404


def test_c_numbering_labels_roman_legal_and_cross_level():
    from soiluat.extract import _Lvl, render_label

    lv = {0: _Lvl("upperRoman", "Chương %1", start=1), 1: _Lvl("decimal", "Điều %2."), 2: _Lvl("lowerLetter", "%3)")}
    c: dict = {}
    got = [render_label(lv, c, 1, i) for i in (0, 1, 2, 2, 0, 1, 2)]
    assert got == ["Chương I", "Điều 1.", "a)", "b)", "Chương II", "Điều 1.", "a)"]
    legal = {0: _Lvl(text="%1."), 1: _Lvl(text="%1.%2"), 2: _Lvl(text="%1.%2.%3")}
    c = {}
    assert [render_label(legal, c, 2, i) for i in (0, 1, 1, 0, 1, 2)] == ["1.", "1.1", "1.2", "2.", "2.1", "2.1.1"]
    assert render_label({0: _Lvl("lowerRoman", "%1.", start=5)}, {}, 3, 0) == "v."
    assert render_label({0: _Lvl("bullet", "\uf0b7")}, {}, 4, 0) == "-"
