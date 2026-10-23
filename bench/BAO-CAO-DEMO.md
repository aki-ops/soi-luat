# Báo cáo chạy demo + đo hiệu năng — Soi Luật 0.7.0

Ngày đo: 21/10/2026. Đo trên bản code **trước khi sửa** (bản gốc được sao lưu trước khi chỉnh).
Chạy lại toàn bộ: `python bench/gen_corpus.py DIR`, `python bench/word_tools.py DIR`, `python bench/run_bench.py DIR`.

## 1. Máy đo

| | |
|---|---|
| CPU | AMD Ryzen 5 5600GT, 6 nhân / 12 luồng, GPU tích hợp (không dùng tới) |
| RAM | 15,4 GB, **chỉ còn ~1,3 GB trống** lúc đo (máy đang chạy nhiều thứ) |
| Ổ | SSD |
| Phần mềm | Windows 11, Python 3.11, Office (Word/Excel), Tesseract 5.4 + gói `vie` (cài mới cho demo) |

Máy mạnh hơn mục tiêu (8 GB), nên có chạy thêm một lượt **giới hạn Search App còn 2 luồng CPU** để giả máy yếu.

## 2. Bộ dữ liệu thử

- **Kho tải:** 300 văn bản sinh tự động (nghị định/thông tư 8 lĩnh vực, 13–40 Điều/văn bản, 30% là văn bản xử phạt): 248 DOCX, 40 PDF chữ (Word xuất), 12 PDF scan 200 dpi.
- **Kho lớn:** thêm 1.452 DOCX → **1.762 văn bản, 133.425 đơn vị, DB 162 MB**.
- **Bộ file "bẩn" (18 file)** dựng bằng Word thật, mô phỏng file văn phòng không đúng format: Word tự đánh số Điều, nội dung trong bảng, footnote/comment/text box/header, `.doc` cũ, PDF scan sạch / nghiêng + nhiễu, PDF trộn, PDF có bảng, định dạng lệch chuẩn (`Điều thứ hai`, `1)`, `a.`), hai văn bản trong một file, công văn không có Điều, trùng tên file ở hai thư mục, bản sao y hệt, phụ lục Excel, ảnh chụp trang JPG, PDF 45 trang.
- **268 truy vấn có đáp án** + 22 kỳ vọng cho file bẩn.

## 3. Hiệu năng

### Nạp file (Importer, một worker)

| Loại | Số file | Thời gian / file (trung vị) | RAM đỉnh |
|---|---|---|---|
| DOCX | 248 | **0,10 s** | 138 MB |
| PDF chữ | 40 | **0,5 s** (≈ 0,11 s/trang) | 78 MB |
| PDF scan + OCR | 12 (57 trang) | **5,1 s** (≈ **1,05 s/trang**) | 175 MB |
| File bẩn có OCR | 18 | 0,3 s (tối đa 6,6 s) | 252 MB |

- 1.400 DOCX nạp liên tục vào kho đang lớn dần: đều **~0,11 s/file**, không chậm dần.
- Một lần chạy đầu bị chậm dần tới ~6 s/file, nhưng **không tái hiện được** (nghi do RAM trống thấp hoặc antivirus quét file vừa tạo).
- OCR chính xác **~97% số từ** với bản scan sạch, **~95%** với bản nghiêng và nhiễu. Lỗi chủ yếu nằm ở dấu, ví dụ `cấm → cầm/cắm`, `bố → bồ`, `hằng → bằng`.

### Tra cứu (Search App)

| | Kho 310 văn bản | Kho 1.762 văn bản |
|---|---|---|
| Khởi động | 1,3–1,8 s | — |
| RAM lúc rảnh / đỉnh | **57 MB / 63 MB** | — |
| CPU lúc rảnh | 0,2–0,5 % | — |
| Độ trễ tra từ khoá p50 / p95 / max | **190 / 340 / 500 ms** | **~1,2–1,5 s mỗi truy vấn** |
| Cùng kho, giới hạn 2 luồng | 192 / 325 / 636 ms | — |
| Tra số hiệu | ~20 ms | ~1,2 s |
| Xuất Word 10 thẻ | 0,08 s | |
| Sao lưu SQLite | 0,9 s (29 MB) | |

**Kết luận hiệu năng:**
- RAM và CPU rất nhẹ, dư xa ngưỡng 600 MB.
- Độ trễ **tăng tuyến tính theo kích thước kho**: kho ~1.800 văn bản đã vượt ngưỡng 1 giây.
- Nguyên nhân đã profile được: mỗi truy vấn, `search.vocab_phrases()` đọc và chuẩn hoá lại tên **toàn bộ** Điều trong kho, chiếm ~90% thời gian tìm.

## 4. Chất lượng tìm kiếm (kho 310 văn bản)

