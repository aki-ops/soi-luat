from soiluat.cards import KIND_RANK2, Q6_LABEL, assemble_cards
from soiluat.fold import fold_search, search_accent
from soiluat.ingest import ingest_path
from soiluat.labels import labels_for_unit
from soiluat.parse import ParsedUnit
from soiluat.rebuild import rebuild_document
from soiluat.search import cascade_search, lookup_so_hieu
from soiluat.sohieu import find_so_hieu, find_so_hieu_prefix


def test_f1_bat_buoc_not_che_tai():
    u = ParsedUnit(
        level="khoan",
        addr_part="D1.K1",
        title="",
        text="Các thông tin bắt buộc phải nộp đầy đủ.",
        parent_addr="D1",
        confidence=1.0,
    )
    labs = labels_for_unit(u)
    assert "CHE_TAI" not in labs
    assert "NGHIA_VU" in labs


def test_f1_rang_buoc_not_che_tai():
    u = ParsedUnit(
        level="khoan",
        addr_part="D1.K1",
        title="",
        text="Quy định ràng buộc trách nhiệm của các bên.",
        parent_addr="D1",
        confidence=1.0,
    )
    assert "CHE_TAI" not in labels_for_unit(u)


def test_f1_tham_quyen_dieu_not_che_tai():
    dieu = ParsedUnit(
        level="dieu",
        addr_part="D3",
        title="Thẩm quyền xử phạt",
        text="Thẩm quyền xử phạt",
        parent_addr=None,
        confidence=1.0,
    )
    khoan = ParsedUnit(
        level="khoan",
        addr_part="D3.K1",
        title="",
        text="Phạt tiền từ 1.000.000 đồng đến 2.000.000 đồng đối với hành vi x.",
        parent_addr="D3",
        confidence=1.0,
    )
    assert "CHE_TAI" not in labels_for_unit(khoan, parent=dieu, dieu=dieu)
    assert "CHE_TAI" not in labels_for_unit(dieu, dieu=dieu)


def test_f1_diem_inherits_phat_hanh_vi():
    dieu = ParsedUnit(
        level="dieu",
        addr_part="D12",
        title="Xử phạt",
        text="Xử phạt",
        parent_addr=None,
        confidence=1.0,
    )
    khoan = ParsedUnit(
        level="khoan",
        addr_part="D12.K1",
        title="",
        text="Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng đối với các hành vi sau đây:",
        parent_addr="D12",
        confidence=1.0,
    )
    diem = ParsedUnit(
        level="diem",
        addr_part="D12.K1.Đa",
        title="",
        text="Không báo cáo định kỳ.",
        parent_addr="D12.K1",
        confidence=1.0,
    )
    assert "CHE_TAI" in labels_for_unit(khoan, parent=dieu, dieu=dieu)
    assert "CHE_TAI" in labels_for_unit(diem, parent=khoan, dieu=dieu)


def test_f1_buoc_khac_phuc():
    dieu = ParsedUnit(
        level="dieu",
        addr_part="D20",
        title="Biện pháp khắc phục hậu quả",
        text="Biện pháp khắc phục hậu quả",
        parent_addr=None,
        confidence=1.0,
    )
    khoan = ParsedUnit(
        level="khoan",
        addr_part="D20.K1",
        title="",
        text="Buộc khôi phục lại tình trạng ban đầu.",
        parent_addr="D20",
        confidence=1.0,
    )
    assert "CHE_TAI" in labels_for_unit(khoan, parent=dieu, dieu=dieu)


def test_f4_prefix_regex():
    assert find_so_hieu("15/2020") is None
    assert find_so_hieu_prefix("15/2020") == "15/2020"
    assert find_so_hieu_prefix("xem 15/2020 hôm nay") == "15/2020"
    assert find_so_hieu_prefix("15/2020/NĐ-CP") is None
    assert find_so_hieu("15/2020/NĐ-CP")


