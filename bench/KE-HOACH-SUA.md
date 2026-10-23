# Kế hoạch sửa lỗ hổng — 4 agent song song

Đọc trước: [BAO-CAO-DEMO.md](BAO-CAO-DEMO.md), mục 6 (bảng L1–L21).
Code nằm trong `src/soiluat/`. Thư mục **không phải git repo**: chỉ sửa file mình sở hữu.

## Luật chung (mọi agent)

1. **Chỉ sửa file thuộc phần mình** (bảng dưới). Cần thay đổi ở file của agent khác thì **ghi vào báo cáo cuối**, không tự sửa.
2. **Không sửa** `tests/conftest.py` và `tests/test_v07.py` (người điều phối giữ). Test cũ trong phần mình sở hữu thì được sửa nếu hành vi đổi có chủ đích; ghi rõ lý do.
3. Giữ **hợp đồng 0.7**:
   - không LLM, embedding hay vector;
   - Search App (`app.py` và mọi thứ nó import) **không import** `pytesseract`, `PIL` hay `soiluat.ocr` (`test_app_does_not_import_ocr` phải còn xanh);
   - không tự `UPDATE hieu_luc`;
   - không lấy mức phạt từ bảng;
   - chỉ nghe `127.0.0.1`.
4. Không thêm dependency bắt buộc. Dependency tuỳ chọn thì báo agent D thêm vào extras trong `pyproject.toml`.
5. Viết test mới vào file riêng của phần mình: `tests/test_a_*.py`, `tests/test_b_*.py`, `tests/test_c_*.py`, `tests/test_d_*.py`.
   - Trong lúc làm, chạy test của phần mình.
   - Cuối cùng chạy `python -m pytest`. Lỗi ở phần agent khác (đang sửa song song) thì chỉ ghi lại, không sửa.
