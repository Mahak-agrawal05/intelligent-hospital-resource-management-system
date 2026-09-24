import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:MahakPostgre17%40@localhost:5432/intelligent_hospital"
)