def test_f4_like_prefix_not_115(db, tmp_path):
    a = tmp_path / "nd15.txt"
    a.write_text(
        "Nghị định số 15/2020/NĐ-CP\nĐiều 1. Một\n1. Nội dung một.\n",
        encoding="utf-8",
    )
    b = tmp_path / "nd115.txt"
    b.write_text(
        "Nghị định số 115/2020/NĐ-CP\nĐiều 1. Khác\n1. Nội dung khác hẳn unique115token.\n",
        encoding="utf-8",
    )
    ingest_path(db, a, tmp_path)
    ingest_path(db, b, tmp_path)
    ids = lookup_so_hieu(db, "15/2020")
    assert ids
    paths = [
        db.execute(
            "SELECT d.so_hieu FROM units u JOIN documents d ON d.id = u.doc_id WHERE u.id = ?",
            (i,),
        ).fetchone()["so_hieu"]
        for i in ids
    ]
    assert all("15/2020" in (s or "") for s in paths)
    assert not any((s or "").startswith("115/") for s in paths)
    ids115 = lookup_so_hieu(db, "115/2020")
    assert ids115
    so115 = db.execute(
        "SELECT d.so_hieu FROM units u JOIN documents d ON d.id = u.doc_id WHERE u.id = ?",
        (ids115[0],),
    ).fetchone()["so_hieu"]
    assert "115/2020" in so115


def test_q6_accent_does_not_match_thue_when_thue_exists(db, tmp_path):
    p = tmp_path / "thue.txt"
    p.write_text(
        "Nghị định số 1/2020/NĐ-CP\nĐiều 1. Thuê nhà\n1. Bên thuê nhà phải ký hợp đồng unique_thue_only.\n",
        encoding="utf-8",
    )
    ingest_path(db, p, tmp_path)
    result = cascade_search(db, "thuế")
    cards = assemble_cards(
        db, result.ids, fold_ids=result.fold_ids, f2_ids=result.f2_ids
    )
    assert result.ids
    assert result.fold_ids
    assert any(Q6_LABEL in c.warnings for c in cards)


def test_q6_keeps_thue_out_when_accent_hits(db, tmp_path):
    good = tmp_path / "thue_ok.txt"
    good.write_text(
        "Nghị định số 2/2020/NĐ-CP\nĐiều 1. Thuế\n1. Người nộp thuế phải kê khai unique_thue_accent.\n",
        encoding="utf-8",
    )
    bad = tmp_path / "thue_fold.txt"
    bad.write_text(
        "Nghị định số 3/2020/NĐ-CP\nĐiều 1. Thuê\n1. Bên thuê nhà unique_thue_fold_only.\n",
        encoding="utf-8",
    )
    ingest_path(db, good, tmp_path)
    ingest_path(db, bad, tmp_path)
    result = cascade_search(db, "thuế")
    texts = [
        db.execute("SELECT raw_text FROM units WHERE id = ?", (i,)).fetchone()["raw_text"]
        for i in result.ids
    ]
    blob = " ".join(texts)
    assert "unique_thue_accent" in blob
    assert "unique_thue_fold_only" not in blob
    assert not result.fold_ids or all(
        "unique_thue_fold_only"
        not in (
            db.execute("SELECT raw_text FROM units WHERE id = ?", (i,)).fetchone()["raw_text"]
            or ""
        )
        for i in result.ids
        if i not in result.f2_ids
    )


def test_f2_ocr_fold_merged(db, tmp_path):
    good = tmp_path / "ocr_ok.txt"
    good.write_text(
        "Nghị định số 4/2020/NĐ-CP\nĐiều 1. Thuế\n1. Người nộp thuế unique_ocr_good.\n",
        encoding="utf-8",
    )
    ingest_path(db, good, tmp_path)
    scan = tmp_path / "ocr_bad.txt"
    scan.write_text(
        "Nghị định số 5/2020/NĐ-CP\nĐiều 1. Thue\n1. Nguoi nop thue unique_ocr_bad.\n",
        encoding="utf-8",
    )
    doc_id = ingest_path(db, scan, tmp_path)
    db.execute(
        "UPDATE pages SET extraction_method = 'ocr', ocr_status = 'ocr_xong', "
        "verification_status = 'chua' WHERE doc_id = ?",
        (doc_id,),
    )
    db.execute(
        "UPDATE units SET extraction_method = 'ocr' WHERE doc_id = ?",
        (doc_id,),
    )
    db.commit()
    result = cascade_search(db, "thuế")
    texts = [
        db.execute("SELECT raw_text FROM units WHERE id = ?", (i,)).fetchone()["raw_text"]
        for i in result.ids
    ]
    blob = " ".join(t or "" for t in texts)
    assert "unique_ocr_good" in blob
    assert "unique_ocr_bad" in blob
    cards = assemble_cards(
        db, result.ids, fold_ids=result.fold_ids, f2_ids=result.f2_ids
    )
    assert result.f2_ids
    assert any(Q6_LABEL in c.warnings and c.ocr_unverified for c in cards if c.q6_fold)


