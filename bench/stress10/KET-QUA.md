# 10 file lệch cấu trúc — kết quả (21/10/2026)

Chạy lại: `python bench/stress10/gen.py` rồi `python bench/stress10/run.py <thư mục data> [soiluat.db nền]`.
Kho nền 318 văn bản demo + 10 file này. Mỗi file 2 truy vấn (từ khoá, câu hỏi) = 20 truy vấn; "đúng" = thẻ chứa cụm đáp án nằm trong top 10.

| File | Dạng | Cấu trúc | Nạp | Tìm (từ khoá / câu hỏi) | Vấn đề thấy |
|---|---|---|---|---|---|
| s01 thông báo | DOCX văn xuôi | không Điều | đủ | 1 / 1 | — |
| s02 quy chế | DOCX "Quy tắc n", "Mục 3.1" | không Điều | đủ | 1 / 1 | "Quy tắc", "Mục 3.1" không thành đơn vị riêng |
| s03 biên bản | TXT **không dấu**, gạch đầu dòng | không Điều | đủ | 1 / **trượt** | câu hỏi tiếng Việt có dấu kết thúc "trước ngày nào?" ra 0 thẻ |
| s04 hỏi đáp | PDF chữ **hai cột** | Câu/Trả lời | đủ | 1 / 1 | hai cột bị nhận là bảng: câu hỏi cột trái và cột phải xen kẽ từng dòng, câu trả lời cuối bị tách ra ngoài bảng |
| s05 biểu phạt | XLSX hai sheet | bảng | đủ | 1 / hạng 3 | mất tên sheet; số không có dấu phân cách; mức phạt chỉ ở bảng nên thẻ không có số tiền riêng |
| s06 quy trình | DOCX "Bước n" + bảng + "Lưu ý" | không Điều | đủ | 1 / 1 | — |
| s07 đơn | **ảnh JPG** nghiêng, nhiễu | thư | OCR | 1 / 1 | OCR đọc **năm 2026 thành 2028**, "ĐỀ"→"ĐÈ", "hưởng"→"hướng" |
| s08 nghị quyết | DOCX La Mã I./II. + a) b) | không Điều | đủ, nhận `loai = nghi_quyet` | 1 / 1 | a), b) không thành điểm vì không có Điều |
| s09 hợp đồng | DOCX "ĐIỀU 1 – …", 1.1, 1.2 | Điều gạch nối | đủ | 1 / 1 | **"Điều 1 – Tên" / "Điều 1 - Tên" không được nhận là Điều** → cả hợp đồng thành 1 đoạn; "1.1" không thành khoản |
| s10 markdown | MD `#`, `##`, bảng | tiêu đề # | đủ | 1 / 1 | `#` không thành cấp; bảng markdown giữ nguyên |

**19/20 truy vấn đúng.** 10/10 file nạp, không file nào lỗi hay mất chữ.

## Hạn chế chung

- Cả 10 file chỉ ra **1 đơn vị "đoạn" mỗi file** (điểm cấu trúc 0). Tìm đúng, nhưng trích dẫn chỉ là "cả văn bản", không chỉ ra Bước 3 hay Quy tắc 2.
- Văn bản dài không cấu trúc (thử 80 đoạn) bị cắt khối ~350 từ (≈ 7 đoạn); đáp án nằm trong khối 7 đoạn, thẻ hiện cả khối.
- Số hiệu, ngày ban hành, loại: gần như không trích được từ văn xuôi (chỉ s08 ra loại).

## Có thể sửa nhỏ

1. Nhận "Điều n – / - Tên" (dấu gạch ngang).
2. Bỏ đuôi hỏi "ngày nào", "tháng nào", "năm nào", "mấy ngày" khỏi câu hỏi.
3. PDF hai cột không có đường kẻ: không coi là bảng nếu các dòng không thẳng hàng như hàng bảng (hoặc đọc theo cột).
4. OCR: chữ số sai (2026→2028) không sửa được bằng code; thẻ vẫn nhãn "OCR chưa xác minh".
