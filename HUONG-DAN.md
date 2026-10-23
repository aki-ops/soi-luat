# Soi Luật — Hướng dẫn sử dụng

Soi Luật là app tra cứu văn bản pháp luật **chạy ngay trên máy bạn** (Windows). Bạn nạp văn bản (Word, PDF, ảnh scan, Excel…) vào một "kho" riêng, rồi hỏi bằng từ khoá hoặc câu hỏi tự nhiên. Kết quả là **nguyên văn** Điều/khoản trong văn bản của bạn, kèm văn bản nguồn và số trang, không phải lời diễn giải của máy.

- Không cần internet, không gửi dữ liệu đi đâu. App chỉ nghe ở `127.0.0.1` (chỉ máy bạn truy cập được).
- Không dùng AI sinh văn bản. Chế độ Advance chỉ dùng một mô hình nhỏ để hiểu nghĩa câu hỏi, chạy trên CPU.

---

## 1. Cài đặt

1. Chạy file **`SoiLuat-Setup.exe`** (khoảng 300 MB).
2. Bấm Next theo các bước. Không cần quyền admin; app cài vào `%LOCALAPPDATA%\Programs\SoiLuat`.
3. Tích "Mở Soi Luật" ở bước cuối, hoặc mở từ Start menu → **Soi Luật**.

Windows SmartScreen có thể báo "không rõ nhà phát hành" vì bộ cài chưa có chữ ký số. Chọn **More info → Run anyway** nếu bạn tin nguồn file.

Cài đè lên bản cũ thì **kho dữ liệu được giữ nguyên**. Gỡ app: Settings → Apps → Soi Luật (kho vẫn còn, xem mục 9 nếu muốn xoá hẳn).

## 2. Mở và tắt app

- Mở **Soi Luật** từ Start menu: hiện một cửa sổ đen (console) và trình duyệt tự mở trang `http://127.0.0.1:8000`.
- Cổng 8000 đang bận thì app tự thử 8001 … 8020; địa chỉ thật được in trong cửa sổ đen.
- **Tắt app: đóng cửa sổ đen.** Đóng trình duyệt chưa tắt app.

## 3. Giao diện

Giao diện kiểu chat, chỉ có ba thứ:

| Vị trí | Là gì |
|---|---|
| Góc trên **bên trái**: **Nạp file** | Mở khung nạp văn bản. Có chấm báo khi app đang đọc file ở nền. |
| Góc trên **bên phải**: biểu tượng bánh răng | Mở **Cài đặt**. |
| Ô nhập ở dưới | Gõ câu hỏi, **Enter** để gửi, **Shift+Enter** xuống dòng. Nút **Bộ lọc** bên cạnh để lọc kết quả. |

Giữa màn hình là khung trò chuyện: câu hỏi của bạn ở bên phải, kết quả ở dưới.

## 4. Nạp văn bản vào kho

Bấm **Nạp file** (góc trên trái).

### Cách nạp

- **Chọn file**: chọn nhiều file một lúc.
- **Chọn thư mục**: nạp cả thư mục, kể cả thư mục con.
- **Kéo thả** file hoặc thư mục vào cửa sổ app.
- **Nạp từ đường dẫn có sẵn trên máy** (mục mở rộng bên dưới): gõ `D:\VanBan` hoặc `D:\VanBan\nd15.pdf`. Cách này giữ file ở chỗ cũ, không chép vào kho; nếu sau này bạn dời hoặc xoá file gốc thì không xem được ảnh trang gốc.

File chọn hoặc kéo thả được chép vào thư mục `data\files` của kho. Cùng tên và cùng nội dung thì dùng lại, cùng tên nhưng khác nội dung thì lưu thêm thành `ten (2).pdf`.

### Định dạng nhận được

| Loại | Ghi chú |
|---|---|
| `.docx`, `.txt`, `.md` | Nhanh nhất (~0,1 giây/file). Bảng, chú thích cuối trang, comment, text box trong Word được giữ lại. |
| `.pdf` có chữ | ~0,5 giây/file. |
| `.pdf` scan, ảnh `.jpg .png .tif .bmp` | Cần **OCR**, khoảng 1,7 giây/trang. |
| `.xlsx` | Mỗi sheet là một trang. |
| `.doc`, `.rtf` | Cần máy có **Microsoft Word** (hoặc LibreOffice). |

File đuôi khác bị bỏ qua (có báo).

### Hai ô tuỳ chọn

- **OCR trang scan/ảnh** (mặc định bật): cần cho PDF scan hoặc ảnh. App đã kèm Tesseract tiếng Việt, không cần cài thêm. Quên bật thì file scan hiện trạng thái **cần OCR**; nạp lại với ô này bật.
- **Ép chia theo đoạn (không tách Điều)**: dùng cho tài liệu không có cấu trúc "Điều … khoản …" (biên bản, ghi chú, công văn). App chia theo đoạn thay vì tìm Điều.

