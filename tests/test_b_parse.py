"""B — parser: L7 (trùng path), L8 (định dạng lệch), L9 (tách văn bản), L10 (trang), ghi chú."""

from dataclasses import dataclass, field

from soiluat.extract import ExtractedPage
from soiluat.parse import parse_pages, parse_structure, so_tu_chu, split_documents


@dataclass
class Page(ExtractedPage):
    # không phụ thuộc A: tự khai báo trường mới của H1
    notes: list = field(default_factory=list)
    ocr_conf: float | None = None


@dataclass
class Note:
    kind: str
    text: str
    ref: str | None = None


def _pg(no: int, text: str, **kw) -> Page:
    return Page(page_no=no, text=text, kind="text_ok", extraction_method="docx", **kw)


def _paths(r) -> list[str]:
    return [u.addr_part for u in r.units]


D09 = """BỘ CÔNG THƯƠNG
Số: 77/2022/TT-BCT
THÔNG TƯ
Quy định về quản lý nhân viên bán hàng
Chương I
QUY ĐỊNH CHUNG
Mục 1. PHẠM VI
ĐIỀU 1: PHẠM VI ĐIỀU CHỈNH
1) Thông tư này quy định về quản lý nhân viên bán hàng tại siêu thị.
Điều thứ hai. Nghĩa vụ của nhân viên
1) Nhân viên bán hàng phải đeo thẻ nhân viên khi làm việc
tại quầy và phải mặc đồng phục theo quy định của
doanh nghiệp.
a. Thẻ nhân viên phải ghi rõ họ tên và mã số;
đ) Thẻ phải còn hiệu lực.
Điều 3 . Hành vi bị cấm
1/ Nghiêm cấm nhân viên nhận tiền boa của khách hàng.
Điều 4.Hiệu lực
1. Thông tư này có hiệu lực từ ngày 01/01/2023.
"""


def test_l8_dinh_dang_lech():
    r = parse_structure(D09)
    assert r.tier == 2  # Điều không chuẩn → tầng 2
    p = _paths(r)
    assert p == [
        "D1", "D1.K1", "D2", "D2.K1", "D2.K1.Đa", "D2.K1.Đđ", "D3", "D3.K1", "D4", "D4.K1",
    ]
    by = {u.addr_part: u for u in r.units}
    assert "doanh nghiệp." in by["D2.K1"].text  # dòng ngắt giữa câu gộp vào khoản
    assert by["D4"].title == "Hiệu lực"
    # Chương/Mục không thành đơn vị, không dính vào text
    assert not any("QUY ĐỊNH CHUNG" in u.text or "Mục 1" in u.text for u in r.units)


def test_noi_dung_truoc_dieu_dau_khong_mat():
    # ảnh chụp trang 2: khoản mồ côi trước Điều đầu tiên
    text = (
        "nhiệm về tính chính xác.\n"
        "3. Tổ chức tín dụng phải báo cáo định kỳ.\n"
        "4. Cơ sở phải bố trí người vận hành.\n"
        "a) có chứng chỉ;\n"
        "5. Cơ sở phải lưu giữ sổ nhật ký vận hành lò hơi.\n"
        "Điều 6. Kiểm định\n1. Cơ sở phải kiểm định nồi hơi.\n"
        "Điều 7. Hiệu lực\n1. Có hiệu lực.\n"
    )
    r = parse_structure(text)
    doan = [u for u in r.units if u.level == "doan"]
    assert [u.addr_part for u in doan] == ["p1.para1", "p1.para2", "p1.para3", "p1.para4"]
    assert "sổ nhật ký vận hành lò hơi" in doan[-1].text
    assert "a) có chứng chỉ;" in doan[2].text
    assert "D6.K1" in _paths(r)


def test_phan_mo_dau_chuan_khong_thanh_don_vi():
    r = parse_structure(D11.split("Nơi nhận")[0] + "\nĐiều 3. Ba\n1. x.")
    assert not any(u.level == "doan" for u in r.units)
    t = ("CHÍNH PHỦ\nSố: 1/2020/NĐ-CP\nHà Nội, ngày 1 tháng 2 năm 2020\nNGHỊ ĐỊNH\n"
         "Quy định chi tiết về thuế\nCăn cứ Luật Tổ chức Chính phủ;\nTheo đề nghị của Bộ trưởng;\n"
         "Chính phủ ban hành Nghị định quy định chi tiết.\nChương I\nQUY ĐỊNH CHUNG\n"
         "Điều 1. Một\n1. A.\nĐiều 2. Hai\n1. B.\n")
    assert [u.addr_part for u in parse_structure(t).units] == ["D1", "D1.K1", "D2", "D2.K1"]


def test_so_tu_chu():
    assert so_tu_chu("hai") == 2
    assert so_tu_chu("nhất") == 1
    assert so_tu_chu("mười") == 10
    assert so_tu_chu("mười lăm") == 15
    assert so_tu_chu("hai mươi") == 20
    assert so_tu_chu("2") == 2
    assert so_tu_chu("bảy mươi hai") == 72
    assert so_tu_chu("ngày") is None


def test_l8_trich_dan_khong_thanh_dieu():
    text = (
        "Nghị định số 1/2020/NĐ-CP\n"
        "Điều 1. Một\n1. Tổ chức thực hiện theo quy định tại\nĐiều 5.\n"
        "2. Không lập hồ sơ theo quy định tại\nĐiều 6 Nghị định này;\n"
        "Điều 2. Hai\n1. Khoản hai.\n"
    )
    r = parse_structure(text)
    assert [u.addr_part for u in r.units if u.level == "dieu"] == ["D1", "D2"]
    assert "Điều 5." in {u.addr_part: u for u in r.units}["D1.K1"].text


