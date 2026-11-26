"""Terminal chat: `uv run emporio-chat [--session ID] [--phone "(67) 9..."] [--show-tools]`."""

import argparse
import logging
import uuid
from dataclasses import replace

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from emporio_agent.agent import open_agent, tool_call_preview
from emporio_agent.config import load_settings

EXIT_WORDS = {"sair", "exit", "quit"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the Empório da Música assistant.")
    parser.add_argument("--session", help="conversation id to resume (default: new session)")
    parser.add_argument("--phone", help="simulate the customer's WhatsApp number")
    parser.add_argument("--model", help="override LLM_MODEL, e.g. openai:gpt-6-luna")
    parser.add_argument("--show-tools", action="store_true", help="print the tool calls")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    settings = load_settings()
    if args.model:
        settings = replace(settings, llm_model=args.model)
    session = args.session or uuid.uuid4().hex[:8]
    console = Console()

    with open_agent(settings) as agent:
        storage = "Postgres" if settings.database_url else "memória"
        console.print(
            Panel(
                f"Empório da Música — assistente virtual\n"
                f"modelo: {settings.llm_model} · sessão: {session} · histórico: {storage}\n"
                f"Digite 'sair' para encerrar. Retome depois com --session {session}",
                style="cyan",
            )
        )
        for role, text in agent.history(session):
            label = "[bold green]Você[/]" if role == "user" else "[bold cyan]Empório[/]"
            console.print(f"{label}: {text}", style="dim")

        while True:
            try:
                message = console.input("[bold green]Você:[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not message:
                continue
            if message.lower() in EXIT_WORDS:
                break
            with console.status("digitando..."):
                reply = agent.reply(session, message, customer_phone=args.phone)
            if args.show_tools:
                for call in reply.tool_calls:
                    console.print(f"  ⚙ {tool_call_preview(call, 200)}", style="dim yellow")
            console.print("[bold cyan]Empório:[/]")
            console.print(Markdown(reply.text))
        console.print(f"\nAté logo! Sessão salva: {session}", style="cyan")


if __name__ == "__main__":
    main()
