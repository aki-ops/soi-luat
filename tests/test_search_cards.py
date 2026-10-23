from soiluat.cards import KIND_RANK1, KIND_RANK2, KIND_RANK3, assemble_cards
from soiluat.search import cascade_search, lookup_so_hieu


def test_lookup_so_hieu_folded(db, sample_doc):
    ids = lookup_so_hieu(db, "15/2020/nd-cp")
    assert ids
    ids2 = lookup_so_hieu(db, "15/2020/NĐ-CP")
    assert set(ids) == set(ids2)


def test_fts_dieu_kien_style(db, sample_doc):
    ids, tier, _ = cascade_search(db, "bao cao dinh ky")
    assert ids
    assert tier <= 6


def test_cards_unconfirmed_is_candidate_not_confirmed(db, sample_doc):
    ids, _, _ = cascade_search(db, "bao cao")
    cards = assemble_cards(db, ids)
    kinds = {c.kind for c in cards}
    assert KIND_RANK1 not in kinds
    assert KIND_RANK2 in kinds or KIND_RANK3 in kinds


def test_cards_confirmed(db, sample_doc):
    db.execute("UPDATE links SET confirmed = 1")
    db.commit()
    ids, _, _ = cascade_search(db, "bao cao")
    cards = assemble_cards(db, ids)
    assert any(c.kind == KIND_RANK1 for c in cards)
    for c in cards:
        if c.kind == KIND_RANK1:
            assert "chủ thể" not in c.sample.lower()
            assert c.duty_text
            assert c.sanction_text


def test_synonym_union_not_and_all(db, sample_doc):
    db.execute(
        "INSERT INTO synonyms(term, alt, kind, approved) VALUES (?,?,?,1)",
        ("cham", "khong dung thoi han", "dong_nghia"),
    )
    db.commit()
    ids_with, _, note = cascade_search(db, "cham bao cao dinh ky")
    assert isinstance(ids_with, list)
    # tầng 3 không được làm hỏng tầng 2: vẫn ra báo cáo
    ids2, _, _ = cascade_search(db, "bao cao dinh ky")
    assert ids2


def test_card_warns_unclear_effect(db, sample_doc):
    ids, _, _ = cascade_search(db, "bao cao")
    cards = assemble_cards(db, ids)
    assert any("Hiệu lực chưa rõ" in c.warnings for c in cards)
