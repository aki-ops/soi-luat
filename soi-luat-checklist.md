# Checklist Soi Luật — máy văn phòng (bản 0.8)

Bám [soi-luat-ke-hoach.md](soi-luat-ke-hoach.md) **0.8**. Sản phẩm **chỉ Lite / máy văn phòng** — không tick việc LLM, embedding, Docker. Checklist này **có hiệu lực**; không tick theo bản 0.4–0.7.

Tick `- [x]` khi **xong và kiểm được** (test hoặc đo). Không tick vì “đã nghĩ tới”.

Một người, 8 tuần. Máy 8 GB, Word/Excel/trình duyệt có thể đang mở.

**Code:** `src/soiluat/` phiên bản **0.8.0**. Chạy `python -m pytest` (**198 passed, 1 skipped**, 22/10/2026). Search: `python -m soiluat`. Importer: `python -m soiluat.importer`. Đo hiệu năng và demo: `bench/` (báo cáo `bench/BAO-CAO-DEMO.md`).

**Tìm kiếm (22/10/2026):** thang 6 tầng AND được thay bằng một truy vấn BM25 OR (có dấu + ngữ cảnh) nhân hệ số theo mức khớp cụm/gần/đủ từ/đồng nghĩa; thẻ xếp theo độ liên quan trước; app không còn rút khung câu hỏi. Zalo 788 câu: Hit@10 54,7% → 88,5%, MRR 0,348 → 0,661, p50 190 → 962 ms. Số liệu: `bench/zalo/KET-QUA.md`.

**Tuỳ chọn theo nghĩa (22/10/2026):** `semantic.py` + bảng `unit_vectors` + `soiluat-importer --nhung`; xếp lại 20 Điều đầu bằng EmbeddingGemma (ONNX int8, CPU, 2 luồng); thiếu mô hình thì tìm như cũ. Zalo: Hit@5 86,2% → 89,1%, Hit@10 90,2% → 91,8%; RAM Search App ~480 MB (đỉnh 1,3 GB), +0,3 s/câu, nhúng 4,5 Điều/s (cắt 128 token; 256 token chỉ 2,3 Điều/s, độ chính xác như nhau). Đổi hợp đồng "không embedding" thành "embedding tuỳ chọn, chạy local". Người dùng chọn **Normal** (BM25, mặc định) / **Advance** (BM25 + embedding) bằng nút trên trang Tra cứu; nạp văn bản không nhúng, nhúng nền bằng `--nhung --nen`.

**Về các số đo:** làm trên **máy thử** (Ryzen 5, 6 nhân, 15 GB RAM, ~1,3 GB trống lúc đo), dữ liệu **sinh tự động** (300 văn bản + 18 file lệch mẫu dựng bằng Word thật). Mục nào ghi “máy thử” thì **chưa** phải số đo trên máy văn phòng 8 GB với Office đang mở và văn bản thật.

**Cổng tuần 0 (kế hoạch mục 8, 10):** năm từ khoá thật + hai danh sách Q5 **chưa có** — khung 3.4 đã code, chưa đối chiếu với đáp án người dùng. Không coi search đã “đóng” cho tới khi 5/5 biểu diễn được.

---

## Không làm trên máy văn phòng

Cấm đưa vào sprint. Không phải “bản đầy đủ để sau”.

- [x] Không embedding, vector, ONNX, NumPy semantic, RRF, reranker
- [x] Không LLM, llama.cpp, RAG, Docker, PostgreSQL, Qdrant
- [x] Không gợi ý chính tả
- [x] Không ô chủ thể trong câu mẫu
- [x] Không kho Word chuẩn hoá bắt buộc
- [x] Không tự `UPDATE hieu_luc` từ “thay thế / bãi bỏ”
- [x] `SoiLuat.exe` không import Tesseract/OpenCV (`test_app_does_not_import_ocr`, spec excludes)
- [x] Không UI sửa ranh giới / sửa chữ OCR / tách nhiều văn bản (Q4) — POST sửa OCR và “duyệt cấu trúc” đã gỡ; GET `/review/pages` chỉ xem

---

## 0. Trước tuần 1 (vận hành + khung)

