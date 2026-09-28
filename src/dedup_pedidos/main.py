import typer
from analyzer import DatabaseAnalyzer
from config import DB_CONFIG
from deduplicator import TransactionalDeduplicator
from reporter import ReportGenerator
from rich.console import Console
from rich.prompt import Confirm, Prompt

app = typer.Typer(help="CLI de Diagnóstico e Deduplicação Transacional de Pedidos")
console = Console()

@app.command()
def start():
    console.print("[bold blue]=== Gerenciador de Duplicidades PostgreSQL ===[/bold blue]\n")

    analyzer = DatabaseAnalyzer(DB_CONFIG)
    console.print("Buscando bases de dados disponíveis...")
    all_dbs = analyzer.list_target_databases()

    all_groups = []
    # 1. Varre bases do servidor e seleciona apenas as com duplicidades
    for db in all_dbs:
        groups = analyzer.diagnose_database(db)
        if groups:
            all_groups.extend(groups)

    if not all_groups:
        console.print("[bold green]Nenhuma duplicidade encontrada no servidor![/bold green]")
        return

    # Exibe diagnóstico na tela
    ReportGenerator.render_terminal(all_groups)

    # 2. Exportação de Relatórios
    export_choice = Prompt.ask(
        "Deseja exportar o diagnóstico?",
        choices=["tela", "csv", "pdf", "nenhum"],
        default="tela"
    )
    if export_choice == "csv":
        ReportGenerator.export_csv(all_groups, "relatorio_diagnostico.csv")
        console.print("[green]Salvo em relatorio_diagnostico.csv[/green]")
    elif export_choice == "pdf":
        ReportGenerator.export_pdf(all_groups, "relatorio_diagnostico.pdf")
        console.print("[green]Salvo em relatorio_diagnostico.pdf[/green]")

    # 3. Intervenção ou Processamento
    mode = Prompt.ask(
        "Escolha o modo de deduplicação",
        choices=["auto_simulacao", "auto_efetivo", "manual", "sair"],
        default="auto_simulacao"
    )

    if mode == "sair":
        return

    dedup = TransactionalDeduplicator(DB_CONFIG)

    for group in all_groups:
        canonical_id = group.canonical_id

        # Seleção manual de registro a manter se solicitado
        if mode == "manual" or group.conflict_type.name == "MANUAL_MERGE_REQUIRED":
            console.print(f"\n[yellow]Atencão: Grupo {group.numero_pedido} - Filial {group.filial} na base {group.db_name}[/yellow]")
            for idx, p in enumerate(group.pedidos):
                console.print(f"[{idx + 1}] ID: {p.id} | Itens: {p.item_pedido_count} | Tem Relacionado: {p.has_item_relacionado}")

            choice = int(Prompt.ask("Selecione o número do registro a SER PRESERVADO", default="1"))
            canonical_id = group.pedidos[choice - 1].id

        if not canonical_id:
            console.print(f"[red]Ignorando grupo {group.numero_pedido} sem registro selecionado.[/red]")
            continue

        is_dry_run = True if "simulacao" in mode else False

        if not is_dry_run:
            if not Confirm.ask(f"[bold red]CONFIRMA A DELEÇÃO PERMANENTE na base {group.db_name}?[/bold red]"):
                continue

        # Executa processo transacional
        log = dedup.execute_deduplication(group, canonical_id=canonical_id, dry_run=is_dry_run)

        console.print(f"[bold]Resultado ({log['status']}):[/bold] {log['deleted_headers']} cabeçalho(s) e {log['deleted_item_pedidos']} item(ns) removidos.")
        if is_dry_run:
            console.print("[cyan]* Modelação em Simulação: Nenhum dado foi alterado permanentemente no BD.[/cyan]")

if __name__ == "__main__":
    app()
