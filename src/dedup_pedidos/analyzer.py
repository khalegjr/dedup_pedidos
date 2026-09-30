import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor

from .config import DEFAULT_DB
from .models import ConflictType, DependentRecord, DuplicateGroup, PedidoDiagnostic


class DatabaseAnalyzer:
    def __init__(self, server_config: dict):
        self.server_config = server_config

    def list_target_databases(self) -> list[str]:
        """Busca todas as bases de dados do servidor ignorando bases de sistema."""
        try:
            conn = psycopg2.connect(**self.server_config, dbname=DEFAULT_DB)
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

    def diagnose_database(self, db_name: str) -> list[DuplicateGroup]:
        """Executa a análise de integridade em um banco específico.
        Caso o banco não possua a tabela 'public.pedido', ignora e pula silenciosamente.
        """
        try:
            conn = psycopg2.connect(**self.server_config, dbname=db_name)
        except Exception:
            # Falha na conexão com o banco específico
            return []

        groups: list[DuplicateGroup] = []

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT numero_pedido, filial, COUNT(*) as qtd
                    FROM public.pedido
                    WHERE numero_pedido IS NOT NULL AND filial IS NOT NULL
                    GROUP BY numero_pedido, filial
                    HAVING COUNT(*) > 1;
                """)
                dups = cursor.fetchall()

                for dup in dups:
                    num_pedido = dup['numero_pedido']
                    filial = dup['filial']

                    cursor.execute("""
                        SELECT id, numero_pedido, filial, grupo_id, data_encerramento
                        FROM public.pedido
                        WHERE numero_pedido = %s AND filial = %s
                        ORDER BY id ASC;
                    """, (num_pedido, filial))
                    pedidos_db = cursor.fetchall()

                    pedidos_diag = []
                    count_with_item_rel = 0

                    for p in pedidos_db:
                        pid = p['id']

                        cursor.execute("SELECT COUNT(*) FROM public.item_pedido WHERE pedido_id = %s;", (pid,))
                        cnt_items = cursor.fetchone()['count']

                        cursor.execute("SELECT COUNT(*) FROM public.item_relacionado WHERE pedido_id = %s;", (pid,))
                        cnt_item_rel = cursor.fetchone()['count']

                        cursor.execute("SELECT COUNT(*) FROM public.item_relacionado_servico WHERE pedido_id = %s;", (pid,))
                        cnt_item_rel_serv = cursor.fetchone()['count']

                        cursor.execute("SELECT COUNT(*) FROM public.log_associacao WHERE pedido_id = %s;", (pid,))
                        cnt_log = cursor.fetchone()['count']

                        has_rel = (cnt_item_rel > 0 or cnt_item_rel_serv > 0)
                        if has_rel:
                            count_with_item_rel += 1

                        deps = []
                        if cnt_item_rel > 0:
                            deps.append(DependentRecord("item_relacionado", pid, "pedido_id", f"{cnt_item_rel} itens"))
                        if cnt_item_rel_serv > 0:
                            deps.append(DependentRecord("item_relacionado_servico", pid, "pedido_id", f"{cnt_item_rel_serv} itens"))
                        if cnt_log > 0:
                            deps.append(DependentRecord("log_associacao", pid, "pedido_id", f"{cnt_log} registros"))

                        pedidos_diag.append(PedidoDiagnostic(
                            id=pid,
                            numero_pedido=num_pedido,
                            filial=filial,
                            item_pedido_count=cnt_items,
                            has_item_relacionado=(cnt_item_rel > 0),
                            has_item_relacionado_servico=(cnt_item_rel_serv > 0),
                            total_dependencias=len(deps),
                            dependencias=deps
                        ))

                    group = DuplicateGroup(db_name=db_name, numero_pedido=num_pedido, filial=filial, pedidos=pedidos_diag)

                    if count_with_item_rel > 1:
                        group.conflict_type = ConflictType.MANUAL_MERGE_REQUIRED
                        group.reason = "Conflito: Múltiplos pedidos possuem vínculo com item_relacionado. Exige intervenção manual."
                    else:
                        sorted_p = sorted(
                            pedidos_diag,
                            key=lambda x: (
                                x.has_item_relacionado or x.has_item_relacionado_servico,
                                x.item_pedido_count
                            ),
                            reverse=True
                        )
                        group.canonical_id = sorted_p[0].id
                        group.reason = f"Preservado ID {sorted_p[0].id} por prioridade de relacionamentos e volume de itens."

                    groups.append(group)

        except (errors.UndefinedTable, errors.UndefinedObject, psycopg2.ProgrammingError):
            # Se a tabela public.pedido (ou outra tabela esperada) não existir no banco, cancela a transação e pula
            conn.rollback()
            return []
        except Exception:
            conn.rollback()
            return []
        finally:
            conn.close()

        return groups
