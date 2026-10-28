"""Xếp lại top-5 bằng AITeamVN Vietnamese_Reranker (cross-encoder, ONNX int8, CPU) và đo độ tin cậy.

Chỉ chạy ở chế độ Advance, khi đã cài mô hình (thư mục `aiteamvn-reranker`) và có onnxruntime/tokenizers/numpy;
thiếu thì không làm gì (tìm như trước). Mô hình nạp lười ở lần tìm Advance đầu tiên, một lần mỗi process.
Chấm cặp (câu hỏi, "tiêu đề\\nnội dung Điều"), cắt còn MAXLEN token (cắt phần Điều). `gap` = điểm hạng 1 − điểm hạng 2:
gap ≥ SURE_GAP thì kết quả đầu "độ tin cậy cao".
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from soiluat import semantic
from soiluat.config import data_dir

TOPN = 5  # số Điều đầu được chấm lại; top-10 chỉ hơn 0,5–1,8 điểm Hit@1 mà chậm gấp đôi
MAXLEN = 384  # 192 token không hơn BM25 + vector; 384 là mức đã đo
THREADS = 2
# Ngưỡng cho đúng mô hình này, 384 token, top-5: kiểm chéo giữa Zalo và gold, ~58% số câu vượt ngưỡng với Hit@1 ~93%.
# Đổi mô hình, độ dài hay TOPN thì đo lại.
SURE_GAP = 3.0
PAD_ID = 1  # XLM-R


def model_dir() -> Path:
    raw = os.environ.get("SOILUAT_RERANK_DIR")
    if raw:
        return Path(raw)
    path = data_dir() / "models" / "aiteamvn-reranker"
    if not path.exists() and getattr(sys, "frozen", False):  # bản đóng gói: models\ nằm cạnh SoiLuat.exe
        return Path(sys.executable).resolve().parent / "models" / "aiteamvn-reranker"
    return path


def model_installed() -> bool:
    path = model_dir()
    return (path / "onnx" / "model_int8.onnx").exists() and (path / "tokenizer.json").exists()


class Ranker:
    def __init__(self, path: Path, threads: int | None = None):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads or THREADS
        so.inter_op_num_threads = 1
        so.enable_cpu_mem_arena = False
        so.enable_mem_pattern = False
        self.sess = ort.InferenceSession(str(path / "onnx" / "model_int8.onnx"), so, providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(path / "tokenizer.json"))
        self.tok.enable_truncation(MAXLEN, strategy="only_second")

    def score(self, query: str, docs: list[str]) -> list[float]:
        np = self.np
        enc = self.tok.encode_batch([(query, d) for d in docs])
        n = max(len(e.ids) for e in enc)
        ids = np.full((len(docs), n), PAD_ID, np.int64)
        mask = np.zeros((len(docs), n), np.int64)
        for r, e in enumerate(enc):
            ids[r, :len(e.ids)] = e.ids
            mask[r, :len(e.ids)] = 1
        return self.sess.run(["logits"], {"input_ids": ids, "attention_mask": mask})[0][:, 0].tolist()


_RK: Ranker | None = None
_RK_TRIED = False


def ranker() -> Ranker | None:
    """Nạp lần đầu cần dùng; lỗi/thiếu thì None (một lần mỗi process)."""
    global _RK, _RK_TRIED
    if os.environ.get("SOILUAT_SEMANTIC") == "0":
        return None
    if not _RK_TRIED:
        _RK_TRIED = True
        if model_installed():
            try:
                _RK = Ranker(model_dir())
            except Exception:  # noqa: BLE001 — thiếu thư viện / mô hình hỏng: giữ thứ tự cũ
                _RK = None
    return _RK


def _doc(conn: sqlite3.Connection, root_id: int) -> str:
    title, body = semantic.root_parts(conn, root_id)
    return f"{title}\n{body}" if title else body


def rerank_top(conn: sqlite3.Connection, query: str, ids: list[int]) -> tuple[list[int], float | None]:
    """Xếp lại TOPN Điều gốc đầu của `ids` theo điểm cross-encoder. Trả (ids mới, gap); gap None khi không chấm
    (không phải Advance, thiếu mô hình, hoặc dưới 2 Điều). Khoản/điểm cùng một Điều đi theo Điều; phần sau TOPN giữ nguyên."""
    if not ids or semantic.get_mode(conn) != "advance":
        return ids, None
    rk = ranker()
    if rk is None:
        return ids, None
    roots = semantic.root_ids(conn, ids)
    order = list(dict.fromkeys(roots.get(i, -i) for i in ids))
    slots = [k for k, r in enumerate(order[:TOPN]) if r > 0]  # id âm: đơn vị không tìm được Điều gốc, không chấm
    if len(slots) < 2:
        return ids, None
    cand = [order[k] for k in slots]
    sc = dict(zip(cand, rk.score(query, [_doc(conn, r) for r in cand])))
    ranked = sorted(cand, key=lambda r: -sc[r])  # sorted ổn định: điểm bằng nhau giữ thứ tự cũ
    for k, r in zip(slots, ranked):
        order[k] = r
    pos = {r: k for k, r in enumerate(order)}
    return sorted(ids, key=lambda i: pos[roots.get(i, -i)]), sc[ranked[0]] - sc[ranked[1]]
