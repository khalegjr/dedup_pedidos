from collections.abc import Generator
from contextlib import contextmanager

import psycopg2
from config import DB_CONFIG, MAX_CONNECTIONS, MIN_CONNECTIONS
from psycopg2 import pool


class DatabaseManager:
    """
    Gerenciador de pool de conexões por banco de dados.
    Lida apenas com consultas e transações DML (SELECT, UPDATE, DELETE).
    """
    _pools = {}

    @classmethod
    def get_pool(cls, db_name: str) -> pool.SimpleConnectionPool:
        """Cria ou recupera um pool de conexões reutilizável para a base especificada."""
        if db_name not in cls._pools:
            config = {**DB_CONFIG, "dbname": db_name}
            cls._pools[db_name] = pool.SimpleConnectionPool(
                minconn=MIN_CONNECTIONS,
                maxconn=MAX_CONNECTIONS,
                **config
            )
        return cls._pools[db_name]

    @classmethod
    @contextmanager
    def get_connection(cls, db_name: str = DB_CONFIG["dbname"]) -> Generator[psycopg2.extensions.connection, None, None]:
        """
        Gerenciador de contexto que fornece uma conexão do pool e a devolve automaticamente.
        """
        pool_obj = cls.get_pool(db_name)
        conn = pool_obj.getconn()
        try:
            yield conn
        finally:
            pool_obj.putconn(conn)

    @classmethod
    def close_all_pools(cls):
        """Encerra todos os pools de conexão ao finalizar a aplicação."""
        for db_name, pool_obj in cls._pools.items():
            if not pool_obj.closed:
                pool_obj.closeall()
        cls._pools.clear()
