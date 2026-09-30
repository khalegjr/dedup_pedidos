from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from .config import DEFAULT_DB, SERVER_CONFIG
from .reporter import ReportGenerator
from .runner import ScriptRunner

app = typer.Typer(help="CLI de Deduplicação via Script SQL")
console = Console()


@app.command()
def start(script_path: str = "script/deduplicacao_pedidos.sql"):
    console.print("[bold blue]=== Gerenciador de Deduplicação via Script SQL ===[/bold blue]\n")

    try:
        runner = ScriptRunner(SERVER_CONFIG, script_path=script_path)
    except Exception as e:
        console.print(f"[bold red]Erro ao carregar o script SQL:[/bold red] {e}")
        return

    console.print("Listando bases de dados disponíveis no servidor...")
    databases = runner.list_target_databases(default_db=DEFAULT_DB)

    if not databases:
        console.print("[yellow]Nenhuma base de dados encontrada para processamento.[/yellow]")
        return

    console.print(f"Bases encontradas: [cyan]{', '.join(databases)}[/cyan]\n")

    mode = Prompt.ask(
        "Escolha o modo de execução",
        choices=["simulacao", "efetivo", "sair"],
        default="simulacao"
    )

    if mode == "sair":
        return

    is_simulation = (mode == "simulacao")

    if not is_simulation:
        if not Confirm.ask("[bold red]ATENÇÃO: As alterações serão salvas permanentemente (COMMIT). Deseja continuar?[/bold red]"):
            console.print("[yellow]Operação cancelada pelo usuário.[/yellow]")
            return

    results = []

    console.print("\n[bold]Iniciando processamento das bases...[/bold]\n")
    for db in databases:
        console.print(f"Executando na base: [bold cyan]{db}[/bold cyan]...")
        res = runner.execute_db_script(db, is_simulation=is_simulation)

        if res.get("skipped"):
            console.print(f"  └─ [yellow]Ignorada:[/yellow] {res['error']}")
        elif not res["success"]:
            console.print(f"  └─ [bold red]ROLLBACK EFETUADO:[/bold red] {res['error']}")
        else:
            diff_status = "[bold white on red]DIVERGÊNCIAS DETECTADAS[/bold white on red]" if res["has_diff_alert"] else "[green]OK[/green]"
            console.print(f"  └─ Concluído com sucesso ({'Simulação' if is_simulation else 'Efetivo'}) | Status: {diff_status}")

        results.append(res)

    # Exibe imediatamente o resultado consolidado no console
    ReportGenerator.render_console_summary(results)

    # Loop de seleção e exportação contínua de relatórios
    while True:
        report_choice = Prompt.ask(
            "\nEscolha a opção de relatório",
            choices=["tela", "csv", "pdf", "json", "finalizar"],
            default="finalizar"
        )

        if report_choice == "finalizar":
            console.print("[bold green]Aplicação finalizada com sucesso.[/bold green]")
            break

        if report_choice == "tela":
            ReportGenerator.render_console_summary(results)
        else:
            default_dir = str(Path.cwd().resolve())
            user_path = Prompt.ask(
                "Informe o caminho/diretório para salvar o arquivo",
                default=default_dir
            )

            if report_choice == "csv":
                ReportGenerator.export_csv(results, user_path)
            elif report_choice == "json":
                ReportGenerator.export_json(results, user_path)
            elif report_choice == "pdf":
                ReportGenerator.export_pdf(results, user_path)


if __name__ == "__main__":
    app()
