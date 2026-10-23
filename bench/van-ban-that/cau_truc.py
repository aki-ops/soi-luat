"""Đếm Điều tách được so với số Điều thật (dieu_that.json, đếm trên bản scan, không tính Điều được trích dẫn).

python cau_truc.py DATA_DIR
"Khớp" = có đơn vị gốc D<n> (không hậu tố ~) với 1 ≤ n ≤ số Điều thật; không xét trang (thô hơn cách đếm của agent).
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from soiluat.db import connect  # noqa: E402

that = json.load(open(Path(__file__).with_name("dieu_that.json"), encoding="utf-8"))
conn = connect(Path(sys.argv[1]) / "soiluat.db")
tong_that = tong_khop = tong_thua = 0
for d in conn.execute("SELECT id, file_path, so_hieu FROM documents ORDER BY file_path"):
    name = Path(d[1]).name
    paths = [r[0] for r in conn.execute("SELECT path FROM units WHERE doc_id = ? AND parent_id IS NULL AND level = 'dieu'", (d[0],))]
    doan = conn.execute("SELECT COUNT(*) FROM units WHERE doc_id = ? AND level = 'doan'", (d[0],)).fetchone()[0]
    nums = {int(m.group(1)) for p in paths if (m := re.fullmatch(r"D(\d+)", p))}
    n = that[name]
    khop = sum(1 for k in nums if 1 <= k <= n)
    thua = len(paths) - khop
    tong_that, tong_khop, tong_thua = tong_that + n, tong_khop + khop, tong_thua + thua
    print(f"{name:22} that={n:3} khop={khop:3} thua={thua:2} doan={doan:3} so_hieu={d[2]}")
print(f"TONG that={tong_that} khop={tong_khop} ({tong_khop / tong_that:.0%}) thua={tong_thua}")
