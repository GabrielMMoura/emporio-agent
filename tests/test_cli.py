from openai import APIConnectionError

from emporio_agent.agent import ToolCall, Turn
from emporio_agent.cli import chat
from emporio_agent.transcript import to_markdown


class ScriptedAgent:
    """Stands in for the LLM-backed agent; the CLI loop is what is under test."""

    def __init__(self, error=None):
        self.asked = []
        self.resets = 0
        self.error = error

    def ask(self, message):
        if self.error:
            raise self.error
        self.asked.append(message)
        return Turn(
            message,
            f"resposta para {message}",
            [ToolCall("get_store_status", "{}", '{"is_open": true}')],
        )

    def reset(self):
        self.resets += 1


def run(agent, inputs, debug=False):
    feed = iter(inputs)
    output = []

    def read(_prompt):
        try:
            return next(feed)
        except StopIteration:
            raise EOFError from None

    turns = chat(agent, read=read, write=output.append, debug=debug)
    return turns, "\n".join(output)


def test_chat_sends_messages_and_stops_on_exit_command():
    agent = ScriptedAgent()
    turns, output = run(agent, ["oi", "  ", "estão abertos?", "/sair", "nunca enviada"])
    assert agent.asked == ["oi", "estão abertos?"]
    assert len(turns) == 2
    assert "Empório: resposta para oi" in output


def test_chat_ends_on_eof():
    turns, output = run(ScriptedAgent(), ["oi"])
    assert len(turns) == 1
    assert output.endswith("Até mais!")


def test_new_conversation_command_resets_agent_and_turns():
    agent = ScriptedAgent()
    turns, _ = run(agent, ["oi", "/novo", "olá"])
    assert agent.resets == 1
    assert [t.user for t in turns] == ["olá"]


def test_debug_shows_tool_calls():
    _, output = run(ScriptedAgent(), ["oi"], debug=True)
    assert "[tool] get_store_status()" in output
    _, quiet = run(ScriptedAgent(), ["oi"])
    assert "[tool]" not in quiet


def test_api_errors_do_not_crash_the_chat():
    error = APIConnectionError(request=None)
    turns, output = run(ScriptedAgent(error=error), ["oi"])
    assert turns == []
    assert "erro ao falar com o modelo" in output


def test_transcript_markdown_lists_tools_per_turn():
    turns = [
        Turn("Oi", "Olá!\nComo posso ajudar?"),
        Turn(
            "Quanto custa o GD20?",
            "R$ 2.199,00",
            [ToolCall("search_products", '{"query": "gd20"}', '{"total_matches": 1}')],
        ),
    ]
    md = to_markdown(turns, "Preço", description="Consulta de preço.", model="m")
    assert md.startswith("# Preço\n\nConsulta de preço.\n\nModel: `m`")
    assert "> Olá!\n> Como posso ajudar?" in md
    assert "Tools called: none" in md
    assert 'Tools called: `search_products(query="gd20")`' in md
    assert '"total_matches": 1' in md
    assert md.endswith("> R$ 2.199,00\n")
