"""Đo tìm kiếm trên câu hỏi thật Zalo AI 2021 Legal: cách hiện tại vs BM25 OR.

python bench/zalo/eval.py ZALO_DIR DATA_DIR [test|train] [--limit N]

Một câu "đúng" khi Điều đáp án (mã văn bản + số Điều) nằm trong 10 kết quả đầu (đơn vị gom theo Điều).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from soiluat.cards import assemble_cards  # noqa: E402
from soiluat.db import connect  # noqa: E402
from soiluat.fold import fold_search, search_accent  # noqa: E402
from soiluat.query import classify_query, strip_question  # noqa: E402
from soiluat.search import DIEU_CAP, cascade_search  # noqa: E402

K = 10
DIEU = re.compile(r"^D(\d+[a-z]?)", re.I)
# thứ tự cột units_fts: title_search, search_accent, search_text, context_search, context_accent
COLS = ("title_search", "search_accent", "search_text", "context_search", "context_accent")


class Kho:
    def __init__(self, conn):
        self.conn = conn
        self.law = {r[0]: r[1] for r in conn.execute("SELECT id, file_path FROM documents")}
        self.n_units = conn.execute("SELECT COUNT(*) FROM units").fetchone()[0]
        self._df: dict[tuple[str, str], int] = {}

    def key(self, unit_id: int) -> str | None:
        r = self.conn.execute("SELECT doc_id, path FROM units WHERE id = ?", (unit_id,)).fetchone()
        m = DIEU.match(r[1] or "") if r else None
        return f"{self.law[r[0]]}+{m.group(1).lower()}" if m else None

    def df(self, tok: str, col: str) -> int:
        k = (tok, col)
        if k not in self._df:
            # units_vocab là fts5vocab 'row': số đơn vị chứa từ ở bất kỳ cột nào
            r = self.conn.execute("SELECT doc FROM units_vocab WHERE term = ?", (tok,)).fetchone()
            self._df[k] = int(r[0]) if r else 0
        return self._df[k]


def current(kho: Kho, q: str) -> list[str]:
    """Đúng như app._search_ctx (không bộ lọc)."""
    conn = kho.conn
    r = cascade_search(conn, q)  # như app._search_ctx: nguyên câu hỏi
    ids = r.ids[:DIEU_CAP] if r.note == "dieu" else r.ids
    idset = set(ids)
    cards = assemble_cards(conn, ids, synonym_note=r.note, fold_ids={i for i in r.fold_ids if i in idset},
                           f2_ids={i for i in r.f2_ids if i in idset}, tiers=r.tiers, intent=r.intent)
    out: list[str] = []
    for c in cards:
        k = kho.key(c.unit_ids[0]) if c.unit_ids else None
        if k and k not in out:
            out.append(k)
        if len(out) == K:
            break
    return out


def words(q: str, fold: bool) -> list[str]:
    s = fold_search(q) if fold else search_accent(q)
    return list(dict.fromkeys(w for w in re.findall(r"\w+", s) if w))


def bm25_or(kho: Kho, q: str, *, cols: tuple[str, ...], fold: bool, prune: float | None = None,
            weights: tuple[float, ...] = (1, 1, 1, 1, 1)) -> list[str]:
    toks = words(q, fold)
    if prune is not None:  # bỏ từ có mặt ở quá nhiều đơn vị (dựa trên dữ liệu, không phải danh sách tay)
        col = cols[0]
        kept = [t for t in toks if kho.df(t, col) <= prune * kho.n_units]
        toks = kept or toks
    if not toks:
        return []
    expr = "{" + " ".join(cols) + "} : (" + " OR ".join('"' + t.replace('"', '""') + '"' for t in toks) + ")"
    rows = kho.conn.execute(
        f"SELECT rowid FROM units_fts WHERE units_fts MATCH ? ORDER BY bm25(units_fts, {','.join(map(str, weights))}) LIMIT 300",
        (expr,),
    ).fetchall()
    out: list[str] = []
    for (uid,) in rows:
        k = kho.key(uid)
        if k and k not in out:
            out.append(k)
            if len(out) == K:
                break
    return out


METHODS = {
    "hien_tai": current,
    "bm25_or_codau": lambda kho, q: bm25_or(kho, q, cols=("search_accent",), fold=False),
    "bm25_or_codau_bo_tu_tren_20pct": lambda kho, q: bm25_or(kho, q, cols=("search_accent",), fold=False, prune=0.20),
    "bm25_or_codau_bo_tu_tren_35pct": lambda kho, q: bm25_or(kho, q, cols=("search_accent",), fold=False, prune=0.35),
    "bm25_or_codau_kem_ngucanh": lambda kho, q: bm25_or(
        kho, q, cols=("search_accent", "context_accent"), fold=False, weights=(1, 1, 1, 1, 0.3)),
    "bm25_or_khongdau": lambda kho, q: bm25_or(kho, q, cols=("search_text",), fold=True),
}


def main(zalo: Path, data: Path, split: str, limit: int | None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    qs = {d["_id"]: d["text"] for d in map(json.loads, open(zalo / "queries.jsonl", encoding="utf-8"))}
    rel: dict[str, set[str]] = defaultdict(set)
    for d in map(json.loads, open(zalo / f"qrels_{split}.jsonl", encoding="utf-8")):
        rel[d["query-id"]].add(d["corpus-id"].lower())
    qids = sorted(rel)[:limit] if limit else sorted(rel)
    kho = Kho(connect(data / "soiluat.db"))
    report: dict[str, dict] = {}
    per_q: dict[str, dict] = {}
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    for name, fn in METHODS.items():
        if only and name not in only:
            continue
        hit = rr = rec = zero = 0.0
        lat: list[float] = []
        for qid in qids:
            q = qs[qid]
            t = time.perf_counter()
            got = fn(kho, q)
            lat.append((time.perf_counter() - t) * 1000)
            want = rel[qid]
            ranks = [i for i, k in enumerate(got, start=1) if k in want]
            hit += bool(ranks)
            rr += 1 / ranks[0] if ranks else 0
            rec += len(set(got) & want) / len(want)
            zero += not got
            per_q.setdefault(qid, {"q": q, "dap_an": sorted(want)})[name] = ranks[0] if ranks else None
        n = len(qids)
        lat.sort()
        report[name] = {
            "Hit@10": round(hit / n, 3), "Recall@10": round(rec / n, 3), "MRR@10": round(rr / n, 3),
            "khong_ket_qua": round(zero / n, 3), "p50_ms": round(lat[n // 2]), "p95_ms": round(lat[int(n * 0.95)]),
        }
        print(name, report[name], flush=True)
    out = Path(__file__).parent / f"ket_qua_{split}{'_' + sys.argv[sys.argv.index('--tag') + 1] if '--tag' in sys.argv else ''}.json"
    out.write_text(json.dumps({"so_cau": len(qids), "phuong_phap": report, "tung_cau": per_q},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("ghi", out)


if __name__ == "__main__":
    flags = {"--limit", "--only", "--tag"}
    a = [x for i, x in enumerate(sys.argv[1:], 1) if not x.startswith("--") and sys.argv[i - 1] not in flags]
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    main(Path(a[0]), Path(a[1]), a[2] if len(a) > 2 else "test", lim)