| Nhóm truy vấn | Ví dụ | Có đáp án trong top 10 | Tỷ lệ đúng trong top 10 |
|---|---|---|---|
| Từ khoá đúng chữ | `kê khai thuế giá trị gia tăng` | **100%** | 0,89 |
| Không dấu | `ke khai thue gia tri gia tang` | **100%** | 0,84 |
| Số hiệu / Điều + số hiệu | `Điều 5 21/2024/NĐ-CP` | **100%** | 1,00 |
| Câu hỏi | `tổ chức tín dụng có phải báo cáo … không?` | 70% | **0,31** |
| Viết tắt | `đóng BHXH bắt buộc`, `lập HĐĐT` | 56% | 0,42 |
| Diễn đạt khác | `xin giấy phép xây dựng`, `mua bình chữa cháy` | 40% | 0,29 |
| Hỏi mức phạt | `mức phạt không đóng bảo hiểm xã hội bắt buộc` | **0%** | 0,00 |

**Tóm lại, kết quả phụ thuộc rất mạnh vào cách hỏi.** Gõ đúng chữ trong văn bản thì gần như luôn ra. Hỏi kiểu tự nhiên, viết tắt hoặc hỏi "mức phạt" thì phần lớn trượt.

## 5. Kết quả với file không đúng format

| File | Kết quả |
|---|---|
| Word tự đánh số Điều | Nạp đúng cấu trúc, nhưng thẻ khớp đúng nguyên câu bị xếp thứ 13 (lỗi xếp hạng, mục L16) |
| Nội dung trong **bảng Word** | **Mất**, không tìm được |
| PDF có bảng | Chữ các ô bị **trộn lẫn theo dòng** ("Không niêm yết giá dịch Phạt tiền từ 3.000.000 vụ cầm đồ…") |
| Footnote / comment / text box / header (Word) | **Mất cả 4** |
| `.doc` cũ, `.xlsx`, ảnh `.jpg` | **Từ chối** ("Không hỗ trợ") |
| PDF scan sạch / nghiêng-nhiễu / trộn | Tìm được, có nhãn "OCR chưa xác minh" ✔ |
| PDF scan khi **thiếu Tesseract** | Báo "thành công" nhưng **0 chữ**, không cảnh báo |
| Định dạng lệch (`Điều thứ hai`, `1)`…) | **Lỗi, cả file không nạp được** (UNIQUE `units.doc_id, path`) |
| Hai văn bản trong một file | **Lỗi, cả file không nạp được** |
| PDF 45 trang (ghép nhiều văn bản) | **Lỗi, cả file không nạp được** |
| Công văn không có Điều | Nạp dạng đoạn, tìm được ✔ |
| Bản sao y hệt | Bỏ qua đúng (trùng hash) ✔ |
| **Trùng tên file ở 2 thư mục** | File sau **ghi đè** file trước, **mất dữ liệu** |
| Nạp cả thư mục bằng CLI | **Dừng hẳn ở file lỗi đầu tiên**, các file sau không được nạp |

Ngoài ra:
- Mọi trích dẫn đều ghi "Trang 1–N", **không biết đoạn nằm ở trang nào**.
- Ngày ban hành và hiệu lực không được trích (310/310 "chưa rõ").
- Cổng 8000 cố định: trên máy đo đã có ứng dụng khác chiếm cổng 8000, mở trình duyệt có thể ra **ứng dụng khác**.

## 6. Danh sách lỗ hổng

| Mã | Lỗ hổng | Mức | Bằng chứng |
|---|---|---|---|
| L1 | Bỏ bảng, footnote, comment, text box, header/footer trong DOCX | Cao | d02, d03 |
| L2 | Không nhận `.doc`, ảnh (`.jpg/.png/.tif`), `.xlsx` | Cao | d04, d14, d15 |
| L3 | Bảng trong PDF bị trộn chữ giữa các ô | TB | d08 |
| L4 | OCR im lặng khi thiếu Tesseract; không tự tìm `tesseract.exe` / `tessdata` | Cao | ocr_no_path |
| L5 | OCR sai dấu (~3–5% từ), chưa tiền xử lý ảnh (deskew, 300 dpi) | TB | d06 |
| L6 | Chỉ OCR trang < 40 ký tự; trang trộn chữ và ảnh bị bỏ qua | TB | đọc code |
| L7 | **Trùng số Điều/Khoản → crash cả file** | **Rất cao** | d09, d11, d16 |
| L8 | Không nhận `Điều thứ hai`, `Điều 3 .`, khoản `1)` `1/`, điểm `a.` | Cao | d09 |
| L9 | Không tách hai văn bản trong một file; mất số hiệu văn bản thứ 2 | TB | d11 |
| L10 | Không có số trang cho từng Điều/Khoản | Cao | mọi thẻ "Trang 1–N" |
| L11 | Không trích ngày ban hành / ngày hiệu lực | TB | 310/310 |
| L12 | **File ngoài thư mục data chỉ lưu tên file → trùng tên thì ghi đè** | **Rất cao** | trung_ten |
| L13 | CLI nạp thư mục dừng ở file lỗi đầu tiên; lọc đuôi file im lặng | Cao | cli_dirty |
| L14 | Nút "Nạp" trên UI không có tuỳ chọn OCR; bản exe gọi `sys.executable -m` sẽ hỏng | Cao | đọc code |
| L15 | Cổng 8000 cố định, không phát hiện xung đột | TB | máy đo |
| L16 | Xếp theo hạng rủi ro trước độ khớp: khớp nguyên câu bị đẩy xuống dưới | Cao | d01 thứ 13 |
| L17 | Câu hỏi "mức phạt…" ra 0% | Cao | muc_phat |
| L18 | Từ điển đồng nghĩa/viết tắt rỗng, không có UI quản lý | Cao | viet_tat, dien_dat_khac |
| L19 | Câu hỏi tự nhiên: chủ thể và từ đệm làm loãng truy vấn | TB | cau_hoi P@10 0,31 |
| L20 | **Độ trễ tăng theo kích thước kho** (`vocab_phrases` quét toàn kho mỗi lần tìm) | **Rất cao** | 1,762 văn bản → 1,5 s |
| L21 | Dẫn chiếu "khoản 1 Điều 5 Nghị định X" luôn nối về Điều 5 **của chính văn bản đang đọc** | TB | đọc code `links.py` |

