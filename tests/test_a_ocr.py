"""L4/L5: ocr_status() theo H2, lỗi từng trang, khử nghiêng, OCR thật khi máy có Tesseract."""

import subprocess
import sys

import pytest

from soiluat import ocr
from soiluat.extract import ExtractedPage, extract_file


def _isolate(monkeypatch, tmp_path):
    for var in ("SOILUAT_TESSERACT", "SOILUAT_TESSDATA", "TESSDATA_PREFIX"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    monkeypatch.setenv("PATH", "")


def test_ocr_status_keys_and_env_priority(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    exe = tmp_path / "tess" / "tesseract.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    td = tmp_path / "td"
    td.mkdir()
    (td / "vie.traineddata").write_bytes(b"")
    (td / "osd.traineddata").write_bytes(b"")
    monkeypatch.setenv("SOILUAT_TESSERACT", str(exe))
    monkeypatch.setenv("SOILUAT_TESSDATA", str(td))
    st = ocr.ocr_status()
    assert set(st) == {"ok", "tesseract_cmd", "tessdata", "langs", "message"}
    assert st["tesseract_cmd"] == str(exe)
    assert st["tessdata"] == str(td)
    assert st["langs"] == ["osd", "vie"]


def test_ocr_status_tessdata_beside_exe_and_localappdata(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    exe = tmp_path / "tess" / "tesseract.exe"
    (exe.parent / "tessdata").mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setenv("SOILUAT_TESSERACT", str(exe.parent))  # cho phép trỏ thư mục
    assert ocr.find_tesseract() == str(exe)
    assert ocr.find_tessdata(str(exe)) == (None, [])  # tessdata chỉ có eng/osd: không tính
    (exe.parent / "tessdata" / "vie.traineddata").write_bytes(b"")
    assert ocr.find_tessdata(str(exe))[0] == str(exe.parent / "tessdata")
    lad = tmp_path / "lad" / "SoiLuat" / "tessdata"
    lad.mkdir(parents=True)
    (lad / "vie.traineddata").write_bytes(b"")
    assert ocr.find_tessdata(str(exe))[0] == str(lad)  # %LOCALAPPDATA%\SoiLuat đứng trước


def test_ocr_status_missing_vie_message(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(ocr, "find_tesseract", lambda: None)
    st = ocr.ocr_status()
    assert st["ok"] is False
    assert "tesseract.exe" in st["message"] and "vie.traineddata" in st["message"]


def test_ocr_module_does_not_import_engine_at_load():
    code = (
        "import sys, soiluat.ocr, soiluat.extract, soiluat.convert; "
        "bad = [m for m in ('pytesseract', 'PIL', 'win32com') if m in sys.modules]; "
        "assert not bad, bad"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_page_error_marks_loi_ocr(tmp_path, monkeypatch):
    pytest.importorskip("pytesseract")
    from PIL import Image

    monkeypatch.setattr(
        ocr,
        "ocr_status",
        lambda: {"ok": True, "tesseract_cmd": "x", "tessdata": str(tmp_path), "langs": ["vie"], "message": ""},
    )
    calls = []

    def fake(img, cfg, use_osd):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("hỏng")
        return "Điều 1. Chữ trang hai", 87.5

    monkeypatch.setattr(ocr, "ocr_image", fake)
    p = tmp_path / "s.tif"
    Image.new("L", (20, 20), 255).save(p, save_all=True, append_images=[Image.new("L", (20, 20), 255)])
    pages = ocr.maybe_ocr_pages(p, extract_file(p))
    assert [(x.ocr_status, x.text, x.ocr_conf) for x in pages] == [
        ("loi_ocr", "", None),
        ("ocr_xong", "Điều 1. Chữ trang hai", 87.5),
    ]
    assert pages[1].extraction_method == "ocr"


def _lines_image(angle: float):
    from PIL import Image, ImageDraw

    img = Image.new("L", (1200, 1600), 255)
    d = ImageDraw.Draw(img)
    for y in range(150, 1450, 60):
        for x in range(120, 1050, 70):
            d.rectangle([x, y, x + 50, y + 22], fill=0)  # "chữ" giả theo dòng
    return img.rotate(angle, expand=True, fillcolor=255)


@pytest.mark.parametrize("angle", [0.0, 2.0, -3.5])
def test_estimate_skew(angle):
    pytest.importorskip("PIL")
    assert abs(ocr.estimate_skew(_lines_image(angle)) + angle) <= 0.3


def test_real_ocr_on_png(tmp_path):
    if not ocr.ocr_status()["ok"]:
        pytest.skip("máy không có Tesseract + vie")
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1400, 300), "white")
    font = ImageFont.load_default(size=48)
    ImageDraw.Draw(img).text((60, 100), "DIEU 5. HIEU LUC THI HANH 2024", fill="black", font=font)
    p = tmp_path / "trang.png"
    img.rotate(2, expand=True, fillcolor="white").save(p)
    pages = ocr.maybe_ocr_pages(p, extract_file(p))
    assert pages[0].ocr_status == "ocr_xong"
    assert "DIEU 5" in pages[0].text.upper() and "2024" in pages[0].text
    assert pages[0].ocr_conf is not None and 0 <= pages[0].ocr_conf <= 100


def _fake_pipeline(monkeypatch, first, second, rot):
    pytest.importorskip("PIL")
    calls = {"osd": 0, "ocr": []}
    results = iter([first, second])

    def fake_data(gray, cfg):
        calls["ocr"].append(gray.size)
        return next(results)

    def fake_osd(gray, cfg):
        calls["osd"] += 1
        return rot

    monkeypatch.setattr(ocr, "ocr_data", fake_data)
    monkeypatch.setattr(ocr, "osd_rotation", fake_osd)
    return calls


def _page_img():
    from PIL import Image

    return Image.new("L", (1000, 1400), 255)  # 1,4 MP


def test_osd_skipped_when_first_pass_good(monkeypatch):
    calls = _fake_pipeline(monkeypatch, ("chữ " * 300, 88.0), None, 90)
    assert ocr.ocr_image(_page_img(), "", True) == ("chữ " * 300, 88.0)
    assert calls["osd"] == 0 and len(calls["ocr"]) == 1


def test_osd_on_low_conf_keeps_better_pass(monkeypatch):
    calls = _fake_pipeline(monkeypatch, ("rác", 31.0), ("Điều 1. Đúng chiều", 90.0), 90)
    assert ocr.ocr_image(_page_img(), "", True) == ("Điều 1. Đúng chiều", 90.0)
    assert calls["osd"] == 1
    assert calls["ocr"] == [(1000, 1400), (1400, 1000)]  # lượt hai trên ảnh đã xoay 90°


def test_osd_on_sparse_text_but_keeps_first_if_not_better(monkeypatch):
    # conf cao nhưng chỉ vài chữ trên cả trang → thử OSD; lượt hai kém hơn thì giữ lượt đầu
    calls = _fake_pipeline(monkeypatch, ("ab", 80.0), ("x", 40.0), 180)
    assert ocr.ocr_image(_page_img(), "", True) == ("ab", 80.0)
    assert calls["osd"] == 1


def test_osd_no_rotation_no_second_pass(monkeypatch):
    calls = _fake_pipeline(monkeypatch, ("rác", 30.0), None, 0)
    assert ocr.ocr_image(_page_img(), "", True) == ("rác", 30.0)
    assert len(calls["ocr"]) == 1
    calls = _fake_pipeline(monkeypatch, ("rác", 30.0), None, 90)
    ocr.ocr_image(_page_img(), "", False)  # máy không có osd.traineddata
    assert calls["osd"] == 0


def test_real_ocr_rotated_page_uses_osd(tmp_path):
    st = ocr.ocr_status()
    if not st["ok"] or "osd" not in st["langs"]:
        pytest.skip("máy không có Tesseract + vie + osd")
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("L", (1700, 2200), 255)
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=36)  # chữ thường: OSD đoán chiều kém với toàn chữ hoa
    for i in range(30):
        d.text((120, 120 + i * 65), f"Dieu {i + 1}. Doanh nghiep phai nop bao cao giam sat hang quy.", fill=0, font=font)
    p = tmp_path / "xoay.png"
    img.rotate(90, expand=True, fillcolor=255).save(p)
    pages = ocr.maybe_ocr_pages(p, extract_file(p))
    assert "giam sat hang quy" in pages[0].text  # lượt đầu (đọc ngang) chỉ ~35 conf
    assert pages[0].ocr_conf is not None and pages[0].ocr_conf >= 75
