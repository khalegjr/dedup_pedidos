import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DEFAULT_DB = os.getenv("DEFAULT_DB", "postgres")

MIN_CONNECTIONS = int(os.getenv("MIN_CONNECTIONS", "1"))
MAX_CONNECTIONS = int(os.getenv("MAX_CONNECTIONS", "10"))

# Configuração de acesso ao servidor (sem dbname fixo)
SERVER_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
}
