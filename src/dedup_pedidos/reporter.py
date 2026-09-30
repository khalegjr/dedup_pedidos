import csv
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


class ReportGenerator:

    @staticmethod
    def resolve_output_path(destination_path: str, format_extension: str) -> Path:
        target = Path(destination_path).expanduser().resolve()
        if target.is_dir():
            target = target / f"relatorio_diff_dedup.{format_extension}"
        else:
            if target.suffix.lower() != f".{format_extension}":
                target = target.with_suffix(f".{format_extension}")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    @classmethod
    def render_console_summary(cls, execution_results: list[dict[str, Any]]):
        console.print("\n[bold green]=== RESUMO GERAL DAS BASES PROCESSADAS ===[/bold green]\n")

        # Alerta inicial rápido sobre divergências encontradas
        alert_dbs = [r["database"] for r in execution_results if r.get("has_diff_alert")]
        if alert_dbs:
            console.print(Panel(
                "[bold white on red] ATENÇÃO: As seguintes bases possuem divergências no resumo (diff != 0): [/bold white on red]\n"
                + ", ".join(alert_dbs),
                title="[bold yellow]Divergências Detectadas[/bold yellow]"
            ))
        else:
            console.print("[bold green]✔ Nenhuma divergência de registros ou quantidades foi encontrada nas bases elegíveis.[/bold green]\n")

        for res in execution_results:
            db_name = res["database"]

            if res.get("skipped"):
                console.print(f"[yellow]⚪ Base {db_name}: Ignorada/Ignorável ({res['error']})[/yellow]")
                continue

            if not res["success"]:
                console.print(f"[bold red]❌ Base {db_name}: Efetivado ROLLBACK devido a erro![/bold red]")
                console.print(f"   [red]Motivo: {res['error']}[/red]\n")
                continue

            # Base executada com sucesso
            has_alert = res.get("has_diff_alert", False)
            status_tag = "[bold white on red] COM DIVERGÊNCIAS [/bold white on red]" if has_alert else "[bold green] SEM DIVERGÊNCIAS [/bold green]"

            table = Table(
                title=f"Base: {db_name} {status_tag}",
                show_lines=True,
                header_style="bold magenta"
            )
            table.add_column("Nº Pedido")
            table.add_column("Item")
            table.add_column("Reg. Antes", justify="right")
            table.add_column("Reg. Depois", justify="right")
            table.add_column("Diff Reg.", justify="right")
            table.add_column("Qtd Antes", justify="right")
            table.add_column("Qtd Depois", justify="right")
            table.add_column("Diff Qtd", justify="right")

            for r in res["diff_rows"]:
                diff_reg = r["diff_registros"]
                diff_qtd = r["diff_quantidade"]
                is_divergent = (diff_reg != 0 or diff_qtd != 0)

                # Estilo com fundo vermelho e texto branco para divergências
                row_style = "bold white on red" if is_divergent else None

                table.add_row(
                    str(r["numero_pedido"]),
                    str(r["item"]),
                    str(r["registros_antes"]),
                    str(r["registros_depois"]),
                    str(diff_reg),
                    f"{r['qtd_antes']:.2f}",
                    f"{r['qtd_depois']:.2f}",
                    f"{diff_qtd:.2f}",
                    style=row_style
                )

            console.print(table)
            console.print("\n")

    @classmethod
    def export_csv(cls, execution_results: list[dict[str, Any]], output_path: str):
        path = cls.resolve_output_path(output_path, "csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "DATABASE", "NUMERO_PEDIDO", "ITEM",
                "REGISTROS_ANTES", "REGISTROS_DEPOIS", "DIFF_REGISTROS",
                "QTD_ANTES", "QTD_DEPOIS", "DIFF_QUANTIDADE", "HAS_DIVERGENCE"
            ])
            for res in execution_results:
                if res.get("success"):
                    for r in res["diff_rows"]:
                        has_div = (r["diff_registros"] != 0 or r["diff_quantidade"] != 0)
                        writer.writerow([
                            res["database"], r["numero_pedido"], r["item"],
                            r["registros_antes"], r["registros_depois"], r["diff_registros"],
                            r["qtd_antes"], r["qtd_depois"], r["diff_quantidade"],
                            "SIM" if has_div else "NAO"
                        ])
        console.print(f"[bold green]Relatório CSV salvo com sucesso em:[/bold green] {path}")

    @classmethod
    def export_json(cls, execution_results: list[dict[str, Any]], output_path: str):
        path = cls.resolve_output_path(output_path, "json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(execution_results, f, indent=2, ensure_ascii=False)
        console.print(f"[bold green]Relatório JSON salvo com sucesso em:[/bold green] {path}")

    @classmethod
    def export_pdf(cls, execution_results: list[dict[str, Any]], output_path: str):
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
            console.print("[bold red]Erro: A biblioteca 'reportlab' é necessária para PDF. Execute 'uv add reportlab'.[/bold red]")
            return

        doc = SimpleDocTemplate(str(path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = [Paragraph("Relatório Resumo de Divergências de Deduplicação", styles['Title']), Spacer(1, 12)]

        for res in execution_results:
            if not res.get("success"):
                continue

            story.append(Paragraph(f"Base de Dados: {res['database']}", styles['Heading2']))
            data = [["Nº Pedido", "Item", "Reg. Antes", "Reg. Dep.", "Diff Reg.", "Qtd Antes", "Qtd Dep.", "Diff Qtd"]]

            table_styles = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 8)
            ]

            for row_idx, r in enumerate(res["diff_rows"], start=1):
                is_divergent = (r["diff_registros"] != 0 or r["diff_quantidade"] != 0)
                data.append([
                    str(r["numero_pedido"]), str(r["item"]),
                    str(r["registros_antes"]), str(r["registros_depois"]), str(r["diff_registros"]),
                    f"{r['qtd_antes']:.2f}", f"{r['qtd_depois']:.2f}", f"{r['diff_quantidade']:.2f}"
                ])
                if is_divergent:
                    table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.red))
                    table_styles.append(('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.white))

            t = RLTable(data)
            t.setStyle(TableStyle(table_styles))
            story.append(t)
            story.append(Spacer(1, 12))

        doc.build(story)
        console.print(f"[bold green]Relatório PDF salvo com sucesso em:[/bold green] {path}")
