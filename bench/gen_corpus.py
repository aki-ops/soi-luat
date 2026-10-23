"""Sinh kho thử cho demo + đo hiệu năng.

python bench/gen_corpus.py OUT_DIR [--n 300] [--seed 7]

Ra:
  OUT_DIR/scale/docx/*.docx      kho tải (Word gõ tay "Điều n.")
  OUT_DIR/scale/_pdf_src/*.docx  nguồn để Word đổi sang PDF chữ / PDF scan (bench/word_tools.py)
  OUT_DIR/manifest.json          đáp án: (số hiệu, Điều) chứa cụm nghĩa vụ/cấm/chế tài
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from docx import Document

TOPICS = [
    {
        "key": "thue", "subj": "người nộp thuế", "co_quan": "Bộ Tài chính", "tt": "TT-BTC",
        "acts": [("kê khai", "thuế giá trị gia tăng"), ("nộp", "hồ sơ khai thuế"),
                 ("lập", "hóa đơn điện tử"), ("lưu trữ", "chứng từ kế toán"),
                 ("thông báo", "thay đổi thông tin đăng ký thuế")],
        "bans": ["sử dụng hóa đơn không hợp pháp", "khai sai làm giảm số thuế phải nộp",
                 "hủy hóa đơn trái quy định"],
        "defs": [("Hóa đơn điện tử", "hóa đơn được thể hiện ở dạng dữ liệu điện tử"),
                 ("Kỳ tính thuế", "khoảng thời gian để xác định số thuế phải nộp")],
    },
    {
        "key": "nganhang", "subj": "tổ chức tín dụng", "co_quan": "Ngân hàng Nhà nước", "tt": "TT-NHNN",
        "acts": [("báo cáo", "tỷ lệ an toàn vốn"), ("duy trì", "tỷ lệ dự trữ bắt buộc"),
                 ("công bố", "lãi suất huy động"), ("ban hành", "quy định nội bộ về quản lý rủi ro"),
                 ("gửi", "báo cáo tài chính đã được kiểm toán")],
        "bans": ["cấp tín dụng cho đối tượng không được cấp tín dụng",
                 "tiết lộ thông tin khách hàng trái quy định", "cho vay vượt giới hạn cấp tín dụng"],
        "defs": [("Vốn tự có", "giá trị thực của vốn điều lệ và các quỹ dự trữ"),
                 ("Khách hàng", "tổ chức, cá nhân có quan hệ tín dụng với tổ chức tín dụng")],
    },
    {
        "key": "laodong", "subj": "người sử dụng lao động", "co_quan": "Bộ Lao động - Thương binh và Xã hội",
        "tt": "TT-BLĐTBXH",
        "acts": [("giao kết", "hợp đồng lao động bằng văn bản"), ("đóng", "bảo hiểm xã hội bắt buộc"),
                 ("trả", "lương làm thêm giờ"), ("tổ chức", "huấn luyện an toàn vệ sinh lao động"),
                 ("báo cáo", "tình hình sử dụng lao động")],
        "bans": ["giữ bản chính giấy tờ tùy thân của người lao động", "cưỡng bức lao động",
                 "phân biệt đối xử trong lao động"],
        "defs": [("Người lao động", "người làm việc cho người sử dụng lao động theo thỏa thuận"),
                 ("Thời giờ làm thêm", "khoảng thời gian làm việc ngoài thời giờ làm việc bình thường")],
    },
    {
        "key": "moitruong", "subj": "chủ dự án đầu tư", "co_quan": "Bộ Tài nguyên và Môi trường",
        "tt": "TT-BTNMT",
        "acts": [("lập", "báo cáo đánh giá tác động môi trường"), ("vận hành", "hệ thống xử lý nước thải"),
                 ("quan trắc", "khí thải công nghiệp"), ("thu gom", "chất thải nguy hại"),
                 ("đề nghị cấp", "giấy phép môi trường")],
        "bans": ["xả nước thải chưa qua xử lý ra môi trường", "chôn lấp chất thải nguy hại trái quy định"],
        "defs": [("Chất thải nguy hại", "chất thải chứa yếu tố độc hại, dễ cháy, dễ nổ")],
    },
    {
        "key": "thucpham", "subj": "cơ sở sản xuất thực phẩm", "co_quan": "Bộ Y tế", "tt": "TT-BYT",
        "acts": [("tự công bố", "sản phẩm thực phẩm"), ("kiểm nghiệm", "định kỳ sản phẩm"),
                 ("ghi", "nhãn hàng hóa"), ("lưu", "mẫu thực phẩm"),
                 ("tổ chức khám", "sức khỏe định kỳ cho người trực tiếp sản xuất")],
        "bans": ["sử dụng phụ gia ngoài danh mục được phép", "kinh doanh thực phẩm quá hạn sử dụng"],
        "defs": [("Phụ gia thực phẩm", "chất được chủ định đưa vào thực phẩm trong quá trình sản xuất")],
    },
    {
        "key": "pccc", "subj": "cơ sở kinh doanh", "co_quan": "Bộ Công an", "tt": "TT-BCA",
        "acts": [("trang bị", "phương tiện phòng cháy và chữa cháy"), ("xây dựng", "phương án chữa cháy"),
                 ("tổ chức thực tập", "phương án chữa cháy"), ("kiểm tra", "hệ thống báo cháy tự động")],
        "bans": ["che khuất lối thoát nạn", "tự ý thay đổi công năng công trình"],
        "defs": [("Lối thoát nạn", "lối đi dẫn tới đường thoát nạn an toàn")],
    },
    {
        "key": "dulieu", "subj": "bên kiểm soát dữ liệu", "co_quan": "Bộ Công an", "tt": "TT-BCA",
        "acts": [("thông báo", "vi phạm quy định bảo vệ dữ liệu cá nhân"),
                 ("lập", "hồ sơ đánh giá tác động xử lý dữ liệu cá nhân"),
                 ("thu thập", "sự đồng ý của chủ thể dữ liệu"), ("xóa", "dữ liệu cá nhân khi hết mục đích")],
        "bans": ["mua bán dữ liệu cá nhân", "chuyển dữ liệu cá nhân ra nước ngoài trái quy định"],
        "defs": [("Dữ liệu cá nhân", "thông tin gắn liền với một con người cụ thể")],
    },
    {
        "key": "xaydung", "subj": "chủ đầu tư", "co_quan": "Bộ Xây dựng", "tt": "TT-BXD",
        "acts": [("đề nghị cấp", "giấy phép xây dựng"), ("lập", "nhật ký thi công xây dựng"),
                 ("mua", "bảo hiểm công trình trong thời gian xây dựng"),
                 ("tổ chức nghiệm thu", "công trình trước khi đưa vào sử dụng")],
        "bans": ["xây dựng sai nội dung giấy phép xây dựng", "lấn chiếm hành lang bảo vệ công trình"],
        "defs": [("Công trình xây dựng", "sản phẩm được tạo thành bởi sức lao động của con người")],
    },
]

TAILS = ["", " theo mẫu quy định tại Phụ lục I ban hành kèm theo Nghị định này",
         " chậm nhất 30 ngày kể từ ngày phát sinh", " trước ngày 31 tháng 3 hằng năm",
         " theo hướng dẫn của cơ quan có thẩm quyền", " và chịu trách nhiệm về tính chính xác"]
FILL = ["Việc thực hiện phải bảo đảm công khai, minh bạch, đúng quy định của pháp luật.",
        "Cơ quan quản lý có trách nhiệm hướng dẫn, kiểm tra việc thực hiện quy định tại Điều này.",
        "Hồ sơ được nộp trực tiếp, qua dịch vụ bưu chính hoặc qua Cổng dịch vụ công quốc gia.",
        "Trường hợp có vướng mắc, tổ chức, cá nhân phản ánh về cơ quan chủ trì để được hướng dẫn."]


def _money(rng: random.Random) -> tuple[int, int]:
    lo = rng.choice([1, 2, 5, 10, 15, 20, 30, 40, 50])
    return lo, lo * 2


def gen_doc(rng: random.Random, idx: int) -> dict:
    t = rng.choice(TOPICS)
    year = rng.choice(range(2015, 2026))
    nd = rng.random() < 0.6
    so = f"{idx + 1}/{year}/{'NĐ-CP' if nd else t['tt']}"
    xu_phat = rng.random() < 0.3
    loai_name = "NGHỊ ĐỊNH" if nd else "THÔNG TƯ"
    title = (f"Quy định xử phạt vi phạm hành chính trong lĩnh vực {t['key']}" if xu_phat
             else f"Quy định chi tiết một số điều về quản lý {t['key']}")
    lines = [
        "CHÍNH PHỦ" if nd else t["co_quan"].upper(),
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "Độc lập - Tự do - Hạnh phúc",
        f"Số: {so}",
        f"Hà Nội, ngày {rng.randint(1, 28)} tháng {rng.randint(1, 12)} năm {year}",
        loai_name,
        title,
        "Căn cứ Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;",
        f"Theo đề nghị của {t['co_quan']};",
        "Chương I",
        "QUY ĐỊNH CHUNG",
    ]
    dieus: list[dict] = []
    n = 0

    def add_dieu(name: str, khoans: list[str | tuple[str, list[str]]], kind: str, phrases: list[str]):
        nonlocal n
        n += 1
        lines.append(f"Điều {n}. {name}")
        for k_i, k in enumerate(khoans, start=1):
            if isinstance(k, tuple):
                lines.append(f"{k_i}. {k[0]}")
                for p_i, p in enumerate(k[1]):
                    lines.append(f"{chr(ord('a') + p_i)}) {p}")
            else:
                lines.append(f"{k_i}. {k}")
        dieus.append({"dieu": n, "name": name, "kind": kind, "phrases": phrases})

    add_dieu("Phạm vi điều chỉnh", [f"{loai_name.capitalize()} này {title[0].lower() + title[1:]}."], "khac", [])
    add_dieu("Đối tượng áp dụng", [f"{loai_name.capitalize()} này áp dụng đối với {t['subj']} và cơ quan, tổ chức có liên quan."], "khac", [])
    d_term, d_def = rng.choice(t["defs"])
    add_dieu("Giải thích từ ngữ", [(f"Trong {loai_name.lower()} này, các từ ngữ dưới đây được hiểu như sau:", [f"{d_term} là {d_def}."])], "dinh_nghia", [d_term.lower()])
    lines += ["Chương II", "QUY ĐỊNH CỤ THỂ"]
    duty_dieu: dict[tuple[str, str], int] = {}
    for _ in range(rng.randint(8, 26)):
        r = rng.random()
        if r < 0.55:
            acts = rng.sample(t["acts"], k=min(len(t["acts"]), rng.randint(1, 3)))
            khoans: list = []
            ph = []
            for a, o in acts:
                khoans.append(f"{t['subj'].capitalize()} phải {a} {o}{rng.choice(TAILS)}.")
                ph.append(f"{a} {o}")
            if rng.random() < 0.4:
                khoans.append(rng.choice(FILL))
            a0, o0 = acts[0]
            add_dieu(f"Trách nhiệm {a0} {o0}", khoans, "nghia_vu", ph)
            for a, o in acts:
                duty_dieu.setdefault((a, o), n)
        elif r < 0.7:
            bans = rng.sample(t["bans"], k=min(len(t["bans"]), 2))
            add_dieu("Các hành vi bị nghiêm cấm", [f"Nghiêm cấm {b}." for b in bans], "cam", bans)
        elif r < 0.85:
            a, o = rng.choice(t["acts"])
            add_dieu(f"Điều kiện {a} {o}", [(f"{t['subj'].capitalize()} phải đáp ứng các điều kiện sau đây:",
                                               ["Có hồ sơ hợp lệ theo quy định;", "Có đủ nhân sự chuyên trách;"])],
                     "dieu_kien", [f"điều kiện {a} {o}"])
        else:
            add_dieu("Quyền của tổ chức, cá nhân", [f"{t['subj'].capitalize()} có quyền đề nghị cơ quan có thẩm quyền hướng dẫn.", rng.choice(FILL)], "quyen", [])
    if xu_phat:
        lines += ["Chương III", "HÀNH VI VI PHẠM, HÌNH THỨC XỬ PHẠT"]
        for (a, o), dd in list(duty_dieu.items())[:6]:
            lo, hi = _money(rng)
            add_dieu(f"Vi phạm quy định về {a} {o}",
                     [(f"Phạt tiền từ {lo}.000.000 đồng đến {hi}.000.000 đồng đối với một trong các hành vi sau đây:",
                       [f"Không {a} {o} theo quy định tại Điều {dd} {loai_name.capitalize()} này;",
                        f"{a.capitalize()} {o} không đúng thời hạn quy định."]),
                      f"Biện pháp khắc phục hậu quả: Buộc {a} {o} theo quy định."],
                     "che_tai", [f"không {a} {o}", f"phạt {a} {o}"])
    lines += ["Chương IV", "ĐIỀU KHOẢN THI HÀNH"]
    add_dieu("Hiệu lực thi hành", [f"{loai_name.capitalize()} này có hiệu lực từ ngày 01 tháng 7 năm {year}."], "khac", [])
    add_dieu("Trách nhiệm thi hành", ["Các Bộ trưởng, Thủ trưởng cơ quan ngang bộ chịu trách nhiệm thi hành."], "khac", [])
    lines += ["Nơi nhận:", "- Như Điều " + str(n) + ";", "- Lưu: VT.", "TM. CHÍNH PHỦ" if nd else "KT. BỘ TRƯỞNG", "THỦ TƯỚNG" if nd else "THỨ TRƯỞNG"]
    return {"so_hieu": so, "topic": t["key"], "xu_phat": xu_phat, "lines": lines, "dieus": dieus}


def write_docx(lines: list[str], path: Path) -> None:
    d = Document()
    for ln in lines:
        p = d.add_paragraph(ln)
        if ln.startswith("Điều ") or ln.isupper():
            for r in p.runs:
                r.bold = True
    d.save(str(path))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--pdf-text", type=int, default=40, help="số văn bản đưa sang PDF chữ")
    ap.add_argument("--pdf-scan", type=int, default=12, help="số văn bản đưa sang PDF scan")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = Path(a.out)
    (out / "scale" / "docx").mkdir(parents=True, exist_ok=True)
    (out / "scale" / "_pdf_src").mkdir(parents=True, exist_ok=True)
    manifest = []
    for i in range(a.n):
        doc = gen_doc(rng, i)
        if i < a.pdf_text:
            fmt = "pdf_text"
        elif i < a.pdf_text + a.pdf_scan:
            fmt = "pdf_scan"
        else:
            fmt = "docx"
        name = f"vb{i + 1:04d}"
        folder = out / "scale" / ("docx" if fmt == "docx" else "_pdf_src")
        write_docx(doc["lines"], folder / f"{name}.docx")
        manifest.append({"file": name, "fmt": fmt, **{k: doc[k] for k in ("so_hieu", "topic", "xu_phat", "dieus")}})
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{a.n} văn bản -> {out}")


if __name__ == "__main__":
    main()
