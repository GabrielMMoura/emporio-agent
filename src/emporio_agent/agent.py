"""Function-calling loop with in-memory conversation history."""

import json
from dataclasses import dataclass, field

from openai import OpenAI

from emporio_agent import clock
from emporio_agent.config import Settings
from emporio_agent.prompts import build_system_prompt
from emporio_agent.tools import execute_tool, tool_schemas

MAX_TOOL_ROUNDS = 6

FALLBACK_REPLY = (
    "Desculpa, não consegui concluir essa consulta agora. Para não te deixar sem resposta, "
    "fala com a nossa equipe pelo WhatsApp (67) 3341-4444 ou pelo e-mail "
    "contato@emporiodamusica.com.br."
)


@dataclass
class ToolCall:
    name: str
    arguments: str
    result: str


@dataclass
class Turn:
    user: str
    reply: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class Agent:
    def __init__(self, client: OpenAI, model: str, max_tool_rounds: int = MAX_TOOL_ROUNDS):
        self.client = client
        self.model = model
        self.max_tool_rounds = max_tool_rounds
        self.messages: list[dict] = []  # conversation history, without the system prompt

    def reset(self) -> None:
        self.messages = []

    def ask(self, user_message: str) -> Turn:
        """Answers one customer message, calling tools as many rounds as the model needs.

        If the API fails, the history is rolled back so the conversation stays consistent.
        """
        history_size = len(self.messages)
        self.messages.append({"role": "user", "content": user_message})
        turn = Turn(user=user_message, reply="")
        try:
            for _ in range(self.max_tool_rounds):
                message = self._complete()
                if not message.tool_calls:
                    turn.reply = message.content or ""
                    break
                self._run_tool_calls(message, turn)
            else:
                turn.reply = FALLBACK_REPLY
        except Exception:
            del self.messages[history_size:]
            raise
        self.messages.append({"role": "assistant", "content": turn.reply})
        return turn

    def _complete(self):
        system = {"role": "system", "content": build_system_prompt(clock.now())}
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[system, *self.messages],
            tools=tool_schemas(),
        )
        return response.choices[0].message

    def _run_tool_calls(self, message, turn: Turn) -> None:
        self.messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        )
        for call in message.tool_calls:
            result = execute_tool(call.function.name, call.function.arguments)
            turn.tool_calls.append(ToolCall(call.function.name, call.function.arguments, result))
            self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result})


def create_agent(settings: Settings) -> Agent:
    if not settings.api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    return Agent(client, settings.model)


def format_arguments(arguments: str) -> str:
    """Compact, readable rendering of tool-call arguments for transcripts and debug output."""
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return arguments
    return ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in parsed.items())