## 6b. Sau khi sửa (0.8.0, cùng máy, cùng bộ dữ liệu)

`pytest`: 90 → **177 passed**.

| | Trước | Sau |
|---|---|---|
| File bẩn nạp được | 12/18 | **18/18** |
| Kỳ vọng file bẩn tìm thấy | 6/22 | **22/22** (có số trang thật) |
| Nạp thư mục bằng CLI | dừng ở file lỗi đầu tiên | chạy hết, mã thoát 0 |
| DOCX / PDF chữ (s/file) | 0,10 / 0,51 | 0,08 / 0,46 |
| OCR (57 trang) | 60 s | 69 s (OSD chỉ chạy khi trang kém) |
| Tra cứu, kho 310 văn bản: p50 / p95 | 188 / 343 ms | **49 / 76 ms** |
| Tra cứu, kho 1.762 văn bản: p50 / p95 (đo trong process) | 930 / 1.173 ms | **88 / 125 ms** |
| RAM Search App lúc rảnh | 57 MB | 59 MB |

| Nhóm truy vấn | Có đáp án trong top 10 (trước → sau) | Tỷ lệ đúng trong top 10 (trước → sau) |
|---|---|---|
| Từ khoá | 100% → 100% | 0,89 → 0,91 |
| Không dấu | 100% → 100% | 0,84 → 0,84 |
| Câu hỏi | 70% → **100%** | 0,31 → **0,86** |
| Viết tắt | 56% → **100%** | 0,42 → **0,93** |
| Hỏi mức phạt | 0% → **100%** | 0,00 → **0,88** |
| Diễn đạt khác | 40% → 70% | 0,29 → 0,53 (cần người duyệt từ điển ở `/review/synonyms`) |
| Số hiệu / Điều + số hiệu | 100% → 100% | 1,00 → 1,00 |

Còn tồn:
- "Điều n + số hiệu" trên kho lớn: p95 ~0,8 s.
- OCR vẫn sai dấu ~3–5% số từ.
- Chưa build exe thật trên máy Windows sạch.
- Dữ liệu là dữ liệu sinh tự động, chưa thử với kho văn bản thật.

## 7. Kế hoạch sửa (4 agent chạy song song, không đụng file của nhau)

| Agent | Phạm vi | File sở hữu |
|---|---|---|
| **A — Đọc file đầu vào** | L1, L2, L3, L4, L5, L6 | `extract.py`, `ocr.py`, `convert.py` (mới), test extract/ocr/docx |
| **B — Parser + nạp an toàn** | L7, L8, L9, L10, L11, L12, L13, L21 | `parse.py`, `ingest.py`, `rebuild.py`, `importer.py`, `labels.py`, `links.py`, `sohieu.py`, `health.py`, test parse/importer/rebuild/labels |
| **C — Tìm kiếm + xếp hạng** | L16, L17, L18 (dữ liệu và hàm), L19, L20 | `search.py`, `query.py`, `cards.py`, `fold.py`, `db.py`, `schema.sql`, `synonyms_seed.csv` (mới), test search/query |
| **D — App, hiển thị, đóng gói** | L14, L15, L18 (UI), hiển thị trang/ghi chú, trạng thái OCR | `app.py`, `templates/*`, `config.py`, `export_word.py`, `pack/*`, `README.md`, test app/host/pack |

Ràng buộc chung:
- Giữ đúng hợp đồng 0.7: không LLM, không embedding, Search App không import Tesseract, không tự đổi hiệu lực.
- Mỗi agent thêm test cho phần mình.
- Chạy lại `pytest` và bộ demo này sau khi gộp để so trước/sau.