6. Theo phong cách code hiện có: Python 3.11, comment tiếng Việt ngắn, hàm nhỏ, không thêm lớp trừu tượng thừa.
7. Dữ liệu demo (chỉ đọc; muốn ghi thì copy ra chỗ khác): `DEMO=C:\Users\Admin\AppData\Local\Temp\claude\C--Users-Admin-Documents-GitHub-Law\fee43992-0f15-426e-8d90-84356ea2f50a\scratchpad\demo`
   - `DEMO\dirty\` — 18 file bẩn (xem `DEMO\dirty_expect.json`)
   - `DEMO\big2\data\soiluat.db` — kho 1.762 văn bản (162 MB) để đo tốc độ
   - Tesseract: `C:\Program Files\Tesseract-OCR\tesseract.exe`; tessdata có `vie` ở `%LOCALAPPDATA%\SoiLuatDemo\tessdata` (thư mục cài chỉ có eng/osd)
   - Word và Excel có trên máy (COM qua `pywin32`, đã cài)

## Sở hữu file

| Agent | File |
|---|---|
| A — Đọc file | `extract.py`, `ocr.py`, `convert.py` (mới), `tests/test_extract.py`, `tests/test_ocr.py`, `tests/test_docx.py`, `tests/test_a_*.py` |
| B — Parser + nạp | `parse.py`, `ingest.py`, `rebuild.py`, `importer.py`, `labels.py`, `links.py`, `sohieu.py`, `health.py`, `tests/test_parse.py`, `tests/test_importer.py`, `tests/test_health_rebuild.py`, `tests/test_labels.py`, `tests/test_fines.py`, `tests/test_b_*.py` |
| C — Tìm kiếm | `search.py`, `query.py`, `cards.py`, `fold.py`, `db.py`, `schema.sql`, `synonyms_seed.csv` (mới, trong `src/soiluat/`), `tests/test_query.py`, `tests/test_search_cards.py`, `tests/test_filters.py`, `tests/test_fold.py`, `tests/test_queries_fixture.py`, `tests/test_review_queue.py`, `tests/fixtures/*`, `tests/test_c_*.py` |
| D — App + đóng gói | `app.py`, `config.py`, `export_word.py`, `templates/*`, `pack/*`, `pyproject.toml`, `README.md`, `tests/test_app_export.py`, `tests/test_host_csrf.py`, `tests/test_pack_spec.py`, `tests/test_d_*.py` |

## Hợp đồng giữa các phần (bắt buộc làm đúng, vì các phần viết song song)

### H1. `extract.py` (A) → ingest (B)

- `SUPPORTED_SUFFIXES: frozenset[str]` — mọi đuôi `extract_file` nhận được. Ít nhất: `.docx .doc .rtf .pdf .txt .md .jpg .jpeg .png .tif .tiff .bmp .xlsx`.
- `ExtractedPage` giữ nguyên các trường cũ và thêm hai trường có mặc định:
  - `notes: list[Note] = field(default_factory=list)`
  - `ocr_conf: float | None = None`
- `@dataclass class Note: kind: str; text: str; ref: str | None = None`
  - `kind` thuộc `footnote | endnote | comment | textbox | header | footer`.
- **Bảng** được nội tuyến vào `text` đúng vị trí đọc, mỗi hàng một dòng dạng `| ô 1 | ô 2 | ô 3 |`: bắt đầu bằng `| `, kết thúc bằng ` |`, ô rỗng giữ chỗ.
- **Footnote/endnote:** chèn mốc `[^n]` vào text ngay chỗ tham chiếu, kèm `Note(kind="footnote", ref="n", text=...)` trên trang có mốc.
- Comment, text box, header, footer: chỉ đưa vào `notes` của trang 1. `ref = None`, riêng comment thì `ref` là đoạn chữ được comment (≤ 80 ký tự).
- DOCX tách trang theo ngắt trang cứng **và** `w:lastRenderedPageBreak`, để số trang gần với Word.
- Ảnh (`.jpg/.png/.tif/.bmp`): mỗi ảnh hoặc frame là một trang, `kind="image"`, `ocr_status="cho_ocr"`, `text=""`.
- `.doc` / `.rtf`: `convert.py` đổi sang `.docx` tạm. Thứ tự thử: Word COM (pywin32), LibreOffice `soffice`, cuối cùng `ValueError` có hướng dẫn tiếng Việt.
- `.xlsx`: mỗi sheet là một trang, các hàng ở dạng `| … |` như trên. Không thêm dependency, đọc bằng `zipfile` + XML.

### H2. `ocr.py` (A) → importer (B), app (D)

- `ocr_status() -> dict` với khoá `ok: bool, tesseract_cmd: str|None, tessdata: str|None, langs: list[str], message: str`.
  - Tìm `tesseract.exe` lần lượt ở: env `SOILUAT_TESSERACT` → `PATH` → `C:\Program Files\Tesseract-OCR` → `%LOCALAPPDATA%\Programs\Tesseract-OCR` → thư mục `tesseract\` cạnh exe khi đóng gói (`sys.frozen`).
  - Tìm tessdata lần lượt ở: env `SOILUAT_TESSDATA` → `TESSDATA_PREFIX` → `%LOCALAPPDATA%\SoiLuat\tessdata` → `%LOCALAPPDATA%\SoiLuatDemo\tessdata` → `<thư mục tesseract>\tessdata`.
  - Phải có `vie`.
  - Module **không** import `pytesseract` hay `PIL` ở mức module.
- `class OcrUnavailable(RuntimeError)`, thông báo tiếng Việt nói cần cài gì.
- `maybe_ocr_pages(path, pages) -> pages` nhận **cả PDF lẫn ảnh**.
  - Có trang cần OCR mà OCR không dùng được thì **raise `OcrUnavailable`**, không im lặng nữa.
  - Ghi `ocr_conf` cho từng trang.

### H3. Importer (B) → app (D)

- `python -m soiluat.importer --check-ocr` in **một dòng JSON** = `ocr_status()` ra stdout rồi thoát mã 0.
- `python -m soiluat.importer PATH [--ocr] [--doan]`:
  - lỗi từng file không dừng cả lượt; mỗi file ghi `import_jobs`;
  - cuối cùng in tóm tắt; có file lỗi thì mã thoát 1.
- Trang cần OCR mà không có `--ocr`: nạp chữ có được, và job ghi `error` dạng cảnh báo "N trang cần OCR, nạp lại với --ocr". Status vẫn `done`.

### H4. Đường dẫn đơn vị (B tạo → C/D hiển thị)

- Điều trùng số trong cùng văn bản: lần thứ 2 trở đi mang hậu tố `~n` ngay sau số Điều, ví dụ `D5~2`, `D5~2.K1`, `D5~2.K1.Đa`. Không còn crash UNIQUE.
- Ghi chú (footnote, comment, text box…): đơn vị `level="ghi_chu"`, path `GC1`, `GC2`…
  - `parent_id` là đơn vị chứa mốc `[^n]` nếu tìm được.
  - Không gắn nhãn rủi ro (thuộc hạng 4).
- C cập nhật `fold.pretty_path` và `fold.dieu_path`:
  - `D5~2.K1` → `Điều 5 (lần 2) khoản 1`;
  - `dieu_path("D5~2.K1")` → `D5~2`;
  - `GC3` → `ghi chú 3`;
  - `dieu_path("GC3", "ghi_chu")` → `GC3`.
- B cập nhật regex Điều trong `links.py` cho có `~n`.
- Hai văn bản trong một file (B):
  - tách thành **nhiều dòng `documents`**;
  - văn bản thứ k ≥ 2 có `file_path = "<path>#vb<k>"` và `sha256 = "<sha>#vb<k>"`;
  - văn bản 1 giữ nguyên `file_path`;
  - chỉ tách khi chắc chắn: có khối đầu văn bản mới (Số: …/…, tên loại văn bản) **và** đánh số Điều bắt đầu lại từ 1.
- Đơn vị chứa dòng bảng `| … |` → `from_table = 1`.
- `units.page_from` / `page_to` là số trang thật, tính từ ranh giới trang của `pages`.

### H5. Đường dẫn file (B)

- File nằm trong thư mục data: giữ đường dẫn tương đối như cũ.
- File ngoài thư mục data: lưu **đường dẫn tuyệt đối** (dấu `/`), không chỉ tên file. Không đổi các dòng cũ đã có trong DB.

### H6. Card / tìm kiếm (C) → giao diện (D)

- `Card` thêm các trường có mặc định:
  - `page_to: int | None`;
  - `notes: list[str]` (text các đơn vị `ghi_chu` con của Điều trong thẻ, tối đa 3);
  - `match_tier: int` (1–6; 0 cho tra số hiệu);
  - `intent: str` (`""` hoặc `"muc_phat"`).
- `page_from` / `page_to` lấy từ đơn vị hiển thị đầu tiên của thẻ.
- Seed từ điển: `db.init_schema` nạp `synonyms_seed.csv` (cột `term,alt,kind,approved`) bằng `INSERT OR IGNORE`. Viết tắt chuẩn có `approved=1`; diễn đạt khác có `approved=0` để người duyệt.
- D làm UI `/review/synonyms`: liệt kê, duyệt (`approved=1`), thêm, xoá. Chỉ dùng SQL trên bảng `synonyms` có sẵn.

### H7. App (D)

- Cổng: env `SOILUAT_PORT` hoặc `--port`; mặc định 8000.
  - Nếu đã có thứ trả lời trên `127.0.0.1:<cổng>`, thử 8001…8020, in URL thật, mở trình duyệt (`webbrowser.open`).
- Lệnh gọi Importer:
  - chạy từ mã nguồn: `[sys.executable, "-m", "soiluat.importer", ...]`;
  - đóng gói (`sys.frozen`): `SoiLuatImporter.exe` (tìm cạnh exe hoặc `..\SoiLuatImporter\SoiLuatImporter.exe`).
  - Form nạp có ô **OCR**. Trang `/jobs` hiện trạng thái OCR bằng cách gọi `importer --check-ocr` (subprocess, timeout 10 s; cache theo phiên).
- Hiển thị:
  - "Trang x–y" trên thẻ và trang nguồn;
  - ghi chú/footnote trong thẻ và trang nguồn;
  - ngày ban hành/hiệu lực ở `/review/docs` và trên thẻ khi có (cột `documents.ngay_ban_hanh` / `ngay_hieu_luc` do B điền dạng `YYYY-MM-DD`).
- `pyproject.toml`: thêm extra `word = ["pywin32>=306"]`, và gom `ocr` cùng `word` vào hướng dẫn README.

## Việc của từng agent (chi tiết trong prompt riêng)

- **A:** L1, L2, L3, L4, L5 (tiền xử lý ảnh: 300 dpi, xám, tự xoay bằng OSD nếu có), L6 (OCR cả trang trộn và trang chữ rác).
- **B:** L7, L8, L9, L10, L11, L12, L13, L21 + H3, H4, H5.
- **C:** L16, L17, L18 (seed + nạp), L19, L20 + H4 (phần `fold`), H6.
- **D:** L14, L15, L18 (UI) + H6 (hiển thị), H7.
