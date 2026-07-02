import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from init_db import create_database


# ---- DB creation tests ----

def test_create_database_creates_file():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    os.unlink(path)
    result = create_database(path)
    assert os.path.exists(result)
    os.unlink(path)


def test_create_database_has_required_tables():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    os.unlink(path)
    create_database(path)
    conn = sqlite3.connect(path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    os.unlink(path)
    assert tables == {"students", "courses", "enrollments"}


def test_create_database_has_seed_data():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    os.unlink(path)
    create_database(path)
    conn = sqlite3.connect(path)
    count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    conn.close()
    os.unlink(path)
    assert count >= 5


# ---- SQLiteAdapter tests ----

from db import SQLiteAdapter, ValidationError


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    create_database(path)
    return path


@pytest.fixture
def adapter(db_path):
    return SQLiteAdapter(db_path)


def test_list_tables(adapter):
    tables = adapter.list_tables()
    assert set(tables) >= {"students", "courses", "enrollments"}


def test_get_table_schema(adapter):
    cols = adapter.get_table_schema("students")
    names = {c["name"] for c in cols}
    assert names >= {"id", "name", "cohort", "score"}


def test_get_table_schema_unknown_table(adapter):
    with pytest.raises(ValidationError, match="Unknown table"):
        adapter.get_table_schema("nonexistent")


def test_search_all(adapter):
    result = adapter.search("students")
    assert result["count"] >= 5
    assert "rows" in result
    assert result["table"] == "students"


def test_search_with_filter(adapter):
    result = adapter.search(
        "students",
        filters=[{"column": "cohort", "operator": "=", "value": "A1"}],
    )
    assert result["count"] >= 1
    for row in result["rows"]:
        assert row["cohort"] == "A1"


def test_search_with_columns(adapter):
    result = adapter.search("students", columns=["name", "score"])
    assert "name" in result["rows"][0]
    assert "cohort" not in result["rows"][0]


def test_search_with_ordering(adapter):
    result = adapter.search("students", order_by="score", descending=True, limit=3)
    scores = [r["score"] for r in result["rows"]]
    assert scores == sorted(scores, reverse=True)


def test_search_with_pagination(adapter):
    page1 = adapter.search("students", limit=2, offset=0)["rows"]
    page2 = adapter.search("students", limit=2, offset=2)["rows"]
    assert page1[0]["id"] != page2[0]["id"]


def test_search_unknown_table(adapter):
    with pytest.raises(ValidationError, match="Unknown table"):
        adapter.search("ghost")


def test_search_unknown_column_in_filter(adapter):
    with pytest.raises(ValidationError, match="Unknown column"):
        adapter.search(
            "students",
            filters=[{"column": "ghost", "operator": "=", "value": "x"}],
        )


def test_search_unsupported_operator(adapter):
    with pytest.raises(ValidationError, match="Unsupported operator"):
        adapter.search(
            "students",
            filters=[{"column": "cohort", "operator": "DROP", "value": "x"}],
        )


# ---- insert tests ----

def test_insert_student(adapter):
    result = adapter.insert(
        "students",
        {"name": "Zara Test", "cohort": "Z1", "score": 77.0, "email": "zara@test.com"},
    )
    assert result["inserted_id"] is not None
    assert result["values"]["name"] == "Zara Test"


def test_insert_empty_values(adapter):
    with pytest.raises(ValidationError, match="cannot be empty"):
        adapter.insert("students", {})


def test_insert_unknown_table(adapter):
    with pytest.raises(ValidationError, match="Unknown table"):
        adapter.insert("ghost", {"name": "X"})


def test_insert_unknown_column(adapter):
    with pytest.raises(ValidationError, match="Unknown column"):
        adapter.insert("students", {"ghost_col": "X"})


def test_insert_persists(adapter):
    before = adapter.search("students")["count"]
    adapter.insert("students", {"name": "Persist Test", "cohort": "P1", "score": 55.0})
    after = adapter.search("students")["count"]
    assert after == before + 1


# ---- aggregate tests ----

def test_aggregate_count(adapter):
    result = adapter.aggregate("students", "count")
    assert result["results"][0]["value"] >= 5


def test_aggregate_avg(adapter):
    result = adapter.aggregate("students", "avg", column="score")
    assert result["results"][0]["value"] > 0


def test_aggregate_sum(adapter):
    result = adapter.aggregate("students", "sum", column="score")
    assert result["results"][0]["value"] > 0


def test_aggregate_min_max(adapter):
    mn = adapter.aggregate("students", "min", column="score")["results"][0]["value"]
    mx = adapter.aggregate("students", "max", column="score")["results"][0]["value"]
    assert mn <= mx


def test_aggregate_group_by(adapter):
    result = adapter.aggregate("students", "avg", column="score", group_by="cohort")
    assert len(result["results"]) >= 2
    for row in result["results"]:
        assert "cohort" in row
        assert "value" in row


def test_aggregate_count_with_filter(adapter):
    result = adapter.aggregate(
        "students",
        "count",
        filters=[{"column": "cohort", "operator": "=", "value": "A1"}],
    )
    assert result["results"][0]["value"] >= 1


def test_aggregate_bad_metric(adapter):
    with pytest.raises(ValidationError, match="Unsupported metric"):
        adapter.aggregate("students", "DROP")


def test_aggregate_metric_requires_column(adapter):
    with pytest.raises(ValidationError, match="requires a 'column'"):
        adapter.aggregate("students", "avg")


def test_aggregate_unknown_group_by(adapter):
    with pytest.raises(ValidationError, match="Unknown column"):
        adapter.aggregate("students", "count", group_by="ghost")