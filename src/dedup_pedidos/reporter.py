import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import DuplicateGroup

console = Console()

class ReportGenerator:

    @staticmethod
    def resolve_output_path(destination_path: str, default_filename: str) -> Path:
        """Trata e valida caminhos de arquivos para Windows, Mac e Linux."""
        target = Path(destination_path).expanduser().resolve()

        # Se for um diretório existente, anexa o nome de arquivo padrão
        if target.is_dir():
            return target / default_filename

        # Se o diretório pai não existir, cria automaticamente
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    @classmethod
    def render_execution_summary(cls, execution_logs: list[dict[str, Any]], skipped_groups: list[DuplicateGroup]):
        console.print("\n[bold green]=== RELATÓRIO DE EXECUÇÃO E ALTERAÇÕES ===[/bold green]\n")

        # 1. Tabela de Alterações Executadas / Simuladas
        if execution_logs:
            for log in execution_logs:
                title = f"Base: {log['database']} | Pedido: {log['numero_pedido']} | Filial: {log['filial']} (ID Mantido: {log['canonical_id']})"
                console.print(Panel(f"[bold]{title}[/bold]\nStatus: {log['status']}"))

                table = Table(title="Comparativo de Itens (Mantidos vs Excluídos)", show_lines=True)
                table.add_column("Status Item", style="cyan")
                table.add_column("ID Item", style="bold")
                table.add_column("ID Pedido Original")
                table.add_column("Qtd")
                table.add_column("Preço Unit.")
                table.add_column("Preço Total")
                table.add_column("Qtd Entrada")

                for item in log["kept_items"]:
                    table.add_row(
                        "[green]MANTIDO[/green]",
                        str(item["id"]),
                        str(item["pedido_id"]),
                        f"{item['quantidade']:.2f}",
                        f"R$ {item['preco_unitario']:.2f}",
                        f"R$ {item['preco_total']:.2f}",
                        str(item['quantidade_entrada']) if item['quantidade_entrada'] is not None else "-"
                    )

                for item in log["deleted_items"]:
                    table.add_row(
                        "[red]EXCLUÍDO[/red]",
                        str(item["id"]),
                        str(item["pedido_id"]),
                        f"{item['quantidade']:.2f}",
                        f"R$ {item['preco_unitario']:.2f}",
                        f"R$ {item['preco_total']:.2f}",
                        str(item['quantidade_entrada']) if item['quantidade_entrada'] is not None else "-"
                    )

                console.print(table)
                console.print("\n")

        # 2. Agrupamento Final de Itens Pulados
        if skipped_groups:
            console.print(Panel("[bold yellow]REGISTROS PULADOS / PENDENTES DE AÇÃO MANUAL[/bold yellow]"))
            skip_table = Table(show_header=True, header_style="bold yellow", show_lines=True)
            skip_table.add_column("Base de Dados")
            skip_table.add_column("Nº Pedido")
            skip_table.add_column("Filial")
            skip_table.add_column("Qtd Pedidos Envolvidos")
            skip_table.add_column("Motivo do Pulo")

            for group in skipped_groups:
                skip_table.add_row(
                    group.db_name,
                    group.numero_pedido,
                    group.filial,
                    str(len(group.pedidos)),
                    group.reason or "Ação manual ignorada pelo usuário"
                )
            console.print(skip_table)

    @classmethod
    def export_json_report(cls, execution_logs: list[dict[str, Any]], skipped_groups: list[DuplicateGroup], output_path: str):
        path = cls.resolve_output_path(output_path, "relatorio_execucao.json")

        skipped_data = [
            {
                "database": g.db_name,
                "numero_pedido": g.numero_pedido,
                "filial": g.filial,
                "reason": g.reason,
                "involved_ids": [p.id for p in g.pedidos]
            }
            for g in skipped_groups
        ]

        payload = {
            "generated_at": str(Path().cwd()),
            "executed_operations": execution_logs,
            "skipped_operations": skipped_data
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        console.print(f"[bold green]Relatório salvo com sucesso em:[/bold green] {path}")
