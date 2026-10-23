import pytest

from soiluat import ocr
from soiluat.extract import ExtractedPage
from soiluat.ocr import OcrUnavailable, maybe_ocr_pages


def test_maybe_ocr_skips_text_ok(tmp_path):
    pages = [
        ExtractedPage(
            page_no=1,
            text="đã có chữ",
            kind="text_ok",
            extraction_method="pdf_text",
            ocr_status="khong_can",
        )
    ]
    out = maybe_ocr_pages(tmp_path / "no.pdf", pages)
    assert out[0].text == "đã có chữ"
    assert out[0].extraction_method == "pdf_text"
    assert out[0].ocr_status == "khong_can"


def test_maybe_ocr_without_engine_raises(tmp_path, monkeypatch):
    # H2: thiếu OCR mà có trang cần OCR thì báo lỗi, không im lặng trả 0 chữ
    monkeypatch.setattr(
        ocr,
        "ocr_status",
        lambda: {"ok": False, "tesseract_cmd": None, "tessdata": None, "langs": [],
                 "message": "Không tìm thấy tesseract.exe"},
    )
    pages = [
        ExtractedPage(
            page_no=1,
            text="",
            kind="image",
            extraction_method="pdf_text",
            ocr_status="cho_ocr",
        )
    ]
    with pytest.raises(OcrUnavailable, match="tesseract"):
        maybe_ocr_pages(tmp_path / "missing.pdf", pages)
    assert pages[0].ocr_status == "cho_ocr"
