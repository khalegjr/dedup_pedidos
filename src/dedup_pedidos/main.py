from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from .analyzer import DatabaseAnalyzer
from .config import SERVER_CONFIG
from .deduplicator import TransactionalDeduplicator
from .reporter import ReportGenerator

app = typer.Typer(help="CLI de Diagnóstico e Deduplicação Transacional de Pedidos")
console = Console()

@app.command()
def start():
    console.print("[bold blue]=== Gerenciador de Duplicidades PostgreSQL ===[/bold blue]\n")

    analyzer = DatabaseAnalyzer(SERVER_CONFIG)
    console.print("Buscando bases de dados disponíveis...")
    all_dbs = analyzer.list_target_databases()

    all_groups = []
    for db in all_dbs:
        groups = analyzer.diagnose_database(db)
        if groups:
            all_groups.extend(groups)

    if not all_groups:
        console.print("[bold green]Nenhuma duplicidade encontrada no servidor![/bold green]")
        return

    mode = Prompt.ask(
        "Escolha o modo de execução",
        choices=["auto_simulacao", "auto_efetivo", "manual", "sair"],
        default="auto_simulacao"
    )

    if mode == "sair":
        return

    dedup = TransactionalDeduplicator(SERVER_CONFIG)
    execution_logs = []
    skipped_groups = []

    for group in all_groups:
        canonical_id = group.canonical_id
        is_manual_required = (group.conflict_type.name == "MANUAL_MERGE_REQUIRED")

        if mode == "manual" or is_manual_required:
            console.print(f"\n[yellow]Atenção: Pedido {group.numero_pedido} - Filial {group.filial} na base {group.db_name}[/yellow]")
            for idx, p in enumerate(group.pedidos):
                console.print(f"  [{idx + 1}] ID: {p.id} | Itens: {p.item_pedido_count} | Tem Relacionado: {p.has_item_relacionado}")

            choices = [str(i + 1) for i in range(len(group.pedidos))] + ["pular"]
            choice = Prompt.ask(
                "Selecione o número do ID a MANTER ou digite 'pular'",
                choices=choices,
                default="pular"
            )

            if choice == "pular":
                group.reason = "Ignorado pelo operador durante o fluxo manual."
                skipped_groups.append(group)
                console.print("[cyan]-> Grupo pulado.[/cyan]")
                continue
            else:
                canonical_id = group.pedidos[int(choice) - 1].id

        if not canonical_id:
            group.reason = "Sem ID canônico definido."
            skipped_groups.append(group)
            continue

        is_dry_run = True if "simulacao" in mode else False

        if not is_dry_run:
            if not Confirm.ask(f"[bold red]CONFIRMA A DELEÇÃO PERMANENTE na base {group.db_name}?[/bold red]"):
                group.reason = "Operação de deleção cancelada pelo usuário."
                skipped_groups.append(group)
                continue

        log = dedup.execute_deduplication(group, canonical_id=canonical_id, dry_run=is_dry_run)
        execution_logs.append(log)

    # Exibição do relatório em tela
    ReportGenerator.render_execution_summary(execution_logs, skipped_groups)

    # Seleção de local de salvamento
    if Confirm.ask("\nDeseja salvar o relatório detalhado em arquivo?"):
        default_dir = str(Path.cwd().resolve())
        user_path = Prompt.ask(
            "Informe o caminho/pasta para salvar (Padrão: raiz do projeto)",
            default=default_dir
        )
        ReportGenerator.export_json_report(execution_logs, skipped_groups, user_path)

if __name__ == "__main__":
    app()
