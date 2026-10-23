"""Nhúng (bằng đúng code app, semantic.embed_roots) các Điều mà bước xếp lại sẽ chạm tới cho tập câu hỏi.

python bench/zalo/embed_needed.py ZALO_DIR DATA_DIR [test|train]

Xếp lại chỉ đụng TOP Điều đầu của BM25, nên nhúng đúng những Điều đó cho kết quả y như nhúng cả kho
(cả kho 61 nghìn Điều mất ~3,8 giờ ở 2 luồng, 128 token). Cần SOILUAT_MODEL_DIR và onnxruntime/tokenizers/numpy.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from soiluat import semantic  # noqa: E402
from soiluat.db import connect, init_schema  # noqa: E402
from soiluat.search import cascade_search  # noqa: E402


def main(zalo: Path, data: Path, split: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    conn = connect(data / "soiluat.db")
    init_schema(conn)
    qs = {d["_id"]: d["text"] for d in map(json.loads, open(zalo / "queries.jsonl", encoding="utf-8"))}
    qids = sorted({json.loads(x)["query-id"] for x in open(zalo / f"qrels_{split}.jsonl", encoding="utf-8")})
    os.environ["SOILUAT_SEMANTIC"] = "0"  # lấy thứ tự BM25 thuần
    need: dict[int, None] = {}
    for q in qids:
        ids = cascade_search(conn, qs[q]).ids
        roots = semantic.root_ids(conn, ids)
        for r in list(dict.fromkeys(roots[i] for i in ids if i in roots))[:semantic.TOP]:
            need[r] = None
    del os.environ["SOILUAT_SEMANTIC"]
    have = {r[0] for r in conn.execute("SELECT unit_id FROM unit_vectors WHERE model = ?", (semantic.MODEL_NAME,))}
    todo = [r for r in need if r not in have]
    print(f"{len(qids)} câu, {len(need)} Điều cần, {len(todo)} chưa có vector", flush=True)
    enc = semantic.encoder()
    assert enc is not None, f"không nạp được mô hình ở {semantic.model_dir()}"
    t0 = time.perf_counter()

    def tick(done: int, total: int, sec: float) -> None:
        if done % 640 == 0 or done == total:
            print(f"  {done}/{total} Điều, {sec:.0f} s, {done / sec:.2f} Điều/s", flush=True)

    sec = semantic.embed_roots(conn, enc, todo, progress=tick)
    print(f"xong: {len(todo)} Điều trong {sec:.0f} s ({len(todo) / max(sec, 1e-9):.2f} Điều/s, "
          f"{semantic.THREADS} luồng); tổng {time.perf_counter() - t0:.0f} s")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "test")
