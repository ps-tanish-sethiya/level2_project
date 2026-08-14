"""
DevOps AI Interactive Rich CLI Entrypoint.
Provides a sleek, modern, professional terminal interface for developer build/PR diagnosis.
"""

import os
import sys
import io
import time
import logging
import argparse
from typing import Dict, Any

# Ensure project root is in sys.path for package imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Global File Logger Configuration for Entire Project
logs_dir = os.path.join(project_root, "logs")
os.makedirs(logs_dir, exist_ok=True)
log_filepath = os.path.join(logs_dir, "devsentinel.log")

# Ensure all root loggers output to logs/devsentinel.log
file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm

# Ensure stdout and stderr handle UTF-8 safely on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from agent.agent import DevSentinelAgent, AgentRunResult

console = Console()


def print_banner():
    target_repo = os.getenv("GITHUB_DEMO_REPO", "ps-tanish-sethiya/demo-target-repo")
    banner_text = Text()
    banner_text.append("🛡️  DevOps AI Agent ", style="bold cyan")
    banner_text.append("v2.0 -- Agentic Build & PR Diagnosis System\n", style="bold white")
    banner_text.append("Primary: ", style="dim white")
    banner_text.append("Google Gemini 3.5 Lite ", style="bold blue")
    banner_text.append("| Local: ", style="dim white")
    banner_text.append("Ollama llama3.2:3b ", style="bold green")
    banner_text.append("| Fallback: ", style="dim white")
    banner_text.append("Groq 70B\n", style="bold magenta")
    banner_text.append("Target Repository: ", style="dim white")
    banner_text.append(f"{target_repo}", style="bold yellow")
    from agent.mcp_client import MCPClientWrapper
    tool_count = len(MCPClientWrapper().list_tools())
    banner_text.append(f"{tool_count} Registered", style="bold cyan")

    console.print(Panel(banner_text, border_style="cyan", padding=(1, 2)))


def human_confirmation_prompt(incident_data: Dict[str, Any]) -> bool:
    """
    Sleek Rich CLI Confirmation prompt presented to human operator before state-changing write.
    """
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold cyan]Component:[/bold cyan]", incident_data.get("component", "N/A"))
    table.add_row("[bold cyan]Summary:[/bold cyan]", incident_data.get("summary", "N/A"))
    table.add_row("[bold cyan]Root Cause:[/bold cyan]", incident_data.get("root_cause", "N/A"))
    table.add_row("[bold cyan]Resolution:[/bold cyan]", incident_data.get("resolution", "N/A"))

    console.print()
    console.print(Panel(table, title="[bold yellow]⚠️  HUMAN APPROVAL REQUIRED: LOG INCIDENT[/bold yellow]", border_style="yellow"))
    
    return Confirm.ask("[bold yellow]Do you approve writing this incident record to SQLite database?[/bold yellow]", default=False)


def print_help():
    table = Table(title="Quick Diagnostic Commands", show_header=True, header_style="bold cyan", border_style="dim cyan")
    table.add_column("Command / Preset", style="bold yellow")
    table.add_column("Description", style="white")

    table.add_row("1", "Check PyYAML 5.1 CVE security vulnerabilities")
    table.add_row("2", "Diagnose flaky CI test (test_auth_token)")
    table.add_row("3", "Diagnose current repository build failure")
    table.add_row("tools", "List all 10 registered MCP Server tools")
    table.add_row("clear", "Clear screen and reprint banner")
    table.add_row("exit / q", "Quit session")
    console.print(table)


def run_cli_session(query: str = None):
    print_banner()

    agent = DevSentinelAgent(max_iterations=8)

    if query:
        _execute_query(agent, query)
        return

    console.print("[dim]Type [bold yellow]help[/bold yellow] for sample queries, [bold yellow]1-3[/bold yellow] for presets, [bold yellow]tools[/bold yellow] to list MCP tools, or [bold yellow]exit[/bold yellow] to quit.\n[/dim]")

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]DevOps AI[/bold cyan] [bold green]>[/bold green]").strip()
            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd in ("exit", "quit", "q"):
                console.print("[bold cyan]Exiting session. Goodbye![/bold cyan]")
                break
            elif cmd == "help":
                print_help()
                continue
            elif cmd == "clear":
                console.clear()
                print_banner()
                continue
            elif cmd == "tools":
                _print_tools()
                continue
            elif cmd == "1":
                user_input = "Is this PR safe to merge with PyYAML 5.1 dependency?"
            elif cmd == "2":
                user_input = "Why is test_auth_token failing intermittently on CI?"
            elif cmd == "3":
                user_input = "what is issue in the current repository?"

            _execute_query(agent, user_input)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Session closed.[/bold cyan]")
            break


def _print_tools():
    from agent.mcp_client import MCPClientWrapper
    tools = MCPClientWrapper().list_tools()
    table = Table(title="Registered MCP Server Tools", show_header=True, header_style="bold cyan", border_style="cyan")
    table.add_column("#", style="dim white", width=3)
    table.add_column("Tool Name", style="bold yellow")
    table.add_column("Description", style="white")
    table.add_column("Parameters", style="bold cyan")

    for i, t in enumerate(tools, 1):
        params = ", ".join(t['parameters']['properties'].keys())
        table.add_row(str(i), t['name'], t['description'], params)

    console.print(table)


def _execute_query(agent: DevSentinelAgent, query: str):
    import time
    console.print(Panel(f"[bold white]{query}[/bold white]", title="[bold cyan]🔍 Active Diagnostic Query[/bold cyan]", border_style="cyan"))

    start_time = time.time()
    with console.status("[bold cyan]Analyzing telemetry and executing diagnostic trajectory across MCP tools...[/bold cyan]", spinner="dots"):
        result: AgentRunResult = agent.run(
            query=query,
            confirm_callback=human_confirmation_prompt
        )
    elapsed_seconds = time.time() - start_time

    # Step Execution Log Table
    if result.steps:
        table = Table(title="⚡ Diagnostic Reaction Trajectory", show_header=True, header_style="bold blue", border_style="dim cyan")
        table.add_column("Step", style="bold cyan", justify="center", width=6)
        table.add_column("Provider", style="bold magenta", width=10)
        table.add_column("Action / Tool Call", style="bold yellow")
        table.add_column("Observation Summary", style="dim white")

        for step in result.steps:
            provider = step.provider_used.upper()
            tool = step.tool_name or "N/A"
            obs = str(step.observation) if step.observation else ""
            if len(obs) > 110:
                obs = obs[:110] + "..."
            table.add_row(f"#{step.step_number}", provider, tool, obs)

        console.print(table)
        console.print()

    # Executive Diagnosis Markdown Output
    md_report = Markdown(result.final_answer)
    console.print(Panel(md_report, title="[bold green]📋 Synthesized Diagnosis & Executive Report[/bold green]", border_style="green", padding=(1, 2)))
    console.print(f"[dim]⏱️ Latency: [bold yellow]{elapsed_seconds:.2f}s[/bold yellow] | Total Tool Calls: [bold cyan]{result.total_tool_calls}[/bold cyan] | Primary Provider: [bold green]{result.provider_used.upper()}[/bold green][/dim]\n")


def main():
    parser = argparse.ArgumentParser(description="DevOps AI Agent CLI")
    parser.add_argument("query", nargs="?", help="Optional natural language diagnosis query")
    args = parser.parse_args()

    run_cli_session(query=args.query)


if __name__ == "__main__":
    main()
