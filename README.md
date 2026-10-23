# Soi Luật

Tra cứu nghị định/thông tư **trên máy văn phòng** (Windows, 8 GB, Office có thể đang mở): FTS5 + từ điển + parser + quy tắc + người duyệt; tuỳ chọn xếp lại kết quả theo nghĩa bằng EmbeddingGemma chạy CPU (không LLM, không gửi dữ liệu ra ngoài).

Bản **0.8**. Kế hoạch **0.8**: [soi-luat-ke-hoach.md](soi-luat-ke-hoach.md) · Checklist: [soi-luat-checklist.md](soi-luat-checklist.md)

## Cài

Python 3.11+. Trong thư mục repo:

```text
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Tuỳ chọn, chỉ Importer dùng:

```text
pip install -e ".[ocr]"     :: OCR PDF scan và ảnh
pip install -e ".[word]"    :: đổi .doc/.rtf qua Word (pywin32)
```

Search App **không** nạp Tesseract.

### Cài Tesseract + tiếng Việt

```text
winget install UB-Mannheim.TesseractOCR
```

Bản cài chỉ có `eng`/`osd`. Tải `vie.traineddata` (repo `tesseract-ocr/tessdata`) và chép vào **một** trong các chỗ:

- `%LOCALAPPDATA%\SoiLuat\tessdata\` (khuyên dùng, không cần quyền admin);
- thư mục chỉ bởi `SOILUAT_TESSDATA` hoặc `TESSDATA_PREFIX`;
- `C:\Program Files\Tesseract-OCR\tessdata\`.

`tesseract.exe` không nằm ở chỗ chuẩn thì đặt `SOILUAT_TESSERACT=đường\dẫn\tesseract.exe`. Kiểm tra:

```text
python -m soiluat.importer --check-ocr
```

In một dòng JSON (`"ok": true` là dùng được). Trang `/jobs` cũng hiện trạng thái này.

### File nạp được

`.docx .pdf .txt .md`; `.doc` và `.rtf` (cần Word hoặc LibreOffice trên máy); ảnh `.jpg .png .tif .bmp` (cần OCR); `.xlsx` (mỗi sheet một trang). Bảng, footnote, comment, text box trong Word được giữ lại.

### Tuỳ chọn: xếp lại theo nghĩa (EmbeddingGemma)

Không bắt buộc. Thiếu mô hình hoặc thư viện thì app tìm như cũ (BM25).

```text
pip install -e ".[nghia]"
```

Tải từ `huggingface.co/onnx-community/embeddinggemma-300m-ONNX` (giấy phép Gemma) vào `<thư mục dữ liệu>\models\embeddinggemma\`
(hoặc đặt `SOILUAT_MODEL_DIR`): `tokenizer.json`, `onnx\model_quantized.onnx`, `onnx\model_quantized.onnx_data` (~315 MB).
Sau khi nạp văn bản, tính vector một lần (cắt 128 token mỗi Điều: ~4,5 Điều/giây ở 2 luồng, file 100 Điều ≈ 22 giây, 10 nghìn Điều ≈ 37 phút; dừng giữa chừng chạy lại sẽ tiếp tục):

```text
python -m soiluat.importer --nhung
python -m soiluat.importer duong\toi\thu_muc --nhung   :: nạp rồi nhúng luôn
```

Nạp văn bản **không** tự nhúng (vẫn nhanh: DOCX ~0,08 s/file); Importer chỉ nhắc còn bao nhiêu Điều chưa có vector. Nhúng nền, 1 luồng, ưu tiên CPU thấp nhất (không làm chậm Word/Excel; dừng rồi chạy lại sẽ tiếp):

```text
python -m soiluat.importer --nhung --nen
```

Có thể hẹn bằng Task Scheduler ban đêm. Điều chưa nhúng vẫn tìm được bằng BM25 và không bị phạt hạng khi xếp lại.

Trên trang Tra cứu có nút **Chế độ tìm: Normal / Advance** (lưu trong kho, mặc định Normal):
- **Normal**: BM25 thuần, không nạp mô hình (RAM ~75 MB).
- **Advance**: BM25 + embedding. Chưa cài mô hình thì báo và tìm như Normal; còn Điều chưa nhúng thì hiện số lượng.
  Ngoài xếp lại 20 Điều đầu của BM25, còn thêm 20 Điều gần nghĩa nhất toàn kho (tìm được cả câu hỏi không chung chữ nào, vd. ghi chú viết tự do); phần thêm chỉ chen sau, không đổi thứ tự các Điều BM25 tìm ra, và thẻ có nhãn "tìm theo nghĩa, không chung từ khoá". Chỉ thêm Điều có độ giống (cosine) ≥ 0,50 (`semantic.DENSE_MIN`), nên câu vô nghĩa vẫn báo "Không tìm thấy". Tắt phần thêm: `semantic.DENSE_K = 0` (khi đó không nạp ma trận). Phần này chỉ phủ Điều đã nhúng, nên nên nhúng cả kho (`--nhung`). Ma trận vector giữ trong RAM: +65 MB với 61 nghìn Điều (đỉnh +140 MB lúc nạp), nạp ở câu Advance đầu tiên mất 0,4 s, tới ~6 s nếu ổ đĩa chưa cache.

Ở Advance, Search App nạp mô hình và ma trận vector ở câu tìm đầu tiên: RAM ~550 MB khi chạy, **đỉnh ~1,4 GB** (kho Zalo 61 nghìn Điều; không có 20 Điều từ vector: ~490 MB, đỉnh ~1,3 GB), mỗi câu thêm ~0,3–0,5 s.
Câu tìm đầu tiên sau khi bật app phải đọc kho từ ổ đĩa: kho 1,4 GB (61 nghìn Điều) mất 3–18 s ở Normal, 7–36 s ở Advance tuỳ Windows còn giữ file trong cache hay không; các câu sau ~1,1 s (Normal) / ~1,6 s (Advance). Ép tắt (bỏ qua nút): `set SOILUAT_SEMANTIC=0`.
Số đo độ chính xác: `bench/zalo/KET-QUA.md` (bộ Zalo), `bench/van-ban-that/KET-QUA.md` (21 văn bản thật, phần lớn bản scan).

## Dữ liệu

Mặc định `./data`. Đổi: `set SOILUAT_DATA=C:\Users\...\SoiLuat`

## Lệnh

Khám sức khoẻ kho (có cột Q2 “phạt tiền từ” và dòng `_TONG`):

```text
python -m soiluat.health duong\toi\kho -o health.csv
```

Nạp văn bản (process Importer):

```text
python -m soiluat.importer duong\toi\file_or_folder
python -m soiluat.importer duong\toi\folder --ocr
python -m soiluat.importer duong\toi\file --doan
```

`--doan` ép chia theo đoạn (tầng 3). Muốn sửa ranh giới hoặc chữ OCR: sửa file nguồn rồi nạp lại — không có UI sửa trong app.

Nạp từ giao diện: trang `/jobs`, có ô **OCR** và **chia đoạn**. File lỗi không dừng cả lượt; lỗi ghi ở cột "lỗi".

Tra cứu (chỉ `127.0.0.1`):

```text
python -m soiluat
python -m soiluat --port 8100
```

Cổng mặc định 8000, đổi bằng `--port` hoặc `set SOILUAT_PORT=8100`. Cổng đã có ứng dụng khác thì tự thử 8001…8020. URL thật được in ra và tự mở trình duyệt (tắt: `set SOILUAT_NO_BROWSER=1`).

- Duyệt liên kết nghĩa vụ–chế tài: `/review`
- Duyệt gợi ý thay thế/bãi bỏ: `/review/hints` (không tự đổi hiệu lực)
- Danh sách đối tượng Q5: `/review/subjects`
- Từ điển đồng nghĩa / viết tắt: `/review/synonyms` (chỉ cặp đã duyệt được dùng khi tìm)
- Metadata văn bản / hiệu lực / ngày ban hành: `/review/docs`
- Ảnh trang gốc PDF/ảnh: `/page/{id văn bản}/{số trang}` (liên kết nằm ở trang nguồn của đơn vị)
- Truy vấn bỏ sót: `/missed`
- Job nạp + trạng thái OCR: `/jobs`

## Kiểm thử

```text
pytest
```

## Sao lưu

Nút **Sao lưu SQLite** trên trang chủ, hoặc `POST /backup` ghi `data/backup/soiluat.db`. Hoặc copy cả thư mục data khi **cả hai** process đã tắt.

## Đóng gói (tuần 8)

Máy có Python (máy build):

```text
powershell -File pack\build.ps1
```

Ra `dist\SoiLuat\SoiLuat.exe` và `dist\SoiLuatImporter\SoiLuatImporter.exe` (onedir). Search App **không** kèm Tesseract. Copy **cả thư mục `dist`** (giữ hai thư mục cạnh nhau để nút Nạp tìm được Importer), không cần cài Python trên máy chạy.

Bản đủ (OCR tiếng Việt + Advance); máy build cần thêm onnxruntime, tokenizers, numpy:

```text
powershell -File pack\build.ps1 -Tesseract "C:\Program Files\Tesseract-OCR" -VieData duong\toi\vie.traineddata -Model duong\toi\embeddinggemma
```

| Thư mục trong `dist` | Dung lượng (đo 23/10/2026) |
|---|---|
| `SoiLuat\` (Search App, kèm thư viện Advance) | 142 MB |
| `SoiLuatImporter\` (gồm `tesseract\`: chỉ `tesseract.exe` + DLL nó cần, `tessdata` chỉ `vie` + `osd` để xoay trang) | 289 MB |
| `models\embeddinggemma\` (mô hình Advance) | 315 MB |
| **Tổng** | **~737 MB** |

Bản đóng gói dùng Tesseract và mô hình đi kèm trước bản cài trên máy. Không kèm dữ liệu: kho `data\` được tạo trống ở thư mục chạy lần đầu. Bỏ `-Model` thì Advance báo "Chưa cài mô hình" (Normal vẫn chạy); bỏ `-Tesseract`/`-VieData` thì máy chạy phải cài Tesseract như mục trên.