def test_f3_uu_tien_and_ha_uu(db, sample_doc):
    db.execute(
        "INSERT INTO subject_rules(phrase, phrase_fold, kind, approved) "
        "VALUES (?, ?, 'uu_tien', 1)",
        ("tổ chức tín dụng", fold_search("tổ chức tín dụng")),
    )
    db.execute(
        "INSERT INTO subject_rules(phrase, phrase_fold, kind, approved) "
        "VALUES (?, ?, 'ha_uu_tien', 1)",
        ("Bộ", fold_search("Bộ")),
    )
    db.commit()
    result = cascade_search(db, "tổ chức tín dụng")
    cards = assemble_cards(db, result.ids)
    assert any(c.q5_priority for c in cards)
    from soiluat.cards import _phrase_hits

    assert not _phrase_hits("Cơ quan phạtviên lập biên bản.", "phạt", False)
    assert _phrase_hits("Phạt tiền từ một triệu đồng.", "phạt", False)
    # "Bộ" một tiếng: không khớp "bộ" thường
    bo_unit = ParsedUnit(
        level="khoan",
        addr_part="Dx.K1",
        title="",
        text="Các bộ phải báo cáo.",
        parent_addr=None,
        confidence=1.0,
    )
    from soiluat.cards import apply_q5

    db.execute(
        "INSERT INTO units(doc_id, path, level, title, title_search, raw_text, "
        "normalized_text, search_accent, search_text, extraction_method, "
        "verification_status) VALUES (?, 'Dx.K1', 'khoan', '', '', ?, ?, ?, ?, 'txt', 'chua')",
        (
            sample_doc,
            bo_unit.text,
            bo_unit.text,
            search_accent(bo_unit.text),
            fold_search(bo_unit.text),
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM units WHERE path = 'Dx.K1'").fetchone()
    uu, ha = apply_q5(db, row, None)
    assert not ha


def test_c3_context_match(db, sample_doc):
    parent = db.execute("SELECT * FROM units WHERE path = 'D12.K1'").fetchone()
    assert parent is not None
    ctx = parent["raw_text"] or ""
    db.execute(
        "INSERT INTO units(doc_id, parent_id, path, level, title, title_search, "
        "raw_text, normalized_text, search_accent, search_text, context_search, "
        "context_accent, page_from, page_to, boundary_confidence, extraction_method, "
        "verification_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,1,1.0,'txt','chua')",
        (
            sample_doc,
            parent["id"],
            "D12.K1.Đa",
            "diem",
            "",
            "",
            "Không nộp báo cáo đúng hạn.",
            "Không nộp báo cáo đúng hạn.",
            search_accent("Không nộp báo cáo đúng hạn."),
            fold_search("Không nộp báo cáo đúng hạn."),
            fold_search(ctx),
            search_accent(ctx),
        ),
    )
    db.commit()
    result = cascade_search(db, "phat tien")
    paths = [
        db.execute("SELECT path FROM units WHERE id = ?", (i,)).fetchone()["path"]
        for i in result.ids
    ]
    assert any(p == "D12.K1.Đa" for p in paths)
    assert any(p == "D12.K1" or p.startswith("D12.K1.") for p in paths)


def test_d1_che_tai_alone_is_rank2(db, tmp_path):
    p = tmp_path / "only_fine.txt"
    p.write_text(
        "Nghị định số 6/2020/NĐ-CP\n"
        "Điều 1. Xử phạt\n"
        "1. Phạt tiền từ 5.000.000 đồng đến 6.000.000 đồng đối với hành vi unique_only_che_tai.\n",
        encoding="utf-8",
    )
    ingest_path(db, p, tmp_path)
    result = cascade_search(db, "unique_only_che_tai")
    cards = assemble_cards(db, result.ids)
    kinds = {c.kind for c in cards}
    assert KIND_RANK2 in kinds
    assert any(c.rank == 2 for c in cards)


def test_c1_query_log_set_null_on_rebuild(db, sample_doc):
    uid = db.execute(
        "SELECT id FROM units WHERE doc_id = ? LIMIT 1", (sample_doc,)
    ).fetchone()["id"]
    db.execute(
        "INSERT INTO query_log(query_raw, result_count, selected_unit, "
        "selected_doc_id, selected_path, created_at) VALUES (?,?,?,?,?,?)",
        ("x", 0, uid, sample_doc, "D5", "2020-01-01T00:00:00+00:00"),
    )
    db.commit()
    rebuild_document(db, sample_doc)
    row = db.execute("SELECT selected_unit, selected_doc_id, selected_path FROM query_log").fetchone()
    assert row["selected_unit"] is None
    assert row["selected_doc_id"] == sample_doc
    assert row["selected_path"] == "D5"


def test_e5_skipped_duplicate(db, tmp_path, sample_doc):
    src = tmp_path / "nd15.txt"
    dest = tmp_path / "other" / "nd15.txt"
    dest.parent.mkdir()
    dest.write_bytes(src.read_bytes())
    ingest_path(db, dest, tmp_path)
    n = db.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
    assert n == 1
    job = db.execute(
        "SELECT status, existing_file_path FROM import_jobs WHERE status = 'skipped_duplicate'"
    ).fetchone()
    assert job is not None
    assert job["existing_file_path"]


def test_qh15_and_ttlt():
    assert find_so_hieu("Luật số 64/2025/QH15") == "64/2025/QH15"
    assert find_so_hieu("01/2020/TTLT-BTP-NHNN")


def test_escape_fts_specials_do_not_crash(db, sample_doc):
    ids, _, _ = cascade_search(db, 'bao " * AND ( NOT NEAR')
    assert isinstance(ids, list)


def test_thoi_han_dieu_kien_and_negation():
    han = ParsedUnit(
        level="khoan",
        addr_part="D1.K1",
        title="",
        text="Phải nộp hồ sơ trước ngày 15 hàng tháng.",
        parent_addr="D1",
        confidence=1.0,
    )
    labs = labels_for_unit(han)
    assert "THOI_HAN" in labs
    assert "NGHIA_VU" in labs
    dk = ParsedUnit(
        level="khoan",
        addr_part="D1.K2",
        title="",
        text="Tổ chức phải đáp ứng điều kiện về vốn.",
        parent_addr="D1",
        confidence=1.0,
    )
    assert "DIEU_KIEN" in labels_for_unit(dk)
    neg = ParsedUnit(
        level="khoan",
        addr_part="D1.K3",
        title="",
        text="Tổ chức không bắt buộc báo cáo khi đã gửi quý trước.",
        parent_addr="D1",
        confidence=1.0,
    )
    assert "NGHIA_VU" not in labels_for_unit(neg)


def test_f3_longest_phrase_and_dieu_title(db, sample_doc):
    from soiluat.cards import apply_q5

    db.execute(
        "INSERT INTO subject_rules(phrase, phrase_fold, kind, approved) VALUES (?,?,?,1)",
        ("ngân hàng", fold_search("ngân hàng"), "uu_tien"),
    )
    db.execute(
        "INSERT INTO subject_rules(phrase, phrase_fold, kind, approved) VALUES (?,?,?,1)",
        ("Ngân hàng Nhà nước", fold_search("Ngân hàng Nhà nước"), "uu_tien"),
    )
    db.execute(
        "INSERT INTO subject_rules(phrase, phrase_fold, kind, approved) VALUES (?,?,?,1)",
        ("cơ quan nhà nước", fold_search("cơ quan nhà nước"), "ha_uu_tien"),
    )
    db.commit()
    db.execute(
        "INSERT INTO units(doc_id, path, level, title, title_search, raw_text, "
        "normalized_text, search_accent, search_text, extraction_method, "
        "verification_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            sample_doc,
            "D80",
            "dieu",
            "Trách nhiệm của cơ quan nhà nước",
            fold_search("Trách nhiệm của cơ quan nhà nước"),
            "Các đơn vị thực hiện.",
            "Các đơn vị thực hiện.",
            search_accent("Các đơn vị thực hiện."),
            fold_search("Các đơn vị thực hiện."),
            "txt",
            "chua",
        ),
    )
    db.commit()
    dieu = db.execute("SELECT * FROM units WHERE path = 'D80'").fetchone()
    uu, ha = apply_q5(db, dieu, dieu)
    assert ha
    from soiluat.cards import _best_rule

    rules = db.execute(
        "SELECT phrase, kind FROM subject_rules WHERE approved = 1"
    ).fetchall()
    best = _best_rule(rules, "Ngân hàng Nhà nước phải cấp phép.", "uu_tien")
    assert best is not None
    assert best["phrase"] == "Ngân hàng Nhà nước"


def test_two_files_same_so_hieu(db, tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text(
        "Nghị định số 15/2020/NĐ-CP\nĐiều 1. A\n1. Nội dung file A unique_file_a.\nĐiều 2. B\n1. Hai.\n",
        encoding="utf-8",
    )
    b.write_text(
        "Nghị định số 15/2020/NĐ-CP\nĐiều 1. C\n1. Nội dung file B unique_file_b.\nĐiều 2. D\n1. Hai.\n",
        encoding="utf-8",
    )
    ingest_path(db, a, tmp_path)
    ingest_path(db, b, tmp_path)
    n = db.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE so_hieu_search = ?",
        ("15/2020/nd-cp",),
    ).fetchone()["n"]
    assert n == 2
    ids = lookup_so_hieu(db, "15/2020/NĐ-CP")
    texts = [
        db.execute("SELECT raw_text FROM units WHERE id = ?", (i,)).fetchone()["raw_text"]
        for i in ids
    ]
    blob = " ".join(t or "" for t in texts)
    assert "unique_file_a" in blob and "unique_file_b" in blob


def test_change_so_hieu_keeps_confirmed_links(db, sample_doc):
    db.execute("UPDATE links SET confirmed = 1")
    db.commit()
    n_before = db.execute(
        "SELECT COUNT(*) AS n FROM links WHERE confirmed = 1"
    ).fetchone()["n"]
    db.execute(
        "UPDATE documents SET so_hieu = ?, so_hieu_search = ? WHERE id = ?",
        ("99/2020/NĐ-CP", "99/2020/nd-cp", sample_doc),
    )
    db.commit()
    n_after = db.execute(
        "SELECT COUNT(*) AS n FROM links WHERE confirmed = 1"
    ).fetchone()["n"]
    assert n_after == n_before
    paths = {r["path"] for r in db.execute("SELECT path FROM units WHERE doc_id = ?", (sample_doc,))}
    assert "D5" in paths


def test_e2_cross_doc_snapshot(db, tmp_path):
    a = tmp_path / "doc_a.txt"
    b = tmp_path / "doc_b.txt"
    a.write_text(
        "Nghị định số 7/2020/NĐ-CP\nĐiều 1. Xử phạt\n"
        "1. Phạt tiền từ 1.000.000 đồng đến 2.000.000 đồng đối với hành vi unique_e2_a.\n"
        "Điều 2. Khác\n1. Nội dung.\n",
        encoding="utf-8",
    )
    b.write_text(
        "Thông tư số 8/2020/TT-NHNN\nĐiều 1. Nghĩa vụ\n1. Tổ chức phải unique_e2_b báo cáo.\nĐiều 2. Hai\n1. Hai.\n",
        encoding="utf-8",
    )
    ida = ingest_path(db, a, tmp_path)
    idb = ingest_path(db, b, tmp_path)
    su = db.execute(
        "SELECT u.id FROM units u JOIN unit_labels l ON l.unit_id = u.id "
        "WHERE u.doc_id = ? AND l.label = 'CHE_TAI' LIMIT 1",
        (ida,),
    ).fetchone()
    du = db.execute(
        "SELECT u.id FROM units u JOIN unit_labels l ON l.unit_id = u.id "
        "WHERE u.doc_id = ? AND l.label = 'NGHIA_VU' LIMIT 1",
        (idb,),
    ).fetchone()
    assert su and du
    db.execute(
        "INSERT OR IGNORE INTO links(sanction_unit, duty_unit, method, confirmed) "
        "VALUES (?, ?, 'goi_y', 1)",
        (su["id"], du["id"]),
    )
    db.commit()
    a.write_text(
        "Nghị định số 7/2020/NĐ-CP\nĐiều 1. Xử phạt\n"
        "1. Phạt tiền từ 1.000.000 đồng đến 2.000.000 đồng đối với hành vi unique_e2_a sửa.\n"
        "Điều 2. Khác\n1. Nội dung.\n",
        encoding="utf-8",
    )
    ingest_path(db, a, tmp_path)
    row = db.execute(
        "SELECT l.confirmed, du.doc_id AS ddoc FROM links l "
        "JOIN units du ON du.id = l.duty_unit WHERE l.confirmed = 1"
    ).fetchone()
    assert row is not None
    assert row["ddoc"] == idb


def test_noi_bo_dieu_nay(db, tmp_path):
    p = tmp_path / "noibo.txt"
    p.write_text(
        "Nghị định số 9/2020/NĐ-CP\n"
        "Điều 5. Báo cáo và xử phạt\n"
        "1. Tổ chức tín dụng phải nộp báo cáo unique_noibo_duty.\n"
        "2. Phạt tiền từ 1.000.000 đồng đến 2.000.000 đồng đối với hành vi vi phạm khoản 1 Điều này.\n",
        encoding="utf-8",
    )
    ingest_path(db, p, tmp_path)
    row = db.execute(
        "SELECT method FROM links WHERE method = 'noi_bo'"
    ).fetchone()
    assert row is not None


def test_fine_source_on_diem(db, tmp_path):
    p = tmp_path / "diemfine.txt"
    p.write_text(
        "Nghị định số 10/2020/NĐ-CP\n"
        "Điều 1. Xử phạt\n"
        "1. Phạt tiền từ 3.000.000 đồng đến 4.000.000 đồng đối với các hành vi sau đây:\n"
        "a) Không nộp hồ sơ unique_diem_fine.\n"
        "Điều 2. Khác\n1. Nội dung.\n",
        encoding="utf-8",
    )
    ingest_path(db, p, tmp_path)
    row = db.execute(
        "SELECT fine_min, fine_max, fine_source_unit FROM units WHERE path LIKE '%.Đa'"
    ).fetchone()
    assert row is not None
    assert row["fine_min"] == 3_000_000
    assert row["fine_source_unit"] is not None


def test_force_doan_ingest(db, tmp_path):
    p = tmp_path / "doan.txt"
    p.write_text(
        "Nghị định số 11/2020/NĐ-CP\nĐiều 1. Một\n1. Khoản.\nĐiều 2. Hai\n1. Khoản.\n",
        encoding="utf-8",
    )
    ingest_path(db, p, tmp_path, force_doan=True)
    levels = {
        r["level"]
        for r in db.execute("SELECT level FROM units").fetchall()
    }
    assert levels <= {"doan"}
    doc = db.execute("SELECT fallback_doan FROM documents").fetchone()
    assert doc["fallback_doan"] == 1


def test_unsigned_query_finds_signed_text(db, sample_doc):
    result = cascade_search(db, "bao cao")
    assert result.ids
    assert result.tier <= 3


def test_dinh_ki_matches_dinh_ky(db, sample_doc):
    ky = cascade_search(db, "báo cáo định kỳ")
    ki = cascade_search(db, "báo cáo định kì")
    assert ky.ids
    assert ki.ids
    assert ki.tier <= 3
    ky_dieu = {
        r["path"].split(".")[0]
        for r in db.execute(
            f"SELECT path FROM units WHERE id IN ({','.join('?' * len(ky.ids))})",
            ky.ids,
        )
    }
    ki_dieu = {
        r["path"].split(".")[0]
        for r in db.execute(
            f"SELECT path FROM units WHERE id IN ({','.join('?' * len(ki.ids))})",
            ki.ids,
        )
    }
    assert "D5" in ky_dieu and "D5" in ki_dieu


def test_keyword_plus_so_hieu_filters_fts(db, sample_doc):
    result = cascade_search(db, "báo cáo 15/2020")
    assert result.note != "so_hieu" or result.ids
    texts = [
        db.execute("SELECT raw_text FROM units WHERE id = ?", (i,)).fetchone()["raw_text"]
        for i in result.ids
    ]
    blob = " ".join(t or "" for t in texts)
    assert "báo cáo" in blob.lower() or "bao cao" in blob.lower()
    assert "đối tượng áp dụng" not in blob.lower()


def test_dieu_only_matches_path_not_digit(db, sample_doc):
    result = cascade_search(db, "Điều 5")
    assert result.note == "dieu"
    paths = {
        db.execute("SELECT path FROM units WHERE id = ?", (i,)).fetchone()["path"]
        for i in result.ids
    }
    assert all(p == "D5" or p.startswith("D5.") for p in paths)
    assert not any(p.startswith("D12") for p in paths)