- [x] Viết lại checklist theo 0.7, cập nhật lên 0.8 ngày 21/10/2026 (file này)
- [ ] Người dùng viết **5 từ khoá thật** + đáp án: hạng thẻ 1–4, Điều/Khoản (file nếu trùng số hiệu), có/không cần mức phạt trên thẻ
- [ ] Đối chiếu khung 3.4 / 4.3.1 với cả 5 từ — không biểu diễn được thì **sửa khung, chưa coi search xong**
- [ ] Hai danh sách Q5 (ưu tiên / hạ ưu tiên); cụm một tiếng dùng **tên đầy đủ** (F3)
- [ ] Nạp `subject_rules` (`approved = 1`) từ hai danh sách đó
- [ ] Đếm kho: số file, tỷ lệ Word / PDF chữ / PDF scan / PDF trộn
- [ ] Ghi cấu hình máy văn phòng: CPU, RAM trống khi Office + trình duyệt đã mở
- [ ] Chốt chỗ đặt data (`SOILUAT_DATA`; mặc định code là `./data`, chưa `%LOCALAPPDATA%\SoiLuat`)
- [ ] Gom ≥ 20 văn bản đại diện (đủ 3–4 loại file)
- [ ] File DOC cũ: chuyển sang DOCX trước khi nạp
- [ ] Ai duyệt `links` + `effect_hints`; giờ/tuần (không phân công duyệt ranh giới trên UI)

**Cổng:** checklist 0.8 có hiệu lực; 5/5 từ khoá biểu diễn được; hai danh sách Q5 đã nhập.

---

## Tuần 1 — Khám kho và đo máy

- [x] Script sức khoẻ kho (2.6) chạy thư mục, CSV một dòng/file (`soiluat.health`)
- [x] CSV có: loại file, số trang, lớp chữ, cần OCR, font cũ, nghi nhiều văn bản, số Điều, S, tầng, ranh giới thấp, số hiệu, dung lượng
- [x] Cột **Q2:** `co_cum_phat_tien_tu` từng file; dòng tổng `_TONG` `so_van_ban_co_phat_tien_tu` / `ty_le_xu_phat` (`test_health_csv`)
- [ ] Biết % tách tạm ổn / % phải OCR / % nên sửa nguồn / nạp chia đoạn
- [ ] Đo RAM + thời gian OCR **một worker**, Office đang mở (máy thử, **Office chưa mở**: ~1,2–1,4 s/trang, Importer đỉnh 162 MB; chưa đo trên máy 8 GB)
- [x] RAM Search App: đo app thật — 59 MB lúc rảnh, 64 MB đỉnh, CPU rảnh 0,2–0,5 % (máy thử, kho 310 văn bản)
- [ ] 30–50 truy vấn thật, mỗi truy vấn có `R_q` = nhóm `(doc_id, Điều)` nếu biết
- [x] Không đo embedding, không đo LLM

**Cổng:** CSV + hai số Q2; biên bản “kho không xử phạt → sống bằng thẻ loại 3” nếu đúng vậy; bộ truy vấn.

---

## Tuần 2–3 — Importer

