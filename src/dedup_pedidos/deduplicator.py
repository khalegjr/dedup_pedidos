from datetime import datetime
from typing import Any

import psycopg2

from .models import DuplicateGroup


class TransactionalDeduplicator:
    def __init__(self, server_config: dict):
        self.server_config = server_config

    def execute_deduplication(
        self,
        group: DuplicateGroup,
        canonical_id: str,
        dry_run: bool = True
    ) -> dict[str, Any]:
        conn = psycopg2.connect(**self.server_config, dbname=group.db_name)
        cursor = conn.cursor()

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
            "deleted_item_pedidos": 0,
            "deleted_headers": 0,
            "backup_data": {}
        }

        try:
            cursor.execute("BEGIN;")

            cursor.execute("SELECT * FROM public.pedido WHERE id IN %s;", (all_ids,))
            audit_log["backup_data"]["pedido"] = cursor.fetchall()

            cursor.execute("SELECT * FROM public.item_pedido WHERE pedido_id IN %s;", (all_ids,))
            audit_log["backup_data"]["item_pedido"] = cursor.fetchall()

            for disc_id in discarded_ids:
                cursor.execute("UPDATE public.item_relacionado SET pedido_id = %s WHERE pedido_id = %s;", (canonical_id, disc_id))
                if cursor.rowcount > 0:
                    audit_log["transferred_records"].append(f"item_relacionado: {cursor.rowcount} linhas de {disc_id} -> {canonical_id}")

                cursor.execute("UPDATE public.item_relacionado_servico SET pedido_id = %s WHERE pedido_id = %s;", (canonical_id, disc_id))
                if cursor.rowcount > 0:
                    audit_log["transferred_records"].append(f"item_relacionado_servico: {cursor.rowcount} linhas de {disc_id} -> {canonical_id}")

                cursor.execute("UPDATE public.log_associacao SET pedido_id = %s WHERE pedido_id = %s;", (canonical_id, disc_id))
                if cursor.rowcount > 0:
                    audit_log["transferred_records"].append(f"log_associacao: {cursor.rowcount} linhas de {disc_id} -> {canonical_id}")

            cursor.execute("DELETE FROM public.item_pedido WHERE pedido_id IN %s;", (tuple(discarded_ids),))
            audit_log["deleted_item_pedidos"] = cursor.rowcount

            cursor.execute("DELETE FROM public.pedido WHERE id IN %s;", (tuple(discarded_ids),))
            audit_log["deleted_headers"] = cursor.rowcount

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
