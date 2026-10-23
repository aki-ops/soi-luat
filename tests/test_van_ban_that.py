"""Lỗi gặp khi nạp 21 văn bản thật (bench/van-ban-that): ngoặc OCR lạc, bảng giả trong PDF, dòng số hiệu."""
from soiluat.extract import _real_table
from soiluat.parse import SO_LINE, parse_structure


def _dieu(text):
    return [u.addr_part for u in parse_structure(text).units if u.level == "dieu"]


LUAT = (
    "QUỐC HỘI\n"
    "Luật số: 18/2026/QH16\n"
    "LUẬT\n"
    "Căn cứ Nghị quyết số 203/2025/QH15;\n"
    "Điều 1. Phạm vi điều chỉnh\n"
    "Luật này quy định quyền {stray}hạn của chính quyền.\n"
    "Điều 2. Đối tượng áp dụng\n"
    "1. Cơ quan nhà nước.\n"
    "Điều 3. Hiệu lực thi hành\n"
    "Luật này có hiệu lực từ ngày 01 tháng 10 năm 2026.\n"
)


def test_stray_ocr_quote_mid_sentence_keeps_later_dieu():
    for stray in ("“", '"', "”"):
        assert _dieu(LUAT.format(stray=stray)) == ["D1", "D2", "D3"], stray


def test_stray_quote_inside_word_and_heading_line():
    t = LUAT.format(stray="").replace("quyền hạn", "quyền h“ạn").replace("Điều 2. Đối tượng áp dụng",
                                                                          "Điều 2. Đối tượng“áp dụng")
    assert _dieu(t) == ["D1", "D2", "D3"]


def test_stray_quote_in_preamble_before_dieu_1():
    t = LUAT.format(stray="").replace("Luật số: 18/2026/QH16", 'Luật số: 18/2026/QH16 "DỌc lập')
    assert _dieu(t) == ["D1", "D2", "D3"]


SUA_DOI = (
    "Luật số: 23/2026/QH16\n"
    "Điều 1. Sửa đổi, bổ sung một số điều\n"
    "1. Sửa đổi Điều 5 như sau:\n"
    "“Điều 5. Báo cáo định kỳ\n"
    "1. Cơ quan phải báo cáo hằng năm.\n"
    "2. Bổ sung điểm e vào khoản 2 Điều 6 như sau:\n"
    "“e) Đại lý quản lý tài sản bảo đảm\n"
    "Điều 2. Hiệu lực thi hành\n"
    "1. Luật này có hiệu lực từ ngày 01 tháng 12 năm 2026.\n"
)


def test_quoted_article_still_protected_but_unclosed_quote_recovers_at_next_own_dieu():
    # “Điều 5. là trích dẫn; ngoặc đóng sau “e) bị OCR làm mất: "Điều 2." đúng thứ tự vẫn là Điều của văn bản
    assert _dieu(SUA_DOI) == ["D1", "D2"]


def test_quote_after_colon_on_same_line_opens_block():
    t = ("Điều 1. Sửa đổi\n1. Sửa đổi Điều 7 như sau: “Điều 7. Thanh tra\n"
         "Điều 8. Kiểm tra định kỳ\nCơ quan kiểm tra hằng năm.”\nĐiều 2. Hiệu lực\n1. Có hiệu lực.\n")
    assert _dieu(t) == ["D1", "D2"]


def test_so_line_accepts_luat_so_and_space_before_slash():
    assert parse_structure(LUAT.format(stray="")).so_hieu == "18/2026/QH16"
    t = "CHÍNH PHỦ\nSố: 388 /2026/NĐ-CP\nNGHỊ ĐỊNH\nCăn cứ Luật số 97/2025/QH15;\nĐiều 1. A\n1. x.\n"
    assert parse_structure(t).so_hieu == "388/2026/NĐ-CP"
    assert not SO_LINE.match("số 40/2019/QH14.")  # dòng căn cứ bị ngắt, không phải dòng số hiệu


