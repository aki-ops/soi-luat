"""Xếp hạng lại theo nghĩa (EmbeddingGemma): logic trộn hạng, lưu vector, dự phòng khi thiếu mô hình."""

import os
from pathlib import Path

import pytest

from soiluat import search, semantic
from soiluat.ingest import ingest_path

np = pytest.importorskip("numpy")

TEXT = """Nghị định số 9/2024/NĐ-CP
Điều 1. Giá dịch vụ
1. Cơ sở phải niêm yết giá.
Điều 2. Thuế
1. Nộp thuế đúng hạn.
a) Nộp tại kho bạc.
Điều 3. Mũ bảo hiểm
1. Người đi xe máy phải đội mũ bảo hiểm.
"""


class FakeEncoder:
    """Vector theo từ khoá: đủ để kiểm logic, không cần mô hình thật."""
    np = np
    KEYS = ("giá", "thuế", "mũ")

    def encode(self, texts, batch=8):
        v = np.array([[float(k in t.lower()) for k in self.KEYS] + [1e-3] for t in texts], np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)


@pytest.fixture
def doc(db, tmp_path):
    p = tmp_path / "nd9.txt"
    p.write_text(TEXT, encoding="utf-8")
    return ingest_path(db, p, tmp_path)


@pytest.fixture
def fake(monkeypatch, db):
    semantic.set_mode(db, "advance")
    enc = FakeEncoder()
    monkeypatch.setattr(semantic, "_ENC", enc)
    monkeypatch.setattr(semantic, "_ENC_TRIED", True)
    monkeypatch.delenv("SOILUAT_SEMANTIC", raising=False)
    return enc


def _unit(db, path):
    return db.execute("SELECT id FROM units WHERE path = ?", (path,)).fetchone()[0]


def test_root_ids_map_khoan_and_diem_to_dieu(db, doc):
    d2 = _unit(db, "D2")
    kids = [r[0] for r in db.execute("SELECT id FROM units WHERE path LIKE 'D2.%'")]
    assert kids and set(semantic.root_ids(db, kids).values()) == {d2}
    doan = db.execute("SELECT id FROM units WHERE level = 'doan'").fetchone()[0]
    assert semantic.root_ids(db, [doan]) == {doan: doan}  # đoạn 'p1.para1' là gốc của chính nó


def test_embed_roots_only_roots_and_idempotent(db, doc, fake):
    todo = semantic.missing_roots(db)
    roots = [r[0] for r in db.execute("SELECT id FROM units WHERE parent_id IS NULL")]
    assert sorted(todo) == sorted(roots) and len(roots) == 4  # 3 Điều + đoạn mở đầu
    assert "Nộp tại kho bạc" in semantic.root_text(db, _unit(db, "D2"))  # Điều gồm cả khoản, điểm
    semantic.embed_roots(db, fake, todo)
    assert semantic.missing_roots(db) == []
    n = db.execute("SELECT COUNT(*), MIN(length(vec)) FROM unit_vectors").fetchone()
    assert n[0] == 4 and n[1] == 4 * 2  # float16 × DIM của FakeEncoder


def test_rerank_moves_semantic_match_up(db, doc, fake, monkeypatch):
    monkeypatch.setattr(semantic, "DENSE_K", 0)  # chỉ xếp lại
    semantic.embed_roots(db, fake, semantic.missing_roots(db))
    a, b, c = (_unit(db, p) for p in ("D1", "D2", "D3"))
    kb = _unit(db, "D2.K1")
    out = semantic.rerank(db, "đội mũ khi đi xe", [a, b, kb, c])
    # BM25: D1, D2, D3; theo nghĩa D3 giống nhất → D3 vượt D2, D1 giữ đầu (RRF), đơn vị cùng Điều vẫn liền nhau
    assert out == [a, c, b, kb]


