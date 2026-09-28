from collections.abc import Generator
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool

from .config import DEFAULT_DB, MAX_CONNECTIONS, MIN_CONNECTIONS, SERVER_CONFIG


class DatabaseManager:
    _pools = {}

    @classmethod
    def get_pool(cls, db_name: str) -> pool.SimpleConnectionPool:
        if db_name not in cls._pools:
            cls._pools[db_name] = pool.SimpleConnectionPool(
                minconn=MIN_CONNECTIONS,
                maxconn=MAX_CONNECTIONS,
                dbname=db_name,
                **SERVER_CONFIG
            )
        return cls._pools[db_name]

    @classmethod
    @contextmanager
    def get_connection(cls, db_name: str = DEFAULT_DB) -> Generator[psycopg2.extensions.connection, None, None]:
        pool_obj = cls.get_pool(db_name)
        conn = pool_obj.getconn()
        try:
            yield conn
        finally:
            pool_obj.putconn(conn)

    @classmethod
    def close_all_pools(cls):
        for db_name, pool_obj in cls._pools.items():
            if not pool_obj.closed:
                pool_obj.closeall()
        cls._pools.clear()
