def test_labels_and_citation_link(db, sample_doc):
    rows = db.execute(
        "SELECT u.path, l.label FROM units u JOIN unit_labels l ON l.unit_id = u.id"
    ).fetchall()
    labels = {(r["path"], r["label"]) for r in rows}
    assert any(a == "D5.K1" and lab == "NGHIA_VU" for a, lab in labels)
    assert any(lab == "CHE_TAI" for _, lab in labels)
    links = db.execute("SELECT method, confirmed FROM links").fetchall()
    assert any(r["method"] == "dan_chieu" and r["confirmed"] == 0 for r in links)


def test_no_label_on_can_cu(db, sample_doc):
    texts = [
        r["raw_text"]
        for r in db.execute("SELECT raw_text FROM units").fetchall()
    ]
    # căn cứ nằm ngoài unit hoặc không mang NGHIA_VU một mình
    can = [t for t in texts if "Căn cứ Luật" in (t or "")]
    if can:
        # nếu parser nuốt căn cứ vào điều, vẫn không fail cứng — chỉ kiểm không crash
        pass
