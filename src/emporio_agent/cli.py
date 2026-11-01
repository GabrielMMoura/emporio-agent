"""Interactive chat in the terminal.

uv run emporio-agent [--debug] [--save conversa.md]
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from openai import OpenAIError

from emporio_agent.agent import Agent, Turn, create_agent, format_arguments
from emporio_agent.config import load_settings
from emporio_agent.transcript import to_markdown

WELCOME = (
    "Empório da Música — atendimento virtual\n"
    "Digite sua mensagem. Comandos: /novo (nova conversa), /sair (encerrar)."
)


def chat(
    agent: Agent,
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
    debug: bool = False,
) -> list[Turn]:
    """Runs the conversation until /sair or end of input. Returns the turns of the last session."""
    turns: list[Turn] = []
    write(WELCOME)
    while True:
        try:
            message = read("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message:
            continue
        if message.lower() in ("/sair", "/exit", "/quit"):
            break
        if message.lower() == "/novo":
            agent.reset()
            turns = []
            write("(nova conversa)")
            continue
        try:
            turn = agent.ask(message)
        except OpenAIError as exc:
            write(f"[erro ao falar com o modelo: {exc.__class__.__name__}] Tente novamente.")
            continue
        turns.append(turn)
        if debug:
            for call in turn.tool_calls:
                write(f"  [tool] {call.name}({format_arguments(call.arguments)})")
        write(f"\nEmpório: {turn.reply}")
    write("Até mais!")
    return turns


def main() -> None:
    parser = argparse.ArgumentParser(description="Empório da Música customer service agent")
    parser.add_argument("--debug", action="store_true", help="show tool calls")
    parser.add_argument("--save", type=Path, help="save the conversation as Markdown")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    settings = load_settings()
    try:
        agent = create_agent(settings)
    except RuntimeError as exc:
        sys.exit(str(exc))

    turns = chat(agent, debug=args.debug)
    if args.save and turns:
        args.save.write_text(to_markdown(turns, "Conversa", model=settings.model), encoding="utf-8")
        print(f"Conversa salva em {args.save}")


if __name__ == "__main__":
    main()
