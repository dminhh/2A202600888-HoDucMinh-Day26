import sqlite3
from typing import Optional

SUPPORTED_OPERATORS = {"=", "!=", ">", "<", ">=", "<=", "like"}
SUPPORTED_METRICS   = {"count", "avg", "sum", "min", "max"}


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def list_tables(self) -> list:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        return [r[0] for r in rows]

    def get_table_schema(self, table: str) -> list:
        self._validate_table(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [
            {
                "cid":     row[0],
                "name":    row[1],
                "type":    row[2],
                "notnull": bool(row[3]),
                "default": row[4],
                "pk":      bool(row[5]),
            }
            for row in rows
        ]

    # ------------------------------------------------------------------ #
    # Internal validators                                                  #
    # ------------------------------------------------------------------ #

    def _validate_table(self, table: str):
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(
                f"Unknown table '{table}'. Available: {tables}"
            )

    def _validate_columns(self, table: str, columns: list):
        schema   = self.get_table_schema(table)
        valid    = {c["name"] for c in schema}
        bad_cols = [c for c in columns if c not in valid]
        if bad_cols:
            raise ValidationError(
                f"Unknown column(s) {bad_cols} in '{table}'. "
                f"Available: {sorted(valid)}"
            )

    def _build_where(self, table: str, filters: list) -> tuple:
        """Returns (where_clause_str, params_list)."""
        schema        = self.get_table_schema(table)
        valid         = {c["name"] for c in schema}
        parts, params = [], []
        for f in filters:
            col = f.get("column")
            op  = str(f.get("operator", "=")).lower()
            val = f.get("value")
            if col not in valid:
                raise ValidationError(f"Unknown column '{col}' in '{table}'")
            if op not in SUPPORTED_OPERATORS:
                raise ValidationError(
                    f"Unsupported operator '{op}'. "
                    f"Supported: {sorted(SUPPORTED_OPERATORS)}"
                )
            parts.append(f"{col} {op} ?")
            params.append(val)
        clause = ("WHERE " + " AND ".join(parts)) if parts else ""
        return clause, params

    # ------------------------------------------------------------------ #
    # Tools                                                                #
    # ------------------------------------------------------------------ #

    def search(
        self,
        table: str,
        columns: Optional[list] = None,
        filters: Optional[list] = None,
        limit: int = 20,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = False,
    ) -> dict:
        self._validate_table(table)
        schema     = self.get_table_schema(table)
        valid_cols = {c["name"] for c in schema}

        if columns:
            self._validate_columns(table, columns)
            col_clause = ", ".join(columns)
        else:
            col_clause = "*"

        where, params = self._build_where(table, filters or [])

        order_clause = ""
        if order_by:
            if order_by not in valid_cols:
                raise ValidationError(f"Unknown column '{order_by}' for ORDER BY")
            direction    = "DESC" if descending else "ASC"
            order_clause = f"ORDER BY {order_by} {direction}"

        sql = (
            f"SELECT {col_clause} FROM {table} "
            f"{where} {order_clause} LIMIT ? OFFSET ?"
        )
        params += [limit, offset]

        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        return {"table": table, "count": len(rows), "rows": rows}

    def insert(self, table: str, values: dict) -> dict:
        if not values:
            raise ValidationError("'values' cannot be empty")
        self._validate_table(table)
        self._validate_columns(table, list(values.keys()))

        cols         = list(values.keys())
        placeholders = ", ".join("?" for _ in cols)
        col_names    = ", ".join(cols)
        sql          = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
        row_values   = [values[c] for c in cols]

        with self.connect() as conn:
            cursor = conn.execute(sql, row_values)
            conn.commit()
            row_id = cursor.lastrowid
        return {"table": table, "inserted_id": row_id, "values": values}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: Optional[str] = None,
        filters: Optional[list] = None,
        group_by: Optional[str] = None,
    ) -> dict:
        metric = metric.lower()
        if metric not in SUPPORTED_METRICS:
            raise ValidationError(
                f"Unsupported metric '{metric}'. "
                f"Supported: {sorted(SUPPORTED_METRICS)}"
            )

        self._validate_table(table)
        schema     = self.get_table_schema(table)
        valid_cols = {c["name"] for c in schema}

        if metric == "count":
            agg_expr = "COUNT(*)"
        else:
            if not column:
                raise ValidationError(f"metric '{metric}' requires a 'column'")
            if column not in valid_cols:
                raise ValidationError(f"Unknown column '{column}' in '{table}'")
            agg_expr = f"{metric.upper()}({column})"

        where, params = self._build_where(table, filters or [])

        if group_by:
            if group_by not in valid_cols:
                raise ValidationError(f"Unknown column '{group_by}' for GROUP BY")
            group_clause = f"GROUP BY {group_by}"
            sql = (
                f"SELECT {group_by}, {agg_expr} AS value "
                f"FROM {table} {where} {group_clause}"
            )
        else:
            sql = f"SELECT {agg_expr} AS value FROM {table} {where}"

        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        return {
            "table":    table,
            "metric":   metric,
            "column":   column,
            "group_by": group_by,
            "results":  rows,
        }
