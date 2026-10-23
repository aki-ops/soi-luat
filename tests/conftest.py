from __future__ import annotations

from pathlib import Path

import pytest

from soiluat.db import connect, init_schema
from soiluat.ingest import ingest_path

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _allow_test_host(monkeypatch):
    monkeypatch.setenv("SOILUAT_ALLOW_TEST_HOST", "1")


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "soiluat.db")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_doc(db, tmp_path):
    src = FIXTURES / "nd15.txt"
    dest = tmp_path / "nd15.txt"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    doc_id = ingest_path(db, dest, tmp_path)
    return doc_id
