import os

import psycopg2.pool

# Global connection pool
_pool = None


def get_db_pool():
    """
    Returns the global database connection pool.
    Initializes it if it doesn't exist.
    """
    global _pool
    if _pool is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise Exception("DATABASE_URL not set")

        # Initialize the pool
        # minconn=1, maxconn=5 (keep it small for serverless to avoid exhausting DB limits)
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 5, db_url)

    return _pool


def get_db_connection():
    """
    Gets a connection from the pool.
    """
    pool = get_db_pool()
    return pool.getconn()


def get_db():
    """
    FastAPI dependency that yields a database connection from the pool.
    Returns the connection to the pool after the request is finished.
    """
    pool = get_db_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)
