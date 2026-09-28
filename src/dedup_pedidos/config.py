import os

# Configurações do servidor PostgreSQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_MAINTENANCE_DB = os.getenv("DB_MAINTENANCE_DB", "postgres")

# Pool de Conexões
MIN_CONNECTIONS = int(os.getenv("MIN_CONNECTIONS", "1"))
MAX_CONNECTIONS = int(os.getenv("MAX_CONNECTIONS", "10"))

# Dicionário base de configuração para uso no psycopg2 / asyncpg
DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "dbname": DB_MAINTENANCE_DB
}
