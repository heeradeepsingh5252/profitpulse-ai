
from contextlib import contextmanager
from threading import Lock
from typing import Iterator

from profitpulse.config import DATABASE_URL

_pool = None
_pool_lock = Lock()


def get_pool():
    """Create and return a healthy PostgreSQL connection pool."""
    global _pool

    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    with _pool_lock:
        # Reuse an existing healthy pool.
        if _pool is not None and not _pool.closed:
            return _pool

        # Create a new pool without opening connections immediately.
        new_pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1,
            max_size=10,
            timeout=10,
            kwargs={"row_factory": dict_row},
            open=False,
        )

        try:
            # Open the pool and verify database connectivity.
            new_pool.open(wait=True, timeout=30)

        except Exception:
            if not new_pool.closed:
                new_pool.close()
            raise

        # Store the pool only after successful initialization.
        _pool = new_pool
        return _pool


@contextmanager
def organization_connection(organization_id: str) -> Iterator:
    """Set transaction-local tenant context for PostgreSQL RLS.

    Demo only: organization identity is supplied through a request header.
    Production must use verified user identity and membership authorization.
    """
    with get_pool().connection() as conn:
        with conn.transaction():
            conn.execute(
                "SELECT set_config('app.current_organization_id', %s, true)",
                (str(organization_id),),
            )
            yield conn


def close_pool() -> None:
    """Close the PostgreSQL connection pool during application shutdown."""
    global _pool

    with _pool_lock:
        pool = _pool
        _pool = None

    if pool is not None and not pool.closed:
        pool.close()
