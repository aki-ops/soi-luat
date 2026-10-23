from pathlib import Path

from soiluat.parse import parse_structure
from soiluat.sohieu import find_so_hieu

FIXTURE = Path(__file__).parent / "fixtures" / "nd15.txt"


def test_parse_dieu_khoan():
    text = FIXTURE.read_text(encoding="utf-8")
    r = parse_structure(text)
    assert r.so_hieu and "15/2020" in r.so_hieu
    dieu = [u for u in r.units if u.level == "dieu"]
    assert len(dieu) >= 3
    addrs = {u.addr_part for u in r.units}
    assert any(a == "D5.K1" or a.startswith("D5.K1") for a in addrs)
    assert r.c_khoan == 1.0
    assert r.c_phu > 0.5
    assert r.c_lien_tuc == 1.0
    assert r.s >= 0.6
    assert r.tier in (1, 2)


def test_c_lien_tuc_consecutive():
    text = (
        "Nghị định số 1/2020/NĐ-CP\n"
        "Điều 1. Một\n1. Khoản một.\n"
        "Điều 2. Hai\n1. Khoản hai.\n"
        "Điều 3. Ba\n1. Khoản ba.\n"
    )
    r = parse_structure(text)
    assert r.c_lien_tuc == 1.0
    assert r.s >= 0.6


def test_s_below_threshold_uses_tier3():
    text = (
        "Nghị định số 1/2020/NĐ-CP\n"
        "Điều 1. Một\n5. Khoản năm.\n"
        "Điều 9. Chín\n8. Khoản tám.\n"
        "Điều 20. Hai mươi\n3. Khoản ba.\n"
    )
    r = parse_structure(text)
    assert r.tier == 3
    assert all(u.level == "doan" for u in r.units)


def test_force_doan():
    text = "Nghị định số 1/2020/NĐ-CP\nĐiều 1. Một\n1. Khoản một.\nĐiều 2. Hai\n1. Khoản hai.\n"
    r = parse_structure(text, force_doan=True)
    assert r.tier == 3
    assert r.so_hieu and "1/2020" in r.so_hieu


def test_parse_fallback_without_dieu():
    r = parse_structure("Đây là đoạn văn không có cấu trúc điều khoản gì cả. " * 5)
    assert r.tier == 3
    assert r.units
    assert all(u.level == "doan" for u in r.units)


def test_find_so_hieu():
    assert find_so_hieu("xem 15/2020/NĐ-CP ngay") is not None
