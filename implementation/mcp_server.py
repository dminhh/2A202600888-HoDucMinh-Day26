import json
import os
import sys
from typing import Optional, List

sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from db import SQLiteAdapter, ValidationError
from init_db import create_database, DB_PATH

# Bootstrap DB on first run
if not os.path.exists(DB_PATH):
    create_database(DB_PATH)

adapter = SQLiteAdapter(DB_PATH)
mcp = FastMCP("SQLite Lab MCP Server")


@mcp.tool(name="search")
def search(
    table: str,
    filters: Optional[List[dict]] = None,
    columns: Optional[List[str]] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: Optional[str] = None,
    descending: bool = False,
) -> dict:
    """Search rows in a database table.

    Args:
        table: Table name — one of: students, courses, enrollments.
        filters: List of filter dicts: [{"column": "...", "operator": "...", "value": ...}].
                 Allowed operators: =, !=, >, <, >=, <=, like
        columns: Column names to return (omit for all columns).
        limit: Max rows to return (default 20).
        offset: Row offset for pagination (default 0).
        order_by: Column name to sort by.
        descending: Sort descending when True (default False).

    Returns:
        {"table": str, "count": int, "rows": list[dict]}
    """
    try:
        return adapter.search(
            table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    except ValidationError as e:
        raise ValueError(str(e))


@mcp.tool(name="insert")
def insert(table: str, values: dict) -> dict:
    """Insert a new row into a database table.

    Args:
        table: Table name — one of: students, courses, enrollments.
        values: Dict mapping column names to values, e.g.
                {"name": "Alice", "cohort": "A1", "score": 95.0}

    Returns:
        {"table": str, "inserted_id": int, "values": dict}
    """
    try:
        return adapter.insert(table, values)
    except ValidationError as e:
        raise ValueError(str(e))


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: Optional[str] = None,
    filters: Optional[List[dict]] = None,
    group_by: Optional[str] = None,
) -> dict:
    """Compute aggregate metrics on a database table.

    Args:
        table: Table name — one of: students, courses, enrollments.
        metric: Aggregate function — one of: count, avg, sum, min, max.
        column: Column to aggregate (required for avg, sum, min, max).
        filters: Optional filter list (same format as search).
        group_by: Optional column to group results by.

    Returns:
        {"table", "metric", "column", "group_by", "results": list[dict]}
    """
    try:
        return adapter.aggregate(
            table,
            metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
    except ValidationError as e:
        raise ValueError(str(e))


@mcp.resource("schema://database")
def database_schema() -> str:
    """Full database schema — all tables and their column definitions as JSON."""
    tables = adapter.list_tables()
    schema = {t: adapter.get_table_schema(t) for t in tables}
    return json.dumps(schema, indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Schema for a single database table as JSON.

    Args:
        table_name: Name of the table (students | courses | enrollments).
    """
    try:
        cols = adapter.get_table_schema(table_name)
        return json.dumps({"table": table_name, "columns": cols}, indent=2)
    except ValidationError as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