### Theo dõi tiến độ

Danh sách trong khung Nạp file cho thấy từng file lần lượt:

| Trạng thái | Nghĩa |
|---|---|
| chờ / đang nạp | Đang trong hàng đợi / đang đọc. Trang OCR hiện tiến độ. |
| **đủ** | Nạp xong. Với PDF nhiều văn bản gộp, có ghi "N văn bản". |
| **cần OCR** | Trang là ảnh mà chưa bật OCR. |
| **trùng** | Đã có đúng file này trong kho. |
| **không đổi** | File không thay đổi so với lần nạp trước. |
| **lỗi** | Có ghi lý do ngay trên dòng. Một file lỗi **không** làm dừng cả lượt. |

Bạn **vẫn hỏi được trong lúc đang nạp**. Nút **Xoá danh sách** chỉ xoá danh sách hiển thị, không xoá văn bản trong kho.

> App không có chỗ sửa chữ trực tiếp. Muốn sửa ranh giới Điều hoặc chữ OCR, hãy sửa file nguồn rồi nạp lại **bằng đường dẫn có sẵn trên máy** (cùng đường dẫn thì app cập nhật văn bản cũ). Nếu chọn/kéo thả một file cùng tên nhưng nội dung đã khác, app lưu thành `ten (2).ext` và coi là một văn bản **mới**; hiện chưa có nút xoá từng văn bản khỏi kho.

## 5. Hỏi và đọc kết quả

### Cách hỏi

Gõ vào ô dưới, Enter. Ba kiểu đều được:

| Kiểu | Ví dụ |
|---|---|
| Từ khoá | `báo cáo định kỳ` |
| Câu hỏi | `mức phạt không đội mũ bảo hiểm là bao nhiêu?` |
| Số hiệu / Điều | `15/2020/NĐ-CP Điều 5` |

Mẹo: từ khoá ngắn, đúng thuật ngữ thường ra tốt nhất. Có dấu hay không dấu đều được. App có từ điển đồng nghĩa và viết tắt (xem mục 8). Lần mở đầu, ba gợi ý dưới tiêu đề "Hỏi về quy định" bấm vào là chạy luôn.

### Bộ lọc

Bấm **Bộ lọc** cạnh ô nhập:

- **Loại**: Luật/Bộ luật, Pháp lệnh, Nghị quyết, Nghị định, Thông tư, Quyết định, Chỉ thị, Công văn…
- **Cơ quan ban hành**: gõ một phần tên.
- **Hiệu lực**: Còn / Hết / Chưa rõ.

Có bộ lọc đang bật thì nút Bộ lọc hiện một chấm.

### Đọc một thẻ kết quả

Mỗi kết quả là một thẻ, từ trên xuống:

- **Nhãn** màu (ví dụ "Rủi ro: nghĩa vụ / điều cấm / thời hạn / điều kiện, chưa rõ chế tài", hoặc "Quy định liên quan"). Đầu trang kết quả có bốn ô thống kê: rủi ro có liên kết đã duyệt, rủi ro có chế tài, rủi ro chưa rõ chế tài, quy định liên quan.
- **Tiêu đề** và **nguyên văn** quy định. Nếu có chế tài đi kèm, nó hiện ở khối riêng "Chế tài".
- Dòng thông tin: tình trạng hiệu lực (**Còn / Hết / Chưa rõ hiệu lực**), số hiệu, số trang, ngày ban hành, ngày hiệu lực.
- **Cảnh báo ⚠** nếu có (ví dụ hiệu lực chưa rõ).
- Cuối thẻ: tên file nguồn và **Xem nguồn →**.

Thẻ có dòng **"tìm theo nghĩa, không chung từ khoá"** là thẻ do chế độ Advance thêm vào: nó gần nghĩa với câu hỏi nhưng không chứa từ bạn gõ. Đọc kỹ trước khi dùng.

Hiệu lực mặc định là "chưa rõ" cho đến khi bạn đặt trong **Cài đặt → Văn bản** (mục 7): app không tự quyết văn bản nào còn hay hết hiệu lực.

Hỏi mà kho không có gì khớp thì app báo **"Không tìm thấy quy định khớp…"** và có thể gợi ý từ trong từ điển. Câu như vậy được ghi vào **Truy vấn bỏ sót** để bạn bổ sung từ điển sau.

### Xem nguồn

**Xem nguồn →** mở trang mới hiện đúng Điều/khoản, tên file, số hiệu, trang, ngày ban hành/hiệu lực, cách trích chữ, chú thích cuối trang. Với văn bản scan hoặc ảnh, có thêm **ảnh trang gốc** để đối chiếu với chữ OCR (nếu file gốc còn ở chỗ cũ).

### Xuất ra Word

