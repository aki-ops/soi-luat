"""Sinh 10 file khác định dạng, KHÔNG theo cấu trúc Điều/khoản, để thử khả năng đọc + tìm.

python bench/stress10/gen.py            # ra bench/stress10/files/ và expected.json
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import fitz
from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "files"
ARIAL = r"C:\Windows\Fonts\arial.ttf"
EXP: list[dict] = []


def E(file: str, marker: str, *queries: str) -> None:
    """marker: cụm (đã chuẩn hoá chữ thường) phải xuất hiện trong thẻ top 10 của mỗi truy vấn."""
    for q in queries:
        EXP.append({"file": file, "q": q, "marker": marker})


def para(d, text, bold=False, size=None, align=None):
    p = d.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    if size:
        r.font.size = Pt(size)
    if align == "c":
        p.alignment = 1
    return p


def s01():
    d = Document()
    para(d, "UBND PHƯỜNG BÌNH AN", True, align="c")
    para(d, "THÔNG BÁO", True, 14, "c")
    para(d, "Về việc gia hạn thời gian tiếp nhận hồ sơ cấp đổi giấy phép kinh doanh hộ cá nhân", True, align="c")
    para(d, "Kính gửi: Các hộ kinh doanh trên địa bàn phường.")
    para(d, "Thực hiện chủ trương của Thành phố về chuẩn hóa dữ liệu kinh doanh, Ủy ban nhân dân phường thông báo như sau:")
    para(d, "Hồ sơ cấp đổi giấy phép kinh doanh hộ cá nhân được nhận đến hết ngày 15 tháng 11 năm 2026 tại Bộ phận một cửa, "
            "giờ hành chính các ngày trong tuần, không nhận hồ sơ qua tin nhắn.")
    para(d, "Hộ nào quá hạn nói trên sẽ phải làm thủ tục đăng ký mới và không được giữ mã số cũ.")
    para(d, "Mọi thắc mắc xin liên hệ cán bộ phụ trách theo số điện thoại niêm yết tại trụ sở.")
    para(d, "Trân trọng thông báo./.")
    d.save(OUT / "s01_thong_bao_van_xuoi.docx")
    E("s01", "15 tháng 11 năm 2026", "hạn nhận hồ sơ cấp đổi giấy phép kinh doanh hộ cá nhân",
      "Hộ kinh doanh nộp hồ sơ đổi giấy phép đến ngày nào?")


def s02():
    d = Document()
    para(d, "QUY CHẾ LÀM VIỆC NỘI BỘ CÔNG TY", True, 14, "c")
    para(d, "Phần I - NGUYÊN TẮC CHUNG", True)
    para(d, "Quy tắc 1. Mọi nhân viên có trách nhiệm chấp hành giờ làm việc đã đăng ký.")
    para(d, "Quy tắc 2. Nhân viên được nghỉ bù tối đa 3 ngày liên tục sau đợt công tác dài ngày, phải báo trước trưởng bộ phận.")
    para(d, "Phần II - THANH TOÁN CHI PHÍ", True)
    para(d, "Quy tắc 3. Chứng từ công tác phí phải nộp trong vòng 10 ngày kể từ ngày kết thúc chuyến đi.")
    para(d, "Mục 3.1 Chứng từ hợp lệ gồm hóa đơn, vé và giấy đề nghị thanh toán.")
    para(d, "Mục 3.2 Chứng từ thiếu chữ ký bị trả lại, không được tính vào kỳ lương.")
    d.save(OUT / "s02_quy_che_quy_tac_phan.docx")
    E("s02", "nghỉ bù tối đa 3 ngày", "nghỉ bù sau công tác dài ngày", "Đi công tác dài ngày về được nghỉ bù mấy ngày?")


def s03():
    txt = """BIEN BAN HOP BAN CHI DAO DU AN KHU DO THI MOI
Thoi gian: 8 gio 30 ngay 12/10/2026

Noi dung cuoc hop:
- Dong chi Truong ban thong qua tien do giai phong mat bang dat 82%.
- Cac y kien thao luan:
   + So Tai nguyen de nghi bo sung kinh phi do dac.
   + UBND xa de xuat tang cuong tuyen truyen.
* Ket luan:
   Giao So Xay dung hoan thanh ra soat quy hoach khu tai dinh cu truoc ngay 30/12/2026.
   Giao Ban boi thuong bao cao tien do moi tuan vao thu Sau.
