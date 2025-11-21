import psycopg2
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

def get_connection():
    """
    Підключення до БД.
    - Якщо є DATABASE_URL (наприклад, на Render) – використовуємо його.
    - Інакше – збираємо з POSTGRES_* змінних (локальний Docker).
    """
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Очікується URL типу: postgres://user:pass@host:port/dbname
        url = urlparse(database_url)
        return psycopg2.connect(
            dbname=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
    else:
        # Локальний варіант (Docker Compose)
        return psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", 5432)
        )