def test_rerank_adds_dense_match_bm25_missed(db, doc, fake, monkeypatch):
    semantic.embed_roots(db, fake, semantic.missing_roots(db))
    a, b, c = (_unit(db, p) for p in ("D1", "D2", "D3"))
    monkeypatch.setattr(semantic, "DENSE_K", 1)
    # BM25 chỉ ra D1, D2 (không chung chữ với D3); vector toàn kho thêm D3 — chỉ có điểm theo nghĩa nên đứng sau
    assert semantic.rerank(db, "đội mũ khi đi xe", [a, b]) == [a, b, c]
    assert semantic.rerank(db, "đội mũ khi đi xe", []) == [c]  # BM25 không ra gì vẫn có kết quả
    monkeypatch.setattr(semantic, "DENSE_MIN", 0.9)  # "giá thuế mũ" giống mỗi Điều ~0,58: không Điều nào đủ ngưỡng
    assert semantic.rerank(db, "giá thuế mũ", []) == []  # không bịa kết quả khi chẳng gì đủ gần
    monkeypatch.setattr(semantic, "DENSE_MIN", 0.5)
    # chỉ thêm, không xáo: thứ tự các Điều BM25 tìm ra giống hệt khi tắt phần thêm
    with_k = [i for i in semantic.rerank(db, "đội mũ khi đi xe", [b, c, a]) if i in (a, b, c)]
    monkeypatch.setattr(semantic, "DENSE_K", 0)
    assert with_k == semantic.rerank(db, "đội mũ khi đi xe", [b, c, a])
    monkeypatch.setattr(semantic, "DENSE_K", 1)
    other = db.execute("SELECT MAX(doc_id) + 1 FROM units").fetchone()[0]
    assert semantic.rerank(db, "đội mũ khi đi xe", [a, b], doc_ids=[other]) == [a, b]  # tra trong văn bản khác


def test_dense_only_card_marked_and_note_titled_by_file(db, doc, fake, tmp_path):
    from soiluat.cards import assemble_cards

    note = tmp_path / "kn-tien.txt"
    # FakeEncoder so chuỗi con nên "mũi" giống nghĩa "mũ"; BM25 coi là hai từ khác nhau
    note.write_text("Bị đau mũi thì nên đi khám sớm.\n", encoding="utf-8")
    ingest_path(db, note, tmp_path)
    semantic.embed_roots(db, fake, semantic.missing_roots(db))
    r = search.cascade_search(db, "mũ")  # BM25 chỉ ra D3; vector thêm cả ghi chú dù không chung chữ
    nid = db.execute("SELECT u.id FROM units u JOIN documents d ON d.id = u.doc_id WHERE d.file_path LIKE ?",
                     ("%kn-tien%",)).fetchone()[0]
    assert r.tiers[_unit(db, "D3")] < 7 and r.tiers[nid] == 7
    c = next(c for c in assemble_cards(db, r.ids, tiers=r.tiers) if nid in c.unit_ids)
    assert c.match_tier == 7 and c.title == "kn-tien · trang 1 đoạn 1"


def test_rerank_keeps_order_without_vectors_or_model(db, doc, fake, monkeypatch):
    ids = [_unit(db, p) for p in ("D1", "D2", "D3")]
    assert semantic.rerank(db, "đội mũ", ids) == ids  # chưa nhúng
    semantic.embed_roots(db, fake, semantic.missing_roots(db))
    monkeypatch.setenv("SOILUAT_SEMANTIC", "0")
    assert semantic.rerank(db, "đội mũ", ids) == ids  # tắt bằng biến môi trường


def test_frozen_model_dir_beside_exe(tmp_path, monkeypatch):
    import sys

    monkeypatch.delenv("SOILUAT_MODEL_DIR", raising=False)
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path / "data"))
    assert semantic.model_dir() == tmp_path / "data" / "models" / "embeddinggemma"  # chạy từ mã nguồn
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "SoiLuat" / "SoiLuat.exe"))
    assert semantic.model_dir() == tmp_path / "dist" / "SoiLuat" / "models" / "embeddinggemma"


def test_missing_model_dir_gives_no_encoder(tmp_path, monkeypatch):
    monkeypatch.setenv("SOILUAT_MODEL_DIR", str(tmp_path / "khong_co"))
    monkeypatch.setattr(semantic, "_ENC", None)
    monkeypatch.setattr(semantic, "_ENC_TRIED", False)
    monkeypatch.delenv("SOILUAT_SEMANTIC", raising=False)
    assert semantic.encoder() is None


def test_cascade_search_goes_through_rerank(db, doc, monkeypatch):
    calls = []

    def spy(conn, q, ids, doc_ids=None):
        calls.append(q)
        return list(reversed(ids))

    base = search.cascade_search(db, "nộp thuế").ids
    monkeypatch.setattr(semantic, "rerank", spy)
    assert search.cascade_search(db, "nộp thuế").ids == list(reversed(base)) and calls == ["nộp thuế"]