def test_real_table_rejects_shaded_boxes_and_word_grids():
    assert not _real_table([["Điều 2. Đối tượng áp dụng"], ["Nghị định này áp dụng đối với"], [None]])
    assert not _real_table([["Khuyến khích cơ quan", None], ["tối ưu hóa khả năng", ""], ["tuệ nhân tạo.", None]])
    grid = [["là", "t", "ập", "hợp"] + [None] * 10 + ["thủ", "t", "ục"], ["hành", "chính", "được"] + [None] * 14]
    assert not _real_table(grid)
    assert _real_table([["STT", "Công việc"], ["1", "Chế tạo, lắp ráp"], ["2", "Trực tiếp sản xuất"]])


def test_lost_dieu_heading_does_not_drop_whole_doc_to_paragraphs():
    # mộc đè tiêu đề Điều 2: khoản của nó nối vào Điều 1 (đánh lại từ 1), văn bản vẫn tách theo Điều
    t = ("Luật số: 19/2026/QH16\nĐiều 1. Sửa đổi, bổ sung một số điều\n1. Sửa đổi Điều 5.\n2. Sửa đổi Điều 7.\n"
         "Điều LỀJeuủoan fin.Ỉìanh\n1. Luật này có hiệu lực từ ngày 01 tháng 3 năm 2027.\n2. Sửa đổi khoản 4 Điều 40.\n"
         "Điều 3. Điều khoản chuyển tiếp\n1. Hồ sơ đã nộp tiếp tục giải quyết.\n2. Chứng chỉ đã cấp còn giá trị.\n")
    r = parse_structure(t)
    assert [u.addr_part for u in r.units if u.level == "dieu"] == ["D1", "D3"] and r.tier < 3


