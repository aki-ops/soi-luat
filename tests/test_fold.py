from soiluat.fold import fold_search, search_accent


def test_fold_dieu_kien():
    assert fold_search("Điều kiện hoạt động") == "dieu kien hoat dong"


def test_fold_d_stroke_to_d():
    assert fold_search("đồng") == "dong"
    assert fold_search("Đồng") == "dong"


def test_fold_eth_to_d():
    assert fold_search("Ðiều") == "dieu"


def test_fold_whitespace():
    assert fold_search("  a   b\n c ") == "a b c"


def test_search_accent_keeps_diacritics():
    assert search_accent("Thuế") == "thuế"
    assert "thue" not in search_accent("Thuế")
    assert search_accent("Ðiều") == search_accent("Điều")


def test_iy_ky_equals_ki():
    from soiluat.fold import iy_norm_token, iy_token_alts

    assert iy_norm_token("kỳ") == iy_norm_token("kì")
    assert "kỳ" in iy_token_alts("kì")
    assert iy_norm_token("hay") == "hay"
    assert iy_token_alts("hay") == ("hay",)