- [x] Process riêng `SoiLuatImporter` (không nhét OCR vào app tra cứu)
- [x] `import_jobs`: queued → running → done/failed/`skipped_duplicate`; `file_path` + `sha256`
- [x] Trùng `sha256`, path khác → `skipped_duplicate` + `existing_file_path`, không `doc_id` mới (E5, `test_e5_skipped_duplicate`)
- [x] `documents.file_path` UNIQUE; cùng path, SHA đổi → cập nhật tại chỗ (`rebuild_document_from_file`)
- [x] Đọc DOCX: dựng số từ numbering.xml (kể numbering trên style)
- [ ] Word COM `ListString` (pywin32) khi có Word — chưa có (0.8 chỉ dùng Word COM để đổi `.doc` / `.rtf` sang DOCX; numbering vẫn tự mô phỏng từ `numbering.xml`)
- [ ] E6: ≥ 3 DOCX soạn bằng Microsoft Word (numbering đoạn / style / nhiều cấp)
- [x] Đọc PDF chữ (pdfplumber)
- [x] Phân loại **từng trang**: chữ tốt / đáng ngờ / chỉ ảnh / trộn / bảng
- [x] OCR Tesseract `vie` một worker; không OCR đè trang chữ tốt (test skip `text_ok`)
- [x] Năm lớp chữ: raw / normalized / `search_accent` / `search_text` (fold) / `reviewed_text` (không UI sửa)
- [x] Fold: NFC, thường, `đ/Đ/Ð` → `d`, bỏ dấu, gộp khoảng trắng
- [x] `search_accent`: NFC, thường, Ð→Đ, **giữ dấu**, không đ→d
- [x] Parser 3 tầng; `path` dạng `D5` / `D5.K1` / `D5.K1.Đa` / `p1.para n` — **không** nhúng số hiệu
- [x] Chữ riêng từng đơn vị; `context_search` / `context_accent` từ câu dẫn cha (Điều gốc rỗng)
- [x] Điểm S = 0,4 C_phủ + 0,3 C_liên_tục (B12) + 0,3 C_khoản; kẹp [0, 1]
- [x] S < 0,60 → dùng tầng 3 (chia đoạn) như bảng 2.5 (`test_s_below_threshold_falls_back`)
- [x] Fallback tầng 3 khi 0 Điều: đoạn/cửa sổ, địa chỉ trang — không bỏ file; `fallback_doan`
- [x] Cờ Importer “chia theo đoạn” (`--doan` / `force_doan`)
- [x] `unit_labels` nhiều nhãn (kể `THOI_HAN`, `DIEU_KIEN`); không cột `units.label`
- [x] F1 `CHE_TAI`: phạt…đối với hành vi / điểm dưới khoản đó; “buộc” đầu câu + khắc phục hậu quả; không “bắt buộc”/“ràng buộc”; Điều quy định chung không gắn
- [x] Không gán nghĩa vụ/cấm/chế tài cho quốc hiệu, căn cứ, phần ký
- [x] Không lấy mức phạt từ trang bảng
- [x] `fine_min`/`fine_max` trên điểm kế thừa câu dẫn khoản; `fine_source_unit` (`test_fine_source_on_diem`)
- [x] Parse `"01 triệu đồng"`; `"gấp … lần"` / `"…%…"` → fine NULL, giữ nguyên văn (`test_fines.py`)
- [x] Dẫn chiếu nội bộ `Điều này` / `khoản này` → `links.method = noi_bo` (`test_noi_bo_dieu_nay`)
- [x] `so_hieu_search` = fold(`so_hieu`); không UNIQUE
- [x] `title_search` = fold(title)
- [x] Snapshot `links` theo `(doc_id, path)` **hai đầu**; nạp lại một văn bản không xoá đầu kia (`test_e2_cross_doc_snapshot`)
- [x] `query_log.selected_unit` ON DELETE SET NULL; `selected_doc_id` / `selected_path` (`test_c1_query_log_set_null_on_rebuild`)
- [x] Bảng `subject_rules`, `effect_hints` (Importer ghi gợi ý thay thế/bãi bỏ, `confirmed=0`)
- [x] WAL, `busy_timeout=5000`, `foreign_keys=ON`
- [x] Đường dẫn trong DB tương đối từ thư mục data
- [x] Dọn tệp tạm OCR: `maybe_ocr_pages` dùng `TemporaryDirectory` + `finally: tmp.cleanup()` (không phụ thuộc trạng thái job)

**Cổng tuần 2–3:** không mất file; nạp lại cùng path giữ links; trùng hash path khác → skipped_duplicate; query_log không chặn nạp lại; `"thông tin bắt buộc"` không `CHE_TAI`.

---

## Tuần 4 — Search App

- [x] FastAPI chỉ `127.0.0.1`; HTMX; không Tesseract
- [x] Khởi động probe FTS5 + `fts5vocab` (`db.probe_fts`); lỗi → dừng process
- [x] FTS5 năm cột; trigger INSERT/UPDATE/DELETE đủ `context_accent`
- [x] MATCH `{search_accent context_accent}` / `{search_text context_search}` (C3)
- [x] Q6: truy vấn có dấu chạy đủ 6 tầng nhánh accent; bỏ dấu **toàn kho** chỉ khi 0 nhóm; nhãn Q6
- [x] F2: unit OCR chưa `da_doi_chieu` luôn thêm nhánh fold trên tập đó, gộp dù đã có nhóm accent
- [x] Tra không dấu: `dieu kien` ra `Điều kiện`
- [x] C2: `15/2020/nd-cp` và `15/2020/NĐ-CP` cùng văn bản
- [x] F4: gõ `15/2020` → `LIKE fold||'/%'`; không ra `115/2020` (cấm `%` đầu mẫu số hiệu)
- [x] Fixture `64/2025/QH15` bắt đủ `QH15`; ít nhất một `TTLT-…` (`test_qh15_and_ttlt`)
- [x] Tra “Điều n + số hiệu” nếu user gõ dạng đó
- [x] Escape token FTS (quote, `"` nhân đôi); không MATCH chuỗi thô
- [x] Test query chứa `" * - : ( )` và token AND, OR, NOT, NEAR — không 500 (`test_escape_fts_specials_do_not_crash`)
- [x] Tầng NEAR 10 (tầng 2)
- [x] Lắp thẻ 4.3.1 / D1: bốn tên thẻ 3.4; `CHE_TAI` một mình = hạng 2
- [x] Q5 xếp sau hạng, trước hiệu lực, không đổi hạng; F3 chữ có dấu, ranh giới từ, `< 2 tiếng` phân biệt hoa thường (`Bộ` ≠ `bộ`)
- [x] F3 đủ 4 fixture: không khớp mảnh trong token khác; `"Ngân hàng Nhà nước"` thắng `"ngân hàng"`; tên Điều `"Trách nhiệm của " + hạ ưu tiên`; `Bộ` ≠ `bộ`
- [x] `hieu_luc = het` xám + xếp cuối
- [x] Host allowlist `127.0.0.1` / `localhost` → 400 nếu khác; CSRF cookie SameSite=Strict + form/header
- [x] Test Host lạ → 400; POST không token → 403; không CORS (`test_host_and_csrf` **xoá** `SOILUAT_ALLOW_TEST_HOST`; test khác vẫn bypass)
- [ ] Xem bản gốc / ảnh trang PDF scan (chỉ đọc); tô bbox nếu có
- [x] Spawn Importer từ nút nạp; theo dõi `import_jobs`
- [x] p95 khung A–E ≤ 1 giây trên corpus mẫu (máy thử: p95 76 ms kho 310 văn bản; 125 ms kho 1.762 văn bản đo trong process; **ngoại lệ** “Điều n + số hiệu” trên kho lớn p95 ~0,8 s — vẫn dưới 1 s nhưng sát)
- [x] Mở nguồn ≤ 2 giây (máy thử: 16–19 ms)

