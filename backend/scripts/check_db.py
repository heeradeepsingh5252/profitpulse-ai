from profitpulse.config import DEMO_ORGANIZATION_ID
from profitpulse.db import get_pool, organization_connection


def main():
    with get_pool().connection() as conn:
        print("Database connection: OK")
        version = conn.execute("SELECT version() AS version").fetchone()["version"]
        print("PostgreSQL:", version.split(",")[0])

    with organization_connection(DEMO_ORGANIZATION_ID) as conn:
        org = conn.execute(
            "SELECT display_name FROM organizations WHERE id=%s", (DEMO_ORGANIZATION_ID,)
        ).fetchone()
        if not org:
            raise SystemExit("Demo organization missing; inspect PostgreSQL initialization logs")
        print("Organization:", org["display_name"])
        for table in ("customers", "products", "orders", "suppliers", "journal_entries", "journal_lines"):
            count = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            print(f"{table}: {count}")
        totals = conn.execute(
            "SELECT COALESCE(sum(debit),0) AS debits, COALESCE(sum(credit),0) AS credits FROM journal_lines"
        ).fetchone()
        print("Trial balance totals:", totals)
        if totals["debits"] != totals["credits"]:
            raise SystemExit("Trial balance is not balanced")


if __name__ == "__main__":
    main()
