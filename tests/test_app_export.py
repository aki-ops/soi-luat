from pathlib import Path

from fastapi.testclient import TestClient

from soiluat.cards import assemble_cards
from soiluat.db import backup_db
from soiluat.export_word import export_cards
from soiluat.search import cascade_search


def test_app_does_not_import_ocr():
    import sys

    sys.modules.pop("soiluat.ocr", None)
    sys.modules.pop("soiluat.app", None)
    import soiluat.app  # noqa: F401

    assert "soiluat.ocr" not in sys.modules


def test_http_search(tmp_path, monkeypatch):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    from soiluat.app import app
    from soiluat.config import db_path
    from soiluat.db import connect, init_schema
    from soiluat.ingest import ingest_path

    conn = connect(db_path())
    init_schema(conn)
    src = Path(__file__).parent / "fixtures" / "nd15.txt"
    dest = tmp_path / "nd15.txt"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    ingest_path(conn, dest, tmp_path)
    conn.close()

    client = TestClient(app)
    r = client.get("/", params={"q": "bao cao dinh ky"})
    assert r.status_code == 200
    assert "Soi Luật" in r.text
    assert "Điều" in r.text or "báo cáo" in r.text.lower()
    assert "Hiệu lực chưa rõ" in r.text


def test_export_and_backup(db, sample_doc, tmp_path):
    db.execute("UPDATE links SET confirmed = 1")
    db.commit()
    ids, _, _ = cascade_search(db, "bao cao")
    cards = assemble_cards(db, ids)
    dest = tmp_path / "out.docx"
    export_cards(cards, dest)
    assert dest.exists() and dest.stat().st_size > 0
    bak = tmp_path / "backup" / "soiluat.db"
    backup_db(tmp_path / "soiluat.db", bak)
    assert bak.exists() and bak.stat().st_size > 0
    from soiluat.db import connect

    restored = connect(bak)
    n = restored.execute("SELECT COUNT(*) AS n FROM units").fetchone()["n"]
    restored.close()
    assert n > 0
