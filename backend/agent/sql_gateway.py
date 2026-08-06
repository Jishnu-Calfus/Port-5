"""
The actual security boundary for the data agent. An LLM drafts SQL text;
this file is the deterministic, non-LLM gate that decides whether that SQL
is allowed to run at all. Nothing in this file calls the model or touches a
live database connection -- it's a pure function, which is what makes it
possible to unit-test exhaustively (see test_sql_gateway.py) without any
Postgres/OpenAI dependency.

The read-only Postgres role is the first line of defense (a write attempt
fails no matter what). This gateway is the second: it makes sure the SQL
only ever touches the tables/columns we actually recognize, is a single
plain SELECT, and stays within a sane row limit -- independent of whether
the database permissions are ever misconfigured.
"""
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

from backend.agent.schema_registry import ALLOWED_TABLES

DEFAULT_LIMIT = 500
MAX_LIMIT = 500

# Postgres functions that read files, control other connections, or reach
# outside this database entirely. None of these have any legitimate use in
# an analytics question about feedback data.
DANGEROUS_FUNCTIONS = {
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "dblink", "dblink_exec",
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
}

# A qualify() schema needs a type per column, but the type itself is never
# checked for our purposes -- only whether the column exists. "TEXT" is a
# placeholder, not a claim about the real column type.
_QUALIFY_SCHEMA = {table: {col: "TEXT" for col in cols} for table, cols in ALLOWED_TABLES.items()}


class SQLValidationError(Exception):
    """Raised with a human-readable reason. This message is meant to be fed
    back to whatever drafted the SQL so it can correct itself -- write the
    reason as an instruction, not just a rejection."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def validate_and_rewrite(raw_sql: str) -> str:
    """Returns SQL that is safe to execute, or raises SQLValidationError.
    Checks run in order from cheapest/most-obviously-dangerous to most
    detailed, and the only rewrite (adding a LIMIT) happens last, after
    every rejection check has already passed -- rewriting is never used to
    "fix" something that would otherwise be rejected."""
    tree = _require_single_select(raw_sql)
    _require_known_tables_and_columns(tree)
    _reject_dangerous_functions(tree)
    _reject_nested_write_statements(tree)
    return _enforce_limit(tree).sql(dialect="postgres")


def _require_single_select(raw_sql: str) -> exp.Select:
    # sqlglot.parse() splits on statement-separating semicolons and returns
    # one parsed statement per piece. More than one non-empty statement
    # means someone tried to smuggle a second command in after a semicolon
    # (the classic "; DROP TABLE ..." injection shape) -- reject before
    # even looking at what the extra statement contains.
    statements = [s for s in sqlglot.parse(raw_sql, dialect="postgres") if s is not None]
    if len(statements) != 1:
        raise SQLValidationError(
            f"Expected exactly one SQL statement, got {len(statements)}. "
            "Do not separate multiple statements with a semicolon."
        )

    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise SQLValidationError(
            f"Only SELECT statements are allowed, not {type(tree).__name__}."
        )
    return tree


def _require_known_tables_and_columns(tree: exp.Select) -> None:
    # Table check first, and separately from column checking: qualify()
    # below resolves column->table references, but it does NOT reject a
    # table that simply isn't in the schema dict (confirmed by testing --
    # a query against a Postgres system table like pg_shadow "qualifies"
    # fine even though it's nowhere in ALLOWED_TABLES). So table names have
    # to be checked explicitly, not left to qualify() to catch.
    for table in tree.find_all(exp.Table):
        if table.name not in ALLOWED_TABLES:
            raise SQLValidationError(
                f"Unknown table '{table.name}'. Allowed tables: {', '.join(sorted(ALLOWED_TABLES))}."
            )

    # qualify() resolves every column reference to the table it actually
    # belongs to (even ones written without a table prefix, as long as
    # that's unambiguous), and raises if a column can't be resolved at all
    # -- e.g. because it's genuinely ambiguous across a join, or doesn't
    # exist anywhere. Anything qualify() can't confidently resolve is
    # rejected rather than guessed at.
    try:
        qualified = qualify(tree.copy(), schema=_QUALIFY_SCHEMA)
    except Exception as exc:
        raise SQLValidationError(
            f"Could not resolve every column unambiguously ({exc}). "
            "Qualify columns with their table name, e.g. fact_feedback.timestamp."
        )

    for column in qualified.find_all(exp.Column):
        table_name = column.table
        if table_name and column.name not in ALLOWED_TABLES.get(table_name, set()):
            raise SQLValidationError(f"Unknown column '{table_name}.{column.name}'.")


def _reject_dangerous_functions(tree: exp.Select) -> None:
    for func in tree.find_all(exp.Func, exp.Anonymous):
        name = (func.name or "").lower()
        if name in DANGEROUS_FUNCTIONS:
            raise SQLValidationError(f"Function '{name}' is not permitted.")


def _reject_nested_write_statements(tree: exp.Select) -> None:
    # Redundant with _require_single_select in the common case, but catches
    # a write statement smuggled inside a CTE, e.g.
    # "WITH x AS (DELETE FROM fact_feedback RETURNING *) SELECT * FROM x" --
    # that whole thing still parses as a single top-level SELECT.
    write_types = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create)
    if any(tree.find_all(*write_types)):
        raise SQLValidationError("Query must not contain any data- or schema-modifying clause.")


def _enforce_limit(tree: exp.Select) -> exp.Select:
    existing = tree.args.get("limit")
    if existing is None:
        return tree.limit(DEFAULT_LIMIT)

    try:
        requested = int(existing.expression.this)
    except (AttributeError, ValueError, TypeError):
        requested = None

    if requested is None or requested > MAX_LIMIT:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(MAX_LIMIT)))
    return tree