@pytest.mark.skipif(not os.environ.get("SOILUAT_MODEL_DIR"), reason="cần SOILUAT_MODEL_DIR trỏ tới mô hình thật")
def test_real_model_prefers_related_text(monkeypatch):
    pytest.importorskip("onnxruntime")
    enc = semantic.Encoder(Path(os.environ["SOILUAT_MODEL_DIR"]))
    assert enc.tok.truncation["max_length"] == semantic.MAXLEN
    long = enc.encode([semantic.D_PRE.format(t="none") + "quy định " * 400])  # dài hơn 128 token vẫn nhúng được
    assert long.shape == (1, semantic.DIM)
    q, helmet, tax = enc.encode([semantic.Q_PRE + "không đội mũ bảo hiểm bị phạt bao nhiêu",
                                 semantic.D_PRE.format(t="none") + "Phạt tiền người điều khiển xe mô tô không đội mũ bảo hiểm",
                                 semantic.D_PRE.format(t="none") + "Thời hạn nộp hồ sơ khai thuế giá trị gia tăng"])
    assert float(q @ helmet) > float(q @ tax)


def test_unembedded_dieu_not_penalised_and_pending_counts(db, doc, fake):
    a, b, c = (_unit(db, p) for p in ("D1", "D2", "D3"))
    assert semantic.pending(db) == 4
    semantic.embed_roots(db, fake, [c])  # chỉ D3 có vector: D1, D2 là "văn bản mới"
    assert semantic.pending(db) == 3
    # D1, D2 chưa nhúng giữ hạng BM25; D3 giống nghĩa nhất vẫn vượt D2 nhưng không vượt cả D1 (hạng 1)
    assert semantic.rerank(db, "đội mũ khi đi xe", [a, b, c]) == [a, c, b]


def test_nen_flag_sets_one_thread_and_idle(monkeypatch, tmp_path, db, doc):
    from soiluat import importer

    seen = {}
    monkeypatch.setattr(semantic, "lower_priority", lambda: seen.setdefault("idle", True))
    monkeypatch.setattr(semantic, "encoder", lambda: None)  # không nạp mô hình thật
    monkeypatch.setattr(semantic, "THREADS", 2)
    assert importer._embed(db, background=True) == 2
    assert seen == {"idle": True} and semantic.THREADS == 1


def test_normal_mode_never_loads_model(db, doc, fake, monkeypatch):
    semantic.embed_roots(db, fake, semantic.missing_roots(db))
    ids = [_unit(db, p) for p in ("D1", "D2", "D3")]
    semantic.set_mode(db, "normal")
    monkeypatch.setattr(semantic, "encoder", lambda: pytest.fail("normal không được nạp mô hình"))
    assert semantic.rerank(db, "đội mũ khi đi xe", ids) == ids
    assert semantic.get_mode(db) == "normal"
    with pytest.raises(ValueError):
        semantic.set_mode(db, "turbo")


def test_mode_defaults_to_normal(db):
    assert semantic.get_mode(db) == "normal"


def test_default_truncation_is_128_and_named_in_model():
    # 128 token: Zalo đo độ chính xác như 256, nhúng nhanh gấp đôi; tên mô hình mang độ dài để vector cũ không bị dùng lẫn
    assert semantic.MAXLEN == 128 and semantic.MODEL_NAME.endswith("len128")


def test_toggle_on_search_page(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import soiluat.app as appmod

    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    monkeypatch.setenv("SOILUAT_MODEL_DIR", str(tmp_path / "khong_co"))
    c = TestClient(appmod.app)
    h = {"Host": "127.0.0.1"}
    page = c.get("/", headers=h).text
    assert 'value="normal" aria-pressed="true"' in page and "BM25 thuần" in page
    r = c.post("/settings/mode", data={"mode": "advance", "q": "đội mũ"}, headers=h, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/?q=")
    page = c.get("/", headers=h).text
    assert 'value="advance" aria-pressed="true"' in page and "Chưa cài mô hình" in page
    assert c.post("/settings/mode", data={"mode": "turbo"}, headers=h).status_code == 400