"""
    (OUT / "s03_bien_ban_hop_khong_dau.txt").write_text(txt, encoding="utf-8")
    E("s03", "ra soat quy hoach khu tai dinh cu", "rà soát quy hoạch khu tái định cư", "Sở Xây dựng phải rà soát quy hoạch tái định cư trước ngày nào?")


def s04():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_font(fontname="vn", fontfile=ARIAL)
    page.insert_text((200, 50), "HỎI - ĐÁP VỀ CHÍNH SÁCH THUẾ", fontname="vn", fontsize=14)
    left = ["Câu 1: Ai phải nộp lệ phí môn bài?", "Trả lời: Tổ chức, cá nhân kinh doanh theo quy định.",
            "Câu 2: Doanh nghiệp siêu nhỏ có được giảm", "lệ phí môn bài không?",
            "Trả lời: Doanh nghiệp siêu nhỏ được giảm 50%", "lệ phí môn bài năm đầu thành lập."]
    right = ["Câu 3: Thời hạn nộp tờ khai quyết toán?", "Trả lời: Chậm nhất ngày cuối cùng của tháng",
             "thứ ba kể từ ngày kết thúc năm.", "Câu 4: Nộp muộn có bị tính lãi không?",
             "Trả lời: Có, tính lãi chậm nộp theo ngày."]
    for i, t in enumerate(left):
        page.insert_text((50, 100 + 22 * i), t, fontname="vn", fontsize=10)
    for i, t in enumerate(right):
        page.insert_text((320, 100 + 22 * i), t, fontname="vn", fontsize=10)
    doc.save(OUT / "s04_hoi_dap_hai_cot.pdf")
    E("s04", "giảm 50%", "lệ phí môn bài doanh nghiệp siêu nhỏ giảm", "Doanh nghiệp siêu nhỏ có được giảm lệ phí môn bài không?")


def s05():
    wb = Workbook()
    ws = wb.active
    ws.title = "Biểu mức phạt"
    ws.append(["Hành vi vi phạm", "Mức tối thiểu (đồng)", "Mức tối đa (đồng)", "Căn cứ"])
    ws.append(["Không niêm yết giá hàng hóa theo quy định", 2000000, 5000000, "Biểu 1"])
    ws.append(["Bán hàng hóa không có hóa đơn", 3000000, 8000000, "Biểu 1"])
    ws.append(["Cung cấp thông tin sai sự thật cho cơ quan quản lý", 5000000, 10000000, "Biểu 2"])
    ws2 = wb.create_sheet("Ghi chú")
    ws2.append(["Mức phạt đối với tổ chức gấp đôi mức phạt đối với cá nhân."])
    wb.save(OUT / "s05_bang_muc_phat.xlsx")
    E("s05", "không niêm yết giá hàng hóa", "phạt không niêm yết giá hàng hóa", "Không niêm yết giá bị phạt bao nhiêu?")


def s06():
    d = Document()
    para(d, "QUY TRÌNH TIẾP NHẬN HỒ SƠ MỘT CỬA", True, 14, "c")
    para(d, "Bước 1: Công dân nộp hồ sơ tại quầy tiếp nhận.")
    para(d, "Bước 2: Cán bộ in số thứ tự và hướng dẫn điền biểu mẫu.")
    para(d, "Bước 3: Cán bộ tiếp nhận kiểm tra hồ sơ trong 02 giờ làm việc và cấp phiếu hẹn trả kết quả.")
    t = d.add_table(rows=3, cols=3)
    t.style = "Table Grid"
    for r, row in enumerate([["Bước", "Người thực hiện", "Thời hạn"], ["Tiếp nhận", "Cán bộ một cửa", "02 giờ"],
                             ["Thẩm định", "Chuyên viên", "05 ngày làm việc"]]):
        for c, v in enumerate(row):
            t.cell(r, c).text = v
    para(d, "Lưu ý: hồ sơ thiếu thành phần được trả lại ngay trong ngày, không giữ lại.")
    para(d, "Bước 4: Chuyên viên thẩm định trong thời hạn 05 ngày làm việc.")
    para(d, "Bước 5: Lãnh đạo ký duyệt và trả kết quả cho công dân.")
    d.save(OUT / "s06_quy_trinh_buoc_bang.docx")
    E("s06", "02 giờ làm việc", "kiểm tra hồ sơ trong 02 giờ làm việc", "Cán bộ một cửa kiểm tra hồ sơ trong bao lâu?")


def s07():
    lines = ["CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "Độc lập - Tự do - Hạnh phúc", "", "ĐƠN ĐỀ NGHỊ",
             "Kính gửi: Chi cục Thuế khu vực 5", "",
             "Tôi tên là Nguyễn Văn Hòa, chủ hộ kinh doanh cửa hàng vật liệu xây dựng.",
             "Do ảnh hưởng của bão số 9, cửa hàng bị ngập và hư hỏng nặng.",
             "Tôi làm đơn này đề nghị miễn tiền thuê đất trong thời gian",
             "khắc phục hậu quả bão số 9 là sáu tháng kể từ tháng 10 năm 2026.",
             "", "Tôi xin chân thành cảm ơn.", "Người làm đơn"]
    img = Image.new("L", (1240, 1000), 255)
    dr = ImageDraw.Draw(img)
    f = ImageFont.truetype(ARIAL, 30)
    for i, ln in enumerate(lines):
        dr.text((90, 60 + 62 * i), ln, fill=60, font=f)
    rnd = random.Random(5)
    px = img.load()
    for _ in range(9000):
        x, y = rnd.randrange(img.width), rnd.randrange(img.height)
        px[x, y] = rnd.randrange(150, 255)
    img = img.rotate(1.6, expand=True, fillcolor=250).filter(ImageFilter.GaussianBlur(0.6))
    img.convert("RGB").save(OUT / "s07_don_de_nghi_anh_chup.jpg", quality=70, dpi=(150, 150))
    E("s07", "miễn tiền thuê đất", "miễn tiền thuê đất khắc phục hậu quả bão", "Hộ kinh doanh bị bão có được miễn tiền thuê đất không?")


def s08():
    d = Document()
    para(d, "NGHỊ QUYẾT", True, 14, "c")
    para(d, "Về nhiệm vụ phát triển kinh tế - xã hội năm 2027", True, align="c")
    para(d, "I. ĐÁNH GIÁ TÌNH HÌNH", True)
    para(d, "Năm 2026 kinh tế tăng trưởng ổn định, thu ngân sách đạt dự toán.")
    para(d, "II. NHIỆM VỤ TRỌNG TÂM", True)
    para(d, "1. Về giảm nghèo:")
    para(d, "a) Phấn đấu giảm tỷ lệ hộ nghèo đa chiều xuống dưới 2,5% vào cuối năm 2027;")
    para(d, "b) Hỗ trợ nhà ở cho hộ nghèo chưa có nhà ở ổn định.")
    para(d, "2. Về đầu tư công: giải ngân đạt tối thiểu 95% kế hoạch vốn được giao.")
    para(d, "III. TỔ CHỨC THỰC HIỆN", True)
    para(d, "Ủy ban nhân dân tỉnh chịu trách nhiệm triển khai Nghị quyết này.")
    d.save(OUT / "s08_nghi_quyet_la_ma.docx")
    E("s08", "2,5%", "giảm tỷ lệ hộ nghèo đa chiều dưới 2,5%", "Mục tiêu giảm hộ nghèo đa chiều đến cuối năm 2027 là bao nhiêu?")


def s09():
    d = Document()
    para(d, "HỢP ĐỒNG THI CÔNG XÂY DỰNG SỐ 12/HĐ-XD", True, 14, "c")
    para(d, "ĐIỀU 1 – ĐỐI TƯỢNG HỢP ĐỒNG", True)
    para(d, "1.1 Bên A giao cho Bên B thi công hạng mục nhà xưởng theo bản vẽ đính kèm.")
    para(d, "1.2 Giá trị hợp đồng là giá trọn gói, không điều chỉnh.")
    para(d, "ĐIỀU 2 – BẢO HÀNH", True)
    para(d, "2.1 Bên B phải bảo hành công trình trong 24 tháng kể từ ngày nghiệm thu.")
    para(d, "2.2 Trong thời gian bảo hành, Bên B sửa chữa miễn phí hư hỏng do lỗi thi công.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "ĐẠI DIỆN BÊN A"
    t.cell(0, 1).text = "ĐẠI DIỆN BÊN B"
    d.save(OUT / "s09_hop_dong_mau_so_cham.docx")
    E("s09", "24 tháng", "bảo hành công trình 24 tháng kể từ ngày nghiệm thu", "Nhà thầu phải bảo hành công trình bao lâu?")


def s10():
    md = """# Hướng dẫn nội bộ về an toàn thông tin

## 1. Phạm vi
Áp dụng cho mọi máy tính của cơ quan.

## 3. Quản lý tài khoản
### 3.1 Cấp tài khoản
Tài khoản chỉ cấp khi có phê duyệt của thủ trưởng đơn vị.

### 3.2 Mật khẩu
Mật khẩu tối thiểu 12 ký tự và đổi định kỳ 90 ngày; không dùng lại 5 mật khẩu gần nhất.

| Loại sự cố | Thời hạn báo cáo |
|---|---|
| Lộ mật khẩu | 4 giờ |
| Mất thiết bị | 24 giờ |
"""
    (OUT / "s10_huong_dan_markdown.md").write_text(md, encoding="utf-8")
    E("s10", "12 ký tự", "mật khẩu tối thiểu 12 ký tự", "Mật khẩu phải có độ dài tối thiểu bao nhiêu ký tự?")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (s01, s02, s03, s04, s05, s06, s07, s08, s09, s10):
        fn()
    (OUT.parent / "expected.json").write_text(json.dumps(EXP, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(list(OUT.iterdir())), "file,", len(EXP), "truy vấn")
