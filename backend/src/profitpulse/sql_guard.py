import sqlglot
from sqlglot import exp


class UnsafeQueryError(ValueError):
    pass


def validate_read_only_select(sql: str, max_rows: int = 500) -> str:
    """Allow one read-only SELECT statement and cap returned rows.

    This is a starter validation layer, not a complete SQL sandbox. Production
    execution must additionally use a restricted DB role, statement timeout,
    schema/table allowlists, resource limits and audit logging.
    """
    statements = sqlglot.parse(sql, read="postgres")
    if len(statements) != 1 or statements[0] is None:
        raise UnsafeQueryError("Exactly one SQL statement is allowed")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise UnsafeQueryError("Only SELECT queries are allowed")
    if any(isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command)) for node in tree.walk()):
        raise UnsafeQueryError("Query contains a prohibited operation")
    if tree.args.get("into") is not None or tree.args.get("locks"):
        raise UnsafeQueryError("SELECT INTO and row locking are prohibited")
    if not tree.args.get("limit"):
        tree = tree.limit(max_rows)
    return tree.sql(dialect="postgres")