Tick **Chọn xuất** ở các thẻ muốn lấy, kéo xuống cuối rồi bấm **Xuất Word các thẻ đã chọn**. Bạn nhận một file `.docx` gồm nguyên văn, số hiệu, trang và tình trạng hiệu lực của từng thẻ.

## 6. Hai chế độ tìm: Normal và Advance

Đổi trong **Cài đặt → Chế độ tìm**. Lựa chọn được nhớ trong kho. Dòng nhỏ dưới ô nhập cho biết đang ở chế độ nào.

| | **Normal** (mặc định) | **Advance** |
|---|---|---|
| Cách tìm | Khớp từ khoá (BM25) | Khớp từ khoá + hiểu nghĩa |
| RAM | ~75 MB | ~0,5–1,4 GB |
| Tốc độ | ~0,3 giây (kho nhỏ) | ~0,6 giây; câu đầu tiên chậm hơn vì nạp mô hình |
| Khi nào nên dùng | Mọi máy; từ khoá rõ ràng | Câu hỏi diễn đạt khác chữ trong văn bản; ghi chú tự viết |

Cách Advance làm việc: xếp lại 20 kết quả đầu của Normal theo độ gần nghĩa, và thêm tối đa 20 Điều gần nghĩa nhất toàn kho (chỉ thêm nếu đủ giống). Thứ tự kết quả Normal **không bị đảo**; phần thêm chỉ nằm sau. Đo thực tế trên bộ 788 câu hỏi pháp lý: câu đúng nằm trong 10 kết quả đầu ở **90,2%** (Normal) và **92,5%** (Advance).

Khi mở Advance lần đầu, app tự **tính vector nền** cho các Điều chưa có (khoảng 4–5 Điều/giây) khi không có file nào đang nạp. Tiến độ hiện ở khung Nạp file; trong lúc chưa xong, Điều chưa tính vẫn tìm được bằng từ khoá. Kho lớn thì lần đầu tính lâu (10 nghìn Điều khoảng 37 phút), có thể để máy chạy; tắt giữa chừng rồi mở lại sẽ tiếp tục.

## 7. Cài đặt (góc trên bên phải)

- **Chế độ tìm**: Normal / Advance (mục 6).
- **OCR (tiếng Việt)**: cho biết OCR sẵn sàng chưa (ví dụ "Sẵn sàng (eng, osd, vie)"). Bấm **Kiểm tra lại** nếu cần.
- **Dữ liệu**: số văn bản trong kho; nút **Sao lưu SQLite** (mục 9).
- **Quản lý kho** (mỗi liên kết mở tab mới):
  - **Duyệt liên kết**: app tự đoán chế tài đi kèm một nghĩa vụ; bạn bấm **Đúng/Sai**. Liên kết chưa duyệt vẫn hiện, ghi rõ "liên kết máy gợi ý".
  - **Hiệu lực gợi ý**: gợi ý "thay thế/bãi bỏ" tìm thấy trong văn bản. **Không tự đổi hiệu lực**; chấp nhận chỉ đánh dấu bạn đã xem.
  - **Đối tượng Q5**: danh sách cụm chữ muốn **ưu tiên** hoặc **hạ ưu tiên** trong kết quả. Cụm một tiếng nên nhập tên đầy đủ.
  - **Văn bản**: bảng văn bản trong kho; nơi **đặt Còn/Hết/Chưa rõ hiệu lực** và sửa **số hiệu** từng văn bản.
  - **Từ điển**: cặp đồng nghĩa/viết tắt ("từ" thay bằng "…"). Chỉ cặp đã duyệt mới được dùng khi tìm; cặp bạn thêm tay được duyệt luôn.
  - **Truy vấn bỏ sót**: các câu hỏi không ra kết quả, để bạn bổ sung từ điển.

## 8. Mẹo để tìm tốt hơn

1. **Đặt hiệu lực** cho văn bản (Cài đặt → Văn bản) rồi lọc "Còn" khi tra cứu.
2. **Kiểm tra số hiệu** văn bản scan: OCR có thể đọc sai số hiệu hoặc ngày; sửa trong Cài đặt → Văn bản.
3. Câu hỏi không ra gì: thêm cặp từ đồng nghĩa vào **Từ điển** theo gợi ý từ **Truy vấn bỏ sót**.
4. Ghi chú, biên bản, tài liệu không có "Điều": bật **Ép chia theo đoạn** khi nạp, và dùng **Advance** để tìm theo nghĩa.
5. Luôn bấm **Xem nguồn** để đối chiếu với bản gốc trước khi dùng kết quả.

## 9. Dữ liệu, sao lưu, xoá

**Kho nằm ở đâu**

