import os
from urllib.parse import urlparse

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        parsed = urlparse(database_url)
        return psycopg.connect(
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432,
            connect_timeout=5,
        )

    return psycopg.connect(
        dbname=os.getenv("POSTGRES_DB", "chnu_jobs"),
        user=os.getenv("POSTGRES_USER", "chnu_jobs"),
        password=os.getenv("POSTGRES_PASSWORD", "chnu_jobs_password"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        connect_timeout=5,
    )
