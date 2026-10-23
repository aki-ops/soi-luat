from soiluat.labels import extract_fines, labels_for_unit
from soiluat.parse import ParsedUnit


def test_extract_fines_prose():
    t = "Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng đối với hành vi x."
    assert extract_fines(t, False) == (10_000_000, 20_000_000)


def test_extract_fines_trieu():
    t = "Phạt tiền từ 10 triệu đồng đến 20 triệu đồng đối với hành vi x."
    assert extract_fines(t, False) == (10_000_000, 20_000_000)
    assert extract_fines("Phạt tiền 01 triệu đồng.", False) == (1_000_000, 1_000_000)


def test_extract_fines_gap_and_percent_null():
    assert extract_fines("Phạt tiền gấp hai lần mức phạt cũ.", False) == (None, None)
    assert extract_fines("Phạt tiền bằng 10% doanh thu.", False) == (None, None)
    t = "Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng."
    assert extract_fines(t, True) == (None, None)


def test_labels_skip_preamble():
    u = ParsedUnit(
        level="doan",
        addr_part="x",
        title="",
        text="Căn cứ Luật Các tổ chức tín dụng, Chính phủ ban hành.",
        parent_addr=None,
        confidence=1.0,
    )
    assert "NGHIA_VU" not in labels_for_unit(u)
