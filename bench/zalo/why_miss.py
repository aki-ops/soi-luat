"""Câu cách hiện tại trượt: trượt ở khâu nào (rút câu hỏi / tầng AND / xếp thẻ)?

python bench/zalo/why_miss.py ZALO_DIR DATA_DIR [--limit N]
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from eval import Kho, bm25_or, connect  # noqa: E402

from soiluat.cards import assemble_cards  # noqa: E402
from soiluat.query import classify_query, strip_question  # noqa: E402
from soiluat.search import cascade_search  # noqa: E402


def main(zalo: Path, data: Path, limit: int | None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    qs = {d["_id"]: d["text"] for d in map(json.loads, open(zalo / "queries.jsonl", encoding="utf-8"))}
    rel: dict[str, set[str]] = defaultdict(set)
    for d in map(json.loads, open(zalo / "qrels_test.jsonl", encoding="utf-8")):
        rel[d["query-id"]].add(d["corpus-id"].lower())
    kho = Kho(connect(data / "soiluat.db"))
    why = Counter()
    shown = 0
    for qid in sorted(rel)[:limit] if limit else sorted(rel):
        q, want = qs[qid], rel[qid]
        q_use = strip_question(q) if classify_query(q) == "question" else q
        r = cascade_search(kho.conn, q_use)
        keys_hit = {kho.key(i) for i in r.ids}
        cards = assemble_cards(kho.conn, r.ids, synonym_note=r.note, fold_ids=set(r.fold_ids), f2_ids=set(r.f2_ids),
                               tiers=r.tiers, intent=r.intent)
        order = []
        for c in cards:
            k = kho.key(c.unit_ids[0]) if c.unit_ids else None
            if k and k not in order:
                order.append(k)
        pos = next((i for i, k in enumerate(order, 1) if k in want), None)
        if pos and pos <= 10:
            continue
        b = bm25_or(kho, q, cols=("search_accent", "context_accent"), fold=False, weights=(1, 1, 1, 1, 0.3))
        if not r.ids:
            cause = "0 kết quả (AND rỗng mọi tầng)"
        elif not (keys_hit & want):
            cause = f"tầng {r.tier} khớp được nhưng không chứa Điều đáp án ({len(r.ids)} đơn vị, trần 50/tầng)"
        else:
            cause = f"có trong kết quả nhưng xếp thẻ đẩy xuống hạng {pos}"
        why[cause.split(" (")[0].split(" hạng")[0]] += 1
        if shown < 12:
            shown += 1
            bpos = next((i for i, k in enumerate(b, 1) if k in want), None)
            print(f"- {q}\n    rút gọn: «{q_use}» | tầng {r.tier} | {cause} | BM25: {bpos}")
    print("\nNguyên nhân trượt:", dict(why))


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    main(Path(sys.argv[1]), Path(sys.argv[2]), lim)
