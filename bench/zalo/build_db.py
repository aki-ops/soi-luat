"""Nạp corpus Zalo AI 2021 Legal Text Retrieval vào một kho Soi Luật để đo tìm kiếm.

python bench/zalo/build_db.py ZALO_DIR DATA_DIR

ZALO_DIR chứa corpus_test-00000-of-00001.parquet (tải từ HF GreenNode/zalo-ai-legal-text-retrieval-vn).
Mỗi văn bản (phần trước dấu + của id) ghép lại thành một văn bản "Số: … / Điều n. … " rồi đi qua
đúng đường nạp thật (parse_pages → _store_doc → nhãn, liên kết). file_path = mã văn bản Zalo.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from soiluat.db import connect, init_schema  # noqa: E402
from soiluat.extract import ExtractedPage  # noqa: E402
from soiluat.ingest import _after_units, _store_doc  # noqa: E402


def main(zalo: Path, data: Path) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    data.mkdir(parents=True, exist_ok=True)
    db = data / "soiluat.db"
    if db.exists():
        raise SystemExit(f"{db} đã có — xoá trước khi dựng lại")
    c = pd.read_parquet(zalo / "corpus_test-00000-of-00001.parquet")
    c["law"] = c.id.str.rsplit("+", n=1).str[0]
    c["k"] = pd.to_numeric(c.id.str.rsplit("+", n=1).str[1], errors="coerce")
    conn = connect(db)
    init_schema(conn)
    t0 = time.time()
    laws = c.groupby("law", sort=True)
    for i, (law, g) in enumerate(laws, start=1):
        g = g.sort_values("k")
        body = "\n".join(f"{t}\n{x}" for t, x in zip(g.title, g.text))
        text = f"Số: {law.upper()}\n{body}"
        page = ExtractedPage(page_no=1, text=text, kind="text", extraction_method="text")
        doc_id, so_hieu = _store_doc(conn, None, law, law, [page], False, None)
        _after_units(conn, doc_id, so_hieu)
        if i % 200 == 0:
            conn.commit()
            print(f"{i}/{len(laws)} văn bản, {time.time() - t0:.0f}s", flush=True)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM units").fetchone()[0]
    print(f"Xong {len(laws)} văn bản, {n} đơn vị, {time.time() - t0:.0f}s, DB {db.stat().st_size / 2**20:.0f} MB")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
