import csv
from pathlib import Path
from typing import Any

from rich.console import Console
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

        # 1. ÍNDICE GERAL DE BASES
        index_table = Table(
            title="📋 ÍNDICE GERAL DE BASES DE DADOS",
            show_lines=True,
            header_style="bold cyan"
        )
        index_table.add_column("Índice", justify="center", style="bold")
        index_table.add_column("Base de Dados", style="bold")
        index_table.add_column("Status / Resultado", justify="left")

        for idx, res in enumerate(execution_results, start=1):
            db_name = res["database"]

            if res.get("skipped"):
                status_str = f"[yellow]PULADA: {res['error']}[/yellow]"
            elif not res.get("success"):
                status_str = f"[bold red]ROLLBACK: {res['error']}[/bold red]"
            else:
                div_count = res.get("divergent_count", 0)
                if div_count > 0:
                    status_str = f"[bold white on red] COM DIVERGÊNCIAS ({div_count} registro{'s' if div_count > 1 else ''}) [/bold white on red]"
                else:
                    status_str = "[bold green]✔ SEM DIVERGÊNCIAS[/bold green]"

            index_table.add_row(str(idx), db_name, status_str)

        console.print(index_table)
        console.print("\n" + "="*80 + "\n")

        # 2. DETALHAMENTO DAS BASES EXECUTADAS
        for idx, res in enumerate(execution_results, start=1):
            db_name = res["database"]

            if res.get("skipped") or not res.get("success"):
                continue

            div_count = res.get("divergent_count", 0)
            if div_count > 0:
                tag_status = f"[bold white on red][{div_count} registro{'s' if div_count > 1 else ''} com divergência{'s' if div_count > 1 else ''}][/bold white on red]"
            else:
                tag_status = "[bold green][sem registros com divergências][/bold green]"

            title_text = f"[{idx}] Base de Dados: {db_name} {tag_status}"

            table = Table(
                title=title_text,
                show_lines=True,
                header_style="bold magenta"
            )
            table.add_column("Nº Pedido")
            table.add_column("Filial")
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

                row_style = "bold white on red" if is_divergent else None

                table.add_row(
                    str(r["numero_pedido"]),
                    str(r.get("filial", "")),
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
            # Adicionado FILIAL logo após NUMERO_PEDIDO
            writer.writerow([
                "BASE", "STATUS", "NUMERO_PEDIDO", "FILIAL", "ITEM",
                "REGISTROS_ANTES", "REGISTROS_DEPOIS", "DIFF_REGISTROS",
                "QTD_ANTES", "QTD_DEPOIS", "DIFF_QUANTIDADE"
            ])

            for res in execution_results:
                if res.get("skipped") or not res.get("success"):
                    continue

                for r in res.get("diff_rows", []):
                    is_divergent = (r["diff_registros"] != 0 or r["diff_quantidade"] != 0)
                    status_registro = "com divergência" if is_divergent else "sem divergência"

                    writer.writerow([
                        res["database"],
                        status_registro,
                        r["numero_pedido"],
                        r.get("filial", ""),
                        r["item"],
                        r["registros_antes"],
                        r["registros_depois"],
                        r["diff_registros"],
                        r["qtd_antes"],
                        r["qtd_depois"],
                        r["diff_quantidade"]
                    ])

        console.print(f"[bold green]Relatório CSV salvo com sucesso em:[/bold green] {path}")

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
            console.print("[bold red]Erro: Biblioteca 'reportlab' ausente. Execute 'uv add reportlab'.[/bold red]")
            return

        doc = SimpleDocTemplate(str(path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = [Paragraph("Relatório Resumo de Deduplicação de Pedidos", styles['Title']), Spacer(1, 12)]

        # ÍNDICE NO PDF
        story.append(Paragraph("Índice Geral de Bases de Dados", styles['Heading2']))
        idx_data = [["Índice", "Base de Dados", "Status / Motivo"]]

        for idx, res in enumerate(execution_results, start=1):
            if res.get("skipped"):
                status_txt = f"PULADA: {res['error']}"
            elif not res.get("success"):
                status_txt = f"ROLLBACK: {res['error']}"
            else:
                div_count = res.get("divergent_count", 0)
                status_txt = f"COM DIVERGÊNCIAS ({div_count})" if div_count > 0 else "SEM DIVERGÊNCIAS"

            idx_data.append([str(idx), res["database"], status_txt])

        idx_table = RLTable(idx_data, colWidths=[50, 150, 300])
        idx_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 8)
        ]))
        story.append(idx_table)
        story.append(Spacer(1, 18))

        # DETALHAMENTO NO PDF COM COLUNA FILIAL
        for idx, res in enumerate(execution_results, start=1):
            if not res.get("success") or res.get("skipped"):
                continue

            div_count = res.get("divergent_count", 0)
            status_txt = f"[{div_count} registros com divergência]" if div_count > 0 else "[sem registros com divergências]"

            story.append(Paragraph(f"[{idx}] Base de Dados: {res['database']} {status_txt}", styles['Heading2']))
            data = [["Nº Pedido", "Filial", "Item", "Reg. Antes", "Reg. Dep.", "Diff Reg.", "Qtd Antes", "Qtd Dep.", "Diff Qtd"]]

            table_styles = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 8)
            ]

            for row_idx, r in enumerate(res["diff_rows"], start=1):
                is_divergent = (r["diff_registros"] != 0 or r["diff_quantidade"] != 0)
                data.append([
                    str(r["numero_pedido"]), str(r.get("filial", "")), str(r["item"]),
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
        console.print(f"[bold green]Relatório PDF salvo em:[/bold green] {path}")
