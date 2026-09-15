import atexit
import logging
from contextlib import contextmanager
from typing import Generator, Optional
import psycopg
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from src.config import settings

logger = logging.getLogger("mtg_assistant.database")


def configure_connection(conn: psycopg.Connection) -> None:
    """
    Configures each connection acquired from the pool with pgvector type support.
    Gracefully ignores if vector extension is not yet installed in database.
    """
    try:
        register_vector(conn)
    except Exception as exc:
        logger.debug("pgvector extension not yet available on connection: %s", exc)


class Database:
    """
    Centralized PostgreSQL connection pool manager with pgvector support.
    Provides thread-safe synchronous connection pooling via psycopg_pool.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        min_size: int = 1,
        max_size: int = 10,
        timeout: float = 3.0,
    ):
        self.database_url = database_url or settings.database_url
        self.min_size = min_size
        self.max_size = max_size
        self.timeout = timeout
        self._pool: Optional[ConnectionPool] = None

    def _get_pool(self) -> ConnectionPool:
        if self._pool is None:
            if not self.database_url:
                raise ValueError("DATABASE_URL is not configured.")
            self._pool = ConnectionPool(
                conninfo=self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
                timeout=self.timeout,
                configure=configure_connection,
                open=True,
                kwargs={"connect_timeout": int(self.timeout)},
            )
        return self._pool

    @contextmanager
    def connection(self) -> Generator[psycopg.Connection, None, None]:
        """
        Yields an active database connection from the pool with pgvector registered.
        Automatically returns the connection to the pool upon context exit.
        """
        pool = self._get_pool()
        with pool.connection() as conn:
            yield conn

    def is_reachable(self) -> bool:
        """
        Checks basic PostgreSQL connectivity without requiring pgvector extension.
        Essential for initial bootstrapping and apply_schema execution on fresh databases.
        """
        if not self.database_url:
            return False
        try:
            with psycopg.connect(self.database_url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            return True
        except Exception as exc:
            logger.debug("Database reachability check failed: %s", exc)
            return False

    def is_vector_ready(self) -> bool:
        """
        Checks if PostgreSQL is reachable AND pgvector extension is registered and usable.
        """
        if not self.database_url:
            return False
        try:
            with psycopg.connect(self.database_url, connect_timeout=2) as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            return True
        except Exception as exc:
            logger.debug("Database vector check failed: %s", exc)
            return False

    def is_available(self) -> bool:
        """
        Fast healthcheck returning True if PostgreSQL is reachable and pgvector is registered.
        Maintains backwards compatibility for vector-dependent services.
        """
        return self.is_vector_ready()

    def close(self) -> None:
        """Closes the connection pool and releases all resources."""
        if self._pool is not None:
            try:
                self._pool.close()
            except Exception as exc:
                logger.warning("Error closing database pool: %s", exc)
            finally:
                self._pool = None


# Default global instance
database = Database()
atexit.register(database.close)
