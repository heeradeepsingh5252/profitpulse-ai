from contextlib import contextmanager
from typing import Iterator

from profitpulse.config import DATABASE_URL

_pool = None


def get_pool():
    """Create the PostgreSQL pool on first use, allowing pure unit tests without DB deps."""
    global _pool
    if _pool is None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        _pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1,
            max_size=10,
            timeout=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
        _pool.wait(timeout=10)
    return _pool


@contextmanager
def organization_connection(organization_id: str) -> Iterator:
    """Set transaction-local tenant context for PostgreSQL RLS.

    Demo only: the organization ID is supplied in a request header. Production
    must derive it from a verified identity and a membership/authorization check.
    """
    with get_pool().connection() as conn:
        with conn.transaction():
            conn.execute(
                "SELECT set_config('app.current_organization_id', %s, true)",
                (str(organization_id),),
            )
            yield conn


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