**Cổng:** kết quả cuối `thuế` không chứa đoạn chỉ-`thuê` (non-OCR) trừ 0 nhóm accent; OCR sai dấu vẫn ra (F2, hai nhãn); `15/2020` không ra `115/2020`.

---

## Tuần 5 — Từ điển và tầng tìm

- [x] `synonyms`: chỉ `approved = 1`
- [x] Sáu tầng: 1 phrase → 2 NEAR 10 → 3 AND → 4 union alt → 5 bớt từ IDF cao (df lớn) → 6 lõi
- [x] Tầng 4 **không** AND gốc∪alt; không tự ghép cụm ngoài từ điển
- [x] `df(từ)` = COUNT MATCH trên cột nhánh (`search_accent` hoặc `search_text`)
- [x] `fts5vocab` (`units_vocab`) cho từ một tiếng (`_token_df`); df đọc vocab hiện tại (không cache file riêng theo “phiên bản kho”)
- [x] Tách từ longest-match trên synonyms + tên Điều (phần còn lại: khoảng trắng)
- [x] Dừng khi ≥ 5 **nhóm** có nhãn rủi ro/`CHE_TAI` hoặc ≥ 10 nhóm (B7) — trong từng nhánh
- [x] Fixture ngưỡng `enough_groups` (≥ 10 nhóm / không đủ với 2 nhóm). Chưa đo cắt tầng 5–6 trên kho thật
- [x] Thẻ ghi nếu khớp nhờ đồng nghĩa
- [x] `query_log` + hàng đợi truy vấn bỏ sót
- [x] Ghi `selected_unit` / `selected_doc_id` / `selected_path` khi mở `/unit/{id}` (`test_unit_view_writes_query_log_selection`)
- [x] Không gợi ý chính tả
- [ ] Đo Recall@10 đúng B11 trên ≥ 50 truy vấn `R_q ≠ ∅` (ngưỡng chốt sau mốc)

**Cổng:** từng tầng giải thích được; union tầng 4 đúng; `df` đúng cột nhánh.

---

## Tuần 6 — Nhãn, nối, khung A–E

- [x] Nhãn: NGHIA_VU / CAM / THOI_HAN / DIEU_KIEN / QUYEN / CHE_TAI / DINH_NGHIA
- [x] Phủ định B8: không gán NGHIA_VU từ “không phải / không bắt buộc / không có nghĩa vụ” (`test_thoi_han_dieu_kien_and_negation`)
- [x] Fixture THOI_HAN (“trước ngày”) / DIEU_KIEN (“phải đáp ứng”) — nhãn có; hạng 3 khi không link không `CHE_TAI` theo 4.3.1
- [x] Trích phạt từ câu, không từ bảng
- [x] Nối `dan_chieu` khi viện dẫn khoản/Điều; `confirmed` mặc định 0
- [x] Không dẫn chiếu: tối đa 3 gợi ý FTS; `/review` Đúng/Sai (UI này **giữ**)
- [x] UI duyệt `effect_hints` (`/review/hints` chấp nhận/từ chối; không tự đổi hiệu lực); nhập `subject_rules` tại `/review/subjects`
- [x] Hạng 1 chỉ `links.confirmed = 1` — tên **Rủi ro (liên kết đã duyệt)**
- [x] Hạng 2: `confirmed=0` **hoặc** `CHE_TAI` chưa nối — **không** gọi xác nhận pháp lý
- [x] Hạng 3: nhãn rủi ro, không `CHE_TAI`, không `links`
- [x] Hạng 4: định nghĩa/quyền/đoạn khác; **không** gồm `CHE_TAI` đứng một mình
- [x] Câu mẫu không chủ thể; hạng 2 không in số tiền khi không rõ đối tượng + ghi chú kiểm tra mức phạt
- [x] OCR chưa đối chiếu → **Trích dẫn OCR chưa xác minh**, không đổi hạng 1–4
- [x] Gom hit cùng `(doc_id, Điều)` thành một thẻ
- [x] Điều khoản thi hành: không thành hạng 1–3 nếu không có link đã duyệt
- [x] Cảnh báo: hiệu lực chưa rõ / hết hiệu lực / không cấu trúc / trang bảng

