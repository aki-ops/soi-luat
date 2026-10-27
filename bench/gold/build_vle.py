"""Dựng bộ gold câu hỏi thật từ ViLegalExperts (tư vấn luật thật, 09/2026) ánh xạ vào kho Zalo.

python -I bench/gold/build_vle.py ZALO_DIR VLE_DIR OUT_DIR [--n 500]

ZALO_DIR: corpus_test-00000-of-00001.parquet + queries.jsonl (GreenNode/zalo-ai-legal-text-retrieval-vn).
VLE_DIR: test_data.json, dev_data.json (HF DatNguyenAIML/ViLegalExperts, QA_single_context).
OUT_DIR: ghi queries.jsonl + qrels_gold.jsonl cùng định dạng GreenNode, để chạy
    python bench/zalo/eval.py OUT_DIR <data Zalo> gold
Dữ liệu ViLegalExperts chưa ghi giấy phép: chỉ ghi ra OUT_DIR (ngoài repo), không commit.

Giữ một câu khi: trả lời dẫn đúng 1 văn bản và đúng 1 số Điều; văn bản có trong kho Zalo; đoạn trích trong
câu trả lời trùng ≥ 40% bộ 3-từ của Điều đó trong kho (cùng phiên bản, không lệch số Điều); câu hỏi không
gần trùng (≥ 50% bộ 8-từ) câu nào của Zalo; không trùng câu đã giữ.
"""

from __future__ import annotations

import json
import random
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

DIEU = re.compile(r"Điều\s+(\d+[a-z]?)\b")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s).lower()).strip()


def grams(s: str, n: int) -> set[str]:
    w = re.findall(r"\w+", norm(s))
    return {" ".join(w[i:i + n]) for i in range(max(1, len(w) - n + 1))}


def main(zalo: Path, vle: Path, out: Path, n: int) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    corpus = pd.read_parquet(zalo / "corpus_test-00000-of-00001.parquet")
    text = dict(zip(corpus.id, corpus.text))
    laws = set(corpus.id.str.rsplit("+", n=1).str[0])
    zq8 = set()
    for d in map(json.loads, open(zalo / "queries.jsonl", encoding="utf-8")):
        zq8 |= grams(d["text"], 8)
    seen: set[str] = set()
    keep: list[dict] = []
    stats = dict.fromkeys(("tong", "mot_vb", "co_trong_kho", "mot_dieu", "trich_khop", "khong_gan_zalo"), 0)
    for split in ("test", "dev"):
        for key, x in json.load(open(vle / f"{split}_data.json", encoding="utf-8")).items():
            stats["tong"] += 1
            ctx = list(x["contexts"].values())
            if len(ctx) != 1:
                continue
            stats["mot_vb"] += 1
            law = (ctx[0].get("Số hiệu:") or "").strip().lower()
            if law not in laws:
                continue
            stats["co_trong_kho"] += 1
            ds = set(DIEU.findall(x["answer"]))
            cid = f"{law}+{next(iter(ds))}" if len(ds) == 1 else None
            if cid not in text:
                continue
            stats["mot_dieu"] += 1
            art = grams(text[cid], 3)
            if not art or len(art & grams(x["answer"], 3)) / len(art) < 0.4:
                continue
            stats["trich_khop"] += 1
            q = x["question"].strip()
            g8 = grams(q, 8)
            if len(g8 & zq8) / len(g8) >= 0.5 or norm(q) in seen:
                continue
            stats["khong_gan_zalo"] += 1
            seen.add(norm(q))
            keep.append({"_id": f"vle-{split}-{key}", "text": q, "dap_an": cid, "link": x.get("link", "")})
    random.Random(2026).shuffle(keep)
    keep = sorted(keep[:n], key=lambda d: d["_id"])
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "queries.jsonl", "w", encoding="utf-8") as fq, open(out / "qrels_gold.jsonl", "w", encoding="utf-8") as fr:
        for d in keep:
            fq.write(json.dumps({"_id": d["_id"], "text": d["text"], "link": d["link"]}, ensure_ascii=False) + "\n")
            fr.write(json.dumps({"query-id": d["_id"], "corpus-id": d["dap_an"], "score": 1}, ensure_ascii=False) + "\n")
    print(stats, "→ ghi", len(keep), "câu vào", out)


if __name__ == "__main__":
    a = [x for i, x in enumerate(sys.argv[1:], 1) if not x.startswith("--") and sys.argv[i - 1] != "--n"]
    main(Path(a[0]), Path(a[1]), Path(a[2]), int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 500)
