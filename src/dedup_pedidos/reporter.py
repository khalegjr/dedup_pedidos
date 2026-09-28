import csv
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
    def resolve_output_path(destination_path: str, format_extension: str) -> Path:
        """Resolve o caminho no OS, cria diretórios e garante a extensão correta."""
        target = Path(destination_path).expanduser().resolve()

        # Se for um diretório existente, insere nome de arquivo padrão
        if target.is_dir():
            target = target / f"relatorio_alteracoes.{format_extension}"
        else:
            # Força/corrige a extensão do arquivo conforme o formato escolhido
            if target.suffix.lower() != f".{format_extension}":
                target = target.with_suffix(f".{format_extension}")

        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    @classmethod
    def render_execution_summary(cls, execution_logs: list[dict[str, Any]], skipped_groups: list[DuplicateGroup]):
        console.print("\n[bold green]=== RELATÓRIO DE EXECUÇÃO E ALTERAÇÕES ===[/bold green]\n")

        if execution_logs:
            for log in execution_logs:
                title = f"Base: {log['database']} | Pedido: {log['numero_pedido']} | Filial: {log['filial']} (ID Mantido: {log['canonical_id']})"
                console.print(Panel(f"[bold]{title}[/bold]\nStatus: {log['status']}"))

                table = Table(title="Comparativo de Itens (Mantidos vs Excluídos)", show_lines=True)
                table.add_column("Status Item", style="cyan")
                table.add_column("ID Item", style="bold")
                table.add_column("ID Pedido Original")
                table.add_column("Item", style="magenta")
                table.add_column("Qtd")
                table.add_column("Preço Unit.")
                table.add_column("Preço Total")
                table.add_column("Qtd Entrada")

                for item in log["kept_items"]:
                    table.add_row(
                        "[green]MANTIDO[/green]",
                        str(item["id"]),
                        str(item["pedido_id"]),
                        item["item"],
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
                        item["item"],
                        f"{item['quantidade']:.2f}",
                        f"R$ {item['preco_unitario']:.2f}",
                        f"R$ {item['preco_total']:.2f}",
                        str(item['quantidade_entrada']) if item['quantidade_entrada'] is not None else "-"
                    )

                console.print(table)
                console.print("\n")

        if skipped_groups:
            console.print(Panel("[bold yellow]REGISTROS PULADOS / PENDENTES DE AÇÃO MANUAL[/bold yellow]"))
            skip_table = Table(show_header=True, header_style="bold yellow", show_lines=True)
            skip_table.add_column("Base de Dados")
            skip_table.add_column("Nº Pedido")
            skip_table.add_column("Filial")
            skip_table.add_column("Qtd Pedidos Envolvidos")
            skip_table.add_column("Motivo")

            for group in skipped_groups:
                skip_table.add_row(
                    group.db_name,
                    group.numero_pedido,
                    group.filial,
                    str(len(group.pedidos)),
                    group.reason or "Ação manual ignorada pelo operador"
                )
            console.print(skip_table)

    @classmethod
    def export_csv(cls, execution_logs: list[dict[str, Any]], skipped_groups: list[DuplicateGroup], output_path: str):
        path = cls.resolve_output_path(output_path, "csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["TIPO_REGISTRO", "DATABASE", "NUMERO_PEDIDO", "FILIAL", "STATUS_ITEM", "ITEM_ID", "PEDIDO_ID_ORIGEM", "ITEM", "QUANTIDADE", "PRECO_UNITARIO", "PRECO_TOTAL", "QUANTIDADE_ENTRADA", "MOTIVO"])

            for log in execution_logs:
                for item in log["kept_items"]:
                    writer.writerow(["EXECUCAO", log["database"], log["numero_pedido"], log["filial"], "MANTIDO", item["id"], item["pedido_id"], item["item"], item["quantidade"], item["preco_unitario"], item["preco_total"], item["quantidade_entrada"], ""])
                for item in log["deleted_items"]:
                    writer.writerow(["EXECUCAO", log["database"], log["numero_pedido"], log["filial"], "EXCLUIDO", item["id"], item["pedido_id"], item["item"], item["quantidade"], item["preco_unitario"], item["preco_total"], item["quantidade_entrada"], ""])

            for g in skipped_groups:
                writer.writerow(["PULADO", g.db_name, g.numero_pedido, g.filial, "-", "-", "-", "-", "-", "-", "-", "-", g.reason])

        console.print(f"[bold green]Relatório CSV salvo em:[/bold green] {path}")

    @classmethod
    def export_json(cls, execution_logs: list[dict[str, Any]], skipped_groups: list[DuplicateGroup], output_path: str):
        path = cls.resolve_output_path(output_path, "json")
        payload = {
            "executed_operations": execution_logs,
            "skipped_operations": [
                {
                    "database": g.db_name,
                    "numero_pedido": g.numero_pedido,
                    "filial": g.filial,
                    "reason": g.reason
                } for g in skipped_groups
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        console.print(f"[bold green]Relatório JSON salvo em:[/bold green] {path}")

    @classmethod
    def export_pdf(cls, execution_logs: list[dict[str, Any]], skipped_groups: list[DuplicateGroup], output_path: str):
        path = cls.resolve_output_path(output_path, "pdf")
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                TableStyle,
            )
            from reportlab.platypus import Table as RLTable
        except ImportError:
            console.print("[bold red]Erro: A biblioteca 'reportlab' é necessária para gerar PDFs. Execute 'uv add reportlab'.[/bold red]")
            return

        doc = SimpleDocTemplate(str(path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = [Paragraph("Relatório de Exclusão e Comparativo de Itens", styles['Title']), Spacer(1, 12)]

        for log in execution_logs:
            story.append(Paragraph(f"Base: {log['database']} | Pedido: {log['numero_pedido']} | Filial: {log['filial']}", styles['Heading2']))
            data = [["Status", "ID Item", "ID Pedido", "Item", "Qtd", "Preço Unit.", "Preço Total", "Qtd Ent."]]

            for item in log["kept_items"]:
                data.append(["MANTIDO", str(item["id"]), str(item["pedido_id"]), item["item"], f"{item['quantidade']:.2f}", f"R$ {item['preco_unitario']:.2f}", f"R$ {item['preco_total']:.2f}", str(item['quantidade_entrada'] or "-")])
            for item in log["deleted_items"]:
                data.append(["EXCLUIDO", str(item["id"]), str(item["pedido_id"]), item["item"], f"{item['quantidade']:.2f}", f"R$ {item['preco_unitario']:.2f}", f"R$ {item['preco_total']:.2f}", str(item['quantidade_entrada'] or "-")])

            t = RLTable(data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 8)
            ]))
            story.append(t)
            story.append(Spacer(1, 12))

        doc.build(story)
        console.print(f"[bold green]Relatório PDF salvo em:[/bold green] {path}")
