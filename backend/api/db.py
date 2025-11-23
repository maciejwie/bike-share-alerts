import os
import psycopg2


def get_db_connection():
    """
    Establishes a connection to the database.
    This is a synchronous connection, suitable for use in FastAPI dependency with threadpool.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not set")

    conn = psycopg2.connect(db_url)
    return conn


def get_db():
    """
    FastAPI dependency that yields a database connection.
    Closes the connection after the request is finished.
    """
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()
