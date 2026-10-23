import csv
from pathlib import Path

from soiluat.search import cascade_search

QUERIES = Path(__file__).parent / "fixtures" / "queries.csv"


def test_fixture_queries_hit_expected_dieu(db, sample_doc):
    rows = list(csv.DictReader(QUERIES.open(encoding="utf-8")))
    assert len(rows) >= 8
    for row in rows:
        ids, _, _ = cascade_search(db, row["query"])
        assert ids, row["query"]
        paths = [
            db.execute("SELECT path FROM units WHERE id = ?", (i,)).fetchone()["path"]
            for i in ids
        ]
        assert any(
            p == row["expect"] or p.startswith(row["expect"] + ".") for p in paths
        ), (row["query"], paths)
