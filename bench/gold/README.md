# Bộ gold: đo tìm kiếm trên câu hỏi mô hình chưa thấy

Bộ Zalo 788 câu (`bench/zalo`) **nằm trọn trong tập train gốc của Zalo AI 2021**: cả 788 câu khớp nguyên văn với
3.196 câu train gốc (HF `NghiemAbe/Legal_Train_Zalo`). Mô hình nào đã huấn luyện trên tập đó sẽ được điểm cao giả
trên bộ này. Ví dụ `bkai-foundation-models/vietnamese-bi-encoder` ghi rõ đã huấn luyện trên 80% tập train Zalo.
Vì vậy mọi thay đổi mô hình phải được đo thêm trên ba phần dưới đây, và **chỉ giữ khi tốt hơn trên cả Zalo lẫn gold**.

| Phần | Số câu | Nguồn | Kho | Chạy |
|---|---|---|---|---|
| `vle` | 500 | ViLegalExperts (tư vấn luật thật, thuvienphapluat, công bố 09/2026) | kho Zalo | `bench/zalo/eval.py <gold_vle> <data Zalo> gold` |
| `van-ban-that` | 84 | Câu hỏi đã kiểm chứng trên 21 văn bản 2026 (mới hơn mọi mô hình) | 21 PDF test | `bench/van-ban-that/eval_real.py <realdocs> normal\|advance` |
| `van-phong` | tự gom | Câu hỏi thật của người dùng văn phòng | kho của bạn | như dòng trên, với `queries.json` của bạn |

## Phần `vle`: dựng lại

Tải `QA_single_context/test_data.json` và `dev_data.json` từ HF `DatNguyenAIML/ViLegalExperts`, rồi:

```text
python -I bench/gold/build_vle.py <thư mục zalo> <thư mục ViLegalExperts> <thư mục ra> --n 500
```

Script chỉ giữ câu mà câu trả lời của luật sư dẫn đúng một văn bản, đúng một Điều, văn bản đó có trong kho Zalo,
đoạn trích khớp ≥ 40% nội dung Điều trong kho (loại lệch phiên bản), và câu hỏi không gần trùng câu nào của Zalo.
Từ 35.505 câu còn 5.437 câu đạt; lấy ngẫu nhiên 500 (hạt giống 2026).

ViLegalExperts **chưa ghi giấy phép**, nên câu hỏi chỉ nằm trên máy: không commit thư mục ra, và
`bench/zalo/ket_qua_gold*.json` đã nằm trong `.gitignore`.

Hạn chế: câu hỏi lấy từ bài viết của thuvienphapluat.vn. Bộ TVPL mà BKAI dùng để huấn luyện cũng cào từ trang này,
nên vẫn có thể lẫn với dữ liệu huấn luyện của một số mô hình (thấp hơn Zalo, nhưng không bằng 0).

## Phần `van-phong`: gom câu hỏi thật

Đây là phần quan trọng nhất về lâu dài: đo đúng thứ người dùng thật hỏi trên đúng kho của họ.

1. Mỗi khi có người hỏi một câu và bạn biết Điều trả lời đúng, ghi vào `queries.json`
   (chép từ [van_phong.mau.json](van_phong.mau.json), xoá hai dòng ví dụ):
   - `q`: câu hỏi đúng như người dùng gõ (giữ lỗi chính tả, viết tắt);
   - `file`: tên file văn bản trong kho (đúng tên ở cuối thẻ kết quả);
   - `dieu_doc`: số Điều trả lời đúng; `also_ok`: các Điều khác cũng chấp nhận;
   - tuỳ chọn: `kind` (`cau_hoi` hoặc `tu_khoa`), `page`, `nguon` (ghi chú).
2. Đặt `queries.json` cạnh thư mục `data` của kho. Với app đã cài: `%LOCALAPPDATA%\SoiLuat\queries.json`.
3. Chạy (máy có Python và repo):

```text
python bench/van-ban-that/eval_real.py %LOCALAPPDATA%\SoiLuat normal
```

Gợi ý: trang **Truy vấn bỏ sót** (Cài đặt → Quản lý kho) liệt kê câu không ra kết quả, là nguồn câu khó tốt.
Nên có tối thiểu 100 câu trước khi dùng phần này để chọn mô hình.
