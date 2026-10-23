"""Nạp 21 văn bản thật (chinhphu.vn) vào kho mới, đo từng file, ghi thống kê cấu trúc/OCR."""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
P = Path(sys.argv[1])  # .../realdocs
data = P / "data"
import os  # noqa: E402

os.environ["SOILUAT_DATA"] = str(data)
from soiluat.db import connect, init_schema  # noqa: E402
from soiluat.importer import import_one  # noqa: E402

data.mkdir(parents=True, exist_ok=True)
conn = connect(data / "soiluat.db")
init_schema(conn)
man = {m["file"]: m for m in json.load(open(P / "manifest.json", encoding="utf-8"))}
out = []
T0 = time.perf_counter()
for f in sorted((P / "files").glob("*.pdf")):
    t = time.perf_counter()
    st, note = import_one(conn, f, data, ocr=True, doan=False)
    sec = time.perf_counter() - t
    d = conn.execute("SELECT * FROM documents WHERE file_path LIKE ? ORDER BY id DESC LIMIT 1", ("%" + f.name,)).fetchone()
    rec = {"file": f.name, "so_hieu_that": man[f.name]["so_hieu"], "trang_thai": st, "ghi_chu": note, "giay": round(sec, 1)}
    if d:
        pages = conn.execute("SELECT kind, ocr_status, ocr_conf FROM pages WHERE doc_id = ?", (d["id"],)).fetchall()
        lv = dict(conn.execute("SELECT level, COUNT(*) FROM units WHERE doc_id = ? GROUP BY level", (d["id"],)).fetchall())
        labels = dict(conn.execute("SELECT l.label, COUNT(*) FROM unit_labels l JOIN units u ON u.id = l.unit_id"
                                   " WHERE u.doc_id = ? GROUP BY l.label", (d["id"],)).fetchall())
        confs = [p["ocr_conf"] for p in pages if p["ocr_conf"] is not None]
        rec.update(so_hieu_doc=d["so_hieu"], loai=d["loai"], co_quan=d["co_quan"], ngay_ban_hanh=d["ngay_ban_hanh"], ngay_hieu_luc=d["ngay_hieu_luc"],
                   cach_trich=d["extraction_method"], diem_cau_truc=d["struct_score"], so_trang=len(pages),
                   trang_ocr=sum(1 for p in pages if p["kind"] != "text"), ocr_conf_tb=round(sum(confs) / len(confs), 1) if confs else None,
                   don_vi=lv, nhan=labels)
    out.append(rec)
    print(json.dumps(rec, ensure_ascii=False), flush=True)
print(f"TỔNG {len(out)} file trong {time.perf_counter() - T0:.0f} s")
json.dump(out, open(P / "import_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