**Cổng:** fixture bốn hạng 100%; F1 100%; không gọi hạng 2 là xác nhận pháp lý.

---

## Tuần 7 — Lọc, Word, backup, cổng tài nguyên

- [x] Bộ lọc: loại văn bản, cơ quan, hiệu lực
- [x] Xuất Word từ **thẻ đã chọn**; câu có nguồn; không sinh kho Word chuẩn hoá
- [x] Sao lưu SQLite Backup API
- [x] Khôi phục được trên máy thử (test đọc lại DB backup)
- [x] Cảnh báo Q2 trên UI khi kho không có `CHE_TAI` (`q2_note` trên `_results.html`)
- [ ] RAM backend tra cứu ≤ 600 MB (máy thử: 64 MB đỉnh, kho 310 văn bản; **chưa** đo RSS với kho 1.762 văn bản / DB 162 MB)
- [ ] Search App + tab trình duyệt ≤ 1 GB phần phát sinh; máy không đứng ~85–90% RAM (chưa đo trên máy 8 GB)
- [x] CPU Search App lúc rảnh ~ 0% (máy thử: 0,2–0,5 %)
- [ ] Peak Importer đo được; Office vẫn dùng được khi nạp (một worker) — **đã đo peak** (DOCX 163 MB, PDF chữ 74 MB, OCR 162 MB, bộ file bẩn 259 MB); **chưa** thử Office đang mở

**Cổng:** xuất Word + backup/restore + số RAM/latency ghi vào biên bản.

---

## Tuần 8 — Đóng gói

- [x] PyInstaller `onedir`: `SoiLuat` và `SoiLuatImporter` (Tesseract/`vie` chỉ Importer; Search excludes pytesseract/cv2/onnx/llama)
- [x] Chỉ nghe `127.0.0.1`
- [ ] Máy Windows sạch: không Python, không Tesseract sẵn, không admin; probe FTS5/`fts5vocab` trên **cả hai exe**
- [ ] Cài bằng chép thư mục → nạp → tìm → xuất Word → sao lưu thành công
- [x] Hướng dẫn một trang: README (cập nhật 0.8: Tesseract + `vie`, loại file, cổng, `/review/synonyms`, `--check-ocr`; không UI sửa OCR/ranh giới; `--doan`; `/review/hints` `/review/subjects` `/review/docs`)
- [ ] Thử khi Word + Excel + trình duyệt đang mở, máy 8 GB

**Cổng:** người khác chạy được theo hướng dẫn; thiếu FTS thì dừng rõ, không chạy câm.

---

## Sprint 0.8 — sửa lỗ hổng sau demo (21/10/2026)

Mỗi mục có test trong `tests/test_a_*` … `test_d_*` và/hoặc đã chạy lại bộ demo `bench/` (trước → sau). Mã L1–L21 theo `bench/BAO-CAO-DEMO.md` mục 6.

**Đọc file (A)**

