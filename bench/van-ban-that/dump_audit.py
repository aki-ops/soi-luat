"""Sau khi nạp: (1) đo độ đúng OCR trên 84 câu bằng chứng (chép tay từ ảnh scan) so với chữ OCR của đúng trang;
(2) xuất mỗi văn bản một file JSON (siêu dữ liệu, danh sách Điều đã tách, chữ OCR các trang mẫu) cho agent kiểm tra.

python dump_audit.py REALDOCS
"""
import difflib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from soiluat.db import connect  # noqa: E402
from soiluat.fold import fold_search  # noqa: E402

P = Path(sys.argv[1])
conn = connect(P / "data" / "soiluat.db")
man = {m["file"]: m for m in json.load(open(P / "manifest.json", encoding="utf-8"))}
qs = json.load(open(P / "queries.json", encoding="utf-8"))
out_dir = P / "audit"
out_dir.mkdir(exist_ok=True)


def best_window(needle: str, hay: str) -> float:
    """Độ giống ký tự (0..1) giữa câu bằng chứng và đoạn khớp nhất trong chữ OCR (cùng độ dài, so có dấu, bỏ khoảng trắng thừa)."""
    n, h = " ".join(needle.split()).lower(), " ".join(hay.split()).lower()
    if not n or not h:
        return 0.0
    sm = difflib.SequenceMatcher(None, h, n, autojunk=False)
    m = max(sm.get_matching_blocks(), key=lambda b: b.size)
    best = 0.0
    for start in range(max(0, m.a - m.b - 40), max(1, m.a - m.b + 41), 4):  # trượt quanh khối khớp dài nhất
        best = max(best, difflib.SequenceMatcher(None, h[start:start + len(n)], n, autojunk=False).ratio())
    return best


docs = {Path(r["file_path"]).name: r for r in conn.execute("SELECT * FROM documents")}
ocr_rows = []
for q in qs:
    d = docs.get(q["file"])
    pg = conn.execute("SELECT raw_text FROM pages WHERE doc_id = ? AND page_no = ?", (d["id"], q["page"])).fetchone() if d else None
    ev = q["evidence"].replace("...", " ").replace("…", " ")
    parts = [p.strip() for p in ev.split("  ") if len(p.strip()) > 15] or [ev]
    sim = sum(best_window(p, pg[0] or "") * len(p) for p in parts) / sum(len(p) for p in parts) if pg else 0.0
    exact = bool(pg) and fold_search(" ".join(parts[0].split()))[:40] in fold_search(" ".join((pg[0] or "").split()))
    ocr_rows.append({"file": q["file"], "page": q["page"], "giong": round(sim, 3), "khop_bo_dau_40kt": exact})
sims = sorted(r["giong"] for r in ocr_rows)
print(json.dumps({"ocr_bang_chung": len(sims), "giong_tb": round(sum(sims) / len(sims), 3), "giong_trung_vi": sims[len(sims) // 2],
                  "duoi_0.9": sum(s < .9 for s in sims), "duoi_0.8": sum(s < .8 for s in sims),
                  "khop_bo_dau": sum(r["khop_bo_dau_40kt"] for r in ocr_rows)}, ensure_ascii=False))
json.dump(ocr_rows, open(P / "ocr_bang_chung.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for name, d in docs.items():
    pages = conn.execute("SELECT page_no, kind, ocr_conf, raw_text FROM pages WHERE doc_id = ? ORDER BY page_no", (d["id"],)).fetchall()
    roots = conn.execute("SELECT path, level, title, page_from, page_to, normalized_text FROM units WHERE doc_id = ? AND parent_id IS NULL ORDER BY id",
                         (d["id"],)).fetchall()
    lv = dict(conn.execute("SELECT level, COUNT(*) FROM units WHERE doc_id = ? GROUP BY level", (d["id"],)).fetchall())
    sample = sorted({1, *(q["page"] for q in qs if q["file"] == name)})
    json.dump({
        "file": name, "pdf": str(P / "files" / name), "that": {"so_hieu": man[name]["so_hieu"], "trich_yeu": man[name].get("trich_yeu")},
        "doc": {k: d[k] for k in ("so_hieu", "loai", "co_quan", "ngay_ban_hanh", "ngay_hieu_luc", "struct_score",
                                  "fallback_doan", "multi_document_suspected", "extraction_method")},
        "so_trang": len(pages), "ocr_conf_tung_trang": {p["page_no"]: p["ocr_conf"] for p in pages},
        "so_don_vi_theo_cap": lv,
        "dieu_da_tach": [{"path": r["path"], "level": r["level"], "title": r["title"], "trang": [r["page_from"], r["page_to"]],
                          "dau": (r["normalized_text"] or "")[:140]} for r in roots],
        "chu_ocr_trang_mau": {p["page_no"]: (p["raw_text"] or "")[:4000] for p in pages if p["page_no"] in sample},
        "cau_hoi": [q for q in qs if q["file"] == name],
    }, open(out_dir / (Path(name).stem + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("xuat", len(docs), "file vao", out_dir)
