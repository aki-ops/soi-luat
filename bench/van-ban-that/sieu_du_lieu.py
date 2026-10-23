"""So siêu dữ liệu đã nạp (import_result.json) với giá trị thật đọc trên bản scan (agent kiểm lần 1, đã phản biện).

python sieu_du_lieu.py DATA_DIR   (kho đã nạp từ import_real.py; manifest.json cùng thư mục với script)
Cơ quan thật suy từ đuôi số hiệu; so không phân biệt dấu/hoa thường (OCR hay đọc QUÓC thay QUỐC).
"""
import json
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
CO_QUAN = {"QH16": "QUỐC HỘI", "NĐ-CP": "CHÍNH PHỦ", "QĐ-TTg": "THỦ TƯỚNG CHÍNH PHỦ", "TT-BTC": "BỘ TÀI CHÍNH",
           "TT-BNV": "BỘ NỘI VỤ", "TT-BKHCN": "BỘ KHOA HỌC VÀ CÔNG NGHỆ", "TT-BGDĐT": "BỘ GIÁO DỤC VÀ ĐÀO TẠO"}
LUAT = "2026-08-24"  # ngày Quốc hội thông qua cả 7 luật
BAN_HANH = {"154": "2026-10-15", "155": "2026-10-16", "156": "2026-10-20", "26": "2026-10-15", "27": "2026-10-20",
            "61": "2026-10-15", "89": "2026-10-16", "384": "2026-10-09", "385": "2026-10-09", "388": "2026-10-13",
            "389": "2026-10-14", "390": "2026-10-16", "391": "2026-10-20", "48": "2026-10-09"}
HIEU_LUC = {"18": "2026-10-01", "17": "2027-03-01", "19": "2027-03-01", "21": "2027-01-01", "22": "2027-03-01",
            "23": "2026-12-01", "24": "2027-03-01", "154": "2027-01-01", "155": "2026-12-01", "156": "2026-11-01",
            "26": "2026-11-29", "27": "2027-01-01", "61": "2026-12-01", "89": "2026-12-01", "384": "2027-01-01",
            "385": "2026-10-10", "388": "2026-12-01", "389": "2026-11-30", "390": "2026-10-16", "391": "2026-12-05",
            "48": "2027-03-01"}
LOAI = {"QH16": "luat", "NĐ-CP": "nghi_dinh", "QĐ-TTg": "quyet_dinh"}


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").replace("Đ", "D").replace("đ", "d")) if not unicodedata.combining(c)).lower()


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from soiluat.db import connect  # noqa: E402

man = {m["file"]: m["so_hieu"] for m in json.load(open(Path(__file__).with_name("manifest.json"), encoding="utf-8"))}
conn = connect(Path(sys.argv[1]) / "soiluat.db")
rows = [{"file": Path(d["file_path"]).name, "so_hieu_that": man[Path(d["file_path"]).name], "so_hieu_doc": d["so_hieu"], "loai": d["loai"],
         "ngay_ban_hanh": d["ngay_ban_hanh"], "ngay_hieu_luc": d["ngay_hieu_luc"], "co_quan": d["co_quan"]}
        for d in conn.execute("SELECT * FROM documents ORDER BY file_path")]
ok = {k: 0 for k in ("so_hieu", "loai", "ngay_ban_hanh", "ngay_hieu_luc", "co_quan")}
for r in rows:
    n, y, suf = r["so_hieu_that"].split("/")
    cq = CO_QUAN[suf]
    truth = {"so_hieu": r["so_hieu_that"], "loai": LOAI.get(suf, "thong_tu"),
             "ngay_ban_hanh": LUAT if suf == "QH16" else BAN_HANH[n], "ngay_hieu_luc": HIEU_LUC[n], "co_quan": cq}
    got = {"so_hieu": r.get("so_hieu_doc"), "loai": r.get("loai"), "ngay_ban_hanh": r.get("ngay_ban_hanh"),
           "ngay_hieu_luc": r.get("ngay_hieu_luc"), "co_quan": r.get("co_quan")}
    bad = []
    for k in ok:
        same = fold(got[k]) == fold(truth[k]) if k == "co_quan" else got[k] == truth[k]
        ok[k] += same
        if not same:
            bad.append(f"{k}: {got[k]!r} (đúng {truth[k]!r})")
    print(f"{Path(r['file']).name:22} " + ("OK" if not bad else " | ".join(bad)))
print({k: f"{v}/{len(rows)}" for k, v in ok.items()})