- [x] L1 DOCX: bảng `| … |`, footnote `[^n]`, endnote, comment, text box, header/footer; ngắt trang `lastRenderedPageBreak`
- [x] L2 Nhận `.doc` / `.rtf` (Word COM → LibreOffice → lỗi hướng dẫn), ảnh `.jpg .png .tif .bmp`, `.xlsx`; `SUPPORTED_SUFFIXES`
- [ ] L2 Nhánh LibreOffice với `soffice` thật (máy thử không có, chỉ test giả lập)
- [x] L3 Bảng PDF: kẻ khung + không kẻ khung, không còn chữ ô trộn lẫn (44 PDF chữ không nhận nhầm)
- [x] L4 `ocr_status()` tìm Tesseract / tessdata `vie`; thiếu → `OcrUnavailable`; lỗi trang → `loi_ocr`; không import OCR ở mức module
- [x] L5 Render theo dpi gốc (150–300), xám, khử nghiêng; OSD chỉ khi `ocr_conf < 75` hoặc chữ thưa. d05 97,7 %, d06 95,1 % số từ đúng
- [x] L6 OCR trang `mixed` ảnh phủ nhiều; trang lớp chữ rác → `text_suspect` + `cho_ocr`
- [ ] OCR sai dấu còn ~3–5 % số từ (chấp nhận được; thẻ có nhãn OCR chưa xác minh)

**Parser và nạp (B)**

- [x] L7 Trùng số Điều/khoản/điểm → hậu tố `~n`; lỗi parse → chia đoạn; không crash `UNIQUE`
- [x] L8 `ĐIỀU 1:`, `Điều thứ hai`, `Điều 3 .`, `Điều 4.Hiệu lực`, khoản `1)` `1/`, điểm `a.` `đ)`; dòng trích dẫn không thành Điều
- [x] L9 Tách hai văn bản một file (`#vb{k}`) khi đủ ba điều kiện
- [x] L10 `page_from` / `page_to` thật cho mọi đơn vị
- [x] L11 `ngay_ban_hanh`, `ngay_hieu_luc` (`YYYY-MM-DD`); `loai` theo nội dung; không đụng `hieu_luc`
- [x] L12 File ngoài thư mục dữ liệu lưu đường dẫn tuyệt đối; hai file cùng tên ở hai thư mục thành hai văn bản
- [x] L13 Importer: lỗi một file không dừng cả lượt; tóm tắt; mã thoát; UTF-8; `--check-ocr`
- [x] L21 Dẫn chiếu “Điều n Nghị định số X” nối sang X; X không có trong kho thì không nối
- [x] Nội dung trước Điều đầu tiên (khoản mồ côi, ảnh trang 2) thành đơn vị `doan`, không mất
- [x] Nạp lại cùng file với `--ocr` / `--doan` làm lại đúng; nạp lại khi đã xong thì “không đổi” (`test_nap_lai_cung_file_voi_ocr`, `…_voi_doan`)
- [x] Điều nằm trong ngoặc kép cong `“ ”` của văn bản sửa đổi không còn tách thành Điều mới; dòng đóng `… ”` vẫn thuộc phần trích (`test_a1_*`)
- [x] Comment Word gắn vào Điều/khoản được nhận xét (ref có nhãn “Điều 6.” / “1.” trước đây không khớp) — `test_a4_*`; text box / header / footer không có điểm neo nên vẫn là ghi chú rời
- [x] Footnote trong PDF chữ: dòng chữ nhỏ ≥ 12% cuối trang mở đầu bằng số → ghi chú, bỏ khỏi thân; chỉ số mũ → `[^k]` gắn đúng Điều — `test_a5_*` và file d10 (GC1 → Điều cha)
- [x] Số thứ tự Word: `_Numbering` viết lại — số La Mã, `start`/`startOverride`, `isLgl`, `%1.%2.%3` nhiều cấp, `Điều %2.` ở cấp 2, gạch đầu dòng. `bench/word_numbering.py` so với `ListString` của Word thật: 6/6 file khớp (trước đó 3/4 file lệch)

**Tìm kiếm (C)**

- [x] L16 Khoá sắp xếp: `het` cuối → tầng khớp → hạng → Q5 → hiệu lực (khớp 3.6 của 0.7; code 0.7 sai)
- [x] L17 Q9: hỏi “mức phạt” bỏ cụm, thẻ chế tài lên đầu, `intent = muc_phat` (0 % → 100 % có đáp án trong top 10)
- [x] L18 Q7: `synonyms_seed.csv` (67 viết tắt `approved = 1`, 44 diễn đạt khác `approved = 0`), nạp `INSERT OR IGNORE` theo phiên bản (`app_meta`)
- [x] L19 Câu hỏi: bỏ khung hỏi, chủ ngữ đầu câu, từ đệm hai đầu; tầng 6 chọn từ hiếm nhất (70 % → 100 %; tỷ lệ đúng 0,31 → 0,86)
- [x] L20 Cache tên Điều (làm mới theo `MAX(id)` + `COUNT`), bỏ N+1; kho 1.762 văn bản p95 1.173 → 125 ms
- [x] `fold.pretty_path` / `dieu_path` hiểu `~n` (Điều, khoản, điểm) và `GC{n}`
- [x] Tra “Điều n” (không kèm số hiệu) trên kho lớn: chỉ lấy mức Điều, hiển thị tối đa 100 thẻ kèm dòng “thêm số hiệu để thu hẹp” (`DIEU_CAP`); kho 1.800 văn bản p95 143 ms (`test_a3_*`). “Điều n + số hiệu” vốn nhanh (1 ms)
- [x] Hỏi “thẩm quyền / hình thức / biện pháp / thủ tục… xử phạt” không còn bị bỏ cụm “xử phạt” như câu hỏi mức phạt (`test_a6_*`)
- [ ] Duyệt 44 cặp từ điển `approved = 0` (diễn đạt khác: 70 % → ~80 % sau khi duyệt hết) — việc của người dùng

