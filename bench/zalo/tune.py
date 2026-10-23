"""Chỉnh tham số tìm kiếm trên TẬP TRAIN (không đụng test).

python bench/zalo/tune.py ZALO_DIR DATA_DIR [số câu]
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from eval import Kho, connect, current  # noqa: E402

from soiluat import search  # noqa: E402


def main(zalo: Path, data: Path, n: int) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    qs = {d["_id"]: d["text"] for d in map(json.loads, open(zalo / "queries.jsonl", encoding="utf-8"))}
    rel: dict[str, set[str]] = defaultdict(set)
    for d in map(json.loads, open(zalo / "qrels_train.jsonl", encoding="utf-8")):
        rel[d["query-id"]].add(d["corpus-id"].lower())
    qids = sorted(rel)[:: max(1, len(rel) // n)][:n]  # lấy đều, không chỉ đầu danh sách
    kho = Kho(connect(data / "soiluat.db"))
    grid = [dict(A=2.0, W="1.0, 1.0, 1.0, 0.5, 0.5"), dict(A=2.0, W="1.0, 1.0, 1.0, 0.8, 0.8"), dict(A=1.0, W="1.0, 1.0, 1.0, 0.8, 0.8"), dict(A=2.0, W="1.0, 1.0, 1.0, 1.0, 1.0")]
    base = dict(W=search.BM25_WEIGHTS, BOOST=dict(search.BOOST), A=search.BIGRAM_ALPHA)
    for g in grid:
        search.BM25_WEIGHTS = g.get("W", base["W"])
        search.BOOST = g.get("BOOST", base["BOOST"])
        search.BIGRAM_ALPHA = g.get("A", base["A"])
        hit = rr = 0.0
        lat = []
        for qid in qids:
            t = time.perf_counter()
            got = current(kho, qs[qid])
            lat.append((time.perf_counter() - t) * 1000)
            r = [i for i, k in enumerate(got, 1) if k in rel[qid]]
            hit += bool(r)
            rr += 1 / r[0] if r else 0
        lat.sort()
        print(g, f"Hit@10={hit / len(qids):.3f} MRR={rr / len(qids):.3f} p50={lat[len(lat) // 2]:.0f}ms p95={lat[int(len(lat) * .95)]:.0f}ms", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 150)