def test_l7_trung_dieu_khoan_diem_khong_crash():
    text = (
        "Nghị định số 1/2020/NĐ-CP\n"
        "Điều 1. A\n1. Một.\n1. Một lần nữa.\na) điểm a;\na) điểm a lần 2.\n"
        "Điều 2. B\n1. Hai.\n"
        "Điều 1. A lặp\n1. Một của Điều lặp.\n"
        "Điều 2. B lặp\n1. Hai lặp.\n"
    )
    r = parse_structure(text)
    p = _paths(r)
    assert len(p) == len(set(p))
    assert "D1.K1~2" in p and "D1.K1~2.Đa~2" in p
    assert "D1~2" in p and "D1~2.K1" in p and "D2~2.K1" in p


def test_l7_parse_loi_thi_chia_doan(monkeypatch):
    import soiluat.parse as P

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(P, "_parse_lines", boom)
    r = parse_structure("Điều 1. Một\n1. Khoản.\n")
    assert r.tier == 3 and r.units and all(u.level == "doan" for u in r.units)


def test_l10_so_trang_that():
    pages = [
        _pg(1, "Nghị định số 1/2020/NĐ-CP\nĐiều 1. Một\n1. Khoản một trang 1."),
        _pg(2, "2. Khoản hai sang trang 2.\nĐiều 2. Hai\n1. Khoản."),
        _pg(3, "Điều 3. Ba\n1. Khoản ba."),
    ]
    r = parse_pages(pages)
    by = {u.addr_part: (u.page_from, u.page_to) for u in r.units}
    assert by["D1"] == (1, 2)  # Điều phủ cả khoản con
    assert by["D1.K1"] == (1, 1)
    assert by["D1.K2"] == (2, 2)
    assert by["D2"] == (2, 2)
    assert by["D3.K1"] == (3, 3)


def test_l10_trang_cho_doan():
    words = " ".join(["chữ"] * 300)
    r = parse_pages([_pg(1, words), _pg(2, words)])
    assert r.tier == 3
    assert r.units[0].page_from == 1 and r.units[-1].page_to == 2


def test_ghi_chu_va_bang():
    pages = [
        _pg(
            1,
            "Nghị định số 1/2020/NĐ-CP\nĐiều 1. Một\n1. Theo Nghị định số 123/2024[^1].\n"
            "Điều 2. Mức phạt\n| Hành vi | Mức phạt |\n| Không niêm yết | 1.000.000 đồng |",
            notes=[
                Note("footnote", "Nghị định số 123/2024/NĐ-CP ngày 1/1/2024", "1"),
                Note("header", "Phòng pháp chế"),
            ],
        )
    ]
    r = parse_pages(pages)
    by = {u.addr_part: u for u in r.units}
    assert by["GC1"].level == "ghi_chu" and by["GC1"].parent_addr == "D1.K1"
    assert by["GC2"].parent_addr is None and by["GC2"].page_from == 1
    assert by["D2"].from_table and not by["D1"].from_table


D11 = """BỘ XÂY DỰNG
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Số: 912/2023/TT-BXD
Hà Nội, ngày 15 tháng 9 năm 2023
THÔNG TƯ
Điều 1. Phạm vi
1. Một.
Điều 2. Hiệu lực
1. Thông tư này có hiệu lực từ ngày 01 tháng 7 năm 2023.
Nơi nhận:
- Lưu: VT.
KT. BỘ TRƯỞNG
THỨ TRƯỞNG
BỘ XÂY DỰNG
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
Số: 88/2023/NĐ-CP
Hà Nội, ngày 5 tháng 7 năm 2019
THÔNG TƯ
Điều 1. Phạm vi
1. Hai.
Điều 2. Bảo quản
1. Doanh nghiệp phải bảo quản hồ sơ hải quan trong 5 năm."""


def test_l9_tach_hai_van_ban():
    segs = split_documents([_pg(1, D11)])
    assert len(segs) == 2
    assert segs[1][0].text.startswith("BỘ XÂY DỰNG")
    assert "THỨ TRƯỞNG" in segs[0][0].text
    r1, r2 = parse_pages(segs[0]), parse_pages(segs[1])
    assert r1.so_hieu == "912/2023/TT-BXD" and r2.so_hieu == "88/2023/NĐ-CP"
    assert "D2.K1" in _paths(r2)


def test_l9_khong_tach_khi_khong_chac():
    # Điều không về lại 1 → không tách
    t = D11.replace("Số: 88/2023/NĐ-CP\nHà Nội, ngày 5 tháng 7 năm 2019\nTHÔNG TƯ\nĐiều 1.",
                    "Số: 88/2023/NĐ-CP\nHà Nội, ngày 5 tháng 7 năm 2019\nTHÔNG TƯ\nĐiều 3.")
    assert len(split_documents([_pg(1, t)])) == 1
    # trích dẫn "Số: …" nhưng không có tên loại văn bản → không tách
    t2 = "Điều 1. A\n1. x.\nSố: 5/2020/NĐ-CP\nĐiều 1. B\n1. y."
    assert len(split_documents([_pg(1, t2)])) == 1


def test_l9_ghi_chu_theo_moc_khi_cat_trang():
    note = Note("footnote", "chú thích văn bản 2", "7")
    segs = split_documents([_pg(1, D11.replace("trong 5 năm.", "trong 5 năm[^7]."), notes=[note])])
    assert len(segs) == 2
    assert not segs[0][0].notes and segs[1][0].notes == [note]