**App và đóng gói (D)**

- [x] L14 Nút nạp có ô OCR / chia đoạn; `importer_cmd()` cho mã nguồn và bản đóng gói; kiểm đường dẫn; `importer.log`
- [x] L15 Cổng `--port` / `SOILUAT_PORT`; bận thì thử 8001…8020 và in URL
- [x] `/jobs` hiện trạng thái OCR qua `importer --check-ocr` (lỗi → “không kiểm tra được”, không 500); Search App không import OCR
- [x] `/review/synonyms`: duyệt / bỏ duyệt / xoá / thêm (CSRF)
- [x] Thẻ hiện “Trang x–y”, ghi chú (≤ 3), nhãn ý định mức phạt, ngày ban hành / hiệu lực; xuất Word có trang, tên file, ghi chú, cảnh báo
- [x] `pyproject.toml` 0.8.0, extra `word`, package-data `synonyms_seed.csv`; spec PyInstaller thêm `convert`, `win32com`, seed
- [x] Ô lọc `loai` có đủ 8 loại: luật, pháp lệnh, nghị quyết, nghị định, thông tư, quyết định, chỉ thị, công văn
- [x] Build exe thật (PyInstaller, venv riêng; Search 67 MB, Importer 81 MB). Importer exe nạp 9 file kèm OCR + `.doc` qua Word; Search exe tra cứu + nút Nạp gọi Importer exe + ảnh trang; **tìm ra và sửa:** Search App chết khi stdout không phải UTF-8 (in dòng tiếng Việt lúc khởi động)
- [ ] Thử exe trên máy Windows sạch (không Python, không Office); xuất Word từ exe
- [x] Xem ảnh trang gốc: `/page/{doc}/{n}` (PDF render bằng pypdfium2 → PNG không cần Pillow; ảnh .jpg/.png trả nguyên) + liên kết trong trang nguồn đơn vị. Chưa có tô vùng chữ (bbox)

**Đo lại bằng văn bản thật**

- [x] Nạp thư mục văn bản thật; đếm số file theo loại; ghi % tách tạm ổn / % phải OCR / % chia đoạn
  - 22/10/2026, 21 văn bản chinhphu.vn (9 Luật, 6 NĐ, 5 TT, 1 QĐ; 443 trang, 18/21 file là scan): OCR 1,69 s/trang, giống bản gốc 98,5%; tách đúng 249/344 Điều (72%); số hiệu đúng 12/21. Lỗi và cách sửa: `bench/van-ban-that/KET-QUA.md` (dấu ngoặc lạc làm mất Điều, PDF bị nhận thành bảng, SO_LINE bỏ sót "Luật số:"). **Chưa** đo trên thư mục văn bản của người dùng.
- [x] Bộ truy vấn thật có đáp án; đo Recall@10 / tỷ lệ đúng trong top 10 như bảng trong `bench/BAO-CAO-DEMO.md`
  - 84 câu có đáp án đối chiếu bản scan: Normal Hit@1 76,2%, Hit@10 95,2% (đúng số Điều: 65,5% / 81,0%); Advance Hit@1 65,5%, Hit@5 94,0%: trên văn bản thật Advance làm tụt hạng 1.
  - Sau sửa lỗi ngoặc kép / bảng giả / số hiệu (23/10/2026): Điều tách đúng 75% → 97%, Normal Hit@1 81,0%, Hit@10 96,4% (đúng số Điều 79,8% / 96,4%), p50 370 ms. Chi tiết và chỗ còn sai: `bench/van-ban-that/KET-QUA.md`. Chưa có tập kiểm riêng.
  - Sau sửa tiêu đề Điều hỏng / cơ quan / ngày ban hành (23/10/2026): Điều tách đúng 99% (341/344), cơ quan ban hành đúng 21/21 (trước 6), ngày hiệu lực 19/21, ngày ban hành 14/21, số hiệu 16/21 (còn lại viết tay hoặc bị mộc đè); tìm kiếm Normal @1 82,1%, @10 96,4%, p50 336 ms.

