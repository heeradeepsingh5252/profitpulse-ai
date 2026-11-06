import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://profitpulse_app:local_app_password_change_me@localhost:5432/profitpulse",
)
DEMO_ORGANIZATION_ID = os.getenv(
    "DEMO_ORGANIZATION_ID", "11111111-1111-4111-8111-111111111111"
)
MAX_CSV_BYTES = int(os.getenv("MAX_CSV_BYTES", str(5 * 1024 * 1024)))
