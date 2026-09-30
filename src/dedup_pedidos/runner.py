from pathlib import Path
from typing import Any

import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor


class ScriptRunner:
    def __init__(self, server_config: dict, script_path: str = "script/deduplicacao_pedidos.sql"):
        self.server_config = server_config
        self.script_path = Path(script_path)
        self._raw_sql = self._load_script()

    def _load_script(self) -> str:
        if not self.script_path.exists():
            raise FileNotFoundError(f"Arquivo SQL não encontrado: {self.script_path.resolve()}")

        sql = self.script_path.read_text(encoding="utf-8")

        # Remove comandos de transação explícitos do script
        sql_lines = []
        for line in sql.splitlines():
            stripped = line.strip().upper()
            if stripped in ("BEGIN;", "COMMIT;", "ROLLBACK;"):
                continue
            sql_lines.append(line)

        return "\n".join(sql_lines)

    def list_target_databases(self, default_db: str = "postgres") -> list[str]:
        """Listagem de bases de dados acessíveis no servidor."""
        try:
            conn = psycopg2.connect(**self.server_config, dbname=default_db)
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT datname FROM pg_database
                    WHERE datistemplate = false AND datname NOT IN ('postgres', 'pg_toast');
                """)
                dbs = [row[0] for row in cursor.fetchall()]
            conn.close()
            return dbs
        except Exception:
            return []

    def check_has_duplicates(self, conn) -> bool:
        """Verificação prévia e rápida se a base possui pedidos duplicados por (numero_pedido, filial)."""
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 1
                FROM public.pedido
                WHERE numero_pedido IS NOT NULL AND filial IS NOT NULL
                GROUP BY numero_pedido, filial
                HAVING COUNT(*) > 1
                LIMIT 1;
            """)
            return cursor.fetchone() is not None

    def execute_db_script(self, db_name: str, is_simulation: bool) -> dict[str, Any]:
        """Executa a checagem rápida e, se houver duplicatas, executa a rotina SQL em uma base específica."""
        result = {
            "database": db_name,
            "success": False,
            "skipped": False,
            "error": None,
            "diff_rows": [],
            "has_diff_alert": False
        }

        try:
            conn = psycopg2.connect(**self.server_config, dbname=db_name)
        except Exception as e:
            result["skipped"] = True
            result["error"] = f"Falha na conexão: {e!s}"
            return result

        try:
            # 1. Checagem prévia de existência da tabela e duplicatas
            if not self.check_has_duplicates(conn):
                result["skipped"] = True
                result["error"] = "Nenhuma duplicidade encontrada (numero_pedido, filial)."
                return result

            # 2. Execução da rotina completa apenas se houver duplicatas
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                conn.autocommit = False  # Inicia bloco transacional nativo

                # Executa o script SQL de deduplicação
                cursor.execute(self._raw_sql)

                # Coleta os dados do relatório DIFF
                cursor.execute("SELECT * FROM relatorio_diff_tmp ORDER BY numero_pedido, item;")
                rows = cursor.fetchall()

                formatted_rows = []
                for row in rows:
                    r_dict = dict(row)
                    if r_dict.get("diff_registros", 0) != 0 or r_dict.get("diff_quantidade", 0) != 0:
                        result["has_diff_alert"] = True
                    formatted_rows.append(r_dict)

                result["diff_rows"] = formatted_rows
                result["success"] = True

                if is_simulation:
                    conn.rollback()
                else:
                    conn.commit()

        except (errors.UndefinedTable, errors.UndefinedObject):
            conn.rollback() if not conn.closed and not conn.autocommit else None
            result["skipped"] = True
            result["error"] = "Tabelas necessárias (ex: public.pedido) não existem nesta base."
        except Exception as e:
            conn.rollback() if not conn.closed and not conn.autocommit else None
            result["skipped"] = False
            result["error"] = str(e)
        finally:
            if not conn.closed:
                conn.close()

        return result
