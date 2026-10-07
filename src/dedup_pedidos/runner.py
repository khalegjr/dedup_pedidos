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

        # Remove comandos manuais de transação do arquivo .sql,
        # pois a biblioteca psycopg2 vai gerenciar BEGIN/COMMIT/ROLLBACK.
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
        """Verificação prévia e rápida se a base possui pedidos duplicados por (numero_pedido, filial e grupo_id)."""
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 1
                FROM public.pedido
                WHERE numero_pedido IS NOT NULL
                  AND filial IS NOT NULL
                  AND grupo_id IS NOT NULL
                GROUP BY numero_pedido, filial, grupo_id
                HAVING COUNT(*) > 1
                LIMIT 1;
            """)
            return cursor.fetchone() is not None

    def execute_db_script(self, db_name: str, is_simulation: bool) -> dict[str, Any]:
        """Executa a checagem rápida e roda o script SQL garantindo o COMMIT/ROLLBACK correto."""
        result = {
            "database": db_name,
            "success": False,
            "skipped": False,
            "error": None,
            "diff_rows": [],
            "has_diff_alert": False,
            "divergent_count": 0
        }

        try:
            conn = psycopg2.connect(**self.server_config, dbname=db_name)
        except Exception as e:
            result["skipped"] = True
            result["error"] = f"Falha na conexão: {e!s}"
            return result

        try:
            # 1. Checagem se a tabela existe e possui duplicatas por (numero_pedido, filial, grupo_id)
            if not self.check_has_duplicates(conn):
                conn.close()
                result["skipped"] = True
                result["error"] = "Nenhuma duplicidade encontrada (numero_pedido, filial, grupo_id)."
                return result

            # 2. Execução do script SQL na mesma transação
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(self._raw_sql)

                # Coleta os dados do relatório DIFF gerados na tabela temporária
                cursor.execute("""
                    SELECT * FROM relatorio_diff_tmp
                    ORDER BY filial, numero_pedido, grupo_id, item;
                """)
                rows = cursor.fetchall()

                formatted_rows = []
                divergent_count = 0

                for row in rows:
                    r_dict = dict(row)
                    if r_dict.get("diff_registros", 0) != 0 or r_dict.get("diff_quantidade", 0) != 0:
                        divergent_count += 1
                        result["has_diff_alert"] = True
                    formatted_rows.append(r_dict)

                result["diff_rows"] = formatted_rows
                result["divergent_count"] = divergent_count

            # 3. Finalização explícita da transação no banco de dados
            if is_simulation:
                conn.rollback()
                result["success"] = True
            else:
                conn.commit()  # Garante a efetivação física das alterações no PostgreSQL!
                result["success"] = True

        except (errors.UndefinedTable, errors.UndefinedColumn, errors.UndefinedObject) as e:
            if not conn.closed:
                conn.rollback()
            result["skipped"] = True
            result["error"] = f"Tabela ou coluna necessária ausente nesta base: {e.pgerror or e}"
        except Exception as e:
            if not conn.closed:
                conn.rollback()
            result["skipped"] = False
            result["error"] = f"Erro de execução SQL (Rollback efetuado): {e!s}"
        finally:
            if not conn.closed:
                conn.close()

        return result
