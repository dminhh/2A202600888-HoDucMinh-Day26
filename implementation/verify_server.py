#!/usr/bin/env python3
"""Human-readable smoke test for all MCP server components."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from init_db import create_database, DB_PATH
from db import SQLiteAdapter, ValidationError

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

passed = 0
failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"{GREEN}[PASS]{RESET} {msg}")


def fail(msg):
    global failed
    failed += 1
    print(f"{RED}[FAIL]{RESET} {msg}")


def section(title):
    print(f"\n{YELLOW}=== {title} ==={RESET}")


def main():
    if not os.path.exists(DB_PATH):
        create_database(DB_PATH)

    adapter = SQLiteAdapter(DB_PATH)

    # ---- 1. Table discovery ----
    section("Table Discovery")
    tables = adapter.list_tables()
    if set(tables) >= {"students", "courses", "enrollments"}:
        ok(f"Tables found: {tables}")
    else:
        fail(f"Missing required tables, got: {tables}")

    # ---- 2. Search ----
    section("Tool: search")

    result = adapter.search("students")
    if result["count"] >= 5:
        ok(f"search all students: {result['count']} rows")
    else:
        fail(f"Expected >=5 rows, got {result['count']}")

    result = adapter.search(
        "students",
        filters=[{"column": "cohort", "operator": "=", "value": "A1"}],
        order_by="score",
        descending=True,
        limit=5,
    )
    if result["count"] >= 1 and all(r["cohort"] == "A1" for r in result["rows"]):
        ok(f"search cohort=A1 ordered desc: scores={[r['score'] for r in result['rows']]}")
    else:
        fail(f"Filter/order test failed: {result}")

    result = adapter.search("students", columns=["name", "score"], limit=3, offset=0)
    if result["count"] == 3 and "cohort" not in result["rows"][0]:
        ok("search with column selection and pagination: OK")
    else:
        fail(f"Column selection / pagination failed: {result}")

    # ---- 3. Insert ----
    section("Tool: insert")

    result = adapter.insert("students", {
        "name": "Verify User", "cohort": "VER", "score": 99.0, "email": "verify@test.com",
    })
    if result.get("inserted_id"):
        ok(f"insert student: id={result['inserted_id']}, name={result['values']['name']}")
    else:
        fail(f"insert failed: {result}")

    result = adapter.insert("courses", {"name": "MCP Lab", "description": "FastMCP course"})
    if result.get("inserted_id"):
        ok(f"insert course: id={result['inserted_id']}")
    else:
        fail(f"insert course failed: {result}")

    # ---- 4. Aggregate ----
    section("Tool: aggregate")

    result = adapter.aggregate("students", "count")
    ok(f"aggregate count students: {result['results'][0]['value']}")

    result = adapter.aggregate("students", "avg", column="score")
    ok(f"aggregate avg score: {result['results'][0]['value']:.2f}")

    result = adapter.aggregate("students", "sum", column="score")
    ok(f"aggregate sum score: {result['results'][0]['value']:.2f}")

    result = adapter.aggregate("students", "min", column="score")
    ok(f"aggregate min score: {result['results'][0]['value']}")

    result = adapter.aggregate("students", "max", column="score")
    ok(f"aggregate max score: {result['results'][0]['value']}")

    result = adapter.aggregate("students", "avg", column="score", group_by="cohort")
    if len(result["results"]) >= 2:
        ok(f"aggregate avg score by cohort: {result['results']}")
    else:
        fail("aggregate group_by returned fewer groups than expected")

    result = adapter.aggregate(
        "students", "count",
        filters=[{"column": "cohort", "operator": "=", "value": "A1"}],
    )
    ok(f"aggregate count cohort=A1: {result['results'][0]['value']}")

    # ---- 5. Resources ----
    section("Resources")

    tables = adapter.list_tables()
    schema = {t: adapter.get_table_schema(t) for t in tables}
    schema_json = json.dumps(schema, indent=2)
    parsed = json.loads(schema_json)
    if "students" in parsed and "courses" in parsed and "enrollments" in parsed:
        ok("schema://database returns schema for all 3 tables")
    else:
        fail(f"schema://database missing tables, got: {list(parsed.keys())}")

    t_schema = adapter.get_table_schema("students")
    names = {c["name"] for c in t_schema}
    if {"id", "name", "cohort", "score"} <= names:
        ok(f"schema://table/students columns: {sorted(names)}")
    else:
        fail(f"schema://table/students missing expected columns, got: {names}")

    # ---- 6. Error handling ----
    section("Error Handling")

    try:
        adapter.search("nonexistent_table")
        fail("should have rejected unknown table")
    except ValidationError as e:
        ok(f"unknown table rejected: {e}")

    try:
        adapter.search("students", filters=[{"column": "ghost_col", "operator": "=", "value": "x"}])
        fail("should have rejected unknown column")
    except ValidationError as e:
        ok(f"unknown column rejected: {e}")

    try:
        adapter.search("students", filters=[{"column": "cohort", "operator": "INJECT--", "value": "x"}])
        fail("should have rejected bad operator")
    except ValidationError as e:
        ok(f"bad operator rejected: {e}")

    try:
        adapter.insert("students", {})
        fail("should have rejected empty insert")
    except ValidationError as e:
        ok(f"empty insert rejected: {e}")

    try:
        adapter.insert("students", {"bad_column": "x"})
        fail("should have rejected unknown column in insert")
    except ValidationError as e:
        ok(f"unknown column in insert rejected: {e}")

    try:
        adapter.aggregate("students", "DROP")
        fail("should have rejected bad metric")
    except ValidationError as e:
        ok(f"bad metric rejected: {e}")

    try:
        adapter.aggregate("students", "avg")  # missing column
        fail("should have required column for avg")
    except ValidationError as e:
        ok(f"avg without column rejected: {e}")

    try:
        adapter.aggregate("students", "count", group_by="nonexistent_col")
        fail("should have rejected unknown group_by column")
    except ValidationError as e:
        ok(f"unknown group_by column rejected: {e}")

    # ---- Summary ----
    print(f"\n{'=' * 50}")
    total = passed + failed
    print(f"Results: {GREEN}{passed}/{total} passed{RESET}", end="")
    if failed:
        print(f", {RED}{failed} failed{RESET}")
        sys.exit(1)
    else:
        print(f"  {GREEN}All checks passed!{RESET}")


if __name__ == "__main__":
    main()