"""Xếp hạng lại theo nghĩa bằng EmbeddingGemma (ONNX int8, CPU).

Chế độ "advance" (chọn trên Search App, lưu trong app_meta); "normal" (mặc định), thiếu mô hình,
thiếu onnxruntime/tokenizers/numpy, hoặc SOILUAT_SEMANTIC=0 → tìm như cũ (BM25), không nạp mô hình.
Vector tính một lần cho mỗi Điều (đơn vị gốc, parent_id IS NULL) bằng `soiluat-importer --nhung`;
khi tìm chỉ nhúng câu hỏi rồi trộn hạng (RRF) với TOP Điều đầu của BM25, cộng DENSE_K Điều gần nghĩa nhất toàn kho.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

from soiluat.config import data_dir

MODEL_NAME = "embeddinggemma-300m-q8-256-len128"  # đổi MAXLEN/DIM thì đổi tên: vector cũ không trộn với mới
DIM = 256  # Matryoshka: cắt 768 → 256 rồi chuẩn hoá lại
MAXLEN = 128  # token; Zalo: độ chính xác như 256 (Hit@5 89,1%), nhúng nhanh gấp ~2 lần (4,5 Điều/s, 2 luồng)
THREADS = 2  # máy văn phòng: chừa CPU cho Office
TOP = 20  # số Điều đầu của BM25 được xếp lại; tham số chọn trên tập train Zalo
RRF_K = 5
W = 1.0
DENSE_K = 20  # Advance: Điều gần nghĩa nhất toàn kho thêm vào ứng viên (cả khi không chung chữ nào); 0 = chỉ xếp lại
# cosine tối thiểu của Điều thêm: kho Zalo, câu vô nghĩa ("?", "asdf", "xin chào"…) cao nhất 0,47; Điều đáp án
# 96% ≥ 0,50. Riêng cho MODEL_NAME này: đổi mô hình thì đo lại
DENSE_MIN = 0.50
Q_PRE = "task: search result | query: "
D_PRE = "title: {t} | text: "


def model_dir() -> Path:
    raw = os.environ.get("SOILUAT_MODEL_DIR")
    if raw:
        return Path(raw)
    path = data_dir() / "models" / "embeddinggemma"
    if not path.exists() and getattr(sys, "frozen", False):  # bản đóng gói: models\ cạnh SoiLuat\ và SoiLuatImporter\
        return Path(sys.executable).resolve().parent.parent / "models" / "embeddinggemma"
    return path


class Encoder:
    def __init__(self, path: Path, threads: int | None = None):
        threads = threads or THREADS  # đọc lúc gọi: --nen đặt THREADS = 1 trước khi nạp
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        so.enable_cpu_mem_arena = False  # bật: RAM giữ ~1,3 GB sau lần chạy đầu; tắt: ~430 MB
        so.enable_mem_pattern = False
        self.sess = ort.InferenceSession(str(path / "onnx" / "model_quantized.onnx"), so,
                                         providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(path / "tokenizer.json"))
        self.tok.enable_truncation(MAXLEN)

    def encode(self, texts: list[str], batch: int = 8):
        np = self.np
        enc = self.tok.encode_batch(texts)
        order = np.argsort([len(e.ids) for e in enc])  # gom câu cùng độ dài: ít đệm
        out = np.zeros((len(texts), DIM), np.float32)
        for b in range(0, len(texts), batch):
            idx = order[b:b + batch]
            n = max(len(enc[i].ids) for i in idx)
            ids = np.zeros((len(idx), n), np.int64)
            mask = np.zeros((len(idx), n), np.int64)
            for r, i in enumerate(idx):
                ids[r, :len(enc[i].ids)] = enc[i].ids
                mask[r, :len(enc[i].ids)] = 1
            v = self.sess.run(["sentence_embedding"], {"input_ids": ids, "attention_mask": mask})[0][:, :DIM]
            out[idx] = v / np.linalg.norm(v, axis=1, keepdims=True)
        return out


MODES = ("normal", "advance")  # normal: BM25 thuần; advance: BM25 + xếp lại theo nghĩa


def get_mode(conn: sqlite3.Connection) -> str:
    r = conn.execute("SELECT value FROM app_meta WHERE key = 'search_mode'").fetchone()
    return r[0] if r and r[0] in MODES else "normal"  # mặc định normal: máy yếu không nạp mô hình


def set_mode(conn: sqlite3.Connection, mode: str) -> None:
    if mode not in MODES:
        raise ValueError(mode)
    with conn:
        conn.execute("INSERT OR REPLACE INTO app_meta(key, value) VALUES ('search_mode', ?)", (mode,))


def model_installed() -> bool:
    path = model_dir()
    return (path / "onnx" / "model_quantized.onnx").exists() and (path / "tokenizer.json").exists()


def lower_priority() -> None:
    """Chạy nền: mức ưu tiên CPU thấp nhất, không tranh với Word/Excel đang mở."""
    try:
        if os.name == "nt":
            import ctypes

            k = ctypes.windll.kernel32
            k.SetPriorityClass(k.GetCurrentProcess(), 0x00000040)  # IDLE_PRIORITY_CLASS
        else:
            os.nice(19)
    except Exception:  # noqa: BLE001 — không hạ được thì vẫn chạy, chỉ là không nhường
        pass


def pending(conn: sqlite3.Connection) -> int:
    """Số Điều gốc chưa có vector (chỉ có nghĩa khi mô hình đã cài)."""
    return conn.execute(
        "SELECT COUNT(*) FROM units u LEFT JOIN unit_vectors v ON v.unit_id = u.id AND v.model = ?"
        " WHERE u.parent_id IS NULL AND v.unit_id IS NULL", (MODEL_NAME,)).fetchone()[0]


_ENC: Encoder | None = None
_ENC_TRIED = False


def encoder() -> Encoder | None:
    """Nạp mô hình lần đầu cần dùng; lỗi/thiếu thì None (một lần mỗi process)."""
    global _ENC, _ENC_TRIED
    if os.environ.get("SOILUAT_SEMANTIC") == "0":
        return None
    if not _ENC_TRIED:
        _ENC_TRIED = True
        if model_installed():
            try:
                _ENC = Encoder(model_dir())
            except Exception:  # noqa: BLE001 — thiếu thư viện / mô hình hỏng: tìm như cũ
                _ENC = None
    return _ENC


def root_ids(conn: sqlite3.Connection, unit_ids: list[int]) -> dict[int, int]:
    """unit → Điều (hoặc đoạn) gốc chứa nó: gốc là chính nó, con lấy theo tiền tố đường dẫn 'D3.K1' → 'D3'
    (đoạn có đường dẫn 'p1.para1' nhưng không có cha nên không cắt)."""
    rows = conn.execute(
        """SELECT u.id, CASE WHEN u.parent_id IS NULL THEN u.id ELSE r.id END FROM units u
           LEFT JOIN units r ON u.parent_id IS NOT NULL AND r.doc_id = u.doc_id AND r.parent_id IS NULL
            AND r.path = substr(u.path, 1, instr(u.path, '.') - 1)
           WHERE u.id IN (SELECT value FROM json_each(?))""",
        (json.dumps(unit_ids),),
    ).fetchall()
    return {r[0]: r[1] for r in rows if r[1] is not None}


def root_text(conn: sqlite3.Connection, root_id: int) -> str:
    r = conn.execute("SELECT doc_id, path, title FROM units WHERE id = ?", (root_id,)).fetchone()
    body = " ".join(t for (t,) in conn.execute(
        "SELECT COALESCE(reviewed_text, normalized_text) FROM units WHERE doc_id = ? AND (path = ? OR path LIKE ?)"
        " ORDER BY id", (r[0], r[1], r[1] + ".%")) if t)
    return D_PRE.format(t=r[2] or "none") + body


def missing_roots(conn: sqlite3.Connection) -> list[int]:
    return [r[0] for r in conn.execute(
        "SELECT u.id FROM units u LEFT JOIN unit_vectors v ON v.unit_id = u.id AND v.model = ?"
        " WHERE u.parent_id IS NULL AND v.unit_id IS NULL ORDER BY u.id", (MODEL_NAME,))]


def embed_roots(conn: sqlite3.Connection, enc: Encoder, ids: list[int], *, chunk: int = 64,
                progress=None) -> float:
    """Nhúng và lưu vector cho các Điều gốc; trả số giây. Ghi theo từng khối: dừng giữa chừng không mất phần đã xong."""
    t0 = time.perf_counter()
    for b in range(0, len(ids), chunk):
        part = ids[b:b + chunk]
        vecs = enc.encode([root_text(conn, i) for i in part])
        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO unit_vectors(unit_id, model, vec) VALUES (?, ?, ?)",
                [(i, MODEL_NAME, v.astype("float16").tobytes()) for i, v in zip(part, vecs)])
        if progress:
            progress(b + len(part), len(ids), time.perf_counter() - t0)
    return time.perf_counter() - t0


_ALL: dict = {}  # ma trận vector toàn kho, nạp lại khi (file db, số vector, id lớn nhất) đổi


def _all_vectors(conn: sqlite3.Connection, np):
    """(id gốc, doc_id, ma trận float32) của mọi gốc đã nhúng. Kho Zalo 61 nghìn Điều × 256 ≈ 62 MB RAM."""
    db = conn.execute("PRAGMA database_list").fetchone()[2]
    key = (db, *conn.execute("SELECT COUNT(*), MAX(unit_id) FROM unit_vectors WHERE model = ?",
                             (MODEL_NAME,)).fetchone())
    if _ALL.get("key") != key:
        rows = conn.execute("SELECT v.unit_id, u.doc_id, v.vec FROM unit_vectors v JOIN units u ON u.id = v.unit_id"
                            " WHERE v.model = ? ORDER BY v.unit_id", (MODEL_NAME,)).fetchall()
        mat = np.frombuffer(b"".join(r[2] for r in rows), np.float16).reshape(len(rows), -1).astype(np.float32)
        _ALL.update(key=key, ids=np.array([r[0] for r in rows]), docs=np.array([r[1] for r in rows]), mat=mat)
    return _ALL["ids"], _ALL["docs"], _ALL["mat"]


def rerank(conn: sqlite3.Connection, query: str, ids: list[int], doc_ids: list[int] | None = None) -> list[int]:
    """Đổi thứ tự TOP Điều đầu theo RRF(hạng BM25, hạng theo nghĩa); Điều chưa có vector giữ hạng BM25.
    Thêm DENSE_K Điều gần nghĩa nhất toàn kho (trong doc_ids nếu có) dù BM25 không tìm ra: chỉ có điểm theo nghĩa."""
    if get_mode(conn) != "advance" or (len(ids) < 2 and not DENSE_K):
        return ids
    if not conn.execute("SELECT 1 FROM unit_vectors WHERE model = ? LIMIT 1", (MODEL_NAME,)).fetchone():
        return ids  # chưa có vector nào: khỏi nạp mô hình (~0,5–1,3 GB RAM)
    enc = encoder()
    if enc is None:
        return ids
    np = enc.np
    roots = root_ids(conn, ids)
    order = list(dict.fromkeys(roots.get(i, -i) for i in ids))  # đơn vị không tìm được gốc: tự làm gốc
    top = order[:TOP]
    q = enc.encode([Q_PRE + query])[0]
    if DENSE_K:
        all_ids, all_docs, mat = _all_vectors(conn, np)
        row = {int(r): k for k, r in enumerate(all_ids)}
        sim_all = mat @ q
        sims = {r: float(sim_all[row[r]]) for r in top if r in row}
    else:  # chỉ xếp lại: đọc vector của TOP, không giữ ma trận toàn kho
        vecs = dict(conn.execute(
            "SELECT unit_id, vec FROM unit_vectors WHERE model = ? AND unit_id IN (SELECT value FROM json_each(?))",
            (MODEL_NAME, json.dumps(top))).fetchall())
        # theo thứ tự TOP như nhánh trên: hai Điều giống nghĩa bằng nhau thì giữ thứ tự BM25
        sims = {r: float(np.frombuffer(vecs[r], np.float16).astype(np.float32) @ q) for r in top if r in vecs}
    dense = {r: k for k, r in enumerate(sorted(sims, key=lambda r: -sims[r]), 1)}
    # Điều chưa nhúng (văn bản mới nạp, đang nhúng nền): hạng theo nghĩa = hạng BM25, không bị phạt
    score = {r: 1 / (RRF_K + b) + W / (RRF_K + dense.get(r, b)) for b, r in enumerate(top, 1)}
    bm = {r: b for b, r in enumerate(order, 1)}
    if DENSE_K and len(all_ids):
        ok = (np.isin(all_docs, doc_ids) if doc_ids else np.ones(len(all_ids), bool)) & (sim_all >= DENSE_MIN)
        best = [int(all_ids[k]) for k in np.argsort(-np.where(ok, sim_all, -np.inf))[:DENSE_K] if ok[k]]
        # Chỉ thêm, không xáo TOP: hạng theo nghĩa của Điều thêm tính trên toàn kho, TOP giữ điểm như trên.
        # Có ở BM25 sau TOP thì cộng hạng BM25 đó; không có thì chỉ điểm theo nghĩa (≤ 1/(RRF_K+1): không vượt hạng 1)
        score.update((r, (1 / (RRF_K + bm[r]) if r in bm else 0) + W / (RRF_K + k))
                     for k, r in enumerate(best, 1) if r not in score)
    head = sorted(score, key=lambda r: -score[r])
    pos = {r: k for k, r in enumerate(head + [r for r in order[TOP:] if r not in score])}
    new = [r for r in score if r not in bm]  # gốc là chính đơn vị Điều/đoạn nên dùng thẳng làm id
    roots.update((r, r) for r in new)
    return sorted(ids + new, key=lambda i: pos[roots.get(i, -i)])  # sorted ổn định: giữ thứ tự BM25 trong một Điều
