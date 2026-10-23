from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_search_spec_excludes_tesseract():
    text = (ROOT / "pack" / "SoiLuat.spec").read_text(encoding="utf-8")
    assert "pytesseract" in text
    assert "excludes" in text
    assert "SoiLuat" in text


def test_bind_localhost_only():
    from soiluat.config import HOST, PORT

    assert HOST == "127.0.0.1"
    assert PORT == 8000


def test_importer_spec_allows_ocr():
    text = (ROOT / "pack" / "SoiLuatImporter.spec").read_text(encoding="utf-8")
    assert "SoiLuatImporter" in text
    assert "run_importer.py" in text
    search = (ROOT / "pack" / "SoiLuat.spec").read_text(encoding="utf-8")
    assert "run_search.py" in search
