import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict
from models import DuplicateGroup, PedidoDiagnostic, DependentRecord, ConflictType

class DatabaseAnalyzer:
    def __init__(self, db_config: dict):
        self.db_config = db_config

    def list_target_databases((self) -> List[str]:
        """Busca todas as bases de dados do servidor ignorando bases de sistema."""
        conn = psycopg2.connect(**self.db_config, dbname="postgres")
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT datname FROM pg_database
                WHERE datistemplate = false AND datname NOT IN ('postgres', 'pg_toast');
            """)
            dbs = [row[0] for row in cursor.fetchall()]
        conn.close()
        return dbs

    def diagnose_database(self, db_name: str) -> List[DuplicateGroup]:
        """Executa a análise de integridade em um banco específico."""
        config = {**self.db_config, "dbname": db_name}
        try:
            conn = psycopg2.connect(**config)
        except Exception:
            return []

        groups: List[DuplicateGroup] = []

        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # 1. Localiza chaves de negócio duplicadas
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

                # Fetch todos os pedidos duplicados do grupo
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

                    # Contagem de item_pedido
                    cursor.execute("SELECT COUNT(*) FROM public.item_pedido WHERE pedido_id = %s;", (pid,))
                    cnt_items = cursor.fetchone()['count']

                    # Checa vínculo com item_relacionado
                    cursor.execute("SELECT COUNT(*) FROM public.item_relacionado WHERE pedido_id = %s;", (pid,))
                    cnt_item_rel = cursor.fetchone()['count']

                    # Checa vínculo com item_relacionado_servico
                    cursor.execute("SELECT COUNT(*) FROM public.item_relacionado_servico WHERE pedido_id = %s;", (pid,))
                    cnt_item_rel_serv = cursor.fetchone()['count']

                    # Mapeia outras dependências (ex: log_associacao)
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

                # Lógica de seleção do Canônico e classificação de conflito
                group = DuplicateGroup(db_name=db_name, numero_pedido=num_pedido, filial=filial, pedidos=pedidos_diag)

                if count_with_item_rel > 1:
                    group.conflict_type = ConflictType.MANUAL_MERGE_REQUIRED
                    group.reason = "Conflito: Múltiplos pedidos possuem vínculo com item_relacionado. Exige intervenção manual."
                else:
                    # Ordenação determinística pelas regras do requisito
                    # 1. Possui item_relacionado (True > False)
                    # 2. Quantidade de item_pedido (Descendente)
                    # 3. ID (Ordem de inserção/fallback)
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

        conn.close()
        return groups