def test_only_ids_filter_keeps_results_and_order(tmp_path, monkeypatch):
    from soiluat.db import connect, init_schema
    from soiluat.ingest import ingest_path
    from soiluat.search import scored_units

    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    f = tmp_path / "a.txt"
    f.write_text("Số: 1/2024/NĐ-CP\nNGHỊ ĐỊNH\nĐiều 1. Báo cáo định kỳ\n1. Báo cáo gửi hằng năm.\n"
                 "Điều 2. Báo cáo đột xuất\n1. Báo cáo ngay khi có sự cố.\nĐiều 3. Hiệu lực\n1. Có hiệu lực từ ngày ký.\n",
                 encoding="utf-8")
    conn = connect(tmp_path / "soiluat.db")
    init_schema(conn)
    ingest_path(conn, f, tmp_path)
    ids = [r[0] for r in conn.execute("SELECT id FROM units ORDER BY id")]
    allr = scored_units(conn, '"bao" OR "cao"', branch="fold")
    sub = ids[: len(ids) // 2]
    got = scored_units(conn, '"bao" OR "cao"', branch="fold", only_ids=sub)
    assert got and [i for i, _ in got] == [i for i, _ in allr if i in set(sub)]


def test_quoted_block_with_consecutive_dieu_is_not_split_by_recovery():
    # luật sửa Điều 1 và Điều 2 của luật gốc: "Điều 2." trong khối trích dẫn không phải Điều 2 của văn bản
    t = ("Điều 1. Sửa đổi\n1. Sửa đổi Điều 1 và Điều 2 như sau:\n“Điều 1. Phạm vi\nNội dung A.\n"
         "Điều 2. Đối tượng\nNội dung B.”\nĐiều 2. Hiệu lực\n1. Có hiệu lực.\n")
    assert _dieu(t) == ["D1", "D2"]


def test_dieu_heading_with_ocr_damage():
    from soiluat.parse import _dieu_match

    assert _dieu_match("ˆ Điều 21. Tên Điều")[:2] == ("21", "Tên Điều")  # vết mực đầu dòng
    assert _dieu_match("‹ Điều 60. Tên")[0] == "60"
    assert _dieu_match("ĂĐỉều 50. Hành vi vi phạm")[0] == "50"
    assert _dieu_match("Đ1eu 12. Quy định")[0] == "12" and _dieu_match("Đlgu 20. Quy định")[0] == "20"
    assert _dieu_match("| Điều 15. Tên |")[:2] == ("15", "Tên")
    assert _dieu_match("Du 5. abc") is None and _dieu_match("“Điều 5. Tên") is None  # không nhận nhầm, trích dẫn vẫn là trích dẫn


def test_dieu_number_misread_as_letter_is_inferred_from_previous():
    t = "Điều 33. A\n1. x.\nĐiều M Thẩm quyền về đầu tư\n1. y.\nĐiều 35. C\n1. z.\n"
    assert _dieu(t) == ["D33", "D34", "D35"]
    # "Điều X Nghị định này…" là trích dẫn, không phải tiêu đề
    assert _dieu("Điều 1. A\n1. x.\nĐiều B Nghị định này quy định rõ.\n") == ["D1"]


def test_co_quan_from_header_only():
    from soiluat.sohieu import infer_co_quan

    assert infer_co_quan("BỘ TÀI CHÍNH CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nSố: 156/2026/TT-BTC") == "BỘ TÀI CHÍNH"
    assert infer_co_quan("QUÓỐC HỘI CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nLuật số: 22/2026/QH16") == "QUỐC HỘI"
    assert infer_co_quan("QUỐC HỘI CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nLuật số: 22/2026/QH16") == "QUỐC HỘI"
    assert infer_co_quan("| CHÍNH | PHỦ __________ | CỘNG HÒA | XÃ HỘI |\nSố: 385/2026/NĐ-CP") == "CHÍNH PHỦ"
    assert infer_co_quan("THỦ TƯỚNG CHÍNH PHỦ . CỘNG HÒA XÃ HỘI\nSố: 48/2026/QĐ-TTg") == "THỦ TƯỚNG CHÍNH PHỦ"
    assert infer_co_quan("| BỘ NỘI VỤ | CỘNG HÒA |\nSố: 1/2026/TT-BNV") == "BỘ NỘI VỤ"
    assert infer_co_quan("LUẬT\nĐiều 1. Chính phủ quy định chi tiết; Bộ trưởng Bộ Tài chính hướng dẫn") is None
    assert infer_co_quan("CỘNG HÒA\nCHÍNH PHỦ\nHà Nội") == "CHÍNH PHỦ"


def test_ngay_ban_hanh_of_luat_and_ngay_hieu_luc_with_ocr_noise():
    from soiluat.sohieu import find_ngay_ban_hanh, find_ngay_hieu_luc

    luat = ("Điều 3. Hiệu lực\n1. Luật này có hiệu lực thi hành từ ngày 01 tháng 3 năm 2027.\n"
            "Luật này được Quốc hội nước Cộng hòa xã hội chủ nghĩa Việt Nam khóa XVI,\n"
            "Kỳ họp thứ Nhất thông qua ngày 24 tháng 8 năm 2026.\n")
    assert find_ngay_ban_hanh(luat) == "2026-08-24" and find_ngay_hieu_luc(luat) == "2027-03-01"
    # câu kết nằm trước phụ lục dài; "Quốc hội" bị OCR hỏng nhưng còn "Kỳ họp"
    assert find_ngay_ban_hanh(luat.replace("Quốc hội", "Quôrc hội") + "Phụ lục\n" * 300) == "2026-08-24"
    # "Căn cứ Hiến pháp … được Quốc hội thông qua ngày …" ở đầu văn bản không phải ngày ban hành
    assert find_ngay_ban_hanh("Căn cứ Hiến pháp đã được Quốc hội thông qua ngày 28 tháng 11 năm 2013;\n" + "x\n" * 60) is None
    for noisy in ("có hiệu lực thi bành kể từ ngày 01 tháng 12 năm 2026", "có hiệu lực thị hành từ ngày 01 tháng 12 năm 2026",
                  "có hiệu lực thi hành kê từ ngày 01/12/2026"):
        assert find_ngay_hieu_luc("Thông tư này " + noisy) == "2026-12-01", noisy
    # ưu tiên câu "<loại> này có hiệu lực" hơn đoạn trích của luật khác
    assert find_ngay_hieu_luc("Điều 5. Luật khác có hiệu lực từ ngày 01 tháng 1 năm 2029.\nLuật này có hiệu lực từ ngày 01 tháng 3 năm 2027.") == "2027-03-01"
