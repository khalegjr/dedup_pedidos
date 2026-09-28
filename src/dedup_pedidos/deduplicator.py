from datetime import datetime
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from .models import DuplicateGroup


class TransactionalDeduplicator:
    def __init__(self, server_config: dict):
        self.server_config = server_config

    def execute_deduplication(
        self,
        group: DuplicateGroup,
        canonical_id: int,
        dry_run: bool = True
    ) -> dict[str, Any]:
        conn = psycopg2.connect(**self.server_config, dbname=group.db_name)

        discarded_ids = [p.id for p in group.pedidos if p.id != canonical_id]
        all_ids = tuple([p.id for p in group.pedidos])

        audit_log = {
            "timestamp": datetime.now().isoformat(),
            "database": group.db_name,
            "numero_pedido": group.numero_pedido,
            "filial": group.filial,
            "canonical_id": canonical_id,
            "discarded_ids": discarded_ids,
            "dry_run": dry_run,
            "transferred_records": [],
            "deleted_headers_count": len(discarded_ids),
            "kept_items": [],
            "deleted_items": [],
            "status": "PENDING"
        }

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                conn.autocommit = False

                # Busca detalhada incluindo a coluna 'item'
                cursor.execute("""
                    SELECT id, pedido_id, item, quantidade, preco_unitario, preco_total, quantidade_entrada
                    FROM public.item_pedido
                    WHERE pedido_id IN %s;
                """, (all_ids,))
                raw_items = cursor.fetchall()

                for item in raw_items:
                    item_dict = {
                        "id": item["id"],
                        "pedido_id": item["pedido_id"],
                        "item": str(item["item"] or ""),
                        "quantidade": float(item["quantidade"] or 0),
                        "preco_unitario": float(item["preco_unitario"] or 0),
                        "preco_total": float(item["preco_total"] or 0),
                        "quantidade_entrada": float(item["quantidade_entrada"]) if item["quantidade_entrada"] is not None else None
                    }
                    if item["pedido_id"] == canonical_id:
                        audit_log["kept_items"].append(item_dict)
                    else:
                        audit_log["deleted_items"].append(item_dict)

                # Reorientação de FKs em tabelas dependentes
                for disc_id in discarded_ids:
                    for table in ["item_relacionado", "item_relacionado_servico", "log_associacao"]:
                        cursor.execute(f"UPDATE public.{table} SET pedido_id = %s WHERE pedido_id = %s;", (canonical_id, disc_id))
                        if cursor.rowcount > 0:
                            audit_log["transferred_records"].append(f"{table}: {cursor.rowcount} linhas (ID {disc_id} -> {canonical_id})")

                # Exclusão transacional
                cursor.execute("DELETE FROM public.item_pedido WHERE pedido_id IN %s;", (tuple(discarded_ids),))
                cursor.execute("DELETE FROM public.pedido WHERE id IN %s;", (tuple(discarded_ids),))

                # Atualiza quantidade no registro mantido
                cursor.execute("""
                    UPDATE public.pedido
                    SET quantidade_itens = (SELECT COUNT(*) FROM public.item_pedido WHERE pedido_id = %s)
                    WHERE id = %s;
                """, (canonical_id, canonical_id))

                if dry_run:
                    conn.rollback()
                    audit_log["status"] = "SIMULATION_SUCCESS"
                else:
                    conn.commit()
                    audit_log["status"] = "EXECUTION_SUCCESS"

        except Exception as e:
            conn.rollback()
            audit_log["status"] = "FAILED"
            audit_log["error"] = str(e)
            raise e
        finally:
            conn.close()

        return audit_log