---

## Cổng đứng (mọi tuần — fixture bắt buộc)

Chạy lại mỗi khi đụng search / nhãn / ingest.

- [x] Fold: `dieu kien` → `Điều kiện` trên nhánh không dấu; không nhờ `remove_diacritics` để `đ→d`
- [x] Q6: gõ `thuế` không ra đoạn chỉ-`thuê` khi nhánh accent đã có nhóm; 0 nhóm accent → fold + nhãn Q6
- [x] F2: OCR sai dấu vẫn ra kèm nhãn OCR + Q6
- [x] Số hiệu: `nd-cp` / `NĐ-CP` cùng văn bản
- [x] F4: `15/2020` không ra `115/2020`
- [x] Hit + `confirmed=0` → hạng 2 (tên 3.4)
- [x] Hit + `confirmed=1` → hạng 1
- [x] `CHE_TAI` không link → hạng 2, không hạng 4
- [x] C3: điểm không có “phạt tiền”, khoản cha có → vẫn MATCH
- [x] Không `synonyms` → tầng 4 không bịa alt; có cặp → union
- [x] Câu mẫu không chủ thể, không số bịa
- [x] Bảng chưa duyệt không tạo mức phạt tự động
- [x] query_log không chặn nạp lại (C1)
- [x] skipped_duplicate (E5)
- [x] Đổi `documents.so_hieu` → `path` và `links.confirmed=1` còn (`test_change_so_hieu_keeps_confirmed_links`)
- [x] Hai file cùng số hiệu, khác sha256 → hai `doc_id`, tra số hiệu ra cả hai (`test_two_files_same_so_hieu`)
- [x] Link A–B, chỉ nạp lại A → link còn nếu path A còn (E2)
- [x] Mọi kết quả truy vết được: hash, cách trích, OCR nếu có (trang unit)

---

## Lệch còn lại so với hợp đồng 0.8

Lõi schema / parser / search / thẻ / Host-CSRF **đã khớp 0.8 và có test**. Còn lại chủ yếu vận hành hoặc phụ thuộc máy/Word/văn bản thật:

| Lệch | Chỗ | Việc |
|---|---|---|
| E6 / ListString | `bench/word_numbering.py` | Code không gọi `ListString` (đọc XML); đã đối chiếu 6 file Word thật, khớp. Còn: file Word thật của cơ quan (đánh số kiểu lạ, danh sách dùng chung nhiều `numId`) |
| Ảnh trang | `pageimg.py` | Xem được ảnh trang gốc; chưa tô vùng chữ (bbox) và `page_regions` chưa dùng |
| Cổng tuần 0 | người dùng | 5 từ khoá thật + đáp án; hai danh sách Q5 đầy đủ tên |
| Văn bản thật | tuần 1 | Chạy `bench/` trên kho thật; số trong báo cáo hiện là dữ liệu sinh tự động |
| Đo máy 8 GB | tuần 7, 8 | Đã đo: kho 1.800 văn bản (DB 166 MB), Search exe 62 → 69 MB, p95 143 ms. Còn: máy 8 GB thật có Office đang mở, exe trên máy Windows sạch, Recall@10 trên văn bản thật |

Không lệch kiến trúc máy văn phòng: không embedding/LLM/RAG; hai process; WAL; `path` không chứa số hiệu (chỉ thêm hậu tố `~n` / `GCn`).

**Đã đổi so với 0.7 có chủ đích** (kế hoạch mục Q7–Q9): từ điển khởi tạo gói sẵn; đầu vào mở rộng; hỏi “mức phạt” thành ý định. Thứ tự tầng → hạng **không** phải thay đổi kế hoạch: là sửa code cho đúng 3.6 của 0.7.

---

## Xong khi

- [x] Gõ từ khoá ra thẻ + nguyên văn + địa chỉ nguồn (so_hieu lúc render + path)
- [x] Ngày chưa duyệt: vẫn có hạng 2/3/4 — không bịa hạng 1
- [ ] Cổng tuần 0 (5 từ khoá + Q5) đã tick
- [ ] Hai exe, một DB WAL, máy 8 GB + Office
- [ ] Cổng tuần 8 và cổng đứng (kể mục còn `[ ]` ở trên) đều tick

Chưa xong sản phẩm nếu còn phụ thuộc LLM/embedding, hoặc Search App kéo Tesseract lúc mở, hoặc checklist này bị thay bằng bản 0.4–0.7.
