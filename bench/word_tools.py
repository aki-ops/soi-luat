"""Dùng Microsoft Word (COM) dựng file thử giống văn phòng thật.

python bench/word_tools.py OUT_DIR

Cần chạy gen_corpus.py trước. Ra:
  OUT_DIR/scale/pdf_text/*.pdf     Word -> PDF chữ
  OUT_DIR/scale/pdf_scan/*.pdf     PDF chữ -> ảnh (giả scan) -> PDF chỉ ảnh
  OUT_DIR/dirty/...                bộ file "bẩn" để soi lỗ hổng
  OUT_DIR/dirty_expect.json        cụm cần tìm thấy + file mong đợi
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageFilter, JpegImagePlugin  # noqa: F401  (PDF ảnh cần plugin JPEG)

sys.path.insert(0, str(Path(__file__).parent))
from gen_corpus import gen_doc  # noqa: E402

WD_PDF = 17
WD_DOC97 = 0
WD_DOCX = 16


def word():
    import win32com.client

    w = win32com.client.DispatchEx("Word.Application")
    w.Visible = False
    w.DisplayAlerts = 0
    return w


def to_pdf(w, src: Path, dst: Path) -> None:
    d = w.Documents.Open(str(src.resolve()), ReadOnly=True)
    try:
        d.ExportAsFixedFormat(str(dst.resolve()), WD_PDF)
    finally:
        d.Close(False)


def rasterize(pdf_in: Path, pdf_out: Path, dpi: int = 200, skew: float = 0.0, noise: bool = False,
              pages: set[int] | None = None) -> None:
    """Giả scan: render trang thành ảnh. pages=None: mọi trang; khác: chỉ các trang đó (PDF trộn)."""
    src = pdfium.PdfDocument(str(pdf_in))
    rng = random.Random(1)
    if pages is None:
        imgs = []
        for i in range(len(src)):
            imgs.append(_scan_img(src[i], dpi, skew, noise, rng))
        imgs[0].save(str(pdf_out), save_all=True, append_images=imgs[1:], resolution=dpi)
        src.close()
        return
    out = pdfium.PdfDocument.new()
    for i in range(len(src)):
        if i in pages:
            img = _scan_img(src[i], dpi, skew, noise, rng)
            tmp = pdf_out.with_suffix(f".p{i}.pdf")
            img.save(str(tmp), resolution=dpi)
            one = pdfium.PdfDocument(str(tmp))
            out.import_pages(one)
            one.close()
            tmp.unlink()
        else:
            out.import_pages(src, [i])
    out.save(str(pdf_out))
    out.close()
    src.close()


def _scan_img(page, dpi: int, skew: float, noise: bool, rng: random.Random) -> Image.Image:
    img = page.render(scale=dpi / 72).to_pil().convert("L")
    if skew:
        img = img.rotate(skew, expand=True, fillcolor=255)
    if noise:
        px = img.load()
        w, h = img.size
        for _ in range(w * h // 300):
            px[rng.randrange(w), rng.randrange(h)] = rng.choice((0, 90, 160))
        img = img.filter(ImageFilter.GaussianBlur(0.6))
    return img


def new_doc(w, lines: list[str]):
    d = w.Documents.Add()
    d.Content.Text = "\r".join(lines)
    return d


def para_find(d, start: str):
    for p in d.Paragraphs:
        if start in p.Range.Text:
            return p
    raise KeyError(start)


def base_lines(seed: int, extra_khoan: str, at_dieu: int = 5) -> tuple[list[str], dict]:
    doc = gen_doc(random.Random(seed), 900 + seed)
    lines = doc["lines"]
    # chèn khoản riêng (cụm duy nhất để tra) vào cuối Điều at_dieu
    start = next(i for i, ln in enumerate(lines) if ln.startswith(f"Điều {at_dieu}."))
    end = next(i for i, ln in enumerate(lines) if ln.startswith(f"Điều {at_dieu + 1}."))
    while lines[end - 1].startswith("Chương") or lines[end - 1].isupper():
        end -= 1
    k = 1 + sum(1 for ln in lines[start:end] if ln.split(".", 1)[0].isdigit())
    lines.insert(end, f"{k}. {extra_khoan}")
    return lines, doc


def build_dirty(w, out: Path) -> list[dict]:
    dd = out / "dirty"
    dd.mkdir(parents=True, exist_ok=True)
    exp: list[dict] = []

    def E(file, query, want, note):
        exp.append({"file": file, "query": query, "want": want, "note": note})

    # d01: Word tự đánh số "Điều %1." (list numbering, không gõ tay)
    lines, _ = base_lines(1, "Doanh nghiệp phải nộp báo cáo giám sát an toàn thực phẩm hằng quý.")
    d = new_doc(w, lines)
    lt = d.ListTemplates.Add(True)
    fmts = [("Điều %1.", 0), ("%2.", 0), ("%3)", 4)]
    for lvl, (f, style) in enumerate(fmts, start=1):
        L = lt.ListLevels(lvl)
        L.NumberFormat = f
        L.NumberStyle = style
    for p in d.Paragraphs:
        t = p.Range.Text.strip()
        lvl, cut = 0, 0
        if t.startswith("Điều ") and ". " in t[:10]:
            lvl, cut = 1, t.index(". ") + 2
        elif t[:3].rstrip(". ").isdigit() and ". " in t[:4]:
            lvl, cut = 2, t.index(". ") + 2
        elif len(t) > 2 and t[1] == ")" and t[0].isalpha():
            lvl, cut = 3, 3
        if lvl:
            r = p.Range
            r.SetRange(r.Start, r.Start + cut)
            r.Delete()
            p.Range.ListFormat.ApplyListTemplate(lt, True)
            p.Range.ListFormat.ListLevelNumber = lvl
    d.SaveAs2(str((dd / "d01_word_tu_dong_danh_so.docx").resolve()), WD_DOCX)
    d.Close(False)
    E("d01_word_tu_dong_danh_so.docx", "nộp báo cáo giám sát an toàn thực phẩm", "Điều 5",
      "Word tự đánh số Điều/khoản/điểm (không gõ tay)")

    # d02: nội dung chỉ nằm trong bảng
    lines, _ = base_lines(2, "Mức phạt đối với các hành vi vi phạm quy định tại bảng dưới đây:")
    d = new_doc(w, lines)
    p = para_find(d, "Mức phạt đối với các hành vi")
    p.Range.InsertParagraphAfter()
    t = d.Tables.Add(p.Next().Range, 4, 3)
    rows = [("STT", "Hành vi vi phạm", "Mức phạt"),
            ("1", "Không niêm yết giá dịch vụ cầm đồ", "Phạt tiền từ 3.000.000 đồng đến 5.000.000 đồng"),
            ("2", "Không lập sổ theo dõi tài sản cầm cố", "Phạt tiền từ 5.000.000 đồng đến 10.000.000 đồng"),
            ("3", "Cho vay cầm đồ vượt lãi suất tối đa", "Phạt tiền từ 20.000.000 đồng đến 40.000.000 đồng")]
    for i, row in enumerate(rows, start=1):
        for j, v in enumerate(row, start=1):
            t.Cell(i, j).Range.Text = v
    d.SaveAs2(str((dd / "d02_bang_muc_phat.docx").resolve()), WD_DOCX)
    d.ExportAsFixedFormat(str((dd / "d08_pdf_co_bang.pdf").resolve()), WD_PDF)
    d.Close(False)
    E("d02_bang_muc_phat.docx", "niêm yết giá dịch vụ cầm đồ", "bảng", "hành vi + mức phạt chỉ có trong bảng Word")
    E("d08_pdf_co_bang.pdf", "lập sổ theo dõi tài sản cầm cố", "bảng", "bảng trong PDF chữ")

    # d03: chú thích chân trang, comment, header/footer, text box
    lines, _ = base_lines(3, "Tổ chức phải công khai quy trình xử lý khiếu nại của khách hàng.")
    d = new_doc(w, lines)
    r = para_find(d, "Điều 4.").Range.Duplicate
    r.MoveEnd(1, -1)
    r.Collapse(0)  # footnote vào range chưa collapse sẽ thay mất chữ
    fn = d.Footnotes.Add(r)  # tham số Text qua pywin32 bị bỏ qua -> gán sau
    fn.Range.Text = "Điều này được sửa đổi, bổ sung bởi khoản 4 Điều 1 Nghị định số 123/2024/NĐ-CP."
    p2 = para_find(d, "Điều 6.")
    d.Comments.Add(p2.Range, "Cần đối chiếu với Thông tư 45 về thời hạn lưu trữ hồ sơ.")
    d.Sections(1).Headers(1).Range.Text = "BẢN LƯU NỘI BỘ - PHÒNG PHÁP CHẾ"
    d.Sections(1).Footers(1).Range.Text = "Ghi chú chân trang: văn bản đã được rà soát ngày 15/3/2025"
    tb = d.Shapes.AddTextbox(1, 380, 60, 180, 60)
    tb.TextFrame.TextRange.Text = "Ghi chú: áp dụng riêng cho doanh nghiệp nhỏ và vừa"
    d.SaveAs2(str((dd / "d03_chu_thich_comment.docx").resolve()), WD_DOCX)
    d.ExportAsFixedFormat(str((dd / "d10_pdf_co_chu_thich.pdf").resolve()), WD_PDF)
    d.Close(False)
    E("d03_chu_thich_comment.docx", "Nghị định số 123/2024", "footnote", "chú thích chân trang (footnote)")
    E("d03_chu_thich_comment.docx", "đối chiếu với Thông tư 45", "comment", "comment của người soạn")
    E("d03_chu_thich_comment.docx", "doanh nghiệp nhỏ và vừa", "textbox", "ghi chú trong text box")
    E("d03_chu_thich_comment.docx", "phòng pháp chế", "header", "header")
    E("d10_pdf_co_chu_thich.pdf", "Nghị định số 123/2024", "footnote", "footnote trong PDF chữ")
    E("d03_chu_thich_comment.docx", "công khai quy trình xử lý khiếu nại", "Điều 5", "nội dung thường (đối chứng)")

    # d04: Word 97-2003 .doc
    lines, _ = base_lines(4, "Doanh nghiệp phải đăng ký kinh doanh dịch vụ lữ hành quốc tế.")
    d = new_doc(w, lines)
    d.SaveAs2(str((dd / "d04_word_cu.doc").resolve()), WD_DOC97)
    d.Close(False)
    E("d04_word_cu.doc", "đăng ký kinh doanh dịch vụ lữ hành", "Điều 5", "file .doc đời cũ")

    # d05/d06/d07: PDF scan sạch / nghiêng + nhiễu / trộn
    for name, seed, phrase, kw in [
        ("d05_pdf_scan_sach", 5, "Doanh nghiệp phải lắp đặt camera giám sát tại kho hàng.", dict(dpi=200)),
        ("d06_pdf_scan_nghieng_nhieu", 6, "Cơ sở phải niêm phong mẫu lưu trong vòng 24 giờ.",
         dict(dpi=150, skew=1.5, noise=True)),
        ("d07_pdf_tron", 7, "Đơn vị phải bố trí cán bộ đầu mối tiếp nhận phản ánh.", dict(dpi=200, pages={1})),
    ]:
        lines, _ = base_lines(seed, phrase)
        d = new_doc(w, lines)
        tmp = dd / f"{name}.src.pdf"
        d.ExportAsFixedFormat(str(tmp.resolve()), WD_PDF)
        d.Close(False)
        rasterize(tmp, dd / f"{name}.pdf", **kw)
        tmp.unlink()
        q = phrase.split(" phải ", 1)[1].rstrip(".")
        E(f"{name}.pdf", q, "Điều 5", {"d05_pdf_scan_sach": "PDF scan sạch 200dpi",
                                         "d06_pdf_scan_nghieng_nhieu": "PDF scan 150dpi, nghiêng 1.5°, nhiễu",
                                         "d07_pdf_tron": "PDF trộn: trang 2 là ảnh scan"}[name])

    # d09: định dạng lệch chuẩn
    lines = [
        "BỘ CÔNG THƯƠNG", "Số: 77/2022/TT-BCT", "THÔNG TƯ", "Quy định về quản lý nhân viên bán hàng",
        "Chương I", "QUY ĐỊNH CHUNG", "Mục 1. PHẠM VI",
        "ĐIỀU 1: PHẠM VI ĐIỀU CHỈNH",
        "1) Thông tư này quy định về quản lý nhân viên bán hàng tại siêu thị.",
        "Điều thứ hai. Nghĩa vụ của nhân viên",
        "1) Nhân viên bán hàng phải đeo thẻ nhân viên khi làm việc",
        "tại quầy và phải mặc đồng phục theo quy định của",
        "doanh nghiệp.",
        "a. Thẻ nhân viên phải ghi rõ họ tên và mã số;",
        "b. Thẻ phải còn hiệu lực.",
        "Điều 3 . Hành vi bị cấm",
        "1/ Nghiêm cấm nhân viên nhận tiền boa của khách hàng.",
        "Điều 4.Hiệu lực",
        "1. Thông tư này có hiệu lực từ ngày 01/01/2023.",
    ]
    d = new_doc(w, lines)
    d.SaveAs2(str((dd / "d09_dinh_dang_le.docx").resolve()), WD_DOCX)
    d.Close(False)
    E("d09_dinh_dang_le.docx", "đeo thẻ nhân viên", "Điều 2", "'Điều thứ hai', khoản '1)', điểm 'a.', câu bị ngắt dòng")
    E("d09_dinh_dang_le.docx", "nhận tiền boa", "Điều 3", "'Điều 3 .' có dấu cách, khoản '1/'")

    # d11: hai văn bản trong một file
    a_lines, _ = base_lines(11, "Doanh nghiệp phải cập nhật danh mục hàng hóa xuất khẩu.")
    b_lines, _ = base_lines(12, "Doanh nghiệp phải bảo quản hồ sơ hải quan trong 5 năm.")
    b_lines = [("Số: 88/2023/NĐ-CP" if ln.startswith("Số: ") else ln) for ln in b_lines]
    d = new_doc(w, a_lines + b_lines)
    d.SaveAs2(str((dd / "d11_hai_van_ban.docx").resolve()), WD_DOCX)
    d.Close(False)
    E("d11_hai_van_ban.docx", "88/2023/NĐ-CP", "so_hieu 88/2023/NĐ-CP", "văn bản thứ 2 ghép trong cùng file")
    E("d11_hai_van_ban.docx", "bảo quản hồ sơ hải quan", "Điều 5 (văn bản 2)", "Điều trùng số giữa 2 văn bản")

    # d12: công văn không có Điều
    lines = ["BỘ TÀI CHÍNH", "Số: 1234/BTC-TCT", "V/v hướng dẫn tạm dừng tiếp nhận hồ sơ",
             "Kính gửi: Cục Thuế các tỉnh, thành phố.",
             "Bộ Tài chính hướng dẫn tạm dừng tiếp nhận hồ sơ trực tuyến từ ngày 01/10/2025 để nâng cấp hệ thống.",
             "Người nộp thuế phải nộp hồ sơ giấy tại bộ phận một cửa trong thời gian tạm dừng.",
             "Trong quá trình thực hiện, nếu có vướng mắc đề nghị phản ánh về Bộ Tài chính."]
    d = new_doc(w, lines)
    d.SaveAs2(str((dd / "d12_cong_van.docx").resolve()), WD_DOCX)
    d.Close(False)
    E("d12_cong_van.docx", "tạm dừng tiếp nhận hồ sơ trực tuyến", "đoạn", "công văn không chia Điều")

    # trùng tên file ở hai thư mục
    for sub, phrase in (("a", "Đơn vị phải kiểm định thang máy định kỳ."), ("b", "Đơn vị phải kiểm định nồi hơi định kỳ.")):
        (dd / "trung_ten" / sub).mkdir(parents=True, exist_ok=True)
        lines, _ = base_lines(20 + ord(sub), phrase)
        d = new_doc(w, lines)
        d.SaveAs2(str((dd / "trung_ten" / sub / "quy-dinh.docx").resolve()), WD_DOCX)
        d.Close(False)
    E("trung_ten/a/quy-dinh.docx", "kiểm định thang máy", "Điều 5", "trùng tên file (thư mục a)")
    E("trung_ten/b/quy-dinh.docx", "kiểm định nồi hơi", "Điều 5", "trùng tên file (thư mục b)")

    # bản sao y hệt
    shutil.copy(dd / "d02_bang_muc_phat.docx", dd / "d13_ban_sao_d02.docx")

    # ảnh chụp trang (JPG) + phụ lục Excel
    lines, _ = base_lines(14, "Cơ sở phải lưu giữ sổ nhật ký vận hành lò hơi.")
    d = new_doc(w, lines)
    tmp = dd / "d15.src.pdf"
    d.ExportAsFixedFormat(str(tmp.resolve()), WD_PDF)
    d.Close(False)
    src = pdfium.PdfDocument(str(tmp))
    src[1].render(scale=200 / 72).to_pil().convert("L").save(str(dd / "d15_anh_chup_trang.jpg"), quality=80)
    src.close()
    tmp.unlink()
    E("d15_anh_chup_trang.jpg", "sổ nhật ký vận hành lò hơi", "Điều 5", "ảnh chụp trang (JPG)")
    try:
        import win32com.client

        x = win32com.client.DispatchEx("Excel.Application")
        x.Visible = False
        x.DisplayAlerts = False
        wb = x.Workbooks.Add()
        ws = wb.Worksheets(1)
        for i, row in enumerate([("STT", "Nội dung", "Mức thu"), (1, "Phí thẩm định hồ sơ cấp phép khai thác khoáng sản", "5.000.000"),
                                 (2, "Phí thẩm định báo cáo đánh giá tác động", "12.000.000")], start=1):
            for j, v in enumerate(row, start=1):
                ws.Cells(i, j).Value = v
        wb.SaveAs(str((dd / "d14_phu_luc.xlsx").resolve()), 51)
        wb.Close(False)
        x.Quit()
        E("d14_phu_luc.xlsx", "phí thẩm định hồ sơ cấp phép khai thác khoáng sản", "dòng 2", "phụ lục Excel")
    except Exception as e:  # Excel không có thì bỏ
        print("Bỏ Excel:", e)

    # PDF lớn ~150 trang (đo RAM/thời gian)
    big: list[str] = []
    for s in range(30, 42):
        ls = gen_doc(random.Random(s), 950 + s)["lines"]
        big += ls if not big else ls[9:-5]
    d = new_doc(w, big)
    d.ExportAsFixedFormat(str((dd / "d16_pdf_lon.pdf").resolve()), WD_PDF)
    d.Close(False)
    return exp


def main() -> None:
    out = Path(sys.argv[1])
    w = word()
    try:
        src = out / "scale" / "_pdf_src"
        man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        (out / "scale" / "pdf_text").mkdir(parents=True, exist_ok=True)
        (out / "scale" / "pdf_scan").mkdir(parents=True, exist_ok=True)
        for m in man:
            if m["fmt"] == "docx" or (out / "scale" / m["fmt"] / f"{m['file']}.pdf").exists():
                continue
            s = src / f"{m['file']}.docx"
            if m["fmt"] == "pdf_text":
                to_pdf(w, s, out / "scale" / "pdf_text" / f"{m['file']}.pdf")
            else:
                tmp = out / "scale" / "pdf_scan" / f"{m['file']}.src.pdf"
                to_pdf(w, s, tmp)
                rasterize(tmp, out / "scale" / "pdf_scan" / f"{m['file']}.pdf", dpi=200)
                tmp.unlink()
        print("scale PDF xong")
        exp = build_dirty(w, out)
        (out / "dirty_expect.json").write_text(json.dumps(exp, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"dirty: {len(exp)} kỳ vọng")
    finally:
        w.Quit()


if __name__ == "__main__":
    main()
