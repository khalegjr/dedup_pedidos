import csv

from models import DuplicateGroup
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, TableStyle
from reportlab.platypus import Table as PDFTable
from rich.console import Console
from rich.table import Table

console = Console()

class ReportGenerator:

    @staticmethod
    def render_terminal(groups: list[DuplicateGroup]):
        """Exibe resumo visual no Terminal via Rich."""
        table = Table(title="Diagnóstico de Pedidos Duplicados por Base")
        table.add_column("Banco de Dados", style="cyan")
        table.add_column("Nº Pedido", style="magenta")
        table.add_column("Filial", style="green")
        table.add_column("Qtd Duplicados", style="yellow")
        table.add_column("Status Resolução", style="bold white")

        for g in groups:
            status = "[bold green]Auto-Sugerido[/bold green]" if g.canonical_id else "[bold red]Requer Mesclagem Manual[/bold red]"
            table.add_row(g.db_name, g.numero_pedido, g.filial, str(len(g.pedidos)), status)

        console.print(table)

    @staticmethod
    def export_csv(groups: list[DuplicateGroup], filepath: str):
        """Exporta o diagnóstico consolidated em CSV."""
        with open(filepath, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(['nome_banco', 'numero_pedido', 'filial', 'pedido_id', 'item_pedido_count', 'has_item_relacionado', 'sugestao_status'])
            for g in groups:
                for p in g.pedidos:
                    is_canonical = (p.id == g.canonical_id)
                    writer.writerow([
                        g.db_name, p.numero_pedido, p.filial, p.id,
                        p.item_pedido_count, p.has_item_relacionado,
                        "PRESERVAR" if is_canonical else "EXCLUIR/ANALISAR"
                    ])

    @staticmethod
    def export_pdf(groups: list[DuplicateGroup], filepath: str):
        """Gera relatório gerencial em PDF."""
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("<b>Relatório de Diagnóstico de Duplicidades de Pedidos</b>", styles['Title']))
        elements.append(Spacer(1, 12))

        data = [["Banco", "Pedido", "Filial", "ID", "Itens", "Relacionado?", "Ação Sugerida"]]
        for g in groups:
            for p in g.pedidos:
                action = "PRESERVAR" if p.id == g.canonical_id else "EXCLUIR"
                if not g.canonical_id:
                    action = "MANUAL"
                data.append([g.db_name, p.numero_pedido, p.filial, p.id[:8] + "...", str(p.item_pedido_count), str(p.has_item_relacionado), action])

        t = PDFTable(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(t)
        doc.build(elements)
