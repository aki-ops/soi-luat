from pathlib import Path

from soiluat.importer import main


def test_importer_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    src = Path(__file__).parent / "fixtures" / "nd15.txt"
    dest = tmp_path / "in" / "nd15.txt"
    dest.parent.mkdir()
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    assert main([str(dest)]) == 0
    db = tmp_path / "soiluat.db"
    assert db.exists()
