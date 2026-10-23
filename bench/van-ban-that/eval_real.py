"""Chấm tìm kiếm trên kho văn bản thật: 84 câu đã kiểm chứng (realdocs/queries.json).

python eval_real.py REALDOCS normal|advance
Trúng (rộng): thẻ cùng file và (Điều ∈ {dieu_doc, dieu_quoted, also_ok} hoặc trang thẻ phủ trang bằng chứng).
Trúng (chặt): chỉ tính Điều. Hạng = vị trí thẻ (như người dùng thấy), không gộp.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
P, MODE = Path(sys.argv[1]), sys.argv[2]
os.environ["SOILUAT_DATA"] = str(P / "data")
from soiluat import semantic  # noqa: E402
from soiluat.cards import assemble_cards  # noqa: E402
from soiluat.db import connect  # noqa: E402
from soiluat.search import DIEU_CAP, cascade_search  # noqa: E402

DIEU = re.compile(r"^D(\d+)", re.I)
conn = connect(P / "data" / "soiluat.db")
semantic.set_mode(conn, MODE)
qs = json.load(open(P / "queries.json", encoding="utf-8"))


def cards_for(q):
    r = cascade_search(conn, q)
    ids = r.ids[:DIEU_CAP] if r.note == "dieu" else r.ids
    idset = set(ids)
    return assemble_cards(conn, ids, synonym_note=r.note, fold_ids={i for i in r.fold_ids if i in idset},
                          f2_ids={i for i in r.f2_ids if i in idset}, tiers=r.tiers, intent=r.intent)


def dieu_of(c):
    row = conn.execute("SELECT path FROM units WHERE id = ?", (c.unit_ids[0],)).fetchone() if c.unit_ids else None
    m = DIEU.match(row[0]) if row else None
    return m.group(1) if m else None


if MODE == "advance":  # nạp mô hình trước, không tính vào độ trễ câu đầu
    cards_for("khởi động")
out, lat = [], []
for q in qs:
    ok_dieu = {x for x in [q["dieu_doc"], q["dieu_quoted"], *q.get("also_ok", [])] if x}
    t = time.perf_counter()
    cs = cards_for(q["q"])
    lat.append((time.perf_counter() - t) * 1000)
    loose = strict = None
    for k, c in enumerate(cs, 1):
        if Path(c.file_path).name != q["file"]:
            continue
        d = dieu_of(c)
        pf, pt = c.page_from, c.page_to or c.page_from
        if strict is None and d in ok_dieu:
            strict = k
        if loose is None and (d in ok_dieu or (pf is not None and pf <= q["page"] <= pt)):
            loose = k
    file_rank = next((k for k, c in enumerate(cs, 1) if Path(c.file_path).name == q["file"]), None)
    out.append({**{k: q[k] for k in ("file", "kind", "q", "dieu_doc", "page")}, "rong": loose, "chat": strict,
                "file_dau": file_rank, "so_the": len(cs), "ms": round(lat[-1])})


def hit(key, sub=None):
    v = [o[key] for o in out if sub is None or o["kind"] == sub]
    return {k: round(sum(1 for r in v if r and r <= k) / len(v) * 100, 1) for k in (1, 3, 5, 10)}


lat.sort()
rep = {"mode": MODE, "so_cau": len(out), "rong": hit("rong"), "chat": hit("chat"),
       "rong_tu_khoa": hit("rong", "tu_khoa"), "rong_cau_hoi": hit("rong", "cau_hoi"), "dung_file_top1": hit("file_dau")[1],
       "p50_ms": round(lat[len(lat) // 2]), "p95_ms": round(lat[int(len(lat) * .95)]),
       "the_tb": round(sum(o["so_the"] for o in out) / len(out), 1)}
print(json.dumps(rep, ensure_ascii=False))
json.dump({"tong": rep, "tung_cau": out}, open(P / f"eval_{MODE}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
