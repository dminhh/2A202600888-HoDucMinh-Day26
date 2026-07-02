import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from init_db import create_database
from db import SQLiteAdapter, ValidationError


@pytest.fixture
def adapter(tmp_path):
    path = str(tmp_path / "test.db")
    create_database(path)
    return SQLiteAdapter(path)


# ---- search tool ----

def test_tool_search_valid(adapter):
    result = adapter.search(
        "students",
        filters=[{"column": "cohort", "operator": "=", "value": "A1"}],
    )
    assert isinstance(result["rows"], list)
    assert result["count"] >= 1


def test_tool_search_bad_table_raises(adapter):
    with pytest.raises(ValidationError):
        adapter.search("nowhere")


def test_tool_search_ordered_pagination(adapter):
    result = adapter.search("students", order_by="score", descending=True, limit=3, offset=0)
    assert result["count"] == 3
    scores = [r["score"] for r in result["rows"]]
    assert scores == sorted(scores, reverse=True)


# ---- insert tool ----

def test_tool_insert_valid(adapter):
    result = adapter.insert(
        "students",
        {"name": "MCP User", "cohort": "MCP1", "score": 100.0},
    )
    assert result["inserted_id"] > 0


def test_tool_insert_empty_raises(adapter):
    with pytest.raises(ValidationError):
        adapter.insert("students", {})


def test_tool_insert_unknown_col_raises(adapter):
    with pytest.raises(ValidationError):
        adapter.insert("students", {"does_not_exist": "x"})


# ---- aggregate tool ----

def test_tool_aggregate_count(adapter):
    result = adapter.aggregate("students", "count")
    assert result["results"][0]["value"] >= 5


def test_tool_aggregate_avg(adapter):
    result = adapter.aggregate("students", "avg", column="score")
    val = result["results"][0]["value"]
    assert 0 < val < 200


def test_tool_aggregate_sum(adapter):
    result = adapter.aggregate("students", "sum", column="score")
    assert result["results"][0]["value"] > 0


def test_tool_aggregate_min_max(adapter):
    mn = adapter.aggregate("students", "min", column="score")["results"][0]["value"]
    mx = adapter.aggregate("students", "max", column="score")["results"][0]["value"]
    assert mn <= mx


def test_tool_aggregate_group_by(adapter):
    result = adapter.aggregate("students", "avg", column="score", group_by="cohort")
    assert len(result["results"]) >= 2
    for row in result["results"]:
        assert "cohort" in row and "value" in row


def test_tool_aggregate_bad_metric_raises(adapter):
    with pytest.raises(ValidationError):
        adapter.aggregate("students", "HACK")


def test_tool_aggregate_avg_no_column_raises(adapter):
    with pytest.raises(ValidationError):
        adapter.aggregate("students", "avg")


# ---- resources (via adapter helpers) ----

def test_resource_database_schema(adapter):
    import json
    tables = adapter.list_tables()
    schema = {t: adapter.get_table_schema(t) for t in tables}
    assert "students" in schema
    assert any(c["name"] == "cohort" for c in schema["students"])


def test_resource_table_schema_valid(adapter):
    cols = adapter.get_table_schema("students")
    names = {c["name"] for c in cols}
    assert "id" in names and "name" in names


def test_resource_table_schema_invalid(adapter):
    with pytest.raises(ValidationError):
        adapter.get_table_schema("ghost")