- Cài bằng `SoiLuat-Setup.exe`: `%LOCALAPPDATA%\SoiLuat\data` (dán đường dẫn đó vào thanh địa chỉ File Explorer để mở).
- Chạy `SoiLuat.exe` trực tiếp từ thư mục nào đó: thư mục `data` nằm ngay trong thư mục đang chạy. Biến môi trường `SOILUAT_DATA` đổi được vị trí.

Trong `data` có `soiluat.db` (toàn bộ văn bản, chỉ mục, vector), `files\` (các file đã nạp) và `backup\`.

**Sao lưu**: Cài đặt → **Sao lưu SQLite** ghi bản sao vào `data\backup\soiluat.db`. Muốn chuyển sang máy khác: tắt app, chép nguyên thư mục `data`.

**Xoá hẳn kho**: tắt app, xoá thư mục `data`. Lần mở sau kho sẽ trống.

**Quyền riêng tư**: mọi thứ ở trong máy; app không kết nối ra internet.

## 10. Dòng lệnh (tuỳ chọn)

Dành cho nạp hàng loạt không cần mở giao diện. Kho của dòng lệnh là thư mục `data` trong thư mục đang đứng, nên để nạp vào **cùng kho với app đã cài**, đặt biến môi trường trước (PowerShell):

```text
$env:SOILUAT_DATA = "$env:LOCALAPPDATA\SoiLuat\data"
cd "$env:LOCALAPPDATA\Programs\SoiLuat"
.\SoiLuat.exe import D:\VanBan --ocr
```

Các lệnh khác (cú pháp ngắn, bỏ `.\` nếu đã ở trong thư mục cài):

```text
SoiLuat.exe import D:\VanBan                 :: nạp cả thư mục
SoiLuat.exe import D:\VanBan --ocr           :: kèm OCR
SoiLuat.exe import D:\ghi_chu.docx --doan    :: ép chia theo đoạn
SoiLuat.exe import --check-ocr               :: kiểm tra OCR (in JSON)
SoiLuat.exe import --nhung --nen             :: tính vector nền, nhường CPU
```

Thông số khác: `SoiLuat.exe --port 8100` đổi cổng; `set SOILUAT_NO_BROWSER=1` tắt tự mở trình duyệt.

## 11. Khắc phục sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Trình duyệt không tự mở | Mở tay địa chỉ in trong cửa sổ đen (thường `http://127.0.0.1:8000`). |
| Trang không vào được | App đã tắt (cửa sổ đen bị đóng). Mở lại từ Start menu. |
| File scan báo **cần OCR** | Nạp lại với ô **OCR** được bật. |
| OCR báo chưa sẵn sàng | Cài đặt → OCR → Kiểm tra lại. Bản cài đã kèm Tesseract tiếng Việt; nếu báo lỗi, cài lại app. |
| `.doc`/`.rtf` báo lỗi | Cần Microsoft Word (hoặc LibreOffice). Hoặc lưu thành `.docx` rồi nạp. |
| Advance báo "Chưa cài mô hình" | Thiếu thư mục `models\embeddinggemma` cạnh `SoiLuat.exe`; cài lại bằng bộ cài đủ. App vẫn tìm như Normal. |
| Câu đầu ở Advance chậm | Bình thường: đang nạp mô hình và vector vào RAM. Kho lớn (~60 nghìn Điều) có thể 7–36 giây lần đầu; các câu sau ~1,5 giây. |
| Máy ì khi Advance | Chuyển về Normal; hoặc đợi tính vector nền xong. |
| Câu hỏi không ra kết quả | Thử từ khoá ngắn hơn, bỏ bộ lọc, gõ số hiệu; xem **Truy vấn bỏ sót** và thêm vào Từ điển. |
| Số hiệu/ngày sai ở văn bản scan | Sửa tay trong Cài đặt → Văn bản. |
| Mở app hai lần | Lần hai chạy ở cổng kế (8001…) trên **cùng kho**. Đừng nạp file ở hai bản cùng lúc; đóng cửa sổ đen thừa. |

## 12. Giới hạn cần biết

- **Chỉ là công cụ tra cứu**, không phải tư vấn pháp lý. Luôn đối chiếu bản gốc.
- App không tự biết văn bản nào hết hiệu lực; "Chưa rõ hiệu lực" là mặc định và bạn phải đặt tay.
- Văn bản scan chất lượng thấp hoặc chữ viết tay: OCR có thể sai chữ, số hiệu và ngày tháng.
- Một số Điều có cấu trúc lạ có thể không tách được; Phụ lục dạng bảng dài tìm kém hơn Điều thường.
- Thẻ "tìm theo nghĩa" có thể không liên quan trực tiếp; ngưỡng cắt được chỉnh cho mô hình hiện tại.
- Bản cài hiện chưa thử trên nhiều máy Windows khác nhau.

---

Mã nguồn và tài liệu kỹ thuật: <https://github.com/aki-ops/soi-luat> (xem `README.md`).
